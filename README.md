# 小康 AI 语音助手

这是一个基于 Python 的本地语音助手项目，当前版本以“小康”为助手名，主要面向 Windows 桌面运行和 Ubuntu 设备部署。项目包含客户端、音频采集播放、本地网关、语音识别、语音合成、LLM 对话、MCP 工具和局域网设备控制能力。

当前仓库已经精简为两套依赖文件：

- `requirements_forwindows.txt`：Windows 环境使用。
- `requirements_forubuntu.txt`：Ubuntu 环境使用，适合香橙派、地瓜派等 SBC 设备部署。

## 功能概览

- GUI / CLI 两种运行模式。
- 默认使用 WebSocket 协议连接本地网关。
- 本地网关提供 OTA 配置、激活接口和语音 WebSocket 服务。
- 支持 Vosk 离线 ASR，也预留 Whisper / OpenAI 兼容 ASR 配置。
- 支持 Edge TTS，Ubuntu 可配置 espeak 作为兜底。
- 支持摄像头、截图、系统控制、音乐、日程、倒计时等 MCP 工具。
- 支持通过自然语言向局域网设备发送控制命令。
- 支持唤醒词，但默认关闭，需要模型文件后再开启。

## 目录说明

```text
.
├── main.py                         # 主程序入口
├── config/
│   ├── config.json                 # 客户端、网络、音频、远程控制配置
│   └── efuse.json                  # 设备标识相关配置
├── local_gateway/
│   ├── app.py                      # 本地网关，负责 OTA / WebSocket / ASR / TTS / LLM
│   ├── .env.example                # 网关环境变量模板
│   └── models/                     # Vosk 等本地模型目录
├── src/                            # 客户端核心代码
├── assets/                         # 静态资源
├── libs/                           # libopus / webrtc_apm 等本地库
├── models/                         # 唤醒词模型目录
├── scripts/                        # 调试、检测、systemd 等辅助脚本
├── requirements_forwindows.txt     # Windows 依赖
└── requirements_forubuntu.txt      # Ubuntu 依赖
```

## 环境要求

建议使用 Python 3.10 或 3.11。项目中包含 PyQt5、音频、OpenCV、Vosk、Opus 等依赖，Python 版本过新时某些二进制包可能没有合适的 wheel。

Windows 需要：

- Python 3.10 / 3.11
- 麦克风和扬声器
- 可访问外网的网络环境，用于 LLM 和 Edge TTS

Ubuntu / 香橙派 / 地瓜派建议先安装系统依赖：

```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  portaudio19-dev libasound2-dev libopus0 libopus-dev \
  ffmpeg espeak-ng \
  libgl1 libglib2.0-0 \
  lsof
```

如果要运行 GUI，还需要桌面环境、Qt 相关运行库和音频设备权限。

## 安装依赖

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements_forwindows.txt
```

### Ubuntu

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements_forubuntu.txt
```

如果在开发板上安装较慢，建议使用国内 PyPI 镜像：

```bash
pip install -r requirements_forubuntu.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 配置本地网关

本地网关配置文件在 `local_gateway/.env`。首次使用时复制模板：

### Windows

```powershell
copy local_gateway\.env.example local_gateway\.env
```

### Ubuntu

```bash
cp local_gateway/.env.example local_gateway/.env
```

重点配置项：

```env
GATEWAY_HOST=127.0.0.1
GATEWAY_PORT=8787
WS_TOKEN=local-dev-token
WS_PUBLIC_URL=ws://127.0.0.1:8787/xiaokang/v1/

VOLC_API_KEY=
VOLC_MODEL=ark-code-latest
VOLC_OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3

ASR_BACKEND=vosk
VOSK_MODEL_PATH=local_gateway/models/vosk-model-small-cn-0.22
```

说明：

- `VOLC_API_KEY` 是大模型 API Key，不填时网关可以启动，但无法正常调用 LLM。
- `WS_TOKEN` 必须和 `config/config.json` 里的 `SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN` 保持一致。
- 如果客户端和网关不在同一台机器，`WS_PUBLIC_URL` 要改成网关机器的局域网 IP，例如 `ws://192.168.1.10:8787/xiaokang/v1/`。

## 配置客户端

主配置文件是 `config/config.json`。当前默认会连接本地网关：

```json
{
  "SYSTEM_OPTIONS": {
    "NETWORK": {
      "OTA_VERSION_URL": "http://127.0.0.1:8787/xiaokang/ota/",
      "WEBSOCKET_URL": "ws://127.0.0.1:8787/xiaokang/v1/",
      "WEBSOCKET_ACCESS_TOKEN": "local-dev-token"
    }
  }
}
```

常用配置：

