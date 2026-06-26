# SCBKR 本地責任鏈模型｜Local Responsibility Chain Model

**SCBKR Local Responsibility Chain Model**  
本地 AI 責任鏈工作台｜使用者簽名 Gate｜四庫 Data Center｜Release Candidate

版本：`0.15.0-rc.1`  
階段：`P15-Q Release Candidate + PATCH-1`  
後端：`FastAPI`  
前端：`React + TypeScript`  
桌面端：`Tauri`  
模型接入：`LM Studio / Ollama / OpenAI-compatible API`

語言文件：  
[English Documentation](./README_EN.md)

---

## 一、目前版本狀態

目前版本：

**SCBKR `0.15.0-rc.1`｜P15-Q Release Candidate + PATCH-1**

目前狀態：

- P15-Q Release Candidate 主流程已完成。
- P15-Q PATCH-1 已修復 Windows smoke 入庫目標與 Data Center 簽名 Gate。
- Windows Desktop Preview workflow 已通過。
- 目前可進入正式實機驗收與 1.0 上線整理。

目前產品階段：

**SCBKR 1.0｜本地責任鏈基礎版**

下一階段產品方向：

**SCBKR 2.0｜規則驅動 AI 引擎作業系統**

---

## 二、產品定位

SCBKR 不是一般聊天機器人。

SCBKR 也不是單純 RAG、不是單純 Agent、不是單純本地模型 UI。

SCBKR 是一套本地 AI 責任鏈工作台。

它的核心不是讓模型「先回答」，而是讓模型在回答、生成、入庫、引用、改寫、刪除、封存、工具執行之前，先通過使用者定義的責任鏈。

![SCBKR Hero](docs/images/scbkr-hero-en.png)

核心原則：

> 模型可以協助，但不能越權。  
> 沒有使用者簽名，責任鏈不成立。  
> 沒有驗收，不能入庫。  
> 沒有二次確認，不能寫入四庫。  
> 沒有有效證據，不能引用。  

SCBKR 的目標是讓使用者在自己的電腦上建立一套：

- 可確認
- 可簽名
- 可驗收
- 可入庫
- 可回放
- 可審計
- 可持續累積規則
- 可連接本地模型
- 可由手機遠端操作本機 AI 工作台

的本地責任鏈 AI 系統。

---

## 三、SCBKR 解決什麼問題

一般 AI 工具常見問題：

- 使用者一輸入，模型就直接生成。
- 任務目的不清楚，模型仍然硬答。
- 權限、邊界、資料來源、驗收條件沒有先確認。
- 模型生成錯誤後，使用者只能反覆重問。
- 錯誤內容可能污染長期記憶。
- 模型可能把一次性草稿當成未來規則。
- Agent / 工具 / 自動化流程可能沒有明確責任歸屬。
- 使用者不知道模型到底依照什麼資料做判斷。
- 每次任務都從零開始，無法累積有效責任鏈。

SCBKR 改變流程。

SCBKR 不讓模型直接把輸出變成規則、記憶、行動或入庫資料。

SCBKR 要求模型先建立責任鏈確認單。

使用者確認並簽名後，模型才可以依照確認單生成。

---

## 四、核心閉環流程

SCBKR 目前 1.0 的核心流程：

![Responsibility Loop](docs/images/responsibility-loop.png)

```text
Chat
→ Workbench
→ SCBKR Draft Grammar
→ Owner Signature
→ Generation
→ User Review
→ Storage Request
→ Second Confirmation
→ Data Center
→ Four-store Evidence Reuse
```

人話版本：

1. 使用者輸入需求。
2. 系統建立任務。
3. 模型幫忙產生 S / C / B / K / R 草案。
4. 使用者檢查與修改。
5. 草案一修改，舊簽名作廢。
6. 使用者重新簽名後，責任鏈才成立。
7. 模型才可以正式生成。
8. 使用者驗收生成結果。
9. 驗收通過後，才可以建立入庫請求。
10. 入庫前必須使用者二次確認。
11. 寫入 Data Center / 四庫。
12. 未來任務只能引用已簽名、已驗收、未撤銷、未封存、未被取代且與任務相關的資料。

