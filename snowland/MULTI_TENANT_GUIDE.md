# 🏔️ 多租戶系統使用指南

## 📝 系統架構說明

這是一個 **B2B SaaS 多租戶滑雪預訂系統**，支持多個滑雪學校共用同一套系統，每個學校的資料完全隔離。

---

## 🎯 URL 結構

### 新的 URL 結構（已實現）
```
http://localhost:8000/                      ← Landing Page（選擇客戶）
http://localhost:8000/booking/snowland/     ← 雪域創遊的預訂頁面
http://localhost:8000/booking/snowland/payment/  ← 雪域創遊的付款頁面
http://localhost:8000/control/snowland/     ← 雪域創遊的管理後台
http://localhost:8000/api/snowland/xxx      ← 雪域創遊的 API
```

### 為什麼是 `/booking/<client_code>/` 而不是 `/<client_code>/booking/`？

✅ **優點**：
1. 更符合 REST 設計風格
2. 前端路由更容易配置（例如 React Router 的 `/booking/*`）
3. 登入後可以透過 session 自動帶入 client_code，URL 可以簡化

---

## 🔧 技術實現

### 1. **TenantMiddleware（自動識別租戶）**

Middleware 會按照以下優先順序獲取 `client_code`：

1. **從 URL 中提取**：`/booking/<client_code>/` → 提取 `snowland`
2. **從 Session 獲取**：如果用戶已登入，從 `request.session['client_code']` 獲取
3. **從 GET 參數獲取**：`/booking/?client=snowland`

一旦獲取到 `client_code`，會自動：
- 查詢 `Client` 模型
- 注入到 `request.tenant`
- 存入 `session`（下次就不用再提供）

### 2. **@require_tenant 裝飾器（自動注入）**

在 view 函數上使用裝飾器，不用每次手動處理：

```python
from booking.decorators import require_tenant

@require_tenant
def my_view(request, client_code):
    # request.tenant 已經自動注入
    # client_code 參數也自動傳入
    tenant = request.tenant  # Client 物件
    coaches = Coach.objects.filter(client=tenant)
    ...
```

### 3. **登入流程自動記住 client_code**

當用戶登入時，系統會：
1. 從 URL 或 GET 參數獲取 `client_code`
2. 存入 `session['client_code']`
3. 之後所有請求都自動使用該 client

---

## 🚀 部署步驟

### 步驟 1：運行 Migrations

```bash
# 進入專案目錄
cd /mnt/c/FlashFalconSystem/snowland

# 激活虛擬環境（如果有）
source venv/bin/activate

# 運行 migrations
python manage.py makemigrations
python manage.py migrate
```

### 步驟 2：創建測試客戶

進入 Django shell：
```bash
python manage.py shell
```

創建客戶：
```python
from Client.models import Client

# 創建「雪域創遊」客戶
snowland = Client.objects.create(
    name='雪域創遊',
    internal_code='snowland',  # 這是 URL 中的 client_code
    is_active=True,
    sales='張三',
    program='標準方案'
)

# 創建另一個測試客戶
test_client = Client.objects.create(
    name='測試滑雪學校',
    internal_code='testski',
    is_active=True,
    sales='李四',
    program='進階方案'
)

print("客戶創建完成！")
```

### 步驟 3：關聯現有資料到客戶

```python
from Client.models import Client
from Coach.models import Coach
from Resorts.models import Resorts
from booking.models import ReservationGroup
from Coursekit.models import CourseCategory

# 獲取「雪域創遊」客戶
snowland = Client.objects.get(internal_code='snowland')

# 將所有現有資料關聯到這個客戶
Coach.objects.filter(client__isnull=True).update(client=snowland)
Resorts.objects.filter(client__isnull=True).update(client=snowland)
ReservationGroup.objects.filter(client__isnull=True).update(client=snowland)
CourseCategory.objects.filter(client__isnull=True).update(client=snowland)

print("資料關聯完成！")
```

### 步驟 4：啟動服務器並測試

```bash
# 啟動 Django
python manage.py runserver
```

然後在瀏覽器訪問：

1. **Landing Page**：http://localhost:8000/
   - 應該看到客戶列表

2. **雪域創遊預訂頁面**：http://localhost:8000/booking/snowland/
   - 應該進入預訂系統
   - 只能看到雪域創遊的教練、雪場、課程

3. **測試租戶隔離**：http://localhost:8000/booking/testski/
   - 應該看到空的資料（因為還沒為這個客戶添加資料）

4. **測試錯誤客戶**：http://localhost:8000/booking/wrongclient/
   - 應該看到 404 錯誤

---

## 🧪 測試多租戶隔離

### 測試 1：URL 中指定 client_code

```bash
# 訪問雪域創遊
curl http://localhost:8000/booking/snowland/

# 訪問測試滑雪學校
curl http://localhost:8000/booking/testski/
```

### 測試 2：Session 自動記住 client_code

1. 訪問：`http://localhost:8000/booking/snowland/`
2. 登入
3. 之後訪問 `/booking/api/coaches/` 時，系統會自動使用 `snowland`

