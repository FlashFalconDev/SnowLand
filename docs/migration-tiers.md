# Migration 分級與演練

| 分級 | 常見操作與驗證 | 小陌核准 |
| --- | --- | --- |
| Tier 1（instant） | 可空欄位新增、新表等。確認 DDL 無須鎖表重建或複製，且舊版相容。即使 MySQL 使用 INSTANT，仍可能等待 metadata lock。 | 列入上線兩步確認的 migration 清單。 |
| Tier 2（可能鎖表或重建） | Table-copy、外鍵、加索引、改欄型別。列出資料量、預計鎖或重建時間、部署時段及舊版相容證據。 | PR 逐支說明，在部署計畫第 1 步取得同意。 |
| Tier 3（破壞性） | 刪欄、刪表、rename、資料回填或刪除。確認對舊版、既有資料與反向操作的影響，寫明不可逆之處和復原方式。 | PR 逐支說明，在部署計畫第 1 步取得同意。 |

任何正式 DB 資料或結構操作都走兩步確認。先確認滾動部署期間新舊版可共用 schema，也要驗證退回舊版後仍能讀寫新版寫入的資料。加外鍵時檢查舊版刪除與清理流程。正式備份與回退見 [EB 部署設定](aws-eb-deployment.md#migration-與發布) 和 [後端 EB 發布與回退手冊](backend-eb-release-rollback.md)。

## PR 離線檢查

在 repo 根目錄執行 `python tools/check_pr_migrations.py --base origin/main --pr-body-file <PR 說明檔>`，開進 `bot` 時改用 `--base origin/bot`。腳本以指定 base 與已提交 HEAD 的 merge base 比對，也可由 `PR_BODY` 提供 PR 內文。

有 migration 時依 [PR 範本](../.github/pull_request_template.md) 填一行 `Migration：有`，並用項目符號逐支列出反引號包住的完整 repo 路徑與分級。既有 migration 改動或刪除、編號重複、可判定的相依分叉，以及漏填 PR 清單都會使檢查失敗。無法解析的相依性會提示人工核對。分級提示供審查參考，最終分級依實際 SQL 與證據。CI 的 `migration-check` 提供回報，分支保護的必過檢查沿用原本三項。

## 隔離 MySQL 前進、回退、再前進

1. 依 [代理工作教訓](agent-lessons.md) 使用隔離 MySQL。SQLite 測試不檢查部分 MySQL 欄位限制，且會跳過部分舊 migrations。演練請新建拋棄式 MySQL 空庫，使用專用帳號。Docker 只對 loopback 開 port；連線目標不得轉送到正式庫，也不得掛載真實資料或使用正式憑證。
2. 用環境變數提供 `SNOWLAND_DRILL_USER` 和 `SNOWLAND_DRILL_PASSWORD`。可設定 `SNOWLAND_DRILL_HOST`、`SNOWLAND_DRILL_PORT`、`SNOWLAND_DRILL_DB`，預設為 `127.0.0.1:33306` 和 `snowland_migration_drill`。只接受 `localhost`／`127.0.0.1`，或 GitHub Actions 中名為 `mysql` 的 service。庫名須以底線分隔包含 `test`、`drill` 或 `throwaway`。已有表或 view 的資料庫會被拒絕。
3. 在 repo 根目錄確認計畫，再用已安裝 `snowland/requirements.txt` 的 Python 執行演練，結束後銷毀本次專用容器及資料。預設回退一支，可用 `--steps` 改步數。

```powershell
python tools/migration_rollback_drill.py --app booking --steps 2 --dry-run
python tools/migration_rollback_drill.py --app booking --steps 2
```

乾跑只印計畫並驗證連線目標格式。正式執行會載入真實 migration graph，依序遷移至指定 app 的最新版本、回退指定步數、再套用原版本，逐步核對 `django_migrations`。遇到分叉、無法選定回退點、不可逆或執行失敗時回傳非 0。空庫演練只涵蓋前後向操作，資料量、鎖表、資料保留和新舊版讀寫仍須依 PR 範圍補證據。