---

## 五、SCBKR 五維責任鏈

SCBKR 使用五維責任鏈：

| 維度 | 名稱 | 作用 |
|---|---|---|
| S | Subject / Interface｜主體 / 介面 | 確認任務主體、任務名稱、輸入內容、輸出形式與操作介面 |
| C | Causality / Backend｜因果 / 後端 | 確認流程、順序、依賴、資料流、測試條件與失敗影響 |
| B | Boundary / Behavior｜邊界 / 行為 | 確認可讀取、可寫入、可呼叫、可停止、可入庫的範圍 |
| K | Knowledge / Style｜依據 / 風格 | 確認參考資料、規則、來源、風格、可信度與歷史案例 |
| R | Replay / Signature｜回放 / 簽名 | 確認驗收條件、回放紀錄、簽名狀態與審計資料 |

模型可以協助建立這五維草案。

但模型不能自行確認、不能自行簽名、不能自行驗收、不能自行入庫。

---

## 六、目前 1.0 已完成能力

目前 SCBKR 1.0 Release Candidate 已具備：

- Chat 對話入口
- Chat-to-Workbench 任務建立
- SCBKR Draft Grammar
- 模型輔助 S / C / B / K / R 草案
- 使用者簽名 Gate
- 模型不能簽名
- 草案修改後舊簽名作廢
- confirmed gate
- generation gate
- user review gate
- storage request
- second confirmation storage gate
- Data Center
- 四庫寫入
- 四庫引用條件
- Data Center 更改 / 封存 / 取代簽名 Gate
- SQLite task persistence
- JSONL ledger replay
- physical local storage
- Windows desktop build / smoke workflow
- FastAPI 本地後端
- React + TypeScript 前端
- Tauri desktop shell
- LM Studio / Ollama / OpenAI-compatible API 接入基礎
- activeBackendUrl
- same-Wi-Fi / mobile companion operation foundation
- Release Candidate metadata
- Windows Desktop Preview workflow success

---

## 七、使用者簽名 Gate

使用者簽名是 SCBKR 的核心 Gate。

![Owner Signature Workbench](docs/images/workbench-owner-signature.png)

沒有使用者簽名：

- SCBKR 不成立。
- 模型不能正式生成。
- 生成結果不能驗收。
- 驗收結果不能入庫。
- 資料不能成為未來引用依據。

模型不能使用以下身分簽名：

- model
- assistant
- system

只有使用者明確輸入 signature，並以 `confirmed_by=user` 確認後，SCBKR 才成立。

草案內容只要修改：

- 使用者簽名會被清空。
- 生成結果作廢。
- 驗收結果作廢。
- 入庫狀態作廢。
- 使用者必須重新簽名。

---

## 八、入庫 Gate

SCBKR 不允許模型自動入庫。

入庫必須同時滿足：

- `review_passed=true`
- `storage_confirmed=true`
- `second_confirm=true`
- `confirmed_by=user`
- `signature` 不可空
- SCBKR 必須是 `owner_signed`
- physical write gate 必須完成

這代表：

模型可以生成草稿。

但資料要不要進入長期系統，必須由使用者驗收與二次確認。

---

## 九、四庫與 Data Center

SCBKR Data Center 是模型未來工作的責任鏈資料層。

![Four Store Evidence](docs/images/four-store-evidence.png)

目前正式四庫：

| 四庫 | 作用 |
|---|---|
| vector｜向量庫 | 相似任務檢索、語意索引、責任鏈案例查詢 |
| corpus｜語料庫 | 保存原始文本、文件、外部資料、任務依據 |
| logic｜邏輯庫 | 保存流程、規則、測試條件、工程邏輯與判準 |
| memory｜記憶庫 | 保存使用者確認過的長期偏好、禁止規則與判斷標準 |

