# 代理工作教訓

- 長度與唯一性（#62 `age_range`）。GitHub CI 的 SQLite 測試不強制執行 Django 欄位的 `max_length`，CI 的 MySQL 測試與部署前的隔離 MySQL 驗證會拒絕超長字串。例如 `age_range='PRIVATE_AGE'` 有 11 字元，超過欄位上限 10。測試資料須遵守欄位長度與唯一鍵，使用實際取得的主鍵，避免依賴自增 ID。
- 串流關閉（#71／#78）。測試中直接呼叫 `StreamingHttpResponse`／`FileResponse` 的 `.close()` 會觸發 `request_finished` → `close_old_connections`。MySQL 會關閉 `TestCase` 交易中的連線，後續查詢會拋出 `TransactionManagementError`，權限流程也可能把錯誤轉成 403。記憶體 SQLite 不會關閉這條連線。用 `b''.join(response.streaming_content)` 讀完內容，讓測試用戶端收尾。請勿手動呼叫 `.close()`。

後端改動請檢查 CI 的 `backend-mysql` job，審查者須跑 MySQL 測試。
