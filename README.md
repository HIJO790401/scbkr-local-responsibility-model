# SCBKR 本地責任鏈模型

SCBKR 不是聊天機器人。
SCBKR 是本地 AI 責任鏈工作台。

核心流程：

```text
輸入 → SCBKR → confirmed → generate → review → storage_confirmed → 四庫 → ledger
```

## 五維責任鏈

- S｜介面 / 主體
- C｜後端 / 因果
- B｜邊界 / 行為
- K｜依據 / 風格
- R｜回放 / 簽名

## 核心鎖

- confirmed 鎖：`confirmed = false` 時不得 generate。
- review_passed 鎖：`review_passed = false` 時不得進入標準入庫流程。
- storage_confirmed 鎖：`storage_confirmed = false` 時不得寫入四庫。

## P0-P12 施工順序

- P0｜專案初始化
- P1｜任務與 SCBKR 結構
- P2｜回放帳本
- P3｜前端主畫面
- P4｜SCBKR 生成器
- P5｜模型接口
- P6｜任務生成流程
- P7｜驗收與回退
- P8｜四庫寫入
- P9｜向量檢索
- P10｜權限鎖
- P11｜驗收失敗入記憶規則
- P12｜測試與文件

## P0 狀態

P0 只是 skeleton，不是功能完成。
本階段僅建立 root files、固定資料夾、config placeholder、schema placeholder、docs skeleton、scripts placeholder。
