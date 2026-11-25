# LINE 工程訊息中繼整合說明

SnowLand 的 LINE 工程訊息中繼將群組裡包含「工程」的文字訊息送到 Cursor Automation。Worker 在 LINE 驗簽成功後即回 HTTP 200，轉發結果與這個回應分開處理。

每筆 POST 的 JSON 欄位為 `source`（固定為 `line`）、`groupId`、`userId`、`text`、`timestamp`（UTC ISO 8601）、`timestampMs`（LINE 原始毫秒時間）、`messageId`、`webhookEventId`。LINE 未提供 `userId` 時該值為 `null`。

接收端從 `X-Relay-Signature` 的 `t=<Unix 秒>,v1=<小寫十六進位>` 取出時間與摘要。以 `RELAY_SIGNING_SECRET` 對 `t`、一個句點與原始 HTTP body 位元組的串接值計算 HMAC-SHA256，再用固定時間比較核對 `v1`。

測試、部署與密鑰設定見 [Worker README](../tools/line-engineering-relay/README.md)。
