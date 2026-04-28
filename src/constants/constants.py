import platform

from src.utils.config_manager import ConfigManager

config = ConfigManager.get_instance()


class ListeningMode:
    """
    鐩戝惉妯″紡.
    """

    REALTIME = "realtime"
    AUTO_STOP = "auto_stop"
    MANUAL = "manual"


class AbortReason:
    """
    涓鍘熷洜.
    """

    NONE = "none"
    WAKE_WORD_DETECTED = "wake_word_detected"
    USER_INTERRUPTION = "user_interruption"


class DeviceState:
    """
    璁惧鐘舵€?
    """

    IDLE = "idle"
    CONNECTING = "connecting"
    LISTENING = "listening"
    SPEAKING = "speaking"


class EventType:
    """
    浜嬩欢绫诲瀷.
    """

    SCHEDULE_EVENT = "schedule_event"
    AUDIO_INPUT_READY_EVENT = "audio_input_ready_event"
    AUDIO_OUTPUT_READY_EVENT = "audio_output_ready_event"


def is_official_server(ws_addr: str) -> bool:
    """鍒ゆ柇鏄惁涓哄皬鏅哄畼鏂圭殑鏈嶅姟鍣ㄥ湴鍧€.

    Args:
        ws_addr (str): WebSocket 鍦板潃

    Returns:
        bool: 鏄惁涓哄皬鏅哄畼鏂圭殑鏈嶅姟鍣ㄥ湴鍧€
    """
    return "local gateway" in ws_addr


def get_frame_duration() -> int:
    """鑾峰彇璁惧鐨勫抚闀垮害.

    杩斿洖:
        int: 甯ч暱搴?姣)
    """
    try:
        # 妫€鏌ユ槸鍚︿负瀹樻柟鏈嶅姟鍣?        ota_url = config.get_config("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")
        ota_url = config.get_config("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")
        if not is_official_server(ota_url):
            return 60

        # 妫€娴婣RM鏋舵瀯璁惧锛堝鏍戣帗娲撅級
        machine = platform.machine().lower()
        arm_archs = ["arm", "aarch64", "armv7l", "armv6l"]
        is_arm_device = any(arch in machine for arch in arm_archs)

        if is_arm_device:
            # ARM璁惧锛堝鏍戣帗娲撅級浣跨敤杈冨ぇ甯ч暱浠ュ噺灏慍PU璐熻浇
            return 60
        else:
            # 鍏朵粬璁惧锛圵indows/macOS/Linux x86锛夐兘鏈夎冻澶熸€ц兘锛屼娇鐢ㄤ綆寤惰繜
            return 20

    except Exception:
        # 濡傛灉鑾峰彇澶辫触锛岃繑鍥為粯璁ゅ€?0ms锛堥€傚悎澶у鏁扮幇浠ｈ澶囷級
        return 20


class AudioConfig:
    """
    闊抽閰嶇疆绫?
    """

    # 鍥哄畾閰嶇疆
    INPUT_SAMPLE_RATE = 16000  # 杈撳叆閲囨牱鐜?6kHz
    # 杈撳嚭閲囨牱鐜囷細瀹樻柟鏈嶅姟鍣ㄤ娇鐢?4kHz锛屽叾浠栦娇鐢?6kHz
    _ota_url = config.get_config("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")
    OUTPUT_SAMPLE_RATE = 24000 if is_official_server(_ota_url) else 16000
    MAX_INPUT_CHANNELS = 2
    MAX_OUTPUT_CHANNELS = 2
    CHANNELS = 1  # 鏈嶅姟绔崗璁姹傦細鍗曞０閬?
    # 璁惧澹伴亾闄愬埗锛堥伩鍏嶅澹伴亾璁惧鎬ц兘娴垂锛?    MAX_INPUT_CHANNELS = 2  # 鏈€澶氫娇鐢?涓緭鍏ュ０閬擄紙绔嬩綋澹帮級
    MAX_OUTPUT_CHANNELS = 2  # 鏈€澶氫娇鐢?涓緭鍑哄０閬擄紙绔嬩綋澹帮級

    # 鍔ㄦ€佽幏鍙栧抚闀垮害
    FRAME_DURATION = get_frame_duration()

    # 鏍规嵁涓嶅悓閲囨牱鐜囪绠楀抚澶у皬
    INPUT_FRAME_SIZE = int(INPUT_SAMPLE_RATE * (FRAME_DURATION / 1000))
    OUTPUT_FRAME_SIZE = int(OUTPUT_SAMPLE_RATE * (FRAME_DURATION / 1000))
    # Linux绯荤粺浣跨敤鍥哄畾甯уぇ灏忎互鍑忓皯PCM鎵撳嵃锛屽叾浠栫郴缁熷姩鎬佽绠?    OUTPUT_FRAME_SIZE = int(OUTPUT_SAMPLE_RATE * (FRAME_DURATION / 1000))

