# SCBKR Desktop AI Product Completion Report

測試日期：2026-08-11
最終發布核對：2026-08-20
公開版本：SCBKR FREE 框架體驗版
作者：許文耀／沈耀888π（Wen-Yao Hsu）

## 1. 桌面產品是否能啟動

**可以，本機 Windows x64 RC 已實際封裝並啟動。**

- Tauri 桌面程式成功啟動內建 PyInstaller API sidecar。
- `http://127.0.0.1:8787/health` 與產品狀態 API 正常回應。
- 封裝版使用全新的 Windows AppData，啟動後顯示 0 個任務、0 筆規則，不會把 repo 測試資料帶給使用者。
- NSIS 安裝程式已產生於 `dist/scbkr-windows-desktop-rc/desktop/SCBKR Local Responsibility Model_2.3.0_x64-setup.exe`。
- 安裝後不需要使用者另外安裝 Python 或 Node.js。

2026-08-11 本機封裝證據：

| 產物 | 大小 | SHA-256 |
| --- | ---: | --- |
| `scbkr_desktop.exe` | 10,732,544 bytes | `3E2BC111D7F8E18AE6F542A7490E18FEC8178C98ADCE5F94ED0874B25C376004` |
| `SCBKR Local Responsibility Model_2.3.0_x64-setup.exe` | 29,336,270 bytes | `DD79BE4D8380F3330369844713F4ED26773242C730F8AE2D4B3503FA580AD6BA` |
| `scbkr-api-x86_64-pc-windows-msvc.exe` | 27,085,405 bytes | `408FD4BE473C8CE37A257935177F718CA0A3ECF3CC80F1D3117D4E46BD771940` |

上表是先前本機建置，不與不同建置環境產生的 GitHub CI 二進位檔宣稱逐位元相同。公開 `main` 的 commit `e35359ce8969b94c2c3a3f6dd5a3d7b068a677ca` 已由 GitHub Actions 成功建置；下載該次 CI artifact 後重新計算結果如下：

| GitHub CI 產物 | 大小 | SHA-256 |
| --- | ---: | --- |
| `SCBKR Local Responsibility Model_2.3.0_x64-setup.exe` | 25,517,719 bytes | `17CE07C2432C60ECB3E37EE406684DE7D489658C19CB9067BE733D298BCBA978` |
| `scbkr_desktop.exe` | 10,737,152 bytes | `5B6CC47AE190E708863A78033F6B22A29CF215B8DE0756621E48802D3312C579` |
| `scbkr-api-x86_64-pc-windows-msvc.exe` | 23,457,034 bytes | `73B34A545E58E49212E8A54FAF1CC58385DB44B26CED9F07EA4136C3D223AA76` |

- GitHub Actions run：`31451472968`，結論 `success`。
- Artifact：`scbkr-windows-desktop-rc`，artifact ID `9086600892`。
- Artifact ZIP digest：`sha256:69cf13a62e79b1030fe004c6bca495884e7348ce330f5a0d25261f410c8bba67`。
- 下載後直接啟動 CI 版 `scbkr-api.exe`，5.91 秒內 `/health` 回覆 `ok=true`、版本 `2.3.0`，中英文產品身分與聊天路由均通過。
- 三個公開執行檔目前 Authenticode 狀態皆為 `NotSigned`；這是可測試 RC，不得冒充已簽章商店發行版。

## 2. 模型是否能連接

**可以。** 產品支援 LM Studio、Ollama 與 OpenAI-compatible API，並提供連線測試、模型名稱、provider 狀態與清楚的失敗訊息。

已用 LM Studio 的 `qwen2.5-3b-instruct` 完成真實 API 呼叫與 Token usage 取證。封裝版不內建模型或 API 金鑰；未連線時會明確顯示「模型未連線」，不會偽造模型結果。

## 3. 模型是否參與規則書生成

**可以，而且模型必須真正參與。**

自然語言規則需求先由硬路由分類，再由 `ModelRulebookAuthor` 建立 SCBKR 專用 messages。模型必須產生：

- S 主體、C 因果、B 邊界、K 依據、R 責任。
- 每一維的人類可讀解釋。
- 缺少資料、需要確認項目、模型不能自行判斷項目、風險、摘要與下一步。

