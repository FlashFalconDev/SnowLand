# 🎨 客戶品牌化指南

## ✅ 已實現的功能

### 1. **動態顯示客戶名稱**

#### 登入頁面
- **檔案**：`src/pages/LoginPage.tsx`
- **顯示位置**：
  - 頁面標題：「{客戶名稱}預約系統」
  - 瀏覽器標籤：「{客戶名稱} - 登入」

#### 範例
```
當用戶選擇「雪域創遊」：
- 頁面顯示：「雪域創遊預約系統」
- 瀏覽器標籤：「雪域創遊 - 登入」

當用戶選擇「測試滑雪學校」：
- 頁面顯示：「測試滑雪學校預約系統」
- 瀏覽器標籤：「測試滑雪學校 - 登入」
```

---

## 🔧 技術實現

### 流程
1. **用戶在 Landing Page 選擇客戶**
   ```typescript
   // ClientSelectionPage.tsx
   const handleClientSelect = (clientCode: string) => {
     const selectedClient = clients.find(c => c.internal_code === clientCode)
     localStorage.setItem('client_code', clientCode)
     localStorage.setItem('client_name', selectedClient.name)
     navigate(`/${clientCode}`)
   }
   ```

2. **LoginPage 讀取並顯示**
   ```typescript
   // LoginPage.tsx
   const { clientName } = useClientInfo()
   // 顯示：{clientName}預約系統
   ```

---

## 📦 新增的文件

### 1. `src/hooks/useClient.ts`
**用途**：統一管理客戶資訊的 hook

**使用方法**：
```typescript
import { useClientInfo } from '@/hooks/useClient'

function MyComponent() {
  const { clientCode, clientName, clientInfo } = useClientInfo()

  return (
    <div>
      <h1>{clientName}預約系統</h1>
      <p>客戶代碼：{clientCode}</p>
    </div>
  )
}
```

**返回值**：
- `clientCode`: 客戶代碼（例如：'snowland'）
- `clientName`: 客戶名稱（例如：'雪域創遊'）
- `clientInfo`: 完整客戶資訊（包含 sales、program 等）

---

## 🎯 其他可以品牌化的地方

### 1. **Logo**
如果客戶有自己的 Logo，可以替換山的圖標：

```typescript
// LoginPage.tsx
const { clientInfo } = useClientInfo()

<div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-primary-500 to-purple-500 mb-4 shadow-lg">
  {clientInfo?.logo_url ? (
    <img src={clientInfo.logo_url} alt={clientName} className="w-12 h-12" />
  ) : (
    <Mountain size={40} className="text-white" />
  )}
</div>
```

### 2. **主題色**
根據客戶設定不同的主題色：

```typescript
// 在 ClientInfo 加入 theme_color
interface ClientInfo {
  internal_code: string
  name: string
  theme_color?: string  // 例如：'#1E40AF'
}

// 使用
<div
  className="bg-gradient-to-br from-primary-500 to-purple-500"
  style={{
    background: clientInfo?.theme_color
      ? `linear-gradient(to bottom right, ${clientInfo.theme_color}, ${lighten(clientInfo.theme_color)})`
      : undefined
  }}
>
```

### 3. **付款頁面**
修改 `PaymentPage.tsx` 也顯示客戶名稱：

```typescript
// src/pages/PaymentPage.tsx
import { useClientInfo } from '@/hooks/useClient'

export default function PaymentPage() {
  const { clientName } = useClientInfo()

  useEffect(() => {
    document.title = `${clientName} - 付款`
  }, [clientName])

  return (
    <div>
      <h1>{clientName} - 付款資訊</h1>
      {/* ... */}
    </div>
  )
}
```

### 4. **歷史紀錄頁面**
修改 `HistoryPage.tsx`：

```typescript
// src/pages/HistoryPage.tsx
import { useClientInfo } from '@/hooks/useClient'

export default function HistoryPage() {
  const { clientName } = useClientInfo()

  useEffect(() => {
    document.title = `${clientName} - 預約紀錄`
  }, [clientName])

  return (
    <div>
      <h1>{clientName} - 預約紀錄</h1>
      {/* ... */}
    </div>
  )
}
```

### 5. **Header/導航欄**
如果有導航欄，也可以顯示客戶名稱：

```typescript
function Header() {
  const { clientName, clientInfo } = useClientInfo()

  return (
    <header className="bg-white shadow">
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center">
          {clientInfo?.logo_url && (
            <img src={clientInfo.logo_url} alt={clientName} className="w-8 h-8 mr-2" />
          )}
          <span className="font-bold">{clientName}</span>
        </div>
        {/* ... 其他導航元素 */}
      </div>
    </header>
  )
}
```

---

## 🧪 測試步驟

### 測試 1：檢查客戶名稱顯示

1. 訪問：`http://localhost:3000/`
2. 選擇「雪域創遊」
3. 應該看到：
   - 頁面標題：「**雪域創遊**預約系統」 ✅
   - 瀏覽器標籤：「**雪域創遊** - 登入」 ✅

4. 返回首頁，選擇「測試滑雪學校」
5. 應該看到：
   - 頁面標題：「**測試滑雪學校**預約系統」 ✅
   - 瀏覽器標籤：「**測試滑雪學校** - 登入」 ✅

### 測試 2：檢查 localStorage

打開瀏覽器 Console，輸入：
```javascript
localStorage.getItem('client_code')   // 應返回：'snowland'
localStorage.getItem('client_name')   // 應返回：'雪域創遊'
localStorage.getItem('client_info')   // 應返回：完整的 JSON 字串
```

### 測試 3：檢查 useClientInfo hook

在任何組件中使用：
```typescript
const { clientCode, clientName, clientInfo } = useClientInfo()
console.log('客戶代碼:', clientCode)      // 'snowland'
console.log('客戶名稱:', clientName)      // '雪域創遊'
console.log('客戶資訊:', clientInfo)      // { internal_code: 'snowland', name: '雪域創遊', ... }
```

---

## 📝 修改的檔案清單

### 修改檔案
1. `src/pages/ClientSelectionPage.tsx` - 存入客戶名稱和完整資訊
2. `src/pages/LoginPage.tsx` - 顯示客戶名稱和更新瀏覽器標題

### 新增檔案
1. `src/hooks/useClient.ts` - 客戶資訊 hook
2. `CLIENT_BRANDING.md` - 本文件

---

## 🎉 完成！

現在你的系統已經支持：
- ✅ 動態顯示客戶名稱在登入頁面
- ✅ 瀏覽器標籤標題也會顯示客戶名稱
- ✅ 可以輕鬆在其他頁面使用 `useClientInfo()` hook

---

## 💡 下一步建議

1. **添加客戶 Logo 支持**
   - 在 `Client` 模型加入 `logo_url` 欄位
   - 在 `ClientSelectionPage` 顯示 Logo
   - 在 `LoginPage` 顯示客戶 Logo

2. **支持客戶主題色**
   - 在 `Client` 模型加入 `theme_color` 欄位
   - 動態修改頁面主題色

3. **其他頁面品牌化**
   - 修改 PaymentPage 顯示客戶名稱
   - 修改 HistoryPage 顯示客戶名稱
   - 在 Header 顯示客戶 Logo 和名稱

---

**現在刷新頁面，重新從首頁選擇客戶，就能看到客戶名稱了！** 🎉
