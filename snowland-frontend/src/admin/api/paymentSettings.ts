import adminApi from './axios'

export interface PaymentSettings {
  bank_name: string
  bank_branch: string
  bank_account_number: string
  bank_account_holder: string
  messenger_options: string[]
  referral_source_options: string[]
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
