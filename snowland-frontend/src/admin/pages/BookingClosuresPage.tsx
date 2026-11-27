import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import {
  createBookingClosure, deleteBookingClosure, fetchBookingClosureOptions, fetchBookingClosures,
} from '../api/bookingClosures'

const listKey = ['admin', 'booking-closures']
const field = 'mt-1 block min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 dark:border-gray-600 dark:bg-gray-900'
const panel = 'rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 sm:p-5'

function closureError(error: unknown, fallback: string) {
  const data = isAxiosError(error) ? error.response?.data : undefined
  if (typeof data?.detail === 'string' && /[\u3400-\u9fff]/.test(data.detail)) return data.detail
  const messages = Object.values(data ?? {}).flat().filter(
    (message): message is string => typeof message === 'string' && /[\u3400-\u9fff]/.test(message),
  )
  return messages.join('，') || fallback
}

export default function BookingClosuresPage() {
  const queryClient = useQueryClient()
  const rules = useQuery({ queryKey: listKey, queryFn: fetchBookingClosures })
  const options = useQuery({ queryKey: [...listKey, 'options'], queryFn: fetchBookingClosureOptions })
  const [scope, setScope] = useState('')
  const [resort, setResort] = useState('')
  const [template, setTemplate] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [singleDay, setSingleDay] = useState(true)
  const [allDay, setAllDay] = useState(true)
  const [sessionId, setSessionId] = useState('')
  const [reason, setReason] = useState('')
  const [feedback, setFeedback] = useState<{ message: string; error?: boolean }>()
  const create = useMutation({
    mutationFn: createBookingClosure,
    onSuccess: async ({ msg, warning }) => {
      setFeedback({ message: warning || msg })
      setReason('')
      await queryClient.invalidateQueries({ queryKey: listKey, exact: true })
    },
    onError: error => setFeedback({ error: true, message: closureError(error, '無法新增停收規則，請檢查輸入後再試。') }),
  })
  const remove = useMutation({
    mutationFn: deleteBookingClosure,
    onSuccess: async () => {
      setFeedback({ message: '停收規則已刪除' })
      await queryClient.invalidateQueries({ queryKey: listKey, exact: true })
    },
    onError: error => setFeedback({ error: true, message: closureError(error, '無法刪除停收規則，請再試一次。') }),
  })

  const busy = create.isPending || remove.isPending
  const canPickResort = Boolean(options.data?.resorts.length)
  const canPickTemplate = Boolean(options.data?.templates.some(row => row.can_close_all_resorts))
  const canPickBoth = canPickResort && options.data?.can_manage_templates
    && options.data.templates.some(row => row.resorts.length)
  const templates = (options.data?.templates ?? []).filter(row => scope === 'template'
    ? row.can_close_all_resorts
    : row.resorts.includes(Number(resort)))
  const sessions = templates.find(row => row.id === Number(template))?.sessions ?? []
  const session = sessions.find(row => row.id === Number(sessionId))

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!scope || busy || (!allDay && !session)) return
    setFeedback(undefined)
    create.mutate({
      resort: scope === 'template' ? null : Number(resort),
      course_template: scope === 'resort' ? null : Number(template),
      date_from: dateFrom,
      date_to: singleDay ? dateFrom : dateTo,
      start_time: allDay ? null : session!.start_time,
      end_time: allDay ? null : session!.end_time,
      reason: reason.trim(),
    })
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5 text-gray-900 dark:text-gray-100">
      <header>
        <h1 className="text-2xl font-bold">停收日期</h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">這只會停止新的前台訂課，已成立的訂單不受影響。</p>
      </header>
      {options.data?.enabled === false && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100">
        此租戶已暫停套用停收規則，仍可新增或刪除。
      </p>}
      {feedback && <p role={feedback.error ? 'alert' : 'status'} className={`rounded-lg p-3 text-sm ${
        feedback.error ? 'bg-red-50 text-red-900 dark:bg-red-950 dark:text-red-100' : 'bg-violet-50 text-violet-900 dark:bg-violet-950 dark:text-violet-100'
      }`}>{feedback.message}</p>}
      <section className={panel}>
        <h2 className="font-semibold">新增停收規則</h2>
        {options.isPending && <p role="status">正在載入雪場與課程時段…</p>}
        {options.isError && <p role="alert">無法載入雪場與課程時段。 <button className="underline" onClick={() => options.refetch()}>重新載入</button></p>}
        {options.data && !canPickResort && !canPickTemplate && <p className="mt-2 text-sm">目前校區範圍沒有可管理的雪場或課程模板。</p>}
        {(canPickResort || canPickTemplate) && <form onSubmit={submit} className="mt-4">
          <fieldset disabled={busy} className="grid gap-4 text-sm sm:grid-cols-2">
            <label>停收範圍
              <select className={field} required value={scope} onChange={event => {
                setScope(event.target.value); setResort(''); setTemplate(''); setSessionId('')
              }}>
                <option value="">請選擇範圍</option>
                {canPickResort && <option value="resort">雪場的所有課程</option>}
                {canPickTemplate && <option value="template">課程模板的所有適用雪場</option>}
                {canPickBoth && <option value="both">指定雪場與課程模板</option>}
              </select>
            </label>
            {scope && scope !== 'template' && <label>雪場
              <select className={field} required value={resort} onChange={event => {
                setResort(event.target.value); setTemplate(''); setSessionId('')
              }}>
                <option value="">請選擇雪場</option>
                {options.data?.resorts.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </label>}
            {(scope === 'template' || scope === 'both' || (scope === 'resort' && !allDay)) && <label>
              {scope === 'resort' ? '參考時段的課程模板' : '課程模板'}
              <select className={field} required value={template} onChange={event => {
                setTemplate(event.target.value); setSessionId('')
              }}>
                <option value="">請選擇課程模板</option>
                {templates.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </label>}
            <label>日期類型
              <select className={field} value={singleDay ? 'single' : 'range'} onChange={event => setSingleDay(event.target.value === 'single')}>
                <option value="single">單日</option>
                <option value="range">日期區間</option>
              </select>
            </label>
            <label>{singleDay ? '日期' : '開始日期'}
              <input className={field} required type="date" value={dateFrom} onChange={event => setDateFrom(event.target.value)} />
            </label>
            {!singleDay && <label>結束日期
              <input className={field} required type="date" min={dateFrom || undefined} value={dateTo} onChange={event => setDateTo(event.target.value)} />
            </label>}
            <label>停收時段
              <select className={field} value={allDay ? 'all' : 'session'} onChange={event => {
                setAllDay(event.target.value === 'all'); setSessionId('')
              }}>
                <option value="all">全天</option>
                <option value="session">指定時段</option>
              </select>
            </label>
            {!allDay && <label>課程時段
              <select className={field} required value={sessionId} onChange={event => setSessionId(event.target.value)}>
                <option value="">{template && !sessions.length ? '此課程沒有啟用中的時段' : '請選擇時段'}</option>
                {sessions.map(row => <option key={row.id} value={row.id}>{row.start_time.slice(0, 5)}–{row.end_time.slice(0, 5)}</option>)}
              </select>
              <span className="mt-1 block text-xs text-gray-600 dark:text-gray-300">時間重疊的課程時段都會停收。</span>
            </label>}
            <label className="sm:col-span-2">內部原因（選填）
              <textarea className={field} maxLength={255} value={reason} onChange={event => setReason(event.target.value)} />
            </label>
            <div className="sm:col-span-2">
              <button type="submit" disabled={!scope || (!allDay && !session)} className="min-h-11 rounded-lg bg-violet-700 px-4 font-medium text-white disabled:opacity-50">
                {create.isPending ? '新增中…' : '新增停收規則'}
              </button>
            </div>
          </fieldset>
        </form>}
      </section>
      <section className={panel}>
        <h2 className="font-semibold">停收規則</h2>
        {rules.isPending && <p role="status">正在載入停收規則…</p>}
        {rules.isError && <p role="alert">無法載入停收規則。 <button className="underline" onClick={() => rules.refetch()}>重新載入</button></p>}
        {rules.data?.length === 0 && <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">目前沒有停收規則。</p>}
        <ul className="mt-2 divide-y divide-gray-200 dark:divide-gray-700">
          {rules.data?.map(rule => {
            const name = [rule.resort_name, rule.template_name].filter(Boolean).join('／')
            const period = rule.date_from === rule.date_to ? rule.date_from : `${rule.date_from}～${rule.date_to}`
            const time = rule.start_time && rule.end_time ? `${rule.start_time.slice(0, 5)}–${rule.end_time.slice(0, 5)}` : '全天'
            return <li key={rule.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="min-w-0 break-words">
                <p className="font-medium">{name}</p>
                <p className="text-sm">{period} · {time}</p>
                {rule.reason && <p className="text-sm text-gray-600 dark:text-gray-300">{rule.reason}</p>}
              </div>
              <button type="button" disabled={busy} aria-label={`刪除 ${name} ${period} ${time} 的停收規則`}
                className="min-h-11 rounded-lg border border-red-200 px-3 text-sm text-red-700 disabled:opacity-50 dark:text-red-300"
                onClick={() => {
                  if (window.confirm(`確定刪除「${name}」${period} ${time} 的停收規則？`)) {
                    setFeedback(undefined); remove.mutate(rule.id)
                  }
                }}>刪除</button>
            </li>
          })}
        </ul>
      </section>
    </div>
  )
}
