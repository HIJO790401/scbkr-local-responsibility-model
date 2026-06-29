# 本地模型設定

SCBKR 支援多種模型 provider，但模型只能協助生成，不能取代簽名、驗收或入庫確認。

## Provider

- Sandbox：用於安全測試與無外部服務情境。
- LM Studio：常見本機模型服務。
- Ollama：常見本機模型 runtime。
- OpenAI-compatible API：任何相容 API 格式的 endpoint。
- Custom endpoint：由使用者自行設定的服務。

## localhost、區網與外部 endpoint

- localhost / 127.0.0.1 / ::1：本機模型呼叫，資料送到同一台電腦。
- 192.168.x.x：區網呼叫，資料送到同一 Wi-Fi / LAN 內的指定主機。
- external API：資料會送到使用者設定的外部服務，請確認服務條款與資料保護政策。

## API Key 安全提醒

不要把 API key commit 到 Git。不要把 key 貼在公開 issue、截圖或文件中。若使用外部 API，請只使用必要權限，並定期輪替 key。
