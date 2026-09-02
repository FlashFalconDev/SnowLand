# 雪域滑雪預約系統 - React 遷移指南

## 📋 前端功能完整清單

### 一、核心業務流程（主要功能）

| 流程編號 | 功能名稱 | 當前實現方式 | 涉及組件/函數 | React 對應組件建議 |
|---------|---------|-------------|--------------|------------------|
| **1** | **登入流程** | Django Social Auth + Google OAuth | Google 登入按鈕 | `<GoogleLoginButton />` |
| **2** | **課程大類選擇** | Modal 彈窗 | `courseCategoryModal` | `<CourseCategorySelector />` |
| **3** | **雪場選擇** | Modal 彈窗 | `resortModal` | `<ResortSelector />` |
| **4** | **課程類型選擇** | Modal 彈窗 | `courseTypeModal` | `<CourseTypeSelector />` |
| **5** | **人數選擇** | Modal 彈窗 + 增減按鈕 | `peopleModal`, `decreasePeople()`, `increasePeople()` | `<PeopleCountSelector />` |
| **6** | **6歲以下檢查** | 條件式 Modal | `under6QuestionModal`, `under6SuggestModal` | `<Under6Modal />` |
| **7** | **能力等級選擇** | Modal 彈窗 | `abilityLevelModal` | `<AbilityLevelSelector />` |
| **8** | **5步驟預約流程** | 動態生成 Steps | `stepsConfig`, `renderSteps()` | `<BookingSteps />` |
| **9** | **教練選擇** | Modal + API 查詢 | `coachSelectModal`, `selectCoachFromModal()` | `<CoachSelector />` |
| **10** | **裝備租借選擇** | 按鈕選擇 | `selectEquipment()` | `<EquipmentSelector />` |
| **11** | **課程模板選擇** | 卡片網格 | `selectCourseTemplate()` | `<CourseTemplateGrid />` |
| **12** | **日期選擇（日曆）** | 自訂日曆組件 | `initCalendar()`, `selectDate()` | `<CustomCalendar />` |
| **13** | **時段選擇** | 按鈕選擇 | `selectTimeSlot()` | `<TimeSlotSelector />` |
| **14** | **加入購物車** | 狀態管理 + 本地儲存 | `addToCartButton`, `cart` 陣列 | `<CartButton />` + Redux/Context |
| **15** | **購物車查看** | Modal 彈窗 | `cartModal`, `openModal()` | `<CartModal />` |
| **16** | **確定預約（送出）** | API 呼叫 | `confirmBooking()` | `<ConfirmBookingButton />` |
| **17** | **預約歷史查看** | Modal + API | `reservationsModal` | `<ReservationHistoryModal />` | ✅ 已實現（過濾已刪除預約）|

---

### 二、功能細項拆解（依流程順序）

#### 🔐 登入與用戶管理
| 功能 | 說明 | 當前實現 | React 組件建議 |
|------|------|---------|---------------|
| Google 登入 | OAuth2 登入 | Django `socialaccount` | `<GoogleLoginButton />` |
| 用戶頭像顯示 | 顯示 Google 頭像 | `profile-container` | `<UserAvatar />` |
| 用戶選單 | 登出、查看預約 | `profile-menu` | `<UserMenu />` |

---

#### 📝 預約流程前置選擇（Modal 系列）

| 步驟 | Modal ID | 功能 | 函數 | React 組件 | 資料來源 |
|------|----------|------|------|-----------|---------|
| 1 | `courseCategoryModal` | 選擇課程大類（單板/雙板/攝影） | `selectCourseCategory()` | `<CourseCategoryModal />` | `COURSE_CATEGORIES` |
| 2 | `resortModal` | 選擇雪場 | `selectResort()` | `<ResortModal />` | `RESORT_CHOICES` |
| 3 | `courseTypeModal` | 選擇課程類型 | `selectCourseType()` | `<CourseTypeModal />` | `COURSE_TYPES` |
| 4 | `peopleModal` | 選擇人數（1-6人） | `confirmPeopleCount()` | `<PeopleModal />` | State |
| 5 | `under6QuestionModal` | 6歲以下是否可自主滑行 | `handleUnder6SelfSki()` | `<Under6QuestionModal />` | State |
| 6 | `under6SuggestModal` | 建議1對1流程 | `confirmUnder6Suggest()` | `<Under6SuggestModal />` | State |
| 7 | `abilityLevelModal` | 選擇滑雪能力等級 | 能力按鈕點擊 | `<AbilityLevelModal />` | `ABILITY_LEVEL_CHOICES` |

