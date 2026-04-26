import asyncio
import audioop
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from openai import OpenAI

try:
    import edge_tts
except Exception:  # pragma: no cover
    edge_tts = None

try:
    import imageio_ffmpeg  # type: ignore
except Exception:  # pragma: no cover
    imageio_ffmpeg = None

try:
    import opuslib
except Exception:  # pragma: no cover
    opuslib = None

try:
    from faster_whisper import WhisperModel
except Exception:  # pragma: no cover
    WhisperModel = None

try:
    from vosk import KaldiRecognizer, Model as VoskModel, SetLogLevel
except Exception:  # pragma: no cover
    KaldiRecognizer = None
    SetLogLevel = None
    VoskModel = None


def _load_env_file(file_path: Path) -> None:
    if not file_path.exists():
        return

    for line in file_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (key not in os.environ or not os.environ.get(key)):
            os.environ[key] = value


_BASE_DIR = Path(__file__).resolve().parent
_load_env_file(_BASE_DIR / ".env")
_load_env_file(_BASE_DIR / ".en")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name, str(default))
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = _env(name, str(default))
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name, "1" if default else "0").lower()
    return value in ("1", "true", "yes", "on")


APP_HOST = _env("GATEWAY_HOST", "127.0.0.1")
APP_PORT = int(_env("GATEWAY_PORT", "8787"))
WS_TOKEN = _env("WS_TOKEN", "local-dev-token")
WS_PUBLIC_URL = _env("WS_PUBLIC_URL", f"ws://{APP_HOST}:{APP_PORT}/xiaokang/v1/")
TTS_VOICE = _env("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
TTS_RATE = _env("TTS_RATE", "+0%")
TTS_PITCH = _env("TTS_PITCH", "+2Hz")
TTS_VOLUME = _env("TTS_VOLUME", "+0%")
TTS_EXPRESSIVE = _env_bool("TTS_EXPRESSIVE", True)
TTS_ALLOW_FALLBACK = _env_bool("TTS_ALLOW_FALLBACK", False)
TTS_SAPI_RATE = _env_int("TTS_SAPI_RATE", -2)
TTS_SAPI_VOLUME = _env_int("TTS_SAPI_VOLUME", 95)
TTS_SAPI_PITCH = _env_int("TTS_SAPI_PITCH", 4)
TTS_SAPI_XML = _env_bool("TTS_SAPI_XML", True)
ESPEAK_VOICE = _env("ESPEAK_VOICE", "zh")
ASR_MODEL = _env("ASR_MODEL", "whisper-1")
ASR_BACKEND = _env("ASR_BACKEND", "vosk")
ASR_VOSK_STREAMING = _env_bool("ASR_VOSK_STREAMING", True)
ASR_TRIM_SILENCE = _env_bool("ASR_TRIM_SILENCE", True)
ASR_SILENCE_THRESHOLD = _env_int("ASR_SILENCE_THRESHOLD", 700)
ASR_KEEP_TAIL_MS = _env_int("ASR_KEEP_TAIL_MS", 180)
ASR_MIN_AUDIO_MS = _env_int("ASR_MIN_AUDIO_MS", 250)
WHISPER_MODEL_SIZE = _env("WHISPER_MODEL_SIZE", "tiny")
WHISPER_DEVICE = _env("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = _env("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_LANGUAGE = _env("WHISPER_LANGUAGE", "zh")
WHISPER_BEAM_SIZE = int(_env("WHISPER_BEAM_SIZE", "1") or 1)
WHISPER_CPU_THREADS = int(_env("WHISPER_CPU_THREADS", "4") or 4)
VOSK_MODEL_PATH = _env(
    "VOSK_MODEL_PATH", str(_BASE_DIR / "models" / "vosk-model-small-cn-0.22")
)

VOLC_API_KEY = _env("VOLC_API_KEY")
VOLC_MODEL = _env("VOLC_MODEL", "ark-code-latest")
VOLC_OPENAI_BASE_URL = _env(
    "VOLC_OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"
)
LLM_TEMPERATURE = _env_float("LLM_TEMPERATURE", 0.2)
LLM_MAX_TOKENS = _env_int("LLM_MAX_TOKENS", 180)
LLM_STREAMING = _env_bool("LLM_STREAMING", True)
STREAM_TTS_CHUNK_CHARS = _env_int("STREAM_TTS_CHUNK_CHARS", 24)
STREAM_TTS_MIN_CHARS = _env_int("STREAM_TTS_MIN_CHARS", STREAM_TTS_CHUNK_CHARS)
STREAM_TTS_MAX_CHARS = _env_int(
    "STREAM_TTS_MAX_CHARS", max(STREAM_TTS_MIN_CHARS + 12, STREAM_TTS_MIN_CHARS * 2)
)
AUDIO_SEND_REALTIME = _env_bool("AUDIO_SEND_REALTIME", False)
TTS_PREROLL_MS = max(0, _env_int("TTS_PREROLL_MS", 300))
LLM_THINKING_TYPE = _env("LLM_THINKING_TYPE", "disabled").lower() or "disabled"
INJECT_CURRENT_TIME = _env_bool("INJECT_CURRENT_TIME", True)
CURRENT_TIMEZONE = _env("CURRENT_TIMEZONE", "Asia/Shanghai")
FFMPEG_PATH = _env("FFMPEG_PATH", "")


def _build_client() -> OpenAI | None:
    if not VOLC_API_KEY:
        return None
    return OpenAI(api_key=VOLC_API_KEY, base_url=VOLC_OPENAI_BASE_URL)


def _resolve_ffmpeg_path() -> str | None:
    """查找可用的 ffmpeg，优先使用显式配置，再回退到系统 PATH 和 imageio_ffmpeg。"""
    if FFMPEG_PATH and Path(FFMPEG_PATH).exists():
        return FFMPEG_PATH

    found = shutil.which("ffmpeg")
    if found:
        return found

    if imageio_ffmpeg is not None:
        try:
            exe_path = imageio_ffmpeg.get_ffmpeg_exe()
            if exe_path and Path(exe_path).exists():
                return exe_path
        except Exception:
            pass

    return None


def _build_system_prompt() -> str:
    """构造给大模型的系统提示词，并按需注入当前设备时间。"""
    base_prompt = "你是小康，一个简洁、友好的中文语音助手，优先给出可执行答案。"
    if not INJECT_CURRENT_TIME:
        return base_prompt

    now = None
    if ZoneInfo is not None and CURRENT_TIMEZONE:
        try:
            now = datetime.now(ZoneInfo(CURRENT_TIMEZONE))
        except Exception:
            now = None

    if now is None:
        now = datetime.now()

    current_time_text = now.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"{base_prompt} "
        f"当前设备时间（{CURRENT_TIMEZONE or 'local'}）是：{current_time_text}。"
        "当用户询问今天或现在时间时，优先依据该时间回答。"
    )


openai_client = _build_client()
app = FastAPI(title="xiaokang local gateway", version="0.1.0")
logger = logging.getLogger("local_gateway")
_whisper_model = None
_vosk_model = None
_tts_backend_logged: set[str] = set()

if SetLogLevel is not None:
    try:
        SetLogLevel(-1)
    except Exception:
        pass


def _check_auth_header(auth_value: str | None) -> None:
    expected = f"Bearer {WS_TOKEN}"
    if not auth_value or auth_value != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _extract_auth_from_ws(websocket: WebSocket) -> str:
    return websocket.headers.get("authorization", "")


def _call_model(user_text: str) -> str:
    """非流式调用大模型，作为流式调用失败时的回退路径。"""
    if not user_text:
        return "你还没有输入内容。"

    if openai_client is None:
        return (
            "本地网关已连接，但未配置 VOLC_API_KEY。"
            "请在 local_gateway/.env 中填写后重启网关。"
        )

    kwargs: dict[str, Any] = {
        "model": VOLC_MODEL,
        "messages": [
            {
                "role": "system",
                "content": _build_system_prompt(),
            },
            {"role": "user", "content": user_text},
        ],
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
    }

    if LLM_THINKING_TYPE in ("enabled", "disabled"):
        kwargs["extra_body"] = {"thinking": {"type": LLM_THINKING_TYPE}}

    result = openai_client.chat.completions.create(**kwargs)
    return (result.choices[0].message.content or "").strip() or "我暂时没有生成内容。"


def _extract_delta_text(stream_chunk: Any) -> str:
    choices = getattr(stream_chunk, "choices", None)
    if not choices:
        return ""

    delta = getattr(choices[0], "delta", None)
    if delta is None:
        return ""

    content = getattr(delta, "content", None)
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                value = part.get("text") or ""
            else:
                value = getattr(part, "text", "")
            if value:
                texts.append(str(value))
        return "".join(texts)

    return ""


def _normalize_user_text(user_text: str) -> str:
    """清理唤醒词前缀，并把常见设备别名统一成内部容易识别的写法。"""
    text = (user_text or "").strip()
    if not text:
        return text

    prefix_patterns = [
        r"^小康小康[，,：: ]*",
        r"^小康[，,：: ]*",
    ]
    for pattern in prefix_patterns:
        text = re.sub(pattern, "", text)

    alias_map = {
        "计算机": "电脑",
        "主机": "电脑",
        "b机": "B机",
        "B机": "B机",
        "无人飞机": "无人机",
        "飞机": "无人机",
        "飞行器": "无人机",
    }
    for source, target in alias_map.items():
        text = text.replace(source, target)

    return text.strip() or (user_text or "").strip()


def _load_remote_control_settings() -> dict[str, Any]:
    """读取远程控制配置，配置缺失时使用安全的默认值。"""
    default_settings: dict[str, Any] = {
        "ENABLED": False,
        "DEFAULT_TARGET_IP": "",
        "DEFAULT_PORT": 5005,
        "DEFAULT_TIMEOUT": 5,
        "COMMAND_PATH": "/command",
    }

    config_path = _BASE_DIR.parent / "config" / "config.json"
    if not config_path.exists():
        return default_settings

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        remote_cfg = config_data.get("REMOTE_CONTROL") or {}
        if not isinstance(remote_cfg, dict):
            return default_settings

        merged = default_settings.copy()
        merged.update(remote_cfg)
        return merged
    except Exception:
        return default_settings


def _send_remote_command_local(action: str, args_json: str = "{}") -> str:
    """从本地网关直接向局域网设备发送控制指令。"""
    remote_cfg = _load_remote_control_settings()
    if not bool(remote_cfg.get("ENABLED", False)):
        return "远程控制未启用，请在 config/config.json 中将 REMOTE_CONTROL.ENABLED 设为 true"

    target_ip = str(remote_cfg.get("DEFAULT_TARGET_IP", "") or "").strip()
    if not target_ip:
        return "未配置 B 机 IP，请设置 config/config.json 中 REMOTE_CONTROL.DEFAULT_TARGET_IP"

    try:
        port = int(remote_cfg.get("DEFAULT_PORT", 5005) or 5005)
    except Exception:
        port = 5005

    try:
        timeout = float(remote_cfg.get("DEFAULT_TIMEOUT", 5) or 5)
    except Exception:
        timeout = 5.0

    command_path = str(remote_cfg.get("COMMAND_PATH", "/command") or "/command")
    if not command_path.startswith("/"):
        command_path = "/" + command_path

    try:
        args_obj = json.loads(args_json or "{}")
        if not isinstance(args_obj, dict):
            return "参数必须是 JSON 对象，例如 {\"value\":60}"
    except Exception as exc:
        return f"参数 JSON 解析失败: {exc}"

    payload = {
        "id": datetime.now().strftime("cmd-%Y%m%d-%H%M%S"),
        "action": action,
        "args": args_obj,
    }
    url = f"http://{target_ip}:{port}{command_path}"

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="ignore")
            logger.info(
                "远程指令发送成功: target=%s:%s action=%s status=%s response=%s",
                target_ip,
                port,
                action,
                response.status,
                body,
            )
            return "发送成功"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        logger.error(
            "远程指令 HTTP 失败: target=%s:%s action=%s code=%s body=%s",
            target_ip,
            port,
            action,
            exc.code,
            body,
        )
        return "发送失败"
    except Exception as exc:
        logger.error(
            "远程指令发送失败: target=%s:%s action=%s error=%s",
            target_ip,
            port,
            action,
            exc,
        )
        return "发送失败"


