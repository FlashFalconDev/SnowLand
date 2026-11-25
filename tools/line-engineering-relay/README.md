# SnowLand LINE 工程訊息中繼

Cloudflare Worker 接收 LINE Messaging API webhook，將群組內包含「工程」的文字訊息逐筆送到 Cursor Automation webhook。

## 運作方式

- 僅接受 POST，請求體上限為 1 MiB。使用 `LINE_CHANNEL_SECRET` 和原始位元組驗證 `X-Line-Signature`。
- 驗簽成功立即回 HTTP 200，並透過 `ctx.waitUntil` 在背景篩選與轉發。LINE 驗證請求與不符合條件的事件不會轉發。
- 每則符合條件的訊息送出一筆 JSON POST。若 LINE 未提供 `userId`，該欄位為 `null`。
- 中繼目的地由 `wrangler.toml` 的 `RELAY_WEBHOOK_URL` 指定。Worker 只記錄轉發失敗狀態，且不使用 LINE access token。

## 在本機執行離線測試

在 `tools/line-engineering-relay/` 使用 Node.js 22 以上版本執行。測試使用 `node:test` 並模擬下游 HTTP 請求與 `ctx.waitUntil`。

```powershell
npm install --offline --no-audit --no-fund --cache .npm-cache
npm test
```

## 部署到 Cloudflare

1. 在 `tools/line-engineering-relay/` 登入並部署 Worker。首次執行 `npx wrangler` 時，可能會提示下載 Wrangler。

   ```powershell
   npx wrangler login
   npx wrangler deploy
   ```

2. 在同一目錄以互動提示輸入兩把密鑰。**`LINE_CHANNEL_SECRET` 由小陌本人輸入，不要貼在聊天或 commit 裡。** `RELAY_SIGNING_SECRET` 必須和接收端用來驗簽的密鑰相同。

   ```powershell
   npx wrangler secret put LINE_CHANNEL_SECRET
   npx wrangler secret put RELAY_SIGNING_SECRET
   ```

3. 確認 LINE Messaging API 頻道的 Webhook URL 可供本中繼使用，再填入 Wrangler 顯示的 Worker HTTPS URL 並執行 LINE 的 **Verify**。若該頻道已有預約 webhook，請先確認切換後的流量安排。每個頻道設定一個 Webhook URL。[LINE Developers 設定說明](https://developers.line.biz/en/tips/2026/07/23/using-multiple-api-tools/)

接收端驗簽契約見 [LINE 工程訊息中繼整合說明](../../docs/line-engineering-relay.md)。
