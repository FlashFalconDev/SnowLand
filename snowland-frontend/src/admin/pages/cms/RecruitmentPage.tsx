import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import RecruitmentFields from '@/components/site/RecruitmentFields'
import {
  recruitmentError, recruitmentFileFormats, type FieldType, type FileFormat,
  type RecruitmentField, type RecruitmentSettings,
} from '@/components/site/recruitmentForm'
import { currentClientCode } from '@/utils/tenant'
import adminApi from '../../api/axios'

const fieldTypes: Record<FieldType, string> = {
  short: '簡答', long: '長答', single: '單選', multiple: '複選', file: '附件上傳',
}
const panel = 'rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 sm:p-6'
const input = 'mt-1 w-full rounded-md border border-gray-300 bg-transparent p-2 dark:border-gray-600'
const button = 'rounded-md border border-gray-300 px-3 py-2 text-sm font-medium disabled:opacity-40 dark:border-gray-600'
const primary = 'rounded-md bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50'

function defaults(type: FieldType): Pick<RecruitmentField, 'options' | 'formats' | 'max_mb'> {
  if (type === 'file') return {formats: ['pdf'], max_mb: 5}
  if (type === 'single' || type === 'multiple') return {options: []}
  return {}
}

function FormEditor({settings}: {settings: RecruitmentSettings}) {
  const [draft, setDraft] = useState(settings)
  const [preview, setPreview] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  function changeFields(fields: RecruitmentField[]) {
    setDraft(value => ({...value, fields}))
    setMessage('')
  }
  function update(index: number, field: RecruitmentField) {
    changeFields(draft.fields.map((current, position) => position === index ? field : current))
  }
  function move(index: number, direction: number) {
    const fields = [...draft.fields]
    const [field] = fields.splice(index, 1)
    fields.splice(index + direction, 0, field)
    changeFields(fields)
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const fields = draft.fields.map(field => ({
        ...field, label: field.label.trim(), options: field.options?.map(option => option.trim()).filter(Boolean),
      }))
      const saved = await adminApi.put('/recruitment/settings/', {...draft, fields}) as unknown as RecruitmentSettings
      setDraft(saved)
      setMessage(saved.enabled ? '已儲存，官網站內應徵已開放。' : '已儲存，站內應徵未開放。')
    } catch (failure) {
      setError(recruitmentError(failure, '儲存失敗，請稍後再試。'))
    } finally {
      setSaving(false)
    }
  }

  return <div className="space-y-5">
    <form className={panel} onSubmit={save}>
      <fieldset disabled={saving} className="space-y-5">
        <label className="flex items-center gap-2 font-medium">
          <input type="checkbox" checked={draft.enabled} onChange={event => {
            const enabled = event.target.checked
            setDraft(value => ({...value, enabled}))
            setMessage('')
          }} />開放站內應徵
        </label>
        {draft.fields.map((field, index) => <fieldset key={field.id} className="space-y-3 rounded-md border border-gray-200 p-4 dark:border-gray-700">
          <legend className="px-1 text-sm font-medium">題目 {index + 1}</legend>
          <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
            <label className="text-sm">題目名稱
              <input required maxLength={150} value={field.label} className={input}
                onChange={event => update(index, {...field, label: event.target.value})} />
            </label>
            <label className="text-sm">題型
              <select className={input} value={field.type} onChange={event => {
                const type = event.target.value as FieldType
                update(index, {id: field.id, label: field.label, required: field.required, type, ...defaults(type)})
              }}>{Object.entries(fieldTypes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
            </label>
          </div>
          {(field.type === 'single' || field.type === 'multiple') && <label className="block text-sm">選項（每行一個）
            <textarea required rows={3} className={input} value={field.options?.join('\n') ?? ''}
              onChange={event => update(index, {...field, options: event.target.value.split('\n')})} />
          </label>}
          {field.type === 'file' && <div className="flex flex-wrap items-end gap-4">
            <fieldset className="flex flex-wrap gap-3 text-sm">
              <legend className="mb-2">允許格式</legend>
              {Object.entries(recruitmentFileFormats).map(([key, {label}]) => {
                const format = key as FileFormat
                return <label key={format} className="flex items-center gap-2">
                  <input type="checkbox" checked={field.formats?.includes(format) ?? false} onChange={event => {
                    const formats = field.formats ?? []
                    update(index, {...field, formats: event.target.checked ? [...formats, format] : formats.filter(value => value !== format)})
                  }} />{label}
                </label>
              })}
            </fieldset>
            <label className="text-sm">單檔上限（MB）
              <input type="number" required min={1} max={10} value={field.max_mb ?? ''} className={`${input} w-24`}
                onChange={event => update(index, {...field, max_mb: event.target.value ? event.target.valueAsNumber : undefined})} />
            </label>
          </div>}
          <div className="flex flex-wrap items-center gap-2">
            <label className="mr-auto flex items-center gap-2 text-sm">
              <input type="checkbox" checked={field.required}
                onChange={event => update(index, {...field, required: event.target.checked})} />必填
            </label>
            <button className={button} type="button" disabled={!index} onClick={() => move(index, -1)}>上移</button>
            <button className={button} type="button" disabled={index === draft.fields.length - 1} onClick={() => move(index, 1)}>下移</button>
            <button className={button} type="button" onClick={() => changeFields(draft.fields.filter(item => item.id !== field.id))}>移除題目</button>
          </div>
        </fieldset>)}
        <div className="flex flex-wrap gap-3">
          <button type="button" className={button} disabled={draft.fields.length >= 30} onClick={() => {
            changeFields([...draft.fields, {id: crypto.randomUUID(), label: '', required: false, type: 'short'}])
          }}>新增題目</button>
          <button type="button" className={button} aria-expanded={preview} onClick={() => setPreview(value => !value)}>{preview ? '收起預覽' : '預覽表單'}</button>
          <button type="submit" className={primary}>{saving ? '儲存中…' : '儲存表單'}</button>
        </div>
      </fieldset>
      {error && <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-300">{error}</p>}
      {message && <p role="status" className="mt-4 text-sm">{message}</p>}
    </form>
    {preview && <section className={panel} aria-label="表單預覽">
      <h2 className="mb-4 font-semibold">表單預覽</h2>
      <fieldset disabled><RecruitmentFields fields={draft.fields} /></fieldset>
      {!draft.fields.length && <p className="text-sm">請先新增題目。</p>}
    </section>}
  </div>
}

interface ApplicationSummary { id: number; submission_id: string; submitted_at: string }
interface Application extends ApplicationSummary {
  fields: RecruitmentField[]
  answers: Record<string, string | string[]>
  attachments: Record<string, {name: string; format: FileFormat; size: number}>
}
interface ApplicationPage { results: ApplicationSummary[]; count: number; next: string | null; previous: string | null }

function applicationDate(value: string) {
  return new Date(value).toLocaleString('zh-TW', {dateStyle: 'medium', timeStyle: 'short'})
}

function ApplicationInbox({client}: {client: string}) {
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<number | null>(null)
  const list = useQuery({
    queryKey: ['recruitment-applications', client, page],
    queryFn: () => adminApi.get('/recruitment/', {params: {page}}) as unknown as Promise<ApplicationPage>,
    gcTime: 0,
  })
  const details = useQuery({
    queryKey: ['recruitment-application', client, selected],
    queryFn: () => adminApi.get(`/recruitment/${selected}/`) as unknown as Promise<Application>,
    enabled: selected !== null,
    gcTime: 0,
  })
  if (selected !== null) return <section className={panel}>
    <button type="button" className={button} onClick={() => setSelected(null)}>返回收件列表</button>
    {details.isError && <p role="alert" className="mt-4 text-sm">無法載入應徵資料。<button type="button" className="ml-2 underline" onClick={() => details.refetch()}>重試</button></p>}
    {details.isPending && <p role="status" className="mt-4 text-sm">載入中…</p>}
    {details.data && <>
      <h2 className="mt-5 font-semibold">應徵資料</h2>
      <p className="mt-1 break-all text-sm">{applicationDate(details.data.submitted_at)} · {details.data.submission_id}</p>
      <dl className="mt-4 space-y-4">
        {details.data.fields.map(field => {
          const answer = details.data.answers[field.id]
          const attachment = details.data.attachments[field.id]
          return <div key={field.id} className="border-t border-gray-200 pt-3 dark:border-gray-700">
            <dt className="font-medium">{field.label}</dt>
            <dd className="mt-1 whitespace-pre-wrap break-words text-sm">
              {attachment ? <a className="text-violet-600 underline dark:text-violet-300" download
                href={`/api/admin/${encodeURIComponent(client)}/recruitment/${selected}/attachments/${field.id}/`}>{attachment.name}</a>
              : (Array.isArray(answer) ? answer.join('、') : answer) || '未填寫'}
            </dd>
          </div>
        })}
      </dl>
    </>}
  </section>

  return <section className={panel}>
    <h2 className="font-semibold">應徵收件</h2>
    {list.isError && <p role="alert" className="mt-4 text-sm">無法載入收件。<button type="button" className="ml-2 underline" onClick={() => list.refetch()}>重試</button></p>}
    {list.isPending && <p role="status" className="mt-4 text-sm">載入中…</p>}
    {list.data && <>
      {!list.data.results.length && <p className="mt-4 text-sm">目前沒有應徵資料。</p>}
      <ul className="divide-y divide-gray-200 dark:divide-gray-700">
        {list.data.results.map(application => <li key={application.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
          <div className="min-w-0 text-sm">
            <p>{applicationDate(application.submitted_at)}</p>
            <p className="break-all opacity-70">{application.submission_id}</p>
          </div>
          <button type="button" className={button} onClick={() => setSelected(application.id)}>查看應徵</button>
        </li>)}
      </ul>
      {list.data.count > 20 && <div className="mt-4 flex items-center gap-3">
        <button type="button" className={button} disabled={!list.data.previous} onClick={() => setPage(value => value - 1)}>上一頁</button>
        <span className="text-sm">第 {page} 頁</span>
        <button type="button" className={button} disabled={!list.data.next} onClick={() => setPage(value => value + 1)}>下一頁</button>
      </div>}
    </>}
  </section>
}

function RecruitmentConsole({client}: {client: string}) {
  const [tab, setTab] = useState<'settings' | 'inbox'>('settings')
  const settings = useQuery({
    queryKey: ['recruitment-settings', client],
    queryFn: () => adminApi.get('/recruitment/settings/') as unknown as Promise<RecruitmentSettings>,
    refetchOnWindowFocus: false,
  })
  return <main className="space-y-5 text-gray-900 dark:text-gray-100">
    <h1 className="text-2xl font-semibold">教練招募</h1>
    <div className="flex gap-2">
      <button className={tab === 'settings' ? primary : button} type="button" aria-pressed={tab === 'settings'} onClick={() => setTab('settings')}>表單設定</button>
      <button className={tab === 'inbox' ? primary : button} type="button" aria-pressed={tab === 'inbox'} onClick={() => setTab('inbox')}>應徵收件</button>
    </div>
    <div hidden={tab !== 'settings'}>
      {settings.isError && <p role="alert">無法載入設定。<button type="button" className="ml-2 underline" onClick={() => settings.refetch()}>重試</button></p>}
      {settings.isPending && <p role="status">載入中…</p>}
      {settings.data && <FormEditor settings={settings.data} />}
    </div>
    {tab === 'inbox' && <ApplicationInbox client={client} />}
  </main>
}

export default function RecruitmentPage() {
  const client = currentClientCode()
  return <RecruitmentConsole key={client} client={client} />
}