---

#### 🎯 5步驟預約流程（主流程）

| 步驟編號 | 步驟名稱 | 圖示 | 功能 | 函數 | React 組件 | 資料來源 |
|---------|---------|------|------|------|-----------|---------|
| Step 1 | 選擇教練 | users | 可選指定教練或不指定 | `openCoachModal()` | `<CoachSelector />` | API: `/api/coaches/` |
| Step 2 | 裝備租借 | shopping-bag | 選擇是否租借裝備 | `selectEquipment()` | `<EquipmentSelector />` | `EQUIPMENT_CHOICES` |
| Step 3 | 選擇課程模板 | book-open | 選擇課程時長和類型 | `selectCourseTemplate()` | `<CourseTemplateGrid />` | `COURSE_TEMPLATES` |
| Step 4 | 選擇日期 | calendar-days | 日曆選擇上課日期 | `selectDate()` | `<CustomCalendar />` | State + API |
| Step 5 | 選擇時段 | clock | 選擇上課時段 | `selectTimeSlot()` | `<TimeSlotSelector />` | `COURSE_SESSIONS` |

---

#### 🛒 購物車系統

| 功能 | 說明 | 當前實現 | React 組件 | State 管理建議 |
|------|------|---------|-----------|---------------|
| 購物車按鈕 | 固定在右上角 | `view-cart-button` | `<CartButton />` | Redux/Context |
| 購物車數量徽章 | 顯示購物車項目數 | `cart.length` | `<CartBadge />` | Redux Selector |
| 加入購物車 | 將當前選擇加入購物車 | `addToCartButton` | `<AddToCartButton />` | Redux Action |
| 查看購物車 | 彈窗顯示所有項目 | `cartModal` | `<CartModal />` | Redux Store |
| 移除項目 | 從購物車移除 | `removeCourse()` | `<RemoveButton />` | Redux Action |
| 計算總價 | 即時計算總金額 | `cartTotalAmount` | `<CartTotal />` | Redux Selector |
| 確定預約 | 送出所有購物車項目 | `confirmBooking()` | `<ConfirmButton />` | API Call |

---

#### 👨‍🏫 教練選擇系統

| 功能 | 說明 | 當前實現 | React 組件 | API |
|------|------|---------|-----------|-----|
| 教練列表 | 顯示可選教練 | `renderCoachList()` | `<CoachList />` | `GET /api/coaches/` |
| 語言篩選 | 依語言篩選教練 | `onLanguageChange()` | `<LanguageFilter />` | 前端過濾 |
| 教練搜尋 | 依名稱搜尋 | `searchCoach()` | `<CoachSearch />` | 前端搜尋 |
| 教練卡片 | 顯示教練資訊 | `coach-item` | `<CoachCard />` | - |
| 選擇教練 | 點擊選擇 | `selectCoachFromModal()` | `<CoachCard onClick />` | - |
| 教練預約時段 | 顯示已被預約的時段 | `fetchBookedSlots()` | `<BookedSlots />` | `GET /api/coach-bookings/` |
| 不指定教練 | 選擇任意教練 | `selectCoachFromModal('any')` | `<AnyCoachButton />` | - |

---

#### 📅 日曆系統（複雜組件）

| 功能 | 說明 | 當前實現 | React 組件 | 狀態 |
|------|------|---------|-----------|------|
| 渲染日曆 | 顯示當月日期 | `updateCalendarDays()` | `<CalendarGrid />` | `currentMonth`, `currentYear` |
| 月份切換 | 上一月/下一月 | `changeMonth()` | `<MonthNavigator />` | State |
| 日期選擇 | 點擊選擇日期 | `selectDate()` | `<DayCell onClick />` | `selectedDate` |
| 不可選日期 | 灰色顯示過去日期 | CSS class `disabled` | `<DayCell disabled />` | 計算邏輯 |
| 已預約標記 | 顯示該日已被預約 | `updateCalendarWithBookings()` | `<BookingMarker />` | API 資料 |
| 日期範圍檢查 | 檢查課程開放日期 | `isDateWithinRange()` | 前端邏輯 | `COURSE_TEMPLATES` |

