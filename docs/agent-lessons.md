# 代理工作教訓

- GitHub CI 使用 SQLite，資料庫不會強制執行 Django 欄位的 `max_length`。建立測試資料時仍須遵守 model 欄位長度，因為部署前的 premerge 會在隔離的 MySQL 上跑測試，超長字串會失敗。例如 `age_range='PRIVATE_AGE'` 有 11 字元，超過欄位上限 10。

- 長度與唯一性（#62 `age_range`）。SQLite 不檢查 `max_length`。測試資料須遵守欄位長度與唯一鍵，使用實際取得的主鍵，避免依賴自增 ID。
- 串流關閉（#71／#78）。測試中直接呼叫 `StreamingHttpResponse`／`FileResponse` 的 `.close()` 會觸發 `request_finished` → `close_old_connections`。MySQL 會關閉 `TestCase` 交易中的連線，後續查詢會拋出 `TransactionManagementError`，權限流程也可能把錯誤轉成 403。記憶體 SQLite 不會關閉這條連線。用 `b''.join(response.streaming_content)` 讀完內容，讓測試用戶端收尾。請勿手動呼叫 `.close()`。

後端改動請檢查 CI 的 `backend-mysql` job，審查者須跑 MySQL 測試。
