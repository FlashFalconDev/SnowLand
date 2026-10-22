# SnowLand EB 雙主機部署設定

## 環境與部署來源

EB application bundle 的根目錄為 `snowland/`，其中包含 `manage.py`、`requirements.txt`、`Procfile` 與 `.ebextensions/`。不要直接把整個 Git repository 當成 EB application bundle；前端另行建置與部署。

本次只修改程式及部署設定，未建立 AWS 資源、上傳既有附件或執行正式資料庫 migration。

## 本次部署所需的環境變數名稱

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `STATIC_URL`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_REGION`
- `SNOWLAND_PRIVATE_MEDIA_BUCKET`
- `Mysql_NAME`
- `Mysql_USER`
- `Mysql_PASSWORD`
- `Mysql_HOST`
- `Mysql_PORT`

本機不設定私有 Bucket 時，繼續使用本機儲存，並可用 `SNOWLAND_PRIVATE_COURSE_MEDIA_ROOT` 指定路徑。正式雙主機必須設定私有 Bucket，避免附件分散到兩台磁碟。

`DJANGO_DEBUG` 只有明確設定為 `1` 才啟用。`DJANGO_SECRET_KEY` 必須使用新產生的密鑰，兩台主機相同；缺少時停止啟動。根目錄的 `.env.local` 是 Git 忽略的本機設定，系統環境變數優先；不得將它打包到 EB。

`DJANGO_ALLOWED_HOSTS` 與 `DJANGO_CSRF_TRUSTED_ORIGINS` 使用逗號分隔；前者填主機名稱，後者包含 scheme。另須依既有前後端分離設定確認 CORS；本次沒有修改 CORS 規則。

## S3 與 IAM

靜態檔使用 Django 5.1 的 `STORAGES['staticfiles']`。`STATIC_URL` 指向客戶自己的 HTTPS 靜態網址，URL 路徑同時作為 S3 靜態檔 prefix。靜態 Bucket/CDN 的讀取政策需另行設定，不能把私有附件 Bucket 公開。

私有檔案固定使用獨立 Bucket 的 `private_course_media/` prefix，保留既有資料庫 file name。`url()` 仍會拒絕直接產生檔案網址；下載仍經既有身分與租戶權限檢查，透過 storage 讀檔及處理 Range。

依需求保留 `default_acl='private'`。部署時 Bucket 必須啟用 ACL，且持續封鎖公開存取；若使用新 Bucket 預設的 Bucket owner enforced（停用 ACL），上傳會被拒絕，需先調整 Bucket 或另行確認改採不傳 ACL 的私有政策方案。

正式環境使用 EC2 instance role，不設定 `AWS_ACCESS_KEY_ID`／`AWS_SECRET_ACCESS_KEY`。角色需有靜態檔發布及私有檔案讀寫刪除的必要權限；現有私有 ACL 寫入亦需相應的 `s3:PutObjectAcl` 權限。SSE-KMS 加密時另授予適用的 KMS 權限。

本機附件不會自動搬到 S3。先備份，再將原本媒體根目錄內容複製到私有 Bucket 的 `private_course_media/`，保留相對路徑；完成筆數、內容及授權下載驗證後，才讓兩台主機切換到該 Bucket。

## 健康檢查與 IMDSv2

ALB 健康檢查設定為 `/healthz/`，成功碼僅 `200`。路由不要求登入，且豁免 Django HTTPS 轉址；檢查資料庫連線失敗時回 `503`，不回傳例外細節，也不執行排程或寫入資料。

`ensure_connection()` 確認連線可建立；它不代表 migration、S3 或其他外部服務健康，也不會對已存在的連線額外執行查詢。資料庫全面故障可能使所有 target 同時不健康，不能將此端點當成全部依賴健康的保證。

啟動時只使用 IMDSv2 token 讀取 EC2 IPv4，驗證格式後加入 `ALLOWED_HOSTS`；不退回 IMDSv1。本機或 metadata 無法連線時，使用環境變數中的 hosts。

## Migration 與發布

`.ebextensions/02_migrate.config` 使用 EB 虛擬環境，並以 `leader_only: true` 執行 `migrate --noinput`。此設定適用單次環境部署，不是跨環境／跨部署的全域鎖；不要同時部署多個環境操作同一資料庫。

執行前備份並檢查 migration 與舊版本相容性；有失敗不得忽略錯誤。新增主機、擴容與一般啟動不應另外執行 migration。

## 機密與 Git

根目錄 `.env` 停止追蹤但保留本機檔案。本次檢查其 Git 歷史只含 `VITE_GOOGLE_CLIENT_ID`，這是公開識別碼，不是 OAuth Client Secret，無須當成私密金鑰輪替。

原始碼內舊 Django 密鑰已移除；正式環境需另行設定全新 `DJANGO_SECRET_KEY`。切換密鑰會影響以舊密鑰簽署的 Session、JWT 與其他簽章，應安排重新登入。移除目前檔案不會清除 Git 歷史；舊密鑰不得再使用。

本次不會修改客戶或 FlashFalcon 的外部服務憑證。若其他地方曾外洩 AWS、Google OAuth Client Secret、資料庫或第三方服務密鑰，需由相應服務完成撤銷、重建及驗證，不能只修改 `.env` 檔案當作輪替完成。

## 驗證結果（2026-10-22）

| 需求 | 驗證方式 | 結果 |
| --- | --- | --- |
| 私有 S3 與本機 fallback（1、2） | 真實 S3Storage/S3File 搭配遠端邊界 mock；兩個實例共用檔案、完整讀取與 Range；既有附件、QR 與簽名授權回歸測試 | PASS |
| 健康檢查（3） | 匿名 HTTP 在啟用 HTTPS 轉址時仍回 200；模擬 DB 故障回 503；SQLite 測試庫真實連線 | PASS |
| IMDSv2（4） | 驗證 token PUT 與 token header GET；無效 IP、IPv6、逾時與 token 錯誤不加入 hosts、不回退 IMDSv1 | PASS |
| Secret、DEBUG、靜態檔與網域（5–8） | 缺 secret 停止啟動；DEBUG 明確啟用；客戶靜態 URL；無設定長期 AWS 憑證；hosts 與 CSRF 清單解析 | PASS |
| Migration（9） | 人工檢查 EB 官方格式與 leader_only；本機及 S3 設定下執行 migration 差異檢查，均無變更 | PASS（設定／差異檢查；未執行 AWS 部署） |
| Git 與機密（10） | `.env` 停止追蹤並保留本機檔案；歷史變數名稱盤點；移除硬編碼 Django 密鑰並產生新的本機密鑰 | PASS（Git 歷史未改寫） |

執行：`manage.py test snowland.tests_deployment API.tests_course_media_uploads API.tests_class_group_qr API.tests_payroll_documents booking.tests_google_login_config --settings=snowland.test_settings`，51 項通過。`manage.py check --settings=snowland.test_settings`、Python 語法與 Git whitespace 檢查通過。

尚未進行真實 AWS S3／IAM／ALB／IMDS 與 EB 部署驗收，不能將遠端邊界 mock 的結果當成雲端實測。部署時仍需設定新密鑰、Bucket 與角色，搬遷附件並完成實機驗收。
