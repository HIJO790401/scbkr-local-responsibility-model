# SCBKR 本地責任鏈模型｜Local Responsibility Chain Model

**SCBKR Local Responsibility Chain Model** 是一套本地 AI 責任鏈控制系統。

它不是一般聊天機器人。
它不是單純 RAG。
它不是模型公司。
它不是讓模型替使用者直接決定答案的工具。

SCBKR 的核心是：

> 讓模型在生成之前，先進入任務責任鏈；
> 讓使用者在規則成立之前，保留最終簽名權；
> 讓可用的判準進入四庫，成為後續任務可索引、可回放、可驗收的依據。

SCBKR 不靠無限堆疊聊天上下文維持記憶。
SCBKR 靠的是：

* SCBKR 五維確認單
* 使用者簽名
* 驗收 gate
* 二次確認入庫
* Data Center
* 四庫索引
* ledger / hash / replay
* owner-signed evidence reuse

換句話說：

> 模型可以參與，但模型不能越權。
> 模型可以生成草案，但規則必須由使用者簽名才成立。
> 模型可以引用資料，但只能引用已簽名、已驗收、未撤銷的資料。

---

## 一、產品定位

SCBKR 是一套 **本地 AI 工作流責任鏈控制層**。

使用者可以在自己的電腦上接入：

* LM Studio
* Ollama
* OpenAI-compatible API
* 其他自訂模型 endpoint
* Sandbox 模式

SCBKR 不直接把使用者輸入丟給模型自由回答，而是將任務轉成可確認、可修改、可簽名、可驗收、可入庫、可回放的責任鏈流程。

核心定位：

```text
Chat 是自然語言入口。
Workbench 是責任鏈確認台。
S/C/B/K/R 是任務責任語法。
Data Center 是可回放資料中心。
四庫是可索引規則層。
模型是草案與編譯助手。
使用者是最終簽名者。
```

---

## 二、SCBKR 解決什麼問題

一般 AI 產品常見問題：

* 使用者一輸入，模型立刻生成。
* 任務目的不清楚，模型仍然硬答。
* 權限、資料來源、風格、驗收條件沒有先確認。
* 模型生成錯誤後，使用者只能反覆重問。
* 每次任務都從零開始，無法累積有效判準。
* 聊天上下文越來越長，最後只能換視窗或重新整理背景。
* 記憶黑箱，不知道模型引用了什麼。
* 錯誤答案容易污染未來任務。

SCBKR 的解法：

```text
使用者輸入
→ 系統判斷 intent
→ 建立確認單
→ 模型產生 Task Understanding
→ 系統編譯 S/C/B/K/R
→ 使用者修改
→ 使用者簽名
→ 模型生成
→ 使用者驗收
→ 入庫建議
→ 二次確認寫入
→ 四庫索引
→ Data Center 回放
→ 後續任務引用已簽名規則
```

SCBKR 的重點不是讓模型更自由，而是讓模型在明確的責任鏈中工作。

---

## 三、SCBKR 五維責任鏈

每個正式任務都會被轉成 SCBKR 五維確認單。

### S｜Subject / 任務主體

定義：

* 任務名稱
* 使用者原始指令
* 任務主體
* 輸出形式
* 操作介面

S 不是普通標題。
S 是任務是否成立的主體入口。

---

### C｜Causality / 流程因果

定義：

* 流程步驟
* 執行順序
* 資料流
* 依賴條件
* 測試條件
* 核心因果鏈

C 不是普通步驟清單。
C 要說明任務為什麼可以被執行、如何執行、錯在哪裡會中斷。

---

### B｜Boundary / 邊界行為

定義：

* 可讀範圍
* 可寫範圍
* 可呼叫服務
* 停止條件
* 入庫限制
* 禁止行為

B 是模型行動邊界。

模型不得自行確認。
模型不得自行簽名。
模型不得自行驗收。
模型不得自行入庫。
模型不得自行修改或刪除 Data Center。

---

### K｜Knowledge / 依據風格