正式 UI 入庫目標只允許：

```text
vector
corpus
logic
memory
```

`exports` 不是正式四庫入庫目標。

Data Center 支援：

- 查看寫入資料
- 查看引用資料
- 查看任務紀錄
- 查看 storage item
- 更改資料
- 封存資料
- 取代資料
- 回放審計

Data Center 更改、封存、取代也必須輸入：

**資料中心使用者簽名**

Data Center 不共用 Workbench 的簽名欄。

---

## 十、四庫引用 Gate

未來任務不可亂引用資料。

SCBKR 只允許引用符合以下條件的資料：

- owner_signed
- review_passed
- storage_confirmed
- not revoked
- not archived
- not superseded
- 與目前任務相關

不可作為正式依據：

- 未簽名資料
- 未驗收資料
- revoked 資料
- archived 資料
- superseded 資料
- similar_grammar 但未明確採用的資料
- 模型臨時草案
- 外部搜尋但未驗收資料

---

## 十一、目前系統架構

SCBKR 目前架構如下：

![Architecture](docs/images/architecture.png)

目前 SCBKR 1.0 架構：

```text
React / TypeScript Web UI
        ↓
Workbench / Chat / Data Center
        ↓
FastAPI Local Backend
        ↓
SCBKR Draft Grammar / Gate System
        ↓
SQLite / JSONL Ledger / Physical Local Storage
        ↓
Four Stores: vector / corpus / logic / memory
        ↓
LM Studio / Ollama / OpenAI-compatible API
```

桌面端：

```text
Tauri Desktop Shell
→ FastAPI Sidecar
→ React Web UI
→ Local Data Center
```

手機端：

```text
Mobile Companion App / Mobile Browser
→ activeBackendUrl
→ User Local Computer
→ SCBKR Runtime
→ Local Model / Compatible API
```

手機不是獨立模型主體。

手機是連回使用者本機 SCBKR Runtime 的操作入口。

---

## 十二、模型接入

SCBKR 目前支援自接入：

- Sandbox
- LM Studio
- Ollama
- OpenAI-compatible API
- Custom endpoint

模型設定包含：

- Provider
- Mode
- Base URL
- Model Name
- API Key
- Temperature
- Max Tokens
- Timeout
- Context Length

API Key 在讀取設定時會遮罩，不應明文回傳。

---

## 十三、外部 API 與本機模型邊界

SCBKR 的安全規則：

只有 loopback URL 可視為本機模型：

```text
127.0.0.1
localhost
[::1]
```

非 loopback URL，例如：

```text
192.168.x.x
區網另一台電腦
公網 API
遠端 OpenAI-compatible endpoint
```

即使 provider 顯示為 LM Studio / Ollama，也必須視為外部模型呼叫。

外部模型呼叫必須經過 external API guard。

---

## 十四、手機同 Wi-Fi / 遠端操作定位

SCBKR 的手機定位：

**手機不是內建 LLM。**

手機是操作入口。

手機可以連回使用者自己的本機電腦 / desktop sidecar / backend。

手機可操作：

- Chat
- Workbench
- S / C / B / K / R 查看
- 使用者簽名
- 模型生成
- 驗收
- 二次確認入庫
- Data Center 查看
- 模型設定
- Backend URL 設定

目標使用方式：

```text
手機 App / 手機瀏覽器
→ 使用者指定的 activeBackendUrl
→ 本機電腦 SCBKR Runtime
→ 本地模型 / OpenAI-compatible endpoint
```

---

## 十五、SCBKR 1.0 上線目標

目前 1.0 的產品目標是：

**讓 SCBKR 成為可下載、可安裝、可連本地模型、可簽名、可驗收、可入庫、可回放的本地責任鏈基礎版。**

1.0 上線前需要整理：