def _infer_remote_action_from_text(text: str) -> tuple[str, str] | None:
    """从自然语言中推断远程动作与参数 JSON。"""
    clean_text = (text or "").strip()
    if not clean_text:
        return None

    volume_match = re.search(r"(?:音量|声音)[^0-9]{0,8}(\d{1,3})", clean_text)
    if volume_match:
        volume = int(volume_match.group(1))
        volume = max(0, min(100, volume))
        return "set_volume", json.dumps({"value": volume}, ensure_ascii=False)

    natural_map = [
        ("前进", "前进"),
        ("后退", "后退"),
        ("左转", "左转"),
        ("右转", "右转"),
        ("起飞", "起飞"),
        ("降落", "降落"),
        ("下降", "下降"),
        ("停止", "停止"),
        ("暂停", "暂停"),
        ("继续", "继续"),
        ("开始", "开始"),
        ("开灯", "开灯"),
        ("关灯", "关灯"),
        ("测试连接", "ping"),
    ]
    for keyword, action in natural_map:
        if keyword in clean_text:
            return action, json.dumps({"text": keyword}, ensure_ascii=False)

    return None


def _try_handle_remote_b_command(user_text: str) -> str | None:
    """识别“让电脑/无人机执行...”这类自然语言，并优先在本地完成远程控制。"""
    text = (user_text or "").strip()
    if not text:
        return None

    trigger_words = (
        "电脑",
        "给电脑",
        "让电脑",
        "B机",
        "给B机",
        "让B机",
        "无人机",
        "给无人机",
        "让无人机",
        "飞机",
        "给飞机",
        "让飞机",
        "飞行器",
        "给飞行器",
        "让飞行器",
    )
    if not any(word in text for word in trigger_words):
        return None

    action_patterns = [
        r"action\s*(?:是|=|为)?\s*([a-zA-Z_][\w\-]*)",
        r"(?:给电脑|让电脑|给B机|让B机|给无人机|让无人机)(?:发送指令|执行)\s*[：: ]\s*([a-zA-Z_][\w\-]*)",
        r"(?:给飞机|让飞机|给飞行器|让飞行器)(?:发送指令|执行)\s*[：: ]\s*([a-zA-Z_][\w\-]*)",
    ]

    action = ""
    for pattern in action_patterns:
        matched = re.search(pattern, text, flags=re.IGNORECASE)
        if matched:
            action = matched.group(1).strip()
            break

    if not action:
        inferred = _infer_remote_action_from_text(text)
        if inferred:
            action, args_json = inferred
        else:
            return "我识别到你要发送远程控制指令，但没有识别出具体动作。你可以说：小康小康让无人机起飞。"
    else:
        args_json = "{}"

    args_match = re.search(r"参数\s*[：:]\s*(\{.*\})", text)
    if not args_match:
        args_match = re.search(r"(\{.*\})", text)
    if args_match:
        args_json = args_match.group(1).strip()

    result_text = _send_remote_command_local(action=action, args_json=args_json)
    return result_text


