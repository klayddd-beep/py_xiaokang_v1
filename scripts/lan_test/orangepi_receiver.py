#!/usr/bin/env python3
"""OrangePi LAN command receiver.

Run this on OrangePi. It exposes:
- GET  /health
- POST /command

Request body example:
{
  "id": "cmd-20260414-120000",
  "action": "set_volume",
  "args": {"value": 60}
}

You can provide a command map JSON to execute custom actions safely.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_ACTION_MAP: Dict[str, List[str]] = {
    # 默认不执行任何本地动作脚本，避免误触发不存在的控制程序。
    # 需要其他动作时请通过 --action-map 显式配置。
}

TAKEOFF_ACTIONS = {"起飞", "takeoff"}
TAKEOFF_SIGNAL_VALUE = 1


def _run_command(cmd: List[str], timeout: int) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
        }


def _set_volume(value: int) -> Dict[str, Any]:
    value = max(0, min(100, int(value)))

    if shutil.which("wpctl"):
        normalized = max(0.0, min(1.0, value / 100.0))
        return _run_command(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", str(normalized)], 5)

    if shutil.which("pactl"):
        return _run_command(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{value}%"], 5)

    if shutil.which("amixer"):
        return _run_command(["amixer", "sset", "Master", f"{value}%"], 5)

    return {
        "ok": False,
        "returncode": -1,
        "stdout": "",
        "stderr": "no audio tool found (wpctl/pactl/amixer)",
    }


def _load_action_map(path: Optional[str]) -> Dict[str, List[str]]:
    if not path:
        return DEFAULT_ACTION_MAP.copy()

    p = Path(path)
    if not p.exists():
        logging.warning("action map file not found: %s", p)
        return DEFAULT_ACTION_MAP.copy()

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("action map must be a JSON object")

        validated: Dict[str, List[str]] = DEFAULT_ACTION_MAP.copy()
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v):
                validated[k] = v
        return validated
    except Exception as exc:
        logging.warning("failed to load action map: %s", exc)
        return DEFAULT_ACTION_MAP.copy()


def _detect_ros_mode(preferred_mode: str) -> str:
    mode = (preferred_mode or "auto").strip().lower()
    if mode in ("ros2", "off"):
        return mode

    if shutil.which("ros2"):
        return "ros2"
    return "off"


def _publish_takeoff_flag(
    topic: str,
    value: int,
    mode: str,
    timeout: int,
    publish_count: int,
    publish_interval: float,
) -> Dict[str, Any]:
    resolved_mode = _detect_ros_mode(mode)
    if resolved_mode == "off":
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "ros2 cli not found",
            "mode": resolved_mode,
            "topic": topic,
            "value": int(value),
            "msg_type": "UInt8",
            "publish_count": max(1, int(publish_count)),
            "success_count": 0,
            "attempts": [],
        }

    repeat = max(1, int(publish_count))
    interval = max(0.0, float(publish_interval))
    attempts: List[Dict[str, Any]] = []
    success_count = 0

    for index in range(repeat):
        cmd = [
            "ros2",
            "topic",
            "pub",
            "--once",
            topic,
            "std_msgs/msg/UInt8",
            "{data: " + str(int(value)) + "}",
        ]

        result = _run_command(cmd, timeout)
        if result.get("ok"):
            success_count += 1
        attempts.append(
            {
                "index": index + 1,
                "ok": bool(result.get("ok", False)),
                "returncode": result.get("returncode", -1),
                "stderr": result.get("stderr", ""),
            }
        )

        if index < repeat - 1 and interval > 0:
            time.sleep(interval)

    return {
        "ok": success_count > 0,
        "mode": resolved_mode,
        "topic": topic,
        "value": int(value),
        "msg_type": "UInt8",
        "publish_count": repeat,
        "success_count": success_count,
        "attempts": attempts,
    }


def _start_ros_topic_echo(topic: str, mode: str) -> Optional[subprocess.Popen[str]]:
    resolved_mode = _detect_ros_mode(mode)
    if resolved_mode == "off":
        logging.warning("ROS topic echo disabled: ros2 cli not found or ros-mode=off")
        return None

    cmd = ["ros2", "topic", "echo", topic]
    try:
        process: subprocess.Popen[str] = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        logging.warning("failed to start ROS topic echo for %s: %s", topic, exc)
        return None

    def _pump_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            text = line.rstrip()
            if text:
                logging.info("[ros2 echo %s] %s", topic, text)

    thread = threading.Thread(target=_pump_output, daemon=True)
    thread.start()
    logging.info("Started ROS topic echo: %s", " ".join(cmd))
    return process


class ReceiverConfig:
    def __init__(
        self,
        action_map: Dict[str, List[str]],
        command_timeout: int,
        ros_mode: str,
        ros_takeoff_topic: str,
        ros_command_timeout: int,
        ros_publish_count: int,
        ros_publish_interval: float,
    ):
        self.action_map = action_map
        self.command_timeout = command_timeout
        self.ros_mode = ros_mode
        self.ros_takeoff_topic = ros_takeoff_topic
        self.ros_command_timeout = ros_command_timeout
        self.ros_publish_count = ros_publish_count
        self.ros_publish_interval = ros_publish_interval


class CommandHandler(BaseHTTPRequestHandler):
    server_version = "OrangePiReceiver/1.0"
    config: ReceiverConfig

    def _send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "orangepi-receiver",
                    "time": datetime.now().isoformat(timespec="seconds"),
                },
            )
            return

        self._send_json(404, {"ok": False, "error": "Not Found"})

    def do_POST(self) -> None:
        if self.path != "/command":
            self._send_json(404, {"ok": False, "error": "Not Found"})
            return

        content_len = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_len) if content_len > 0 else b"{}"

        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "Invalid JSON"})
            return

        command_id = str(payload.get("id", "")) or datetime.now().strftime("%Y%m%d%H%M%S")
        action = str(payload.get("action", "")).strip()
        args = payload.get("args", {})
        if not isinstance(args, dict):
            args = {}

        logging.info("recv command id=%s action=%s args=%s", command_id, action, args)

        if not action:
            self._send_json(400, {"ok": False, "error": "Missing action", "id": command_id})
            return

        # Built-in actions
        if action == "ping":
            self._send_json(
                200,
                {
                    "ok": True,
                    "id": command_id,
                    "message": "pong from OrangePi",
                    "time": datetime.now().isoformat(timespec="seconds"),
                },
            )
            return

        if action == "set_volume":
            value = args.get("value", 50)
            try:
                value = int(value)
            except Exception:
                value = 50
            result = _set_volume(value)
            self._send_json(
                200 if result["ok"] else 500,
                {
                    "ok": result["ok"],
                    "id": command_id,
                    "action": action,
                    "args": {"value": value},
                    "result": result,
                },
            )
            return

        if action in TAKEOFF_ACTIONS:
            result = _publish_takeoff_flag(
                topic=self.config.ros_takeoff_topic,
                value=TAKEOFF_SIGNAL_VALUE,
                mode=self.config.ros_mode,
                timeout=self.config.ros_command_timeout,
                publish_count=self.config.ros_publish_count,
                publish_interval=self.config.ros_publish_interval,
            )
            self._send_json(
                200 if result["ok"] else 500,
                {
                    "ok": result["ok"],
                    "id": command_id,
                    "action": action,
                    "ros_flag": True,
                    "flag_value": TAKEOFF_SIGNAL_VALUE,
                    "result": result,
                },
            )
            return

        # Custom mapped actions from JSON file
        cmd = self.config.action_map.get(action)
        if cmd:
            result = _run_command(cmd, self.config.command_timeout)
            self._send_json(
                200 if result["ok"] else 500,
                {
                    "ok": result["ok"],
                    "id": command_id,
                    "action": action,
                    "exec": cmd,
                    "result": result,
                },
            )
            return

        self._send_json(
            400,
            {
                "ok": False,
                "id": command_id,
                "error": "Unknown action",
                "action": action,
                "hint": "Use ping/set_volume or takeoff to publish ROS uint8 flag. For other actions, configure --action-map JSON.",
            },
        )

    def log_message(self, fmt: str, *args: Any) -> None:
        logging.debug("HTTP %s", fmt % args)


def main() -> None:
    parser = argparse.ArgumentParser(description="OrangePi LAN command receiver")
    parser.add_argument("--host", default="0.0.0.0", help="listen host")
    parser.add_argument("--port", type=int, default=5005, help="listen port")
    parser.add_argument(
        "--action-map",
        default="",
        help="JSON file path: {\"action\": [\"cmd\", \"arg1\"], ...}",
    )
    parser.add_argument("--command-timeout", type=int, default=8, help="subprocess timeout seconds")
    parser.add_argument(
        "--ros-mode",
        default="ros2",
        choices=["auto", "ros2", "off"],
        help="ROS publish mode for takeoff flag",
    )
    parser.add_argument(
        "--ros-takeoff-topic",
        default="/voice/allow_takeoff",
        help="ROS UInt8 topic for takeoff signal",
    )
    parser.add_argument(
        "--ros-command-timeout",
        type=int,
        default=3,
        help="ROS CLI publish timeout seconds",
    )
    parser.add_argument(
        "--ros-publish-count",
        type=int,
        default=3,
        help="publish attempts for ROS signal",
    )
    parser.add_argument(
        "--ros-publish-interval",
        type=float,
        default=0.12,
        help="seconds between repeated ROS publishes",
    )
    parser.add_argument(
        "--no-ros-echo",
        action="store_true",
        help="do not print ros2 topic echo output while receiver is running",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    action_map = _load_action_map(args.action_map)
    CommandHandler.config = ReceiverConfig(
        action_map=action_map,
        command_timeout=args.command_timeout,
        ros_mode=args.ros_mode,
        ros_takeoff_topic=args.ros_takeoff_topic,
        ros_command_timeout=args.ros_command_timeout,
        ros_publish_count=args.ros_publish_count,
        ros_publish_interval=args.ros_publish_interval,
    )

    server = ThreadingHTTPServer((args.host, args.port), CommandHandler)
    logging.info("OrangePi receiver started: http://%s:%s", args.host, args.port)
    logging.info("Health: GET /health | Command: POST /command")
    logging.info(
        "ROS takeoff signal: mode=%s topic=%s type=UInt8 value=%s repeat=%s",
        _detect_ros_mode(args.ros_mode),
        args.ros_takeoff_topic,
        TAKEOFF_SIGNAL_VALUE,
        args.ros_publish_count,
    )
    if action_map:
        logging.info("Loaded action map keys: %s", ", ".join(sorted(action_map.keys())))
    else:
        logging.info("No custom action map loaded. Built-ins: ping, set_volume, takeoff->ROS signal")

    echo_process = None
    if not args.no_ros_echo:
        echo_process = _start_ros_topic_echo(args.ros_takeoff_topic, args.ros_mode)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Interrupted, shutting down...")
    finally:
        if echo_process and echo_process.poll() is None:
            echo_process.terminate()
            try:
                echo_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                echo_process.kill()
        server.server_close()


if __name__ == "__main__":
    main()
