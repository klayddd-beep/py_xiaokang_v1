# 鎵嬫満鐑偣涓嬬殑 A鈫払 鎸囦护鑱旇皟锛圤rangePi -> Windows锛?
## 1) 缃戠粶鍑嗗
1. 鎵嬫満寮€鐑偣銆?2. OrangePi 鍜?Windows 閮借繛鎺ュ埌鍚屼竴涓儹鐐广€?3. 鍦?Windows 涓婃墽琛?`ipconfig`锛岃涓?Wi-Fi 鐨?IPv4锛堜緥濡?`192.168.43.120`锛夈€?
## 2) Windows 绔細鍚姩鎺ユ敹鍣紙B 绔級
鍦?Windows PowerShell 涓繍琛岋細

```powershell
cd <浣犵殑椤圭洰鐩綍>\scripts\lan_test
python windows_receiver.py --host 0.0.0.0 --port 5005
```

鐪嬪埌濡備笅鏃ュ織琛ㄧず鎴愬姛锛?- `Windows 鎺ユ敹鍣ㄥ惎鍔ㄦ垚鍔焋
- `鍋ュ悍妫€鏌? GET /health | 鎸囦护鎺ュ彛: POST /command`

### Windows 闃茬伀澧欙紙棣栨蹇呭仛锛?濡傛灉 OrangePi 璁块棶涓嶅埌锛岃鏀捐 Python 鎴栫鍙?5005锛?
```powershell
netsh advfirewall firewall add rule name="LanReceiver5005" dir=in action=allow protocol=TCP localport=5005
```

## 3) OrangePi 绔細鍙戦€佹祴璇曟寚浠わ紙A 绔級
鍦?OrangePi 涓婅繍琛岋細

```bash
cd /home/orangepi/xiaokang
/home/orangepi/xiaokang/.venv/bin/python scripts/lan_test/send_to_windows.py \
  --target-ip 192.168.43.120 \
  --port 5005 \
  --action set_volume \
  --args '{"value":60}'
```

濡傛灉鎴愬姛锛屼細鐪嬪埌锛?- OrangePi: `HTTP 200`
- Windows: `鏀跺埌鎸囦护 | id=... | action=set_volume | args={'value': 60}`

## 4) 鍋ュ悍妫€鏌ワ紙鍙€夛級
鍦?OrangePi 渚ф鏌?Windows 鎺ユ敹鍣ㄦ槸鍚﹀湪绾匡細

```bash
curl http://192.168.43.120:5005/health
```

## 5) 鍚庣画鎺?AI 璇煶鎺у埗
寤鸿灏嗚嚜鐒惰瑷€鏄犲皠鎴愮粺涓€ JSON锛?
```json
{
  "id": "cmd-20260405-153000",
  "action": "set_volume",
  "args": {"value": 60}
}
```

鍚庨潰鍙鎶?`send_to_windows.py` 鐨勮皟鐢ㄥ皝瑁呮垚浣犵殑 AI 宸ュ叿锛圡CP/tool锛夊嵆鍙€?
## 6) 宸查泦鎴?MCP 宸ュ叿锛堝彲鐩存帴璇煶瑙﹀彂锛?椤圭洰宸叉柊澧?MCP 宸ュ叿锛歚remote.device.send_command`銆?
榛樿閰嶇疆鍦?`config/config.json` 鐨?`REMOTE_CONTROL`锛?
```json
"REMOTE_CONTROL": {
  "ENABLED": true,
  "DEFAULT_TARGET_IP": "10.82.220.73",
  "DEFAULT_PORT": 5005,
  "DEFAULT_TIMEOUT": 5,
  "COMMAND_PATH": "/command"
}
```

褰撲綘瀵?AI 璇翠互涓嬭瘽鏈椂锛屽彲瑙﹀彂杩滅▼鎺у埗锛?- `缁欑數鑴戝彂閫佹寚浠わ紝action鏄痯ing`
- `缁欑數鑴戞墽琛?set_volume锛屽弬鏁?value=60`
- `璁╃數鑴戞墽琛?open_app锛屽弬鏁?name=寰俊`

涔熸敮鎸佽嚜鐒惰瑷€鍔ㄤ綔锛堟棤闇€鏄惧紡鍙傛暟锛夛細
- `灏忔櫤灏忔櫤甯垜璁╃數鑴戝墠杩沗
- `灏忔櫤灏忔櫤甯垜璁╃數鑴戝悗閫€`
- `灏忔櫤灏忔櫤甯垜璁╃數鑴戝仠姝
- `灏忔櫤灏忔櫤甯垜鎶婄數鑴戦煶閲忚皟鍒?0`

寤鸿鍥哄畾鍙ｄ护锛?- `缁欑數鑴戞墽琛岋細<action>`
- `鍙傛暟锛?json瀵硅薄>`

鎴栫洿鎺ヨ鑷劧璇█锛?- `璁╃數鑴戝墠杩沗
- `璁╃數鑴戝仠姝

渚嬪锛?- `缁欑數鑴戞墽琛岋細set_volume锛屽弬鏁帮細{"value":60}`