def _iter_model_stream(user_text: str):
    """流式调用大模型，把增量文本逐段产出，便于边生成边合成语音。"""
    if not user_text:
        yield "你还没有输入内容。"
        return

    if openai_client is None:
        yield (
            "本地网关已连接，但未配置 VOLC_API_KEY。"
            "请在 local_gateway/.env 中填写后重启网关。"
        )
        return

    kwargs: dict[str, Any] = {
        "model": VOLC_MODEL,
        "messages": [
            {
                "role": "system",
                "content": _build_system_prompt(),
            },
            {"role": "user", "content": user_text},
        ],
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
        "stream": True,
    }

    if LLM_THINKING_TYPE in ("enabled", "disabled"):
        kwargs["extra_body"] = {"thinking": {"type": LLM_THINKING_TYPE}}

    stream = openai_client.chat.completions.create(**kwargs)

    for chunk in stream:
        delta_text = _extract_delta_text(chunk)
        if delta_text:
            yield delta_text

async def _stream_model_deltas(user_text: str):
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def worker() -> None:
        try:
            for delta_text in _iter_model_stream(user_text):
                loop.call_soon_threadsafe(queue.put_nowait, ("delta", delta_text))
            loop.call_soon_threadsafe(queue.put_nowait, ("done", ""))
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))

    threading.Thread(target=worker, daemon=True).start()

    while True:
        event_type, payload = await queue.get()
        if event_type == "delta":
            yield payload
            continue
        if event_type == "error":
            raise RuntimeError(payload)
        break


def _split_stream_text(
    buffer: str, min_chars: int, max_chars: int
) -> tuple[list[str], str]:
    segments: list[str] = []
    hard_separators = "。！？!?\n"
    soft_separators = "，,、；;"
    min_chars = max(4, min_chars)
    max_chars = max(min_chars + 1, max_chars)

    while len(buffer) >= max_chars:
        candidate_index = -1
        for index, char in enumerate(buffer[:max_chars]):
            if char in hard_separators and index + 1 >= min_chars:
                candidate_index = index

        if candidate_index == -1:
            piece = buffer[:max_chars].strip()
            buffer = buffer[max_chars:]
        else:
            piece = buffer[: candidate_index + 1].strip()
            buffer = buffer[candidate_index + 1 :]

        if piece:
            segments.append(piece)

    while True:
        split_index = -1
        for index, char in enumerate(buffer):
            if char in hard_separators and index + 1 >= min_chars:
                split_index = index
                break

        if split_index == -1 and len(buffer) >= min_chars + 20:
            for index, char in enumerate(buffer):
                if char in soft_separators and index + 1 >= min_chars:
                    split_index = index
                    break

        if split_index != -1:
            piece = buffer[: split_index + 1].strip()
            buffer = buffer[split_index + 1 :]
            if piece:
                segments.append(piece)
            continue

        break

    return segments, buffer


