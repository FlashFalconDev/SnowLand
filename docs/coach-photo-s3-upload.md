# 教練官網照片上傳（S3）

後台「教練介紹 → 編輯官網介紹」的照片欄位改以上傳為主，並保留貼上網址／站內路徑作為後備。

## 做法（仿 FlashFalcon 的後端代傳）

FlashFalcon（`External/apiAWS.py` 的 `BytesIO_upload_s3`）由後端接收檔案、設定 `ContentType`、以 boto3 `upload_fileobj` 寫入 bucket（不送物件 ACL，公開讀取由 bucket policy 控制），回傳 `https://{bucket}.s3.{region}.amazonaws.com/{key}`。SnowLand 沿用同一模式（`snowland/API/coach_photo_storage.py`）：

- `POST /api/admin/snowland/website-coach-editor/<id>/upload-photo/`（multipart，欄位 `photo`）：沿用 `IsTenantManager` + `permission_key='site_coaches'`、CSRF、租戶／校區範圍（`get_object()`）及 `can_manage`。後端以 Pillow 驗證內容為 JPEG／PNG／WebP 並限制大小，key 為 `{prefix}/{tenant_id}/{coach_id}/{uuid}.{ext}`，不使用使用者檔名。
- 上傳只回傳 URL，不直接改資料；按「儲存變更」時才由既有 PATCH 寫入 `Coach.img`（欄位不變）。
- `GET .../website-coach-editor/photo-upload-config/`：回報是否啟用上傳與大小上限；未設定 bucket 時前端自動只顯示網址欄。
- `img` 為 null 或字面 `None` 時，API 回傳與前端皆視為空白。

## 環境變數（只列名稱，值由主機環境設定）

| 變數 | 用途 |
| --- | --- |
| `SNOWLAND_COACH_PHOTO_BUCKET` | 公開讀取的 bucket；留空＝停用上傳 |
| `SNOWLAND_COACH_PHOTO_REGION` | 未設時退回 `AWS_REGION` |
| `SNOWLAND_COACH_PHOTO_PREFIX` | key 前綴，預設 `coach-photos` |
| `SNOWLAND_COACH_PHOTO_PUBLIC_BASE_URL` | 選填，CDN／自訂網域 |
| `SNOWLAND_COACH_PHOTO_MAX_BYTES` | 預設 5242880（5 MB） |

憑證沿用 EB 執行個體 IAM role（與既有 S3 設定一致），不得寫入程式或文件。

## 上線前需先準備

1. 建立（或指定）bucket，關閉物件 ACL（BucketOwnerEnforced）。
2. bucket policy 對 `coach-photos/*` 開放公開 `s3:GetObject`（或經 CloudFront）。
3. EB instance role 對該 prefix 具 `s3:PutObject`。
4. 在 EB 設定上列環境變數。
5. `Coach.img` 為 `URLField(max_length=200)`；S3 URL 約 100 字內。若改用過長的 CDN 網域需留意此上限。

## 測試

- 後端：`python manage.py test API.tests_website_coach_editor`（S3 以 mock，不連 AWS）。
- 前端：`npm test`（`tests/test-coach-photo-upload.cjs`、`tests/test-website-coach-editor.cjs`）。