- `WAKE_WORD_OPTIONS.USE_WAKE_WORD`：是否启用唤醒词，默认建议保持 `false`。
- `AUDIO_DEVICES`：输入和输出设备，GUI 设置页会自动写入。
- `REMOTE_CONTROL`：局域网设备控制配置。
- `CAMERA`：摄像头和视觉模型配置。

远程控制示例：

```json
"REMOTE_CONTROL": {
  "ENABLED": true,
  "DEFAULT_TARGET_IP": "192.168.1.20",
  "DEFAULT_PORT": 5005,
  "DEFAULT_TIMEOUT": 5,
  "COMMAND_PATH": "/command"
}
```

## 启动方式

### 推荐方式：启动主程序并自动拉起本地网关

```bash
python main.py
```

默认参数等价于：

```bash
python main.py --mode gui --protocol websocket --with-gateway
```

CLI 模式：

```bash
python main.py --mode cli
```

跳过激活流程：

```bash
python main.py --skip-activation
```

重启已存在的本地网关：

```bash
python main.py --restart-gateway
```

不自动启动本地网关：

```bash
python main.py --no-gateway
```

### 单独启动本地网关

```bash
cd local_gateway
python app.py
```

启动后可访问：

- OTA：`http://127.0.0.1:8787/xiaokang/ota/`
- WebSocket：`ws://127.0.0.1:8787/xiaokang/v1/`

可以用脚本检查 OTA 鉴权：

```bash
python scripts/verify_ota_auth.py
```

## Ubuntu 开机自启

仓库提供了 systemd 示例：

```text
scripts/systemd/py-xiaozhi-local-gateway.service
```

默认路径是 `/home/orangepi/py-xiaozhi`。如果你的项目路径不同，先修改 service 文件里的 `WorkingDirectory`、`ExecStart` 和日志路径。

安装并启用：

```bash
sudo cp scripts/systemd/py-xiaozhi-local-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable py-xiaozhi-local-gateway
sudo systemctl start py-xiaozhi-local-gateway
```

查看状态和日志：

```bash
systemctl status py-xiaozhi-local-gateway
tail -f local_gateway/local_gateway.log
```

## Vosk 模型

默认 Vosk 模型路径：

```text
local_gateway/models/vosk-model-small-cn-0.22
```

如果模型不在这个位置，请修改 `local_gateway/.env`：

```env
VOSK_MODEL_PATH=/path/to/vosk-model-small-cn-0.22
```

## 唤醒词

唤醒词默认关闭：

```json
"WAKE_WORD_OPTIONS": {
  "USE_WAKE_WORD": false
}
```

如果要开启，需要把 sherpa-onnx 关键词模型放到 `models/`，至少包含：

```text
encoder.onnx
decoder.onnx
joiner.onnx
tokens.txt
keywords.txt
```

然后把 `USE_WAKE_WORD` 改为 `true`。

## 常用调试脚本

```bash
python scripts/compare_requirements_env.py   # 检查当前环境和 requirements 的差异
python scripts/py_audio_scanner.py           # 扫描音频设备
python scripts/ws_smoke_test.py              # WebSocket 冒烟测试
python scripts/probe_tts_backend.py          # TTS 后端探测
python scripts/music_cache_scanner.py        # 音乐缓存扫描
```

代码格式化：

```bash
./format_code.sh
```

Windows：

```powershell
.\format_code.bat
```

## 常见问题

### 1. 网关启动了，但客户端连接失败

检查三处是否一致：

- `local_gateway/.env` 里的 `WS_TOKEN`
- `config/config.json` 里的 `WEBSOCKET_ACCESS_TOKEN`
- `WS_PUBLIC_URL` / `WEBSOCKET_URL` 的 IP 和端口

如果客户端和网关不在同一台设备，不能使用 `127.0.0.1`，要改成网关设备的局域网 IP。

### 2. Ubuntu 没有声音或找不到麦克风

先扫描设备：

```bash
python scripts/py_audio_scanner.py
```

确认系统能看到声卡后，再在 GUI 设置页选择输入和输出设备。开发板上还需要确认当前用户有音频设备权限。

### 3. Edge TTS 失败

Edge TTS 需要网络。如果希望 Ubuntu 设备在断网时也能发声，可以在 `local_gateway/.env` 中允许兜底：

```env
TTS_ALLOW_FALLBACK=true
ESPEAK_VOICE=zh
```

### 4. Vosk 识别失败

检查 `VOSK_MODEL_PATH` 是否指向真实模型目录，并确认目录内存在模型文件。路径建议使用绝对路径，尤其是在 systemd 启动时。

### 5. PyQt5 在 Ubuntu 上启动失败

优先确认是否安装了桌面环境和 Qt 运行依赖。如果只需要部署语音服务，可以使用 CLI 模式：

```bash
python main.py --mode cli
```

## 许可证

本项目使用 MIT License，详见 `LICENSE`。
