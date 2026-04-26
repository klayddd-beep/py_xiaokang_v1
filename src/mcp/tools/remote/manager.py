"""远程设备控制工具管理器。"""

from typing import Any, Dict

from src.utils.logging_config import get_logger

from .tools import send_remote_command

logger = get_logger(__name__)


class RemoteToolsManager:
    """远程设备控制工具管理器。"""

    def __init__(self):
        self._initialized = False
        logger.info("[RemoteManager] 远程控制工具管理器初始化")

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        try:
            logger.info("[RemoteManager] 开始注册远程控制工具")
            self._register_send_command_tool(
                add_tool, PropertyList, Property, PropertyType
            )
            self._initialized = True
            logger.info("[RemoteManager] 远程控制工具注册完成")
        except Exception as e:
            logger.error(f"[RemoteManager] 远程控制工具注册失败: {e}", exc_info=True)
            raise

    def _register_send_command_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        properties = PropertyList(
            [
                Property("action", PropertyType.STRING),
                Property("args_json", PropertyType.STRING, default_value="{}"),
                Property("target_ip", PropertyType.STRING, default_value=""),
                Property("port", PropertyType.INTEGER, default_value=5005, min_value=1, max_value=65535),
                Property("timeout", PropertyType.INTEGER, default_value=5, min_value=1, max_value=30),
            ]
        )

        add_tool(
            (
                "remote.device.send_command",
                "向局域网远程设备发送JSON控制指令（默认用于Windows接收端 /command）。\n"
                "Use when user says: 给B机发送指令 / 让另一台设备执行 / 远程控制电脑。\n"
                "中文强触发口令（优先调用本工具）：\n"
                "- 小康小康帮我给电脑发送指令\n"
                "- 小康小康帮我让电脑执行...\n"
                "- 帮我让电脑执行...\n"
                "参数:\n"
                "- action: 指令动作名（必填），例如 ping/set_volume/open_app\n"
                "- args_json: JSON对象字符串，例如 {\"value\":60}\n"
                "- target_ip: 目标设备IP，可留空使用配置默认值\n"
                "- port: 目标端口，默认5005\n"
                "- timeout: 请求超时时间（秒）",
                properties,
                send_remote_command,
            )
        )

        quick_properties = PropertyList(
            [
                Property("action", PropertyType.STRING),
                Property("args_json", PropertyType.STRING, default_value="{}"),
            ]
        )
        add_tool(
            (
                "remote.device.send_to_b",
                "快速给B机发送指令（使用配置中的默认IP/端口）。\n"
                "当用户说‘小康小康帮我给电脑...’时优先使用。\n"
                "参数:\n"
                "- action: 指令动作名，例如 ping/set_volume/open_app\n"
                "- args_json: JSON对象字符串，例如 {\"value\":60}",
                quick_properties,
                send_remote_command,
            )
        )

    def is_initialized(self) -> bool:
        return self._initialized

    def get_status(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "tools_count": 2,
            "available_tools": ["send_command", "send_to_b"],
        }


_remote_tools_manager = None


def get_remote_manager() -> RemoteToolsManager:
    global _remote_tools_manager
    if _remote_tools_manager is None:
        _remote_tools_manager = RemoteToolsManager()
        logger.debug("[RemoteManager] 创建远程控制工具管理器实例")
    return _remote_tools_manager
