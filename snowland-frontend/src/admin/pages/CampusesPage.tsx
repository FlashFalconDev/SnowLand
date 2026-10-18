import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Building2, Check, ChevronRight, Edit3, Loader2, MapPin, Plus, ShieldCheck, Trash2, X } from 'lucide-react'
import { useNotification } from '../context'
import { fetchAllAccessibleResorts } from '../api/resorts'
import { fetchAdminMe } from '../api/auth'
import { useAdminDialog } from '../hooks/useAdminDialog'
import {
  createCampus, createOperatingPolicy, deleteCampus, deleteOperatingPolicy, fetchCampuses, fetchOperatingPolicies, updateCampus, updateOperatingPolicy,
  type Campus, type CampusWriteData, type OperatingPolicy,
} from '../api/campuses'

const EMPTY_FORM: CampusWriteData = {
  name: '', code: '', description: '', is_active: true, display_order: 0, resort_ids: [],
}

function errorMessage(error: unknown, fallback: string) {
  const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data
  if (typeof data?.msg === 'string') return data.msg
  if (typeof data?.detail === 'string') return data.detail
  const fieldLabels: Record<string, string> = {
    name: '校區名稱', code: '內部代碼', resort_ids: '可用雪場', non_field_errors: '資料',
  }
  const fieldErrors = Object.entries(fieldLabels).flatMap(([field, label]) => {
    const value = data?.[field]
    const messages = Array.isArray(value) ? value : [value]
    return messages.filter((item): item is string => typeof item === 'string').map((item) => `${label}：${item}`)
  })
  return fieldErrors.join('；') || fallback
}