定義：

* 使用者原始輸入
* 已採用引用
* 類似語法
* 類似邏輯
* 候選但未採用
* 衝突 / 待確認
* 來源可信度
* 風格設定

K 不是把所有搜尋結果都塞給模型。

SCBKR 會區分：

```text
direct_match        可作為正式依據
same_domain         可作為同領域依據
similar_logic       可作為邏輯參考
style_reference     可作為風格參考
similar_grammar     只能參考語法，不得作為正式依據
candidate_only      候選但不採用
irrelevant          不相關
conflict            衝突，需使用者確認
```

---

### R｜Replay / 回放驗收

定義：

* 預期輸出
* 驗收條件
* 回放要求
* 入庫選項
* 使用者簽名狀態
* 審計資料

R 是閉環層。

沒有使用者簽名，SCBKR 不成立。
沒有驗收通過，不能入庫。
沒有二次確認，不能 physical write。

---

## 四、模型角色

SCBKR 不是禁止模型，而是鎖定模型權限。

模型可以：

* 理解使用者任務
* 產生 Task Understanding
* 協助生成 SCBKR 草案
* 協助修改 S/C/B/K/R
* 協助生成正式結果
* 協助整理入庫建議
* 協助查詢 Data Center
* 協助建立更改 / 刪除確認單
* 協助引用已簽名四庫資料

模型不能：

* 自行確認責任鏈
* 自行簽名
* 自行驗收
* 自行入庫
* 自行修改 Data Center
* 自行刪除 Data Center
* 把候選資料當作已引用
* 把未簽名資料當成規則
* 把類似語法當成正式依據
* 繞過使用者確認

模型在 SCBKR 裡的角色是：

```text
describe_compile_only
```

也就是：

> 模型只能描述、理解、拆解、編譯草案。
> 規則是否成立，由使用者簽名決定。

---

## 五、Chat 與 Workbench

SCBKR 的 Chat 不是單純聊天框。

Chat 是自然語言入口。

使用者可以在 Chat 輸入：

* 我要生成一個商業文案確認單
* 幫我做責任鏈
* 幫我建確認單
* 幫我把這段規則寫進工作台
* 幫我查某天的資料中心紀錄
* 幫我修改某條記憶庫規則
* 幫我封存某筆資料

系統會先判斷 intent。

如果只是一般聊天，走 Chat。
如果適合生成確認單，顯示建議卡。
如果使用者明確要求生成確認單，進入 Workbench。

Workbench 負責：

* 顯示任務摘要
* 顯示草案來源
* 顯示 S/C/B/K/R 五卡
* 顯示引用證據
* 支援模型修改工作台
* 支援使用者簽名
* 支援生成
* 支援驗收
* 支援入庫建議
* 支援二次確認寫入

Chat 不負責直接成立規則。
Workbench 才是責任鏈確認台。

---

## 六、四庫與 Data Center

SCBKR 的 Data Center 不是展示頁，而是模型未來工作的規則來源層。

### 1. 向量庫｜Vector Store

用途：

* 相似任務檢索
* 已驗收任務索引
* 降低重複推理
* 提供未來任務的候選引用

### 2. 語料庫｜Corpus Store

用途：

* 保存使用者確認過的原始資料
* 保存外部文件
* 保存對話樣本
* 避免模型憑空編造來源

### 3. 程式邏輯庫｜Logic Store

用途：

* 保存流程規則
* 保存判斷條件
* 保存停止條件
* 保存行動邊界
* 保存產品邏輯
* 保存可重用工作流

### 4. 記憶庫｜Memory Store

用途：

* 保存使用者長期判準
* 保存禁止規則
* 保存偏好
* 保存已簽名主體判斷
* 防止模型反覆犯同樣錯誤

---

## 七、四庫引用規則

後續任務引用四庫時，不是單純關鍵字比對。

資料要被採用，必須符合：

```text
signature_status = owner_signed
review_passed = true
status 不得為 revoked / archived / superseded
relation 必須是 direct_match / same_domain / similar_logic / style_reference
不得只靠泛詞命中
```

