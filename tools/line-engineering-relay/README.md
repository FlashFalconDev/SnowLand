# SnowLand LINE 工程訊息中繼

Cloudflare Worker 接收 LINE 群組訊息。含「工程」的文字會觸發一筆 Cursor Automation POST，附上該群組自台北當日午夜起、最近最多 50 則對話與附件資訊及觸發訊息。

## 運作方式

- LINE webhook 使用 POST。Worker 在 1 MiB 上限內以原始位元組驗證 `X-Line-Signature`，驗簽成功即回 HTTP 200。儲存與轉發透過 `ctx.waitUntil` 在背景執行。
- KV 綁定 `CHAT_HISTORY` 保存群組文字與附件資訊。文字保留原文和連結，每筆記錄的 TTL 為 172800 秒（48 小時）。
- `wrangler.toml` 將私有 R2 bucket `snowland-line-relay-media` 綁定為 `MEDIA_BUCKET`。Worker 使用 `LINE_CHANNEL_ACCESS_TOKEN` 透過 LINE Content API 下載圖片、影片和檔案，預設單檔上限為 50 MiB。缺少 bucket 綁定或 token 時，KV 分別以 `skipped_no_bucket` 或 `skipped_missing_token` 記錄附件資訊。
- 只有含「工程」的群組文字會觸發轉發。附件在 `recent` 或 `context` 中提供 metadata，成功存入且 R2 仍綁定的附件另附短效 `downloadUrl`，預設有效一小時。Worker 的 `GET /media/...` 會驗證簽章與到期時間，再從私有 R2 讀取檔案。
- 日誌只記固定訊息與 HTTP 狀態碼。轉發內容與接收端驗簽契約見 [LINE 工程訊息中繼整合說明](../../docs/line-engineering-relay.md)。

## 轉發 payload

序列化 JSON 依序放 `summary`、觸發欄位、`recent` 與 `recentCount`、截斷與群組資訊，最後才放 `context`。

- `recent` 是觸發前最近 10 則，從最新開始。文字最多 2000 Unicode code points。`context` 第一則是完整觸發，後面才放較舊的訊息，文字最多 200 code points。實際縮短時標記 `textTruncated`，保留完整 emoji 和 ZWJ 序列。項目新增 `taipeiTime`。
- `contextCount` 是觸發、`recent` 和較舊 `context` 的總筆數。`truncated` 和 `truncatedReasons` 說明歷史讀取、歷史筆數或 payload 預算造成的截斷。
- UTF-8 預算預設 24 KiB。`RELAY_MAX_PAYLOAD_BYTES` 可覆寫，非法值回預設，最大 512 KiB。超預算時從 `context` 尾端整則移除最舊訊息。觸發加上 `recent` 仍超預算時會照送並記一則固定警告，超過 512 KiB 硬上限才跳過轉發。
- 觸發和 `recent` 的選填 `senderName` 來自 LINE 群組成員個人檔案唯讀 GET。依群組與使用者在 `CHAT_HISTORY` 快取 24 小時，只存顯示名稱。同一筆轉發的查詢去重並行，各自以約 2 秒為限。失敗時省略名稱。

舊版把由舊到新排列的全部訊息放在 `context`。新版把最新訊息移到 body 前段，讓接收端截取 JSON 前綴時優先保留觸發和最近對話。 [完整欄位與接收端契約](../../docs/line-engineering-relay.md)

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

3. 確認 Cloudflare 已建立私有 R2 bucket `snowland-line-relay-media`，且 `expire-after-2-days` 規則適用整個 bucket。物件自建立起 2 天（48 小時）到期。維持 `r2.dev` 與公開網域停用。
4. 以 `npx wrangler secret list` 確認媒體下載所需的 secret 名稱已存在，並依下方指令部署。首次設定時，在 LINE Developers 填入 Worker Webhook URL 並執行 **Verify**。若該頻道已有預約 webhook，先確認切換後的流量安排。

### 部署後檢查指令

由調度端在核准部署的 worktree 內進入 `tools\line-engineering-relay`，使用 PowerShell 5.1 和已安裝的 Wrangler。先核對設定名稱與綁定，再部署並比對版本 ID。

