# Windows 安裝與啟動

SCBKR Desktop 目前為 Release Candidate。請使用 release artifact 或 Windows installer 測試完整責任鏈。

## 安裝流程

1. 下載 Windows installer / release artifact。
2. 執行安裝程式並完成 SCBKR Desktop 安裝。
3. 確認本機 backend / sidecar 可啟動。
4. 打開 SCBKR Desktop。

## 啟動流程

1. 啟動本機 backend / sidecar。
2. 開啟桌面 app。
3. 設定模型 provider。
4. 建立第一個任務。
5. 在 Workbench 檢查草案。
6. 使用者簽名。
7. 生成、驗收、送出 Storage Request。
8. 二次確認後寫入 Data Center 四庫。

## Windows 防火牆提醒

若手機或其他區網裝置需要連回本機，Windows 防火牆可能需要允許 SCBKR / FastAPI 通訊。只允許可信任網路，避免把開發服務暴露到公網。

## 如何確認 backend health

在本機瀏覽器或終端機檢查 backend health endpoint；若專案設定的 port 不同，請以實際設定為準。

```bash
curl http://127.0.0.1:8000/health
```

## 如何跑完整責任鏈 smoke

1. 建立 Chat 任務。
2. 進入 Workbench。
3. 產生 S / C / B / K / R 草案。
4. 使用者簽名。
5. 執行模型生成。
6. 使用者驗收。
7. 建立 Storage Request。
8. 選擇 vector / corpus / logic / memory 中的正式目標。
9. 二次確認。
10. 在 Data Center 檢查入庫結果。

## 常見問題

- 無法連線 backend：確認 backend / sidecar 是否已啟動。
- 手機連不到：確認同 Wi-Fi、activeBackendUrl、Windows 防火牆與區網 IP。
- 模型沒有回應：確認 provider、endpoint、API key 與本地模型服務狀態。
