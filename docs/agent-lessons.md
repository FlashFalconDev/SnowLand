# 代理工作教訓

- GitHub CI 使用 SQLite，資料庫不會強制執行 Django 欄位的 `max_length`。建立測試資料時仍須遵守 model 欄位長度，因為部署前的 premerge 會在隔離的 MySQL 上跑測試，超長字串會失敗。例如 `age_range='PRIVATE_AGE'` 有 11 字元，超過欄位上限 10。