def _parse_percent_rate(rate_text: str, default_percent: int = 0) -> int:
    match = re.search(r"([+-]?\d+)", rate_text or "")
    if not match:
        return default_percent
    try:
        return int(match.group(1))
    except Exception:
        return default_percent


def _normalize_tts_text(text: str) -> str:
    clean = (text or "").strip()
    if not clean:
        return clean

    clean = re.sub(r"`{1,3}.*?`{1,3}", "", clean)
    clean = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", clean)
    clean = re.sub(r"https?://\S+", "", clean)
    clean = re.sub(r"\s+", " ", clean)
    clean = clean.replace("AI", "人工智能").replace("API", "接口")
    clean = re.sub(r"([，。！？；])\1+", r"\1", clean)

    if clean and clean[-1] not in "。！？!?":
        clean += "。"
    return clean


def _choose_segment_rate(text: str) -> str:
    base = _parse_percent_rate(TTS_RATE, 0)
    segment = (text or "").strip()
    if not segment:
        return f"{base:+d}%"

    delta = 0
    if segment.endswith(("!", "！")):
        delta += 10
    elif segment.endswith(("?", "？")):
        delta += 5
    elif segment.endswith(("。", ";", "；")):
        delta -= 2

    if len(segment) >= 38:
        delta -= 2
    if "请" in segment or "建议" in segment:
        delta -= 2

    value = max(-25, min(35, base + delta))
    return f"{value:+d}%"

def _rate_to_sapi_value(rate_text: str) -> int:
    percent = _parse_percent_rate(rate_text, TTS_SAPI_RATE * 5)
    value = int(round(percent / 5))
    return max(-10, min(10, value))


