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
  reward_balance?: number
  updated_at: string
  history: { id: number; before: { points: number }; after: { points: number }; reason: string; reviewed_by: string; created_at: string }[]
}

export interface LoyaltyPolicy {
  revision: number
  enabled: boolean
  earn_on: 'paid' | 'completed'
  points_per_twd: string
  rewards_per_twd: string
  twd_per_reward: string
  referrer_rewards: number
  new_member_rewards: number
  refund_rule: 'proportional' | 'keep'
  levels: { label: string; minimum_points: number }[]
}

export async function fetchLoyaltyPolicy(): Promise<LoyaltyPolicy> {
  const result = await adminApi.get('/customers/loyalty-policy/') as unknown as { data: LoyaltyPolicy }
  return result.data
}

export async function saveLoyaltyPolicy(policy: LoyaltyPolicy): Promise<LoyaltyPolicy> {
  const result = await adminApi.put('/customers/loyalty-policy/', policy) as unknown as { data: LoyaltyPolicy }
  return result.data
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

export async function fetchCustomers(loyalty = false): Promise<Customer[]> {
  const res = (await adminApi.get('/customers/', { params: loyalty ? { workflow: 'loyalty' } : undefined })) as unknown as ListResp
  return res.data?.list || []
}
