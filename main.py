import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

from src.application import Application
from src.utils.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


# 读取主程序需要访问的本地网关地址和令牌；读取失败时使用本地默认值。
def _load_network_options() -> tuple[str, str]:
    """从config/config.json读取OTA地址和WS访问令牌，读取失败时使用默认值。"""
    default_ota_url = "http://127.0.0.1:8787/xiaokang/ota/"
    default_token = "local-dev-token"

    try:
        config_path = Path(__file__).resolve().parent / "config" / "config.json"
        if not config_path.exists():
            return default_ota_url, default_token

        data = json.loads(config_path.read_text(encoding="utf-8"))
        network = (data.get("SYSTEM_OPTIONS") or {}).get("NETWORK") or {}
        ota_url = str(network.get("OTA_VERSION_URL") or default_ota_url)
        token = str(network.get("WEBSOCKET_ACCESS_TOKEN") or default_token)
        return ota_url, token
    except Exception:
        return default_ota_url, default_token


# 用 OTA 接口做轻量健康检查，判断本地网关是否已经可用。
def _probe_gateway(ota_url: str, token: str, timeout_sec: float = 2.0) -> bool:
    """通过OTA接口探测本地网关是否在线。"""
    request = urllib.request.Request(
        url=ota_url,
        data=b"{}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            return int(response.status) == 200
    except Exception:
        return False


# 默认自动拉起 local_gateway/app.py，避免用户手动开两个进程。
def _stop_existing_gateway(ota_url: str) -> None:
    """停止占用本地网关端口的旧进程，仅用于显式要求重启网关时。"""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(ota_url)
        port = parsed.port or 8787
        pids: set[int] = set()

        if os.name == "nt":
            result = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                if f":{port}" not in line or "LISTENING" not in line.upper():
                    continue
                parts = line.split()
                if parts:
                    try:
                        pids.add(int(parts[-1]))
                    except ValueError:
                        pass

            for pid in pids:
                logger.info("正在停止旧本地网关进程 PID=%s", pid)
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True,
                    timeout=5,
                )
        else:
            result = subprocess.run(
                ["lsof", "-ti", f"tcp:{port}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                try:
                    pids.add(int(line.strip()))
                except ValueError:
                    pass
            for pid in pids:
                logger.info("正在停止旧本地网关进程 PID=%s", pid)
                os.kill(pid, signal.SIGTERM)
    except Exception as e:
        logger.warning("停止旧本地网关失败，将继续尝试启动: %s", e)


def _start_local_gateway_if_needed(
    enable: bool, restart_existing: bool = False
) -> subprocess.Popen | None:
    """按需启动local_gateway，并等待其就绪。"""
    if not enable:
        return None

    ota_url, token = _load_network_options()
    if _probe_gateway(ota_url, token):
        if not restart_existing:
            logger.info("检测到本地网关已运行，跳过自动启动")
            return None
        logger.info("检测到本地网关已运行，按要求重启本地网关")
        _stop_existing_gateway(ota_url)
        time.sleep(0.8)

    gateway_script = Path(__file__).resolve().parent / "local_gateway" / "app.py"
    if not gateway_script.exists():
        logger.error("未找到本地网关脚本: %s", gateway_script)
        return None

    logger.info("未检测到本地网关，正在自动启动: %s", gateway_script)
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(
        [sys.executable, str(gateway_script)],
        cwd=str(gateway_script.parent),
        creationflags=creationflags,
    )

    deadline = time.time() + 20.0
    while time.time() < deadline:
        if process.poll() is not None:
            logger.error("本地网关进程启动后异常退出，exit=%s", process.returncode)
            return None
        if _probe_gateway(ota_url, token):
            logger.info("本地网关已就绪")
            return process
        time.sleep(0.4)

    logger.error("等待本地网关就绪超时")
    try:
        process.terminate()
    except Exception:
        pass
    return None


# 只关闭由当前主进程自动拉起的本地网关，不影响用户手动启动的网关。
def _stop_local_gateway(process: subprocess.Popen | None) -> None:
    """停止由当前主程序拉起的本地网关进程。"""
    if process is None:
        return
    if process.poll() is not None:
        return
    try:
        logger.info("正在停止自动启动的本地网关进程...")
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


# 命令行参数统一放在这里，方便 GUI/CLI、协议和网关开关组合运行。
def parse_args():
    """
    解析命令行参数.
    """
    parser = argparse.ArgumentParser(description="小康AI客户端")
    parser.add_argument(
        "--mode",
        choices=["gui", "cli"],
        default="gui",
        help="运行模式：gui(图形界面) 或 cli(命令行)",
    )
    parser.add_argument(
        "--protocol",
        choices=["mqtt", "websocket"],
        default="websocket",
        help="通信协议：mqtt 或 websocket",
    )
    parser.add_argument(
        "--skip-activation",
        action="store_true",
        help="跳过激活流程，直接启动应用（仅用于调试）",
    )
    gateway_group = parser.add_mutually_exclusive_group()
    gateway_group.add_argument(
        "--with-gateway",
        dest="with_gateway",
        action="store_true",
        default=True,
        help="自动启动本地网关(local_gateway/app.py)后再启动主程序（默认开启）",
    )
    gateway_group.add_argument(
        "--no-gateway",
        dest="with_gateway",
        action="store_false",
        help="不自动启动本地网关",
    )
    parser.add_argument(
        "--restart-gateway",
        action="store_true",
        help="启动主程序前先重启本地网关，确保local_gateway/.env和app.py改动生效",
    )
    return parser.parse_args()


# 启动前先完成设备身份和激活检查；本地 v1 网关通常会直接通过。
async def handle_activation(mode: str) -> bool:
    """处理设备激活流程，依赖已有事件循环.

    Args:
        mode: 运行模式，"gui"或"cli"

    Returns:
        bool: 激活是否成功
    """
    try:
        from src.core.system_initializer import SystemInitializer

        logger.info("开始设备激活流程检查...")

        system_initializer = SystemInitializer()
        # 统一使用 SystemInitializer 内的激活处理，GUI/CLI 自适应
        result = await system_initializer.handle_activation_process(mode=mode)
        success = bool(result.get("is_activated", False))
        logger.info(f"激活流程完成，结果: {success}")
        return success
    except Exception as e:
        logger.error(f"激活流程异常: {e}", exc_info=True)
        return False


# 应用真正的异步入口：激活检查通过后创建 Application 并启动插件系统。
async def start_app(mode: str, protocol: str, skip_activation: bool) -> int:
    """
    启动应用的统一入口（在已有事件循环中执行）.
    """
    logger.info("启动小康AI客户端")

    # 处理激活流程
    if not skip_activation:
        activation_success = await handle_activation(mode)
        if not activation_success:
            logger.error("设备激活失败，程序退出")
            return 1
    else:
        logger.warning("跳过激活流程（调试模式）")

    # 创建并启动应用程序
    app = Application.get_instance()
    return await app.run(mode=mode, protocol=protocol)


if __name__ == "__main__":
    exit_code = 1
    gateway_process = None
    try:
        args = parse_args()
        setup_logging()

        gateway_process = _start_local_gateway_if_needed(
            args.with_gateway,
            restart_existing=args.restart_gateway,
        )

        # 检测Wayland环境并设置Qt平台插件配置
        import os

        is_wayland = (
            os.environ.get("WAYLAND_DISPLAY")
            or os.environ.get("XDG_SESSION_TYPE") == "wayland"
        )

        if args.mode == "gui" and is_wayland:
            # 在Wayland环境下，确保Qt使用正确的平台插件
            if "QT_QPA_PLATFORM" not in os.environ:
                # 优先使用wayland插件，失败则回退到xcb（X11兼容层）
                os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
                logger.info("Wayland环境：设置QT_QPA_PLATFORM=wayland;xcb")

            # 禁用一些在Wayland下不稳定的Qt特性
            os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
            logger.info("Wayland环境检测完成，已应用兼容性配置")

        # 统一设置信号处理：忽略 macOS 上可能出现的 SIGTRAP，避免“trace trap”导致进程退出
        try:
            if hasattr(signal, "SIGINT"):
                # 交由 qasync/Qt 处理 Ctrl+C；保持默认或后续由 GUI 层处理
                pass
            if hasattr(signal, "SIGTERM"):
                # 允许进程收到终止信号时走正常关闭路径
                pass
            if hasattr(signal, "SIGTRAP"):
                signal.signal(signal.SIGTRAP, signal.SIG_IGN)
        except Exception:
            # 某些平台/环境不支持设置这些信号，忽略即可
            pass

        if args.mode == "gui":
            # 在GUI模式下，由main统一创建 QApplication 与 qasync 事件循环
            try:
                import qasync
                from PyQt5.QtWidgets import QApplication
            except ImportError as e:
                logger.error(f"GUI模式需要qasync和PyQt5库: {e}")
                sys.exit(1)

            qt_app = QApplication.instance() or QApplication(sys.argv)

            loop = qasync.QEventLoop(qt_app)
            asyncio.set_event_loop(loop)
            logger.info("已在main中创建qasync事件循环")

            # 确保关闭最后一个窗口不会自动退出应用，避免事件环提前停止
            try:
                qt_app.setQuitOnLastWindowClosed(False)
            except Exception:
                pass

            with loop:
                exit_code = loop.run_until_complete(
                    start_app(args.mode, args.protocol, args.skip_activation)
                )
        else:
            # CLI模式使用标准asyncio事件循环
            exit_code = asyncio.run(
                start_app(args.mode, args.protocol, args.skip_activation)
            )

    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        exit_code = 0
    except SystemExit as e:
        try:
            exit_code = int(e.code) if e.code is not None else 0
        except Exception:
            exit_code = 1
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        exit_code = 1
    finally:
        _stop_local_gateway(gateway_process)
        sys.exit(exit_code)
