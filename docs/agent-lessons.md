# 代理工作教訓

- GitHub CI 使用 SQLite，資料庫不會強制執行 Django 欄位的 `max_length`。建立測試資料時仍須遵守 model 欄位長度，因為部署前的 premerge 會在隔離的 MySQL 上跑測試，超長字串會失敗。例如 `age_range='PRIVATE_AGE'` 有 11 字元，超過欄位上限 10。

- SQLite 綠、MySQL 紅已發生兩次（#62 測試資料超過 `max_length`、#71 相簿測試，根因詳見相簿修正 PR）。後端改動應檢查 CI 的 `backend-mysql`，派工時請審查者跑 MySQL 測試。測試資料須符合欄位長度與唯一性約束，使用實際取得的主鍵，避免依賴 SQLite 的寬鬆行為、寫死自增 ID，或為同一 `(client, user)` 重複建立 `Coach`。
