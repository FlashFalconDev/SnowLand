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

## 本機驗收邊界

僅 DEBUG 且連到 127.0.0.1:3308/test_snowland 時，允許使用 backend tmp/frontend-publish-target.json 指定同一 tmp 下的隔離目錄。私有備份也改用本機測試目錄。正式 SLDB 或 DEBUG關閉時不能啟用此 adapter；SQLite記憶體測試可用設定注入臨時目錄。

本次本機畫面與檔案系統驗收不等於正式 S3／CloudFront 發布驗收。正式啟用仍需由部署管理者設定上述目標及 instance role，另行授權一次正式發布後確認網站與快取。
