import adminApi from './axios'

export interface PaymentSettings {
  bank_name: string
  bank_branch: string
  bank_account_number: string
  bank_account_holder: string
  messenger_options: string[]
  referral_source_options: string[]
}

export interface PaymentAccount {
  id: number
  name: string
  bank_name: string
  bank_branch: string
  account_number: string
  account_holder: string
  overseas_details: string
  campus_ids: number[]
  resort_ids: number[]
  is_default: boolean
  is_active: boolean
  display_order: number
}

interface Resp { code: number; msg: string; data: PaymentSettings }

export async function fetchPaymentSettings(): Promise<PaymentSettings> {
  const res = (await adminApi.get('/payment-settings/')) as unknown as Resp
  return res.data
}

export async function updatePaymentSettings(data: PaymentSettings): Promise<PaymentSettings> {
  const res = (await adminApi.put('/payment-settings/', data)) as unknown as Resp
  return res.data
}

export async function fetchPaymentAccounts(): Promise<PaymentAccount[]> {
  const res = await adminApi.get('/payment-accounts/') as any
  return res.data?.list || []
}

export async function createPaymentAccount(data: Omit<PaymentAccount, 'id'>): Promise<PaymentAccount> {
  const res = await adminApi.post('/payment-accounts/', data) as any
  return res.data || res
}

export async function deletePaymentAccount(id: number): Promise<void> {
  await adminApi.delete(`/payment-accounts/${id}/`)
}