例如：

* 只有「文案」相同，不可採用。
* 只有「規則」相同，不可採用。
* UI 工作台規則不可被餐飲文案任務採用。
* 未簽名資料不可採用。
* 驗收未通過資料不可採用。
* revoked / archived / superseded 資料不可採用。
* similar_grammar 只能作為語法參考，不得作為正式依據。

引用必須顯示 evidence：

* 來源庫
* relation
* adoption_scope
* relation_reason
* task_id
* storage_item_id
* signature_status
* hash / content_hash
* review_passed
* rule_confirmed
* adopted true / false

---

## 八、為什麼 SCBKR 不依賴無限聊天上下文

一般 AI 產品容易遇到：

* 對話太長
* 上下文爆掉
* 模型忘記前面規則
* 必須換視窗
* 使用者反覆貼背景
* token 成本持續上升

SCBKR 的設計不是把所有聊天內容一直塞給模型。

SCBKR 將有價值的內容轉成：

```text
已簽名確認單
已驗收結果
已入庫規則
可回放 Data Center 紀錄
可索引四庫資料
```

下一次任務不需要吃完整聊天歷史，只需要：

* 當前使用者輸入
* 當前 task 狀態
* SCBKR Grammar Pack
* 採用的四庫 evidence
* 必要的 Workbench 草案資料

這樣可以降低：

* 無效 token
* 重複推理
* 背景重貼
* 長上下文漂移
* 錯誤記憶污染

---

## 九、權限與安全邊界

SCBKR 的核心安全原則：

```text
工具未啟用，不得宣稱已執行。
模型未測通，不得宣稱可用。
使用者未簽名，不得 confirmed。
責任鏈未確認，不得生成。
驗收未通過，不得入庫。
未二次確認，不得 physical write。
失敗輸出不得污染記憶。
非本機模型網址不得假裝成本地模型。
```

目前權限鎖包含：

* model_generate
* external_api
* dangerous_operation_confirmed
* storage_write
* ledger_write
* sqlite_runtime
* chromadb_runtime
* embedding_create
* memory_write

外部 API / hybrid 模式必須通過：

```text
external_api = true
dangerous_operation_confirmed = true
```

否則不得呼叫外部 API。

本機模型 URL：

* 127.0.0.1
* localhost
* [::1]

非 loopback URL，例如：

* 192.168.x.x
* 區網另一台電腦
* 公網 API
* 遠端 OpenAI-compatible endpoint

即使 provider 顯示為 LM Studio / Ollama / local mode，也必須視為外部模型呼叫，必須經過 external_api 授權。

---

## 十、核心流程

完整流程：

```text
使用者輸入
→ Chat intent routing
→ 建立 SCBKR 確認單
→ 查詢 Data Center / 四庫
→ Evidence Relation Gate
→ 模型產生 Task Understanding
→ Understanding Compiler 編譯 S/C/B/K/R
→ Workbench 顯示草案
→ 使用者修改 / 要求模型修改
→ 使用者輸入簽名
→ confirmed = true
→ signature_status = owner_signed
→ 開始生成
→ 使用者驗收
→ review_passed = true
→ 產生入庫建議
→ 使用者選擇四庫
→ 使用者二次確認寫入
→ physical write
→ ledger / hash / replay
→ 後續任務引用 owner-signed evidence
```

---

## 十一、目前版本階段

目前版本定位：

```text
SCBKR 本地責任鏈模型｜Release Candidate 收束中
SCBKR Local Responsibility Chain Model｜Release Candidate Alignment
```

目前技術階段：

```text
P15-P 核心閉環已完成
P15-Q Release Candidate 收束尚未執行
```

P15-P 已完成重點：

