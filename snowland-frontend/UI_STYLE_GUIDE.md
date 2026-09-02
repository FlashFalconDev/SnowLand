# React Console 後台 UI 風格模板

> 此文檔作為 AI 提詞模板，用於生成符合現有後台風格的頁面組件。

---

## 技術棧

- **框架**: React 18 + TypeScript
- **樣式**: Tailwind CSS（純 utility-first，無第三方 UI 庫）
- **圖標**: Lucide React
- **路由**: React Router v6

---

## 主題色彩

### 主色調（紫色系）
```
主色:     #8b5cf6  (bg-[#8b5cf6])
深色:     #7c3aed  (hover:bg-[#7c3aed])
淺色:     #a78bfa  (bg-[#a78bfa])
```

### 狀態色彩
| 狀態 | 背景色 | 文字色 | 應用場景 |
|------|--------|--------|----------|
| 成功 | `bg-green-100` | `text-green-700` | 完成、啟用 |
| 警告 | `bg-yellow-100` | `text-yellow-700` | 待處理、提醒 |
| 錯誤 | `bg-red-100` | `text-red-700` | 失敗、停用 |
| 資訊 | `bg-blue-100` | `text-blue-700` | 提示、說明 |
| 預設 | `bg-purple-100` | `text-purple-700` | 其他狀態 |

### 中性色（深色模式適配）
```
背景:     bg-white dark:bg-gray-800
次背景:   bg-gray-50 dark:bg-gray-700
文字:     text-gray-900 dark:text-white
次文字:   text-gray-600 dark:text-gray-300
輔助文字: text-gray-500 dark:text-gray-400
邊框:     border-gray-200 dark:border-gray-700
```

---

## 常用組件樣式

### 按鈕

```tsx
// 主要按鈕（紫色）
<button className="px-4 py-2 bg-[#8b5cf6] text-white font-medium rounded-lg hover:bg-[#7c3aed] transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
  確認
</button>

// 次要按鈕（白色/灰色）
<button className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-medium rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors">
  取消
</button>

// 危險按鈕
<button className="px-4 py-2 bg-red-500 text-white font-medium rounded-lg hover:bg-red-600 transition-colors">
  刪除
</button>

// 圖標按鈕
<button className="p-2 text-gray-500 hover:text-[#8b5cf6] hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors">
  <Edit size={18} />
</button>
```

### 輸入框

```tsx
// 文字輸入
<input
  type="text"
  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#8b5cf6] focus:border-transparent transition-all"
  placeholder="請輸入..."
/>

// 搜尋輸入框（帶圖標）
<div className="relative">
  <Search size={18} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
  <input
    type="text"
    className="w-full pl-10 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#8b5cf6] focus:border-transparent"
    placeholder="搜尋..."
  />
</div>

// 下拉選單
<select className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6] focus:border-transparent">
  <option value="">請選擇</option>
</select>
```

### 卡片容器

```tsx
// 基礎卡片
<div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
  {/* 內容 */}
</div>

// 可互動卡片
<div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm hover:shadow-lg hover:border-[#8b5cf6]/30 transition-all cursor-pointer">
  {/* 內容 */}
</div>
```

### 表格

```tsx
<div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
  <table className="w-full">
    {/* 表頭 */}
    <thead className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
      <tr>
        <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
          欄位名稱
        </th>
      </tr>
    </thead>

    {/* 表身 */}
    <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
      <tr className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
        <td className="px-5 py-4 text-sm text-gray-600 dark:text-gray-300">
          內容
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

### Modal 對話框

```tsx
{/* 背景遮罩 */}
<div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
  {/* Modal 容器 */}
  <div className="relative bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg animate-slideUp">

    {/* 漸層標題區 */}
    <div className="bg-gradient-to-r from-[#8b5cf6] to-[#7c3aed] rounded-t-2xl px-6 py-4">
      <h3 className="text-lg font-semibold text-white">標題</h3>
    </div>

    {/* 內容區 */}
    <div className="p-6">
      {/* Modal 內容 */}
    </div>

    {/* 操作按鈕區 */}
    <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
      <button className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-medium rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors">
        取消
      </button>
      <button className="px-4 py-2 bg-[#8b5cf6] text-white font-medium rounded-lg hover:bg-[#7c3aed] transition-colors">
        確認
      </button>
    </div>

    {/* 關閉按鈕 */}
    <button className="absolute top-4 right-4 text-white/80 hover:text-white transition-colors">
      <X size={20} />
    </button>
  </div>