- Windows installer
- macOS build / notarization roadmap
- Android companion app roadmap
- iOS companion app roadmap
- 中英文切換
- 語言包
- 基礎網頁搜尋
- 安裝說明
- 隱私政策
- 版本更新機制
- 1.0 功能公告
- 2.0 roadmap 公告

1.0 不是終點。

1.0 是可用基底。

---

## 十六、SCBKR 2.0 Roadmap

SCBKR 2.0 不是單純把 UI 做漂亮。

2.0 的產品定位是：

**規則驅動 AI 引擎作業系統**

SCBKR 2.0 的完整產品方向如下：

![SCBKR 2.0 Hero](docs/images/heroEnglish.png)

2.0 會包含兩層：

### 1. 設定規則層

負責：

- 使用者自定義規則
- 沈耀簽名規則包
- 企業內部規則
- 第三方規則包
- 規則版本
- 規則更新
- 規則回滾
- 規則採用 Gate
- 規則衝突檢查
- 規則購買 / 訂閱

### 2. 半自動 / 全自動 AI 引擎層

負責：

- Web Search
- Email 讀取
- Email 草稿
- Code Workspace
- Git / repo 操作
- 圖像生成
- 語音輸入 / 輸出
- 本機檔案
- API 工具
- 排程任務
- 工具權限矩陣
- 半自動執行
- 全自動執行

核心原則：

> 模型沒看到已成立規則，不執行決策。  
> 模型可以搜尋、整理、草擬。  
> 但只要涉及判斷、入庫、外部傳送、寄信、刪除、封存、付款、發布、長期記憶，就必須回到規則層。  

---

## 十七、2.0 最終 UI 方向

SCBKR 2.0 最終 UI 固定為：

```text
左側：規則設定層
中間：Chat 對話入口
右側：Workbench / AI 引擎工具權限
底部：Data Center / 四庫 / 回放紀錄
```

2.0 不能只做成聊天 App。

2.0 不能只做成規則後台。

2.0 不能把 Workbench 藏起來。

2.0 必須同時顯示：

- 規則從哪裡來
- 模型現在能做什麼
- 本次行動依照哪條規則成立
- 使用者是否簽名
- 是否需要驗收
- 是否需要二次確認入庫
- 是否可以半自動或全自動執行

---

## 十八、規則包與商業方向

SCBKR 2.0 的商業方向不是只賣 App。

未來可形成：

- 本地 App
- 使用者自定義規則
- 沈耀簽名規則包
- 規則包訂閱
- 客製化規則設計
- 企業規則包
- 團隊 AI 治理
- Rule Marketplace
- 工具權限套件
- 審計與回放方案

規則來源必須明確：

| 規則類型 | 說明 |
|---|---|
| 使用者自定義規則 | 使用者自己建立、自己簽名、自己承擔 |
| 沈耀簽名規則包 | 由許文耀 / 沈耀888π 建立、版本化、簽名、更新 |
| 企業內部規則 | 由企業內部制定、審核、發布 |
| 外部第三方規則 | 由其他規則作者建立 |
| 模型草案規則 | 尚未成立，只能作為草案 |

若使用者購買或啟用沈耀簽名規則包，模型執行時必須明確標示：

```text
本次判定依照：沈耀簽名規則包
版本：vX.X.X
適用範圍：……
啟用者：使用者
規則作者：許文耀 / 沈耀888π
```

不能把沈耀簽名規則包說成使用者自己設定的規則。

---

## 十九、版本更新策略

SCBKR 未來更新要分層：

| 更新層 | 說明 |
|---|---|
| App 更新 | UI、Workbench、Data Center、桌面殼、手機操作 |
| Backend 更新 | FastAPI、資料庫 schema、四庫邏輯、工具 runtime |
| 規則包更新 | 使用者規則、沈耀規則包、企業規則包 |
| 模型 Runtime 更新 | LM Studio、Ollama、OpenAI-compatible endpoint |
| 工具更新 | Web Search、Email、Code Workspace、Image、Voice、File、API |

更新不能破壞：

