import adminApi from './axios'

interface ListResponse<T> { data?: { list?: T[] } }
interface DetailResponse<T> { data: T }

export interface NotificationTemplate {
  id: number; campus: number | null; name: string; event: string; channel: string
  subject: string; body: string; days_before: number; is_active: boolean; delivery_count: number
}

export interface NotificationDelivery {
  id: number; template_name: string; order_number: string; recipient: string
  scheduled_at: string; sent_at: string | null; status: string; error_message: string
}

export interface PayRule {
  id: number; coach: number; coach_name: string; discipline: string; certification_level: string
  hourly_rate: string; specified_fee: number; referral_percent: string
  assistance_hour_factor: string; supervisor_allowance: number; is_active: boolean
}

export interface PayrollStatement {
  id: number; coach: number; coach_name: string; campus: number; campus_name: string
  period_start: string; period_end: string; course_pay: number; specified_fees: number
  referral_commission: number; assistance_pay: number; supervisor_allowance: number
  adjustment: number; total_amount: number; status: string
}

export interface Evaluation {
  id: number; member_name: string; coach_name: string; course_date: string
  coach_notes: string; self_assessment: Record<string, unknown>; coach_assessment: Record<string, unknown>
  learning_progress: Record<string, unknown>; trail_names: string[]; completed_at: string | null
  media: { id: number; media_type: 'photo' | 'video'; url: string; caption: string; is_public: boolean }[]
}

export interface StaffBookingLink {
  id: number; campus: number; title: string; url: string; expires_at: string
  is_active: boolean; is_available: boolean; created_by_name: string
}

export interface InsuranceRecord {
  id: number; member_name: string; order_number: string; campus_name: string; age_range: string
  insurance_completed_at: string | null; waiver_completed_at: string | null; course_dates: string[]
}

const list = async <T>(path: string): Promise<T[]> => {
  const response = await adminApi.get(path) as unknown as ListResponse<T>
  return response.data?.list || []
}

export const fetchNotificationTemplates = () => list<NotificationTemplate>('/notification-templates/')
export const fetchNotificationDeliveries = () => list<NotificationDelivery>('/notification-deliveries/')
export const fetchPayRules = () => list<PayRule>('/coach-pay-rules/')
export const fetchPayrollStatements = () => list<PayrollStatement>('/payroll-statements/')
export const fetchEvaluations = () => list<Evaluation>('/evaluations/')
export const fetchStaffBookingLinks = () => list<StaffBookingLink>('/staff-booking-links/')
export const fetchInsuranceRecords = () => list<InsuranceRecord>('/insurance-records/?status=missing')

export async function saveNotificationTemplate(data: Partial<NotificationTemplate>) {
  const response = data.id
    ? await adminApi.patch(`/notification-templates/${data.id}/`, data)
    : await adminApi.post('/notification-templates/', data)
  return (response as unknown as DetailResponse<NotificationTemplate>).data
}

export async function savePayRule(data: Partial<PayRule>) {
  const response = data.id
    ? await adminApi.patch(`/coach-pay-rules/${data.id}/`, data)
    : await adminApi.post('/coach-pay-rules/', data)
  return (response as unknown as DetailResponse<PayRule>).data
}

export async function calculatePayroll(data: { coach: number; campus: number; period_start: string; period_end: string }) {
  const response = await adminApi.post('/payroll-statements/calculate/', data)
  return (response as unknown as DetailResponse<PayrollStatement>).data
}

export async function createStaffBookingLink(data: { campus: number; title: string; expires_at: string; cart_snapshot?: unknown[] }) {
  const response = await adminApi.post('/staff-booking-links/', { ...data, cart_snapshot: data.cart_snapshot || [] })
  return (response as unknown as DetailResponse<StaffBookingLink>).data
}

export async function completeInsuranceRecord(id: number, field: 'insurance' | 'waiver') {
  await adminApi.post(`/insurance-records/${id}/complete/`, { field })
}

export async function updateEvaluation(id: number, data: Partial<Evaluation>) {
  await adminApi.patch(`/evaluations/${id}/`, data)
}

export async function addEvaluationMedia(id: number, data: { media_type: 'photo' | 'video'; url: string; caption?: string; is_public?: boolean }) {
  await adminApi.post(`/evaluations/${id}/media/`, data)
}