* Chat intent routing
* Chat-to-Workbench 確認單建立
* SCBKR Grammar Pack
* Task Understanding
* Understanding Compiler
* model_assisted_structured / scbkr_base_logic / draft_failed 草案來源
* 主流程移除 fallback 草案語意
* Evidence Relation Classifier
* Owner Signature Gate
* 使用者簽名確認
* 模型不能簽名
* 修改後重簽機制
* confirmed gate
* generation gate
* review gate
* storage_confirm gate
* second_confirm gate
* 四庫寫入 payload metadata
* Data Center 分類讀取
* owner_signed evidence 後續引用
* external_api guard
* activeBackendUrl routing
* Model Settings
* API key masking
* LM Studio / Ollama / OpenAI-compatible API 接入
* Windows desktop preview build 基礎
* sidecar API build 基礎

目前已知待處理：

### P15-Q Release Candidate 收束

P15-Q 尚未下達指令，預計下一輪處理。

P15-Q 目標：

* 修正 Windows smoke script 對 P15-P gate 的相容性
* storage-confirm smoke payload 補上 second_confirm=true
* 保留 P15-P 使用者簽名與二次確認 gate
* 移除 storage 階段假簽名字串
* 修改 / 重生 / 退回後清空前端簽名
* repo metadata 從 preview / skeleton 收束為 Release Candidate
* desktop package name 移除 skeleton
* tauri.conf 移除 preview / not production installer 語意
* main.rs 移除 SCBKR_DESKTOP_PREVIEW 語意
* README 更新為正式產品定位
* 新增 / 對齊 release build script
* 新增 / 對齊 release smoke script
* Windows installer build 驗收
* 完整流程實機驗收

---

## 十二、目前可跑能力

目前系統已支援：

* 本地 FastAPI API
* React + Vite + TypeScript Web UI
* Windows Desktop / Tauri preview build
* FastAPI sidecar build
* Sandbox 模式
* 模型 Provider 設定
* LM Studio / Ollama / OpenAI-compatible API 設定
* API key 遮罩與清除
* 模型連線測試
* 一般 Chat 入口
* Chat intent routing
* Chat-to-Workbench 建議卡
* 任務建立
* SCBKR 五維草案生成
* 模型 Task Understanding
* 系統編譯 S/C/B/K/R
* 使用者修改 / 模型修改工作台
* 使用者簽名確認
* confirmed 後才可 generate
* 模型正式生成
* 驗收 pass / fail / rollback
* 入庫建議
* 使用者二次確認入庫
* Data Center 讀回
* ledger / hash / audit
* 四庫引用 context
* owner_signed evidence reuse
* activeBackendUrl routing
* external_api guard
* 非 loopback model URL 安全阻擋
* 手機同 Wi-Fi 連線基礎

---

## 十三、尚未完成 / 待正式收束

以下不是產品概念缺口，而是 Release Candidate 發行與上線前收束項：

* P15-Q 尚未執行
* Windows smoke script 需對齊 P15-P second_confirm gate
* Desktop metadata 仍需從 preview / skeleton 收束
* README 舊階段描述需更新
* Release build script 需正式化
* Release smoke script 需正式化
* code signing 尚未設定
* auto-update 尚未設定
* macOS package 尚未完成
* Linux package 尚未完成
* 手機原生 App 尚未提供
* Google Play 版本尚未提供
* Microsoft Store 提交流程尚未整理
* 英文 UI label pack 尚未完成
* 多語系切換尚未完成
* 雲端 SaaS 版本尚未提供
* 外網 tunnel 不自動設定
* model bundle 不內建
* API key 不內建

---

## 十四、固定端口

後端 API：

```text
http://localhost:8787
```

前端 Web：

```text
http://localhost:5500
```

LM Studio 常見本機 endpoint：

```text
http://localhost:1234/v1
```

Ollama OpenAI-compatible endpoint：

```text
http://localhost:11434/v1
```

注意：

```text
localhost / 127.0.0.1 表示同一台電腦本機。
192.168.x.x 或遠端網址會被視為外部模型連線，需要 external_api 授權。
```

---

## 十五、快速開始

安裝 Python package：

```bash
python -m pip install -e .
```

安裝前端依賴：

