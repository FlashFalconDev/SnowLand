# SnowLand LINE 工程訊息中繼

Cloudflare Worker 接收 LINE 群組訊息。含「工程」的文字會觸發一筆 Cursor Automation POST，附上該群組自台北當日午夜起的對話與附件資訊。

## 運作方式

- LINE webhook 使用 POST。Worker 在 1 MiB 上限內以原始位元組驗證 `X-Line-Signature`，驗簽成功即回 HTTP 200。儲存與轉發透過 `ctx.waitUntil` 在背景執行。
- KV 綁定 `CHAT_HISTORY` 保存群組文字與附件資訊。文字保留原文和連結，每筆記錄的 TTL 為 172800 秒（48 小時）。
- 預設部署省略 R2 綁定，圖片、影片和檔案只在 KV 記錄附件資訊。未綁定時標記 `skipped_no_bucket`，缺少 LINE access token 時則標記 `skipped_missing_token`。啟用 `MEDIA_BUCKET` 並設定 token 後，Worker 才會透過 LINE Content API 下載並存入私有 R2，預設單檔上限為 50 MiB。
- 只有含「工程」的群組文字會觸發轉發。附件在 `context` 中提供 metadata，成功存入且 R2 仍綁定的附件另附短效 `downloadUrl`，預設有效一小時。Worker 的 `GET /media/...` 會驗證簽章與到期時間，再從私有 R2 讀取檔案。
- 日誌只記固定訊息與 HTTP 狀態碼。轉發內容與接收端驗簽契約見 [LINE 工程訊息中繼整合說明](../../docs/line-engineering-relay.md)。

## 在本機執行離線測試

使用 Node.js 22 以上版本，在 `tools/line-engineering-relay/` 執行。測試以記憶體模擬 KV、R2 與 HTTP 呼叫。

```powershell
npm test
```

## Cloudflare 設定與部署

1. 確認 `wrangler.toml` 的 `CHAT_HISTORY` 指向已建立的 KV namespace。48 小時 TTL 由 Worker 寫入每筆記錄時設定。
2. 在 Worker 所在目錄於部署階段使用互動提示設定 Worker secrets。**`LINE_CHANNEL_SECRET` 由小陌本人輸入。** `RELAY_SIGNING_SECRET` 須與接收端用於驗簽的密鑰相同。密鑰只透過互動提示輸入。

   ```powershell
   npx wrangler secret put LINE_CHANNEL_SECRET
   npx wrangler secret put RELAY_SIGNING_SECRET
   ```

3. 在部署階段以 `npx wrangler deploy` 部署 Worker。在 LINE Developers 將 Wrangler 顯示的 Worker HTTPS URL 填為 Webhook URL，並執行 **Verify**。每個 LINE 頻道使用一個 Webhook URL。若該頻道已有預約 webhook，先確認切換後的流量安排。

日後要儲存媒體檔時，在 Cloudflare Dashboard 啟用 R2 並建立 `snowland-line-relay-media` bucket。保持私有，關閉 `r2.dev` 與公開網域，為 `line-media/` 前綴設定物件建立後 2 天（48 小時）到期。取消 `wrangler.toml` 內 `[[r2_buckets]]` 綁定片段的註解，由小陌本人透過 `npx wrangler secret put LINE_CHANNEL_ACCESS_TOKEN` 的互動提示設定 token，再重新部署。
