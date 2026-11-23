# SnowLand 資料夾發布

僅 `flashfalcon` 平台入口的最高管理員可使用。此發布器更新 SnowLand 的共用前端網站，與 console.flashfalcon.info 的發布目標、CRM 權限及其他 APP／POS 分開。

## 操作與完成判定

前端 build 後選擇 `dist` 資料夾本身，不需自行壓縮。瀏覽器送出相對路徑及檔案；伺服器驗證 SnowLand 的 application-name 標記、根目錄 index.html、路徑及大小，再儲存私有版本。已有發布進行中時回 409，不能同時寫同一網站。

發布工作會先從實際網站讀回舊檔案並保存備份，接著寫入新版資源，最後寫 index.html，等待 CloudFront invalidation 完成後整理舊檔並登記成功。依原有發布流程清除已不使用的舊檔，避免累積到超過下次備份／還原上限；使用者已開啟的舊頁面可能需要重新整理。Django 靜態檔 prefix、媒體及私有檔案 prefix 不會被發布器覆寫或清除。

還原會重新備份當前網站，實際回寫選定版本並清快取。寫入或清快取失敗會嘗試回復原網站，狀態維持失敗；不能只憑檔案已上傳、is_current 或排入工作，就稱為發布成功。

原有 ZIP 紀錄仍能下載。尚未執行過成功發布的舊 is_current 紀錄不會被當作已上線證據。人工保存的舊 ZIP 須含 SnowLand build 標記才允許發布；系統從實際網站產生的可信備份可還原舊版未含標記的網站。

## 正式啟用設定

這些設定須由部署管理者確認，不會從通用媒體 bucket 自動推測：

| 環境變數 | 內容 |
|---|---|
| SNOWLAND_FRONTEND_BUCKET | 專用網站 bucket；不得是私有媒體 bucket |
| SNOWLAND_FRONTEND_BUCKET_OWNER | 該 bucket 的 AWS 12位帳戶 ID |
| SNOWLAND_FRONTEND_PREFIX | 網站檔案 prefix；根目錄留空，須與 CloudFront OriginPath 一致 |
| SNOWLAND_FRONTEND_DISTRIBUTION_ID | 提供該網站的 CloudFront distribution |
| FRONTEND_URL | 網站 HTTPS origin，須出現在 distribution aliases |
| SNOWLAND_PRIVATE_MEDIA_BUCKET | 既有私有版本備份儲存；版本位於 private_frontend_releases/ |

發布前會核對 bucket owner、CloudFront owner、網站 alias、預設 origin bucket 及 OriginPath。缺設定或不一致時不寫網站。

EC2 instance role 需要網站 prefix 的 s3:ListBucket/GetObject/PutObject/DeleteObject，私有版本 prefix 的相應讀寫刪除權，以及指定 distribution 的 cloudfront:GetDistribution/CreateInvalidation/GetInvalidation。使用 instance role，不新增長期 access key，不傳 PutObjectAcl。

新增 Client.0016_frontend_deployment 僅建立工作紀錄表，依賴已發布的 Client.0015。沒有重置原有課程、會員、訂單或其他 Client。回復程式前需確認沒有仍執行中的發布；回退 migration 會移除工作紀錄，不能將刪除紀錄當成還原網站的方法。

資料夾上限 3,000 檔／1 GiB，單檔100 MiB；Django 的檔數與 EB nginx body limit 已同步調整。接收檔案後由原有 web process 的背景執行緒執行，工作及鎖定狀態放在共用資料庫，不需新增 port 或 worker 服務。

系統自動產生的安全備份另允許 6,000 檔／2 GiB，涵蓋一次新舊版本混合的失敗現場；只有能對應工作備份紀錄的可信備份能以此上限還原，外部上傳仍限3,000檔／1 GiB。暫時整理清單允許兩份安全備份的聯集。超過安全備份上限時不再覆寫，需維護人員先保全現場處理，不能連續重送不同建置而無限制累積。

伺服器在發布途中重啟可能留下未完成工作；頁面會持續顯示未完成／長時間未更新，不會誤報成功或自動放行第二次覆寫。維護人員須先確認舊工作已停止、檢查實際網站及備份，再處理工作狀態。不要直接清除 active 紀錄後重送。

## 用指令發布

Windows PowerShell 5.1 可用 `tools/publish-snowland-frontend.ps1`。請在 SnowLand repo 根目錄執行。`-ApiBase` 接受 HTTPS origin，本機測試也接受 `http://127.0.0.1` 或 `http://localhost` 加連接埠。腳本會拒絕轉址。

### 啟用、輪替與撤銷

