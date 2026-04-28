import asyncio
import importlib.util
from pathlib import Path


gateway_app = Path(__file__).resolve().parents[1] / "local_gateway" / "app.py"
spec = importlib.util.spec_from_file_location("gw", gateway_app)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


async def main() -> None:
    print("edge_tts_installed=", mod.edge_tts is not None)
    print("sherpa_onnx_installed=", mod.sherpa_onnx is not None)
    print("tts_backend=", mod.TTS_BACKEND)
    print("tts_voice=", mod.TTS_VOICE)
    print("tts_sherpa_model=", mod.TTS_SHERPA_MODEL or "(not configured)")

    if mod.TTS_BACKEND == "edge":
        try:
            data = await mod._synthesize_mp3("你好，这是 edge 语音测试。", rate_override="-6%")
            print("edge_ok", len(data), data[:8])
        except Exception as exc:
            print("edge_err", repr(exc))
    else:
        print("edge_skip", "current backend is", mod.TTS_BACKEND)

    try:
        data = await mod._synthesize_wav_with_sherpa(
            "你好，这是 sherpa 本地语音测试。", rate_override="-6%"
        )
        print("sherpa_ok", len(data), data[:8])
    except Exception as exc:
        print("sherpa_err", repr(exc))

    try:
        data = await mod._synthesize_wav_with_windows_sapi(
            "你好，这是 Windows SAPI 语音测试。", rate_override="-10%"
        )
        print("sapi_ok", len(data), data[:8])
    except Exception as exc:
        print("sapi_err", repr(exc))


if __name__ == "__main__":
    asyncio.run(main())
