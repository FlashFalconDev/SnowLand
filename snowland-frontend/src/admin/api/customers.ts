/**
 * 客戶名單 API
 */
import adminApi from './axios'

export interface Customer {
  id: number
  name: string
  email: string
  phone: string
  total_reservations: number
  total_spent: number
  last_visit: string
  age_range: string
  snowboard_skills: string[]
  ski_skills: string[]
  notes?: string
  is_manager?: boolean
  is_coach?: boolean
}

interface ListResp { code: number; msg: string; data: { list: Customer[]; total: number } }

export async function fetchCustomers(): Promise<Customer[]> {
  const res = (await adminApi.get('/customers/')) as unknown as ListResp
  return res.data?.list || []
}
