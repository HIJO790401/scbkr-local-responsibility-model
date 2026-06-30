# SCBKR 2.1 上線設定手冊

這份文件只處理真正上線前需要由作者申請或決定的項目。工程介面已放在產品的「更多 > 上線中心」。資料填齊後，畫面會自動更新準備度。

## 先記住一件事

- 桌面端只能填公開金鑰，例如 Supabase publishable key、Stripe publishable key。
- Stripe secret key、Webhook secret、服務端管理金鑰不得放進桌面程式、GitHub 或截圖。
- 沈耀規則狀態販售的是 Runtime 使用資格，不是私有規則原文。

## 作者要準備的 8 項資料

1. 正式網域：產品官網或服務入口，例如 `https://scbkr.example`。
2. Supabase：Project URL 與 publishable key，用於帳號登入。
3. Stripe：publishable key、月費 Price ID、年費 Price ID、Customer Portal URL。
4. 網路搜尋：SearXNG URL，或由後端環境變數 `SCBKR_BRAVE_API_KEY` 提供 Brave Search API key。若要維持免費可控，優先自架 SearXNG。
5. Microsoft Partner Center：產品 ID，用於 Windows 商店送審。
6. 程式碼簽章：正式發行者名稱與憑證主體。
7. 更新端點：未來放置 Tauri 簽名更新描述檔的位置。
8. 法律與客服：隱私政策網址、服務條款網址、客服信箱。

## 產品內操作

1. 開啟 SCBKR。
2. 進入「更多 > 上線中心」。
3. 將已申請好的公開資料填入對應欄位。
4. 網路搜尋區開啟「允許經使用者確認的網路搜尋」。
5. 按「儲存上線設定」。
6. 檢查上架準備度；未完成項目會標示「需你申請」或「工程」。

本機作者預覽另需先設定環境變數 `SCBKR_OWNER_PREVIEW_TOKEN`，再把同一組值填入「作者預覽權杖」。一般訂閱者不能使用此入口；正式訂閱只接受服務端 entitlement 紀錄，不能由客戶端自行宣稱有效。

## 訂閱商品定義

- 月費與年費都授予 `ShenYao Rule State Runtime` entitlement。
- entitlement 決定可用版本、模式、更新通道與有效期限。
- 客戶端只收到狀態回執、版本資訊及運算結果，不收到私有規則來源。
- 使用者可以在有效狀態下建立自己的規則覆寫；覆寫仍需簽名、驗算與回放。
- entitlement 失效後切回 `INDEPENDENT`，不得假裝仍在沈耀規則狀態。

## 工程驗收

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_2_1_launch_readiness.ps1
python -m pytest -q
npm --prefix apps/web run build
npm --prefix apps/web run test:ui
```

`check_2_1_launch_readiness.ps1` 只讀取狀態，不會送出帳號資料、不會購買服務，也不會自動送審商店。

## 尚未自動完成的外部動作

- 建立或付款購買第三方帳號。
- 接受 Stripe、Supabase 或 Microsoft 的服務條款。
- 取得正式程式碼簽章憑證。
- 按下 Microsoft Store 的最終送審按鈕。
- 把正式私鑰部署到雲端服務端。

這些動作必須由作者持有帳號並確認。其餘產品端設定、檢查、建置與測試可由 Codex 接手操作。
