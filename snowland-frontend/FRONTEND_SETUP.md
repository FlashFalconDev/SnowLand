# 🎨 前端多租戶系統 - 設定與測試指南

## ✅ 已完成的修改

### 1. **新增 Landing Page（客戶選擇頁）**
- 檔案：`src/pages/ClientSelectionPage.tsx`
- 功能：顯示所有可用的客戶，讓用戶選擇

### 2. **修改路由結構**
- 檔案：`src/App.tsx`
- 新增路由：
  - `/` → Landing Page（客戶選擇）
  - `/:clientCode/*` → 客戶專屬路由
  - `/:clientCode/payment` → 付款頁面
  - `/:clientCode/history` → 歷史紀錄

### 3. **修改 API 配置自動加入 client_code**
- 檔案：`src/api/axios.ts`
- 所有 API 請求自動轉換：
  - `/booking/api/xxx` → `/booking/<client_code>/api/xxx`
  - 從 localStorage 或 URL 自動獲取 client_code

### 4. **新增 ClientContext**
- 檔案：`src/contexts/ClientContext.tsx`
- 管理 client_code 的全域狀態

---

## 🚀 如何啟動

### 步驟 1：安裝依賴（如果需要）

```bash
cd /mnt/c/FlashFalconSystem/snowland-frontend
npm install
```

### 步驟 2：確認後端已啟動

確保 Django 後端運行在 `http://localhost:8000`：

```bash
cd /mnt/c/FlashFalconSystem/snowland
python manage.py runserver
```

### 步驟 3：啟動前端開發服務器

```bash
cd /mnt/c/FlashFalconSystem/snowland-frontend
npm run dev
```

應該會看到：
```
VITE v4.x.x  ready in xxx ms

➜  Local:   http://localhost:3000/
➜  Network: use --host to expose
```

---

## 🧪 測試流程

### 測試 1：訪問 Landing Page

1. 打開瀏覽器訪問：`http://localhost:3000/`
2. 應該看到**客戶選擇頁面**，列出：
   - 雪域創遊（snowland）
   - 測試滑雪學校（testski）

### 測試 2：選擇客戶進入預訂系統

1. 點擊「雪域創遊」
2. URL 應該變成：`http://localhost:3000/snowland`
3. 應該看到**登入頁面**
4. 檢查瀏覽器 Console，應該沒有錯誤

### 測試 3：檢查 API 調用

1. 打開瀏覽器開發者工具（F12）
2. 切換到 Network 標籤
3. 登入後，查看 API 請求
4. 應該看到所有 API 請求都是：
   - `http://localhost:8000/booking/snowland/api/xxx` ✅
   - 而不是：`http://localhost:8000/booking/api/xxx` ❌

### 測試 4：測試 localStorage

1. 訪問：`http://localhost:3000/snowland`
2. 打開瀏覽器 Console
3. 輸入：`localStorage.getItem('client_code')`
4. 應該返回：`"snowland"`

### 測試 5：測試租戶切換

1. 訪問：`http://localhost:3000/snowland`（雪域創遊）
2. 登入並預訂課程
3. 回到首頁：`http://localhost:3000/`
4. 點擊「測試滑雪學校」
5. URL 變成：`http://localhost:3000/testski`
6. localStorage 應該更新為：`client_code = "testski"`

---

## 📁 新增/修改的檔案清單

### 新增檔案
1. `src/pages/ClientSelectionPage.tsx` - Landing Page
2. `src/contexts/ClientContext.tsx` - Client 狀態管理
3. `FRONTEND_SETUP.md` - 本文件

### 修改檔案
1. `src/App.tsx` - 路由結構
2. `src/api/axios.ts` - API 配置

---

## 🎯 URL 結構對比

### 舊的 URL 結構（不支援多租戶）
```
http://localhost:3000/              → 登入頁面
http://localhost:3000/payment       → 付款頁面
http://localhost:3000/history       → 歷史紀錄
```

### 新的 URL 結構（支援多租戶）✅
```
http://localhost:3000/                    → Landing Page（選擇客戶）
http://localhost:3000/snowland            → 雪域創遊的登入頁面
http://localhost:3000/snowland/payment    → 雪域創遊的付款頁面
http://localhost:3000/snowland/history    → 雪域創遊的歷史紀錄
http://localhost:3000/testski             → 測試滑雪學校的登入頁面
```

---

## 🔧 API 調用示例

### 自動轉換機制

