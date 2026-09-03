import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Calculator, ClipboardCheck, Link2, Loader2, Plus, Save } from 'lucide-react'
import { fetchCampuses } from '../api/campuses'
import { fetchCoaches } from '../api/coaches'
import {
  calculatePayroll, createStaffBookingLink, fetchEvaluations, fetchNotificationDeliveries,
  fetchNotificationTemplates, fetchPayrollStatements, fetchStaffBookingLinks, fetchPayRules, saveNotificationTemplate, savePayRule,
  fetchInsuranceRecords, completeInsuranceRecord,
  updateEvaluation, addEvaluationMedia, type Evaluation,
} from '../api/operations'
import { useNotification } from '../context'

const PRIMARY = '#8b5cf6'
type Tab = 'notifications' | 'payroll' | 'evaluations' | 'insurance' | 'links'

const tabs: { id: Tab; label: string; icon: typeof Bell }[] = [
  { id: 'notifications', label: '自動通知', icon: Bell },
  { id: 'payroll', label: '薪資結算', icon: Calculator },
  { id: 'evaluations', label: '學習評量', icon: ClipboardCheck },
  { id: 'insurance', label: '保險與聲明書', icon: ClipboardCheck },
  { id: 'links', label: '代客訂課連結', icon: Link2 },
]

const descriptions: Record<Tab, string> = {
  notifications: '設定 Email、LINE 與站內通知，並查看最近發送結果。',
  payroll: '設定教練薪資規則，依校區與期間完成結算。',
  evaluations: '記錄學員進度、教練評語與課程媒體。',
  insurance: '集中處理尚未完成的保險資料與聲明書。',
  links: '建立有校區歸屬的連結，協助客人完成訂課。',
}

const inputClass = 'w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white'
const cardClass = 'rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800'