### 測試 3：GET 參數指定 client

```bash
# 使用 GET 參數
http://localhost:8000/booking/?client=snowland
```

---

## 📊 資料模型關聯

以下模型都已經有 `client` 外鍵：

- ✅ `Coach.client` → 教練屬於哪個客戶
- ✅ `Resorts.client` → 雪場屬於哪個客戶
- ✅ `ReservationGroup.client` → 預訂群組屬於哪個客戶
- ✅ `CourseCategory.client` → 課程大類屬於哪個客戶

所有查詢都會自動過濾：
```python
# 自動過濾當前租戶的教練
coaches = Coach.objects.filter(client=request.tenant)

# 自動過濾當前租戶的雪場
resorts = Resorts.objects.filter(client=request.tenant)
```

---

## 🔐 安全性

### 資料隔離保證

1. **Middleware 層級隔離**：每個請求都會檢查並注入正確的 `tenant`
2. **View 層級過濾**：所有查詢都加上 `client=request.tenant` 過濾
3. **裝飾器保護**：`@require_tenant` 確保沒有 tenant 的請求被拒絕
4. **Session 綁定**：登入後 client_code 綁定到 session，無法跨租戶訪問

### 防止跨租戶訪問

即使用戶知道另一個客戶的 `reservation_group_pk`，也無法訪問：

```python
# 這個查詢會自動加上 client 過濾
group = ReservationGroup.objects.filter(
    pk=reservation_group_pk,
    client=request.tenant  # 強制過濾
).first()
```

---

## 🎨 前端配合（React）

### 方案 1：URL 中帶 client_code（推薦）

前端訪問：
```javascript
// 從 URL 中獲取 client_code
const clientCode = window.location.pathname.split('/')[2] // 從 /booking/snowland/ 提取 snowland

// API 調用
fetch(`/booking/${clientCode}/api/coaches/`)
```

### 方案 2：使用 Session（更簡單）

1. 用戶首次訪問：`http://localhost:3000/booking/snowland/`
2. 登入後，後端 session 記住 `client_code=snowland`
3. 之後所有 API 調用都自動使用該 client：
   ```javascript
   // 不需要在 URL 中帶 client_code
   fetch('/booking/api/coaches/')  // 後端會從 session 獲取
   ```

---

## ⚠️ 注意事項

### 1. **快取鍵需要包含 client_code**

```python
# ❌ 錯誤：所有租戶共用快取
cache_key = 'course_data'

# ✅ 正確：每個租戶獨立快取
cache_key = f'course_data_{client_code}'
```

### 2. **URL 生成需要包含 client_code**

```python
# ❌ 錯誤
next_url = '/booking/payment/'

# ✅ 正確
next_url = f'/booking/{client_code}/payment/'
```

### 3. **所有模型查詢都要過濾 client**

```python
# ❌ 錯誤：會看到所有客戶的教練
coaches = Coach.objects.all()

# ✅ 正確：只看到當前客戶的教練
coaches = Coach.objects.filter(client=request.tenant)
```

---

## 📞 常見問題

### Q1: 我訪問 `http://localhost:3000/` 還是看到舊的登入頁面？

A: 這是因為 port 3000 是前端 React 應用，後端在 port 8000。你需要：
- 訪問 `http://localhost:8000/` 來看 Django 的 Landing Page
- 或者修改前端 React 也支持多租戶

### Q2: 如何讓前端也支持多租戶？

A: 需要修改前端路由：
```typescript
// src/App.tsx
<Routes>
  <Route path="/booking/:clientCode/*" element={<BookingApp />} />
  <Route path="/payment/:clientCode" element={<PaymentPage />} />
</Routes>
```

### Q3: 登入後如何自動帶入 client_code？

A: 系統已經實現了！只要用戶首次訪問時指定 client_code，登入後會自動存入 session。

### Q4: 如何為不同客戶設定不同的品牌顏色？

A: 使用 `Client` 模型中的 `PageColor` 關聯：
```python
# 設定雪域創遊的顏色
from Client.models import Client, PageInfo, PageColor

client = Client.objects.get(internal_code='snowland')
page = PageInfo.objects.get(page_sid='booking')

PageColor.objects.create(
    client=client,
    page=page,
    color_primary='#1E40AF',
    color_secondary='#3B82F6'
)
```

---

## ✅ 總結

### 已完成的功能

- ✅ URL 結構：`/booking/<client_code>/`
- ✅ TenantMiddleware：自動識別和注入租戶
- ✅ @require_tenant 裝飾器：自動處理租戶邏輯
- ✅ Session 記憶：登入後自動記住 client_code
- ✅ Landing Page：選擇客戶頁面
- ✅ 資料隔離：所有查詢都過濾租戶

### 下一步（可選）

- ⬜ 修改 Control app 的所有 views 使用裝飾器
- ⬜ 修改 API views 使用裝飾器
- ⬜ 修改前端 React 支持多租戶路由
- ⬜ 添加租戶特定的品牌設定功能

---

**現在你可以開始測試了！🚀**