export default function CampusesPage() {
  const queryClient = useQueryClient()
  const notification = useNotification()
  const [editing, setEditing] = useState<Campus | null>(null)
  const [form, setForm] = useState<CampusWriteData>(EMPTY_FORM)
  const [showForm, setShowForm] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [deleting, setDeleting] = useState<Campus | null>(null)
  const [deleteError, setDeleteError] = useState('')
  const [policyCampusId, setPolicyCampusId] = useState<number | null>(null)

  const campusesQuery = useQuery({ queryKey: ['admin', 'campuses'], queryFn: fetchCampuses })
  const resortsQuery = useQuery({ queryKey: ['admin', 'resorts', 'all-accessible'], queryFn: fetchAllAccessibleResorts })
  const policiesQuery = useQuery({ queryKey: ['admin', 'operating-policies'], queryFn: fetchOperatingPolicies })
  const adminMeQuery = useQuery({ queryKey: ['admin', 'me'], queryFn: fetchAdminMe })

  const saveCampus = useMutation({
    mutationFn: (data: CampusWriteData) => editing ? updateCampus(editing.id, data) : createCampus(data),
    onMutate: () => setSaveError(''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'campuses'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'operating-policies'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'me'] })
      window.dispatchEvent(new Event('snowland:campuses-updated'))
      notification.success(editing ? '校區已更新' : '校區已建立')
      setShowForm(false)
    },
    onError: (error) => {
      const message = errorMessage(error, '儲存校區失敗，請稍後再試')
      setSaveError(message)
      notification.error(message)
    },
  })

  const removeCampus = useMutation({
    mutationFn: deleteCampus,
    onMutate: () => setDeleteError(''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'campuses'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'me'] })
      window.dispatchEvent(new Event('snowland:campuses-updated'))
      notification.success('校區已刪除')
      setDeleting(null)
    },
    onError: (error) => {
      const message = errorMessage(error, '無法刪除，建議改為停用')
      setDeleteError(message)
      notification.error(message)
    },
  })

  const dialogBusy = saveCampus.isPending || removeCampus.isPending
  const closeDialog = () => { if (!dialogBusy) { setShowForm(false); setDeleting(null) } }
  const campusDialog = useAdminDialog(showForm || !!deleting, dialogBusy, closeDialog)
  const openDelete = (campus: Campus) => { setDeleteError(''); setDeleting(campus) }

  const campuses = campusesQuery.data || []
  const activeCampuses = campuses.filter((campus) => campus.is_active)
  const inactiveCampuses = campuses.filter((campus) => !campus.is_active)
  const resorts = resortsQuery.data || []
  const policies = policiesQuery.data || []
  const canManageCampuses = !!(adminMeQuery.data?.user?.is_superuser || adminMeQuery.data?.user?.role === 'hq_admin')
  const companyPolicy = useMemo(() => policies.find((item) => item.campus === null), [policies])
  const selectedPolicy = useMemo(() => policies.find((item) => item.campus === policyCampusId), [policies, policyCampusId])
  const activePolicy = selectedPolicy || companyPolicy

  useEffect(() => {
    if (policyCampusId !== null && !activeCampuses.some((campus) => campus.id === policyCampusId)) {
      setPolicyCampusId(null)
    }
  }, [activeCampuses, policyCampusId])

  const openNew = () => {
    setEditing(null)
    setSaveError('')
    setForm({ ...EMPTY_FORM, display_order: campuses.length })
    setShowForm(true)
  }

  const openEdit = (campus: Campus) => {
    setEditing(campus)
    setSaveError('')
    setForm({
      name: campus.name,
      code: campus.code,
      description: campus.description || '',
      is_active: campus.is_active,
      display_order: campus.display_order,
      resort_ids: campus.resort_ids || [],
    })
    setShowForm(true)
  }

  if (campusesQuery.isLoading || resortsQuery.isLoading || policiesQuery.isLoading) {
    return <div className="min-h-[50vh] flex items-center justify-center text-gray-500"><Loader2 className="animate-spin mr-2" />載入校區資料…</div>
  }

  if (campusesQuery.isError || resortsQuery.isError || policiesQuery.isError) {
    const retrying = campusesQuery.isFetching || resortsQuery.isFetching || policiesQuery.isFetching
    return <div role="alert" className="mx-auto max-w-xl rounded-xl border border-red-200 bg-white p-6 text-center dark:border-red-900 dark:bg-gray-800">
      <AlertCircle className="mx-auto mb-3 text-red-500" size={28} />
      <h1 className="text-lg font-semibold text-gray-900 dark:text-white">校區或雪場資料載入失敗</h1>
      <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">為避免誤改校區，已暫停編輯。請重試載入資料。</p>
      <button type="button" disabled={retrying} onClick={() => {
        setShowForm(false)
        setDeleting(null)
        void Promise.all([campusesQuery.refetch(), resortsQuery.refetch(), policiesQuery.refetch()])
      }} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50">
        {retrying && <Loader2 className="animate-spin" size={16} />}{retrying ? '重試中…' : '重新載入'}
      </button>
    </div>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">校區與雪場</h1>
          <p className="mt-1 text-gray-500 dark:text-gray-400">先建立校區，再選可用雪場；同一雪場可供多校區使用。{canManageCampuses && '總部可在此管理全部校區，不受上方範圍限制。'}</p>
        </div>
        {canManageCampuses && <button onClick={openNew} className="inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:opacity-90">
          <Plus size={16} />新增校區
        </button>}
      </div>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-900 dark:text-white">使用中校區（{activeCampuses.length}）</h2>
          <span className="text-sm text-gray-500 dark:text-gray-400">雪場可重複勾選</span>
        </div>
        {activeCampuses.length === 0 ? (
          canManageCampuses ? <button onClick={openNew} className="w-full rounded-xl border border-dashed border-violet-300 p-10 text-violet-600 hover:bg-violet-50 dark:border-violet-700 dark:hover:bg-violet-900/20">目前沒有使用中的校區，點這裡新增</button> : <p className="rounded-xl border border-dashed border-gray-300 p-10 text-center text-gray-500">目前沒有使用中的校區，請聯絡總部管理員。</p>
        ) : (
          <div className="grid lg:grid-cols-2 gap-4">
            {activeCampuses.map((campus) => (
              <article key={campus.id} className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400"><Building2 size={20} /></div>
                    <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="truncate font-semibold text-gray-900 dark:text-white">{campus.name}</h3>
                      <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${campus.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>{campus.is_active ? '使用中' : '已停用'}</span>
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{campus.description || '尚未填寫備註'}</p>
                    </div>
                  </div>
                </div>
                {canManageCampuses && <div className="mt-4 flex gap-2 sm:justify-end">
                  <button onClick={() => openEdit(campus)} aria-label={`編輯 ${campus.name}`} className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-3 text-sm font-medium text-violet-700 hover:bg-violet-100 dark:border-violet-700 dark:bg-violet-900/20 dark:text-violet-300 dark:hover:bg-violet-900/40 sm:flex-none"><Edit3 size={16} />編輯校區</button>
                  <button onClick={() => openDelete(campus)} aria-label={`刪除 ${campus.name}`} className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg border border-red-200 px-3 text-sm font-medium text-red-600 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20 sm:flex-none"><Trash2 size={16} />刪除校區</button>
                </div>}
                <div className="mt-4 border-t border-gray-100 pt-4 dark:border-gray-700">
                  <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200"><MapPin size={16} />可使用雪場</div>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {campus.resort_names.length ? campus.resort_names.map((name) => <span key={name} className="rounded-lg bg-gray-100 px-2.5 py-1 text-sm text-gray-700 dark:bg-gray-700 dark:text-gray-200">{name}</span>) : <span className="text-sm text-amber-600">還沒有勾選雪場</span>}
                  </div>
                </div>
                <div className="mt-4 flex gap-6 border-t border-gray-100 pt-4 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400"><span>員工 <b className="text-gray-900 dark:text-white">{campus.staff_count}</b> 人</span><span>教練 <b className="text-gray-900 dark:text-white">{campus.coach_count}</b> 人</span></div>
              </article>
            ))}
          </div>
        )}
        {inactiveCampuses.length > 0 && (
          <details className="mt-4 rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
            <summary className="cursor-pointer px-5 py-4 text-sm font-medium text-gray-600 dark:text-gray-300">已停用校區（{inactiveCampuses.length}）— 不再用於新訂單，點此查看或重新啟用</summary>
            <div className="space-y-2 border-t border-gray-100 px-5 py-4 dark:border-gray-700">
              {inactiveCampuses.map((campus) => (
                <div key={campus.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-gray-50 px-4 py-3 text-sm dark:bg-gray-700">
                  <div><b className="text-gray-900 dark:text-white">{campus.name}</b><p className="mt-1 text-gray-500 dark:text-gray-300">員工 {campus.staff_count} 人 · 教練 {campus.coach_count} 人 · 雪場 {campus.resort_names.length} 個</p></div>
                  {canManageCampuses && <button onClick={() => openEdit(campus)} className="rounded-lg border border-gray-300 px-3 py-2 font-medium text-violet-700 hover:bg-violet-50 dark:border-gray-500 dark:text-violet-300 dark:hover:bg-gray-600">編輯／重新啟用</button>}
                </div>
              ))}
            </div>
          </details>
        )}
      </section>

      {activePolicy && <PolicyCard campuses={activeCampuses} policy={activePolicy} selectedCampusId={policyCampusId} hasOverride={policyCampusId === null || !!selectedPolicy} canEdit={canManageCampuses || policyCampusId !== null} onSelect={setPolicyCampusId} onSaved={() => queryClient.invalidateQueries({ queryKey: ['admin', 'operating-policies'] })} />}

      {showForm && (
        <div className="fixed inset-0 z-[70] flex items-end justify-center bg-black/50 p-0 animate-fadeIn md:items-center md:p-4" onMouseDown={(event) => event.target === event.currentTarget && closeDialog()}>
          <form ref={(element) => { campusDialog.current = element }} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="campus-form-title" onSubmit={(event) => { event.preventDefault(); if (!saveCampus.isPending) saveCampus.mutate(form) }} className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl bg-white shadow-xl dark:bg-gray-800 md:max-w-xl md:rounded-2xl">
            <div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)' }}><div><h2 id="campus-form-title" className="text-lg font-semibold">{editing ? '編輯校區' : '新增校區'}</h2><p className="mt-0.5 text-xs text-white/80">設定校區資料與可使用的雪場</p></div><button type="button" disabled={dialogBusy} onClick={closeDialog} aria-label="關閉" className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg p-1 text-white/80 hover:bg-white/10 hover:text-white"><X size={20} /></button></div>
            <div className="space-y-5 overflow-y-auto p-6">
              <label className="block"><span className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">校區名稱 <span className="text-red-500">*</span></span><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例如：北海道校區" className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" /></label>
              <details className="rounded-lg border border-gray-200 px-3 py-2 dark:border-gray-600">
                <summary className="cursor-pointer text-sm font-medium text-gray-700 dark:text-gray-200">進階設定：內部代碼{!editing && '（可不填）'}</summary>
                <label className="mt-3 block"><span className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">內部代碼 {editing && <span className="text-red-500">*</span>}</span><input required={!!editing} pattern="[a-z0-9-]+" maxLength={50} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })} placeholder="不填則由系統產生" className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" /><span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">{form.code ? <>實際儲存：<strong className="font-medium text-gray-700 dark:text-gray-200">{form.code}</strong></> : '留空時系統會自動產生；一般不需要修改。'}</span></label>
              </details>
              <label className="block"><span className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">備註</span><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} className="w-full resize-none rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" /></label>
              <fieldset><legend className="font-medium">這個校區可使用哪些雪場？</legend><p className="mb-2 mt-1 text-xs text-gray-500 dark:text-gray-400">可複選；同一雪場也可在其他校區使用。</p><div className="space-y-2">{resorts.map((resort) => { const checked = form.resort_ids.includes(resort.id); return <label key={resort.id} className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 dark:border-gray-600 ${checked ? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20' : ''}`}><input type="checkbox" checked={checked} onChange={() => setForm({ ...form, resort_ids: checked ? form.resort_ids.filter((id) => id !== resort.id) : [...form.resort_ids, resort.id] })} /><span className="flex-1">{resort.display_name}</span>{checked && <Check className="text-violet-600" size={18} />}</label> })}</div></fieldset>
              <label className="flex items-center justify-between rounded-lg border p-3 dark:border-gray-600"><span><b>啟用校區</b><small className="block text-gray-500 dark:text-gray-400">停用後仍保留舊訂單</small></span><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} className="w-5 h-5" /></label>
            </div>
            {saveError && <p role="alert" className="mx-6 mb-0 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200">{saveError}</p>}
            <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700"><button type="button" disabled={dialogBusy} onClick={closeDialog} className="min-h-11 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">取消</button><button disabled={saveCampus.isPending} className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">{saveCampus.isPending && <Loader2 size={14} className="animate-spin" />}{saveCampus.isPending ? '儲存中…' : '儲存校區'}</button></div>
          </form>
        </div>
      )}

      {deleting && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 p-4 animate-fadeIn">
          <div ref={(element) => { campusDialog.current = element }} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="campus-delete-title" className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-xl dark:bg-gray-800">
            <div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)' }}><h3 id="campus-delete-title" className="text-lg font-semibold">刪除校區</h3><button disabled={dialogBusy} onClick={closeDialog} aria-label="關閉" className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg p-1 text-white/80 hover:bg-white/10 hover:text-white"><X size={18} /></button></div>
            <div className="p-6"><p className="text-sm text-gray-700 dark:text-gray-300">確定刪除「<b className="text-gray-900 dark:text-white">{deleting.name}</b>」？</p><p className="mt-2 text-xs text-gray-500 dark:text-gray-400">已有訂單或人員使用時，系統會阻止刪除；可改用停用保留舊資料。</p></div>
            {deleteError && <p role="alert" className="mx-6 mb-4 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200">{deleteError}</p>}
            <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700"><button disabled={dialogBusy} onClick={closeDialog} className="min-h-11 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">取消</button><button onClick={() => removeCampus.mutate(deleting.id)} disabled={removeCampus.isPending} className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">{removeCampus.isPending && <Loader2 size={14} className="animate-spin" />}確認刪除</button></div>
          </div>
        </div>
      )}
    </div>
  )
}

function PolicyCard({ campuses, policy, selectedCampusId, hasOverride, canEdit, onSelect, onSaved }: { campuses: Campus[]; policy: OperatingPolicy; selectedCampusId: number | null; hasOverride: boolean; canEdit: boolean; onSelect: (id: number | null) => void; onSaved: () => void }) {
  const notification = useNotification()
  const [draft, setDraft] = useState(policy)
  const [confirmReset, setConfirmReset] = useState(false)
  const mutation = useMutation({ mutationFn: () => hasOverride
    ? updateOperatingPolicy(policy.id, draft)
    : createOperatingPolicy({
        campus: selectedCampusId,
        unpaid_hold_days: draft.unpaid_hold_days,
        provisional_extra_groups: draft.provisional_extra_groups,
        cancellation_fee_percent: draft.cancellation_fee_percent,
        cancellation_rules: draft.cancellation_rules,
        leave_advance_days: draft.leave_advance_days,
        leave_daily_coach_limit: draft.leave_daily_coach_limit,
        leave_max_consecutive_days: draft.leave_max_consecutive_days,
        course_reminder_days: draft.course_reminder_days,
        settings: draft.settings,
      }), onSuccess: () => { notification.success('營運規則已儲存'); onSaved() }, onError: (error) => notification.error(errorMessage(error, '儲存失敗')) })
  const resetMutation = useMutation({
    mutationFn: () => deleteOperatingPolicy(policy.id),
    onSuccess: () => {
      setConfirmReset(false)
      notification.success('已改回沿用全公司預設')
      onSaved()
    },
    onError: (error) => notification.error(errorMessage(error, '無法重設校區規則')),
  })
  const resetDialog = useAdminDialog(confirmReset, resetMutation.isPending, () => setConfirmReset(false))
  useEffect(() => setDraft(policy), [policy, selectedCampusId])
  const refundRulesValid = draft.cancellation_rules.length > 0 && draft.cancellation_rules.every((rule, index) =>
    Number.isInteger(rule.days_before) && rule.days_before >= 0 && Number.isInteger(rule.refund_percent) && rule.refund_percent >= 0 && rule.refund_percent <= 100 &&
    draft.cancellation_rules.findIndex(other => other.days_before === rule.days_before) === index)
  const feeValid = Number(draft.cancellation_fee_percent) >= 0 && Number(draft.cancellation_fee_percent) <= 100
  const numberField = (key: keyof OperatingPolicy, label: string, suffix: string) => (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">{label}</span>
      <div className="flex items-center">
        <input type="number" min={0} value={String(draft[key])} onChange={(e) => setDraft({ ...draft, [key]: Number(e.target.value) })} className="w-full rounded-l-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" />
        <span className="rounded-r-lg border border-l-0 border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300">{suffix}</span>
      </div>
    </label>
  )
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2 font-semibold text-gray-900 dark:text-white"><ShieldCheck className="text-violet-600" size={18} />營運規則</div>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">先用公司預設；有需要再針對個別校區調整。</p>
        </div>
        <select aria-label="營運規則適用範圍" value={selectedCampusId ?? 'company'} onChange={(e) => onSelect(e.target.value === 'company' ? null : Number(e.target.value))} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"><option value="company">全公司預設</option>{campuses.map((campus) => <option key={campus.id} value={campus.id}>{campus.name}</option>)}</select>
      </div>
      {selectedCampusId !== null && !hasOverride && <p className="mb-4 rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-800 dark:bg-blue-900/20 dark:text-blue-200">目前沿用全公司預設；修改並儲存後，這個校區才會使用專屬規則。</p>}
      {selectedCampusId !== null && hasOverride && <p className="mb-4 rounded-lg bg-violet-50 px-3 py-2 text-sm text-violet-800 dark:bg-violet-900/20 dark:text-violet-200">此校區使用專屬規則；全公司預設日後變更時，不會自動套用到這裡。</p>}
      {!canEdit && <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/20 dark:text-amber-200">全公司預設僅供查看；如需修改，請聯絡總部管理員。</p>}
      <fieldset disabled={!canEdit} className={!canEdit ? 'opacity-60' : undefined}>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{numberField('unpaid_hold_days', '未付款保留', '天')}{numberField('provisional_extra_groups', '未付款可加排', '組')}{numberField('leave_advance_days', '請假需提前', '天')}{numberField('leave_daily_coach_limit', '每日請假上限', '人')}</div>
      <div className="mt-5 border-t border-gray-200 pt-4 dark:border-gray-700">
        <h3 className="font-semibold text-gray-900 dark:text-white">取消退費規則</h3>
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">訂單管理取消時，系統依距上課天數選擇符合的級距；手續費依原訂單金額另扣。特殊情況可在該訂單手動指定。</p>
        <label className="mt-4 block max-w-xs text-sm text-gray-700 dark:text-gray-300">退款手續費（原價百分比）
          <input type="number" min="0" max="100" step="0.01" aria-label="退款手續費百分比" value={draft.cancellation_fee_percent} onChange={e => setDraft({ ...draft, cancellation_fee_percent: e.target.value })} className="mt-1 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-600 dark:bg-gray-700 dark:text-white" />
        </label>
        <div className="mt-4 space-y-2">{draft.cancellation_rules.map((rule, index) => <div key={index} className="flex flex-wrap items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <span>課前至少</span><input aria-label={`第 ${index + 1} 級距天數`} type="number" min="0" step="1" value={rule.days_before} onChange={e => setDraft({ ...draft, cancellation_rules: draft.cancellation_rules.map((item, position) => position === index ? { ...item, days_before: Number(e.target.value) } : item) })} className="w-24 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-600 dark:bg-gray-700 dark:text-white" /><span>天，退</span>
          <input aria-label={`第 ${index + 1} 級距比例`} type="number" min="0" max="100" step="1" value={rule.refund_percent} onChange={e => setDraft({ ...draft, cancellation_rules: draft.cancellation_rules.map((item, position) => position === index ? { ...item, refund_percent: Number(e.target.value) } : item) })} className="w-24 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-600 dark:bg-gray-700 dark:text-white" /><span>%</span>
          <button aria-label={`移除第 ${index + 1} 級距`} disabled={draft.cancellation_rules.length <= 1} onClick={() => setDraft({ ...draft, cancellation_rules: draft.cancellation_rules.filter((_, position) => position !== index) })} className="rounded-lg border border-gray-300 px-3 py-2 disabled:opacity-40 dark:border-gray-600">移除</button>
        </div>)}</div>
        <button onClick={() => setDraft({ ...draft, cancellation_rules: [...draft.cancellation_rules, { days_before: Math.max(-1, ...draft.cancellation_rules.map(rule => rule.days_before)) + 1, refund_percent: 100 }] })} className="mt-3 rounded-lg border border-violet-400 px-3 py-2 text-sm text-violet-700 dark:text-violet-300">＋ 新增退費級距</button>
        {(!refundRulesValid || !feeValid) && <p role="alert" className="mt-2 text-sm text-red-600">請確認天數不重複且為非負整數、退費比例與手續費介於 0～100%。</p>}
      </div>
      <div className="mt-5 flex flex-wrap gap-3 border-t border-gray-200 pt-4 dark:border-gray-700">
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !refundRulesValid || !feeValid} className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">儲存營運規則<ChevronRight size={16} /></button>
        {selectedCampusId !== null && hasOverride && <button type="button" onClick={() => setConfirmReset(true)} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700">改回沿用全公司預設</button>}
      </div>
      </fieldset>
      {confirmReset && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 p-4">
        <div ref={(element) => { resetDialog.current = element }} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="policy-reset-title" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-gray-800">
          <h3 id="policy-reset-title" className="text-lg font-semibold text-gray-900 dark:text-white">改回全公司預設？</h3>
          <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">這個校區的專屬規則會移除，立即改用全公司預設；之後公司預設變更也會自動套用。校區、訂單與人員資料不會刪除。</p>
          <div className="mt-6 flex justify-end gap-3">
            <button type="button" onClick={() => setConfirmReset(false)} disabled={resetMutation.isPending} className="min-h-11 rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 dark:border-gray-600 dark:text-gray-200">取消</button>
            <button type="button" onClick={() => resetMutation.mutate()} disabled={resetMutation.isPending} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{resetMutation.isPending ? '處理中…' : '確認改回預設'}</button>
          </div>
        </div>
      </div>}
    </section>
  )
}