---

#### ⏰ 時段選擇系統

| 功能 | 說明 | 當前實現 | React 組件 | 資料來源 |
|------|------|---------|-----------|---------|
| 渲染時段列表 | 依課程模板顯示時段 | `TEMPLATE_SLOTS_CONFIG` | `<TimeSlotList />` | `COURSE_SESSIONS` |
| 時段按鈕 | 可點擊的時段卡片 | `selectTimeSlot()` | `<TimeSlotButton />` | - |
| 時段資訊 | 顯示開始/結束時間 | `start_time`, `end_time` | `<TimeSlotInfo />` | Session 資料 |
| 時段衝突檢查 | 檢查教練是否已被預約 | `checkIfDateFullyBooked()` | 前端邏輯 | API 資料 |

---

#### 🎨 UI/UX 組件

| 組件 | 功能 | 當前實現 | React 組件 |
|------|------|---------|-----------|
| 通知系統 | 顯示成功/錯誤訊息 | `showNotification()` | `<Toast />` / `<Notification />` |
| 載入動畫 | 顯示載入中狀態 | `loadingAnimation` | `<LoadingSpinner />` |
| 返回按鈕 | 返回上一步 | `goBack()` | `<BackButton />` |
| Modal 關閉 | 關閉彈窗 | `closeModal()` | `<Modal onClose />` |
| 步驟指示器 | 顯示當前進度 | `stepsConfig` | `<StepIndicator />` |

---

### 三、全域狀態管理

#### 需要管理的狀態

| 狀態名稱 | 用途 | 當前實現 | React State 建議 |
|---------|------|---------|-----------------|
| `selectedCourseCategory` | 選中的課程大類 | 全域變數 | Redux/Context |
| `selectedResort` | 選中的雪場 | 全域變數 | Redux/Context |
| `selectedCourseType` | 選中的課程類型 | 全域變數 | Redux/Context |
| `peopleCount` | 預約人數 | 全域變數 | Redux/Context |
| `hasUnder6` | 是否有6歲以下 | 全域變數 | Redux/Context |
| `selectedAbilityLevel` | 能力等級 | 全域變數 | Redux/Context |
| `state.selectedcoach` | 選中的教練 | 全域物件 | Redux/Context |
| `state.selectedCourseTemplate` | 選中的課程模板 | 全域物件 | Redux/Context |
| `state.selectedDate` | 選中的日期 | 全域物件 | Redux/Context |
| `state.selectedTimeSlotId` | 選中的時段 | 全域物件 | Redux/Context |
| `state.selectedLanguage` | 選中的語言 | 全域物件 | Redux/Context |
| `state.needEquipment` | 是否需要裝備 | 全域物件 | Redux/Context |
| `cart` | 購物車內容 | 陣列 | Redux Store |
| `currentMonth` | 日曆當前月份 | 全域變數 | Local State |
| `currentYear` | 日曆當前年份 | 全域變數 | Local State |

---

### 四、API 整合

#### 需要呼叫的 API

| API 端點 | 方法 | 用途 | 當前實現 | React Hook 建議 |
|---------|------|------|---------|----------------|
| `/api/coaches/` | GET | 查詢教練列表 | `fetch()` | `useCoaches()` |
| `/api/coach-bookings/` | GET | 查詢教練預約時段 | `fetch()` | `useCoachBookings()` |
| `/api/calculate-price/` | GET | 計算課程價格 | `fetch()` | `useCalculatePrice()` |
| `/api/create_reservation/` | POST | 建立預約 | `confirmBooking()` | `useCreateReservation()` |
| `/api/history_reservations/` | GET | 查詢歷史預約 | `fetch()` | `useReservationHistory()` |
| `/api/payment_gmail/` | POST | 發送付款連結 | `fetch()` | `useSendPaymentEmail()` |

---

### 五、資料流程圖

