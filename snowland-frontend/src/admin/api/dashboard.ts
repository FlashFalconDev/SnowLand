/**
 * 儀表板統計 API
 */
import adminApi from './axios'

export type Period = 'today' | 'yesterday' | 'week' | 'month' | 'custom'

export interface DashboardStats {
  stats: {
    orders: number
    revenue: number
    members: number
    avg_order_value: number
  }
  top_items: { id: number; name: string; quantity: number; revenue: number }[]
  marketing_sources: { name: string; orders: number; revenue: number }[]
  campus_summary: { name: string; orders: number; revenue: number }[]
  recent_orders: {
    sn: string
    member: string
    amount: number
    status: string
    created_at: string
  }[]
}

interface Resp { code: number; msg: string; data: DashboardStats }

export async function fetchDashboard(period: Period = 'month'): Promise<DashboardStats> {
  const res = (await adminApi.get('/dashboard/', { params: { period } })) as unknown as Resp
  return res.data
}
