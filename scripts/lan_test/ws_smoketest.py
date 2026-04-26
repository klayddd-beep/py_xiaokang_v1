import asyncio
import json
import websockets


async def main():
    url = "ws://127.0.0.1:8787/xiaokang/v1/"
    headers = {
        "Authorization": "Bearer local-dev-token",
        "Protocol-Version": "1",
        "Device-Id": "smoketest-device",
        "Client-Id": "smoketest-client",
    }

    async with websockets.connect(url, extra_headers=headers, open_timeout=8) as ws:
        await ws.send(
            json.dumps(
                {
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
            )
        )
        msg = await asyncio.wait_for(ws.recv(), timeout=8)
        print("hello_resp=", msg)

        await ws.send(
            json.dumps({"type": "listen", "state": "detect", "text": "你好"})
        )

        got_json = 0
        got_audio = 0
        for _ in range(20):
            try:
                item = await asyncio.wait_for(ws.recv(), timeout=8)
            except asyncio.TimeoutError:
                break
            if isinstance(item, bytes):
                got_audio += 1
                continue
            got_json += 1
            print("json=", item)
            if '"type": "tts", "state": "stop"' in item:
                break

        print(f"summary json={got_json} audio={got_audio}")


if __name__ == "__main__":
    asyncio.run(main())
