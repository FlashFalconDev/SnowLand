# LINE 工程訊息中繼整合說明

LINE 群組中含「工程」的文字會觸發一筆 Cursor Automation POST。Worker 驗證 LINE 簽章後立即回 HTTP 200，儲存與轉發在背景執行。

## 儲存與設定

- KV 綁定 `CHAT_HISTORY` 以群組和台北日期索引文字與附件資訊，記錄寫入後保留 48 小時（172800 秒）。文字及其中的網址會原樣保存。
- 新寫入使用 `msgr:<清理後群組 ID>:<台北日期>:<15 位反向時間>:<清理後訊息 ID>`。反向時間是 `999999999999999 - Unix 毫秒時間戳`，左側補零到 15 位。KV 依字典序列舉，同一群組和台北日期會先讀到最新時間。
- 過渡期併讀同群組、同日的舊 `msg:`。同一 `messageId` 優先採用新 key，當前 POST 的記憶體資料優先於 KV。所有舊版寫入者停止寫入 `msg:` 後滿 48 小時，且沒有回滾至舊寫入方式，才可移除相容讀取。
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

每次轉發保留觸發訊息（`isTrigger: true`），並從併讀後的唯一訊息選取時間最新的至多 50 則非觸發項目。可在 Worker 環境變數（例如 Wrangler 的 `[vars]`）設定 `RELAY_HISTORY_LIMIT = "75"`。接受正安全整數，無效時採預設。兩種 key 各最多掃 20 頁、每頁最多 100 個 key。新 key 讀滿上限即停止列舉，舊 key 依舊到新掃描，保留已成功取得的資料。

`contextCount` 為實際送出的項目數。`truncated: true` 時附上 `truncatedReasons` 陣列，多個原因可並存，順序如下。`truncated: false` 時省略該欄位。

1. `read_interrupted` 表示任一 prefix 的 KV 讀取發生例外、分頁中斷或達 20 頁後仍有下一頁。
2. `history_limit` 表示非觸發項目達筆數上限，剛好達上限時也回傳。
3. `payload_limit` 表示 UTF-8 JSON 超過傳送上限。預設 512 KiB，可用 `RELAY_MAX_PAYLOAD_BYTES` 覆寫。Worker 從最舊的非觸發項目開始整則移除，保留項目的中文與 emoji 原文完整。必要欄位與觸發項目仍超限時，Worker 跳過轉發。

媒體 `status` 可為 `stored`、`skipped_missing_token`、`skipped_no_bucket`、`skipped_too_large`、`download_failed` 或 `storage_failed`。大小或內容類型尚未知時以 `null` 表示。

## 驗簽與私有下載

接收端從 `X-Relay-Signature` 的 `t=<Unix 秒>,v1=<小寫十六進位>` 取出時間與摘要。以 `RELAY_SIGNING_SECRET` 對 `t`、一個句點與原始 HTTP body 位元組的串接值計算 HMAC-SHA256，再用固定時間比較核對 `v1`。

下載網址的格式為 `GET /media/<編碼後的物件鍵>?exp=<Unix 秒>&sig=<簽章>`。簽章涵蓋 `media`、解碼後的物件鍵與 `exp`，三者以換行字元相隔。Worker 驗證簽章與有效期後從私有 R2 回傳附件，回應設有 `Cache-Control: private, no-store`。網址有效時間由 `MEDIA_URL_TTL_SECONDS` 設定，預設 3600 秒。接收端可在有效期內直接下載。
