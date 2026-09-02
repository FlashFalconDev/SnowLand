# 🔧 客戶代碼與名稱映射

## 🐛 問題說明

### 之前的問題
當用戶訪問 `http://localhost:3000/snowland` 時，頁面顯示的是「測試滑雪學校」而不是「雪域創遊」。

**原因**：
1. localStorage 中有舊的快取資料
2. 系統沒有根據 URL 的 client_code 更新客戶名稱

---

## ✅ 已修正

### 修正內容

#### 1. `useClient.ts` Hook 的改進
檔案：`src/hooks/useClient.ts`

**新功能**：
- ✅ 從 URL 參數自動獲取 `client_code`
- ✅ 檢查 localStorage 快取是否匹配當前 client_code
- ✅ 使用映射表查詢客戶名稱
- ✅ 自動更新 localStorage

**流程**：
```typescript
1. 從 URL 獲取 client_code (例如：/snowland)
   ↓
2. 檢查 localStorage 是否有正確的快取
   ├─ 有且匹配 → 使用快取
   └─ 沒有或不匹配 → 查詢映射表
   ↓
3. 根據 client_code 查詢對應的客戶名稱
   ├─ snowland → "雪域創遊"
   └─ testski → "測試滑雪學校"
   ↓
4. 更新 localStorage 快取
```

#### 2. ClientSelectionPage 的改進
檔案：`src/pages/ClientSelectionPage.tsx`

**新功能**：
- ✅ 輸入 client_code 時清除舊的快取
- ✅ 避免顯示錯誤的客戶名稱

---

## 📊 客戶映射表

### 當前映射
檔案位置：`src/hooks/useClient.ts` (第 57-70 行)

```typescript
const clientMapping: Record<string, ClientInfo> = {
  snowland: {
    internal_code: 'snowland',
    name: '雪域創遊',
    sales: '張三',
    program: '標準方案'
  },
  testski: {
    internal_code: 'testski',
    name: '測試滑雪學校',
    sales: '李四',
    program: '進階方案'
  }
}
```

### 如何新增客戶

當你新增一個客戶時，需要在兩個地方更新：

#### 1. 後端（Django）
```python
# Python manage.py shell
from Client.models import Client

Client.objects.create(
    name='新滑雪學校',
    internal_code='newski',
    is_active=True
)
```

#### 2. 前端（React）
修改 `src/hooks/useClient.ts`：
```typescript
const clientMapping: Record<string, ClientInfo> = {
  snowland: { ... },
  testski: { ... },
  newski: {  // 🔥 新增
    internal_code: 'newski',
    name: '新滑雪學校',
    sales: '王五',
    program: 'VIP 方案'
  }
}
```

---

## 🚀 更好的方案：從後端 API 獲取

### 當前方案的缺點
- ❌ 需要在前端手動維護映射表
- ❌ 新增客戶時需要修改兩個地方
- ❌ 容易忘記更新

### 理想方案：創建後端 API

#### 步驟 1：創建 Django API
```python
# booking/api_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from Client.models import Client

class ClientInfoAPI(APIView):
    """獲取客戶資訊"""
    def get(self, request, client_code):
        try:
            client = Client.objects.get(
                internal_code=client_code,
                is_active=True
            )
            return Response({
                'internal_code': client.internal_code,
                'name': client.name,
                'logo_url': client.logo_url,
                'sales': client.sales,
                'program': client.program,
            })
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=404)
```

#### 步驟 2：修改前端 Hook
```typescript
// src/hooks/useClient.ts
const fetchClientInfo = async (code: string) => {
  try {
    const response = await fetch(`/api/clients/${code}/`)
    const data = await response.json()
    return data
  } catch (err) {
    console.error('Failed to fetch client info:', err)
    return null
  }
}
```

**優點**：
- ✅ 自動同步前後端
- ✅ 新增客戶時只需要在 Django Admin 操作
- ✅ 支援動態更新（例如：客戶改名）

---

## 🧪 測試步驟

### 測試 1：清除快取後訪問 snowland

1. **清除 localStorage**
   ```javascript
   // 打開瀏覽器 Console (F12)
   localStorage.clear()
   ```

2. **訪問 snowland**
   ```
   http://localhost:3000/snowland
   ```

3. **檢查結果**
   - ✅ 頁面標題應該顯示：「**雪域創遊**預約系統」
   - ✅ 瀏覽器標籤：「**雪域創遊** - 登入」

### 測試 2：切換到 testski

1. **訪問 testski**
   ```
   http://localhost:3000/testski
   ```

2. **檢查結果**
   - ✅ 頁面標題應該顯示：「**測試滑雪學校**預約系統」
   - ✅ 瀏覽器標籤：「**測試滑雪學校** - 登入」

### 測試 3：檢查 localStorage

打開瀏覽器 Console：
```javascript
localStorage.getItem('client_code')   // 應返回：'testski'
localStorage.getItem('client_name')   // 應返回：'測試滑雪學校'
```

### 測試 4：從首頁輸入

1. **訪問首頁**
   ```
   http://localhost:3000/
   ```

2. **輸入代碼**
   - 輸入：`snowland`
   - 點擊「繼續」

3. **檢查結果**
   - ✅ URL 變成：`/snowland`
   - ✅ 顯示：「**雪域創遊**預約系統」

---

## 📝 修改的檔案清單

### 修改檔案
1. `src/hooks/useClient.ts`
   - 新增從 URL 獲取 client_code
   - 新增客戶映射表
   - 新增快取驗證邏輯

2. `src/pages/ClientSelectionPage.tsx`
   - 輸入時清除舊快取

### 新增檔案
1. `CLIENT_MAPPING.md` - 本文件

---

## ⚠️ 注意事項

### 1. 映射表需要手動維護
目前客戶資訊是寫死在前端代碼中，新增客戶時記得更新 `src/hooks/useClient.ts`。

### 2. 清除快取
如果發現客戶名稱顯示錯誤，執行：
```javascript
localStorage.clear()
location.reload()
```

### 3. 建議實作後端 API
參考上面的「更好的方案」，創建後端 API 來動態獲取客戶資訊。

---

**現在應該顯示正確的客戶名稱了！清除快取後重新測試！** 🎉
