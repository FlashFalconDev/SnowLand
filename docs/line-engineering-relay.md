# LINE 工程訊息中繼整合說明

LINE 群組中含「工程」的文字會觸發一筆 Cursor Automation POST。Worker 驗證 LINE 簽章後立即回 HTTP 200，儲存與轉發在背景執行。

## 儲存與設定

- KV 綁定 `CHAT_HISTORY` 以群組和台北日期索引文字與附件資訊，記錄寫入後保留 48 小時（172800 秒）。文字及其中的網址會原樣保存。
- 新寫入使用 `msgr:<清理後群組 ID>:<台北日期>:<15 位反向時間>:<清理後訊息 ID>`。反向時間是 `999999999999999 - Unix 毫秒時間戳`，左側補零到 15 位。KV 依字典序列舉，同一群組和台北日期會先讀到最新時間。
- 過渡期併讀同群組、同日的舊 `msg:`。同一 `messageId` 優先採用新 key，當前 POST 的記憶體資料優先於 KV。所有舊版寫入者停止寫入 `msg:` 後滿 48 小時，且沒有回滾至舊寫入方式，才可移除相容讀取。
- `wrangler.toml` 將私有 R2 bucket `snowland-line-relay-media` 綁定為 `MEDIA_BUCKET`。部署前確認整個 bucket 的物件自建立起 2 天到期，並維持 `r2.dev` 與自訂公開網域停用。單檔大小由 `MEDIA_MAX_BYTES` 設定，預設 52428800 位元組（50 MiB）。
- `LINE_CHANNEL_SECRET` 驗證 LINE webhook，`RELAY_SIGNING_SECRET` 簽署轉發內容與下載網址。啟用媒體暫存時，另以 `LINE_CHANNEL_ACCESS_TOKEN` 下載 LINE 媒體。LINE secrets 由小陌本人在互動提示中輸入。 [Worker 設定與測試步驟](../tools/line-engineering-relay/README.md)

## 轉發格式

JSON 頂層依以下順序序列化。接收端若只能取得 body 前綴，會先讀到觸發文字及最新對話。可取得的完整項目仍取決於接收端保留的位元組數。

1. `summary` 是一行摘要，列出 `recent` 和 `context` 中較舊訊息的實際筆數。有截斷原因時一併列出。
2. 觸發欄位 `source`（固定為 `line`）、`text`（完整原文）、`timestamp`（UTC ISO 8601）、`timestampMs`（LINE 原始毫秒時間）、`messageId`、`webhookEventId`、`userId` 及選填 `senderName`。LINE 未提供 `userId` 時，該欄位為 `null`。
3. `recent` 依時間由新到舊，最多 10 則。只選 `timestampMs` 早於觸發的同群組同日訊息。同毫秒的觸發與歷史訊息無法從時間判定先後，因此不納入。`recentCount` 緊接其後，為實際筆數。
4. `truncated`、選填 `truncatedReasons`、`contextCount`、`groupId`、`taipeiDate`、`contextStart`。後兩個日期欄位由觸發訊息決定，例如 `2026-11-25` 和 `2026-11-25T00:00:00+08:00`。
5. `context` 是最後一個欄位。第一則是觸發訊息（`isTrigger: true`，原文完整），之後只有未列入 `recent` 的較舊訊息，依時間由新到舊。其他項目的 `isTrigger` 都是 `false`。

舊版的 `context` 把所有訊息由舊到新排列，接收端截取 JSON 前綴時，晚間訊息可能落在被截掉的尾端。新版把最新訊息提早放進 `recent`，把剩餘項目放在 `context` 尾端，讓較舊訊息優先被截掉。接收端若要重建完整對話，讀取 `context[0]`、`recent`、`context.slice(1)`。`contextCount` 仍是這次送出的訊息總數，等於 `recentCount + context.length`，觸發訊息只計一次。

