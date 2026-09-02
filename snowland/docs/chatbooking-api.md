# SnowLand AI 客服排課 API

這一層是 SnowLand 自己的渠道無關後端，不依賴 FFSystem，也不要求客人回到原本預約網頁。LINE、網站聊天或測試程式都應呼叫同一套客服工具 API。

目前已完成：

- 滑雪與攝影共用的對話 session、欄位狀態與訊息資料表
- 依既有後台資料查詢課程大類、雪場、課型、方案、日期、時段、教練及裝備協助時段
- 直接共用既有權威價格、加購、折扣與排課/建單程式
- 報價快照與 15 分鐘效期
- `state_version` 防止兩個訊息同時覆蓋狀態
- `Idempotency-Key` 防止 webhook 重送造成重複訂單
- session token 與租戶雙重歸屬驗證
- 建立對話的基本速率限制
- 訂單建立後，在聊天中取得銀行資料並提交匯款帳號後五碼
- 真人客服轉接狀態與 AI 停止回覆旗標
- LINE event 去重與工具呼叫稽核所需的資料模型
- 對話過期與資料保存期限清理指令
- OpenAI Responses API 文字理解、回覆與嚴格 function tools
- 價格、選項、知識庫、報價、建單、付款與轉真人工具白名單
- OpenAI `store=false`，對話上下文由 SnowLand 本機訊息紀錄提供
- AI turn 鎖定、工具稽核與訊息／建單冪等處理
- 防止 AI 代替客人同意政策、未看報價即建單、或虛構匯款後五碼
- LINE raw body 簽章驗證、文字 webhook、reply API 與事件去重
- 以 LINE user ID 延續 30 天對話，重送失敗可安全重試
- LINE 群組／聊天室訊息不進入排課流程，避免暴露聯絡與訂單資料
- LINE reply token 不寫入資料庫或 application log

尚未接入：

- LINE 背景工作佇列與 push message（目前 webhook 內同步完成 AI 回覆）
- 信用卡 gateway adapter
- 真人客服工作台通知與接手畫面

## API 路徑

所有 API 均位於：

```text
/booking/{client_code}/api/chat/
```

### 1. 建立對話

```http
POST /booking/snowland/api/chat/sessions/
Content-Type: application/json

{"service_type":"ski"}
```

回傳 `session_token` 只出現一次。後續請求使用：

```http
X-Chat-Session-Token: {session_token}
```

token 不可放在 URL、聊天內容或一般 application log。

### 2. 查詢狀態

```http
GET /booking/snowland/api/chat/sessions/{session_id}/
X-Chat-Session-Token: ...
```

### 3. 更新已理解的欄位

LLM adapter 將使用者文字解析成結構化欄位後，呼叫：

```http
PATCH /booking/snowland/api/chat/sessions/{session_id}/state/
X-Chat-Session-Token: ...
Content-Type: application/json

{
  "state_version": 1,
  "updates": {
    "category_id": 1,
    "resort": "Tomamu"
  }
}
```

改動前置答案會自動移除不再可信的後續答案。例如改雪場會清除課型、方案、日期、時段和教練，但保留聯絡資料。

主要欄位：

```text
service_type: ski | photo
category_id
resort
course_type_id
people_count
has_under_6
under_7_can_self_ski
ability_level_counts
coach_id: integer | any
language: zh | en | ja | yue
template_id
course_dates: [YYYY-MM-DD]
session_id
equipment_option
equipment_assistance_time_slot_id
contact_name
contact_email
contact_phone
referral_source
discount_code
policy_accepted
```

攝影流程會自動採用一人、初學、系統安排及不加購滑雪裝備協助，不要求滑雪專用答案。

### 4. 查詢目前可選項

```http
GET /booking/snowland/api/chat/sessions/{session_id}/options/?field=course_type_id
X-Chat-Session-Token: ...
```

支援的 `field`：

```text
service_type
category_id
resort
course_type_id
people_count
ability_level
language
equipment_option
template_id
course_dates
session_id
coach_id
equipment_assistance_time_slot_id
```

日期另可傳 `month=YYYY-MM`。日期、時段與教練選項會依對話中已選資料篩選。

### 5. 傳送訊息並取得 AI 回覆

