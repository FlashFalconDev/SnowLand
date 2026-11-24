# SnowLand 訂單軟刪除

## 管理入口

平台管理者可在 Django [/admin/](/admin/) 選擇「封存狀態」，可查有效紀錄、含已刪除或僅已刪除。此路由在 `snowland/snowland/urls.py` 掛接 `admin.site.urls`。Django AdminSite 先要求使用者啟用且具 `is_staff`，封存篩選另要求 `is_superuser`。封存明細可讀，編輯和刪除入口關閉。既有訂單管理頁仍依 Django 權限供有效資料使用，新註冊的封存模型僅供平台管理者查看。

`/:clientCode/console/` 的總部管理員（`hq_admin`）由 `Control.TenantStaffMembership` 授權存取該租戶及其校區。Console 的列表、詳情、匯出及操作統一使用有效訂單，即使由平台管理者登入 Console 亦同。`/control/` 是舊管理介面，平台限定的部分路由另由 `Control/legacy_access.py` 守門。會員及教練一般頁面的封存訂單會隱藏，原相簿、簽名及專用檔案入口延續既有授權。

## 批次指令

在 `snowland/` 執行。以下示例使用隔離環境及合成租戶。

```powershell
python manage.py soft_delete_tenant_orders --client-code archive-fixture --dry-run
python manage.py soft_delete_tenant_orders --client-code archive-fixture --apply --confirm-client-code archive-fixture --expected-plan-digest <digest> --actor-id <platform-user-id>
python manage.py soft_delete_tenant_orders --client-code archive-fixture --restore --batch <uuid>
```

1. **預覽**列出 24 個模型的租戶總列、已標、待標、保留、歸戶矛盾及在途列數，附 `plan_digest`。手動無訂單通知及訂單租戶未知的通知另列。代碼必須完整且區分大小寫。
2. **標記**由啟用中的平台管理者 ID 留痕。指令鎖定租戶與相關資料列，在交易內重新核對摘要。歸戶矛盾、在途確認付款、已簽發且未付的藍新表單或寄送中的通知會讓整批停止。成功時回傳 UUID，原來已標記的列維持其既有批次。客人成班只有在標記後無有效訂單時納入，校方預開班保留。
3. **還原**須提供相同租戶及該次 UUID，核對精確的列、旗標、標記時間與操作人，並檢查薪資期間重疊及既有業務唯一鍵。成功後重新計算有效資料，保存還原時間。可加 `--actor-id` 記錄執行還原的平台管理者。
4. **營運結果**是資料可見性與帳務彙總更新。既有金流紀錄及附件持續保存。已驗證的晚到藍新回呼若指向封存單，回 409 並留下供核對的訂單識別，付款與點數維持原樣。薪資與獎金草稿刪除會封存明細並留批次，同一期間或月份須還原原單。已封存共班仍占用既有唯一時段。

## 重算與歷史資料

- 會員點數由人工覆核的 `previous_points`、期初基線及有效流水組成，紅利餘額保留正負值。第一次重算以原帳戶值與全列流水差額推回基線。新結帳、收付款或退款產生的點數流水在帳戶鎖下更新。
- 新結帳以每次結帳 UUID、折扣規則 ID 和套用的預約列記錄使用量。同一結帳對同一規則計一次，只要仍有有效預約即保留該次使用量。規則移除後仍保留結帳時的規則 ID。一般結帳、標記與還原使用共同重算方式。
- 舊折扣列只有文字和金額，無法重建原始購物車。保留各規則的舊使用基線，當租戶可辨識的舊折扣預約均封存時，從有效用量排除該基線。部分舊單保留的情形仍使用原基線，需由帳務確認後才能精確拆分。
- 批次提交後清除該租戶的課程快取。營運 Console 使用經有效條件計算的 API 回應，原有畫面上的舊付款或訂單連結會依 API 回到缺件／找不到的狀態。

## 資料庫變更

`booking/0043_order_soft_delete.py` 與 `Coach/0025_order_soft_delete.py` 對下列各表新增相同三欄。`is_deleted` 為有索引的布林值，舊列是 `False`。`deleted_at` 可為空。`deleted_by_id` 是可為空的使用者 FK，Django 外鍵刪除策略為 `SET_NULL`。表的既有業務唯一約束保留，**未改薪資／獎金唯一約束**。

