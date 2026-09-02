# 雪域滑雪課程預約系統 - React 前端

## 🚀 快速開始

### 安裝依賴
```bash
npm install
```

### 啟動開發伺服器
```bash
npm run dev
```

開啟瀏覽器訪問 `http://localhost:3000`

### 建構生產版本
```bash
npm run build
```

---

## 📁 專案結構

```
src/
├── components/          # React 組件
│   ├── ui/             # 通用 UI 組件（Modal, Button 等）
│   ├── booking/        # 預約相關組件
│   ├── cart/           # 購物車組件
│   └── coach/          # 教練相關組件
├── store/              # Zustand 狀態管理
├── types/              # TypeScript 型別定義
├── hooks/              # 自定義 Hooks
├── api/                # API 請求邏輯
├── utils/              # 工具函數
├── App.tsx             # 主要應用組件
└── main.tsx            # 入口文件
```

---

## 🎨 目前已實作功能

✅ 基礎專案設定（Vite + React + TypeScript）
✅ Tailwind CSS 樣式系統
✅ Zustand 全域狀態管理
✅ 通用 Modal 組件
✅ 課程大類選擇 Modal
✅ 雪場選擇 Modal
✅ 響應式設計（手機/平板/桌面）

---

## 🔧 技術棧

- **React 18** - UI 框架
- **TypeScript** - 型別安全
- **Vite** - 建構工具
- **Tailwind CSS** - 樣式框架
- **Zustand** - 狀態管理
- **Lucide React** - 圖標庫

---

## 📝 待實作功能

- [ ] 課程類型選擇 Modal
- [ ] 人數選擇 Modal
- [ ] 能力等級選擇 Modal
- [ ] 5 步驟預約流程
  - [ ] Step 1: 教練選擇
  - [ ] Step 2: 裝備租借
  - [ ] Step 3: 課程模板選擇
  - [ ] Step 4: 日曆日期選擇
  - [ ] Step 5: 時段選擇
- [ ] 購物車系統
- [ ] API 整合（React Query）
- [ ] 預約歷史查看
- [ ] Google OAuth 登入

---

## 🔗 API 端點

開發環境下，Vite 會自動代理 `/api/*` 請求到 `http://localhost:8000`

確保 Django 後端運行在 8000 port：
```bash
python manage.py runserver
```

---

## 💡 開發建議

1. **組件開發原則**
   - 單一職責：每個組件只做一件事
   - 可複用：通用組件放在 `components/ui/`
   - 型別安全：使用 TypeScript 定義 Props

2. **狀態管理**
   - 全域狀態：使用 Zustand（購物車、預約資料）
   - 本地狀態：使用 useState（Modal 開關）
   - 伺服器狀態：使用 React Query（API 資料）

3. **樣式規範**
   - 優先使用 Tailwind 類別
   - 避免自定義 CSS
   - 保持設計一致性

---

## 🎯 下一步

1. 繼續實作剩餘的 Modal 組件
2. 建立 5 步驟預約流程
3. 整合 React Query 處理 API
4. 加入動畫效果（Framer Motion）
5. 單元測試（Vitest）

---

## 📞 支援

有問題請參考：
- [React 官方文檔](https://react.dev/)
- [Tailwind CSS 文檔](https://tailwindcss.com/)
- [Zustand 文檔](https://zustand-demo.pmnd.rs/)
