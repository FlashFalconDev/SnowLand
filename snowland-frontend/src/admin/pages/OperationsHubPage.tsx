import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Calculator, ClipboardCheck, Link2, Loader2, Plus, Save } from 'lucide-react'
import { fetchCampuses } from '../api/campuses'
import { fetchAdminMe } from '../api/auth'
import { hasAdminPermission } from '../permissions'
import { fetchCourseCategories, fetchCourseTemplates } from '../api/courses'
import {
  calculatePayroll, createStaffBookingLink, fetchEvaluations, fetchNotificationDeliveries,
  fetchNotificationTemplates, fetchPayrollStatements, fetchPayrollCoaches, fetchStaffBookingLinks, fetchPayRules, saveNotificationTemplate, addPayrollAdjustment, editPayrollAdjustment, removePayrollAdjustment, deletePayrollDraft,
  fetchInsuranceRecords, fetchInsuranceRecord, completeInsuranceRecord, fetchCoachEvaluations, saveInsuranceProcessing, type InsuranceRecordDetail,
  fetchCourseUploadLimits, uploadCourseFile,
  updateEvaluation, type Evaluation,
} from '../api/operations'
import { useNotification } from '../context'
import { learningProgressFromText, learningProgressToText } from '@/utils/learningProgress'
import { payrollMonthRange } from '@/utils/payrollDates'
import { useBookingStore } from '@/store/bookingStore'
import ManualNotificationComposer from '../components/ManualNotificationComposer'
import InsuranceCalendar, { insuranceDayRecords } from '../components/InsuranceCalendar'
import InsuranceReminderDialog from '../components/InsuranceReminderDialog'
import PayRuleEditor from '../components/PayRuleEditor'
import StaffIncentiveRulesPanel from '../components/StaffIncentiveRulesPanel'
import StaffIncentiveStatementsPanel from '../components/StaffIncentiveStatementsPanel'
import PayrollReviewActions from '../components/PayrollReviewActions'
import PayrollDocumentSettingsPanel from '../components/PayrollDocumentSettingsPanel'
import PayrollDocumentPanel from '../components/PayrollDocumentPanel'

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
  insurance: '查核學員保險、課前聲明與法定代理人資料，追蹤待補項目。',
  links: '建立有校區歸屬的連結，協助客人完成訂課。',
}

const inputClass = 'w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white'
const cardClass = 'rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800'
const disciplineNames: Record<string, string> = { snowboard: '單板', ski: '雙板', photo: '攝影' }
const displayPayrollDescription = (description: string) => description.replace(/\b(snowboard|ski|photo)\b/g, discipline => disciplineNames[discipline] || discipline)
const teachingHours = (lines: { line_type: string; quantity: string }[] = []) =>
  lines.filter(line => line.line_type === 'course').reduce((sum, line) => sum + Number(line.quantity), 0)
const payrollHoursNote = (line: { line_type: string; quantity: string; metadata?: Record<string, unknown> }) =>
  line.line_type === 'course' && line.metadata?.payroll_hours_source === 'template'
    ? `排課 ${Number(line.metadata.scheduled_hours)} 小時／依模板計薪 ${Number(line.quantity)} 小時`
    : ''
const notificationEvents: Record<string, string> = { order_created: '訂單成立', shared_class_ready: '團體班成班付款', payment_confirmed: '付款完成', pre_course: '課前提醒', missing_documents: '資料未完成', line_group: 'LINE 群組邀請', evaluation_due: '評量未完成' }
const immediateNotificationEvents = new Set(['order_created', 'shared_class_ready', 'payment_confirmed'])
const notificationChannels: Record<string, string> = { email: 'Email', line: 'LINE', in_app: '站內通知' }
const notificationTiming = (template: { event: string; days_before: number; repeat_interval_days: number }) =>
  `${immediateNotificationEvents.has(template.event) || !template.days_before ? '立即' : `提前 ${template.days_before} 天`}${template.event === 'missing_documents' ? template.repeat_interval_days ? ` · 未完成時每 ${template.repeat_interval_days} 天再提醒` : ' · 只提醒一次' : ''}`
const deliveryStatuses: Record<string, string> = { scheduled: '待發送', sending: '發送中／結果待確認', sent: '已發送', failed: '發送失敗', cancelled: '已取消' }

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

export default function OperationsHubPage({ initialTab = 'notifications', fixed = false, coachView = false }: { initialTab?: Tab; fixed?: boolean; coachView?: boolean }) {
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
      {activeTab === 'payroll' && <><StaffIncentiveRulesPanel /><StaffIncentiveStatementsPanel /><PayrollPanel /></>}
      {activeTab === 'evaluations' && <EvaluationsPanel coachView={coachView} />}
      {activeTab === 'insurance' && <InsurancePanel />}
      {activeTab === 'links' && <BookingLinksPanel />}
    </div>
  )
}

function NotificationsPanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const [composing, setComposing] = useState(false)
  const { data: notificationAdmin } = useQuery({ queryKey: ['admin', 'me'], queryFn: fetchAdminMe })
  const canCompose = (hasAdminPermission(notificationAdmin?.user, 'orders') || hasAdminPermission(notificationAdmin?.user, 'customers'))
    && !['campus_manager', 'campus_principal'].includes(notificationAdmin?.user?.role || '')
  const { campuses, selectedCampus } = useScopedCampuses()
  const { data: templates = [], isLoading } = useQuery({ queryKey: ['admin', 'notification-templates'], queryFn: fetchNotificationTemplates })
  const { data: courseTemplates = [], isLoading: coursesLoading, isError: coursesError } = useQuery({ queryKey: ['admin', 'course-templates'], queryFn: fetchCourseTemplates })
  const { data: categories = [] } = useQuery({ queryKey: ['admin', 'course-categories'], queryFn: fetchCourseCategories })
  const { data: deliveries = [] } = useQuery({ queryKey: ['admin', 'notification-deliveries'], queryFn: fetchNotificationDeliveries })
  const emptyForm = () => ({ id: undefined as number | undefined, name: '', campus: selectedCampus, event: 'pre_course', channel: 'email', subject: '', body: '', days_before: '3', repeat_interval_days: '0', course_template_ids: [] as number[], is_active: true })
  const [form, setForm] = useState(emptyForm)
  const repeatInvalid = form.event === 'missing_documents' && (!/^\d+$/.test(form.repeat_interval_days) || Number(form.repeat_interval_days) > 365)
  const sharedClassLinkMissing = form.event === 'shared_class_ready' && form.is_active && !form.body.includes('{payment_url}')
  const recipientHint = form.event === 'missing_documents'
    ? '只提醒還有資料未完成的學員或家長；未綁定及尚未建立的學員名額由訂購人負責。同一位家長只通知一次。'
    : ['pre_course', 'line_group'].includes(form.event)
      ? '通知訂購人，以及實際參加這堂課的已綁定學員或家長；同帳號、同 Email 或同 LINE 帳號不重複通知。'
      : '通知這筆訂單的主要聯絡人，不會把付款連結寄給同行學員。'
  const save = useMutation({ mutationFn: () => saveNotificationTemplate({ ...form, campus: form.campus ? Number(form.campus) : null, days_before: immediateNotificationEvents.has(form.event) ? 0 : Number(form.days_before), repeat_interval_days: form.event === 'missing_documents' ? Number(form.repeat_interval_days) : 0 }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'notification-templates'] }); setForm(emptyForm()); notify.success('通知範本已儲存') }, onError: (e: any) => notify.error(e?.response?.data?.repeat_interval_days?.[0] || e?.response?.data?.body?.[0] || e?.response?.data?.channel?.[0] || e?.response?.data?.detail || e?.response?.data?.msg || '儲存失敗') })
  const edit = (template: (typeof templates)[number]) => {
    setForm({ id: template.id, name: template.name, campus: template.campus ? String(template.campus) : '', event: template.event, channel: template.channel, subject: template.subject, body: template.body, days_before: String(template.days_before), repeat_interval_days: String(template.repeat_interval_days || 0), course_template_ids: template.course_template_ids || [], is_active: template.is_active })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  const toggleCourse = (id: number) => setForm(current => ({ ...current, course_template_ids: current.course_template_ids.includes(id) ? current.course_template_ids.filter(value => value !== id) : [...current.course_template_ids, id] }))
  const courseLabel = (id: number) => {
    const course = courseTemplates.find(item => item.id === id)
    if (!course) return `課程 #${id}`
    const category = categories.find(item => item.types.some(type => type.id === course.course_type))
    return `${course.name}（${category?.name || course.course_type_name} · #${id}）`
  }
  return <><section className={`${cardClass} mb-5 flex flex-wrap items-center justify-between gap-3`}><div><h2 className="font-semibold text-gray-900 dark:text-white">手動站內通知</h2><p className="mt-1 text-sm text-gray-500 dark:text-gray-400">針對單筆訂單或一位會員發送；先預覽，不會寄 Email／LINE。</p></div><button disabled={!canCompose} onClick={() => setComposing(true)} className="rounded-lg bg-violet-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">新增站內通知</button>{!canCompose && <p className="w-full text-xs text-gray-500 dark:text-gray-400">需要完整訂單或會員管理權限；校區摘要帳號請由行政人員協助。</p>}</section><div className="grid gap-5 xl:grid-cols-[380px_1fr]">
    <section className={cardClass}><div className="flex items-center justify-between gap-2"><h2 className="font-semibold text-gray-900 dark:text-white">{form.id ? '編輯通知範本' : '新增通知範本'}</h2>{form.id && <button type="button" onClick={() => setForm(emptyForm())} className="text-sm text-violet-700 hover:underline dark:text-violet-300">取消編輯</button>}</div><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">選事件、管道、課程與時間，系統會依校區自動排程。</p><div className="space-y-3">
      <label className="block text-sm font-medium text-gray-900 dark:text-white">範本名稱<input className={`${inputClass} mt-1`} placeholder="例如：課前三天提醒" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
      <label className="block text-sm font-medium text-gray-900 dark:text-white">適用校區<select className={`${inputClass} mt-1`} value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value })}>{!selectedCampus && <option value="">全部校區</option>}{campuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <div className="grid grid-cols-2 gap-2"><label className="block text-sm font-medium text-gray-900 dark:text-white">何時通知<select className={`${inputClass} mt-1`} value={form.event} onChange={e => setForm({ ...form, event: e.target.value, channel: e.target.value === 'shared_class_ready' && form.channel === 'in_app' ? 'email' : form.channel, days_before: immediateNotificationEvents.has(e.target.value) ? '0' : immediateNotificationEvents.has(form.event) ? '3' : form.days_before })}><option value="order_created">訂單成立</option><option value="shared_class_ready">團體班成班付款</option><option value="payment_confirmed">付款完成</option><option value="pre_course">課前提醒</option><option value="missing_documents">資料未完成</option><option value="line_group">LINE 群組邀請</option><option value="evaluation_due">評量未完成</option></select></label><label className="block text-sm font-medium text-gray-900 dark:text-white">通知方式<select className={`${inputClass} mt-1`} value={form.channel} onChange={e => setForm({ ...form, channel: e.target.value })}><option value="email">Email</option><option value="line">LINE</option>{form.event !== 'shared_class_ready' && <option value="in_app">站內通知</option>}</select></label></div>
      <div role="status" className="rounded-lg bg-blue-50 p-3 text-sm leading-6 text-blue-900 dark:bg-blue-900/30 dark:text-blue-100"><p className="font-semibold">誰會收到？</p><p className="mt-1">{recipientHint}</p><p className="mt-2 text-xs">{form.channel === 'in_app' ? '會員登入後，在「通知中心」查看；不會另外寄 Email 或推播 LINE。' : form.channel === 'line' ? 'LINE 需要可推送的綁定帳號；未綁定者不會收到，建議另設 Email 範本。' : '訂購人使用訂單聯絡信箱，同行學員或家長使用會員帳號信箱。郵件送出成功後，同步到有權限會員的「通知中心」；未綁定者只收到 Email。'}</p></div>
      <fieldset className="rounded-lg border border-gray-200 p-3 dark:border-gray-600"><legend className="px-1 text-sm font-medium text-gray-900 dark:text-white">適用課程</legend><p className="mb-2 text-xs text-gray-500 dark:text-gray-400">不勾選代表所有課程；勾選後只通知指定課程。</p>{coursesLoading ? <p className="text-xs text-gray-500">載入課程中…</p> : coursesError ? <p role="alert" className="text-xs text-red-600">課程載入失敗，請重新整理後再儲存。</p> : <div className="max-h-40 space-y-1 overflow-y-auto">{courseTemplates.map(course => <label key={course.id} className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 text-sm text-gray-800 hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-gray-700"><input type="checkbox" className="mt-0.5 accent-violet-600" checked={form.course_template_ids.includes(course.id)} onChange={() => toggleCourse(course.id)} /><span>{courseLabel(course.id)}<span className="block text-xs text-gray-500 dark:text-gray-400">{course.resort_names?.join('、') || '全部雪場'}</span></span></label>)}{!courseTemplates.length && <p className="text-xs text-gray-500">尚無可選課程，請先建立課程模板。</p>}</div>}</fieldset>
      {immediateNotificationEvents.has(form.event) ? <p className="rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-800 dark:bg-blue-900/30 dark:text-blue-200">事件發生時立即排程，不需設定課前天數。{form.event === 'shared_class_ready' && '成班付款通知會寄給客人，內容必須包含專屬付款連結。'}</p> : <label className="block text-sm font-medium text-gray-900 dark:text-white">第一堂課前幾天發送<input className={`${inputClass} mt-1`} type="number" min="0" value={form.days_before} onChange={e => setForm({ ...form, days_before: e.target.value })} /><span className="mt-1 block text-xs font-normal text-gray-500 dark:text-gray-400">填 0 代表符合通知條件時立即排程。</span></label>}
      <label className="block text-sm font-medium text-gray-900 dark:text-white">通知主旨<input className={`${inputClass} mt-1`} placeholder="例如：上課提醒" value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} /></label>
      <label className="block text-sm font-medium text-gray-900 dark:text-white">通知內容<textarea className={`${inputClass} mt-1 min-h-28`} value={form.body} onChange={e => setForm({ ...form, body: e.target.value })} /></label>
      {form.event === 'shared_class_ready' && <div className="flex flex-wrap items-center gap-2 text-xs"><button type="button" onClick={() => setForm({ ...form, body: `${form.body}${form.body ? '\n' : ''}{payment_url}` })} disabled={form.body.includes('{payment_url}')} className="rounded border border-violet-500 px-2 py-1 font-medium text-violet-700 disabled:opacity-50 dark:text-violet-300">插入專屬付款連結</button>{sharedClassLinkMissing && <span role="alert" className="text-red-600 dark:text-red-300">請在內容加入專屬付款連結後才能啟用。</span>}</div>}
      {form.event === 'missing_documents' && <label className="block text-sm font-medium text-gray-900 dark:text-white">未完成時，每隔幾天再提醒<input className={`${inputClass} mt-1`} type="number" min="0" max="365" step="1" value={form.repeat_interval_days} onChange={e => setForm({ ...form, repeat_interval_days: e.target.value })} aria-invalid={repeatInvalid} /><span className={`mt-1 block text-xs font-normal ${repeatInvalid ? 'text-red-600 dark:text-red-300' : 'text-gray-500 dark:text-gray-400'}`}>{repeatInvalid ? '請填 0～365 的整數。' : Number(form.repeat_interval_days) ? `每隔 ${Number(form.repeat_interval_days)} 天提醒一次；資料補齊或課程取消後停止，上課日期過後不再提醒。不會補寄錯過的次數。` : '填 0 只提醒一次；填 1 代表每天、填 3 代表每三天。'}</span></label>}
      <label className="flex items-center gap-2 text-sm text-gray-800 dark:text-gray-100"><input type="checkbox" className="accent-violet-600" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} />啟用此範本</label>
      <button disabled={!form.name || !form.body || sharedClassLinkMissing || repeatInvalid || save.isPending || coursesLoading || coursesError} onClick={() => save.mutate()} className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}>{save.isPending ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}{form.id ? '儲存修改' : '建立範本'}</button>
    </div></section>
    <div className="space-y-5"><section className={cardClass}><h2 className="mb-3 font-semibold text-gray-900 dark:text-white">目前範本</h2>{isLoading ? <Loader2 className="animate-spin" /> : <div className="space-y-2">{templates.map(t => <div key={t.id} className="rounded-lg border border-gray-100 p-3 text-sm dark:border-gray-700"><div className="flex items-start justify-between gap-2"><div className="flex min-w-0 flex-wrap items-center gap-2"><b className="break-all text-gray-900 dark:text-white">{t.name}</b><span className={`rounded-full px-2 py-0.5 text-xs ${t.is_active ? 'bg-green-50 text-green-700 dark:bg-green-900/40 dark:text-green-300' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'}`}>{t.is_active ? '啟用中' : '已停用'}</span></div><div className="flex shrink-0 items-center gap-3"><span className="text-xs text-gray-500 dark:text-gray-400">已排程 {t.delivery_count} 次</span><button type="button" onClick={() => edit(t)} className="text-xs font-medium text-violet-700 hover:underline dark:text-violet-300" aria-label={`編輯 ${t.name}`}>編輯</button></div></div><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{notificationChannels[t.channel] || t.channel} · {notificationEvents[t.event] || t.event} · {notificationTiming(t)}</p><p className="mt-1 break-words text-xs text-gray-500 dark:text-gray-400">適用課程：{t.course_template_ids?.length ? t.course_template_ids.map(courseLabel).join('、') : '所有課程'}</p></div>)}{!templates.length && <Empty text="尚無範本，先用左側建立一個。" />}</div>}</section>
    <section className={cardClass}><h2 className="mb-3 font-semibold text-gray-900 dark:text-white">最近發送佇列</h2><div className="space-y-2">{deliveries.slice(0, 10).map(d => <div key={d.id} className="flex items-center justify-between gap-3 rounded-lg bg-gray-50 p-3 text-sm dark:bg-gray-900"><div className="min-w-0"><b className="break-words">{d.template_name}</b><p className="mt-1 text-xs font-medium text-violet-700 dark:text-violet-300">{notificationChannels[d.channel] || '通知'}{d.email_synced ? d.local_test ? '（Email 同步 · 本機測試）' : '（Email 同步）' : d.local_test ? '（本機郵件測試）' : d.manual ? '（手動）' : ''}</p><p className="break-all text-xs text-gray-500 dark:text-gray-400">{d.order_number || '會員通知'} · {d.channel === 'in_app' ? `會員 #${d.recipient}` : d.recipient}</p>{d.status === 'failed' && d.error_message && <p className="mt-1 text-xs text-red-600 dark:text-red-300">失敗原因：{d.error_message}</p>}</div><span className={`shrink-0 text-xs font-semibold ${d.status === 'failed' ? 'text-red-600 dark:text-red-300' : 'text-gray-600 dark:text-gray-300'}`}>{deliveryStatuses[d.status] || d.status}</span></div>)}{!deliveries.length && <Empty text="尚無待發送通知。" />}</div></section></div>
  </div>{composing && <ManualNotificationComposer onClose={() => setComposing(false)} />}</>
}

function PayrollPanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const { campuses, selectedCampus } = useScopedCampuses()
  const activeCampuses = campuses.filter(campus => campus.is_active)
  const { data: coaches = [], isError: coachesError } = useQuery({ queryKey: ['admin', 'payroll-coaches'], queryFn: fetchPayrollCoaches })
  const { data: statements = [], isLoading } = useQuery({ queryKey: ['admin', 'payroll'], queryFn: fetchPayrollStatements })
  const { data: rules = [], isLoading: rulesLoading, isError: rulesError } = useQuery({ queryKey: ['admin', 'pay-rules'], queryFn: fetchPayRules })
  const { first, last } = payrollMonthRange()
  const [form, setForm] = useState({ coach: '', campus: selectedCampus, period_start: first, period_end: last })
  const campusCoaches = form.campus ? coaches.filter(coach => coach.campus_ids.includes(Number(form.campus))) : []
  const [detailId, setDetailId] = useState<number | null>(null)
  const detailRef = useRef<HTMLElement | null>(null)
  const [manual, setManual] = useState({ description: '', amount: '', lineId: null as number | null })
  const manualInputRef = useRef<HTMLInputElement | null>(null)
  const [pendingDelete, setPendingDelete] = useState<{ lineId: number | null; label: string } | null>(null)
  const deleteConfirmRef = useRef<HTMLButtonElement | null>(null)
  const [runError, setRunError] = useState('')
  const detail = statements.find(statement => statement.id === detailId)
  useEffect(() => {
    if (detailId !== null) detailRef.current?.scrollIntoView({ behavior: 'auto', block: 'start' })
    setManual({ description: '', amount: '', lineId: null })
    setPendingDelete(null)
  }, [detailId])
  useEffect(() => { if (manual.lineId !== null) { manualInputRef.current?.focus({ preventScroll: true }); manualInputRef.current?.scrollIntoView({ behavior: 'auto', block: 'center' }) } }, [manual.lineId])
  useEffect(() => { if (pendingDelete) { deleteConfirmRef.current?.focus({ preventScroll: true }); deleteConfirmRef.current?.scrollIntoView({ behavior: 'auto', block: 'center' }) } }, [pendingDelete])
  const addManual = useMutation({ mutationFn: () => manual.lineId !== null ? editPayrollAdjustment(detailId!, manual.lineId, { description: manual.description, amount: Number(manual.amount) }) : addPayrollAdjustment(detailId!, { description: manual.description, amount: Number(manual.amount) }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'payroll'] }); notify.success(manual.lineId !== null ? '手動項目已修改，金額已更新' : '手動項目已加入薪資單'); setManual({ description: '', amount: '', lineId: null }) }, onError: (e: any) => notify.error(e?.response?.data?.msg || '儲存項目失敗') })
  const removePayroll = useMutation({ mutationFn: () => {
    if (!pendingDelete || detailId === null) throw new Error('請重新選擇要刪除的項目')
    return pendingDelete.lineId === null ? deletePayrollDraft(detailId) : removePayrollAdjustment(detailId, pendingDelete.lineId)
  }, onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'payroll'] }); if (pendingDelete?.lineId === null) setDetailId(null); setPendingDelete(null); setManual({ description: '', amount: '', lineId: null }); notify.success('已刪除，薪資資料已更新') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '刪除失敗，資料尚未移除') })
  const adjustmentActions = (line: { id: number; line_type: string; description: string; total_amount: number }) => detail?.status === 'draft' && line.line_type === 'adjustment' ? <div className="mt-2 flex gap-4"><button type="button" aria-label={`編輯手動項目 ${line.description}`} disabled={addManual.isPending || removePayroll.isPending} className="min-h-10 text-sm font-medium text-violet-700 disabled:opacity-40 dark:text-violet-300" onClick={() => { setPendingDelete(null); setManual({ lineId: line.id, description: line.description, amount: String(line.total_amount) }) }}>編輯</button><button type="button" aria-label={`刪除手動項目 ${line.description}`} disabled={addManual.isPending || removePayroll.isPending} className="min-h-10 text-sm font-medium text-red-600 disabled:opacity-40 dark:text-red-300" onClick={() => setPendingDelete({ lineId: line.id, label: line.description })}>刪除</button></div> : null
  const run = useMutation({ mutationFn: () => calculatePayroll({ coach: Number(form.coach), campus: Number(form.campus), period_start: form.period_start, period_end: form.period_end }), onSuccess: () => { setRunError(''); qc.invalidateQueries({ queryKey: ['admin', 'payroll'] }); notify.success('薪資已重新計算') }, onError: (e: any) => { const message = e?.response?.data?.detail || e?.response?.data?.msg || '計算失敗'; setRunError(message); notify.error(message) } })
  const hasOverlappingStatements = useMemo(() => statements.some((item, index) => statements.slice(index + 1).some(other =>
    item.coach === other.coach && item.campus === other.campus &&
    item.period_start <= other.period_end && other.period_start <= item.period_end
  )), [statements])
  return <div className="space-y-5"><PayrollDocumentSettingsPanel />{coachesError && <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">教練清單載入失敗，請重新整理後再操作薪資。</p>}<PayRuleEditor rules={rules} coaches={coaches} loading={rulesLoading} failed={rulesError || coachesError} /><section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">計算教練薪資</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">完成課程才列入；時薪、指定費、介紹費、裝備協助與主管加給會分開計算。</p><div className="grid items-end gap-3 md:grid-cols-5">
    <Field label="校區"><select className={inputClass} value={form.campus} onChange={e => { setForm({ ...form, campus: e.target.value, coach: '' }); setRunError('') }}><option value="">請選校區</option>{activeCampuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    <Field label="教練"><select className={inputClass} value={form.coach} disabled={!form.campus || coachesError} onChange={e => setForm({ ...form, coach: e.target.value })}><option value="">{form.campus ? '請選教練' : '請先選校區'}</option>{campusCoaches.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    <Field label="結算開始日"><input className={inputClass} type="date" value={form.period_start} onChange={e => setForm({ ...form, period_start: e.target.value })} /></Field>
    <Field label="結算結束日"><input className={inputClass} type="date" value={form.period_end} onChange={e => setForm({ ...form, period_end: e.target.value })} /></Field>
    <button disabled={!form.coach || !form.campus || run.isPending} onClick={() => run.mutate()} className="rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}>{run.isPending ? '計算中…' : '開始計算'}</button>
  </div>{runError && <p role="alert" className="mt-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">{runError}</p>}</section>
    <section className={cardClass}>
      <div className="mb-2 flex justify-between"><h2 className="font-semibold text-gray-900 dark:text-white">薪資單</h2><span className="text-sm text-gray-500 dark:text-gray-400">共 {statements.length} 張，請逐張核對</span></div>
      {hasOverlappingStatements && <p role="alert" className="mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">現有薪資單有重疊期間，同一堂課可能重複出現。請逐張核對，勿直接加總或發放。</p>}
      {isLoading ? <Loader2 className="animate-spin" /> : statements.length ? <>
        <div className="space-y-3 md:hidden">{statements.map(s => <article key={s.id} className="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
          <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="font-semibold text-gray-900 dark:text-white">{s.coach_name}</h3><p className="text-xs text-gray-500 dark:text-gray-400">{s.campus_name} · {s.period_start}～{s.period_end}</p></div><strong className="shrink-0 text-sm text-gray-900 dark:text-white">NT$ {s.total_amount.toLocaleString()}</strong></div>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-sm"><div><dt className="text-xs text-gray-500 dark:text-gray-400">計薪時數</dt><dd>{teachingHours(s.lines)} 小時</dd></div><div><dt className="text-xs text-gray-500 dark:text-gray-400">課程薪資</dt><dd>NT$ {s.course_pay.toLocaleString()}</dd></div><div className="col-span-2"><dt className="text-xs text-gray-500 dark:text-gray-400">指定費、介紹費、協助與加給</dt><dd>NT$ {(s.specified_fees + s.referral_commission + s.assistance_pay + s.supervisor_allowance).toLocaleString()}</dd></div></dl>
          <button className="mt-3 w-full rounded-lg border border-violet-200 px-3 py-2 text-sm font-semibold text-violet-700 dark:text-violet-300" onClick={() => setDetailId(s.id)}>查看明細</button>
        </article>)}</div>
        <div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[780px] text-left text-sm"><thead className="text-xs text-gray-500 dark:text-gray-400"><tr><th className="py-2">教練／校區</th><th>期間</th><th>計薪時數</th><th>課程</th><th>指定＋介紹＋協助＋加給</th><th className="text-right">應付</th><th className="text-right">操作</th></tr></thead><tbody>{statements.map(s => <tr key={s.id} className="border-t border-gray-100 dark:border-gray-700"><td className="py-3"><b>{s.coach_name}</b><p className="text-xs text-gray-500 dark:text-gray-400">{s.campus_name}</p></td><td>{s.period_start}～{s.period_end}</td><td>{teachingHours(s.lines)} 小時</td><td>NT$ {s.course_pay.toLocaleString()}</td><td>NT$ {(s.specified_fees + s.referral_commission + s.assistance_pay + s.supervisor_allowance).toLocaleString()}</td><td className="text-right font-bold">NT$ {s.total_amount.toLocaleString()}</td><td className="text-right"><button className="whitespace-nowrap rounded-lg border border-violet-200 px-3 py-1 text-violet-700 dark:text-violet-300" onClick={() => setDetailId(s.id)}>查看明細</button></td></tr>)}</tbody></table></div>
      </> : <Empty text="尚無薪資單。選擇校區、教練與期間後開始計算。" />}
    </section>
    {detail && <section ref={detailRef} className={`${cardClass} scroll-mt-20`} aria-label="薪資明細">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><h2 className="font-semibold text-gray-900 dark:text-white">{detail.coach_name} · {detail.period_start}～{detail.period_end}</h2><button onClick={() => setDetailId(null)} className="self-end rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700 sm:self-auto">關閉</button></div>
      <p className="mt-2 text-sm font-medium text-gray-900 dark:text-white">狀態：{({ draft: '草稿（可修改）', review: '待教練確認（已鎖定）', confirmed: '已確認（已鎖定）', paid: '已發放（已鎖定）' } as Record<string, string>)[detail.status] || detail.status}</p>
      <PayrollReviewActions key={`${detail.id}-${detail.review_token}-${detail.status}`} statement={detail} />
      <PayrollDocumentPanel key={`document-${detail.id}-${detail.document_digest}-${detail.signed_at}`} statement={detail} />
      <p className="my-2 text-xs text-gray-500 dark:text-gray-400">計薪合計 {teachingHours(detail.lines)} 小時（不等於實際排課時數）。各項顯示數量、單價與金額；介紹費以折扣後課程費計算。系統項目請調整規則後重新計算，草稿的手動項目可編輯或刪除。法定稅費尚未自動扣除，請先由會計核對。</p>
      {detail.status === 'draft' && <button type="button" disabled={removePayroll.isPending || addManual.isPending} className="mb-2 min-h-10 rounded-lg border border-red-300 px-3 py-2 text-sm font-medium text-red-700 disabled:opacity-40 dark:border-red-800 dark:text-red-300" onClick={() => setPendingDelete({ lineId: null, label: `${detail.coach_name} ${detail.period_start}～${detail.period_end}` })}>刪除這張草稿薪資單</button>}
      {pendingDelete && <div role="alert" className="my-3 rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
        <p className="break-words font-semibold">確認刪除：{pendingDelete.label}？</p>
        <p className="mt-1">{pendingDelete.lineId === null ? '這張草稿與手動項目會移除；原訂單、課程及薪資規則不會刪除。可以重新結算，但手動項目需重新輸入。' : '只移除此手動項目，應付合計會一起更新。'}</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <button type="button" ref={deleteConfirmRef} disabled={removePayroll.isPending} className="min-h-11 rounded-lg border border-gray-300 bg-white px-4 py-2 text-gray-800 dark:border-gray-600 dark:bg-gray-800 dark:text-white" onClick={() => setPendingDelete(null)}>保留，不刪除</button>
          <button type="button" disabled={removePayroll.isPending} className="min-h-11 rounded-lg bg-red-600 px-4 py-2 font-semibold text-white disabled:opacity-40" onClick={() => removePayroll.mutate()}>{removePayroll.isPending ? '刪除中…' : '確認刪除'}</button>
        </div>
      </div>}
      <div className="mt-3 space-y-2 md:hidden">{detail.lines?.map(line => <div key={line.id} className="rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-700"><div className="flex items-start justify-between gap-3"><span className="min-w-0 break-words">{displayPayrollDescription(line.description)}</span><strong className="shrink-0">NT$ {line.total_amount.toLocaleString()}</strong></div><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{line.line_type === 'referral' ? `NT$ ${Number(line.unit_amount).toLocaleString()} × ${line.quantity}%` : `${line.quantity}${line.line_type === 'course' || line.line_type === 'assistance' ? ' 小時' : ' 項'} × NT$ ${Number(line.unit_amount).toLocaleString()}`}</p>{payrollHoursNote(line) && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{payrollHoursNote(line)}</p>}{adjustmentActions(line)}</div>)}</div>
      <div className="mt-3 hidden overflow-x-auto md:block"><table className="w-full text-left text-sm"><thead><tr className="text-gray-500"><th className="py-2">項目</th><th>計算</th><th className="text-right">金額</th></tr></thead><tbody>{detail.lines?.map(line => <tr key={line.id} className="border-t border-gray-100 dark:border-gray-700"><td className="py-2">{displayPayrollDescription(line.description)}{payrollHoursNote(line) && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{payrollHoursNote(line)}</p>}{adjustmentActions(line)}</td><td>{line.line_type === 'referral' ? `NT$ ${Number(line.unit_amount).toLocaleString()} × ${line.quantity}%` : `${line.quantity}${line.line_type === 'course' || line.line_type === 'assistance' ? ' 小時' : ' 項'} × NT$ ${Number(line.unit_amount).toLocaleString()}`}</td><td className="text-right">NT$ {line.total_amount.toLocaleString()}</td></tr>)}</tbody></table></div>
      {!detail.lines?.length && <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">這張薪資單沒有課程明細。請核對期間內是否有已完成課程及對應薪資規則。</p>}
      <p className="mt-3 text-right font-semibold text-gray-900 dark:text-white">應付合計 NT$ {detail.total_amount.toLocaleString()}</p>
      {detail.status === 'draft' && <div className="mt-4 grid gap-2 border-t border-gray-200 pt-4 dark:border-gray-700 sm:grid-cols-[1fr_150px_auto]"><input ref={manualInputRef} aria-label="手動薪資項目說明" className={inputClass} placeholder="項目說明，例如本月日文協助費" value={manual.description} onChange={e => setManual({ ...manual, description: e.target.value })} /><input aria-label="手動薪資項目金額" className={inputClass} type="number" step="1" placeholder="金額，可填負數" value={manual.amount} onChange={e => setManual({ ...manual, amount: e.target.value })} /><div className="flex flex-wrap gap-2"><button disabled={!manual.description.trim() || !manual.amount || !Number.isInteger(Number(manual.amount)) || Number(manual.amount) === 0 || addManual.isPending || removePayroll.isPending} onClick={() => addManual.mutate()} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{addManual.isPending ? '儲存中…' : manual.lineId !== null ? '儲存手動項目' : '新增手動項目'}</button>{manual.lineId !== null && <button type="button" disabled={addManual.isPending} className="min-h-11 px-3 text-sm text-gray-600 dark:text-gray-300" onClick={() => setManual({ description: '', amount: '', lineId: null })}>取消編輯</button>}</div></div>}
    </section>}
  </div>
}

function EvaluationsPanel({ coachView = false }: { coachView?: boolean }) {
  const { data: rows = [], isLoading, isError, refetch } = useQuery({ queryKey: [coachView ? 'coach' : 'admin', 'evaluations'], queryFn: coachView ? fetchCoachEvaluations : fetchEvaluations })
  return <section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">學員進度與課程紀錄</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">{coachView ? '只顯示自己已完成授課的學員，填寫後會同步到會員學習紀錄。' : '評量依角色開放填寫；行政可查看內容並補上照片／影片，不更改教學紀錄。'}</p>{isLoading ? <Loader2 className="animate-spin" /> : isError ? <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300"><p>評量載入失敗，請重新載入。</p><button type="button" onClick={() => void refetch()} className="mt-3 min-h-11 rounded-lg border border-red-300 px-3 py-2 font-semibold dark:border-red-700">重新載入</button></div> : <div className="grid gap-3 xl:grid-cols-2">{rows.map(r => <EvaluationCard key={r.id} row={r} coachView={coachView} />)}{!rows.length && <Empty text={coachView ? '目前沒有自己的已完課學員評量。' : '尚無課程評量。課程建立學員資料後即可開始填寫。'} />}</div>}</section>
}

function EvaluationCard({ row, coachView = false }: { row: Evaluation; coachView?: boolean }) {
  const qc = useQueryClient(); const notify = useNotification()
  const canEditAssessment = row.can_edit_assessment === true
  const rating = Number(row.self_assessment?.satisfaction_rating)
  const hasRating = Number.isInteger(rating) && rating >= 1 && rating <= 5
  const feedback = typeof row.self_assessment?.satisfaction_feedback === 'string' ? row.self_assessment.satisfaction_feedback : ''
  const [editing, setEditing] = useState(false)
  const [notes, setNotes] = useState(row.coach_notes || '')
  const [progress, setProgress] = useState(learningProgressToText(row.learning_progress || {}))
  const [selectedTrails, setSelectedTrails] = useState<string[]>(Array.isArray(row.trail_names) ? row.trail_names : [])
  const [extraTrails, setExtraTrails] = useState('')
  const trailOptions = Array.from(new Set([...(row.available_trails || []), ...(row.trail_names || []), ...selectedTrails]))
  const trails = Array.from(new Set([...selectedTrails, ...extraTrails.split(/[、,\n]/).map(value => value.trim()).filter(Boolean)]))
  const [mediaUrl, setMediaUrl] = useState('')
  const [mediaType, setMediaType] = useState<'photo' | 'video'>('photo')
  const [uploading, setUploading] = useState(false)
  const hasProgress = Object.values(learningProgressFromText(progress)).some(value => value.trim())
  const hasTrails = trails.length > 0
  const trailError = trails.length > 100 ? '完成雪道最多100條，請減少後再儲存。' : trails.some(name => name.length > 120) ? '每條雪道名稱最多120字，請縮短後再儲存。' : ''
  const canComplete = canEditAssessment ? Boolean(notes.trim() || hasProgress || hasTrails) && !trailError : Boolean(mediaUrl.trim())
  const mediaUrlError = mediaUrl.trim() && (() => {
    try { const url = new URL(mediaUrl.trim()); return !['http:', 'https:'].includes(url.protocol) || !url.hostname }
    catch { return true }
  })()
  const save = useMutation({ mutationFn: async () => {
    const learning_progress = learningProgressFromText(progress)
    const media = mediaUrl.trim() ? { new_media: { media_type: mediaType, url: mediaUrl.trim(), is_public: false } } : {}
    await updateEvaluation(row.id, canEditAssessment ? { coach_notes: notes, learning_progress, trail_names: trails, completed_at: new Date().toISOString(), ...media } : media, coachView)
  }, onSuccess: () => { qc.invalidateQueries({ queryKey: [coachView ? 'coach' : 'admin', 'evaluations'] }); setEditing(false); setMediaUrl(''); setSelectedTrails(trails); setExtraTrails(''); notify.success(canEditAssessment ? '評量已儲存' : '課程附件已加入，評量內容未變更') }, onError: (e: any) => notify.error(e?.response?.data?.new_media?.url?.[0] || e?.response?.data?.completed_at?.[0] || e?.response?.data?.detail || e?.response?.data?.msg || '資料未儲存，請稍後再試') })
  return <article className="rounded-xl border border-gray-100 p-4 dark:border-gray-700"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><b>{row.member_name}</b><p className="mt-1 break-all text-xs text-violet-700 dark:text-violet-300">{row.order_number}</p><p className="mt-1 text-xs text-gray-600 dark:text-gray-300">{row.course_date} · {row.course_name || '未設定課程'}</p><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{row.campus_name || '未指定校區'} · {row.resort_name || '未指定雪場'} · 教練：{row.coach_name || '尚未指定'}</p></div><button disabled={uploading || save.isPending} onClick={() => setEditing(!editing)} className="min-h-11 shrink-0 rounded-lg border border-violet-200 px-3 py-1.5 text-xs font-semibold text-violet-700 disabled:opacity-40 dark:border-violet-400 dark:text-violet-300">{editing ? '收起' : canEditAssessment ? '填寫評量' : '管理課程附件'}</button></div>
    {(!editing || !canEditAssessment) && <><p className="mt-3 whitespace-pre-wrap break-words text-sm text-gray-600 dark:text-gray-300">{row.coach_notes || '尚無評語'}</p>{learningProgressToText(row.learning_progress || {}) && <p className="mt-2 whitespace-pre-wrap break-words text-xs text-gray-600 dark:text-gray-300">學習進度：{learningProgressToText(row.learning_progress || {})}</p>}{row.trail_names?.length > 0 && <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">完成雪道：{row.trail_names.join('、')}</p>}<p className="mt-2 text-xs text-gray-500 dark:text-gray-400">媒體 {row.media?.length || 0} 個 · {row.completed_at ? '已完成' : '待填寫'}{!canEditAssessment && ' · 評量僅供查看，可另外加入課程附件'}</p></>}
    {editing && <div className="mt-4 space-y-3">
      {canEditAssessment && <>
      <Field label="給學員的教練評語"><textarea className={`${inputClass} min-h-24`} value={notes} onChange={e => setNotes(e.target.value)} placeholder="用簡單、鼓勵的方式說明這堂課的表現" /></Field>
      <Field label="學習進度（每行一項，例如：煞車：已完成）"><textarea className={`${inputClass} min-h-20`} value={progress} onChange={e => setProgress(e.target.value)} placeholder={'煞車：已完成\n轉彎：持續練習'} /></Field>
      <fieldset className="rounded-lg border border-gray-200 p-3 dark:border-gray-700"><legend className="px-1 text-sm font-medium text-gray-900 dark:text-white">完成雪道（可複選）</legend><p className="mb-2 text-xs text-gray-500 dark:text-gray-400">勾選這堂課實際完成的雪道；名單由「基本設定 → 雪場管理」維護。</p>{trailOptions.length ? <div className="grid gap-2 sm:grid-cols-2">{trailOptions.map(name => <label key={name} className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:text-white"><input type="checkbox" checked={selectedTrails.includes(name)} onChange={event => setSelectedTrails(previous => event.target.checked ? [...previous, name] : previous.filter(value => value !== name))} className="h-4 w-4 shrink-0 accent-violet-600" /><span className="break-words">{name}{!(row.available_trails || []).includes(name) && <span className="ml-1 text-xs text-gray-500 dark:text-gray-400">（原有記錄）</span>}</span></label>)}</div> : <p className="text-sm text-gray-500 dark:text-gray-400">這個雪場尚未設定雪道名單，可先在下方補填。</p>}<div className="mt-3"><Field label="其他完成雪道（選填）"><input className={`${inputClass} min-h-11`} value={extraTrails} onChange={event => setExtraTrails(event.target.value)} placeholder="清單沒有的雪道可在此補填，多條用頓號或逗號分隔" /></Field></div></fieldset>
      {trailError && <p role="alert" className="text-sm text-red-600 dark:text-red-300">{trailError}</p>}
      </>}
      <CourseFileUploader evaluationId={row.id} coachView={coachView} onBusyChange={setUploading} />
      <Field label="照片或影片網址（選填）"><div className="grid gap-2 sm:grid-cols-[120px_1fr]"><select className={`${inputClass} min-h-11`} value={mediaType} onChange={e => setMediaType(e.target.value as 'photo' | 'video')}><option value="photo">照片</option><option value="video">影片</option></select><input className={`${inputClass} min-h-11`} type="url" value={mediaUrl} onChange={e => setMediaUrl(e.target.value)} placeholder="https://..." /></div></Field>
      {mediaUrlError && <p role="alert" className="text-xs text-red-600 dark:text-red-300">請輸入以 http:// 或 https:// 開頭的完整照片／影片網址。</p>}
      <p className="text-xs text-gray-500 dark:text-gray-400">加入後，這筆課程的學員與後台可查看；不會自動公開在官網。</p>
      {!canComplete && !trailError && <p className="text-xs text-amber-700 dark:text-amber-300">{canEditAssessment ? '請先填寫教練評語、學習進度或完成雪道其中一項。' : '可選檔上傳，或填入照片／影片網址；加入附件不會更改評量內容或完成狀態。'}</p>}
      <button disabled={uploading || save.isPending || !canComplete || Boolean(mediaUrlError)} onClick={() => save.mutate()} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}>{save.isPending ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}{canEditAssessment ? '儲存並標示完成' : '加入附件網址'}</button>
    </div>}
    {row.media?.length > 0 && <div aria-label="已加入的課程附件" className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">{row.media.map(media => <div key={media.id} className="min-w-0 rounded-lg border border-gray-200 p-2 dark:border-gray-700">{media.media_type === 'video' ? <video controls preload="metadata" className="aspect-video w-full rounded bg-black object-contain" src={media.url} /> : <a href={media.url} target="_blank" rel="noreferrer" aria-label="開啟課程照片原圖"><img loading="lazy" className="aspect-video w-full rounded bg-gray-100 object-contain dark:bg-gray-900" src={media.url} alt={media.caption || '課程照片'} /></a>}<p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{media.caption || (media.media_type === 'video' ? '課程影片' : '課程照片')} · {media.is_public ? '已公開' : '私密附件'}</p></div>)}</div>}
    {coachView && <section aria-label="學員課後回饋" className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-600 dark:bg-gray-900/40"><h3 className="text-sm font-semibold text-gray-900 dark:text-white">學員課後回饋<span className="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400">唯讀</span></h3>{hasRating ? <><p className="mt-2 text-sm font-semibold text-amber-700 dark:text-amber-300" aria-label={`學員評分 ${rating} / 5 分`}>{'★'.repeat(rating)}{'☆'.repeat(5 - rating)}　{rating} / 5 分</p><p className="mt-2 break-words whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">{feedback || '學員未留下文字意見。'}</p></> : <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">學員尚未提交課後評價。</p>}</section>}
  </article>
}

function CourseFileUploader({ evaluationId, coachView, onBusyChange }: { evaluationId: number; coachView: boolean; onBusyChange: (busy: boolean) => void }) {
  const qc = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [percent, setPercent] = useState(0)
  const [message, setMessage] = useState('')
  const { data: limits, isError, refetch } = useQuery({ queryKey: ['course-upload-limits', coachView, evaluationId], queryFn: () => fetchCourseUploadLimits(evaluationId, coachView) })
  const limit = limits && file ? (/\.(mp4|mov|webm)$/i.test(file.name) || file.type.startsWith('video/') ? limits.video_limit_bytes : limits.photo_limit_bytes) : 0
  const tooLarge = Boolean(file && limit && file.size > limit)
  const upload = useMutation({
    mutationFn: () => uploadCourseFile(evaluationId, file!, coachView, setPercent),
    onMutate: () => { onBusyChange(true); setPercent(0); setMessage('') },
    onSuccess: async () => { setFile(null); if (input.current) input.current.value = ''; setMessage('附件已上傳，學員登入後即可查看。'); await qc.invalidateQueries({ queryKey: [coachView ? 'coach' : 'admin', 'evaluations'] }) },
    onError: (error: any) => setMessage(error?.response?.data?.msg || '上傳未完成，請檢查連線後重試；原評量內容不受影響。'),
    onSettled: () => onBusyChange(false),
  })
  return <section aria-label="上傳課程照片或影片" className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-600 dark:bg-gray-900/40">
    <label className="block text-sm font-semibold text-gray-900 dark:text-white">選擇課程照片或影片<input ref={input} type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm" disabled={upload.isPending} onChange={event => { setFile(event.target.files?.[0] || null); setMessage(''); upload.reset() }} className="mt-2 block min-h-11 w-full min-w-0 text-sm text-gray-700 file:mr-3 file:rounded-lg file:border-0 file:bg-violet-100 file:px-3 file:py-2 file:text-violet-800 dark:text-gray-200" /></label>
    <p className="mt-2 text-xs leading-6 text-gray-500 dark:text-gray-400">{limits ? `${limits.formats.join('、')}；照片上限 ${Math.round(limits.photo_limit_bytes / 1048576)} MB、影片 ${Math.round(limits.video_limit_bytes / 1048576)} MB。` : '正在讀取檔案限制…'}每次上傳一個檔案，成功後可繼續新增；附件立即保存，不會更改評語或評量完成狀態，也不會自動公開在官網。</p>
    {isError && <p role="alert" className="text-sm text-red-600 dark:text-red-300">無法讀取上傳設定。<button className="ml-2 min-h-11 underline" onClick={() => refetch()}>重新載入</button></p>}
    {tooLarge && <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-300">檔案超過上限 {Math.round(limit / 1048576)} MB，請選擇較小的檔案。</p>}
    {upload.isPending && <div role="status" className="mt-3 text-sm text-violet-700 dark:text-violet-300"><p>{percent === 100 ? '傳送完成，正在檢查與儲存…' : `正在上傳 ${percent}%`}</p><progress aria-label="附件上傳進度" className="mt-2 h-2 w-full" max={100} value={percent} /></div>}
    {message && <p role={upload.isError ? 'alert' : 'status'} className={`mt-2 break-words text-sm ${upload.isError ? 'text-red-600 dark:text-red-300' : 'text-emerald-700 dark:text-emerald-300'}`}>{message}</p>}
    <button type="button" disabled={!file || !limits || tooLarge || upload.isPending} onClick={() => upload.mutate()} className="mt-3 min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{upload.isPending ? '上傳中…' : upload.isError ? '重試上傳' : '上傳附件'}</button>
  </section>
}

function BookingLinksPanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const cart = useBookingStore(state => state.cart)
  const clearCart = useBookingStore(state => state.clearCart)
  const { campuses, selectedCampus } = useScopedCampuses()
  const activeCampuses = campuses.filter(campus => campus.is_active)
  const { data: rows = [] } = useQuery({ queryKey: ['admin', 'staff-booking-links'], queryFn: fetchStaffBookingLinks })
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 16)
  const [form, setForm] = useState({ campus: selectedCampus, title: '', expires_at: tomorrow })
  const selectedCartCampus = cart[0]?.campusId
  const cartCampusMatches = cart.length > 0 && cart.every(group => group.campusId === selectedCartCampus && group.courses.length > 0)
  useEffect(() => {
    if (selectedCartCampus && activeCampuses.some(campus => campus.id === selectedCartCampus)) {
      setForm(current => ({ ...current, campus: String(selectedCartCampus) }))
    }
  }, [selectedCartCampus, activeCampuses.map(campus => campus.id).join(',')])
  const create = useMutation({ mutationFn: () => createStaffBookingLink({ campus: Number(form.campus), title: form.title, expires_at: new Date(form.expires_at).toISOString(), cart_snapshot: cart }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'staff-booking-links'] }); clearCart(); setForm({ ...form, title: '' }); notify.success('已建立含課程明細的訂課連結') }, onError: (e: any) => notify.error(e?.response?.data?.cart_snapshot?.[0] || e?.response?.data?.msg || '建立失敗') })
  const copy = async (url: string) => {
    const bookingUrl = new URL(url, window.location.origin)
    const publicUrl = new URL(`${bookingUrl.pathname}${bookingUrl.search}${bookingUrl.hash}`, window.location.origin)
    try {
      await navigator.clipboard.writeText(publicUrl.toString())
      notify.success('連結已複製')
    } catch {
      notify.error('無法複製連結，請檢查瀏覽器權限')
    }
  }
  return <div className="space-y-5"><section className={cardClass}><h2 className="font-semibold text-gray-900 dark:text-white">建立代客訂課連結</h2><p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">先幫客人選好課程，再建立連結。客人登入後會直接看到訂單明細，填完資料即可送出及付款。</p><a href={`/${window.location.pathname.split('/')[1] || 'snowland'}/booking?staff_prepare=1`} className="mb-4 inline-flex items-center gap-2 rounded-lg border border-violet-300 px-4 py-2 text-sm font-semibold text-violet-700 dark:text-violet-300"><Plus size={16} />先幫客人選課</a><div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200">{cart.length ? <><b>已選 {cart.length} 組課程</b><ul className="mt-2 space-y-1">{cart.map(group => <li key={group.id}>{group.resortName} · {group.courses.map(course => `${course.courseTemplateName} ${course.date}`).join('、')} · {group.peopleCount} 人</li>)}</ul></> : '尚未選課。按「先幫客人選課」，完成後回到此頁建立連結。'}</div>{cart.length > 0 && !cartCampusMatches && <p role="alert" className="mb-3 text-sm text-red-600">同一連結只能包含同一校區且有課程的組別，請回選課畫面調整。</p>}<div className="grid items-end gap-3 md:grid-cols-4"><Field label="訂單歸屬校區"><select className={inputClass} value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value })}><option value="">請選校區</option>{activeCampuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field><Field label="用途／客人名稱"><input className={inputClass} placeholder="例如：王小姐三日課" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></Field><Field label="連結失效時間"><input className={inputClass} type="datetime-local" value={form.expires_at} onChange={e => setForm({ ...form, expires_at: e.target.value })} /></Field><button disabled={!cartCampusMatches || Number(form.campus) !== selectedCartCampus || !form.title || create.isPending} onClick={() => create.mutate()} className="flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}><Plus size={16} />建立連結</button></div></section><section className={cardClass}><div className="space-y-3">{rows.map(r => <div key={r.id} className="flex flex-col gap-3 rounded-lg border border-gray-100 p-4 dark:border-gray-700 sm:flex-row sm:items-center sm:justify-between"><div><b>{r.title}</b><p className="text-xs text-gray-500 dark:text-gray-400">{r.is_available ? '可使用' : '已失效'} · 到期 {new Date(r.expires_at).toLocaleString()}</p></div><button disabled={!r.is_available} onClick={() => copy(r.url)} className="rounded-lg border border-violet-200 px-3 py-2 text-sm font-semibold text-violet-600 disabled:opacity-40">複製連結</button></div>)}{!rows.length && <Empty text="尚未建立連結。" />}</div></section></div>
}

const insuranceStatuses = { pending: '尚未投保', checking: '對資料中', processing: '處理中', insured: '已投保完成' }
const insuranceStatusColors = { pending: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200', checking: 'bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-200', processing: 'bg-violet-100 text-violet-900 dark:bg-violet-900/40 dark:text-violet-200', insured: 'bg-green-100 text-green-900 dark:bg-green-900/40 dark:text-green-200' }

function InsurancePanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const [status, setStatus] = useState('all')
  const [processingStatus, setProcessingStatus] = useState('all')
  const [selectedDate, setSelectedDate] = useState('')
  const [reminder, setReminder] = useState<{id:number;field:'insurance'|'waiver'}|null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const { data: rows = [], isLoading, isError, refetch } = useQuery({ queryKey: ['admin', 'insurance-records', status], queryFn: () => fetchInsuranceRecords(status) })
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const filteredRows = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return rows.filter(row => (processingStatus === 'all' || row.insurance_processing_status === processingStatus)
      && (!keyword || `${row.member_name} ${row.sn} ${row.order_number} ${row.campus_name}`.toLowerCase().includes(keyword)))
  }, [rows, search, processingStatus])
  const pageSize = 20
  const datedRows = selectedDate ? insuranceDayRecords(filteredRows,selectedDate) : filteredRows
  const pageCount = Math.max(Math.ceil(datedRows.length / pageSize), 1)
  const currentPage = Math.min(page, pageCount)
  const visibleRows = datedRows.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const complete = useMutation({ mutationFn: ({ id, field }: { id: number; field: 'insurance' | 'waiver' }) => completeInsuranceRecord(id, field), onSuccess: (_, { id }) => { qc.invalidateQueries({ queryKey: ['admin', 'insurance-records'] }); qc.invalidateQueries({ queryKey: ['admin', 'insurance-detail', id] }); notify.success('完成狀態已更新') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '更新失敗') })
  return <section className={cardClass}>
    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div><h2 className="font-semibold text-gray-900 dark:text-white">保險與聲明書資料</h2><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">先核對學員資料，再開啟「查看資料」更新投保進度。資料填齊不等於已投保；紙本確認也不等於線上簽署。</p></div>
      <div className="flex flex-col flex-wrap gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="insurance-status">資料完成狀態</label>
        <select id="insurance-status" className={`${inputClass} sm:w-auto`} value={status} onChange={event => { setStatus(event.target.value); setPage(1); setExpandedId(null) }}><option value="missing">待補資料</option><option value="all">全部資料</option><option value="completed">已標記完成</option></select>
        <select aria-label="投保作業狀態" className={`${inputClass} sm:w-auto`} value={processingStatus} onChange={event => { setProcessingStatus(event.target.value); setPage(1); setExpandedId(null) }}><option value="all">全部投保進度</option>{Object.entries(insuranceStatuses).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select>
        <input aria-label="搜尋學員、訂單或校區" className={`${inputClass} sm:max-w-xs`} placeholder="搜尋學員、訂單或校區" value={search} onChange={event => { setSearch(event.target.value); setPage(1); setExpandedId(null) }} />
      </div>
    </div>
    {isLoading ? <Loader2 aria-label="載入資料中" className="mt-4 animate-spin" /> : isError ? <div role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">資料載入失敗，請稍後重試。<button className="ml-3 min-h-11 underline" onClick={() => refetch()}>重新載入</button></div> : <>
      <InsuranceCalendar rows={filteredRows} selectedDate={selectedDate} onSelect={date=>{setSelectedDate(date);setPage(1);setExpandedId(null)}} />
      <div className="mt-4 space-y-3">{visibleRows.map(row => <div key={row.id} className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0"><b className="text-gray-900 dark:text-white">{row.member_name}</b><p className="break-words text-xs text-gray-500 dark:text-gray-400">{[row.sn || row.order_number, row.campus_name, row.course_dates.join('、')].filter(Boolean).join(' · ')}</p><p className="mt-2 text-xs text-gray-600 dark:text-gray-300">保險資料：{row.insurance_completed_at ? '已填寫／已確認' : '待補'}　聲明書：{row.waiver_completed_at ? '已完成' : '待補'}</p><p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-600 dark:text-gray-300"><span className={`rounded px-2 py-1 ${insuranceStatusColors[row.insurance_processing_status]}`}>{insuranceStatuses[row.insurance_processing_status]}</span><span>投保金額：{row.insurance_premium_amount === null ? '尚未填寫' : `${row.insurance_premium_currency} ${row.insurance_premium_amount}`}</span></p></div>
          <div className="flex flex-wrap gap-2">
            <button aria-expanded={expandedId === row.id} aria-controls={`insurance-detail-${row.id}`} onClick={() => setExpandedId(expandedId === row.id ? null : row.id)} className="min-h-11 rounded-lg border border-gray-300 px-3 py-2 text-xs font-semibold text-gray-700 dark:border-gray-600 dark:text-gray-200">{expandedId === row.id ? '收合資料' : '查看資料'}</button>
            {row.can_remind && !row.insurance_completed_at && <button onClick={()=>setReminder({id:row.id,field:'insurance'})} className="min-h-11 rounded-lg border border-violet-300 px-3 py-2 text-xs font-semibold text-violet-700 dark:border-violet-500 dark:text-violet-200">提醒補保險資料</button>}
            {row.can_remind && !row.waiver_completed_at && <button onClick={()=>setReminder({id:row.id,field:'waiver'})} className="min-h-11 rounded-lg border border-violet-300 px-3 py-2 text-xs font-semibold text-violet-700 dark:border-violet-500 dark:text-violet-200">提醒補聲明書</button>}
            {row.can_mark_complete && !row.insurance_completed_at && <button disabled={complete.isPending} onClick={() => complete.mutate({ id: row.id, field: 'insurance' })} className="min-h-11 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">標記保險資料已確認</button>}
            {row.can_mark_complete && !row.waiver_completed_at && <button disabled={complete.isPending} onClick={() => complete.mutate({ id: row.id, field: 'waiver' })} className="min-h-11 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">標記聲明書完成</button>}
          </div>
        </div>
        {!row.can_mark_complete && <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">僅供查看，不能修改學員資料或標記完成。</p>}
        {expandedId === row.id && <InsuranceDetail id={row.id} />}
      </div>)}{!visibleRows.length && <Empty text={rows.length ? '找不到符合條件的學員。' : status === 'missing' ? '目前沒有待補的學員；可切換全部資料查看。' : '目前沒有符合完成狀態的學員資料。'} />}</div>
      {datedRows.length > pageSize && <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-gray-500 dark:text-gray-400"><span>共 {datedRows.length} 位，顯示第 {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, datedRows.length)} 位</span><div className="flex gap-2"><button disabled={currentPage === 1} onClick={() => { setPage(value => Math.max(value - 1, 1)); setExpandedId(null) }} className="min-h-11 rounded-lg border border-gray-200 px-3 py-2 disabled:opacity-40 dark:border-gray-600">上一頁</button><span className="px-2 py-2">{currentPage} / {pageCount}</span><button disabled={currentPage === pageCount} onClick={() => { setPage(value => Math.min(value + 1, pageCount)); setExpandedId(null) }} className="min-h-11 rounded-lg border border-gray-200 px-3 py-2 disabled:opacity-40 dark:border-gray-600">下一頁</button></div></div>}
    </>}
    {reminder && <InsuranceReminderDialog {...reminder} onClose={()=>setReminder(null)} />}
  </section>
}

function InsuranceDetail({ id }: { id: number }) {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['admin', 'insurance-detail', id], queryFn: () => fetchInsuranceRecord(id), gcTime: 0 })
  const fields = [['full_name', '學員姓名'], ['birth_date', '出生日期'], ['id_number', '身分證／護照號碼'], ['email', '學員 Email'], ['phone', '聯絡電話'], ['emergency_contact', '緊急聯絡人'], ['emergency_phone', '緊急聯絡電話'], ['guardian_name', '法定代理人姓名'], ['guardian_relationship', '與學員的關係']]
  return <div id={`insurance-detail-${id}`} className="mt-4 border-t border-gray-200 pt-4 dark:border-gray-700">
    {isLoading ? <p role="status" className="text-sm text-gray-500 dark:text-gray-400">正在載入學員資料…</p> : isError || !data ? <p role="alert" className="text-sm text-red-600 dark:text-red-400">無法載入這位學員的資料。<button onClick={() => refetch()} className="ml-3 min-h-11 underline">重試</button></p> : <>
      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{fields.map(([key, label]) => <div key={key}><dt className="text-xs text-gray-500 dark:text-gray-400">{label}</dt><dd className="mt-1 break-all text-sm text-gray-900 dark:text-white">{(key === 'email' ? data.member_email : data.insurance_data?.[key]) || '尚未填寫'}</dd></div>)}</dl>
      <div className="mt-5 rounded-lg bg-gray-50 p-4 text-sm text-gray-700 dark:bg-gray-900 dark:text-gray-200">
        <p>簽署身分：{data.insurance_data?.waiver_signer_role === 'guardian' ? '法定代理人' : data.waiver_signature ? '學員本人' : '尚未線上簽署'}</p>
        <p className="mt-2 break-all">線上簽署姓名：{data.waiver_signature || (data.waiver_completed_at ? '人工標記完成（無線上簽名紀錄）' : '尚未簽署')}</p>
        <p className="mt-2 break-all">簽署文件版本：{data.waiver_document_version || '無線上版本紀錄'}</p>
        <p className="mt-2">聲明書完成時間：{data.waiver_completed_at ? new Date(data.waiver_completed_at).toLocaleString('zh-TW') : '尚未完成'}</p>
        <p className="mt-2">宣傳影像授權：{data.media_consent === 'agree' ? '同意公開宣傳' : data.media_consent === 'decline' ? '不同意公開宣傳' : '尚未選擇'}</p>
        {data.waiver_document_snapshot && <details className="mt-3"><summary className="min-h-11 cursor-pointer py-3 font-semibold">查看當時簽署的聲明書內容</summary><div className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-gray-200 bg-white p-4 leading-7 dark:border-gray-700 dark:bg-gray-800">{data.waiver_document_snapshot}</div></details>}
      </div>
      <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">以上為會員填寫及簽署的唯讀紀錄，不會因後台標記完成而修改簽名或文件內容。</p>
      {data.can_mark_complete && <InsuranceProcessingForm key={`${data.id}-${data.insurance_processing_updated_at || 'new'}`} row={data} />}
    </>}
  </div>
}

function InsuranceProcessingForm({ row }: { row: InsuranceRecordDetail }) {
  const qc = useQueryClient(); const notify = useNotification()
  const [status, setStatus] = useState(row.insurance_processing_status)
  const [amount, setAmount] = useState(row.insurance_premium_amount ?? '')
  const [currency, setCurrency] = useState(row.insurance_premium_currency)
  const [confirmed, setConfirmed] = useState(false)
  const needsConfirmation = status === 'insured' && row.insurance_processing_status !== 'insured'
  const changed = status !== row.insurance_processing_status || amount !== (row.insurance_premium_amount ?? '') || currency !== row.insurance_premium_currency
  const valid = (!currency || /^[A-Z]{3}$/.test(currency)) && (!amount || (Number.isFinite(Number(amount)) && Number(amount) >= 0 && Number(amount) <= 99999999.99 && /^[A-Z]{3}$/.test(currency))) && (!needsConfirmation || confirmed)
  const save = useMutation({ mutationFn: () => saveInsuranceProcessing(row.id, { status, premium_amount: amount === '' ? null : amount, currency, expected_updated_at: row.insurance_processing_updated_at, confirm_insured: confirmed }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin','insurance-records'] }); qc.invalidateQueries({ queryKey: ['admin','insurance-detail',row.id] }); notify.success('投保作業紀錄已儲存；系統不會自動投保') },
    onError: (error: any) => { if (error?.response?.status === 409) qc.invalidateQueries({ queryKey: ['admin','insurance-detail',row.id] }); notify.error(String(error?.response?.data?.msg || Object.values(error?.response?.data || {})[0] || '儲存失敗，請重新核對')) },
  })
  return <form onSubmit={event => { event.preventDefault(); if (changed && valid && !save.isPending) save.mutate() }} className="mt-5 rounded-lg border border-gray-200 p-4 dark:border-gray-600">
    <h3 className="font-semibold text-gray-900 dark:text-white">投保作業回報</h3>
    <p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">這是人工作業紀錄，不會向保險公司送件，也不會改動學員資料或聲明書。金額未知可留空，不會當作0元。</p>
    <fieldset disabled={save.isPending} className="grid gap-3 sm:grid-cols-3">
      <Field label="投保進度"><select className={inputClass} value={status} onChange={event => { setStatus(event.target.value as typeof status); setConfirmed(false) }}>{Object.entries(insuranceStatuses).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <Field label="投保金額（選填）"><input className={inputClass} type="number" min="0" max="99999999.99" step="0.01" value={amount} onChange={event => setAmount(event.target.value)} /></Field>
      <Field label="幣別代碼"><input className={inputClass} maxLength={3} pattern="[A-Z]{3}" placeholder="例如 TWD、JPY" required={amount !== ''} value={currency} onChange={event => setCurrency(event.target.value.toUpperCase())} /></Field>
    </fieldset>
    {needsConfirmation && <label className="mt-4 flex min-h-11 items-center gap-2 text-sm text-gray-700 dark:text-gray-200"><input type="checkbox" checked={confirmed} disabled={save.isPending} onChange={event => setConfirmed(event.target.checked)} />我已在保險公司完成投保，本次僅記錄結果</label>}
    <button type="submit" disabled={!changed || !valid || save.isPending} className="mt-4 min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{save.isPending ? '儲存中…' : '儲存投保進度'}</button>
    {row.insurance_processing_updated_at && <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">最後更新：{new Date(row.insurance_processing_updated_at).toLocaleString('zh-TW')}</p>}
  </form>
}

function Empty({ text }: { text: string }) { return <div className="py-8 text-center text-sm text-gray-400">{text}</div> }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="block"><span className="mb-1 block text-xs font-semibold text-gray-600 dark:text-gray-300">{label}</span>{children}</label> }
