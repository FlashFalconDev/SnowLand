# SnowLand 共通代理規則

## 分支與審查

1. 每個任務使用自己的 `C:\FlashFalconDev\snowland-wt\<name>` worktree，分支命名 `codex/<topic>-<date>`。保留有未提交變更的主 checkout。
2. LINE 工程群「叫工程」自行判斷的修整，先同步 `main` 到 `bot` 再開工。PR 開進 `bot`，`frontend-test`、`frontend-build`、`backend-tests` 與審查通過後自動合併。由 `bot` 開 PR 到 `main` 時，附變更、測試與審查結論，等小陌點頭再合。
3. 小陌直接交辦的工作，PR 直接開進 `main`，CI 與審查通過後合併。遇到 CI 或分支保護阻擋就回報，遵守原有檢查。Force push、`reset --hard` 或刪除分支都須先取得明確同意。
4. Codex 撰寫，Claude 審查並實際重跑測試。撰寫和審查使用不同 CLI。

## 正式環境與機密

- 正式部署（EB、正式前端）與正式 DB 資料或結構操作（含 migration、schema 回滾）一律兩步確認。第 1 步說明變更、影響與回退方式，小陌明確同意後才執行第 2 步。
- 一次「上線」授權同一個 commit 和同一份部署計畫。工具、健康檢查、等待時間或腳本造成失敗或自動回滾時，修好流程並由 Claude 審過後可直接重試，最多兩次。換 commit、新增或修改 migration、另需動正式 DB 資料或結構、改計畫範圍，或兩次重試仍失敗，都須重新請小陌確認。
- 憑證由小陌本人輸入，只比對 sha8。禁止提交或印出 `.env`、密碼、token。
- 測試使用測試庫，migration 驗證使用隔離 MySQL。

## 看板與文件

- 在 `agent-monitor` 執行 `node project-update.js upsert snowland-<id> ... --owner "SnowLand 碼匠"`。只在有實質完成時帶 `--progress`。
- 啟動與測試見 [README](README.md) 和 [代理工作教訓](docs/agent-lessons.md)。
- 後端部署見 [EB 部署設定](docs/aws-eb-deployment.md) 和 [EB 發布與回退手冊](docs/backend-eb-release-rollback.md)。有 migration 時讀 [Migration 分級與演練](docs/migration-tiers.md)。
