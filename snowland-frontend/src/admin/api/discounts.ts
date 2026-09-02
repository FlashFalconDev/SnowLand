/**
 * 優惠折扣 API
 */
import adminApi from './axios'

export type DiscountType = 'amount' | 'percent'
export type DiscountScope = 'all' | 'ski' | 'photo' | 'bundle'
export type AmountApplyMode = 'order' | 'item' | 'course' | 'hour'

export interface DiscountCode {
  id: number
  code: string
  name: string
  description: string
  discount_type: DiscountType
  discount_type_label: string
  amount_apply_mode: AmountApplyMode
  amount_apply_mode_label: string
  discount_value: number
  max_discount_amount: number | null
  min_order_amount: number
  apply_scope: DiscountScope
  apply_scope_label: string
  require_multiple_items: boolean
  can_combine: boolean
  is_auto_apply: boolean
  new_customer_only: boolean
  usage_limit: number | null
  used_count: number
  start_at: string | null
  end_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DiscountCodeWriteData {
  code: string
  name?: string
  description?: string
  discount_type: DiscountType
  amount_apply_mode?: AmountApplyMode
  discount_value: number
  max_discount_amount?: number | null
  min_order_amount?: number
  apply_scope: DiscountScope
  require_multiple_items?: boolean
  can_combine?: boolean
  is_auto_apply?: boolean
  new_customer_only?: boolean
  usage_limit?: number | null
  start_at?: string | null
  end_at?: string | null
  is_active: boolean
}

interface DiscountListResp { code: number; msg: string; data: { list: DiscountCode[]; total: number } }
interface DiscountDetailResp { code: number; msg: string; data: DiscountCode }

export async function fetchDiscountCodes(): Promise<DiscountCode[]> {
  const res = (await adminApi.get('/discount-codes/')) as unknown as DiscountListResp
  return res.data?.list || []
}

export async function createDiscountCode(data: DiscountCodeWriteData): Promise<DiscountCode> {
  const res = (await adminApi.post('/discount-codes/', data)) as unknown as DiscountDetailResp
  return res.data
}

export async function updateDiscountCode(id: number, data: DiscountCodeWriteData): Promise<DiscountCode> {
  const res = (await adminApi.put(`/discount-codes/${id}/`, data)) as unknown as DiscountDetailResp
  return res.data
}

export async function deleteDiscountCode(id: number): Promise<void> {
  await adminApi.delete(`/discount-codes/${id}/`)
}