| 項目 | 欄位 |
| --- | --- |
| 共用 | `messageId`、`webhookEventId`、`userId`、`timestamp`、`timestampMs`、新增的 `taipeiTime`（Asia/Taipei，`YYYY-MM-DD HH:mm:ss`）、`type`、`isTrigger` |
| 文字 | `text` 保留原文前綴。`recent` 單則安全上限 2000 Unicode code points，較舊 `context` 單則上限 200。切點往前移到完整字素叢集邊界，保留完整的 emoji 和 ZWJ 序列。實際縮短時加 `textTruncated: true`。`recent` 的附件項目以 `text: null` 表示無文字。 |
| 顯示名稱 | `senderName` 為選填，僅用於 `recent`、觸發頂層及 `context[0]`。 |
| 附件 | 若有檔名則提供 `fileName`。`media` 提供 `type`、`contentType`、`size`（位元組）、`duration`（沿用 LINE 毫秒值）及 `status`。成功儲存且 `MEDIA_BUCKET` 仍綁定時，保留完整 `downloadUrl`。取不到 bucket 時省略連結，附件為 `skipped_no_bucket`（另依現有流程標示缺少 LINE 存取憑證的情形）。 |

同批、同群組同日的訊息與 KV 讀取結果依 `messageId` 去重。Worker 使用既有 `readHistory()`，預設最多保留 50 則非觸發項目。可設定正安全整數 `RELAY_HISTORY_LIMIT`，無效時採預設。兩種 key 各最多掃 20 頁、每頁最多 100 個 key。新 key 讀滿上限即停止列舉。舊 key 依舊到新掃描，保留已成功取得的資料。

`truncated: true` 時附上 `truncatedReasons`。多個原因可依序並存。未達以下條件時，`truncated` 為 `false`，省略 `truncatedReasons`。單則文字縮短由 `textTruncated` 表示。

1. `read_interrupted` 表示任一歷史 prefix 的 KV 讀取發生例外、分頁中斷或達 20 頁後仍有下一頁。
2. `history_limit` 表示非觸發候選項目達歷史筆數上限，剛好達上限時也回傳。
3. `payload_limit` 表示序列化後的 UTF-8 JSON 超過傳送預算。預設 24 KiB（24576 bytes），可用正安全整數 `RELAY_MAX_PAYLOAD_BYTES` 覆寫，無效值回預設，大於 512 KiB 的值以 512 KiB 計。Worker 從 `context` 尾端整則淘汰最舊項目，更新 `summary` 和 `contextCount`。剩下的觸發與完整 `recent` 若仍超過預算，在 512 KiB 內照送並記一則固定警告。若精簡後仍超過 512 KiB（524288 bytes）硬上限，記固定警告並跳過該筆轉發。

媒體 `status` 可為 `stored`、`skipped_missing_token`、`skipped_no_bucket`、`skipped_too_large`、`download_failed` 或 `storage_failed`。大小或內容類型尚未知時以 `null` 表示。

### 顯示名稱快取

每筆轉發針對 `recent` 和觸發訊息的使用者去重，最多 11 人並行查詢。先讀同群組、同使用者在 `CHAT_HISTORY` 的 `profile:<清理後群組 ID>:<清理後使用者 ID>`。快取未命中時，使用 Worker 已配置的 LINE 存取憑證呼叫唯讀的群組成員個人檔案 GET。只取 `displayName`，成功時以文字寫回快取，TTL 為 86400 秒（24 小時）。[LINE 群組成員個人檔案 API](https://developers.line.biz/en/reference/messaging-api/#get-group-member-profile)

單筆查詢連同快取讀寫共用約 2 秒的期限。LINE 或 KV 失敗、逾時、缺少憑證或查無名稱時，省略對應的 `senderName` 並繼續轉發。

## 驗簽與私有下載

接收端從 `X-Relay-Signature` 的 `t=<Unix 秒>,v1=<小寫十六進位>` 取出時間與摘要。以 `RELAY_SIGNING_SECRET` 對 `t`、一個句點與原始 HTTP body 位元組的串接值計算 HMAC-SHA256，再用固定時間比較核對 `v1`。

下載網址的格式為 `GET /media/<編碼後的物件鍵>?exp=<Unix 秒>&sig=<簽章>`。簽章涵蓋 `media`、解碼後的物件鍵與 `exp`，三者以換行字元相隔。Worker 驗證簽章與有效期後從私有 R2 回傳附件，回應設有 `Cache-Control: private, no-store`。網址有效時間由 `MEDIA_URL_TTL_SECONDS` 設定，預設 3600 秒。接收端可在有效期內直接下載。
