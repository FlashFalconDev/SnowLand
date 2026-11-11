import adminApi from './axios'

export interface PaymentSettings {
  order_management_email?: string
  currency_settings?: { jpy_enabled: boolean; jpy_per_twd: string; foreign_reference_only?: boolean; foreign_rates?: Partial<Record<'USD'|'HKD'|'CNY', string>> }
  bank_name: string
  bank_branch: string
  bank_account_number: string
  bank_account_holder: string
  messenger_options: string[]
  referral_source_options: string[]
}

export interface PaymentAccount {
  currency?: import('../../utils/settlementPreview').PaymentCurrency
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

export type PaymentSettingsSection = 'accounts' | 'booking-form'

export async function fetchPaymentSettings(section?: PaymentSettingsSection): Promise<PaymentSettings> {
  const res = (await adminApi.get('/payment-settings/', { params: { section } })) as unknown as Resp
  return res.data
}

export async function updatePaymentSettings(data: Partial<PaymentSettings>, section?: PaymentSettingsSection): Promise<PaymentSettings> {
  const res = (await adminApi.put('/payment-settings/', data, { params: { section } })) as unknown as Resp
  return res.data
}

interface PaymentAccountScopeOptions {
  campuses: { id: number; name: string; is_active: boolean; resort_ids: number[] }[]
  resorts: { id: number; display_name: string }[]
}

export async function fetchPaymentAccountScopeOptions(): Promise<PaymentAccountScopeOptions> {
  const response = await adminApi.get('/payment-accounts/scope-options/', { headers: { 'X-Campus-ID': 'all' } }) as unknown as { data: PaymentAccountScopeOptions }
  return response.data
}

export async function fetchPaymentAccounts(): Promise<PaymentAccount[]> {
  const res = await adminApi.get('/payment-accounts/') as any
  return res.data?.list || []
}

export async function createPaymentAccount(data: Omit<PaymentAccount, 'id'>): Promise<PaymentAccount> {
  const res = await adminApi.post('/payment-accounts/', data) as any
  return res.data || res
}

export async function updatePaymentAccount(id: number, data: Omit<PaymentAccount, 'id'>): Promise<PaymentAccount> {
  const res = await adminApi.patch(`/payment-accounts/${id}/`, data) as any
  return res.data || res
}

export async function deletePaymentAccount(id: number): Promise<void> {
  await adminApi.delete(`/payment-accounts/${id}/`)
}