def _escape_xml(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _build_sapi_xml_text(text: str, rate_value: int) -> str:
    safe = _escape_xml(_normalize_tts_text(text))
    # 鎻掑叆鍙劅鐭ョ殑鍋滈】锛岄檷浣庘€滆繛鐝犵偖寮忊€濇満鍣ㄦ劅
    safe = re.sub(r"([锛?])", r"\1<silence msec=\"180\"/>", safe)
    safe = re.sub(r"([銆傦紒锛??锛?])", r"\1<silence msec=\"260\"/>", safe)

    pitch_value = max(-10, min(10, int(TTS_SAPI_PITCH)))
    volume_value = max(60, min(100, int(TTS_SAPI_VOLUME)))
    return (
        "<speak version=\"1.0\" xml:lang=\"zh-CN\">"
        f"<volume level=\"{volume_value}\">"
        f"<rate speed=\"{rate_value}\">"
        f"<pitch middle=\"{pitch_value}\">{safe}</pitch>"
        "</rate></volume></speak>"
    )


def _log_tts_backend_once(name: str, detail: str = "") -> None:
    key = f"{name}:{detail}"
    if key in _tts_backend_logged:
        return
    _tts_backend_logged.add(key)
    if detail:
        logger.info("TTS backend=%s (%s)", name, detail)
    else:
        logger.info("TTS backend=%s", name)


def _build_wav_from_pcm(pcm_data: bytes, sample_rate: int) -> bytes:
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return wav_buffer.getvalue()


def _trim_pcm_silence(
    pcm_data: bytes,
    sample_rate: int,
    silence_threshold: int,
    keep_tail_ms: int,
    min_audio_ms: int,
) -> bytes:
    if len(pcm_data) < 2:
        return pcm_data

    frame_samples = max(1, int(sample_rate * 0.01))
    frame_bytes = frame_samples * 2
    total_frames = len(pcm_data) // frame_bytes
    if total_frames <= 1:
        return pcm_data

    first_voice = -1
    last_voice = -1

    for frame_index in range(total_frames):
        start = frame_index * frame_bytes
        end = start + frame_bytes
        frame = pcm_data[start:end]
        peak = 0
        for offset in range(0, len(frame), 2):
            sample = int.from_bytes(
                frame[offset : offset + 2], byteorder="little", signed=True
            )
            value = abs(sample)
            if value > peak:
                peak = value
        if peak >= silence_threshold:
            if first_voice == -1:
                first_voice = frame_index
            last_voice = frame_index

    if first_voice == -1 or last_voice == -1:
        return pcm_data

    keep_tail_frames = max(0, int(keep_tail_ms / 10))
    start_frame = first_voice
    end_frame = min(total_frames, last_voice + 1 + keep_tail_frames)

    min_frames = max(1, int(min_audio_ms / 10))
    if end_frame - start_frame < min_frames:
        end_frame = min(total_frames, start_frame + min_frames)

    start_byte = start_frame * frame_bytes
    end_byte = min(len(pcm_data), end_frame * frame_bytes)
    trimmed = pcm_data[start_byte:end_byte]
    return trimmed if trimmed else pcm_data


def _transcribe_wav_bytes_online(wav_bytes: bytes) -> str:
    if openai_client is None:
        raise RuntimeError("未配置 VOLC_API_KEY，无法进行语音识别")

    wav_stream = io.BytesIO(wav_bytes)
    wav_stream.name = "mic.wav"

    result = openai_client.audio.transcriptions.create(
        model=ASR_MODEL,
        file=wav_stream,
    )

    text = getattr(result, "text", None)
    if text is None and isinstance(result, dict):
        text = result.get("text")
    text = (text or "").strip()
    if not text:
        raise RuntimeError("ASR 未返回有效文本")
    return text


def _get_offline_whisper_model():
    global _whisper_model

    if _whisper_model is not None:
        return _whisper_model

    if WhisperModel is None:
        raise RuntimeError("未安装 faster-whisper，请先安装依赖")

    download_root = str(_BASE_DIR / "cache" / "whisper")
    os.makedirs(download_root, exist_ok=True)
    _whisper_model = WhisperModel(
        WHISPER_MODEL_SIZE,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
        download_root=download_root,
        cpu_threads=max(1, WHISPER_CPU_THREADS),
    )
    return _whisper_model


def _transcribe_wav_bytes_offline(wav_bytes: bytes) -> str:
    model = _get_offline_whisper_model()

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(wav_bytes)
            temp_path = temp_file.name

        segments, _info = model.transcribe(
            temp_path,
            language=WHISPER_LANGUAGE or None,
            beam_size=WHISPER_BEAM_SIZE,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = "".join(segment.text for segment in segments).strip()
        if not text:
            raise RuntimeError("离线 ASR 未识别到有效文本")
        return text
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _get_vosk_model():
    global _vosk_model

    if _vosk_model is not None:
        return _vosk_model

    if VoskModel is None:
        raise RuntimeError("未安装 vosk，请先安装依赖")

    # 允许 .env 写相对路径；统一按 local_gateway 目录解析，避免启动目录不同导致找不到模型。
    model_path = Path(VOSK_MODEL_PATH)
    if not model_path.is_absolute():
        model_path = _BASE_DIR / model_path
    if not model_path.exists():
        raise RuntimeError(
            f"Vosk 模型目录不存在: {model_path}。请下载并解压模型后设置 VOSK_MODEL_PATH"
        )

    _vosk_model = VoskModel(str(model_path))
    return _vosk_model


def _transcribe_wav_bytes_vosk(wav_bytes: bytes) -> str:
    model = _get_vosk_model()
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        if channels != 1 or sample_width != 2:
            raise RuntimeError(
                f"Vosk 需要 16-bit 单声道 WAV，当前为 {channels}ch/{sample_width * 8}bit"
            )

        recognizer = KaldiRecognizer(model, float(sample_rate))
        recognizer.SetWords(False)

        while True:
            chunk = wav_file.readframes(4000)
            if not chunk:
                break
            recognizer.AcceptWaveform(chunk)

    final_result = json.loads(recognizer.FinalResult() or "{}")
    text = (final_result.get("text") or "").strip()
    if not text:
        raise RuntimeError("Vosk 未识别到有效文本")
    return text


def _extract_vosk_text(result_json: str) -> str:
    try:
        result = json.loads(result_json or "{}")
    except json.JSONDecodeError:
        return ""
    return (result.get("text") or "").strip()


async def _transcribe_wav_bytes(wav_bytes: bytes) -> str:
    backend = (ASR_BACKEND or "").strip().lower()

    if backend in ("vosk", "offline_vosk"):
        return await asyncio.to_thread(_transcribe_wav_bytes_vosk, wav_bytes)
    if backend in ("offline", "offline_whisper", "whisper"):
        return await asyncio.to_thread(_transcribe_wav_bytes_offline, wav_bytes)
    if backend in ("online", "online_openai", "openai"):
        return await asyncio.to_thread(_transcribe_wav_bytes_online, wav_bytes)

    raise RuntimeError(f"不支持的 ASR_BACKEND: {ASR_BACKEND}")


async def _reply_from_user_text(
    ws: WebSocket,
    user_text: str,
    sample_rate: int,
    frame_duration_ms: int,
) -> None:
    normalized_text = _normalize_user_text(user_text)

    remote_result = await asyncio.to_thread(_try_handle_remote_b_command, normalized_text)
    if remote_result is not None:
        await _send_dialogue_with_audio(
            ws,
            user_text,
            remote_result,
            sample_rate=sample_rate,
            frame_duration_ms=frame_duration_ms,
        )
        return

    if not LLM_STREAMING:
        answer = await asyncio.to_thread(_call_model, normalized_text)
        await _send_dialogue_with_audio(
            ws,
            user_text,
            answer,
            sample_rate=sample_rate,
            frame_duration_ms=frame_duration_ms,
        )
        return

    await _send_dialogue(ws, user_text, "")
    await ws.send_text(json.dumps({"type": "tts", "state": "start", "text": ""}))

    all_parts: list[str] = []
    pending_text = ""
    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    frames_queue: asyncio.Queue[list[bytes] | None] = asyncio.Queue()

    async def tts_producer() -> None:
        while True:
            segment = await text_queue.get()
            if segment is None:
                break
            try:
                segment_rate = _choose_segment_rate(segment) if TTS_EXPRESSIVE else None
                frames = await _synthesize_tts_opus_frames(
                    segment,
                    sample_rate=sample_rate,
                    frame_duration_ms=frame_duration_ms,
                    rate_override=segment_rate,
                )
                if frames:
                    await frames_queue.put(frames)
            except Exception as exc:
                logger.error("流式语音片段合成失败: %s", exc)

        await frames_queue.put(None)

    async def audio_sender() -> None:
        while True:
            frames = await frames_queue.get()
            if frames is None:
                break
            await _send_opus_frames(ws, frames, frame_duration_ms)

    producer_task = asyncio.create_task(tts_producer())
    sender_task = asyncio.create_task(audio_sender())

    try:
        async for delta_text in _stream_model_deltas(normalized_text):
            if not delta_text:
                continue

            all_parts.append(delta_text)
            pending_text += delta_text
            segments, pending_text = _split_stream_text(
                pending_text,
                min_chars=STREAM_TTS_MIN_CHARS,
                max_chars=STREAM_TTS_MAX_CHARS,
            )
            for segment in segments:
                await text_queue.put(segment)

        if pending_text.strip():
            await text_queue.put(pending_text.strip())

        await text_queue.put(None)
        await producer_task
        await sender_task

        await asyncio.sleep(0.08)
        answer = "".join(all_parts).strip() or "我暂时没有生成内容。"
    except Exception as exc:
        logger.error("流式模型调用失败，回退单次调用: %s", exc)
        if not producer_task.done():
            producer_task.cancel()
        if not sender_task.done():
            sender_task.cancel()
        answer = await asyncio.to_thread(_call_model, normalized_text)
        try:
            answer_rate = _choose_segment_rate(answer) if TTS_EXPRESSIVE else None
            frames = await _synthesize_tts_opus_frames(
                answer,
                sample_rate=sample_rate,
                frame_duration_ms=frame_duration_ms,
                rate_override=answer_rate,
            )
            await _send_opus_frames(ws, frames, frame_duration_ms)
            await asyncio.sleep(0.08)
        except Exception as send_exc:
            logger.error("回退语音发送失败: %s", send_exc)

    await ws.send_text(json.dumps({"type": "tts", "state": "stop", "text": answer}))


async def _send_dialogue(ws: WebSocket, user_text: str, answer_text: str) -> None:
    await ws.send_text(json.dumps({"type": "stt", "text": user_text}))
    await ws.send_text(json.dumps({"type": "llm", "emotion": "neutral"}))


async def _send_opus_frames(
    ws: WebSocket,
    frames: list[bytes],
    frame_duration_ms: int,
) -> None:
    """发送TTS音频帧。

    本地PC客户端有自己的播放队列，尽快发送已合成音频可以避免队列被调度抖动饿空。
    如需模拟真实设备的实时推送，可在 .env 中设置 AUDIO_SEND_REALTIME=true。
    """
    frame_interval = max(frame_duration_ms, 20) / 1000.0
    for frame in frames:
        await ws.send_bytes(frame)
        if AUDIO_SEND_REALTIME:
            await asyncio.sleep(frame_interval)
        else:
            await asyncio.sleep(0)
    if not AUDIO_SEND_REALTIME and frames:
        await asyncio.sleep((len(frames) * frame_interval) + 0.08)


async def _synthesize_mp3(text: str, rate_override: str | None = None) -> bytes:
    if edge_tts is None:
        raise RuntimeError("edge-tts 未安装")

    prepared_text = _normalize_tts_text(text)
    if not prepared_text:
        raise RuntimeError("TTS 输入文本为空")

    communicator = edge_tts.Communicate(
        text=prepared_text,
        voice=TTS_VOICE,
        rate=rate_override or TTS_RATE,
        pitch=TTS_PITCH,
        volume=TTS_VOLUME,
    )
    chunks: list[bytes] = []
    async for item in communicator.stream():
        if item.get("type") == "audio":
            chunks.append(item["data"])

    audio = b"".join(chunks)
    if not audio:
        raise RuntimeError("TTS 未返回音频数据")
    return audio


async def _synthesize_wav_with_espeak(text: str) -> bytes:
    espeak_command = shutil.which("espeak-ng") or shutil.which("espeak")
    if not espeak_command:
        raise RuntimeError("系统未安装 espeak/espeak-ng")

    process = await asyncio.create_subprocess_exec(
        espeak_command,
        "--stdout",
        "-v",
        ESPEAK_VOICE,
        text,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_data, stderr_data = await process.communicate()

    if process.returncode != 0:
        error_text = stderr_data.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"espeak 合成失败: {error_text}")
    if not stdout_data:
        raise RuntimeError("espeak 未返回音频数据")
    return stdout_data


async def _synthesize_wav_with_windows_sapi(
    text: str, rate_override: str | None = None
) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Windows SAPI 仅在 Windows 可用")

    def _sapi_to_wav() -> bytes:
        try:
            import win32com.client  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"win32com 不可用: {exc}")

        output_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                output_path = temp_file.name

            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            # SSFMCreateForWrite = 3
            stream.Open(output_path, 3, False)

            speaker = win32com.client.Dispatch("SAPI.SpVoice")

            # Prefer a Chinese voice when available.
            try:
                voices = speaker.GetVoices()
                selected = None
                for i in range(voices.Count):
                    desc = str(voices.Item(i).GetDescription() or "").lower()
                    if ("chinese" in desc) or ("zh" in desc) or ("huihui" in desc):
                        selected = voices.Item(i)
                        break
                if selected is not None:
                    speaker.Voice = selected
            except Exception:
                pass

            rate_value = _rate_to_sapi_value(rate_override or str(TTS_SAPI_RATE * 5))
            try:
                speaker.Rate = rate_value
            except Exception:
                pass

            try:
                speaker.Volume = max(0, min(100, int(TTS_SAPI_VOLUME)))
            except Exception:
                pass

            speaker.AudioOutputStream = stream
            safe_text = _normalize_tts_text(text)
            if TTS_SAPI_XML:
                xml_text = _build_sapi_xml_text(safe_text, rate_value)
                try:
                    # SPF_IS_XML = 8
                    speaker.Speak(xml_text, 8)
                except Exception:
                    speaker.Speak(safe_text)
            else:
                speaker.Speak(safe_text)
            stream.Close()

            data = Path(output_path).read_bytes()
            if not data:
                raise RuntimeError("SAPI 未生成音频数据")
            return data
        finally:
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass

    return await asyncio.to_thread(_sapi_to_wav)


async def _synthesize_tts_audio(text: str, rate_override: str | None = None) -> bytes:
    backend_errors: list[str] = []

    try:
        data = await _synthesize_mp3(text, rate_override=rate_override)
        _log_tts_backend_once("edge_tts", TTS_VOICE)
        return data
    except Exception as exc:
        backend_errors.append(f"edge_tts={exc}")
        if not TTS_ALLOW_FALLBACK:
            logger.error("edge_tts failed and TTS fallback is disabled: %s", exc)
            raise RuntimeError(
                "edge_tts 合成失败，已禁用机械声回退；请检查网络或 edge-tts 安装"
            ) from exc

    try:
        data = await _synthesize_wav_with_espeak(text)
        _log_tts_backend_once("espeak", ESPEAK_VOICE)
        return data
    except Exception as exc:
        backend_errors.append(f"espeak={exc}")

    try:
        data = await _synthesize_wav_with_windows_sapi(
            text,
            rate_override=rate_override,
        )
        _log_tts_backend_once("windows_sapi", f"xml={TTS_SAPI_XML}")
        return data
    except Exception as exc:
        backend_errors.append(f"windows_sapi={exc}")

    raise RuntimeError("; ".join(backend_errors))


async def _decode_audio_to_pcm_s16le(audio_data: bytes, sample_rate: int) -> bytes:
    ffmpeg_path = _resolve_ffmpeg_path()
    if not ffmpeg_path:
        # Fallback: if input is WAV, decode with the standard library.
        try:
            with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
                src_channels = wav_file.getnchannels()
                src_width = wav_file.getsampwidth()
                src_rate = wav_file.getframerate()
                pcm = wav_file.readframes(wav_file.getnframes())

            if not pcm:
                raise RuntimeError("WAV 闊抽涓虹┖")

            # 缁熶竴鍒?6-bit
            if src_width != 2:
                pcm = audioop.lin2lin(pcm, src_width, 2)

            # 缁熶竴鍒板崟澹伴亾
            if src_channels > 1:
                pcm = audioop.tomono(pcm, 2, 0.5, 0.5)

            # Resample to target sample rate.
            if src_rate != sample_rate:
                pcm, _ = audioop.ratecv(
                    pcm,
                    2,
                    1,
                    src_rate,
                    sample_rate,
                    None,
                )

            return pcm
        except Exception as exc:
            raise RuntimeError(
                f"系统未找到 ffmpeg，且 WAV 回退解码失败: {exc}"
            )

    process = await asyncio.create_subprocess_exec(
        ffmpeg_path,
        "-v",
        "error",
        "-i",
        "pipe:0",
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_data, stderr_data = await process.communicate(input=audio_data)

    if process.returncode != 0:
        error_text = stderr_data.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"ffmpeg 转码失败: {error_text}")

    if not stdout_data:
        raise RuntimeError("ffmpeg 未输出 PCM 数据")
    return stdout_data


def _encode_pcm_to_opus_frames(
    pcm_data: bytes, sample_rate: int, frame_duration_ms: int
) -> list[bytes]:
    if opuslib is None:
        raise RuntimeError("opuslib 未安装")

    frame_samples = int(sample_rate * (frame_duration_ms / 1000))
    if frame_samples <= 0:
        frame_samples = int(sample_rate * 0.06)

    frame_bytes = frame_samples * 2  # int16 mono
    encoder = opuslib.Encoder(sample_rate, 1, opuslib.APPLICATION_VOIP)

    encoded_frames: list[bytes] = []
    for start in range(0, len(pcm_data), frame_bytes):
        frame = pcm_data[start : start + frame_bytes]
        if len(frame) < frame_bytes:
            frame = frame + (b"\x00" * (frame_bytes - len(frame)))
        encoded_frames.append(encoder.encode(frame, frame_samples))

    return encoded_frames


def _build_silence_opus_frames(
    sample_rate: int,
    frame_duration_ms: int,
    duration_ms: int,
) -> list[bytes]:
    if duration_ms <= 0:
        return []

    frame_samples = int(sample_rate * (frame_duration_ms / 1000))
    if frame_samples <= 0:
        frame_samples = int(sample_rate * 0.06)

    frame_count = max(1, int((duration_ms + frame_duration_ms - 1) / frame_duration_ms))
    silence_pcm = b"\x00" * frame_samples * 2
    encoder = opuslib.Encoder(sample_rate, 1, opuslib.APPLICATION_VOIP)
    return [encoder.encode(silence_pcm, frame_samples) for _ in range(frame_count)]


async def _synthesize_tts_opus_frames(
    text: str,
    sample_rate: int,
    frame_duration_ms: int,
    rate_override: str | None = None,
) -> list[bytes]:
    audio_data = await _synthesize_tts_audio(text, rate_override=rate_override)
    pcm_data = await _decode_audio_to_pcm_s16le(audio_data, sample_rate)
    return [
        *_build_silence_opus_frames(sample_rate, frame_duration_ms, TTS_PREROLL_MS),
        *_encode_pcm_to_opus_frames(pcm_data, sample_rate, frame_duration_ms),
    ]


async def _send_dialogue_with_audio(
    ws: WebSocket,
    user_text: str,
    answer_text: str,
    sample_rate: int = 16000,
    frame_duration_ms: int = 60,
) -> None:
    await _send_dialogue(ws, user_text, answer_text)
    await ws.send_text(
        json.dumps({"type": "tts", "state": "start", "text": answer_text})
    )

    try:
        answer_rate = _choose_segment_rate(answer_text) if TTS_EXPRESSIVE else None
        frames = await _synthesize_tts_opus_frames(
            answer_text,
            sample_rate=sample_rate,
            frame_duration_ms=frame_duration_ms,
            rate_override=answer_rate,
        )
        await _send_opus_frames(ws, frames, frame_duration_ms)

        await asyncio.sleep(0.08)
    except Exception as exc:
        logger.error("璇煶鍚堟垚鎴栭煶棰戝彂閫佸け璐? %s", exc)

    await ws.send_text(
        json.dumps({"type": "tts", "state": "stop", "text": answer_text})
    )


@app.post("/xiaokang/ota/")
async def ota_config(authorization: str | None = Header(default=None)):
    _check_auth_header(authorization)
    payload = {
        "websocket": {
            "url": WS_PUBLIC_URL,
            "token": WS_TOKEN,
        }
    }
    return JSONResponse(payload)


@app.post("/xiaokang/ota/activate")
async def ota_activate(authorization: str | None = Header(default=None)):
    _check_auth_header(authorization)
    return JSONResponse({"ok": True})


@app.websocket("/xiaokang/v1/")
async def ws_gateway(websocket: WebSocket):
    auth = _extract_auth_from_ws(websocket)
    if auth != f"Bearer {WS_TOKEN}":
        await websocket.close(code=1008)
        return

    await websocket.accept()
    session_id = str(uuid.uuid4())
    sample_rate = 16000
    frame_duration_ms = 60
    listening_active = False
    pcm_buffer = bytearray()
    opus_decoder = None
    vosk_stream_recognizer = None

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message and message.get("bytes") is not None:
                if not listening_active:
                    continue

                if opuslib is None:
                    continue

                if opus_decoder is None:
                    try:
                        opus_decoder = opuslib.Decoder(sample_rate, 1)
                    except Exception as exc:
                        logger.error("鍒涘缓 Opus 瑙ｇ爜鍣ㄥけ璐? %s", exc)
                        continue

                try:
                    frame_samples = int(sample_rate * (frame_duration_ms / 1000))
                    decoded_pcm = opus_decoder.decode(message["bytes"], frame_samples)
                    pcm_buffer.extend(decoded_pcm)
                    if vosk_stream_recognizer is not None:
                        try:
                            vosk_stream_recognizer.AcceptWaveform(decoded_pcm)
                        except Exception as exc:
                            logger.debug("瀹炴椂 Vosk 鍠傛祦澶辫触锛屽凡蹇界暐: %s", exc)
                except Exception as exc:
                    logger.debug("瑙ｇ爜涓婅闊抽甯уけ璐ワ紝宸插拷鐣? %s", exc)
                continue

            text_data = message.get("text")
            if text_data is None:
                continue

            try:
                data: dict[str, Any] = json.loads(text_data)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            if msg_type == "hello":
                audio_params = data.get("audio_params") or {}
                sample_rate = int(audio_params.get("sample_rate") or 16000)
                frame_duration_ms = int(audio_params.get("frame_duration") or 60)
                opus_decoder = None
                vosk_stream_recognizer = None
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "hello",
                            "transport": "websocket",
                            "session_id": session_id,
                        }
                    )
                )
                continue

            if msg_type == "listen" and data.get("state") == "detect":
                user_text = str(data.get("text", "")).strip()
                await _reply_from_user_text(
                    websocket,
                    user_text,
                    sample_rate=sample_rate,
                    frame_duration_ms=frame_duration_ms,
                )
                continue

            if msg_type == "listen" and data.get("state") == "start":
                listening_active = True
                pcm_buffer.clear()
                vosk_stream_recognizer = None
                if opuslib is not None:
                    try:
                        opus_decoder = opuslib.Decoder(sample_rate, 1)
                    except Exception as exc:
                        logger.error("鍒濆鍖栦笂琛?Opus 瑙ｇ爜鍣ㄥけ璐? %s", exc)
                        opus_decoder = None

                if (
                    ASR_VOSK_STREAMING
                    and (ASR_BACKEND or "").strip().lower() in ("vosk", "offline_vosk")
                    and KaldiRecognizer is not None
                ):
                    try:
                        vosk_model = _get_vosk_model()
                        vosk_stream_recognizer = KaldiRecognizer(
                            vosk_model, float(sample_rate)
                        )
                        vosk_stream_recognizer.SetWords(False)
                    except Exception as exc:
                        logger.debug("鍒濆鍖栧疄鏃?Vosk 璇嗗埆鍣ㄥけ璐ワ紝灏嗗洖閫€鏁存璇嗗埆: %s", exc)
                        vosk_stream_recognizer = None
                continue

            if msg_type == "listen" and data.get("state") == "stop":
                listening_active = False
                if not pcm_buffer:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "stt",
                                "text": "",
                            }
                        )
                    )
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "tts",
                                "state": "start",
                                "text": "我没有听清楚，请再说一遍。",
                            }
                        )
                    )
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "tts",
                                "state": "stop",
                                "text": "我没有听清楚，请再说一遍。",
                            }
                        )
                    )
                    continue

                try:
                    asr_started_at = time.perf_counter()
                    user_text = ""
                    used_streaming_asr = False

                    if vosk_stream_recognizer is not None:
                        user_text = _extract_vosk_text(
                            vosk_stream_recognizer.FinalResult()
                        )
                        used_streaming_asr = bool(user_text)

                    raw_pcm = bytes(pcm_buffer)

                    if not user_text:
                        pcm_for_asr = raw_pcm
                        if ASR_TRIM_SILENCE:
                            pcm_for_asr = _trim_pcm_silence(
                                raw_pcm,
                                sample_rate=sample_rate,
                                silence_threshold=ASR_SILENCE_THRESHOLD,
                                keep_tail_ms=ASR_KEEP_TAIL_MS,
                                min_audio_ms=ASR_MIN_AUDIO_MS,
                            )

                        wav_bytes = _build_wav_from_pcm(pcm_for_asr, sample_rate)
                        user_text = await _transcribe_wav_bytes(wav_bytes)

                    asr_ms = (time.perf_counter() - asr_started_at) * 1000
                    logger.info(
                        "ASR 耗时 %.1fms (streaming=%s)", asr_ms, used_streaming_asr
                    )

                    reply_started_at = time.perf_counter()
                    await _reply_from_user_text(
                        websocket,
                        user_text,
                        sample_rate=sample_rate,
                        frame_duration_ms=frame_duration_ms,
                    )
                    reply_ms = (time.perf_counter() - reply_started_at) * 1000
                    logger.info("回复流程耗时 %.1fms", reply_ms)
                except Exception as exc:
                    logger.error("语音识别失败: %s", exc)
                    err_text = str(exc)
                    if "未识别到有效文本" in err_text:
                        fail_text = "我没有听清楚，请靠近麦克风再说一遍。"
                    else:
                        fail_text = f"语音识别失败：{err_text}"
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "tts",
                                "state": "start",
                                "text": fail_text,
                            }
                        )
                    )
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "tts",
                                "state": "stop",
                                "text": fail_text,
                            }
                        )
                    )
                continue

            if msg_type == "abort":
                await websocket.send_text(json.dumps({"type": "tts", "state": "stop"}))

    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=APP_HOST, port=APP_PORT, reload=False)