```
使用者登入
    ↓
選擇課程大類（單板/雙板/攝影）
    ↓
選擇雪場
    ↓
選擇課程類型
    ↓
選擇人數
    ↓
（如有6歲以下）6歲以下檢查
    ↓
選擇能力等級
    ↓
========== 進入5步驟預約流程 ==========
    ↓
Step 1: 選擇教練（可選）
    ├─ 開啟教練選擇 Modal
    ├─ 選擇語言篩選
    ├─ 搜尋教練
    └─ 選擇教練或「任意教練」
    ↓
Step 2: 裝備租借（選擇是否需要）
    ↓
Step 3: 選擇課程模板
    ├─ 顯示可用課程卡片
    └─ 選擇課程時長
    ↓
Step 4: 選擇日期
    ├─ 渲染日曆
    ├─ 顯示已預約標記
    ├─ 檢查日期範圍
    └─ 選擇日期
    ↓
Step 5: 選擇時段
    ├─ 顯示可用時段
    ├─ 檢查時段衝突
    └─ 選擇時段
    ↓
加入購物車
    ↓
（可選）加入新的預約（重複流程）
    ↓
查看購物車
    ├─ 確認所有項目
    ├─ 查看總價
    └─ 移除不要的項目
    ↓
確定預約（送出 API）
    ├─ 顯示載入動畫
    ├─ 呼叫 create_reservation API
    └─ 根據回應跳轉或顯示錯誤
    ↓
（成功）跳轉付款頁面
（失敗）顯示錯誤訊息或建議替代方案
```

---

### 六、組件層級結構建議

```
<App />
├── <AuthProvider />
│   ├── <GoogleLoginButton />
│   └── <UserMenu />
│       ├── <UserAvatar />
│       └── <LogoutButton />
│
├── <BookingProvider />  ← Redux Store 或 Context
│   │
│   ├── <PreBookingModals />  ← 前置選擇 Modals
│   │   ├── <CourseCategoryModal />
│   │   ├── <ResortModal />
│   │   ├── <CourseTypeModal />
│   │   ├── <PeopleCountModal />
│   │   ├── <Under6QuestionModal />
│   │   └── <AbilityLevelModal />
│   │
│   ├── <BookingStepsContainer />  ← 5步驟主流程
│   │   ├── <StepIndicator />
│   │   ├── <StepContent />
│   │   │   ├── Step1: <CoachSelector />
│   │   │   │   ├── <CoachModal />
│   │   │   │   ├── <LanguageFilter />
│   │   │   │   ├── <CoachSearch />
│   │   │   │   └── <CoachList />
│   │   │   │       └── <CoachCard />
│   │   │   │
│   │   │   ├── Step2: <EquipmentSelector />
│   │   │   │
│   │   │   ├── Step3: <CourseTemplateGrid />
│   │   │   │   └── <CourseTemplateCard />
│   │   │   │
│   │   │   ├── Step4: <CustomCalendar />
│   │   │   │   ├── <MonthNavigator />
│   │   │   │   ├── <CalendarHeader />
│   │   │   │   └── <CalendarGrid />
│   │   │   │       └── <DayCell />
│   │   │   │
│   │   │   └── Step5: <TimeSlotSelector />
│   │   │       └── <TimeSlotButton />
│   │   │
│   │   └── <AddToCartButton />
│   │
│   ├── <CartSystem />
│   │   ├── <CartButton />
│   │   │   └── <CartBadge />
│   │   ├── <CartModal />
│   │   │   ├── <CartItemList />
│   │   │   │   └── <CartItem />
│   │   │   ├── <CartTotal />
│   │   │   └── <ConfirmBookingButton />
│   │   └── <ReservationHistoryModal />
│   │
│   └── <UIComponents />  ← 通用組件
│       ├── <Toast />
│       ├── <LoadingSpinner />
│       ├── <Modal />
│       └── <BackButton />
│
└── <NotificationProvider />
```

---

### 七、技術棧建議

#### 核心框架
- **React 18+** - 主框架
- **TypeScript** - 型別安全
- **Vite** - 開發工具

#### 狀態管理
- **Redux Toolkit** - 全域狀態（購物車、預約資料）
  - 或 **Zustand** - 輕量級替代方案
  - 或 **React Context** - 簡單場景

#### UI 框架
- **Tailwind CSS** - 樣式（符合現有風格）
- **Headless UI** - 無樣式組件（Modal, Dialog）
- **Lucide React** - 圖標（已在用）

#### 表單處理
- **React Hook Form** - 表單管理
- **Zod** - 驗證

#### API 請求
- **TanStack Query (React Query)** - 資料獲取和快取
- **Axios** - HTTP 客戶端

#### 日期處理
- **date-fns** - 日期工具（日曆組件）

#### 動畫
- **Framer Motion** - 動畫效果（取代 anime.js）

---