export default function OperationsHubPage({ initialTab = 'notifications', fixed = false }: { initialTab?: Tab; fixed?: boolean }) {
  const [tab, setTab] = useState<Tab>(initialTab)
  const visibleTabs = fixed ? tabs.filter(item => item.id === initialTab) : tabs
  const currentTab = tabs.find(item => item.id === tab) || tabs[0]
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{fixed ? currentTab.label : '進階營運'}</h1>
        <p className="mt-1 text-gray-500 dark:text-gray-400">{fixed ? descriptions[currentTab.id] : '通知、薪資、評量與代客訂課集中在這裡。'}</p>
      </div>
      {!fixed && <div className="grid grid-cols-2 gap-2 rounded-xl bg-gray-100 p-2 dark:bg-gray-900 md:grid-cols-5">
        {visibleTabs.map((item) => <button key={item.id} onClick={() => setTab(item.id)} className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold ${tab === item.id ? 'bg-white text-violet-600 shadow-sm dark:bg-gray-700' : 'text-gray-500 dark:text-gray-400'}`}><item.icon size={16} />{item.label}</button>)}
      </div>}
      {tab === 'notifications' && <NotificationsPanel />}
      {tab === 'payroll' && <PayrollPanel />}
      {tab === 'evaluations' && <EvaluationsPanel />}
      {tab === 'insurance' && <InsurancePanel />}
      {tab === 'links' && <BookingLinksPanel />}
    </div>
  )
}

function NotificationsPanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const { data: campuses = [] } = useQuery({ queryKey: ['admin', 'campuses'], queryFn: fetchCampuses })
  const { data: templates = [], isLoading } = useQuery({ queryKey: ['admin', 'notification-templates'], queryFn: fetchNotificationTemplates })
  const { data: deliveries = [] } = useQuery({ queryKey: ['admin', 'notification-deliveries'], queryFn: fetchNotificationDeliveries })
  const [form, setForm] = useState({ name: '', campus: '', event: 'pre_course', channel: 'email', subject: '', body: '', days_before: '3' })
  const save = useMutation({ mutationFn: () => saveNotificationTemplate({ ...form, campus: form.campus ? Number(form.campus) : null, days_before: Number(form.days_before), is_active: true }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'notification-templates'] }); setForm({ name: '', campus: '', event: 'pre_course', channel: 'email', subject: '', body: '', days_before: '3' }); notify.success('通知範本已儲存') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '儲存失敗') })
  return <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
    <section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">新增通知範本</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">選事件、管道與時間，系統會依校區自動排程。</p><div className="space-y-3">
      <input className={inputClass} placeholder="範本名稱，例如：課前三天提醒" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
      <select className={inputClass} value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value })}><option value="">全部校區</option>{campuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
      <div className="grid grid-cols-2 gap-2"><select className={inputClass} value={form.event} onChange={e => setForm({ ...form, event: e.target.value })}><option value="order_created">訂單成立</option><option value="payment_confirmed">付款完成</option><option value="pre_course">課前提醒</option><option value="missing_documents">資料未完成</option><option value="line_group">LINE 群組邀請</option><option value="evaluation_due">評量未完成</option></select><select className={inputClass} value={form.channel} onChange={e => setForm({ ...form, channel: e.target.value })}><option value="email">Email</option><option value="line">LINE</option><option value="in_app">站內通知</option></select></div>
      <input className={inputClass} type="number" min="0" value={form.days_before} onChange={e => setForm({ ...form, days_before: e.target.value })} placeholder="課前幾天" />
      <input className={inputClass} placeholder="信件主旨" value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} />
      <textarea className={`${inputClass} min-h-28`} placeholder="通知內容" value={form.body} onChange={e => setForm({ ...form, body: e.target.value })} />
      <button disabled={!form.name || !form.body || save.isPending} onClick={() => save.mutate()} className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}>{save.isPending ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}儲存範本</button>
    </div></section>
    <div className="space-y-5"><section className={cardClass}><h2 className="mb-3 font-semibold text-gray-900 dark:text-white">目前範本</h2>{isLoading ? <Loader2 className="animate-spin" /> : <div className="space-y-2">{templates.map(t => <div key={t.id} className="rounded-lg border border-gray-100 p-3 text-sm dark:border-gray-700"><div className="flex justify-between"><b>{t.name}</b><span className="text-xs text-gray-500 dark:text-gray-400">已排程 {t.delivery_count} 次</span></div><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{t.channel.toUpperCase()} · {t.event} · {t.days_before ? `提前 ${t.days_before} 天` : '立即'}</p></div>)}{!templates.length && <Empty text="尚無範本，先用左側建立一個。" />}</div>}</section>
    <section className={cardClass}><h2 className="mb-3 font-semibold text-gray-900 dark:text-white">最近發送佇列</h2><div className="space-y-2">{deliveries.slice(0, 10).map(d => <div key={d.id} className="flex items-center justify-between rounded-lg bg-gray-50 p-3 text-sm dark:bg-gray-900"><div><b>{d.template_name}</b><p className="text-xs text-gray-500 dark:text-gray-400">{d.order_number} · {d.recipient}</p></div><span className="text-xs">{d.status}</span></div>)}{!deliveries.length && <Empty text="尚無待發送通知。" />}</div></section></div>
  </div>
}

function PayrollPanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const { data: campuses = [] } = useQuery({ queryKey: ['admin', 'campuses'], queryFn: fetchCampuses })
  const { data: coaches = [] } = useQuery({ queryKey: ['admin', 'coaches'], queryFn: fetchCoaches })
  const { data: statements = [], isLoading } = useQuery({ queryKey: ['admin', 'payroll'], queryFn: fetchPayrollStatements })
  const { data: rules = [] } = useQuery({ queryKey: ['admin', 'pay-rules'], queryFn: fetchPayRules })
  const now = new Date(); const first = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`; const last = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().slice(0, 10)
  const [form, setForm] = useState({ coach: '', campus: '', period_start: first, period_end: last })
  const [rule, setRule] = useState({ coach: '', discipline: 'snowboard', certification_level: '', hourly_rate: '', specified_fee: '0', referral_percent: '10', assistance_hour_factor: '0.5', supervisor_allowance: '0' })
  const run = useMutation({ mutationFn: () => calculatePayroll({ coach: Number(form.coach), campus: Number(form.campus), period_start: form.period_start, period_end: form.period_end }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'payroll'] }); notify.success('薪資已重新計算') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '計算失敗') })
  const saveRule = useMutation({ mutationFn: () => savePayRule({ ...rule, coach: Number(rule.coach), hourly_rate: rule.hourly_rate, specified_fee: Number(rule.specified_fee), referral_percent: rule.referral_percent, assistance_hour_factor: rule.assistance_hour_factor, supervisor_allowance: Number(rule.supervisor_allowance), is_active: true }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'pay-rules'] }); notify.success('教練薪資規則已儲存') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '規則儲存失敗') })
  const total = useMemo(() => statements.reduce((sum, s) => sum + s.total_amount, 0), [statements])
  return <div className="space-y-5"><section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">教練薪資規則</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">每位教練、每個板種可不同。介紹費預設為折扣後課程費的 10%，不含附加費。</p><div className="grid items-end gap-3 md:grid-cols-4">
    <Field label="教練"><select className={inputClass} value={rule.coach} onChange={e => setRule({ ...rule, coach: e.target.value })}><option value="">請選教練</option>{coaches.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    <Field label="工作類型"><select className={inputClass} value={rule.discipline} onChange={e => setRule({ ...rule, discipline: e.target.value })}><option value="snowboard">單板</option><option value="ski">雙板</option><option value="photo">攝影</option></select></Field>
    <Field label="證照級別（可留空）"><input className={inputClass} value={rule.certification_level} onChange={e => setRule({ ...rule, certification_level: e.target.value })} /></Field>
    <Field label="每小時薪資"><input className={inputClass} type="number" min="0" value={rule.hourly_rate} onChange={e => setRule({ ...rule, hourly_rate: e.target.value })} /></Field>
    <Field label="每組指定教練費"><input className={inputClass} type="number" min="0" value={rule.specified_fee} onChange={e => setRule({ ...rule, specified_fee: e.target.value })} /></Field>
    <Field label="介紹費百分比"><input className={inputClass} type="number" min="0" max="100" step="0.1" value={rule.referral_percent} onChange={e => setRule({ ...rule, referral_percent: e.target.value })} /></Field>
    <Field label="每組裝備協助時數"><input className={inputClass} type="number" min="0" step="0.1" value={rule.assistance_hour_factor} onChange={e => setRule({ ...rule, assistance_hour_factor: e.target.value })} /></Field>
    <Field label="每期主管加給"><input className={inputClass} type="number" min="0" value={rule.supervisor_allowance} onChange={e => setRule({ ...rule, supervisor_allowance: e.target.value })} /></Field>
    <button disabled={!rule.coach || !rule.hourly_rate || saveRule.isPending} onClick={() => saveRule.mutate()} className="rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}>儲存規則</button>
  </div><div className="mt-4 flex flex-wrap gap-2">{rules.map(r => <span key={r.id} className="rounded-full bg-gray-100 px-3 py-1 text-xs dark:bg-gray-700">{r.coach_name} · {r.discipline} · NT$ {Number(r.hourly_rate).toLocaleString()}/時</span>)}</div></section><section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">計算教練薪資</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">完成課程才列入；時薪、指定費、介紹費、裝備協助與主管加給會分開計算。</p><div className="grid items-end gap-3 md:grid-cols-5">
    <Field label="校區"><select className={inputClass} value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value })}><option value="">請選校區</option>{campuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    <Field label="教練"><select className={inputClass} value={form.coach} onChange={e => setForm({ ...form, coach: e.target.value })}><option value="">請選教練</option>{coaches.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    <Field label="結算開始日"><input className={inputClass} type="date" value={form.period_start} onChange={e => setForm({ ...form, period_start: e.target.value })} /></Field>
    <Field label="結算結束日"><input className={inputClass} type="date" value={form.period_end} onChange={e => setForm({ ...form, period_end: e.target.value })} /></Field>
    <button disabled={!form.coach || !form.campus || run.isPending} onClick={() => run.mutate()} className="rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}>{run.isPending ? '計算中…' : '開始計算'}</button>
  </div></section>
    <section className={cardClass}><div className="mb-4 flex justify-between"><h2 className="font-semibold text-gray-900 dark:text-white">薪資單</h2><b className="text-violet-600">合計 NT$ {total.toLocaleString()}</b></div>{isLoading ? <Loader2 className="animate-spin" /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-xs text-gray-500 dark:text-gray-400"><tr><th className="py-2">教練／校區</th><th>期間</th><th>課程</th><th>指定＋介紹＋協助＋加給</th><th className="text-right">應付</th></tr></thead><tbody>{statements.map(s => <tr key={s.id} className="border-t border-gray-100 dark:border-gray-700"><td className="py-3"><b>{s.coach_name}</b><p className="text-xs text-gray-500 dark:text-gray-400">{s.campus_name}</p></td><td>{s.period_start}～{s.period_end}</td><td>NT$ {s.course_pay.toLocaleString()}</td><td>NT$ {(s.specified_fees + s.referral_commission + s.assistance_pay + s.supervisor_allowance).toLocaleString()}</td><td className="text-right font-bold">NT$ {s.total_amount.toLocaleString()}</td></tr>)}</tbody></table>{!statements.length && <Empty text="尚無薪資單。選擇校區、教練與期間後開始計算。" />}</div>}</section></div>
}

function EvaluationsPanel() {
  const { data: rows = [], isLoading } = useQuery({ queryKey: ['admin', 'evaluations'], queryFn: fetchEvaluations })
  return <section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">學員進度與課程紀錄</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">點「填寫評量」即可紀錄教練評語、學習進度、雪道與照片／影片。</p>{isLoading ? <Loader2 className="animate-spin" /> : <div className="grid gap-3 xl:grid-cols-2">{rows.map(r => <EvaluationCard key={r.id} row={r} />)}{!rows.length && <Empty text="尚無課程評量。課程建立學員資料後即可開始填寫。" />}</div>}</section>
}

function EvaluationCard({ row }: { row: Evaluation }) {
  const qc = useQueryClient(); const notify = useNotification()
  const [editing, setEditing] = useState(false)
  const [notes, setNotes] = useState(row.coach_notes || '')
  const [progress, setProgress] = useState(Object.entries(row.learning_progress || {}).map(([key, value]) => `${key}：${value}`).join('\n'))
  const [trails, setTrails] = useState((row.trail_names || []).join('、'))
  const [mediaUrl, setMediaUrl] = useState('')
  const [mediaType, setMediaType] = useState<'photo' | 'video'>('photo')
  const save = useMutation({ mutationFn: async () => {
    const learning_progress = Object.fromEntries(progress.split('\n').map(line => line.split(/[：:]/, 2).map(v => v.trim())).filter(pair => pair[0]))
    await updateEvaluation(row.id, { coach_notes: notes, learning_progress, trail_names: trails.split(/[、,]/).map(v => v.trim()).filter(Boolean), completed_at: new Date().toISOString() })
    if (mediaUrl.trim()) await addEvaluationMedia(row.id, { media_type: mediaType, url: mediaUrl.trim(), is_public: false })
  }, onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'evaluations'] }); setEditing(false); setMediaUrl(''); notify.success('評量已儲存') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '評量儲存失敗') })
  return <article className="rounded-xl border border-gray-100 p-4 dark:border-gray-700"><div className="flex items-start justify-between gap-3"><div><b>{row.member_name}</b><p className="mt-1 text-xs text-violet-600">{row.course_date} · 教練：{row.coach_name || '尚未指定'}</p></div><button onClick={() => setEditing(!editing)} className="shrink-0 rounded-lg border border-violet-200 px-3 py-1.5 text-xs font-semibold text-violet-600">{editing ? '收起' : '填寫評量'}</button></div>
    {!editing ? <><p className="mt-3 text-sm text-gray-600 dark:text-gray-300">{row.coach_notes || '尚無評語'}</p>{row.trail_names?.length > 0 && <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">完成雪道：{row.trail_names.join('、')}</p>}<p className="mt-2 text-xs text-gray-400">媒體 {row.media?.length || 0} 個 · {row.completed_at ? '已完成' : '待填寫'}</p></> : <div className="mt-4 space-y-3">
      <Field label="給學員的教練評語"><textarea className={`${inputClass} min-h-24`} value={notes} onChange={e => setNotes(e.target.value)} placeholder="用簡單、鼓勵的方式說明這堂課的表現" /></Field>
      <Field label="學習進度（每行一項，例如：煞車：已完成）"><textarea className={`${inputClass} min-h-20`} value={progress} onChange={e => setProgress(e.target.value)} placeholder={'煞車：已完成\n轉彎：持續練習'} /></Field>
      <Field label="完成雪道"><input className={inputClass} value={trails} onChange={e => setTrails(e.target.value)} placeholder="用頓號分隔，例如：綠線、Family Run" /></Field>
      <Field label="照片或影片網址（選填）"><div className="grid gap-2 sm:grid-cols-[120px_1fr]"><select className={inputClass} value={mediaType} onChange={e => setMediaType(e.target.value as 'photo' | 'video')}><option value="photo">照片</option><option value="video">影片</option></select><input className={inputClass} type="url" value={mediaUrl} onChange={e => setMediaUrl(e.target.value)} placeholder="https://..." /></div></Field>
      <p className="text-xs text-gray-500 dark:text-gray-400">媒體預設只供內部查看；公開到官網需再到圖庫管理確認。</p>
      <button disabled={save.isPending} onClick={() => save.mutate()} className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}>{save.isPending ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}儲存並標示完成</button>
    </div>}
  </article>
}

function BookingLinksPanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const { data: campuses = [] } = useQuery({ queryKey: ['admin', 'campuses'], queryFn: fetchCampuses })
  const { data: rows = [] } = useQuery({ queryKey: ['admin', 'staff-booking-links'], queryFn: fetchStaffBookingLinks })
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 16)
  const [form, setForm] = useState({ campus: '', title: '', expires_at: tomorrow })
  const create = useMutation({ mutationFn: () => createStaffBookingLink({ campus: Number(form.campus), title: form.title, expires_at: new Date(form.expires_at).toISOString() }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'staff-booking-links'] }); setForm({ ...form, title: '' }); notify.success('訂課連結已建立') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '建立失敗') })
  const copy = async (url: string) => { await navigator.clipboard.writeText(url); notify.success('連結已複製') }
  return <div className="space-y-5"><section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">建立代客訂課連結</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">先指定訂單歸屬校區。把連結傳給客人後，來源會保留建立人員資訊。</p><div className="grid items-end gap-3 md:grid-cols-4"><Field label="訂單歸屬校區"><select className={inputClass} value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value })}><option value="">請選校區</option>{campuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field><Field label="用途／客人名稱"><input className={inputClass} placeholder="例如：王小姐三日課" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></Field><Field label="連結失效時間"><input className={inputClass} type="datetime-local" value={form.expires_at} onChange={e => setForm({ ...form, expires_at: e.target.value })} /></Field><button disabled={!form.campus || !form.title || create.isPending} onClick={() => create.mutate()} className="flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}><Plus size={16} />建立連結</button></div></section><section className={cardClass}><div className="space-y-3">{rows.map(r => <div key={r.id} className="flex flex-col gap-3 rounded-lg border border-gray-100 p-4 dark:border-gray-700 sm:flex-row sm:items-center sm:justify-between"><div><b>{r.title}</b><p className="text-xs text-gray-500 dark:text-gray-400">{r.is_available ? '可使用' : '已失效'} · 到期 {new Date(r.expires_at).toLocaleString()}</p></div><button disabled={!r.is_available} onClick={() => copy(r.url)} className="rounded-lg border border-violet-200 px-3 py-2 text-sm font-semibold text-violet-600 disabled:opacity-40">複製連結</button></div>)}{!rows.length && <Empty text="尚未建立連結。" />}</div></section></div>
}

function InsurancePanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const { data: rows = [], isLoading } = useQuery({ queryKey: ['admin', 'insurance-records'], queryFn: fetchInsuranceRecords })
  const complete = useMutation({ mutationFn: ({ id, field }: { id: number; field: 'insurance' | 'waiver' }) => completeInsuranceRecord(id, field), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'insurance-records'] }); notify.success('完成狀態已更新') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '更新失敗') })
  return <section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">待補保險與聲明書</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">只顯示尚未完成的學員，完成後會自動離開清單。</p>{isLoading ? <Loader2 className="animate-spin" /> : <div className="space-y-3">{rows.map(row => <div key={row.id} className="flex flex-col gap-3 rounded-lg border border-gray-100 p-4 dark:border-gray-700 md:flex-row md:items-center md:justify-between"><div><b>{row.member_name}</b><p className="text-xs text-gray-500 dark:text-gray-400">{row.order_number} · {row.campus_name} · {row.course_dates.join('、')}</p></div><div className="flex gap-2">{!row.insurance_completed_at && <button onClick={() => complete.mutate({ id: row.id, field: 'insurance' })} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white">保險已完成</button>}{!row.waiver_completed_at && <button onClick={() => complete.mutate({ id: row.id, field: 'waiver' })} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white">聲明書已完成</button>}</div></div>)}{!rows.length && <Empty text="所有學員資料都已完成。" />}</div>}</section>
}

function Empty({ text }: { text: string }) { return <div className="py-8 text-center text-sm text-gray-400">{text}</div> }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="block"><span className="mb-1 block text-xs font-semibold text-gray-600 dark:text-gray-300">{label}</span>{children}</label> }
