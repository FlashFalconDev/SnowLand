/**
 * 訂單管理 API
 */
import adminApi from './axios'

export type ReservationStatus =
  | 'created' | 'cancelled' | 'auto_assigned' | 'manually_assigned'
  | 'pending_coach_confirmation' | 'completed' | 'auto_assignment_failed'
  | 'manual_assignment_needed' | 'form_filled' | 'deleted'
export type PaymentStatus = 'unpaid' | 'pending' | 'paid' | 'expired' | 'refunded'

export interface OrderBooking {
  id: number
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
  ability_level: string
  preferred_coach_id: number | null
  preferred_coach: string | null
  is_preferred_coach: boolean
  language: string
  equipment?: string | null
  equipment_assistance_time_label?: string
  number_of_people: number
  status: ReservationStatus
  total_fee: number
  available_coaches?: OrderAvailableCoach[]
  bookings: OrderBooking[]
}

export interface Order {
  id: number
  sn: string
  name: string
  user: number | null
  user_name: string
  user_email: string
  reservations: OrderReservation[]
  total_fee: number
  payment_status: PaymentStatus
  payment_method: string
  bank_account?: string | null
  created_at: string
  order_number?: string
  campus?: number | null
  campus_name?: string
  marketing_source?: string
  marketing_source_detail?: string
  line_group_url?: string
  revisions?: { id: number; version: number; change_type: string; difference_amount: number; reason: string; created_at: string }[]
  cancellation?: { id: number; status: string; reason: string; refund_amount: number; refund_percent: string; handling_fee_percent: string } | null
}

interface ListResp {
  code: number; msg: string
  data: { list: Order[]; total: number; page?: number; page_size?: number; total_pages?: number }
}
interface ActionResp { code: number; msg: string }

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

/** 舊接口：向後相容保留，只取第一頁，避免誤抓全部訂單 */
export async function fetchOrders(): Promise<Order[]> {
  const page = await fetchOrdersPaged({ page: 1, page_size: 10 })
  return page.items
}

export async function fetchOrder(id: number): Promise<Order> {
  const res = (await adminApi.get(`/orders/${id}/`)) as any
  return res.data || res
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
    reservation_updates?: { reservation_id: number; coach_id: number | null }[]
    booking_updates?: { booking_id: number; date: string; start_time: string; end_time: string }[]
  }
): Promise<{ code: number; msg: string }> {
  const res = (await adminApi.put(`/orders/${id}/`, payload)) as unknown as ActionResp
  return res
}

export async function previewOrderRefund(id: number): Promise<{ original_amount: number; days_before: number; refund_percent: number; handling_fee_percent: number; refund_amount: number }> {
  const res = await adminApi.get(`/orders/${id}/refund-preview/`) as any
  return res.data
}

export async function requestOrderCancellation(id: number, payload: { reason: string; reason_note?: string; refund_bank?: { bank_name: string; account_number: string; account_holder: string } }): Promise<void> {
  await adminApi.post(`/orders/${id}/cancel/`, payload)
}

export async function processOrderCancellation(cancellationId: number, status: 'approved' | 'rejected' | 'refunded'): Promise<void> {
  await adminApi.post(`/cancellations/${cancellationId}/process/`, { status })
}