```http
POST /booking/snowland/api/chat/sessions/{session_id}/messages/
X-Chat-Session-Token: ...
Content-Type: application/json

{
  "content": "我想明年一月去 Tomamu 上雙板課",
  "external_message_id": "LINE-webhook-event-or-message-id"
}
```

同一 `external_message_id` 重送不會建立第二筆訊息或重跑已完成的 AI turn。API 會同步呼叫 OpenAI；模型只能使用後端白名單工具，回覆與更新後的 session 一起回傳：

```json
{
  "message_id": 12,
  "created": true,
  "ai_status": "completed",
  "reply": {
    "message_id": 13,
    "content": "請問想預約滑雪課程，還是滑雪攝影？"
  },
  "session": {}
}
```

未設定 `OPENAI_API_KEY` 時訊息仍會保存，但 API 回傳 `503` 與 `openai_not_configured`，不會產生假的客服回覆。

### 6. 取得報價

```http
POST /booking/snowland/api/chat/sessions/{session_id}/quote/
X-Chat-Session-Token: ...
```

報價由後端現有價格與折扣規則重新計算，回傳 `quote_hash`、金額與效期。AI 不可自行計價。

### 7. 確認建單與排課

```http
POST /booking/snowland/api/chat/sessions/{session_id}/confirm/
X-Chat-Session-Token: ...
Idempotency-Key: {stable-key-for-this-user-confirmation}
Content-Type: application/json

{
  "confirmed": true,
  "state_version": 12,
  "quote_hash": "..."
}
```

同一 idempotency key 重送只會回傳第一次成功結果。建單時會共用目前網頁的價格、折扣、訂單與排課程式。

### 8. 付款資料與銀行匯款

```http
GET /booking/snowland/api/chat/sessions/{session_id}/payment/
X-Chat-Session-Token: ...
```

只會回傳該 session 實際建立且屬於同租戶的訂單，不接受外部傳入任意訂單 ID。

```http
POST /booking/snowland/api/chat/sessions/{session_id}/payment/
X-Chat-Session-Token: ...
Content-Type: application/json

{
  "payment_type": "bank_transfer",
  "sender_account": "12345"
}
```

信用卡不能在 LINE 文字中收集卡號。後續 gateway adapter 應回傳付款公司的安全連結；這是唯一合理離開聊天視窗的付款步驟。

### 9. 要求真人客服

```http
POST /booking/snowland/api/chat/sessions/{session_id}/handoff/
X-Chat-Session-Token: ...
Content-Type: application/json

{"reason":"客人要求真人協助"}
```

呼叫後 `ai_enabled=false`，避免 AI 與真人同時回覆。後續可再將此狀態接到 SnowLand 自己的後台工作台。

### 10. LINE webhook

```http
POST /booking/{client_code}/api/chat/line/webhook/
X-Line-Signature: ...
Content-Type: application/json
```

這個端點直接接收 LINE Messaging API webhook，不供前端或人工呼叫。處理順序固定為：

1. 先用未修改的 raw request body 驗證 `X-Line-Signature`。
2. 用 `webhookEventId` 建立事件稽核與去重鎖。
3. 僅接受一對一的 LINE 文字訊息。
4. 以 LINE user ID 找到或建立 SnowLand 對話。
5. 保存客人訊息，交給既有 OpenAI 客服與後端白名單工具。
6. 用本次 `replyToken` 回覆 LINE，完成後才將事件標為已處理。

LINE 的 Verify 請求會送出空的 `events`，簽章正確時此端點回傳 `200`。

## LINE 上線設定

不是只有一個 token。最少需要：

- LINE Messaging API Channel Secret：驗證 webhook 簽章
- LINE Channel Access Token：呼叫 reply API
- LINE Developers 設定的公開 HTTPS webhook URL
- 對應的 SnowLand `client_code`

Channel ID、LINE 官方帳號的 bot user ID 不需放進目前環境變數。

AI 還需要一個模型來源：

- `OPENAI_API_KEY`
- `OPENAI_MODEL`（預設 `gpt-5.6-terra`）

這些都應以環境變數或秘密管理服務提供，不寫進程式碼或資料庫明文欄位。

SnowLand 目前從 `snowland/.env` 載入設定，可複製 `snowland/.env.example`。曾貼在聊天、issue 或原始碼中的 key 必須先撤銷再建立新的 key。

正式環境設定：