</div>
```

### 狀態徽章

```tsx
// 通用徽章組件
const statusStyles = {
  pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  inactive: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  default: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
}

<span className={`px-2.5 py-1 text-xs font-medium rounded-full ${statusStyles.active}`}>
  已啟用
</span>
```

### 加載狀態

```tsx
// 全頁加載
<div className="flex items-center justify-center min-h-[400px]">
  <div className="w-12 h-12 border-4 border-[#8b5cf6] border-t-transparent rounded-full animate-spin" />
</div>

// 按鈕內加載
<button disabled className="px-4 py-2 bg-[#8b5cf6] text-white rounded-lg flex items-center gap-2 disabled:opacity-50">
  <Loader2 size={16} className="animate-spin" />
  處理中...
</button>
```

### 分頁

```tsx
<div className="flex items-center justify-between px-5 py-4 border-t border-gray-200 dark:border-gray-700">
  {/* 資訊 */}
  <div className="text-sm text-gray-600 dark:text-gray-400">
    共 <span className="font-medium">{total}</span> 筆資料
  </div>

  {/* 分頁按鈕 */}
  <div className="flex items-center gap-1">
    <button className="p-2 text-gray-500 hover:text-[#8b5cf6] hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
      <ChevronLeft size={18} />
    </button>

    {/* 頁碼 */}
    <button className="px-3 py-1.5 text-sm rounded-lg bg-[#8b5cf6] text-white">
      1
    </button>
    <button className="px-3 py-1.5 text-sm rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
      2
    </button>

    <button className="p-2 text-gray-500 hover:text-[#8b5cf6] hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
      <ChevronRight size={18} />
    </button>
  </div>
</div>
```

---

## 頁面結構模板

### 列表頁面

```tsx
import { useState, useEffect } from 'react'
import { Search, Plus, Edit, Trash2, Loader2 } from 'lucide-react'

