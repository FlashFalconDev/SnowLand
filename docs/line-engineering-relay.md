# LINE 工程訊息中繼整合說明

LINE 群組中含「工程」的文字會觸發一筆 Cursor Automation POST。Worker 驗證 LINE 簽章後立即回 HTTP 200，儲存與轉發在背景執行。

## 儲存與設定

- KV 綁定 `CHAT_HISTORY` 以群組和台北日期索引文字與附件資訊，記錄寫入後保留 48 小時。文字及其中的網址會原樣保存。
- `wrangler.toml` 將私有 R2 bucket `snowland-line-relay-media` 綁定為 `MEDIA_BUCKET`。部署前確認整個 bucket 的物件自建立起 2 天到期，並維持 `r2.dev` 與自訂公開網域停用。單檔大小由 `MEDIA_MAX_BYTES` 設定，預設 52428800 位元組（50 MiB）。
- `LINE_CHANNEL_SECRET` 驗證 LINE webhook，`RELAY_SIGNING_SECRET` 簽署轉發內容與下載網址。啟用媒體暫存時，另以 `LINE_CHANNEL_ACCESS_TOKEN` 下載 LINE 媒體。LINE secrets 由小陌本人在互動提示中輸入。 [Worker 設定與測試步驟](../tools/line-engineering-relay/README.md)

## 轉發格式

頂層沿用 `source`（固定為 `line`）、`groupId`、`userId`、`text`、`timestamp`（UTC ISO 8601）、`timestampMs`（LINE 原始毫秒時間）、`messageId` 和 `webhookEventId`。LINE 未提供 `userId` 時，該欄位為 `null`。

新增 `taipeiDate`（例如 `2026-11-25`）、`contextStart`（例如 `2026-11-25T00:00:00+08:00`）、`truncated`、`contextCount` 與 `context`。日期以觸發訊息的時間計算。同批、同群組同日的訊息會與 KV 讀取結果合併，依 `messageId` 去重，再依 `timestampMs` 及 `messageId` 升冪排列。

| 項目 | 欄位 |
| --- | --- |
| 共用 | `messageId`、`webhookEventId`、`userId`、`timestamp`、`timestampMs`、`type`、`isTrigger` |
| 文字 | `text` 原文，含其中的連結 |
| 附件 | 若有檔名則提供 `fileName`。 `media` 提供 `type`、`contentType`、`size`（位元組）、`duration`（沿用 LINE 毫秒值）及 `status`。成功儲存且 `MEDIA_BUCKET` 仍綁定時，項目另帶 `downloadUrl`。 |

觸發訊息的 `isTrigger` 為 `true`。`contextCount` 為實際送出的項目數。KV 歷史最多讀取 20 頁、每頁 100 筆，讀取受限或失敗時標記 `truncated: true`。轉發 JSON 以 UTF-8 計算，預設上限 512 KiB。超過時依序移除最舊的非觸發項目並標記 `truncated: true`。若光是必要欄位與觸發項目便超出上限，Worker 跳過這次轉發。

媒體 `status` 可為 `stored`、`skipped_missing_token`、`skipped_no_bucket`、`skipped_too_large`、`download_failed` 或 `storage_failed`。大小或內容類型尚未知時以 `null` 表示。

## 驗簽與私有下載

接收端從 `X-Relay-Signature` 的 `t=<Unix 秒>,v1=<小寫十六進位>` 取出時間與摘要。以 `RELAY_SIGNING_SECRET` 對 `t`、一個句點與原始 HTTP body 位元組的串接值計算 HMAC-SHA256，再用固定時間比較核對 `v1`。

下載網址的格式為 `GET /media/<編碼後的物件鍵>?exp=<Unix 秒>&sig=<簽章>`。簽章涵蓋 `media`、解碼後的物件鍵與 `exp`，三者以換行字元相隔。Worker 驗證簽章與有效期後從私有 R2 回傳附件，回應設有 `Cache-Control: private, no-store`。網址有效時間由 `MEDIA_URL_TTL_SECONDS` 設定，預設 3600 秒。接收端可在有效期內直接下載。
