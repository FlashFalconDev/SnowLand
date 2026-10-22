/**
 * 訂單管理 API
 */
import adminApi from './axios'
import type { OrderSettlement } from '../../components/booking/SettlementSummary'

export type ReservationStatus =
  | 'created' | 'cancelled' | 'auto_assigned' | 'manually_assigned'
  | 'pending_coach_confirmation' | 'completed' | 'auto_assignment_failed'
  | 'manual_assignment_needed' | 'form_filled' | 'deleted'
export type PaymentStatus = 'unpaid' | 'pending' | 'paid' | 'expired' | 'refunded'

export interface OrderBooking {
  id: number
  course_template_id?: number | null
  date: string
  start_time: string
  end_time: string
  course_name: string
}

export interface OrderAvailableCoach {
  id: number
  name: string
  availability_status: 'active' | 'passive'
  requires_confirmation: boolean
}

export interface OrderReservation {
  id: number
  resort: string
  course_type: string
  course_template_id?: number | null
  ability_level: string
  preferred_coach_id: number | null
  preferred_coach: string | null
  is_preferred_coach: boolean
  shared_course_class_id?: number | null
  shared_class_status?: 'collecting' | 'ready' | 'cancelled' | null
  language: string
  equipment?: string | null
  equipment_assistance_time_label?: string
  number_of_people: number
  status: ReservationStatus
  total_fee: number
  available_coaches?: OrderAvailableCoach[]
  bookings: OrderBooking[]
}

export interface OrderRevisionSnapshot {
  order_number?: string
  reservations?: {
    id: number
    resort_id?: number | null
    resort_name?: string
    course_type_name?: string
    course_template_name?: string
    coach_id?: number | null
    coach_name?: string
    people?: number
    payable?: number
    bookings?: { id: number; date: string; start_time: string; end_time: string; course_name?: string }[]
  }[]
}

export interface Order {
  settlement?: OrderSettlement
  received_settlement?: OrderSettlement | null
  id: number
  sn: string
  name: string
  user: number | null
  user_name: string
  user_email: string
  booking_contact?: { name: string; email: string; phone: string; messenger_type: string; messenger_id: string }
  reservations: OrderReservation[]
  total_fee: number
  payment_status: PaymentStatus
  amendment_balance?: { amount: number; statuses: string[];settlement?:{currency:'JPY';amount:number} } | null
  payment_method: string
  bank_account?: string | null
  created_at: string
  order_number?: string
  campus?: number | null
  campus_name?: string
  marketing_source?: string
  marketing_source_detail?: string
  line_group_url?: string
  line_group_qr_url?: string
  revisions?: { id: number; version: number; change_type: string; difference_amount: number; reason: string; created_at: string; snapshot?: OrderRevisionSnapshot }[]
  cancellation?: { id: number; status: string; reason: string; refund_amount: number | null; refund_percent: string; handling_fee_percent: string; calculation_mode: 'auto' | 'rule' | 'manual'; selected_rule_days_before: number | null; requires_cash_review:boolean;actual_received_amount:number|null;cash_review_note:string;currency_snapshot?:CancellationSettlement;refund_bank_name?:string;refund_account_number?:string;refund_account_holder?:string;refund_overseas_details?:string } | null
}

interface ListResp {
  code: number; msg: string
  data: { list: Order[]; total: number; page?: number; page_size?: number; total_pages?: number }
}
interface ActionResp { code: number; msg: string }

export interface CampusManagerOrder {
  id: number
  sn: string
  campus_name: string
  student_alias: string
  number_of_people: number
  course_dates: string[]
  sessions: {
    date: string
    start_time: string
    end_time: string
    course_type: string
    number_of_people: number
    ability_level: string
    age_ranges: string[]
  }[]
}

export interface OrdersQuery {
  page?: number
  page_size?: number
  search?: string
  status?: string
  payment_status?: string
}

