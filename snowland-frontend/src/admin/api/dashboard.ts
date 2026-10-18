/**
 * 儀表板統計 API
 */
import adminApi from './axios'

export type Period = 'today' | 'yesterday' | 'week' | 'month' | 'quarter' | 'custom'
export type DateBasis = 'created' | 'completed'
export interface DashboardFilters { date_basis?: DateBasis; start_date?: string; end_date?: string; resort_id?: string }

export interface DashboardStats {
  restricted_order_details: boolean
  stats: {
    orders: number
    revenue: number
    completed_orders: number
    members: number
    avg_order_value: number
    student_visits: number
    teaching_hours: number
  }
  resort_options: { id: number; display_name: string }[]
  payment_statuses: { status: string; name: string; orders: number }[]
  top_items: { id: number; name: string; quantity: number; revenue: number }[]
  marketing_sources: { name: string; orders: number; revenue: number }[]
  campus_summary: { name: string; orders: number; revenue: number; is_active: boolean | null }[]
  recent_orders: {
    sn: string
    member: string
    amount?: number
    status?: string
    created_at: string
  }[]
}

interface Resp { code: number; msg: string; data: DashboardStats }

export async function fetchDashboard(period: Period = 'month', filters: DashboardFilters = {}): Promise<DashboardStats> {
  const res = (await adminApi.get('/dashboard/', { params: { period, ...filters } })) as unknown as Resp
  return res.data
}

export async function exportDashboard(period: Period, filters: DashboardFilters, format: 'csv' | 'xlsx'): Promise<Blob> {
  return await adminApi.get('/dashboard/', { params: { period, ...filters, export: format }, responseType: 'blob' }) as unknown as Blob
}
