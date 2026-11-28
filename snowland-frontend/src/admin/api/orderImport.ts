import adminApi from './axios'

export interface ImportIssue {
  row_number: number
  order_row_number?: number
  group_key: string
  level: 'ok' | 'warning' | 'error'
  code: string
  message_zh: string
  columns: string[]
}

export interface ImportOrderResult {
  row_number: number
  group_key: string
  status: 'ready' | 'error' | 'full' | 'created' | 'skipped' | 'failed'
  member?: ImportIssue
  amount?: number | null
  reported_amount?: number | null
  amount_difference?: number | null
  lesson_amounts?: { row_number: number; amount: number | null }[]
  issues: ImportIssue[]
  order_id?: number
  order_number?: string
  overbooked?: boolean
}

export interface ImportBatch {
  batch_id: number
  file_sha256: string
  status: 'previewed' | 'committed' | 'partial' | 'failed'
  summary: {
    orders: number
    lessons: number
    amount: number
    errors: number
    full: number
    closed: number
    skipped_examples: number
    committable: number
    warning_orders: number
    blocked_orders: number
    skipped_full: number
    already_imported: number
    full_amount: number
    created?: number
    skipped?: number
    failed?: number
  }
  row_results: ImportIssue[]
  order_results: ImportOrderResult[]
  commit_results?: ImportOrderResult[]
}

export async function downloadOrderImportTemplate() {
  return await adminApi.get('/order-import/template/', { responseType: 'blob' }) as unknown as Blob
}

export async function previewOrderImport(file: File) {
  const body = new FormData()
  body.append('file', file)
  const { data } = await adminApi.post('/order-import/preview/', body, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  }) as unknown as { data: ImportBatch }
  return data
}

export async function commitOrderImport(batchId: number, allowOverbook: boolean, reason: string) {
  const { data } = await adminApi.post('/order-import/commit/', {
    batch_id: batchId, confirm: true, allow_overbook: allowOverbook, overbook_reason: reason,
  }, { timeout: 180000 }) as unknown as { data: ImportBatch }
  return data
}
