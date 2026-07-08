# SCBKR 本地 AI 責任鏈 Runtime  
# SCBKR Local-first AI Responsibility Chain Runtime

> **SCBKR：讓 AI 不必每次重想。**  
> **SCBKR: Stop making AI rethink everything.**

由 **許文耀 / 沈耀 SCBKR Kernel** 驅動的本地 AI 責任鏈系統。  
把使用者的判斷編譯成可簽名、可入庫、可引用的本地規則，讓模型不再依賴長上下文亂猜。

A local-first AI responsibility-chain runtime powered by the **Wen-Yao Hsu / ShenYao SCBKR Kernel**.  
It turns user judgments into signed, local, citable rules — so models reason from four-store rule packages instead of polluted long context.

---

## Current Audit｜目前實測

**Current measured context compression：97.9%**  
**目前實測上下文壓縮率：97.9%**

- Full Context：`107,394 tokens`
- Rule Package：`2,257 tokens`
- Compression：`97.9%`
- Formal Basis：`signed_active_four_store_rules_only`
- Chat Context Used as Formal Basis：`No`
- Target Release：`≥98.06%`

SCBKR 不宣稱空泛節省。  
每次正式回答都可以產生 Token / Cost Audit，檢查模型是否真的從完整上下文切換成最小 `current_rule_package`。

SCBKR does not claim abstract savings.  
Each formal answer can produce a Token / Cost Audit to verify whether the model actually moves from full-context reasoning to a minimal `current_rule_package`.

---

## Visual Overview｜圖卡總覽

### 1. AI Agent 的真正浪費  
### The Real Waste of AI Agents

![AI Agent 的真正浪費](<docs/images/AI Agent 的真正浪費.png>)

AI Agent 不是只耗電，是每次都在重想。  
長上下文、重複推理、工具亂跑、GPU 空轉。真正的浪費，是沒有責任鏈。

AI Agents do not just consume power — they rethink everything.  
Long context, repeated reasoning, tool over-calling, and GPU idle time are symptoms of a missing responsibility chain.

---

### 2. SCBKR 的核心解法  
### The Core SCBKR Solution

![SCBKR 的核心解法](<docs/images/SCBKR 的核心解法.png>)

不要把整個世界丟給模型。  
SCBKR 把使用者判斷變成本地規則；簽名後入四庫；之後只給模型最小規則包。

Stop feeding the whole world to the model.  
SCBKR turns user judgments into local rules; after signature and four-store commit, the model only receives the minimal rule package.

---

### 3. 四庫才是正式判斷標準  
### Four Stores Define the Formal Basis

![四庫才是正式判斷標準](<docs/images/四庫才是正式判斷標準.png>)

SCBKR 不把所有資料都塞給模型。  
它把正式依據拆成四庫：

SCBKR does not dump all data into the model.  
It separates formal authority into four stores:

| Store | 中文 | English |
|---|---|---|
| LOGIC | 已簽名、已啟用的本地規則 | Signed and active local rules |
| CORPUS | 使用者確認的正式資料 | Verified user-confirmed data |
| MEMORY | 使用者長期偏好與限制 | Long-term user preferences and constraints |
| VECTOR | 只召回，不作正式依據 | Recall only, not formal basis |

**Chat context is not formal basis.**  
**聊天上下文不是正式依據。**

---

### 4. Token Audit 實測數字  
### Measured Token / Cost Audit

![Token Audit 實測數字](<docs/images/Token Audit 實測數字.png>)

目前實測：

Current audit:

| Metric | Value |
|---|---:|
| Full Context | `107,394 tokens` |
| Rule Package | `2,257 tokens` |
| Compression | `97.9%` |
| Chat context as formal basis | `No` |
| Target | `≥98.06%` |

這代表模型不再每次讀完整上下文，而是讀取最小正式規則包。

This means the model no longer reads the full context every time; it reads the minimal formal rule package.

---

### 5. 模型只草擬，使用者才簽名  
### The Model Drafts. The User Signs.

![模型只草擬，使用者才簽名](<docs/images/模型只草擬，使用者才簽名.png>)

模型不能簽名。  
模型不能入庫。  
模型不能啟用。  
模型不能終裁。  
使用者簽名後，規則才成立。

The model cannot sign.  
The model cannot store.  
The model cannot activate.  
The model cannot make final rulings.  
A rule becomes valid only after user signature.

**Kernel 提供結構，使用者承擔責任。**  
**Kernel provides structure. The user owns responsibility.**

---

### 6. 一句產品定位  
### Product Positioning

![一句產品定位](<docs/images/一句產品定位.png>)

SCBKR 不是更大的 Agent。  
它是 Agent 前面的本地責任鏈節能層。

SCBKR is not a bigger Agent.  
It is the local responsibility-chain layer before the Agent.

**Rule first. Context second. Responsibility always.**  
**規則優先。上下文其次。責任永遠在場。**

---

## What SCBKR Solves｜SCBKR 解決什麼

AI Agent 的問題不只是模型太大，而是它每次都在重新判斷。

The problem with AI Agents is not only model size.  
The deeper problem is repeated reasoning.

一般 AI Agent 會把聊天歷史、工具結果、檢索候選、舊記憶、未確認資料混在一起，反覆丟進模型重新推理。  
這會造成：

Typical AI Agents repeatedly push chat history, tool outputs, retrieval candidates, old memory, and unverified data back into the model.  
This causes:

- 高 token 成本  
  High token cost