後端只用結構化資料交換與驗證；前端顯示可讀確認單，不把 JSON 暴露給一般使用者。模型未連線、逾時或 schema 不合格時，流程明確失敗，不使用 direct-kernel 模板冒充模型草稿，`fallback_used=false`。

## 4. FREE 是否能生成基本規則

**可以。** FREE 不是空殼，也不是只換按鈕文字。它可完成一般聊天、基本 S/C/B/K/R 模型草擬、逐欄修改、Kernel Validator、使用者自簽、二次確認、四庫編譯、後續規則引用、回放與 Token / Context Audit。

公開 FREE 的定位是 **框架體驗版**：使用者建立、簽署、擁有並承擔自己的規則。它不附帶沈耀正式或私人規則包，也不得在未取得規則包時宣稱正在使用沈耀規則。

規則包邊界以兩條真實路徑驗收，不以虛構規則包代替：

- **無私有規則包**：公開 FREE 以空白規則庫啟動，沒有官方包、訂閱或隱性啟用狀態；使用者仍可自行建立與簽署規則。
- **有本機真實私有規則包**：只有本機檔案實際存在時才執行驗證，確認可辨識內容與簽章狀態，但未完成作者簽章前仍保持 `waiting_owner_signature`，不得訂閱、啟用或冒充正式規則。

公開 checkout 找不到該私有檔案時，對應測試會明確標示 skipped；不會生成替身資料，也不會因此把公開 FREE 判定為失敗。

## 5. NT$690 是否增加深度

**不屬於公開 FREE 發行範圍。** 本機私有產品資料另行保存，不進 GitHub、不進公開安裝包。本報告只證明 FREE 公開產品可執行；不把私有方案狀態當成已公開、已訂閱或已商用上線的證據。

## 6. NT$3,300 是否增加審計深度

**不屬於公開 FREE 發行範圍。** 本機私有產品資料另行保存，不進 GitHub、不進公開安裝包。沈耀正式規則包、深度客製化及商業工作流，應等待後續產品或透過商業合作取得；公開 FREE 不得暴露或暗示已附送這些內容。

## 7. 使用者是否能修改

**可以。** Workbench 顯示草稿來源、模型 provider/name、schema 狀態、Validator 狀態、fallback 狀態與原因，並讓使用者逐欄修改 S/C/B/K/R、補充條件、風險及確認事項。

模型可以協助重寫欄位，但每次修改仍停在草稿或待確認狀態。

## 8. 使用者是否能簽名

**可以，而且只有使用者能簽。**

- 模型不能簽名、入庫、啟用規則或宣稱規則已成立。
- 使用者簽名後仍須經驗收與最後入庫確認。
- 系統會在入庫確認當下重新檢查來源狀態；若草稿建立後底層資料或平行版本已變動，會觸發 conflict 並阻擋舊快照入庫。這修正了「簽的是已被取代狀態」的競態問題。

## 9. 規則是否能入四庫

**可以。** 完成使用者簽名、驗收及最後確認後，系統依責任拆分，而不是把同一段文字複製四次：

- `LOGIC`：命中條件、禁止事項、停止條件、版本、簽名與啟用狀態。
- `CORPUS`：經使用者確認、可作正式依據的資料。
- `MEMORY`：只在相關任務命中時使用的長期偏好。
- `VECTOR`：只存召回索引，不能直接成為正式依據。

規則可修改、建立新版、停用、封存或刪除；版本與操作會保留回放紀錄。

## 10. 再次提問是否命中規則

**可以。** 後續輸入先分類，再依序查 VECTOR 候選、LOGIC 簽名與啟用狀態、CORPUS 可引用資料、MEMORY 任務偏好。只有正式可用的來源才會進入本次規則包。

一般聊天仍可保有基本上下文，但聊天歷史不會因此變成正式規則或污染四庫。

## 11. 模型是否依 current_rule_package 回答

**可以。** 回答前建立最小 `current_rule_package`，內容包括任務、命中規則、規則狀態、可用與不可用資料、禁止事項、停止條件、缺口、輸出限制及是否必須追問。

模型回答後再檢查是否編造資料、引用未確認內容、違反禁止事項、越權執行、漏問必要問題或把草稿說成正式結果。違規輸出會被阻擋、要求重寫或降級為待確認草稿。

外部一般說法不能在產品內自動蓋過目前啟用、已簽名的使用者規則。若來源衝突，系統要求使用者確認，不讓模型自行終裁。

