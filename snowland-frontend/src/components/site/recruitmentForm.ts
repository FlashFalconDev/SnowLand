export type FieldType = 'short' | 'long' | 'single' | 'multiple' | 'file'
export type FileFormat = 'pdf' | 'jpeg' | 'png'

export interface RecruitmentField {
  id: string
  label: string
  type: FieldType
  required: boolean
  options?: string[]
  formats?: FileFormat[]
  max_mb?: number
}

export interface RecruitmentSettings {
  enabled: boolean
  fields: RecruitmentField[]
  revision: string
}

export const recruitmentFileFormats: Record<FileFormat, { label: string; accept: string }> = {
  pdf: {label: 'PDF', accept: '.pdf,application/pdf'},
  jpeg: {label: 'JPEG', accept: '.jpg,.jpeg,image/jpeg'},
  png: {label: 'PNG', accept: '.png,image/png'},
}

interface RecruitmentFailure {
  response?: { data?: { error?: string; fields?: Record<string, string> }; status?: number }
}

export function recruitmentError(failure: unknown, fallback: string) {
  const {data, status} = (failure as RecruitmentFailure)?.response || {}
  if (status === 429) return '送出次數較多，請稍候一分鐘再試。'
  if (typeof data?.error === 'string') return data.error
  const messages: string[] = []
  const visit = (value: unknown) => {
    if (typeof value === 'string') messages.push(value)
    else if (value && typeof value === 'object') Object.values(value).forEach(visit)
  }
  visit(data)
  return messages.join('；') || fallback
}