- 上下文污染  
  Context pollution

- 工具過度呼叫  
  Tool over-calling

- GPU / 算力浪費  
  GPU / compute waste

- 責任鏈不清  
  Unclear responsibility chain

SCBKR 的做法相反：

SCBKR does the opposite:

1. 先把使用者判斷編譯成規則  
   Compile user judgments into rules first

2. 再由使用者編輯與簽名  
   Let the user edit and sign

3. 然後寫入本地四庫  
   Commit into local four stores

4. 最後只給模型最小 `current_rule_package`  
   Then give the model only the minimal `current_rule_package`

---

## SCBKR Runtime Algorithm｜SCBKR 運行算法

SCBKR 的核心不是讓模型變大，而是讓模型少猜。

The core of SCBKR is not making the model bigger.  
It is making the model guess less.

### Flow｜流程

1. **Input｜輸入**  
   使用者輸入聊天、判斷、文案、程式或規則需求。  
   The user enters a chat, judgment, copywriting task, coding request, or rule request.

2. **Route｜路由**  
   系統判斷任務類型：一般聊天、生成規則、寫程式、寫文案、正式判斷。  
   The runtime classifies the task: chat, rule generation, coding, copywriting, or formal judgment.

3. **Kernel Compile｜Kernel 編譯**  
   若使用者要建立規則，系統載入本地 SCBKR Kernel，將輸入編譯成 S/C/B/K/R。  
   If the user wants a rule, the local SCBKR Kernel compiles the input into S/C/B/K/R.

4. **Validator｜驗證器**  
   第0定理、成立條件、失效條件、責任鏈、回放、修復條件會被檢查。  
   不合格不得入庫。  
   The Zeroth Theorem, validity conditions, failure conditions, responsibility chain, replay, and repair path are checked.  
   Invalid drafts cannot be stored.

5. **User Signature｜使用者簽名**  
   模型只能草擬。使用者簽名後，規則才成立。  
   The model can only draft. The rule becomes valid only after user signature.

6. **Four-Store Commit｜四庫入庫**  
   規則與資料寫入本地四庫：LOGIC、CORPUS、MEMORY、VECTOR。  
   Rules and data are committed into local stores: LOGIC, CORPUS, MEMORY, VECTOR.

7. **Minimal Rule Package｜最小規則包**  
   後續回答時，只載入命中的 `current_rule_package`。  
   不再把完整聊天與記憶丟給模型。  
   Future answers load only the matched `current_rule_package`.  
   The full chat history and memory dump are no longer pushed into the model.

8. **Formal Answer｜正式回答**  
   模型根據已簽名、已啟用的本地規則回答。  
   VECTOR 只召回，不作正式依據。  
   The model answers based on signed and active local rules.  
   VECTOR is recall-only and cannot be used as formal basis.

---

## Formula｜核心公式

### Full Context Reasoning｜長上下文推理

Full chat history  
+ full memory dump  
+ tool outputs  
+ retrieval candidates  
+ unverified data  
+ unsigned drafts  
= high token cost + context pollution + repeated reasoning

完整聊天歷史  
+ 完整記憶  
+ 工具輸出  
+ 檢索候選  
+ 未確認資料  
+ 未簽名草稿  
= 高 token 成本 + 上下文污染 + 重複推理

---

### SCBKR Rule Package Reasoning｜SCBKR 規則包推理

Signed rules  
+ citable data  
+ user preferences  
+ boundaries  
+ responsibility conditions  
+ failure conditions  
= minimal context + replayable judgment + auditable responsibility

已簽名規則  
+ 可引用資料  
+ 使用者偏好  
+ 邊界條件  
+ 責任條件  
+ 失效條件  
= 最小上下文 + 可回放判斷 + 可審計責任鏈

---

## Plan Depth｜付費不是模板，是編譯深度

SCBKR does not sell templates.  
SCBKR sells compilation depth.

SCBKR 不販售模板。  
SCBKR 提供的是讓本地模型照責任鏈工作的編譯深度。

| Plan | 中文 | English |
|---|---|---|
| FREE | 基本五維規則、使用者自簽、本地入庫、本地引用 | Basic S/C/B/K/R rules, user self-signature, local storage, local citation |
| NT$690 | 責任鏈補強、缺資料追問、停止條件、模型不可越權提醒 | Responsibility-chain assistance, missing-data questions, stop conditions, model boundary warnings |
| NT$3,300 | 規則書閉環、成立 / 失效條件、風險分級、修復、回放、雙簽、RulePack | Rulebook closure, validity / failure conditions, risk levels, repair paths, replay, dual signature, RulePack |

---

## Product Status｜目前狀態

- Product runtime：Local-first SCBKR Runtime
- Current audit：`97.9% context compression`
- Target audit：`≥98.06%`
- Formal basis：`signed_active_four_store_rules_only`
- Chat context as formal basis：`No`
- Model role：`draft_only`
- User data：local-first
- VECTOR：recall only, not formal basis

---

## Acceptance｜驗收命令

```bash
python -m pytest -q
npm --prefix apps/web run test:ui -- --reporter=line
npm --prefix apps/web run build
````

---

## Signature｜署名

**SCBKR Local-first AI Responsibility Chain Runtime**
**Powered by Wen-Yao Hsu / ShenYao SCBKR Kernel**

**SCBKR 本地 AI 責任鏈 Runtime**
**由許文耀 / 沈耀 SCBKR Kernel 驅動**