1. 使用實際執行發布的 Windows 帳號執行 `.\tools\publish-snowland-frontend.ps1 -NewToken`。腳本將 256-bit token 存入 Windows Credential Manager 的 `SnowLandFrontendPublish`，並輸出部署所需的 SHA-256 摘要。
2. 在後端環境設定 `SNOWLAND_FRONTEND_CLI_TOKEN_SHA256`，使所有 web instances 載入設定。CLI 發布和查詢只接受有效 Bearer token，並要求 `flashfalcon` 平台 Client 啟用。來源 IP 無限制。自動化也可從秘密管理器注入 `SNOWLAND_FRONTEND_CLI_TOKEN` 到腳本所在的程序環境，該設定優先於 Credential Manager。
3. 輪替時用 `-NewToken -TokenTarget <新目標名>` 另建憑證。伺服器將現有摘要移到 `SNOWLAND_FRONTEND_CLI_TOKEN_PREVIOUS_SHA256`，再把新摘要放入 `SNOWLAND_FRONTEND_CLI_TOKEN_SHA256`。發布腳本改用 `-TokenTarget <新目標名>`。輪替期間兩個 token 共用同一個 CLI 身分，能查詢輪替前後的 CLI 工作。
4. 完成切換後移除 `SNOWLAND_FRONTEND_CLI_TOKEN_PREVIOUS_SHA256`，更新所有後端程序，再從 Credential Manager 刪除舊憑證。需要全面停用時移除 `SNOWLAND_FRONTEND_CLI_TOKEN_SHA256` 並更新所有後端程序。需要立即撤銷特定 token 時，將其摘要從兩個槽位移除。

### 建置與送件

```powershell
# 建置、打包及本機驗證
.\tools\publish-snowland-frontend.ps1 -ApiBase https://snowland.tw -DryRun

# 發布已建置的 dist
.\tools\publish-snowland-frontend.ps1 -ApiBase https://snowland.tw -SkipBuild

# 以已保存的 UUID 查詢，適用於上次回應遺失、逾時或換機後查詢
.\tools\publish-snowland-frontend.ps1 -ApiBase https://snowland.tw -RequestId <UUID>
```

預設執行 `npm ci` 與 `npm run build`。已有依賴可用 `-SkipInstall`，只需建置可用 `-BuildOnly`。同一 worktree 每次只能由一個發布腳本建置或封裝，封裝期間請保持 `dist` 內容穩定。`-DryRun` 會顯示 ZIP 檔數及 SHA-256，ZIP 和正式送件的 `request.json` 放在 `tmp/snowland-frontend-publish/<UUID>/`。送前會保存 UUID、API origin 和 ZIP 摘要。伺服器接受根目錄含 SnowLand `index.html` 的靜態 ZIP，壓縮上限 768 MiB，另限 3,000 個項目、解壓 1 GiB、單檔 100 MiB，`index.html` 上限 4 MiB。允許 HTML、JS、CSS、PNG、JPEG、WebP、SVG 和根目錄 `_redirects`。

`POST /api/admin/flashfalcon/frontend-releases/cli/publish/` 接收一個 `archive` multipart 檔案，使用 `Idempotency-Key` UUID。HTTP 202 代表已受理。相同 UUID 與 ZIP 摘要會回傳同一工作。`GET /api/admin/flashfalcon/frontend-releases/cli/jobs/<UUID>/` 查詢該工作，`succeeded` 才代表發布完成。腳本遇到失敗或逾時會以非零結束碼退出。

| 狀況 | 處理方式 |
|---|---|
| 409 `idempotency_conflict` | 該 UUID 已綁定另一份 ZIP。用 `-RequestId` 查原工作，核對 `request.json` 的摘要。 |
| 409 `publication_in_progress` | 網頁或 CLI 已有發布中。先在網頁支援頁或用原 UUID 查工作，待結束後再送新建置。 |
| POST 回應遺失或逾時 | 腳本會用原 UUID 先 GET。仍未確認時，用 `-RequestId` 繼續查詢。確認舊要求是否受理後，若要重試 API，使用原 UUID 與保存的同一份 ZIP。 |
| 工作 `failed` | 由支援頁檢查工作及網站備份。需要還原時使用網頁的既有還原流程。 |

網頁備援為 `/flashfalcon/console/system/support` 的資料夾發布及版本還原，仍使用原本管理員登入權限。

### 上線前確認

確認 API 入口把 `Authorization` 交給後端，允許上述 POST 與 GET、停用這兩條路徑的快取，並讓所有代理、WAF 和請求診斷記錄遮蔽 `Authorization`。用部署環境確認代理接受 ZIP 大小和上傳時間。確認網站 bucket owner、prefix、CloudFront alias、origin 與 `OriginPath` 一致，並核對 instance role 對私有備份、網站物件及指定 distribution 的讀寫和 invalidation 權限。若 bucket 使用 SSE-KMS，另核對加解密所需的 KMS 權限。 [CloudFront Authorization](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/add-origin-custom-headers.html#forward-authorization-headers)、[AWS WAF 日誌](https://docs.aws.amazon.com/waf/latest/developerguide/logging-management.html)

## 本機驗收邊界

僅 DEBUG 且連到 127.0.0.1:3308/test_snowland 時，允許使用 backend tmp/frontend-publish-target.json 指定同一 tmp 下的隔離目錄。私有備份也改用本機測試目錄。正式 SLDB 或 DEBUG關閉時不能啟用此 adapter；SQLite記憶體測試可用設定注入臨時目錄。

本次本機畫面與檔案系統驗收不等於正式 S3／CloudFront 發布驗收。正式啟用仍需由部署管理者設定上述目標及 instance role，另行授權一次正式發布後確認網站與快取。
