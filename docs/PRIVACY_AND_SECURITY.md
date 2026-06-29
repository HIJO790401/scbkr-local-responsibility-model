# 隱私與安全邊界

## 本地優先

SCBKR 主要在本機運行。使用本地模型時，資料留在使用者本機或使用者指定的區網環境。

## 外部 endpoint 風險

使用外部 OpenAI-compatible API 或 custom endpoint 時，資料會送往使用者設定的服務。請先確認 endpoint、服務條款、資料保留政策與 API key 權限。

## 模型不能取代使用者責任

- 模型不能簽名。
- 模型不能驗收。
- 模型不能自動入庫。
- 模型不能自動把輸出變成長期記憶。
- 模型不能繞過 Data Center Gate。

## 搜尋與外部 API 的資料流提醒

若未來啟用搜尋或外部 API，必須清楚標示資料流向、候選資料狀態與使用者確認邊界。未驗收資料不得進入四庫。

## Data Center Gate

Data Center 寫入需要使用者驗收與二次確認。正式四庫僅為 vector / corpus / logic / memory。