```dotenv
LINE_CHANNEL_SECRET=
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CLIENT_CODE=snowland
LINE_API_TIMEOUT_SECONDS=10
LINE_ACKNOWLEDGEMENT_TEXT="已收到您的訊息 ✅\nAI 客服正在查詢課程與排課資料，通常需要數秒至約 1 分鐘，請稍候，不必重複傳送。"
LINE_LOADING_SECONDS=60
LINE_SESSION_TTL_DAYS=30
LINE_WEBHOOK_MAX_BODY_BYTES=1048576
```

`LINE_CLIENT_CODE` 必須等於資料庫中啟用的 `Client.internal_code`。一組 LINE Channel 固定綁一個 client，避免未來多租戶時寫錯訂單。

部署後，LINE Developers 的 Webhook URL 應改成 SnowLand 自己的公開 HTTPS 網域：

```text
https://<snowland-public-domain>/booking/<client_code>/api/chat/line/webhook/
```

目前開發測試使用：

```text
https://ffreact.ngrok.io/booking/snowland/api/chat/line/webhook/
```

不要沿用 FFSystem／FlashFalcon 的舊 callback URL。設定後依序：

1. 執行 Django migration。
2. 在 LINE Developers 貼上新 URL，開啟 `Use webhook`。
3. 按 `Verify`，確認回傳成功。
4. 開啟 webhook redelivery。
5. 關閉 LINE Official Account Manager 的自動回覆與會重複出現的歡迎訊息。
6. 加官方帳號為好友，從 LINE 傳一則「我要預約滑雪課程」做端到端測試。

目前 AI 是在 webhook request 內同步執行。低流量 MVP 可以先測，但正式大量使用前應改成工作佇列：webhook 先驗證、保存並快速回 `200`，worker 完成 AI 後再用 LINE push message 回覆。否則模型或後端工具較慢時，LINE 可能重送 webhook。事件與 AI turn 去重已先完成，因此後續改佇列不需重寫排課核心。

## OpenAI 工具白名單

AI 可使用的工具只有：

```text
get_booking_state
update_booking_details
list_booking_options
search_customer_knowledge
create_booking_quote
confirm_booking
get_payment_info
submit_bank_transfer
request_human_support
```

所有選項與價格仍由 SnowLand 既有後端計算。`confirm_booking` 除了模型判斷外，後端還會驗證客人已看過更早一輪的有效報價，且本次原文包含明確下單語句。政策同意與匯款後五碼也會比對客人原始訊息，不接受模型自行生成的值。

## LINE adapter 實作

目前 adapter 執行：

1. 驗證 raw request body 的 LINE 簽章。
2. 以 webhook event ID 寫入 `ChatBookingEvent`，重送時直接略過。
3. 以 LINE user ID 找或建立 `channel=line` 的 session。
4. 保存 inbound message。
5. 交給 LLM 產生結構化 updates 或受控工具呼叫。
6. 呼叫本文件的 options、quote、confirm、payment、handoff 服務。
7. 立即使用 reply token 回覆可設定的「已收到、處理中」訊息。
8. 保存 AI outbound message，再以具備固定 retry key 的 push message 傳送正式答案。

收到一對一文字訊息後，adapter 會先呼叫 LINE loading API 顯示最長 60 秒的原生載入動畫，AI 回覆送達時動畫會自動消失。這項功能失敗時不會中斷排課或 LINE 回覆。

LINE Official Account Manager 的內建自動回覆必須關閉，否則客人仍會同時收到 Manager 預設文字與 SnowLand 的即時確認訊息。

課程探索不需要固定指令或前綴詞。「課程介紹」、「有哪些課程」、「推薦課程」、「方案差異」等自然語句會直接查詢 SnowLand 正式課程目錄；目錄包含已啟用且已綁定雪場的分類、課程類型與方案，不會改用 FAQ 文章搜尋代替。

LLM 的工具白名單不應包含任意 SQL、任意訂單 ID 查詢或直接修改價格。建單、付款與取消等重要動作仍需明確確認及 idempotency key。

## 資料保存清理

建議每天排程執行：

```text
python manage.py cleanup_chatbooking --retention-days 180
```

它會先將超過 session 效期的對話標為 expired，再刪除超過保存期限的 expired、cancelled、completed 對話及其訊息、草稿與稽核資料。正式啟用前應依隱私政策確認保存天數。