- 使用者簽名紀錄
- Data Center
- 四庫
- ledger
- hash
- 回放資料
- revoked / archived / superseded 狀態
- 使用者啟用的規則包狀態

更新流程應該是：

```text
檢查更新
→ 下載新版
→ 驗證 hash / signature
→ 備份本地資料
→ 停止舊版 runtime
→ 替換 App / Backend
→ 執行資料 migration
→ 檢查責任鏈相容性
→ 啟動新版
→ 成功則完成
→ 失敗則回滾
```

---

## 二十、快速開始

### 安裝 Python package

```bash
python -m pip install -e .
```

### 安裝前端依賴

```bash
npm --prefix apps/web install --package-lock=false
```

### 啟動後端

```bash
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787
```

### 啟動前端

```bash
npm --prefix apps/web run dev
```

打開：

```text
http://localhost:5500
```

---

## 二十一、桌面版 Release Candidate

Desktop package：

```text
scbkr-desktop
```

Version：

```text
0.15.0-rc.1
```

Tauri runtime：

```text
release-candidate
```

Windows RC build output：

```text
dist/scbkr-windows-desktop-rc
```

Code signing may be configured by distributor.

---

## 二十二、常用驗收命令

### Python tests

```bash
python -m pytest -q
```

### Web build

```bash
npm --prefix apps/web run build
```

### Desktop checks

```bash
npm --prefix apps/desktop run check:skeleton
npm --prefix apps/desktop run check:release
```

### Windows release build / smoke

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_desktop_release_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts/smoke_desktop_release_windows.ps1
```

### Windows preview compatibility workflow

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_desktop_preview_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts/smoke_p14c_preview_windows.ps1
```

---

## 二十三、目前已通過的驗收

目前已完成：

- Python tests 通過
- Web build 通過
- Desktop check 通過
- Release check 通過
- Windows Desktop Preview workflow 通過
- P15-Q storage second_confirm gate 修復
- P15-Q PATCH-1 smoke selected_targets 修復
- Data Center signature Gate 修復
- 四庫 UI targets 收束為 vector / corpus / logic / memory

目前可判定：

**SCBKR 1.0 Release Candidate 核心閉環完成，可進入正式實機驗收與上線整理。**

---

## 二十四、GitHub Topics 建議

建議在 GitHub About → Topics 填入：

```text
local-llm
llm-agent
ai-safety
fastapi
tauri
workflow-automation
desktop-app
ollama
lm-studio
agentic-workflow
ai-governance
human-in-the-loop
audit-trail
local-first
responsible-ai
```

---

## 二十五、Roadmap 總結

### 1.0｜本地責任鏈基礎版

目標：

- 能下載
- 能安裝
- 能連本地模型
- 能建立責任鏈
- 能使用者簽名
- 能生成
- 能驗收
- 能入庫
- 能 Data Center 查詢
- 能四庫引用
- 能手機連回本機
- 能中英文切換
- 能基礎網頁搜尋
- 能正式公告上線

### 2.0｜規則驅動 AI 引擎作業系統

目標：

- 規則中心
- 規則包訂閱
- 沈耀簽名規則庫
- 工具權限
- 半自動 AI 引擎
- 全自動 AI 引擎
- Web Search
- Email
- Code Workspace
- Image Generation
- Voice I/O
- Rule Marketplace
- Team / Enterprise Governance

---

## 二十六、核心宣言

SCBKR 的核心不是讓模型更像主人。

SCBKR 的核心是讓模型回到責任鏈裡。

```text
模型可以協助，但不能越權。
使用者可以定義，但必須簽名。
規則可以引用，但必須有效。
資料可以入庫，但必須驗收。
AI 可以執行，但必須依照責任鏈。
```

---

## 二十七、署名

語意防火牆創辦人  
許文耀 / 沈耀888π

Founder of Semantic Firewall  
Wen-Yao Hsu / ShenYao888π

SCBKR Local Responsibility Chain Model