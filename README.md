# SnowLand

本儲存庫包含 SnowLand 前端與後端。兩者可分別啟動及部署，不需要拆成兩個 Git 儲存庫。

| 位置 | 用途 |
| --- | --- |
| `snowland-frontend/` | React 前端、前端設定、前端測試與編譯產物 |
| `snowland/` | Django 後端、後端設定、資料庫 migration、後端測試及 EB 部署設定 |
| `docs/` | 共用操作、部署與交接文件 |
| `tools/` | 共用啟動、本機測試資料庫與內容整理工具；仍保留測試這些工具或後端頁面的檢查 |
| `tmp/`、`output/` | 本機暫存、驗收紀錄與輸出報告；Git 忽略，非部署內容 |

## 設定歸屬

- 前端：複製 `snowland-frontend/.env.example` 為同目錄 `.env.local`，只放 `VITE_` 公開設定。正式編譯也從前端目錄讀取設定。
- 後端：使用 `snowland/snowland/.env.example` 作範本，敏感設定放同目錄 `.env` 或主機環境變數。
- 共用本機資料庫：根目錄 `.env.local` 由 `tools/snowland-test-db.ps1` 管理，僅供本機 `127.0.0.1:3308/test_snowland` 使用。後端仍會讀取這份本機設定，主機環境變數優先。
- 舊版根目錄 `.env` 仍供後端相容讀取公開 Google Client ID，不要直接刪除。前端沒有自己的環境設定檔時，也會相容讀取根目錄的公開 `VITE_` 設定。升級時，原先根目錄 `.env`／`.env.local` 的全部 `VITE_` 設定應搬到前端 `.env.local`；不要複製其他密碼或 Token。
- `.env`、`.env.local`、虛擬環境、`node_modules`、測試資料庫和報告都不提交或部署。

## 本機啟動

前端使用 `tools/snowland-frontend.cmd`，固定 `3000`；後端使用 `tools/snowland-backend.cmd`，固定 `8999`。腳本依自身位置定位專案，專案搬到其他目錄後不用改寫絕對路徑。

啟動腳本不會自行改 port，不會自動執行 migration、建立示範資料或處理排程。初次建立本機資料庫後，需另外檢查並執行所需初始化。不要將本機測試啟動腳本用在正式主機。

## 檢查與部署

- 前端：在 `snowland-frontend/` 執行 `npm ci`、`npm test`、`npm run build`。前端測試位於 `tests/`；部分檢查會讀取同一儲存庫的後端內容範本。
- 後端：在 `snowland/` 執行對應虛擬環境的 Django 檢查與測試。測試環境使用 `snowland.test_settings`，不要將正式資料庫作為測試目標。
- 部署：前端只發布 `snowland-frontend/dist/`；後端 EB 從 `snowland/` 部署。不要把儲存庫根目錄整包上傳。詳細設定見 `docs/aws-eb-deployment.md`。

## 本機目錄搬移

移動整個專案時保留隱藏的 `.git`、本機設定及未提交資料。Windows Python 虛擬環境內部分啟動程式可能含原目錄，搬移後需重新建立虛擬環境。目錄搬移不會變更 GitHub 的儲存庫擁有者；GitHub 移轉必須另外指定接收帳號／組織。
