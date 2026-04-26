# 鏈満缃戝叧锛圔鏂规锛?
杩欎釜鐩綍鎻愪緵涓€涓渶灏忓彲璺戠殑鏈湴缃戝叧锛?
- `xiaokang` 鈫?杩炴帴鏈満 `WebSocket`锛堝皬鏅哄崗璁級
- 缃戝叧 鈫?璋冪敤鐏北鏂硅垷 OpenAI 鍏煎鎺ュ彛

> 璇存槑锛氬綋鍓嶆渶灏忕綉鍏充互鈥滄枃鏈璇濋摼璺€濅负涓伙紙閫氳繃 `listen/detect` 鏂囨湰瑙﹀彂锛夈€?> 闊抽 ASR/TTS 鍏ㄩ摼璺彲鍚庣画鍐嶆墿灞曘€?
## 1) 鍑嗗鐜鍙橀噺

```bash
cd /home/orangepi/xiaokang/local_gateway
cp .env.example .env
```

缂栬緫 `.env`锛岃嚦灏戝～鍐欙細

- `VOLC_API_KEY`

榛樿宸查缃細

- `VOLC_MODEL=ark-code-latest`
- `VOLC_OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3`

## 2) 瀹夎渚濊禆

```bash
cd /home/orangepi/xiaokang/local_gateway
pip install -r ../requirements_forubuntu.txt
```

## 3) 鍚姩缃戝叧

```bash
cd /home/orangepi/xiaokang/local_gateway
set -a
source .env
set +a
python app.py
```

榛樿鐩戝惉锛?
- HTTP OTA: `http://127.0.0.1:8787/xiaokang/ota/`
- WS: `ws://127.0.0.1:8787/xiaokang/v1/`

## 4) 瀹㈡埛绔厤缃?
灏?`config/config.json` 閲岀殑缃戠粶閰嶇疆鏀逛负锛?
```json
"NETWORK": {
  "OTA_VERSION_URL": "http://127.0.0.1:8787/xiaokang/ota/",
  "WEBSOCKET_URL": "ws://127.0.0.1:8787/xiaokang/v1/",
  "WEBSOCKET_ACCESS_TOKEN": "local-dev-token",
  "ACTIVATION_VERSION": "v1",
  "AUTHORIZATION_URL": "http://127.0.0.1:8787/"
}
```

## 5) 鍚姩 xiaokang

```bash
cd /home/orangepi/xiaokang
conda activate xiaokang
python main.py
```

## 甯歌闂

- `401 Unauthorized`锛氭鏌?`WS_TOKEN` 涓?`WEBSOCKET_ACCESS_TOKEN` 鏄惁涓€鑷淬€?- 杩炰笉涓?WS锛氱‘璁ょ綉鍏宠繘绋嬪湪杩愯銆佺鍙?`8787` 鏈崰鐢ㄣ€?- 鏈夎繛鎺ヤ絾涓嶅洖澶嶏細妫€鏌?`.env` 涓?`VOLC_API_KEY` 鏄惁宸插～鍐欍€?
