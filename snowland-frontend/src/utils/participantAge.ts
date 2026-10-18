export function birthDateStatus(value: string, referenceDate: string): { age: number | null; error: string } {
  if (!value) return { age: null, error: '' }
  const validDate = (text: string) => /^\d{4}-\d{2}-\d{2}$/.test(text)
    && Number.isFinite(Date.parse(`${text}T00:00:00Z`))
    && new Date(`${text}T00:00:00Z`).toISOString().slice(0, 10) === text
  if (!validDate(value)) return { age: null, error: '請填寫有效的出生日期。' }
  if (!validDate(referenceDate)) return { age: null, error: '日期驗證資料尚未載入，請重新整理。' }
  if (value > referenceDate) return { age: null, error: '出生日期不能晚於今天。' }
  const age = Number(referenceDate.slice(0, 4)) - Number(value.slice(0, 4))
    - (referenceDate.slice(5) < value.slice(5) ? 1 : 0)
  return { age, error: '' }
}