```powershell
Select-String -LiteralPath .\wrangler.toml -Pattern '^\s*(name|binding|bucket_name|id)\s*=' |
  ForEach-Object { $_.Line.Trim() }
# Worker 為 snowland-line-engineering-relay。
# CHAT_HISTORY 的 namespace ID 為 4936dd68803c482099b9f76e09057be0。
# MEDIA_BUCKET 的 bucket 為 snowland-line-relay-media。

$expectedAccount = Read-Host '輸入預期的 Cloudflare 帳戶 ID'
function Confirm-RelayWranglerAccount {
  $relayIdentity = npx.cmd --no-install wrangler whoami 2>$null
  if ($LASTEXITCODE -ne 0) { throw '無法查核 Wrangler 身分' }
  if ($expectedAccount -notmatch '^[0-9a-f]{32}$' -or ($relayIdentity -join "`n") -notmatch "\b$expectedAccount\b") {
    throw 'Wrangler 身分輸出未確認到預期帳戶'
  }
}
Confirm-RelayWranglerAccount
$relayDeploy = npx.cmd --no-install wrangler deploy --config wrangler.toml 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Worker 部署失敗' }
$relayPublishedVersion = $relayDeploy | Select-String -Pattern 'Current Version ID:\s*([0-9a-f-]{36})' |
  ForEach-Object { $_.Matches[0].Groups[1].Value }
Confirm-RelayWranglerAccount
$relayDeployments = npx.cmd --no-install wrangler deployments list --config wrangler.toml --json 2>$null
if ($LASTEXITCODE -ne 0) { throw '無法列出 Worker 部署' }
try { $relayVersions = ($relayDeployments -join "`n") | ConvertFrom-Json -ErrorAction Stop }
catch { throw '無法解析 Worker 部署清單' }
$relayLatestVersions = $relayVersions | Sort-Object created_on -Descending | Select-Object -First 1 |
  ForEach-Object { $_.versions | Select-Object -ExpandProperty version_id }
if (-not $relayPublishedVersion -or $relayPublishedVersion -notin $relayLatestVersions) {
  throw '最新部署清單未確認到本次發布版本'
}
$relayLatestVersions
```

Worker 讀 `RELAY_WEBHOOK_URL` 做為轉發目的端。目前 `wrangler.toml` 以一般變數配置它。下方只比對 host 和接收端管理者提供的預期 host。若部署採用 secret，`wrangler secret list` 只回傳名稱等中繼資料，請以配置當時核對的 host 或 UTF-8 SHA-256 前 8 碼比對可信紀錄，並由接收端確認有收到已驗簽的請求。僅列出名稱時無法從 Worker 端確認目前 secret 的目的端值。

```powershell
$relaySecrets = npx.cmd --no-install wrangler secret list --config wrangler.toml --format json 2>$null
if ($LASTEXITCODE -ne 0) { throw '無法列出 Worker secret 名稱' }
try { $relayNames = ($relaySecrets -join "`n") | ConvertFrom-Json -ErrorAction Stop }
catch { throw '無法解析 Worker secret 名稱' }
$relayNames | Where-Object { $_.name -eq 'RELAY_WEBHOOK_URL' } | Select-Object -ExpandProperty name

$relayVar = Select-String -LiteralPath .\wrangler.toml -Pattern '^\s*RELAY_WEBHOOK_URL\s*=\s*"([^"]+)"' |
  Select-Object -First 1
if ($relayVar) {
  $relayUri = $null
  if (![uri]::TryCreate($relayVar.Matches[0].Groups[1].Value, [UriKind]::Absolute, [ref]$relayUri)) {
    throw '轉發目的端變數的 URL 格式無效'
  }
  $expectedHost = Read-Host '輸入接收端提供的預期 host'
  [pscustomobject]@{ HostMatches = $relayUri.Host -ieq $expectedHost }
}
```

群組正常收到新事件後，確認有 `msgr:` key。下方只輸出 key 名稱。

```powershell
$relayKeys = npx.cmd --no-install wrangler kv key list --namespace-id 4936dd68803c482099b9f76e09057be0 --prefix msgr: 2>$null
if ($LASTEXITCODE -ne 0) { throw '無法列出歷史 key' }
try { $relayKeyList = ($relayKeys -join "`n") | ConvertFrom-Json -ErrorAction Stop }
catch { throw '無法解析歷史 key 清單' }
$relayKeyList | Select-Object -ExpandProperty name
```

[Wrangler Worker 指令](https://developers.cloudflare.com/workers/wrangler/commands/workers/)、[身分查核](https://developers.cloudflare.com/workers/wrangler/commands/general/#whoami)、[KV 指令](https://developers.cloudflare.com/workers/wrangler/commands/kv/#kv-key-list)