| App | 模型 | 新增複合索引與欄位 |
|---|---|---|
| `booking` | `ReservationGroup` | `sl_group_client_live_date` (client, is_deleted, created_at) |
| `booking` | `SharedCourseClass` | `sl_class_client_live_date` (client, is_deleted, campus, date) |
| `booking` | `Reservation` | `sl_res_group_live_status` (group, is_deleted, status) |
| `booking` | `Booking` | `sl_booking_res_live_date` (reservation, is_deleted, date) |
| `booking` | `MemberDetail` | `sl_member_res_live_active` (reservation, is_deleted, is_active) |
| `booking` | `MemberCourseDocumentRevision` | `sl_document_member_live` (member, is_deleted) |
| `booking` | `ParticipantInvitation` | `sl_invite_member_live` (member, is_deleted) |
| `booking` | `Payment` | `sl_payment_group_live_status` (reservation_group, is_deleted, status)；`sl_payment_live_expiry` (is_deleted, status, expires_at) |
| `booking` | `CancellationRequest` | `sl_cancel_group_live_status` (group, is_deleted, status) |
| `booking` | `OrderRevision` | `sl_revision_group_live_ver` (group, is_deleted, version) |
| `booking` | `OrderAmendment` | `sl_amend_group_live_status` (group, is_deleted, status) |
| `booking` | `OrderAmendmentEvent` | `sl_event_amend_live` (amendment, is_deleted) |
| `booking` | `NotificationDelivery` | `sl_delivery_live_status_date` (is_deleted, status, scheduled_at) |
| `booking` | `OrderLoyalty` | `sl_order_loyalty_account_live` (account, is_deleted) |
| `booking` | `MemberLoyaltyEntry` | `sl_loyalty_account_live_date` (account, is_deleted, created_at) |
| `booking` | `CourseEvaluation` | `sl_eval_booking_live` (booking, is_deleted)；`sl_eval_member_live` (member, is_deleted) |
| `Coach` | `PayrollStatement` | `sl_payroll_campus_live_period` (campus, is_deleted, period_start) |
| `Coach` | `PayrollLine` | `sl_payline_stmt_live_type` (statement, is_deleted, line_type) |
| `Coach` | `StaffIncentiveStatement` | `sl_incentive_campus_live_month` (campus, is_deleted, month) |
| `Coach` | `StaffIncentiveLine` | `sl_incline_stmt_live_type` (statement, is_deleted, line_type)；`sl_incline_source_live` (source_line, is_deleted) |
| `Coach` | `VehicleTrip` | `sl_trip_campus_live_purpose` (campus, is_deleted, purpose, starts_at)；`sl_trip_vehicle_live_status` (vehicle, is_deleted, status, starts_at) |
| `Coach` | `VehicleExpense` | `sl_expense_trip_live` (trip, is_deleted) |
| `Coach` | `VehicleCharge` | `sl_charge_coach_live_month` (coach, is_deleted, first_month) |
| `Coach` | `VehicleDeduction` | `sl_deduct_stmt_live` (statement, is_deleted)；`sl_deduct_charge_live` (charge, is_deleted) |

| Migration | 變更 |
|---|---|
| `Coursekit/0021_order_usage_rollups.py` | `DiscountCode.legacy_used_count` 為可空的非負整數，保存可辨識的舊使用基線。 |
| `booking/0044_order_usage_rollups.py` | `MemberLoyaltyAccount.opening_points`、`opening_rewards` 為可空的有號大整數。新表 `OrderDiscountUsage` 保存 `id`、預約 FK `reservation_id`、數值 `rule_id` 和 UUID `checkout_key`，唯一鍵 `unique_reservation_discount_use` 為 (reservation_id, rule_id)，索引 `discount_use_checkout_idx` 為 (rule_id, checkout_key)。 |
| `booking/0045_tenant_order_archive_batch.py` | 新表 `TenantOrderArchiveBatch` 保存 UUID `id`、`client_id`、`actor_id`、`deleted_at`、`plan_digest`、`targets`、`restored_at`、`restored_by_id`。以交易內的 PK 清單界定單批還原範圍。 |

`snowland.test_settings` 以 SQLite 測試日常查詢與交易。檢查 migration 狀態時可在該設定中暫時啟用 migration graph 並執行 `makemigrations --check --dry-run`，完整套用實際 migration 則使用獨立的 MySQL 8.0。批次演練請使用合成資料。