export default function ExampleListPage() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState([])
  const [search, setSearch] = useState('')

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* 頁面標題 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            頁面標題
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            頁面描述說明
          </p>
        </div>
        <button className="px-4 py-2 bg-[#8b5cf6] text-white font-medium rounded-lg hover:bg-[#7c3aed] transition-colors flex items-center gap-2">
          <Plus size={18} />
          新增
        </button>
      </div>

      {/* 搜尋與篩選區 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={18} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#8b5cf6] focus:border-transparent"
              placeholder="搜尋..."
            />
          </div>
          <select className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]">
            <option value="">全部狀態</option>
            <option value="active">啟用</option>
            <option value="inactive">停用</option>
          </select>
        </div>
      </div>

      {/* 表格區域 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-10 h-10 border-4 border-[#8b5cf6] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                  名稱
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                  狀態
                </th>
                <th className="px-5 py-3 text-right text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {data.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                  <td className="px-5 py-4 text-sm text-gray-900 dark:text-white font-medium">
                    {item.name}
                  </td>
                  <td className="px-5 py-4">
                    <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                      啟用
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button className="p-2 text-gray-500 hover:text-[#8b5cf6] hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors">
                        <Edit size={16} />
                      </button>
                      <button className="p-2 text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
```

### 統計卡片網格

```tsx
// Dashboard 風格統計卡片
<div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
  {[
    { label: '總訂單', value: '1,234', icon: ShoppingCart, color: 'bg-blue-100 dark:bg-blue-900/50 text-blue-600' },
    { label: '總營收', value: 'NT$ 123,456', icon: DollarSign, color: 'bg-green-100 dark:bg-green-900/50 text-green-600' },
    { label: '會員數', value: '5,678', icon: Users, color: 'bg-purple-100 dark:bg-purple-900/50 text-purple-600' },
    { label: '商品數', value: '89', icon: Package, color: 'bg-orange-100 dark:bg-orange-900/50 text-orange-600' },
  ].map((stat, index) => (
    <div key={index} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
      <div className="flex items-center gap-4">
        <div className={`w-12 h-12 ${stat.color} rounded-xl flex items-center justify-center`}>
          <stat.icon size={24} />
        </div>
        <div>
          <div className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</div>
        </div>
      </div>
    </div>
  ))}
</div>
```

---

## 動畫效果

### 在 index.css 中定義

```css
/* 淡入 */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.animate-fadeIn {
  animation: fadeIn 0.3s ease-out;
}

/* 向上滑入 */
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.animate-slideUp {
  animation: slideUp 0.3s ease-out;
}
```

### 通用過渡

```
transition-colors      // 顏色過渡
transition-all         // 所有屬性過渡
duration-200          // 200ms
duration-300          // 300ms
```

---

## 響應式設計

### 斷點

| 前綴 | 寬度 | 說明 |
|------|------|------|
| `sm:` | 640px | 小型平板 |
| `md:` | 768px | 平板/小筆電 |
| `lg:` | 1024px | 桌面 |
| `xl:` | 1280px | 大螢幕 |

### 常用響應式模式

```tsx
// 網格響應
className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"

// 隱藏/顯示
className="hidden sm:block"      // 桌面版才顯示
className="block sm:hidden"      // 手機版才顯示

// Flex 方向
className="flex flex-col sm:flex-row gap-3"

// 間距調整
className="p-4 md:p-6"
className="text-sm md:text-base"
```

---

## 全域通知使用

```tsx
import { useNotification } from '../context/ConsoleContext'

function MyComponent() {
  const { success, error, warning, info } = useNotification()

  const handleSave = async () => {
    try {
      await saveData()
      success('儲存成功！')
    } catch (e) {
      error('儲存失敗，請稍後重試')
    }
  }
}
```

---

## 提詞範例

當需要生成新頁面時，可使用以下提詞格式：

```
請幫我建立一個 [功能名稱] 管理頁面，需要包含：

1. 頁面功能：
   - [列出具體功能需求]

2. 資料欄位：
   - [列出資料欄位]

3. 操作：
   - [列出需要的操作]

請遵循 UI_STYLE_GUIDE.md 的設計規範：
- 使用紫色主題 (#8b5cf6)
- 支援深色模式
- 使用 Tailwind CSS
- 使用 Lucide React 圖標
- 包含加載狀態和錯誤處理
```

---

## 文件結構參考

```
src/
├── pages/
│   └── [PageName]Page.tsx    ← 頁面組件
├── api/
│   └── [resource].ts         ← API 函數
├── hooks/
│   └── use[Resource].ts      ← 資料 Hook
├── types/
│   └── index.ts              ← 型別定義
└── components/
    └── [Component].tsx       ← 共用組件
```

---

## 常用圖標（Lucide React）

```tsx
import {
  // 導航
  Home, Settings, Users, Package, ShoppingCart, LayoutDashboard,

  // 操作
  Plus, Edit, Trash2, Save, X, Check, RefreshCw,

  // 搜尋/篩選
  Search, Filter, SlidersHorizontal,

  // 狀態
  Loader2, AlertCircle, CheckCircle, XCircle, Info,

  // 方向
  ChevronLeft, ChevronRight, ChevronUp, ChevronDown, ArrowLeft,

  // 其他
  Download, Upload, Eye, EyeOff, Calendar, Clock, Mail, Phone,
} from 'lucide-react'
```
