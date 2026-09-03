import adminApi from './axios'

export interface Campus {
  id: number
  name: string
  code: string
  description: string
  is_active: boolean
  display_order: number
  resort_ids: number[]
  resort_names: string[]
  staff_count: number
  coach_count: number
}

export interface CampusWriteData {
  name: string
  code: string
  description: string
  is_active: boolean
  display_order: number
  resort_ids: number[]
}

export interface OperatingPolicy {
  id: number
  campus: number | null
  campus_name: string
  unpaid_hold_days: number
  provisional_extra_groups: number
  cancellation_fee_percent: string | number
  cancellation_rules: { days_before: number; refund_percent: number }[]
  leave_advance_days: number
  leave_daily_coach_limit: number
  leave_max_consecutive_days: number
  course_reminder_days: number[]
  settings: Record<string, unknown>
}

interface ListResp<T> { data?: { list?: T[] } }
interface DetailResp<T> { data: T }

function unwrap<T>(payload: T | DetailResp<T>): T {
  return typeof payload === 'object' && payload !== null && 'data' in payload
    ? (payload as DetailResp<T>).data
    : payload as T
}

export async function fetchCampuses(): Promise<Campus[]> {
  const res = await adminApi.get('/campuses/') as unknown as ListResp<Campus>
  return res.data?.list || []
}

export async function createCampus(data: CampusWriteData): Promise<Campus> {
  const res = await adminApi.post('/campuses/', data) as unknown as Campus | DetailResp<Campus>
  return unwrap(res)
}

export async function updateCampus(id: number, data: CampusWriteData): Promise<Campus> {
  const res = await adminApi.put(`/campuses/${id}/`, data) as unknown as Campus | DetailResp<Campus>
  return unwrap(res)
}

export async function deleteCampus(id: number): Promise<void> {
  await adminApi.delete(`/campuses/${id}/`)
}

export async function fetchOperatingPolicies(): Promise<OperatingPolicy[]> {
  const res = await adminApi.get('/operating-policies/') as unknown as ListResp<OperatingPolicy>
  return res.data?.list || []
}

export async function updateOperatingPolicy(id: number, data: Partial<OperatingPolicy>): Promise<OperatingPolicy> {
  const res = await adminApi.patch(`/operating-policies/${id}/`, data) as unknown as OperatingPolicy | DetailResp<OperatingPolicy>
  return unwrap(res)
}