```bash
npm --prefix apps/web install --package-lock=false
```

啟動後端：

```bash
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787
```

啟動前端：

```bash
npm --prefix apps/web run dev
```

打開：

```text
http://localhost:5500
```

---

## 十六、常用測試

後端與單元測試：

```bash
python -m pytest -q
```

前端 build：

```bash
npm --prefix apps/web run build
```

Desktop skeleton / release check：

```bash
npm --prefix apps/desktop run check:skeleton
```

API title smoke：

```bash
python - <<'PY'
from apps.api.main import app
print(app.title)
PY
```

Windows desktop build / smoke 目前正在 P15-Q 收束中。
P15-Q 將對齊 P15-P 的 owner signature、review gate、second confirm storage gate。

---

## 十七、模型接入

使用者可自行接入：

* Sandbox
* LM Studio
* Ollama
* OpenAI-compatible API
* 自訂 endpoint

模型設定包含：

* Provider
* Mode
* Base URL
* Model Name
* API Key
* Temperature
* Max Tokens
* Timeout

API Key 在讀取設定時只會遮罩，不會明文回傳。

---

## 十八、手機同 Wi-Fi 使用

若前端開發伺服器使用 LAN host 啟動，手機與電腦在同一 Wi-Fi 下，可用手機打開：

```text
http://{電腦區網IP}:5500
```

手機可以作為操作入口：

* 聊天
* 打開 Workbench
* 設定 Backend API URL
* 設定模型
* 建立確認單
* 查看 S/C/B/K/R
* 使用者簽名
* 生成
* 驗收
* 二次確認入庫
* 查看 Data Center

手機不是內建 LLM。
手機端資料仍透過 activeBackendUrl 連回使用者指定的本地後端 / desktop sidecar / API。

---

## 十九、英文版規劃

英文版不重寫底層邏輯。

英文版將以 label pack / i18n 方式處理：

```text
聊天 → Chat
工作台 → Workbench
資料中心 → Data Center
確認責任鏈 → Confirm Responsibility Chain
使用者簽名 → Owner Signature
入庫建議 → Storage Recommendation
二次確認寫入 → Second Confirm Storage
審計資料 → Audit
```

底層仍維持：

* S/C/B/K/R
* owner_signature_required
* model_role = describe_compile_only
* confirmed gate
* review gate
* storage_confirm gate
* second_confirm gate
* Evidence Relation Gate
* Data Center
* 四庫
* ledger / hash / replay

---

## 二十、English Summary

SCBKR Local Responsibility Chain Model is a local AI responsibility-chain control system.

It is not a general chatbot.
It is not a simple RAG tool.
It is not a model company.
It does not allow the model to directly decide and act on behalf of the user.

SCBKR makes the model enter a responsibility-chain workflow before generation.

The system uses:

* Chat as the natural-language entry
* Workbench as the confirmation surface
* S/C/B/K/R as the responsibility-chain grammar
* Data Center as the replayable storage layer
* Four stores as reusable indexed rule stores
* Owner signature as the rule closure condition

The model can assist, draft, describe, and compile.
The model cannot confirm, sign, review, store, update, or delete by itself.

A rule only becomes valid after owner signature.
A result can only be stored after review and second confirmation.
Future tasks can only reuse evidence that is owner-signed, review-passed, and not revoked / archived / superseded.

Current stage:

```text
P15-P core closure completed.
P15-Q Release Candidate alignment pending.
```

---

## 二十一、產品原則

```text
模型不是先回答，而是先交代。
模型不是先生成，而是先確認。
模型可以參與，但不能越權。
規則不是模型成立，而是使用者簽名成立。
資料不是自動記憶，而是驗收後入庫。
引用不是關鍵字命中，而是 evidence relation。
聊天不是無限上下文，而是四庫索引與責任鏈回放。
```

---

## 二十二、簽名

語意防火牆創辦人
許文耀 / 沈耀888π

Founder of Semantic Firewall
Wen-Yao Hsu / ShenYao888π
