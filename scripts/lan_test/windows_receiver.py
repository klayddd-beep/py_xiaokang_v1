#!/usr/bin/env python3
import argparse
import json
import logging
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class CommandHandler(BaseHTTPRequestHandler):
    server_version = "LanCommandReceiver/1.0"

    def _send_json(self, status_code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "windows-receiver",
                    "time": datetime.now().isoformat(timespec="seconds"),
                },
            )
            return
        self._send_json(404, {"ok": False, "error": "Not Found"})

    def do_POST(self):
        if self.path != "/command":
            self._send_json(404, {"ok": False, "error": "Not Found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "Invalid JSON"})
            return

        command_id = str(payload.get("id", "")) or datetime.now().strftime("%Y%m%d%H%M%S")
        action = str(payload.get("action", ""))
        args = payload.get("args", {})

        logging.info("收到指令 | id=%s | action=%s | args=%s", command_id, action, args)

        self._send_json(
            200,
            {
                "ok": True,
                "id": command_id,
                "received_action": action,
                "received_args": args,
                "message": "Windows 已收到指令",
                "time": datetime.now().isoformat(timespec="seconds"),
            },
        )

    def log_message(self, format: str, *args):
        logging.debug("HTTP %s", format % args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Windows 侧局域网指令接收器")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址，默认 0.0.0.0")
    parser.add_argument("--port", type=int, default=5005, help="监听端口，默认 5005")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    server = ThreadingHTTPServer((args.host, args.port), CommandHandler)
    logging.info("Windows 接收器启动成功: http://%s:%s", args.host, args.port)
    logging.info("健康检查: GET /health | 指令接口: POST /command")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("收到中断，正在关闭接收器...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