### 八、建議的資料夾結構

```
snowland-frontend/
├── src/
│   ├── components/
│   │   ├── auth/
│   │   │   ├── GoogleLoginButton.tsx
│   │   │   ├── UserAvatar.tsx
│   │   │   └── UserMenu.tsx
│   │   │
│   │   ├── booking/
│   │   │   ├── modals/
│   │   │   │   ├── CourseCategoryModal.tsx
│   │   │   │   ├── ResortModal.tsx
│   │   │   │   ├── CourseTypeModal.tsx
│   │   │   │   ├── PeopleCountModal.tsx
│   │   │   │   └── AbilityLevelModal.tsx
│   │   │   │
│   │   │   ├── steps/
│   │   │   │   ├── CoachSelector.tsx
│   │   │   │   ├── EquipmentSelector.tsx
│   │   │   │   ├── CourseTemplateGrid.tsx
│   │   │   │   ├── CustomCalendar.tsx
│   │   │   │   └── TimeSlotSelector.tsx
│   │   │   │
│   │   │   ├── BookingStepsContainer.tsx
│   │   │   └── StepIndicator.tsx
│   │   │
│   │   ├── cart/
│   │   │   ├── CartButton.tsx
│   │   │   ├── CartModal.tsx
│   │   │   ├── CartItem.tsx
│   │   │   └── CartTotal.tsx
│   │   │
│   │   ├── coach/
│   │   │   ├── CoachModal.tsx
│   │   │   ├── CoachCard.tsx
│   │   │   ├── CoachList.tsx
│   │   │   ├── LanguageFilter.tsx
│   │   │   └── CoachSearch.tsx
│   │   │
│   │   ├── calendar/
│   │   │   ├── CustomCalendar.tsx
│   │   │   ├── MonthNavigator.tsx
│   │   │   ├── CalendarGrid.tsx
│   │   │   └── DayCell.tsx
│   │   │
│   │   └── ui/
│   │       ├── Modal.tsx
│   │       ├── Toast.tsx
│   │       ├── LoadingSpinner.tsx
│   │       └── BackButton.tsx
│   │
│   ├── store/
│   │   ├── index.ts
│   │   ├── slices/
│   │   │   ├── bookingSlice.ts
│   │   │   ├── cartSlice.ts
│   │   │   └── authSlice.ts
│   │   └── hooks.ts
│   │
│   ├── api/
│   │   ├── axios.ts
│   │   ├── coaches.ts
│   │   ├── reservations.ts
│   │   └── pricing.ts
│   │
│   ├── hooks/
│   │   ├── useCoaches.ts
│   │   ├── useCoachBookings.ts
│   │   ├── useCalculatePrice.ts
│   │   └── useReservationHistory.ts
│   │
│   ├── types/
│   │   ├── booking.ts
│   │   ├── coach.ts
│   │   ├── course.ts
│   │   └── cart.ts
│   │
│   ├── utils/
│   │   ├── dateUtils.ts
│   │   ├── priceUtils.ts
│   │   └── validators.ts
│   │
│   ├── constants/
│   │   └── config.ts
│   │
│   ├── App.tsx
│   └── main.tsx
│
├── public/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

---

### 九、實現進度追蹤

#### 最新更新 (2025-10-15)

**預約歷史紀錄功能 - 完成優化**
- 📍 位置：`/mnt/c/FlashFalconSystem/snowland-frontend/src/pages/HistoryPage.tsx`
- ✅ 已過濾已刪除的預約（status !== 'deleted'）
- ✅ 自動過濾空的預約組（沒有有效預約的組不顯示）
- 🎯 邏輯：
  1. 在 API 返回數據後立即過濾
  2. 過濾每個組內狀態為 'deleted' 的預約
  3. 過濾掉沒有任何有效預約的預約組
  4. 保持狀態乾淨，避免前端顯示已刪除數據

**修改內容：**
```typescript
// 過濾掉已刪除的預約
const filteredHistory = (data.history || [])
  .map(group => ({
    ...group,
    reservations: group.reservations.filter(res => res.status !== 'deleted')
  }))
  .filter(group => group.reservations.length > 0) // 如果組內沒有有效預約，則過濾掉整個組
```

**下一步計劃：**
- [ ] 繼續完成其他預約流程組件的 React 化
- [ ] 實現購物車系統
- [ ] 整合支付流程
