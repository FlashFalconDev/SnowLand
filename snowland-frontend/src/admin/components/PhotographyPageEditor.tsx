import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchPhotographySchema } from '../api/siteContent'

const inputClass = 'mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-[#8b5cf6] dark:border-gray-600 dark:bg-gray-900 dark:text-white'
const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}

export default function PhotographyPageEditor({ season, metadata, onChange }: {
  season: 'winter' | 'summer'; metadata: Record<string, unknown>; onChange: (metadata: Record<string, unknown>) => void
}) {
  const [search, setSearch] = useState('')
  const [matchedKeys, setMatchedKeys] = useState<string[] | null>(null)
  const { data: schema, isLoading, error, refetch } = useQuery({ queryKey: ['admin', 'photography-schema', season], queryFn: () => fetchPhotographySchema(season) })
  const saved = object(metadata.photography)
  const savedValues = object(saved.values)
  const compatible = !Object.keys(saved).length || (saved.version === 1 && saved.season === season)
  const defaults = Object.fromEntries(schema?.sections.flatMap(section => section.fields.map(field => [field.key, field.value])) || [])
  const values = { ...defaults, ...savedValues }
  useEffect(() => {
    if (schema && compatible && (!Object.keys(saved).length || Object.keys(defaults).some(key => !(key in savedValues)))) {
      onChange({ ...metadata, photography: { version: 1, season, values } })
    }
  }, [schema, metadata, compatible, onChange, season])
  if (isLoading) return <p role="status" className="py-6 text-sm text-gray-500 dark:text-gray-400">正在載入攝影頁面欄位…</p>
  if (error || !schema) return <div role="alert" className="py-4 text-sm text-red-600 dark:text-red-300">無法載入攝影頁面欄位。<button type="button" className="ml-2 min-h-11 underline" onClick={() => refetch()}>重新載入欄位</button></div>
  if (!compatible) return <p role="alert" className="text-sm text-red-600 dark:text-red-300">這份資料的季別或版型不符，請先核對，不會自動覆寫。</p>
  const update = (key: string, value: string) => onChange({ ...metadata, photography: { ...saved, version: 1, season, values: { ...values, [key]: value } } })
  const query = search.trim().toLowerCase()
  // Keep the search result stable while editing, even when its text no longer
  // contains the query. Recompute only when the user changes the search.
  const sections = schema.sections.map(section => ({ ...section, fields: section.fields.filter(field => !query || matchedKeys?.includes(field.key)) })).filter(section => section.fields.length)
  return <section className="space-y-4" aria-label="攝影頁面內容編輯">
    <div className="rounded-lg bg-blue-50 p-3 text-sm leading-6 text-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
      <p>依目前官網版型分區編輯；儲存後會更新對應文字與照片，不改排版。</p>
      <p>這裡的價格是官網展示文案；實際訂課收費請到「課程定價」設定。</p>
      <p>此資料代表整頁內容，建議編輯現有資料；有多筆公開資料時，依置頂及排序採用第一筆。</p>
    </div>
    <label className="block text-sm text-gray-700 dark:text-gray-200">搜尋要修改的文字或方案
      <input type="search" className={inputClass} value={search} onChange={event => {
        const value = event.target.value.toLowerCase().trim()
        setSearch(event.target.value)
        setMatchedKeys(schema.sections.flatMap(section => section.fields.filter(field => `${section.label} ${field.label} ${String(values[field.key] || '')}`.toLowerCase().includes(value)).map(field => field.key)))
      }} placeholder="例如：價格、婚紗、常見問題" />
    </label>
    {!sections.length && <p className="text-sm text-gray-500 dark:text-gray-400">沒有符合的欄位。<button type="button" onClick={() => setSearch('')} className="ml-2 min-h-11 underline">清除搜尋</button></p>}
    {sections.map((section, index) => <details key={`${section.id}-${query ? 'filtered' : 'all'}`} open={!!query || index === 0} className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <summary className="cursor-pointer text-sm font-semibold text-gray-900 dark:text-white">{section.label}（{section.fields.length}個欄位）</summary>
      <div className="mt-4 space-y-4">{section.fields.map(field => <label key={field.key} className="block text-sm text-gray-700 dark:text-gray-200">
        {field.label}
        {field.kind === 'text' ? <textarea aria-label={`${section.label}：${field.label}`} rows={String(values[field.key] || '').length > 100 ? 4 : 2} maxLength={20000} className={inputClass} value={String(values[field.key] || '')} onChange={event => update(field.key, event.target.value)} />
          : <input aria-label={`${section.label}：${field.label}`} type={field.kind === 'link' ? 'url' : 'text'} maxLength={500} className={inputClass} value={String(values[field.key] || '')} onChange={event => update(field.key, event.target.value)} />}
        {field.kind === 'image' && typeof values[field.key] === 'string' && /^(https?:\/\/|\/(?!\/))/.test(values[field.key] as string) && <img key={values[field.key] as string} loading="lazy" src={values[field.key] as string} alt={`${section.label}圖片預覽`} className="mt-2 max-h-36 rounded-lg object-contain" onError={event => { event.currentTarget.hidden = true }} />}
      </label>)}</div>
    </details>)}
  </section>
}
