import { useMemo, useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { siteMessages, siteNavigationSources, type SiteLocale } from '@/utils/siteLocale'
import { currentClientCode } from '@/utils/tenant'
import adminApi from '../../api/axios'

const kinds = [
  ['ui', '按鈕與介面'], ['navigation', '官網選單'], ['article', '文章'], ['page', '官網頁面'], ['faq', '常見問題'],
  ['template', '課程模板'], ['type', '課程類型'], ['category', '課程大類'], ['recruitment', '招募題目'],
] as const
const languages = [['zh-Hant', '繁體中文'], ['en', 'English'], ['ja', '日本語']] as const
const button = 'min-h-10 rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:opacity-40 dark:border-gray-600'
const primary = 'min-h-10 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50'
const input = 'w-full rounded-md border border-gray-300 bg-transparent p-2 text-sm dark:border-gray-600'
const panel = 'rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 sm:p-6'
const PAGE_SIZE = 20

type Kind = typeof kinds[number][0]
type Values = Record<SiteLocale, string>
type Entry = { source: string; values: Values }
type Field = { key: string; source: string; label: string }
type Entries = { revision: string; entries: Record<string, Entry>; fields: Field[] }
type Catalog = { items: { scope: string; title: string }[]; more: boolean }
const empty: Values = {'zh-Hant': '', en: '', ja: ''}
const owns = (object: object, key: string) => Object.prototype.hasOwnProperty.call(object, key)

function initialValues(scope: string, data: Entries, field: Field): Values {
  const saved = owns(data.entries, field.key) ? data.entries[field.key] : undefined
  if (saved?.source === field.source) return {...empty, ...saved.values}
  return (scope === 'ui' || scope === 'navigation') && owns(siteMessages, field.source)
    ? {...empty, ...siteMessages[field.source]} : empty
}

function errorText(error: unknown, fallback: string): string {
  const body = (error as {response?: {data?: {error?: string; values?: string[]}}})?.response?.data
  return body?.error || body?.values?.[0] || fallback
}

function TranslationEditor({ scope, title, initial, onDirty }: {
  scope: string; title: string; initial: Entries; onDirty: (value: boolean) => void
}) {
  const [data, setData] = useState(initial)
  const [edits, setEdits] = useState<Record<string, Values>>({})
  const [term, setTerm] = useState('')
  const [page, setPage] = useState(0)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const fields = useMemo(() => {
    if (scope !== 'ui' && scope !== 'navigation') return initial.fields
    const sources = scope === 'ui' ? Object.keys(siteMessages) : [...siteNavigationSources]
    return sources.sort((a, b) => a.localeCompare(b, 'zh-Hant'))
      .map(source => ({key: source, label: scope === 'ui' ? '介面文字' : '選單文字', source}))
  }, [scope, initial.fields])
  const needle = term.trim().toLocaleLowerCase()
  const valuesFor = (field: Field) => owns(edits, field.key) ? edits[field.key] : initialValues(scope, data, field)
  const matched = fields.filter(field => !needle || [field.label, field.source, ...Object.values(initialValues(scope, data, field)), ...Object.values(valuesFor(field))]
    .some(value => value.toLocaleLowerCase().includes(needle)))
  const lastPage = Math.max(0, Math.ceil(matched.length / PAGE_SIZE) - 1)
  const currentPage = Math.min(page, lastPage)
  const edited = Object.keys(edits).length

  function change(field: Field, locale: SiteLocale, value: string) {
    const next = {...edits, [field.key]: {...valuesFor(field), [locale]: value}}
    const baseline = initialValues(scope, data, field)
    if (languages.every(([code]) => next[field.key][code] === baseline[code])) delete next[field.key]
    setEdits(next)
    onDirty(Object.keys(next).length > 0)
    setMessage('')
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!edited || saving) return
    setSaving(true)
    setError('')
    try {
      const updates = fields.filter(field => owns(edits, field.key))
        .map(field => ({key: field.key, source: field.source, values: edits[field.key]}))
      const saved = await adminApi.put('/site-translations/entries/', {revision: data.revision, updates}, {params: {scope}}) as unknown as Entries
      setData({...data, ...saved})
      setEdits({})
      onDirty(false)
      setMessage('已儲存。重新整理官網即可查看。')
    } catch (failure) {
      setError(errorText(failure, '儲存失敗，請稍後再試。'))
    } finally {
      setSaving(false)
    }
  }

  return <form className={panel} onSubmit={save}>
    <h2 className="text-lg font-semibold">{title}</h2>
    <p className="mt-1 text-sm opacity-80">可用原文或任何語言搜尋。語言欄留空時，官網顯示原文。</p>
    <label className="mt-4 block text-sm">搜尋這份文字
      <input type="search" className={`${input} mt-1`} value={term} onChange={event => {setTerm(event.target.value); setPage(0)}} />
    </label>
    <fieldset disabled={saving} className="mt-4 space-y-4">
      {matched.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE).map(field => <div key={field.key} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
        <p className="text-xs font-medium opacity-75">{field.label} · 原文</p>
        <p className="mb-3 mt-1 whitespace-pre-wrap break-words text-sm">{field.source}</p>
        <div className="grid gap-3 lg:grid-cols-3">
          {languages.map(([locale, label]) => <label key={locale} className="text-sm">
            {label}
            <textarea className={`${input} mt-1`} rows={field.source.length > 80 ? 4 : 2} maxLength={30000}
              aria-label={`${field.label} · ${label}`} value={valuesFor(field)[locale]}
              onChange={event => change(field, locale, event.target.value)} />
          </label>)}
        </div>
      </div>)}
    </fieldset>
    {!matched.length && <p className="mt-4 text-sm">{term ? '找不到符合的文字。' : '這個項目目前沒有可翻譯的文字。'}</p>}
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <span className="mr-auto text-sm">{matched.length} 則文字{lastPage > 0 && ` · 第 ${currentPage + 1}／${lastPage + 1} 頁`}</span>
      {lastPage > 0 && <>
        <button type="button" className={button} disabled={!currentPage} onClick={() => setPage(currentPage - 1)}>上一頁文字</button>
        <button type="button" className={button} disabled={currentPage === lastPage} onClick={() => setPage(currentPage + 1)}>下一頁文字</button>
      </>}
      {edited > 0 && <button type="button" className={button} disabled={saving} onClick={() => {setEdits({}); onDirty(false); setError('')}}>捨棄變更</button>}
      <button type="submit" className={primary} disabled={!edited || saving}>{saving ? '儲存中…' : `儲存翻譯${edited ? `（${edited}）` : ''}`}</button>
    </div>
    {error && <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-300">{error}</p>}
    {message && <p role="status" className="mt-3 text-sm">{message}</p>}
  </form>
}

