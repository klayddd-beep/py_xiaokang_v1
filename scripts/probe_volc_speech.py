from pathlib import Path
from openai import OpenAI


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> None:
    env = load_env(Path("local_gateway/.env"))
    client = OpenAI(
        api_key=env.get("VOLC_API_KEY", ""),
        base_url=env.get("VOLC_OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"),
    )

    model_candidates = [
        "tts-1",
        "doubao-tts",
        "doubao-voice",
        "doubao-speech",
        "doubao-seed-1-6-250615",
        "doubao-lite-32k-240828",
    ]
    voice_candidates = [
        "alloy",
        "nova",
        "shimmer",
        "zh_female_sweet",
        "zh_female_qingxin",
        "zh-CN-XiaoyiNeural",
    ]

    ok = False
    for model in model_candidates:
        for voice in voice_candidates:
            try:
                response = client.audio.speech.create(
                    model=model,
                    voice=voice,
                    input="你好呀，我是小康，现在做一次语音测试。",
                )
                payload = response.read() if hasattr(response, "read") else b""
                print(f"OK model={model} voice={voice} bytes={len(payload)}")
                ok = True
                return
            except Exception as exc:
                print(f"FAIL model={model} voice={voice} error={exc}")

    if not ok:
        print("NO_WORKING_VOLC_AUDIO_SPEECH")


if __name__ == "__main__":
    main()