當你在前端調用：
```typescript
import api from '@/api/axios'

// 你的代碼
api.get('/course-categories/')
```

實際發送的請求：
```
GET http://localhost:8000/booking/snowland/api/course-categories/
```

client_code (`snowland`) 是自動加入的！

### 如何運作

1. **從 localStorage 讀取**：
   ```javascript
   const clientCode = localStorage.getItem('client_code') // 'snowland'
   ```

2. **從 URL 讀取**（備用）：
   ```javascript
   // 當前 URL: http://localhost:3000/snowland/payment
   const pathParts = window.location.pathname.split('/')
   const clientCode = pathParts[1] // 'snowland'
   ```

3. **axios 攔截器自動加入**：
   ```javascript
   config.baseURL = `/booking/${clientCode}/api`
   ```

---

## ⚠️ 常見問題

### Q1: 訪問 `http://localhost:3000/` 還是看到舊的登入頁面？

**A**: 可能的原因：
1. **前端沒有重新編譯**：
   - 停止開發服務器（Ctrl+C）
   - 重新運行：`npm run dev`

2. **瀏覽器快取**：
   - 按 Ctrl+Shift+R 強制刷新
   - 或清除瀏覽器快取

3. **修改沒有保存**：
   - 檢查 `src/App.tsx` 是否有保存

### Q2: API 請求失敗，顯示 404？

**A**: 檢查後端：
1. Django 是否在運行：`http://localhost:8000/`
2. 後端是否有創建 Client：
   ```bash
   python manage.py shell
   ```
   ```python
   from Client.models import Client
   Client.objects.filter(internal_code='snowland').exists()  # 應該返回 True
   ```

### Q3: 切換客戶後，還是看到舊客戶的資料？

**A**: 清除快取：
1. 打開瀏覽器 Console
2. 輸入：
   ```javascript
   localStorage.clear()
   location.reload()
   ```

### Q4: 如何添加新的客戶到 Landing Page？

**A**: 修改 `src/pages/ClientSelectionPage.tsx`：
```typescript
const mockClients: Client[] = [
  {
    internal_code: 'snowland',
    name: '雪域創遊',
    sales: '張三',
    program: '標準方案'
  },
  // 🔥 新增客戶
  {
    internal_code: 'newclient',  // URL 會是 /newclient
    name: '新滑雪學校',
    sales: '王五',
    program: 'VIP 方案'
  }
]
```

---

## 🎨 客製化 Landing Page

### 修改樣式

編輯 `src/pages/ClientSelectionPage.tsx`：

```typescript
// 修改背景顏色
<div className="min-h-screen bg-gradient-to-br from-purple-50 to-pink-100">

// 修改卡片樣式
<button className="bg-white rounded-xl p-6 shadow-lg hover:shadow-2xl ...">
```

### 從後端 API 獲取客戶列表

替換 mock 數據：
```typescript
const fetchClients = async () => {
  try {
    const response = await fetch('http://localhost:8000/api/clients/')
    const data = await response.json()
    setClients(data)
    setLoading(false)
  } catch (err) {
    setError('無法載入客戶列表')
    setLoading(false)
  }
}
```

---

## ✅ 檢查清單

部署前確認：

- [ ] 前端啟動正常（`npm run dev`）
- [ ] 後端啟動正常（`python manage.py runserver`）
- [ ] Landing Page 顯示正確（`http://localhost:3000/`）
- [ ] 可以選擇客戶進入系統
- [ ] API 請求包含正確的 client_code
- [ ] localStorage 正確儲存 client_code
- [ ] 可以在不同客戶間切換
- [ ] 登入後 session 記住 client_code

---

## 🚀 下一步

### 選項 1：連接真實的後端 API

修改 `ClientSelectionPage.tsx`，從後端獲取客戶列表：
```typescript
const response = await api.get('/clients/')  // 需要後端實現此 API
```

### 選項 2：添加客戶 Logo

在 `Client` 介面加入 `logo_url`：
```typescript
interface Client {
  internal_code: string
  name: string
  logo_url?: string  // 新增
  sales: string
  program: string
}
```

### 選項 3：記住最後使用的客戶

在 Landing Page 加入「繼續使用上次的客戶」：
```typescript
const lastClient = localStorage.getItem('client_code')
if (lastClient) {
  // 顯示「繼續使用 xxx」按鈕
}
```

---

**現在你可以測試前端了！打開 `http://localhost:3000/` 看看 Landing Page！🎉**
