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
  loyalty?: { alumni_verified: boolean; points: number; previous_points: number } | null
}

export interface LoyaltyReview {
  points: number
  previous_points: number
  alumni_verified: boolean
  level: string
  updated_at: string
  history: { id: number; before: { points: number }; after: { points: number }; reason: string; reviewed_by: string; created_at: string }[]
}

export async function fetchCustomerLoyalty(id: number): Promise<LoyaltyReview> {
  const result = await adminApi.get(`/customers/${id}/loyalty/`) as unknown as { data: LoyaltyReview }
  return result.data
}

export async function saveCustomerLoyalty(id: number, values: { alumni_verified: boolean; previous_points: number; reason: string; expected_updated_at: string }): Promise<LoyaltyReview> {
  const result = await adminApi.post(`/customers/${id}/loyalty/`, values) as unknown as { data: LoyaltyReview }
  return result.data
}

interface ListResp { code: number; msg: string; data: { list: Customer[]; total: number } }

export async function fetchCustomers(): Promise<Customer[]> {
  const res = (await adminApi.get('/customers/')) as unknown as ListResp
  return res.data?.list || []
}