## 12. Token / Context Audit 是否產生

**可以，前端與後端都有可核對的稽核資料。**

使用工具與方法：

- 後端以 provider 回傳的 prompt/completion/total usage 為正式計數。
- 對同一 provider、同一 model、同一任務做 A/B 兩次真實呼叫。
- A 使用有界完整上下文；B 使用最小 `current_rule_package`。
- 保存模型名稱、開始與完成時間、兩次 prompt SHA-256、原始證據 SHA-256、token 數與 latency。
- 若 provider 沒有 usage，系統可顯示 tokenizer 估算，但不得標示為「已驗證成本」。

真實 LM Studio / `qwen2.5-3b-instruct` A/B 結果：

| 指標 | A 完整上下文 | B 規則包 | 節省 |
| --- | ---: | ---: | ---: |
| Prompt tokens | 5,658 | 1,723 | 3,935（69.55%） |
| Completion tokens | 51 | 57 | -6 |
| Total tokens | 5,709 | 1,780 | 3,929（68.82%） |

這證明該次任務大約只需要原 prompt 的 30.45%，不是所有模型與任務固定節省 69.55% 的普遍定律。機器可讀結果在 `reports/token_ab_verified_free.json`。

2026-08-20 取證重新核對了 LM Studio provider log、原始結果檔與公開報告：兩次 usage、時間、模型、prompt hash 與 `raw_source_sha256` 可互相吻合；原始結果檔 SHA-256 為 `B13F50C5B1C8967540EEAC209136CDDEB34872F388D9A46BB925CD26F2ABD863`。但當次 runner 是動態建立 `current_rule_package` 與完整四庫上下文，未另存這兩個欄位的逐位元原文，因此這是**可驗證的歷史實測結果**，不是「已保存完整原始輸入、任何人可逐位元重播」的證明。後續 benchmark 必須同步封存完整 input artifact，才能宣稱完整可重播。

## 13. 目前是否已是可運行桌面 AI 產品

**是本機可安裝、可啟動、可重複驗證的 Windows Desktop RC；不是展示頁或沙箱。**

最新公開 CI 與下載成品驗證：

- GitHub Actions `31451472968`：全部步驟成功，artifact 已上傳。
- `python -m pytest -q`：415 passed、2 skipped、0 failed（30.62 秒）。
- Playwright CI：desktop Chromium 與 mobile Chromium，2 passed（12.7 秒）。
- 下載公開 artifact 後再次執行 Playwright：2 passed（17.6 秒）。
- Vite / TypeScript production build：passed。
- Desktop release contract：passed。
- PyInstaller sidecar health、manifest、雙語 identity、chat route smoke：passed。
- Tauri release 與 NSIS installer：passed。
- 下載後直接啟動 CI sidecar：health、產品 manifest、中英文 identity、一般聊天 identity route 與 OpenAPI 版本均通過；測試結束後程序與 8787 連接埠均已釋放。
- 封裝成品實際啟動與全新 AppData 驗證：passed。
- 實機巡檢聊天、工作台、規則中心、資料中心、工具與搜尋、模型設定、規則狀態、上線中心、說明共 9 個頁面：全部可切換，無橫向溢出，瀏覽器錯誤 0。
- 封裝狀態 API：`FREE`、`release-candidate`、`preview=false`、`sandbox_available=false`、`store_submission_ready=false`，不把 RC 冒充已上架版本。

因此目前狀態是：**SOURCE_COMPLETE + LOCAL_RC_BUILT_AND_LAUNCHED**。

## 14. 還差哪些產品功能

距離 Microsoft Store 公開上架仍有外部發布步驟，不能把本機 RC 說成已上架：

- Windows 程式碼簽章與可驗證發布者身分。
- Microsoft Partner Center 帳戶與應用程式保留名稱。
- 商店年齡分級、法律資料、隱私政策正式網址與支援網址。
- 最終商店截圖、描述、套件上傳、認證與 Microsoft 審核。
- 若要提供雲端帳號、同步、訂閱或外部工具，仍需正式 Auth、後端部署、權限同意與商業基礎設施。

上述外部帳號或法律確認需要作者本人提供或登入；產品程式本體、FREE 定位、雙語 UI、模型協作確認單、四庫、規則引用、衝突重驗與 Token 稽核已完成本機 RC 驗證。
