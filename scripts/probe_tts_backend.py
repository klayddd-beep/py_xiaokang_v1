import asyncio
import importlib.util
from pathlib import Path


gateway_app = Path(__file__).resolve().parents[1] / "local_gateway" / "app.py"
spec = importlib.util.spec_from_file_location("gw", gateway_app)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


async def main() -> None:
    print("edge_tts_installed=", mod.edge_tts is not None)
    print("tts_voice=", mod.TTS_VOICE)

    try:
        data = await mod._synthesize_mp3(
            "你好呀，这是一次 edge 测试语音。", rate_override="-6%"
        )
        print("edge_ok", len(data), data[:8])
    except Exception as exc:
        print("edge_err", repr(exc))

    try:
        data = await mod._synthesize_wav_with_windows_sapi(
            "你好呀，这是一次 SAPI 测试语音。", rate_override="-10%"
        )
        print("sapi_ok", len(data), data[:8])
    except Exception as exc:
        print("sapi_err", repr(exc))


if __name__ == "__main__":
    asyncio.run(main())
