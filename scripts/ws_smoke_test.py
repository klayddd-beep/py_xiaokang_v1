import asyncio
import json

import websockets


async def main() -> None:
    headers = {
        "Authorization": "Bearer local-dev-token",
        "Protocol-Version": "1",
        "Device-Id": "test-device",
        "Client-Id": "test-client",
    }
    ws = await websockets.connect(
        "ws://127.0.0.1:8787/xiaokang/v1/",
        extra_headers=headers,
    )

    hello = {
        "type": "hello",
        "version": 1,
        "features": {"mcp": True},
        "transport": "websocket",
        "audio_params": {
            "format": "opus",
            "sample_rate": 16000,
            "channels": 1,
            "frame_duration": 60,
        },
    }
    await ws.send(json.dumps(hello, ensure_ascii=False))
    reply = await ws.recv()
    print(reply)
    await ws.close()


if __name__ == "__main__":
    asyncio.run(main())
