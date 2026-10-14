import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Calculator, ClipboardCheck, Link2, Loader2, Plus, Save } from 'lucide-react'
import { fetchCampuses } from '../api/campuses'
import { fetchAdminMe } from '../api/auth'
import { hasAdminPermission } from '../permissions'
import { fetchCoaches } from '../api/coaches'
import { fetchCourseCategories, fetchCourseTemplates } from '../api/courses'
import {
  calculatePayroll, createStaffBookingLink, fetchEvaluations, fetchNotificationDeliveries,
  fetchNotificationTemplates, fetchPayrollStatements, fetchStaffBookingLinks, fetchPayRules, saveNotificationTemplate, savePayRule, addPayrollAdjustment,
  fetchInsuranceRecords, completeInsuranceRecord,
  updateEvaluation, addEvaluationMedia, type Evaluation,
} from '../api/operations'
import { useNotification } from '../context'
import { learningProgressFromText, learningProgressToText } from '@/utils/learningProgress'

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
const disciplineNames: Record<string, string> = { snowboard: '單板', ski: '雙板', photo: '攝影' }
const displayPayrollDescription = (description: string) => description.replace(/\b(snowboard|ski|photo)\b/g, discipline => disciplineNames[discipline] || discipline)
const teachingHours = (lines: { line_type: string; quantity: string }[] = []) =>
  lines.filter(line => line.line_type === 'course').reduce((sum, line) => sum + Number(line.quantity), 0)
const notificationEvents: Record<string, string> = { order_created: '訂單成立', payment_confirmed: '付款完成', pre_course: '課前提醒', missing_documents: '資料未完成', line_group: 'LINE 群組邀請', evaluation_due: '評量未完成' }
const notificationChannels: Record<string, string> = { email: 'Email', line: 'LINE', in_app: '站內通知' }
const deliveryStatuses: Record<string, string> = { scheduled: '待發送', sent: '已發送', failed: '發送失敗', cancelled: '已取消' }

function useScopedCampuses() {
  const { data: adminMe } = useQuery({ queryKey: ['admin', 'me'], queryFn: fetchAdminMe })
  const canManageCampuses = hasAdminPermission(adminMe?.user, 'campuses')
  const { data: managedCampuses = [] } = useQuery({ queryKey: ['admin', 'campuses'], queryFn: fetchCampuses, enabled: canManageCampuses })
  const allCampuses = canManageCampuses ? managedCampuses : (adminMe?.user?.campuses || [])
  const selectedCampus = window.localStorage.getItem('snowland_admin_campus_scope') || 'all'
  return {
    campuses: selectedCampus === 'all' ? allCampuses : allCampuses.filter(c => String(c.id) === selectedCampus),
    selectedCampus: selectedCampus === 'all' ? '' : selectedCampus,
  }
}

