/**
 * 雜項 API：訂單寄信、客戶權限、雪場批量、教練自身視角
 */
import adminApi from './axios'

interface Resp { code: number; msg: string; data?: any }

// ==================== 訂單寄信 ====================
export async function sendOrderEmail(
  orderId: number,
  payload: { recipient_email: string; subject: string; message: string }
): Promise<Resp> {
  const res = (await adminApi.post(`/orders/${orderId}/send-email/`, payload)) as unknown as Resp
  return res
}

// ==================== 客戶權限 ====================
export async function updateCustomerPermission(
  userId: number,
  payload: { is_superuser?: boolean; is_manager: boolean; is_coach: boolean; permissions?: string[] }
): Promise<Resp> {
  const res = (await adminApi.post(`/customers/${userId}/permission/`, payload)) as unknown as Resp
  return res
}

// ==================== 員工權限管理 ====================
export interface StaffMember {
  id: number
  username: string
  email: string
  name: string
  is_member?: boolean
  reservation_count?: number
  is_superuser: boolean
  is_manager: boolean
  is_coach: boolean
  permissions?: string[]
  has_coach_record: boolean
  coach_id: number | null
  coach_name: string | null
  date_joined: string
  last_login: string | null
}

export async function fetchStaff(q?: string): Promise<StaffMember[]> {
  const res = (await adminApi.get('/staff/', { params: q ? { q } : {} })) as any
  return res.data?.list || []
}

// ==================== 雪場費用批量 ====================
export async function bulkUpdateResortFees(
  resortId: number,
  fees: { fee_type: string; price: number; is_active?: boolean; description?: string }[]
): Promise<Resp> {
  const res = (await adminApi.post(`/resorts/${resortId}/bulk-fees/`, { fees })) as unknown as Resp
  return res
}

// ==================== 教練視角 ====================
export interface CoachPendingItem {
  id: number
  group_id: number
  user_name: string
  resort: string
  course_type: string
  ability_level: string
  language: string
  number_of_people: number
  total_fee: number
  bookings: { date: string; start_time: string; end_time: string }[]
}

export async function fetchCoachPending(): Promise<CoachPendingItem[]> {
  const res = (await adminApi.get('/coach/pending/')) as any
  return res.data?.list || []
}

export async function coachConfirm(reservationId: number, action: 'accept' | 'reject'): Promise<Resp> {
  const res = (await adminApi.post(`/coach/confirm/${reservationId}/`, { action })) as unknown as Resp
  return res
}

// ==================== 教練我的課程 ====================
export interface MyCourse {
  id: number
  group_id: number
  user_name: string
  resort: string
  course_type: string
  ability_level: string
  language: string
  number_of_people: number
  status: string
  total_fee: number
  is_preferred_coach?: boolean
  bookings: { id: number; date: string; start_time: string; end_time: string; is_scheduled: boolean }[]
  mdt_add: string
}

export async function fetchMyCourses(params?: { status?: string; date_from?: string; date_to?: string }): Promise<MyCourse[]> {
  const res = (await adminApi.get('/coach/my-courses/', { params })) as any
  return res.data?.list || []
}

// ==================== 教練我的月曆 ====================
export interface MyCalendarBooking {
  id: number
  reservation_id?: number
  group_id?: number
  date: string
  start_time: string
  end_time: string
  course_name: string
  course_type?: string
  ability_level?: string
  language?: string
  language_label?: string
  equipment?: string
  equipment_label?: string
  is_preferred_coach?: boolean
  coach_name?: string
  user_name: string
  resort: string
  number_of_people: number
  status: string
  is_scheduled: boolean
  event_type?: 'course' | 'equipment_assistance' | string
  equipment_assistance_time_label?: string
  linked_course_date?: string
}

export async function fetchMyCalendar(params?: { start?: string; end?: string }): Promise<MyCalendarBooking[]> {
  const res = (await adminApi.get('/coach/my-calendar/', { params })) as any
  return res.data?.list || []
}

// ==================== 教練我的請假 ====================
export interface MyLeave {
  id: number
  start_date: string
  end_date: string
  leave_days: number
  reason: string
  status: 'pending' | 'approved' | 'rejected' | 'cancelled'
  processing_result: string
  reviewed_at: string | null
  created_at: string
  affected_count: number
}

export async function fetchMyLeaves(): Promise<MyLeave[]> {
  const res = (await adminApi.get('/coach/my-leaves/')) as any
  return res.data?.list || []
}

export async function applyLeave(payload: { start_date: string; end_date: string; reason: string }): Promise<Resp> {
  const res = (await adminApi.post('/coach/apply-leave/', payload)) as unknown as Resp
  return res
}
