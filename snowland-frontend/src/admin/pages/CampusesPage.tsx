import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Check, ChevronRight, Edit3, Loader2, MapPin, Plus, ShieldCheck, Trash2, X } from 'lucide-react'
import { useNotification } from '../context'
import { fetchResorts } from '../api/resorts'
import {
  createCampus, deleteCampus, fetchCampuses, fetchOperatingPolicies, updateCampus, updateOperatingPolicy,
  type Campus, type CampusWriteData, type OperatingPolicy,
} from '../api/campuses'

const EMPTY_FORM: CampusWriteData = {
  name: '', code: '', description: '', is_active: true, display_order: 0, resort_ids: [],
}

function errorMessage(error: unknown, fallback: string) {
  const data = (error as { response?: { data?: { msg?: string; detail?: string } } })?.response?.data
  return data?.msg || data?.detail || fallback
}

export default function CampusesPage() {
  const queryClient = useQueryClient()
  const notification = useNotification()
  const [editing, setEditing] = useState<Campus | null>(null)
  const [form, setForm] = useState<CampusWriteData>(EMPTY_FORM)
  const [showForm, setShowForm] = useState(false)
  const [deleting, setDeleting] = useState<Campus | null>(null)
  const [policyId, setPolicyId] = useState<number | null>(null)

  const campusesQuery = useQuery({ queryKey: ['admin', 'campuses'], queryFn: fetchCampuses })
  const resortsQuery = useQuery({ queryKey: ['admin', 'resorts'], queryFn: fetchResorts })
  const policiesQuery = useQuery({ queryKey: ['admin', 'operating-policies'], queryFn: fetchOperatingPolicies })

  const saveCampus = useMutation({
    mutationFn: (data: CampusWriteData) => editing ? updateCampus(editing.id, data) : createCampus(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'campuses'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'operating-policies'] })
      notification.success(editing ? '校區已更新' : '校區已建立')
      setShowForm(false)
    },
    onError: (error) => notification.error(errorMessage(error, '儲存校區失敗')),
  })

  const removeCampus = useMutation({
    mutationFn: deleteCampus,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'campuses'] })
      notification.success('校區已刪除')
      setDeleting(null)
    },
    onError: (error) => notification.error(errorMessage(error, '無法刪除，建議改為停用')),
  })

  const campuses = campusesQuery.data || []
  const resorts = resortsQuery.data || []
  const policies = policiesQuery.data || []
  const activePolicy = useMemo(() => policies.find((item) => item.id === policyId) || policies[0], [policies, policyId])

  const openNew = () => {
    setEditing(null)
    setForm({ ...EMPTY_FORM, display_order: campuses.length })
    setShowForm(true)
  }

  const openEdit = (campus: Campus) => {
    setEditing(campus)
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

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">校區與雪場</h1>
          <p className="mt-1 text-gray-500 dark:text-gray-400">先建立校區，再勾選可使用的雪場；同一雪場可由多個校區使用。</p>
        </div>
        <button onClick={openNew} className="inline-flex items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:opacity-90">
          <Plus size={16} />新增校區
        </button>
      </div>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-900 dark:text-white">目前校區（{campuses.length}）</h2>
          <span className="text-sm text-gray-500 dark:text-gray-400">雪場可重複勾選</span>
        </div>
        {campuses.length === 0 ? (
          <button onClick={openNew} className="w-full rounded-xl border border-dashed border-violet-300 p-10 text-violet-600 hover:bg-violet-50 dark:border-violet-700 dark:hover:bg-violet-900/20">尚未建立校區，點這裡開始</button>
        ) : (
          <div className="grid lg:grid-cols-2 gap-4">
            {campuses.map((campus) => (
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
                  <div className="flex gap-1">
                    <button onClick={() => openEdit(campus)} aria-label={`編輯 ${campus.name}`} className="p-2 rounded-lg hover:bg-violet-50 text-violet-600"><Edit3 size={18} /></button>
                    <button onClick={() => setDeleting(campus)} aria-label={`刪除 ${campus.name}`} className="rounded-lg p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"><Trash2 size={18} /></button>
                  </div>
                </div>
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
      </section>

      {activePolicy && <PolicyCard policies={policies} policy={activePolicy} onSelect={setPolicyId} onSaved={() => queryClient.invalidateQueries({ queryKey: ['admin', 'operating-policies'] })} />}

      {showForm && (
        <div className="fixed inset-0 z-[70] flex items-end justify-center bg-black/50 p-0 animate-fadeIn md:items-center md:p-4" onMouseDown={(event) => event.target === event.currentTarget && setShowForm(false)}>
          <form onSubmit={(event) => { event.preventDefault(); saveCampus.mutate(form) }} className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl bg-white shadow-xl dark:bg-gray-800 md:max-w-xl md:rounded-2xl">
            <div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)' }}><div><h2 className="text-lg font-semibold">{editing ? '編輯校區' : '新增校區'}</h2><p className="mt-0.5 text-xs text-white/80">設定校區資料與可使用的雪場</p></div><button type="button" onClick={() => setShowForm(false)} aria-label="關閉" className="rounded-lg p-1 text-white/80 hover:bg-white/10 hover:text-white"><X size={20} /></button></div>
            <div className="space-y-5 overflow-y-auto p-6">
              <label className="block"><span className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">校區名稱 <span className="text-red-500">*</span></span><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例如：北海道校區" className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" /></label>
              <label className="block"><span className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">內部代碼 <span className="text-red-500">*</span></span><input required pattern="[a-z0-9-]+" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })} placeholder="例如：hokkaido" className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" /><span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">只能使用英文小寫、數字與橫線</span></label>
              <label className="block"><span className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">備註</span><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} className="w-full resize-none rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" /></label>
              <fieldset><legend className="font-medium">這個校區可使用哪些雪場？</legend><p className="mb-2 mt-1 text-xs text-gray-500 dark:text-gray-400">可複選；同一雪場也可在其他校區使用。</p><div className="space-y-2">{resorts.map((resort) => { const checked = form.resort_ids.includes(resort.id); return <label key={resort.id} className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 dark:border-gray-600 ${checked ? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20' : ''}`}><input type="checkbox" checked={checked} onChange={() => setForm({ ...form, resort_ids: checked ? form.resort_ids.filter((id) => id !== resort.id) : [...form.resort_ids, resort.id] })} /><span className="flex-1">{resort.display_name}</span>{checked && <Check className="text-violet-600" size={18} />}</label> })}</div></fieldset>
              <label className="flex items-center justify-between rounded-lg border p-3 dark:border-gray-600"><span><b>啟用校區</b><small className="block text-gray-500 dark:text-gray-400">停用後仍保留舊訂單</small></span><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} className="w-5 h-5" /></label>
            </div>
            <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700"><button type="button" onClick={() => setShowForm(false)} className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">取消</button><button disabled={saveCampus.isPending} className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">{saveCampus.isPending && <Loader2 size={14} className="animate-spin" />}{saveCampus.isPending ? '儲存中…' : '儲存校區'}</button></div>
          </form>
        </div>
      )}

      {deleting && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 p-4 animate-fadeIn">
          <div className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-xl dark:bg-gray-800">
            <div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)' }}><h3 className="text-lg font-semibold">刪除校區</h3><button onClick={() => setDeleting(null)} aria-label="關閉" className="rounded-lg p-1 text-white/80 hover:bg-white/10 hover:text-white"><X size={18} /></button></div>
            <div className="p-6"><p className="text-sm text-gray-700 dark:text-gray-300">確定刪除「<b className="text-gray-900 dark:text-white">{deleting.name}</b>」？</p><p className="mt-2 text-xs text-gray-500 dark:text-gray-400">已有訂單或人員使用時，系統會阻止刪除；可改用停用保留舊資料。</p></div>
            <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700"><button onClick={() => setDeleting(null)} className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">取消</button><button onClick={() => removeCampus.mutate(deleting.id)} disabled={removeCampus.isPending} className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">{removeCampus.isPending && <Loader2 size={14} className="animate-spin" />}確認刪除</button></div>
          </div>
        </div>
      )}
    </div>
  )
}

function PolicyCard({ policies, policy, onSelect, onSaved }: { policies: OperatingPolicy[]; policy: OperatingPolicy; onSelect: (id: number) => void; onSaved: () => void }) {
  const notification = useNotification()
  const [draft, setDraft] = useState(policy)
  const mutation = useMutation({ mutationFn: () => updateOperatingPolicy(policy.id, draft), onSuccess: () => { notification.success('營運規則已儲存'); onSaved() }, onError: (error) => notification.error(errorMessage(error, '儲存失敗')) })
  useEffect(() => setDraft(policy), [policy])
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
        <select value={policy.id} onChange={(e) => onSelect(Number(e.target.value))} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white">{policies.map((item) => <option key={item.id} value={item.id}>{item.campus_name || '全公司預設'}</option>)}</select>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{numberField('unpaid_hold_days', '未付款保留', '天')}{numberField('provisional_extra_groups', '未付款可加排', '組')}{numberField('leave_advance_days', '請假需提前', '天')}{numberField('leave_daily_coach_limit', '每日請假上限', '人')}</div>
      <div className="mt-5 border-t border-gray-200 pt-4 dark:border-gray-700"><button onClick={() => mutation.mutate()} disabled={mutation.isPending} className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">儲存營運規則<ChevronRight size={16} /></button></div>
    </section>
  )
}
