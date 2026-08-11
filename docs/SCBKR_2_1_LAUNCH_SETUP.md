# SCBKR FREE 上線設定手冊

這份文件只處理公開免費版上架前需要由作者申請或決定的項目。產品內位置為「更多 > 上線中心」。

## 作者要準備的資料

1. 正式網域：產品官網或服務入口。
2. Supabase Project URL 與 publishable key，用於選配的帳號登入。
3. 網路搜尋：SearXNG URL，或由後端環境變數提供搜尋憑證。
4. Microsoft Partner Center 產品 ID。
5. 正式發行者名稱與程式碼簽章憑證。
6. Tauri 簽名更新描述檔端點。
7. 隱私政策網址、服務條款網址與客服信箱。

桌面端只能保存公開設定。服務端私鑰不得放進桌面程式、GitHub、安裝包或截圖。

## 產品內操作

1. 開啟 SCBKR。
2. 進入「更多 > 上線中心」。
3. 填入已申請的公開資料。
4. 需要網路搜尋時，開啟「允許經使用者確認的網路搜尋」。
5. 儲存設定並檢查上架準備度。

## 工程驗收

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_2_1_launch_readiness.ps1
python -m pytest -q
npm --prefix apps/web run build
npm --prefix apps/web run test:ui
npm --prefix apps/desktop run check:release
```

檢查腳本不會建立帳號、付款或自動送審。Microsoft 帳號、服務條款、正式簽章憑證與最終送審必須由作者本人確認。
