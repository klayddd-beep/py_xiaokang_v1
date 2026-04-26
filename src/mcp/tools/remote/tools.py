"""远程设备控制工具函数。"""

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def _get_remote_config() -> Dict[str, Any]:
    config = ConfigManager()
    return {
        "enabled": bool(config.get_config("REMOTE_CONTROL.ENABLED", False)),
        "default_target_ip": str(
            config.get_config("REMOTE_CONTROL.DEFAULT_TARGET_IP", "") or ""
        ).strip(),
        "default_port": int(config.get_config("REMOTE_CONTROL.DEFAULT_PORT", 5005)),
        "default_timeout": float(
            config.get_config("REMOTE_CONTROL.DEFAULT_TIMEOUT", 5)
        ),
        "command_path": str(
            config.get_config("REMOTE_CONTROL.COMMAND_PATH", "/command") or "/command"
        ).strip()
        or "/command",
    }


def _safe_json_loads(value: str) -> Dict[str, Any]:
    if not value.strip():
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("args_json 必须是 JSON 对象")
    return parsed


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        body_text = response.read().decode("utf-8", errors="ignore")
        return {"status": response.status, "body": body_text}


def send_remote_command(params: Dict[str, Any]) -> str:
    """向远程设备发送控制指令。"""
    remote_cfg = _get_remote_config()
    if not remote_cfg["enabled"]:
        return "远程控制未启用，请在 config/config.json 中将 REMOTE_CONTROL.ENABLED 设为 true"

    target_ip = str(params.get("target_ip", "")).strip() or remote_cfg["default_target_ip"]
    if not target_ip:
        return "缺少目标IP，请提供 target_ip 或配置 REMOTE_CONTROL.DEFAULT_TARGET_IP"

    action = str(params.get("action", "")).strip()
    if not action:
        return "缺少 action 参数"

    try:
        args_obj = _safe_json_loads(str(params.get("args_json", "{}")))
    except Exception as exc:
        return f"args_json 解析失败: {exc}"

    port = int(params.get("port", 0) or remote_cfg["default_port"])
    timeout = float(params.get("timeout", 0) or remote_cfg["default_timeout"])
    command_path = remote_cfg["command_path"]
    if not command_path.startswith("/"):
        command_path = "/" + command_path

    payload = {
        "id": datetime.now().strftime("cmd-%Y%m%d-%H%M%S"),
        "action": action,
        "args": args_obj,
    }
    url = f"http://{target_ip}:{port}{command_path}"

    logger.info(
        "[RemoteTools] 发送远程指令: url=%s action=%s args=%s", url, action, args_obj
    )

    try:
        result = _post_json(url, payload, timeout=timeout)
        body_text = result["body"]
        try:
            parsed = json.loads(body_text)
            body_text = json.dumps(parsed, ensure_ascii=False)
        except Exception:
            pass

        return (
            f"远程指令发送成功: target={target_ip}:{port}, action={action}, "
            f"status={result['status']}, response={body_text}"
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        logger.error("[RemoteTools] 远程指令HTTP失败: %s %s", exc.code, body)
        return f"远程指令HTTP失败: code={exc.code}, body={body}"
    except Exception as exc:
        logger.error("[RemoteTools] 远程指令发送失败: %s", exc)
        return f"远程指令发送失败: {exc}"