export interface OrdersPage {
  items: Order[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export async function fetchOrdersPaged(query: OrdersQuery = {}): Promise<OrdersPage> {
  const params: Record<string, string | number> = {
    page: query.page ?? 1,
    page_size: query.page_size ?? 10,
  }
  if (query.search) params.search = query.search
  if (query.status) params.status = query.status
  if (query.payment_status) params.payment_status = query.payment_status

  const res = (await adminApi.get('/orders/', { params })) as unknown as ListResp
  return {
    items: res.data?.list || [],
    total: res.data?.total || 0,
    page: res.data?.page || 1,
    page_size: res.data?.page_size || 10,
    total_pages: res.data?.total_pages || 0,
  }
}

/** 校區主管專用：只讀近期課程摘要。 */
export async function fetchCampusManagerOrdersPaged(query: Pick<OrdersQuery, 'page' | 'page_size' | 'search'> = {}) {
  const res = (await adminApi.get('/orders/', { params: {
    page: query.page ?? 1,
    page_size: query.page_size ?? 10,
    ...(query.search ? { search: query.search } : {}),
  } })) as unknown as {
    data: { list: CampusManagerOrder[]; total: number; page: number; total_pages: number }
  }
  return res.data
}

/** 舊接口：向後相容保留，只取第一頁，避免誤抓全部訂單 */
export async function fetchOrders(): Promise<Order[]> {
  const page = await fetchOrdersPaged({ page: 1, page_size: 10 })
  return page.items
}

export async function fetchOrder(id: number): Promise<Order> {
  const res = (await adminApi.get(`/orders/${id}/`)) as any
  return res.data || res
}

export async function fetchGuestPaymentLink(id: number): Promise<{ path: string; valid_days: number }> {
  const response = (await adminApi.get(`/orders/${id}/payment-link/`)) as unknown as {
    code: number; data: { path: string; valid_days: number }
  }
  return response.data
}

/**
 * 編輯訂單：指派教練、改付款狀態、可選觸發 AI 排課
 * action='save' → 只儲存變更
 * action='schedule' → 儲存後呼叫 AI 排課
 */
export async function updateOrder(
  id: number,
  payload: {
    action: 'save' | 'schedule'
    payment_status?: PaymentStatus
    payment_currency?: 'TWD' | 'JPY'
    payment_received_amount?: number
    reservation_updates?: { reservation_id: number; coach_id: number | null }[]
    booking_updates?: { booking_id: number; date: string; start_time: string; end_time: string }[]
  }
): Promise<{ code: number; msg: string }> {
  const res = (await adminApi.put(`/orders/${id}/`, payload)) as unknown as ActionResp
  return res
}

export interface OrderAmendmentCourse {
  booking_id: number; template_id: number; date: string; start_time: string; end_time: string
}
export interface OrderAmendmentItem {
  reservation_id: number
  number_of_people?: number
  language?: 'zh' | 'en' | 'yue'
  equipment?: 'rentWithoutyourself' | 'ownWithoutAssistance' | 'assistDuringCourse' | 'purchaseAssistanceTime' | null
  equipment_assistance_time_slot_id?: number | null
  is_preferred_coach?: boolean; preferred_coach_id?: number | null
  discount_amount?: number
  retained_member_ids?: number[]
  ability_level_counts?: Record<string, number>
  courses: OrderAmendmentCourse[]
}
export interface OrderAmendmentQuote {
  settlement?: AmendmentSettlement
  previous_total: number; new_total: number; difference_amount: number
  status: 'preview_only'; notice: string; quote_token: string
  items: {
    reservation_id: number; number_of_people: number; language: string; equipment: string | null
    is_preferred_coach: boolean; preferred_coach_id: number | null
    courses: (OrderAmendmentCourse & { template_name: string })[]
    course_fee: number; coach_fee: number; language_fee: number; equipment_fee: number; discount_amount: number
    previous_amount: number; new_amount: number; price_basis_changed: boolean
    participant_review_required: boolean; discount_changed: boolean
    waiver_resign_count: number; insurance_recheck_count: number
    retained_member_ids: number[] | null; ability_level_counts: Record<string, number> | null
  }[]
}
// This endpoint only previews; it never updates an order or initiates payment.
export async function previewOrderAmendment(orderId: number, changes: OrderAmendmentItem[]): Promise<OrderAmendmentQuote> {
  const result = await adminApi.post(`/orders/${orderId}/amendment-quote/`, { changes }) as unknown as { data: OrderAmendmentQuote }
  return result.data
}

export interface OrderAmendmentConfirmation {
  changes: OrderAmendmentItem[]
  quote_token: string
  request_key: string
  reason: string
  confirmed: boolean
  reschedule?: boolean
}
export interface OrderAmendmentEditorItem extends OrderAmendmentItem {
  resort: string; course_type: string; blocked_reason: string
  members: { id: number; name: string }[]
  templates: { id: number; name: string; is_active: boolean; duration_hours: number; minimum_group_size: number; max_capacity: number; sessions: { start_time: string; end_time: string }[] }[]
  coaches: { id: number; name: string; customer_selectable: boolean }[]
  equipment_slots: { id: number; name: string }[]
}
export async function fetchOrderAmendmentOptions(orderId: number): Promise<{ items: OrderAmendmentEditorItem[] }> {
  const result = await adminApi.get(`/orders/${orderId}/amendment-options/`) as unknown as { data: { items: OrderAmendmentEditorItem[] } }
  return result.data
}
export interface OrderAmendmentResult {
  settlement?: AmendmentSettlement
  id: number; version: number; previous_total: number; new_total: number
  difference_amount: number; balance_amount: number
  status: 'included_in_order' | 'no_difference' | 'topup_due' | 'topup_reported' | 'refund_account_due' | 'refund_due' | 'settled' | 'superseded' | 'cancelled'
  participant_changes: Record<string, { retained_ids: number[]; archived_ids: number[]; created_ids: number[] }>
  bank_snapshot: Record<string, string>
  duplicate: boolean; notification_status: string; notice: string
  notification?: {in_app:string;email:string;local_test:boolean}
}
// The caller keeps the same request_key for retries; this does not collect or refund money.
export async function confirmOrderAmendment(orderId: number, payload: OrderAmendmentConfirmation): Promise<OrderAmendmentResult> {
  const result = await adminApi.post(`/orders/${orderId}/amendment-confirm/`, payload) as unknown as { data: OrderAmendmentResult }
  return result.data
}

export interface AmendmentSettlement {
  currency:'JPY';base_currency:'TWD';rate:string;locked_at?:string|null
  previous_total:number;new_total:number;difference_amount:number;balance_amount:number
}
export interface AmendmentBalance {
  settlement?: AmendmentSettlement
  id: number; version: number; previous_total: number; new_total: number; difference_amount: number; balance_amount: number
  status: OrderAmendmentResult['status']; updated_at: string; settled_at: string | null
  bank_snapshot: Record<string,string>; refund_bank: Record<string,string>; topup_reference: string; review_message: string
  notification?: {in_app:string;email:string;local_test:boolean}
  events: { action: string; previous_status: string; status: string; note: string; reference: string; created_at: string; actor: string }[]
}
export interface AmendmentBalanceAction {
  currency?:'TWD'|'JPY';expected_amount?:number
  amendment_id: number; expected_updated_at: string; request_key: string
  action: 'confirm_topup' | 'reject_topup' | 'confirm_refund'; note: string; confirmed?: boolean
}
export async function fetchAmendmentBalances(orderId:number):Promise<{items:AmendmentBalance[]}> {
  const result=await adminApi.get(`/orders/${orderId}/amendment-balances/`) as unknown as {data:{items:AmendmentBalance[]}}
  return result.data
}
export async function processAmendmentBalance(orderId:number,payload:AmendmentBalanceAction):Promise<{msg:string;data:AmendmentBalance}> {
  return await adminApi.post(`/orders/${orderId}/amendment-balances/`,payload) as unknown as {msg:string;data:AmendmentBalance}
}

export async function completeOrderCourse(orderId: number, reservationId: number): Promise<{ code: number; msg: string }> {
  return await adminApi.post(`/orders/${orderId}/complete-course/`, { reservation_id: reservationId }) as unknown as ActionResp
}

export async function saveClassGroupLink(orderId: number, line_group_url: string): Promise<ActionResp> {
  return await adminApi.post(`/orders/${orderId}/class-group-link/`, { line_group_url }) as unknown as ActionResp
}

export async function saveClassGroupQR(orderId: number, file: File | null, onProgress: (percent: number) => void): Promise<{ msg: string; data: { line_group_qr_url: string } }> {
  if (!file) return await adminApi.delete(`/orders/${orderId}/class-group-qr/`) as any
  const form = new FormData(); form.append('file', file)
  return await adminApi.post(`/orders/${orderId}/class-group-qr/`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: event => onProgress(event.total ? Math.min(99, Math.round(event.loaded * 100 / event.total)) : 0),
  }) as any
}

export interface CancellationSettlement { currency:'JPY';base_currency:'TWD';rate:string;locked_at?:string|null;original_amount:number;refund_amount:number|null;actual_received_amount?:number;cash_review?:{accounting_mode:'original_receipt_ratio';actual_received_amount:number;refund_amount:number;actual_received_base_amount:number;refund_base_amount:number} }
export interface RefundPreview { settlement?:CancellationSettlement;original_amount: number; days_before: number; refund_percent: number; handling_fee_percent: number; refund_amount: number | null; requires_cash_review:boolean; available_rules: { days_before: number; refund_percent: number }[] }
export async function previewOrderRefund(id: number): Promise<RefundPreview> {
  const res = await adminApi.get(`/orders/${id}/refund-preview/`) as any
  return res.data
}

export async function requestOrderCancellation(id: number, payload: { reason: string; reason_note?: string; refund_bank?: { bank_name: string; account_number: string; account_holder: string;overseas_details?:string }; selected_rule_days_before?: number; manual_refund_amount?: number;currency?:'JPY';expected_refund_amount?:number|null }): Promise<void> {
  await adminApi.post(`/orders/${id}/cancel/`, payload)
}

export interface CancellationCashReview { actual_received_amount:number;refund_amount:number;cash_review_note:string;confirmed_received:boolean }
export type CancellationReviewPayload=Partial<CancellationCashReview>&{currency?:'JPY';expected_refund_amount?:number|null;confirmed_refund?:boolean;actual_received_currency_amount?:number;refund_currency_amount?:number}
export async function processOrderCancellation(cancellationId: number, status: 'approved' | 'rejected' | 'refunded', review?:CancellationReviewPayload): Promise<void> {
  await adminApi.post(`/cancellations/${cancellationId}/process/`, { status, ...review })
}