function SiteTranslationsConsole({client}: {client: string}) {
  const [kind, setKind] = useState<Kind>('ui')
  const [target, setTarget] = useState({scope: '', title: ''})
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [dirty, setDirty] = useState(false)
  const direct = kind === 'ui' || kind === 'navigation' || kind === 'recruitment'
  const scope = direct ? kind : target.scope
  const title = direct ? kinds.find(([key]) => key === kind)?.[1] || '' : target.title
  const catalog = useQuery({
    queryKey: ['site-translations-catalog', client, kind, query, page], enabled: !direct,
    queryFn: () => adminApi.get('/site-translations/', {params: {kind, search: query, page}}) as unknown as Promise<Catalog>,
  })
  const detail = useQuery({
    queryKey: ['site-translations-detail', client, scope], enabled: !!scope, gcTime: 0,
    queryFn: () => adminApi.get('/site-translations/entries/', {params: {scope}}) as unknown as Promise<Entries>,
  })
  return <main className="space-y-5">
    <h1 className="text-2xl font-semibold">中英日文字管理</h1>
    <div className="flex flex-wrap gap-2" aria-label="翻譯分類">
      {kinds.map(([value, label]) => <button key={value} type="button" className={value === kind ? primary : button}
        aria-pressed={value === kind} disabled={dirty && value !== kind} onClick={() => {
          if (value === kind) return
          setKind(value); setTarget({scope: '', title: ''}); setSearch(''); setQuery(''); setPage(1)
        }}>{label}</button>)}
    </div>
    {!direct && <section className={panel}>
      <form className="flex items-end gap-2" onSubmit={event => {event.preventDefault(); setQuery(search.trim()); setPage(1)}}>
        <label className="grow text-sm">搜尋名稱<input className={`${input} mt-1`} type="search" value={search} onChange={event => setSearch(event.target.value)} /></label>
        <button type="submit" className={button}>查找</button>
      </form>
      {catalog.isPending && <p className="mt-3 text-sm" role="status">載入中…</p>}
      {catalog.isError && <p className="mt-3 text-sm" role="alert">無法載入項目。<button type="button" className="ml-2 underline" onClick={() => catalog.refetch()}>重試</button></p>}
      {catalog.data?.items.length === 0 && <p className="mt-3 text-sm">找不到項目。</p>}
      <ul className="mt-3 divide-y divide-gray-200 dark:divide-gray-700">
        {catalog.data?.items.map(item => <li key={item.scope}>
          <button type="button" className="min-h-10 w-full px-1 py-2 text-left text-sm hover:underline disabled:opacity-50"
            aria-pressed={scope === item.scope} disabled={dirty} onClick={() => setTarget(item)}>{item.title || '未命名內容'}</button>
        </li>)}
      </ul>
      {(page > 1 || catalog.data?.more) && <div className="mt-2 flex gap-2">
        <button type="button" className={button} disabled={page === 1} onClick={() => setPage(page - 1)}>上一頁項目</button>
        <button type="button" className={button} disabled={!catalog.data?.more} onClick={() => setPage(page + 1)}>下一頁項目</button>
      </div>}
    </section>}
    {scope && detail.isPending && <p role="status">載入文字中…</p>}
    {scope && detail.isError && <p role="alert">無法載入文字。<button type="button" className="ml-2 underline" onClick={() => detail.refetch()}>重試</button></p>}
    {scope && detail.data && <TranslationEditor key={scope} scope={scope} title={title} initial={detail.data} onDirty={setDirty} />}
  </main>
}

export default function SiteTranslationsPage() {
  const client = currentClientCode()
  return <SiteTranslationsConsole key={client} client={client} />
}
