import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAboutSchema, fetchJoinSchema, type AboutSchema } from '../api/siteContent'

const record = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
const inputClass = 'mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-[#8b5cf6] dark:border-gray-600 dark:bg-gray-900 dark:text-white'

export function aboutEditorDefaults(schema: AboutSchema, metadata: Record<string, unknown>) {
  const page = record(metadata.page)
  const blocks = metadata.blocks ?? page.blocks
  return Object.fromEntries(schema.sections.flatMap(section => section.fields.map(field => {
    if (!field.source_heading || !Array.isArray(blocks)) return [field.key, field.value]
    const start = blocks.findIndex(block => record(block).type === 'heading' && record(block).text === field.source_heading)
    const paragraphs: string[] = []
    if (start >= 0) for (const raw of blocks.slice(start + 1)) {
      const block = record(raw)
      if (block.type === 'heading') break
      if (block.type === 'paragraph' && typeof block.text === 'string') paragraphs.push(...block.text.replace(/\s+/g, ' ').trim().split(/(?<=[。！？])\s*/).filter(Boolean))
    }
    const matching = field.source_contains ? paragraphs.filter(text => text.includes(field.source_contains as string)) : paragraphs
    return [field.key, (field.source_first ? matching.slice(0, 1) : matching).join('\n')]
  })))
}

export default function AboutPageEditor({ metadata, onChange, pageKey = 'about' }: {metadata: Record<string, unknown>; onChange: (metadata: Record<string, unknown>) => void; pageKey?: 'about' | 'join-us'}) {
  const name = pageKey === 'about' ? '學校介紹' : '教練招募'
  const [search, setSearch] = useState('')
  const [matchedKeys, setMatchedKeys] = useState<string[] | null>(null)
  const {data: schema, isLoading, error, refetch} = useQuery({queryKey: ['admin', 'original-layout-schema', pageKey], queryFn: pageKey === 'about' ? fetchAboutSchema : fetchJoinSchema})
  const saved = record(metadata.layout), savedValues = record(saved.values)
  const compatible = !('layout' in metadata) || (saved.version === 1 && saved.page_key === pageKey && typeof saved.values === 'object' && !Array.isArray(saved.values) && saved.values !== null && Object.values(savedValues).every(value => typeof value === 'string'))
  const defaults = schema ? aboutEditorDefaults(schema, metadata) : {}
  const values = {...defaults, ...savedValues}
  useEffect(() => {
    if (schema && compatible && (!('layout' in metadata) || Object.keys(defaults).some(key => !(key in savedValues)))) onChange({...metadata, layout: {version: 1, page_key: pageKey, values}})
  }, [schema, metadata, compatible, onChange, pageKey])
  if (isLoading) return <p role="status" className="py-6 text-sm text-gray-500 dark:text-gray-400">正在載入{name}原稿…</p>
  if (error || !schema) return <div role="alert" className="py-4 text-sm text-red-600 dark:text-red-300">無法載入{name}欄位。<button type="button" onClick={() => refetch()} className="ml-2 min-h-11 underline">重新載入欄位</button></div>
  if (!compatible) return <p role="alert" className="text-sm text-red-600 dark:text-red-300">原稿版型資料不符，請先核對，不會自動覆寫。</p>
  const query = search.trim().toLowerCase()
  const fields = schema.sections.flatMap(section => section.fields).filter(field => !query || matchedKeys?.includes(field.key))
  const update = (key: string, value: string) => onChange({...metadata, layout: {...saved, version: 1, page_key: pageKey, values: {...values, [key]: value}}})
  return <section aria-label={`${name}原版型編輯`} className="space-y-4">
    <div className="rounded-lg bg-blue-50 p-3 text-sm leading-6 text-blue-900 dark:bg-blue-950/40 dark:text-blue-200">直接搜尋目前官網的文字或圖片。儲存後更新原版型；這裡不是另加一篇文章，原設定與舊正文不會被刪除。</div>
    <label className="block text-sm text-gray-700 dark:text-gray-200">搜尋原文或欄位
      <input type="search" value={search} className={inputClass} placeholder="例如：親子、學員回饋、圖片" onChange={event => {
        const value = event.target.value.trim().toLowerCase()
        setSearch(event.target.value)
        setMatchedKeys(schema.sections.flatMap(section => section.fields.filter(field => `${field.label} ${String(values[field.key] ?? '')}`.toLowerCase().includes(value)).map(field => field.key)))
      }} />
    </label>
    <p className="text-xs text-gray-500 dark:text-gray-400">顯示 {fields.length}／{schema.sections.flatMap(section => section.fields).length} 個欄位；段落內容每行一段。</p>
    {!fields.length && <button type="button" className="min-h-11 text-sm underline" onClick={() => setSearch('')}>沒有符合欄位，清除搜尋</button>}
    {fields.map(field => <label key={field.key} className="block text-sm text-gray-700 dark:text-gray-200">{field.label}（{field.key.replace(/^(about|join)_/, '')}）
      {field.kind === 'text' ? <textarea aria-label={`${field.label} ${field.key}`} rows={String(values[field.key] ?? '').length > 100 ? 4 : 2} maxLength={20000} className={inputClass} value={String(values[field.key] ?? '')} onChange={event => update(field.key, event.target.value)} />
        : <input aria-label={`${field.label} ${field.key}`} maxLength={2000} className={inputClass} value={String(values[field.key] ?? '')} onChange={event => update(field.key, event.target.value)} />}
      {field.kind === 'image' && typeof values[field.key] === 'string' && /^(https?:\/\/|\/(?!\/))/.test(values[field.key] as string) && <img key={values[field.key] as string} src={values[field.key] as string} alt={`圖片${field.key}預覽`} loading="lazy" className="mt-2 max-h-36 rounded-lg object-contain" onError={event => {event.currentTarget.hidden = true}} />}
    </label>)}
  </section>
}
