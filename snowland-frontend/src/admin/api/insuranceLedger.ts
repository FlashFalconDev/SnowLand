import adminApi from './axios'

export type DepositKind = 'opening' | 'top_up'
export interface LedgerEntry {
  id: number
  sequence: number
  kind: DepositKind | 'deduction' | 'reversal'
  amount: string
  balance_after: string
  created_at: string
  actor: string
  reference: string
  note: string
  member_id: number | null
  order_id: number | null
  reverses_id: number | null
  reversed: boolean
}

export interface InsuranceLedger {
  enabled: boolean
  writable: boolean
  currency: string
  balance: string | null
  low_balance: boolean
  entries: LedgerEntry[]
  page: number
  pages: number
  can_confirm_month: boolean
}

export interface Reconciliation {
  month: string
  opening: string
  top_ups: string
  deductions: string
  reversals: string
  closing: string
  cutoff_sequence: number
  confirmed_at: string | null
  confirmed_by: string | null
  note: string
}

type Evidence = { reference: string; note: string; idempotency_key: string }
type Result<T> = { data: T }

export async function fetchInsuranceLedger(month: string, page: number) {
  const response = await adminApi.get('/insurance-ledger/', { params: { month, page } }) as unknown as Result<InsuranceLedger>
  return response.data
}

export async function depositInsuranceFunds(data: Evidence & { kind: DepositKind; amount: string }) {
  await adminApi.post('/insurance-ledger/deposits/', data)
}

export async function reverseInsuranceEntry(id: number, data: Evidence) {
  await adminApi.post(`/insurance-ledger/entries/${id}/reverse/`, data)
}

export async function fetchInsuranceReconciliation(month: string) {
  const response = await adminApi.get('/insurance-ledger/reconciliation/', { params: { month } }) as unknown as Result<Reconciliation>
  return response.data
}

export async function confirmInsuranceReconciliation(data: {
  month: string; cutoff_sequence: number; statement_balance: string; note: string
}) {
  await adminApi.post('/insurance-ledger/reconciliation/', data)
}
