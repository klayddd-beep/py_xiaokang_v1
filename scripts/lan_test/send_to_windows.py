#!/usr/bin/env python3
import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime


def post_json(url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        content = response.read().decode("utf-8", errors="ignore")
        return {
            "status": response.status,
            "body": content,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="OrangePi 发送测试指令到 Windows")
    parser.add_argument("--target-ip", required=True, help="Windows 设备在热点下的 IP")
    parser.add_argument("--port", type=int, default=5005, help="Windows 接收端端口，默认 5005")
    parser.add_argument("--action", default="ping", help="指令动作名")
    parser.add_argument("--args", default='{"text":"hello from orangepi"}', help="JSON 字符串参数")
    parser.add_argument("--timeout", type=float, default=5.0, help="请求超时秒数")
    args = parser.parse_args()

    try:
        args_obj = json.loads(args.args)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--args 不是合法 JSON: {exc}")

    payload = {
        "id": datetime.now().strftime("cmd-%Y%m%d-%H%M%S"),
        "action": args.action,
        "args": args_obj,
    }

    url = f"http://{args.target_ip}:{args.port}/command"
    print(f"发送到: {url}")
    print(f"载荷: {json.dumps(payload, ensure_ascii=False)}")

    try:
        result = post_json(url, payload, timeout=args.timeout)
        print("请求成功")
        print(f"HTTP {result['status']}")
        print(result["body"])
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        print(f"HTTPError: {exc.code}")
        print(body)
    except Exception as exc:
        print(f"请求失败: {exc}")


if __name__ == "__main__":
    main()
