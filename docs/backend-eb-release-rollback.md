# 後端 EB 發布與回退

封包、環境變數、健康端點與 migration 執行者見 [EB 部署設定](aws-eb-deployment.md)。正式 EB 與正式 DB 操作須依 [共通代理規則](../AGENTS.md) 取得小陌兩步確認。

## 1. 準備、核對與取得核准

1. 用 `git ls-remote origin refs/heads/main` 核對遠端 main HEAD。指定 worktree 應乾淨，且其 HEAD 等於計畫中的候選 SHA 和遠端 main HEAD。記錄目前健康的 EB 環境 VersionLabel、對應程式 SHA 和 Ready/Green/Ok，留作回退目標。已知的舊格式 label 須有包裝器已核對的來源；來源不明就停。
2. 用 EB 環境資源記錄部署前實例數 N0。若能讀取 Auto Scaling 群組，確認 N0 ≥ MinSize、N0 等於 DesiredCapacity。基線不符時每 30 秒查一次，最多等 20 分鐘；仍不符就停。Auto Scaling 查詢權限不足時，記錄 N0 並核對 Ready/Green/Ok。
3. 比對候選版與線上版 migration 差異、獲准的檔名和執行順序，以及正式庫唯讀取得的實際待套清單（例如已授權唯讀連線下的 `showmigrations --plan`）。先前回滾可能已留下相容 schema，須核對預計已套與待套的狀態。現行包裝器提供正式待套清單的方式待確認。缺少唯讀證據、狀態不明、部分套用或清單漂移就停止並回報。
4. 第 1 步計畫列出候選 SHA、PR 與發布範圍、EB 目標與當前健康版本、租戶設定或初始化、待套 migration（順序、[分級](migration-tiers.md)、影響、相容與隔離 MySQL 證據）、快照目標、驗證指令與結果、發布順序、停止條件、應用程式及 schema 回退方式。小陌明確同意後才進第 2 步。
5. 從指定 worktree 的 `snowland/` 目錄使用 SnowlandDeploy 包裝器做部署前驗證。`--verify-only` 核對來源與 PR／CI，執行或沿用同一候選的本機檢查與隔離 MySQL 證據。它不建正式快照、不上傳、不部署。比對收據的 SHA、結果與候選計畫。

```powershell
eb deploy snowland-prod --verify-only --profile snowland --region ap-northeast-1
```

## 2. 備份、換版與驗收

1. 執行第 2 步前重查 main、EB 基線和待套清單。含 migration 的發布沿用 [EB 備份與相容性規則](aws-eb-deployment.md#migration-與發布)。包裝器先核對 RDS 備份目標，再建本次新快照。確認收據和快照狀態為 `available` 才上傳部署；目標不符、權限不足或快照失敗就停。包裝器在無 migration 變更時不建快照。另有正式資料操作時，在計畫列出備份與復原點。
2. 用 `eb deploy snowland-prod --profile snowland --region ap-northeast-1` 部署獲准的候選。EB 滾動換版（Rolling with Additional Batch）會暫時增加批次，依 EB 事件觀察各批實例替換，核對 ALB targets 與實例版本。Migration 由單次 EB 部署的 leader 執行，避免同庫同時部署。核對具名 migration 套用結果；只有 PostBuild 訊息或 smoke 通過時，個別 migration 狀態仍列待確認。
3. 自 EB 更新完成事件和包裝器結束時間中較晚者起，最多等 10 分鐘。約每 20 秒查環境和實例，約每分鐘查 EB 事件。連續兩次都須為預期 VersionLabel、Ready/Green/Ok、恰為 N0 台且異常實例 0 台。實例健康查詢權限不足時，實戰以 N0、HealthStatus=Ok、ALB targets 健康和事件無 `Incorrect application version` 警告交叉核對。短暫 Red、Degraded 或 Severe 先記錄並繼續觀察。
4. 穩定後執行獨立 smoke。包裝器先驗證 probe 規格，再對正式站以唯讀 GET 查 `/healthz/` 與設定的路由，且不跟隨轉址。查收逐筆收據，全部通過才接受後端版本。若同次計畫含前端，後端驗收後才發布。Smoke 的預期 4xx 可能短暫影響 EB 顏色。

```powershell
eb deploy snowland-prod --smoke-only --profile snowland --region ap-northeast-1
```

## 3. 停止、回退與重試

1. 若狀態不明、migration 部分套用或清單漂移，停止後續部署並保留證據。若包裝器明確失敗、EB 有部署 ERROR、健康逾 10 分鐘未過或 smoke 失敗，依獲准計畫回退程式。先查 EB 與收據，確認是否已自動回退。
2. 若需手動回退，依獲准計畫執行 `aws elasticbeanstalk update-environment --environment-name <環境> --version-label <上一個健康 VersionLabel> --profile <profile> --region <region>`，將 EB 環境切回上一個健康版本。保留已套用且與舊版相容的 schema。Schema 回滾、還原快照或修改正式資料都須另走小陌兩步確認。
3. 回退後依第 2 節的健康等待規則，核對 EB `VersionLabel` 為上一個健康版本且環境為 Ready/Green/Ok，再執行 `--smoke-only`。若要重試部署，先用 `--verify-only` 核對候選 commit 的本機檢查與隔離 MySQL 驗證證據。記錄快照、版本、健康、migration、收據與失敗原因。
4. 同一 commit 與計畫範圍內，工具、健康檢查、等待時間或腳本造成失敗或自動回退，修正並由 Claude 重驗後可直接重試，最多兩次。換 commit、新增或修改 migration、另需操作正式 DB、變更計畫範圍或兩次後仍失敗，重新請小陌確認。
5. 看板記錄 PR、SHA、版本、快照狀態、嘗試次數、驗證及回退結果。更新方式見 [共通代理規則](../AGENTS.md#看板與文件)。