export default function OperationsHubPage({ initialTab = 'notifications', fixed = false }: { initialTab?: Tab; fixed?: boolean }) {
  const [tab, setTab] = useState<Tab>(initialTab)
  // Fixed Console routes reuse this component instance; the route prop must win over stale tab state.
  const activeTab = fixed ? initialTab : tab
  const visibleTabs = fixed ? tabs.filter(item => item.id === initialTab) : tabs
  const currentTab = tabs.find(item => item.id === activeTab) || tabs[0]
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{fixed ? currentTab.label : '進階營運'}</h1>
        <p className="mt-1 text-gray-500 dark:text-gray-400">{fixed ? descriptions[currentTab.id] : '通知、薪資、評量與代客訂課集中在這裡。'}</p>
      </div>
      {!fixed && <div className="grid grid-cols-2 gap-2 rounded-xl bg-gray-100 p-2 dark:bg-gray-900 md:grid-cols-5">
        {visibleTabs.map((item) => <button key={item.id} onClick={() => setTab(item.id)} className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold ${activeTab === item.id ? 'bg-white text-violet-600 shadow-sm dark:bg-gray-700' : 'text-gray-500 dark:text-gray-400'}`}><item.icon size={16} />{item.label}</button>)}
      </div>}
      {activeTab === 'notifications' && <NotificationsPanel />}
      {activeTab === 'payroll' && <PayrollPanel />}
      {activeTab === 'evaluations' && <EvaluationsPanel />}
      {activeTab === 'insurance' && <InsurancePanel />}
      {activeTab === 'links' && <BookingLinksPanel />}
    </div>
  )
}

function NotificationsPanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const { campuses, selectedCampus } = useScopedCampuses()
  const { data: templates = [], isLoading } = useQuery({ queryKey: ['admin', 'notification-templates'], queryFn: fetchNotificationTemplates })
  const { data: courseTemplates = [], isLoading: coursesLoading, isError: coursesError } = useQuery({ queryKey: ['admin', 'course-templates'], queryFn: fetchCourseTemplates })
  const { data: categories = [] } = useQuery({ queryKey: ['admin', 'course-categories'], queryFn: fetchCourseCategories })
  const { data: deliveries = [] } = useQuery({ queryKey: ['admin', 'notification-deliveries'], queryFn: fetchNotificationDeliveries })
  const emptyForm = () => ({ id: undefined as number | undefined, name: '', campus: selectedCampus, event: 'pre_course', channel: 'email', subject: '', body: '', days_before: '3', course_template_ids: [] as number[], is_active: true })
  const [form, setForm] = useState(emptyForm)
  const save = useMutation({ mutationFn: () => saveNotificationTemplate({ ...form, campus: form.campus ? Number(form.campus) : null, days_before: Number(form.days_before) }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'notification-templates'] }); setForm(emptyForm()); notify.success('通知範本已儲存') }, onError: (e: any) => notify.error(e?.response?.data?.detail || e?.response?.data?.msg || '儲存失敗') })
  const edit = (template: (typeof templates)[number]) => {
    setForm({ id: template.id, name: template.name, campus: template.campus ? String(template.campus) : '', event: template.event, channel: template.channel, subject: template.subject, body: template.body, days_before: String(template.days_before), course_template_ids: template.course_template_ids || [], is_active: template.is_active })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  const toggleCourse = (id: number) => setForm(current => ({ ...current, course_template_ids: current.course_template_ids.includes(id) ? current.course_template_ids.filter(value => value !== id) : [...current.course_template_ids, id] }))
  const courseLabel = (id: number) => {
    const course = courseTemplates.find(item => item.id === id)
    if (!course) return `課程 #${id}`
    const category = categories.find(item => item.types.some(type => type.id === course.course_type))
    return `${course.name}（${category?.name || course.course_type_name} · #${id}）`
  }
  return <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
    <section className={cardClass}><div className="flex items-center justify-between gap-2"><h2 className="font-semibold text-gray-900 dark:text-white">{form.id ? '編輯通知範本' : '新增通知範本'}</h2>{form.id && <button type="button" onClick={() => setForm(emptyForm())} className="text-sm text-violet-700 hover:underline dark:text-violet-300">取消編輯</button>}</div><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">選事件、管道、課程與時間，系統會依校區自動排程。</p><div className="space-y-3">
      <input className={inputClass} placeholder="範本名稱，例如：課前三天提醒" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
      <select className={inputClass} value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value })}>{!selectedCampus && <option value="">全部校區</option>}{campuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
      <div className="grid grid-cols-2 gap-2"><select className={inputClass} value={form.event} onChange={e => setForm({ ...form, event: e.target.value })}><option value="order_created">訂單成立</option><option value="payment_confirmed">付款完成</option><option value="pre_course">課前提醒</option><option value="missing_documents">資料未完成</option><option value="line_group">LINE 群組邀請</option><option value="evaluation_due">評量未完成</option></select><select className={inputClass} value={form.channel} onChange={e => setForm({ ...form, channel: e.target.value })}><option value="email">Email</option><option value="line">LINE</option><option value="in_app">站內通知</option></select></div>
      <fieldset className="rounded-lg border border-gray-200 p-3 dark:border-gray-600"><legend className="px-1 text-sm font-medium text-gray-900 dark:text-white">適用課程</legend><p className="mb-2 text-xs text-gray-500 dark:text-gray-400">不勾選代表所有課程；勾選後只通知指定課程。</p>{coursesLoading ? <p className="text-xs text-gray-500">載入課程中…</p> : coursesError ? <p role="alert" className="text-xs text-red-600">課程載入失敗，請重新整理後再儲存。</p> : <div className="max-h-40 space-y-1 overflow-y-auto">{courseTemplates.map(course => <label key={course.id} className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 text-sm text-gray-800 hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-gray-700"><input type="checkbox" className="mt-0.5 accent-violet-600" checked={form.course_template_ids.includes(course.id)} onChange={() => toggleCourse(course.id)} /><span>{courseLabel(course.id)}<span className="block text-xs text-gray-500 dark:text-gray-400">{course.resort_names?.join('、') || '全部雪場'}</span></span></label>)}{!courseTemplates.length && <p className="text-xs text-gray-500">尚無可選課程，請先建立課程模板。</p>}</div>}</fieldset>
      <input className={inputClass} type="number" min="0" value={form.days_before} onChange={e => setForm({ ...form, days_before: e.target.value })} placeholder="課前幾天" />
      <input className={inputClass} placeholder="信件主旨" value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} />
      <textarea className={`${inputClass} min-h-28`} placeholder="通知內容" value={form.body} onChange={e => setForm({ ...form, body: e.target.value })} />
      <label className="flex items-center gap-2 text-sm text-gray-800 dark:text-gray-100"><input type="checkbox" className="accent-violet-600" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} />啟用此範本</label>
      <button disabled={!form.name || !form.body || save.isPending || coursesLoading || coursesError} onClick={() => save.mutate()} className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}>{save.isPending ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}{form.id ? '儲存修改' : '建立範本'}</button>
    </div></section>
    <div className="space-y-5"><section className={cardClass}><h2 className="mb-3 font-semibold text-gray-900 dark:text-white">目前範本</h2>{isLoading ? <Loader2 className="animate-spin" /> : <div className="space-y-2">{templates.map(t => <div key={t.id} className="rounded-lg border border-gray-100 p-3 text-sm dark:border-gray-700"><div className="flex items-start justify-between gap-2"><div className="flex items-center gap-2"><b className="text-gray-900 dark:text-white">{t.name}</b><span className={`rounded-full px-2 py-0.5 text-xs ${t.is_active ? 'bg-green-50 text-green-700 dark:bg-green-900/40 dark:text-green-300' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'}`}>{t.is_active ? '啟用中' : '已停用'}</span></div><div className="flex shrink-0 items-center gap-3"><span className="text-xs text-gray-500 dark:text-gray-400">已排程 {t.delivery_count} 次</span><button type="button" onClick={() => edit(t)} className="text-xs font-medium text-violet-700 hover:underline dark:text-violet-300" aria-label={`編輯 ${t.name}`}>編輯</button></div></div><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{notificationChannels[t.channel] || t.channel} · {notificationEvents[t.event] || t.event} · {t.days_before ? `提前 ${t.days_before} 天` : '立即'}</p><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">適用課程：{t.course_template_ids?.length ? t.course_template_ids.map(courseLabel).join('、') : '所有課程'}</p></div>)}{!templates.length && <Empty text="尚無範本，先用左側建立一個。" />}</div>}</section>
    <section className={cardClass}><h2 className="mb-3 font-semibold text-gray-900 dark:text-white">最近發送佇列</h2><div className="space-y-2">{deliveries.slice(0, 10).map(d => <div key={d.id} className="flex items-center justify-between gap-3 rounded-lg bg-gray-50 p-3 text-sm dark:bg-gray-900"><div className="min-w-0"><b>{d.template_name}</b><p className="break-all text-xs text-gray-500 dark:text-gray-400">{d.order_number} · {d.recipient}</p>{d.status === 'failed' && d.error_message && <p className="mt-1 text-xs text-red-600 dark:text-red-300">失敗原因：{d.error_message}</p>}</div><span className={`shrink-0 text-xs font-semibold ${d.status === 'failed' ? 'text-red-600 dark:text-red-300' : 'text-gray-600 dark:text-gray-300'}`}>{deliveryStatuses[d.status] || d.status}</span></div>)}{!deliveries.length && <Empty text="尚無待發送通知。" />}</div></section></div>
  </div>
}

function PayrollPanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const { campuses, selectedCampus } = useScopedCampuses()
  const { data: coaches = [] } = useQuery({ queryKey: ['admin', 'coaches'], queryFn: fetchCoaches })
  const { data: statements = [], isLoading } = useQuery({ queryKey: ['admin', 'payroll'], queryFn: fetchPayrollStatements })
  const { data: rules = [] } = useQuery({ queryKey: ['admin', 'pay-rules'], queryFn: fetchPayRules })
  const now = new Date(); const first = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`; const last = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().slice(0, 10)
  const [form, setForm] = useState({ coach: '', campus: selectedCampus, period_start: first, period_end: last })
  const [rule, setRule] = useState({ coach: '', discipline: 'snowboard', certification_level: '', hourly_rate: '', specified_fee: '0', referral_percent: '10', assistance_hour_factor: '0.5', supervisor_allowance: '0' })
  const [detailId, setDetailId] = useState<number | null>(null)
  const [manual, setManual] = useState({ description: '', amount: '' })
  const [runError, setRunError] = useState('')
  const detail = statements.find(statement => statement.id === detailId)
  const addManual = useMutation({ mutationFn: () => addPayrollAdjustment(detailId!, { description: manual.description, amount: Number(manual.amount) }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'payroll'] }); setManual({ description: '', amount: '' }); notify.success('手動項目已加入薪資單') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '新增項目失敗') })
  const run = useMutation({ mutationFn: () => calculatePayroll({ coach: Number(form.coach), campus: Number(form.campus), period_start: form.period_start, period_end: form.period_end }), onSuccess: () => { setRunError(''); qc.invalidateQueries({ queryKey: ['admin', 'payroll'] }); notify.success('薪資已重新計算') }, onError: (e: any) => { const message = e?.response?.data?.detail || e?.response?.data?.msg || '計算失敗'; setRunError(message); notify.error(message) } })
  const saveRule = useMutation({ mutationFn: () => {
    const existing = rules.find(r => r.coach === Number(rule.coach) && r.course_type === null && r.discipline === rule.discipline && r.certification_level === rule.certification_level)
    return savePayRule({ ...rule, id: existing?.id, course_type: null, coach: Number(rule.coach), hourly_rate: rule.hourly_rate, specified_fee: Number(rule.specified_fee), referral_percent: rule.referral_percent, assistance_hour_factor: rule.assistance_hour_factor, supervisor_allowance: Number(rule.supervisor_allowance), is_active: true })
  }, onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'pay-rules'] }); notify.success('教練薪資規則已儲存') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '規則儲存失敗') })
  const hasOverlappingStatements = useMemo(() => statements.some((item, index) => statements.slice(index + 1).some(other =>
    item.coach === other.coach && item.campus === other.campus &&
    item.period_start <= other.period_end && other.period_start <= item.period_end
  )), [statements])
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
  </div><div className="mt-4 flex flex-wrap gap-2">{rules.map(r => <span key={r.id} className="rounded-full bg-gray-100 px-3 py-1 text-xs dark:bg-gray-700">{r.coach_name} · {disciplineNames[r.discipline] || r.discipline} · NT$ {Number(r.hourly_rate).toLocaleString()}/時</span>)}</div></section><section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">計算教練薪資</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">完成課程才列入；時薪、指定費、介紹費、裝備協助與主管加給會分開計算。</p><div className="grid items-end gap-3 md:grid-cols-5">
    <Field label="校區"><select className={inputClass} value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value })}><option value="">請選校區</option>{campuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    <Field label="教練"><select className={inputClass} value={form.coach} onChange={e => setForm({ ...form, coach: e.target.value })}><option value="">請選教練</option>{coaches.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    <Field label="結算開始日"><input className={inputClass} type="date" value={form.period_start} onChange={e => setForm({ ...form, period_start: e.target.value })} /></Field>
    <Field label="結算結束日"><input className={inputClass} type="date" value={form.period_end} onChange={e => setForm({ ...form, period_end: e.target.value })} /></Field>
    <button disabled={!form.coach || !form.campus || run.isPending} onClick={() => run.mutate()} className="rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}>{run.isPending ? '計算中…' : '開始計算'}</button>
  </div>{runError && <p role="alert" className="mt-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">{runError}</p>}</section>
    <section className={cardClass}>
      <div className="mb-2 flex justify-between"><h2 className="font-semibold text-gray-900 dark:text-white">薪資單</h2><span className="text-sm text-gray-500 dark:text-gray-400">共 {statements.length} 張，請逐張核對</span></div>
      {hasOverlappingStatements && <p role="alert" className="mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">現有薪資單有重疊期間，同一堂課可能重複出現。請逐張核對，勿直接加總或發放。</p>}
      {isLoading ? <Loader2 className="animate-spin" /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-xs text-gray-500 dark:text-gray-400"><tr><th className="py-2">教練／校區</th><th>期間</th><th>授課時數</th><th>課程</th><th>指定＋介紹＋協助＋加給</th><th className="text-right">應付</th><th className="text-right">操作</th></tr></thead><tbody>{statements.map(s => <tr key={s.id} className="border-t border-gray-100 dark:border-gray-700"><td className="py-3"><b>{s.coach_name}</b><p className="text-xs text-gray-500 dark:text-gray-400">{s.campus_name}</p></td><td>{s.period_start}～{s.period_end}</td><td>{teachingHours(s.lines)} 小時</td><td>NT$ {s.course_pay.toLocaleString()}</td><td>NT$ {(s.specified_fees + s.referral_commission + s.assistance_pay + s.supervisor_allowance).toLocaleString()}</td><td className="text-right font-bold">NT$ {s.total_amount.toLocaleString()}</td><td className="text-right"><button className="rounded-lg border border-violet-200 px-3 py-1 text-violet-700 dark:text-violet-300" onClick={() => setDetailId(s.id)}>查看明細</button></td></tr>)}</tbody></table>{!statements.length && <Empty text="尚無薪資單。選擇校區、教練與期間後開始計算。" />}</div>}
    </section>
    {detail && <section className={cardClass} aria-label="薪資明細">
      <div className="flex items-center justify-between"><h2 className="font-semibold text-gray-900 dark:text-white">{detail.coach_name} · {detail.period_start}～{detail.period_end}</h2><button onClick={() => setDetailId(null)} className="text-sm text-gray-500">關閉</button></div>
      <p className="my-2 text-xs text-gray-500 dark:text-gray-400">授課合計 {teachingHours(detail.lines)} 小時。各項顯示數量、單價與金額；介紹費以折扣後課程費計算。法定稅費尚未自動扣除，請先由會計核對。</p>
      <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="text-gray-500"><th className="py-2">項目</th><th>計算</th><th className="text-right">金額</th></tr></thead><tbody>{detail.lines?.map(line => <tr key={line.id} className="border-t border-gray-100 dark:border-gray-700"><td className="py-2">{displayPayrollDescription(line.description)}</td><td>{line.line_type === 'referral' ? `NT$ ${Number(line.unit_amount).toLocaleString()} × ${line.quantity}%` : `${line.quantity}${line.line_type === 'course' || line.line_type === 'assistance' ? ' 小時' : ' 項'} × NT$ ${Number(line.unit_amount).toLocaleString()}`}</td><td className="text-right">NT$ {line.total_amount.toLocaleString()}</td></tr>)}</tbody></table></div>
      {!detail.lines?.length && <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">這張薪資單沒有課程明細。請核對期間內是否有已完成課程及對應薪資規則。</p>}
      <p className="mt-3 text-right font-semibold text-gray-900 dark:text-white">應付合計 NT$ {detail.total_amount.toLocaleString()}</p>
      {detail.status === 'draft' && <div className="mt-4 grid gap-2 border-t border-gray-200 pt-4 dark:border-gray-700 sm:grid-cols-[1fr_150px_auto]"><input aria-label="手動薪資項目說明" className={inputClass} placeholder="項目說明，例如本月日文協助費" value={manual.description} onChange={e => setManual({ ...manual, description: e.target.value })} /><input aria-label="手動薪資項目金額" className={inputClass} type="number" step="1" placeholder="金額，可填負數" value={manual.amount} onChange={e => setManual({ ...manual, amount: e.target.value })} /><button disabled={!manual.description.trim() || !manual.amount || !Number.isInteger(Number(manual.amount)) || addManual.isPending} onClick={() => addManual.mutate()} className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">新增手動項目</button></div>}
    </section>}
  </div>
}

function EvaluationsPanel() {
  const { data: rows = [], isLoading } = useQuery({ queryKey: ['admin', 'evaluations'], queryFn: fetchEvaluations })
  return <section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">學員進度與課程紀錄</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">點「填寫評量」即可紀錄教練評語、學習進度、雪道與照片／影片。</p>{isLoading ? <Loader2 className="animate-spin" /> : <div className="grid gap-3 xl:grid-cols-2">{rows.map(r => <EvaluationCard key={r.id} row={r} />)}{!rows.length && <Empty text="尚無課程評量。課程建立學員資料後即可開始填寫。" />}</div>}</section>
}

function EvaluationCard({ row }: { row: Evaluation }) {
  const qc = useQueryClient(); const notify = useNotification()
  const [editing, setEditing] = useState(false)
  const [notes, setNotes] = useState(row.coach_notes || '')
  const [progress, setProgress] = useState(learningProgressToText(row.learning_progress || {}))
  const [trails, setTrails] = useState((row.trail_names || []).join('、'))
  const [mediaUrl, setMediaUrl] = useState('')
  const [mediaType, setMediaType] = useState<'photo' | 'video'>('photo')
  const save = useMutation({ mutationFn: async () => {
    const learning_progress = learningProgressFromText(progress)
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
  const { campuses, selectedCampus } = useScopedCampuses()
  const { data: rows = [] } = useQuery({ queryKey: ['admin', 'staff-booking-links'], queryFn: fetchStaffBookingLinks })
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 16)
  const [form, setForm] = useState({ campus: selectedCampus, title: '', expires_at: tomorrow })
  const create = useMutation({ mutationFn: () => createStaffBookingLink({ campus: Number(form.campus), title: form.title, expires_at: new Date(form.expires_at).toISOString() }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'staff-booking-links'] }); setForm({ ...form, title: '' }); notify.success('訂課連結已建立') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '建立失敗') })
  const copy = async (url: string) => { await navigator.clipboard.writeText(url); notify.success('連結已複製') }
  return <div className="space-y-5"><section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">建立代客訂課連結</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">先指定訂單歸屬校區。把連結傳給客人後，來源會保留建立人員資訊。</p><div className="grid items-end gap-3 md:grid-cols-4"><Field label="訂單歸屬校區"><select className={inputClass} value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value })}><option value="">請選校區</option>{campuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field><Field label="用途／客人名稱"><input className={inputClass} placeholder="例如：王小姐三日課" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></Field><Field label="連結失效時間"><input className={inputClass} type="datetime-local" value={form.expires_at} onChange={e => setForm({ ...form, expires_at: e.target.value })} /></Field><button disabled={!form.campus || !form.title || create.isPending} onClick={() => create.mutate()} className="flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}><Plus size={16} />建立連結</button></div></section><section className={cardClass}><div className="space-y-3">{rows.map(r => <div key={r.id} className="flex flex-col gap-3 rounded-lg border border-gray-100 p-4 dark:border-gray-700 sm:flex-row sm:items-center sm:justify-between"><div><b>{r.title}</b><p className="text-xs text-gray-500 dark:text-gray-400">{r.is_available ? '可使用' : '已失效'} · 到期 {new Date(r.expires_at).toLocaleString()}</p></div><button disabled={!r.is_available} onClick={() => copy(r.url)} className="rounded-lg border border-violet-200 px-3 py-2 text-sm font-semibold text-violet-600 disabled:opacity-40">複製連結</button></div>)}{!rows.length && <Empty text="尚未建立連結。" />}</div></section></div>
}

function InsurancePanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const { data: rows = [], isLoading } = useQuery({ queryKey: ['admin', 'insurance-records'], queryFn: fetchInsuranceRecords })
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const filteredRows = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return keyword ? rows.filter(row => `${row.member_name} ${row.sn} ${row.order_number} ${row.campus_name}`.toLowerCase().includes(keyword)) : rows
  }, [rows, search])
  const pageSize = 20
  const pageCount = Math.max(Math.ceil(filteredRows.length / pageSize), 1)
  const currentPage = Math.min(page, pageCount)
  const visibleRows = filteredRows.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const complete = useMutation({ mutationFn: ({ id, field }: { id: number; field: 'insurance' | 'waiver' }) => completeInsuranceRecord(id, field), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'insurance-records'] }); notify.success('完成狀態已更新') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '更新失敗') })
  return <section className={cardClass}><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><h2 className="font-semibold text-gray-900 dark:text-white">待補保險與聲明書</h2><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">只顯示尚未完成的學員；收到紙本或人工確認後，可用右側按鈕標記完成。</p></div><input className={`${inputClass} sm:max-w-xs`} placeholder="搜尋學員、訂單或校區" value={search} onChange={event => { setSearch(event.target.value); setPage(1) }} /></div>{isLoading ? <Loader2 className="mt-4 animate-spin" /> : <><div className="mt-4 space-y-3">{visibleRows.map(row => <div key={row.id} className="flex flex-col gap-3 rounded-lg border border-gray-100 p-4 dark:border-gray-700 md:flex-row md:items-center md:justify-between"><div><b>{row.member_name}</b><p className="text-xs text-gray-500 dark:text-gray-400">{row.sn || row.order_number} · {row.campus_name} · {row.course_dates.join('、')}</p></div><div className="flex flex-wrap gap-2">{!row.insurance_completed_at && <button onClick={() => complete.mutate({ id: row.id, field: 'insurance' })} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white">標記保險完成</button>}{!row.waiver_completed_at && <button onClick={() => complete.mutate({ id: row.id, field: 'waiver' })} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white">標記聲明書完成</button>}</div></div>)}{!visibleRows.length && <Empty text={rows.length ? '找不到符合條件的學員。' : '所有學員資料都已完成。'} />}</div>{filteredRows.length > pageSize && <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-gray-500 dark:text-gray-400"><span>共 {filteredRows.length} 位待補，顯示第 {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, filteredRows.length)} 位</span><div className="flex gap-2"><button disabled={currentPage === 1} onClick={() => setPage(value => Math.max(value - 1, 1))} className="rounded-lg border border-gray-200 px-3 py-2 disabled:opacity-40 dark:border-gray-600">上一頁</button><span className="px-2 py-2">{currentPage} / {pageCount}</span><button disabled={currentPage === pageCount} onClick={() => setPage(value => Math.min(value + 1, pageCount))} className="rounded-lg border border-gray-200 px-3 py-2 disabled:opacity-40 dark:border-gray-600">下一頁</button></div></div>}</>}</section>
}

function Empty({ text }: { text: string }) { return <div className="py-8 text-center text-sm text-gray-400">{text}</div> }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="block"><span className="mb-1 block text-xs font-semibold text-gray-600 dark:text-gray-300">{label}</span>{children}</label> }
