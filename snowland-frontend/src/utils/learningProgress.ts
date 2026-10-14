const KEY_LABELS: Record<string, string> = {
  before: '課前程度',
  after: '課後程度',
}

const VALUE_LABELS: Record<string, string> = {
  no_exp: '初學／無經驗',
  level1: '等級 1',
  level2: '等級 2',
  level3: '等級 3',
  level4: '等級 4',
  level5: '等級 5',
  level6: '等級 6',
}

const KEY_CODES = Object.fromEntries(Object.entries(KEY_LABELS).map(([code, label]) => [label, code]))
const VALUE_CODES = Object.fromEntries(Object.entries(VALUE_LABELS).map(([code, label]) => [label, code]))

export function formatAbilityLevel(value: string | null | undefined): string {
  return value ? VALUE_LABELS[value] || value : '未填'
}

export function formatLearningProgressEntry(key: string, value: unknown): string {
  const rawValue = String(value ?? '')
  return `${KEY_LABELS[key] || key}：${VALUE_LABELS[rawValue] || rawValue}`
}

export function learningProgressToText(progress: Record<string, unknown>): string {
  return Object.entries(progress || {}).map(([key, value]) => formatLearningProgressEntry(key, value)).join('\n')
}

export function learningProgressFromText(text: string): Record<string, string> {
  return Object.fromEntries(text.split('\n').map((line) => {
    const [rawKey, ...valueParts] = line.split(/[：:]/)
    const key = rawKey?.trim() || ''
    const value = valueParts.join('：').trim()
    return [KEY_CODES[key] || key, VALUE_CODES[value] || value]
  }).filter(([key]) => key))
}
