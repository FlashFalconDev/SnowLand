import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchStaffIncentiveOptions, fetchStaffIncentiveRules, saveStaffIncentiveRule, type StaffIncentiveRule } from '../api/operations'
import { useNotification } from '../context'

const inputClass = 'mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white'
const blank = () => ({ user: '', campus: '', completed_order_percent: '', is_active: true })

export default function StaffIncentiveRulesPanel() {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(blank)
  const [editing, setEditing] = useState<number | null>(null)
  const [error, setError] = useState('')
  const notify = useNotification(); const qc = useQueryClient()
  const rules = useQuery({ queryKey: ['admin', 'staff-incentive-rules'], queryFn: fetchStaffIncentiveRules, enabled: open })
  const options = useQuery({ queryKey: ['admin', 'staff-incentive-options'], queryFn: fetchStaffIncentiveOptions, enabled: open })
  const reset = () => { setForm(blank()); setEditing(null); setError('') }
  const save = useMutation({
    mutationFn: () => saveStaffIncentiveRule({ id: editing ?? undefined, user: Number(form.user), campus: Number(form.campus), completed_order_percent: form.completed_order_percent, is_active: form.is_active }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ['admin', 'staff-incentive-rules'] }); reset(); notify.success('員工獎金比例已儲存') },
    onError: (e: any) => {
      const data = e?.response?.data
      const values = data && typeof data === 'object' ? Object.values(data).flat().filter(v => typeof v === 'string') : []
      const message = data?.msg || values.join('；') || '儲存失敗，請稍後重試'
      setError(message); notify.error(message)
    },
  })
  const edit = (row: StaffIncentiveRule) => {
    setEditing(row.id); setError('')
    setForm({ user: String(row.user), campus: String(row.campus), completed_order_percent: row.completed_order_percent, is_active: row.is_active })
  }
  const loading = rules.isPending || options.isPending
  const failed = rules.isError || options.isError
  const employees = options.data?.employees.filter(employee => employee.campus_ids.includes(Number(form.campus))) || []
  const eligible = employees.some(employee => employee.id === Number(form.user))
  const currentRule = rules.data?.find(row => row.id === editing)
  const canSave = !!form.campus && (eligible || (editing !== null && !form.is_active))
  return <details className="mb-5 rounded-xl border border-gray-200 bg-white p-5 text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-white" open={open} onToggle={e => setOpen(e.currentTarget.open)}>
    <summary className="min-h-11 cursor-pointer font-semibold">行政員工獎金比例設定</summary>
    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">先選校區，再選員工及比例。同一員工可在不同校區分別設定；不會修改教練時薪。</p>
    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">儲存後，請在下方「行政員工獎金月結」計算或重算草稿；已確認、已記錄發放的舊單不會自動改動。</p>
    {loading && <p role="status" className="mt-4 text-sm">載入員工與設定中…</p>}
    {failed && <div role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">設定載入失敗，暫停儲存。<button type="button" className="ml-2 min-h-11 underline" onClick={() => { void rules.refetch(); void options.refetch() }}>重新載入設定</button></div>}
    <form className="mt-4" onSubmit={e => { e.preventDefault(); setError(''); save.mutate() }}>
      <fieldset disabled={loading || failed || save.isPending} className="grid gap-3 md:grid-cols-3">
        <label className="text-sm">獎金適用校區<select aria-label="獎金適用校區" className={inputClass} required disabled={editing !== null} value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value, user: '' })}><option value="">請選校區</option>{currentRule && !options.data?.campuses.some(c => c.id === currentRule.campus) && <option value={currentRule.campus}>{currentRule.campus_name}（目前停用）</option>}{options.data?.campuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label className="text-sm">獎金員工<select aria-label="獎金員工" className={inputClass} required disabled={!form.campus || editing !== null} value={form.user} onChange={e => setForm({ ...form, user: e.target.value })}><option value="">請選員工</option>{currentRule && !eligible && <option value={currentRule.user}>{currentRule.user_name}（目前不符合任職條件）</option>}{employees.map(employee => <option key={employee.id} value={employee.id}>{employee.name}</option>)}</select></label>
        <label className="text-sm">已完成訂單營收獎金（%）<input aria-label="員工獎金百分比" className={inputClass} required type="number" min="0" max="100" step="0.01" value={form.completed_order_percent} onChange={e => setForm({ ...form, completed_order_percent: e.target.value })} /></label>
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} />啟用此員工獎金比例</label>
        <button disabled={!canSave} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{save.isPending ? '儲存中…' : editing === null ? '新增員工獎金比例' : '儲存員工獎金比例'}</button>
        {editing !== null && <button type="button" className="min-h-11 text-sm text-gray-600 dark:text-gray-300" onClick={reset}>取消獎金比例編輯</button>}
      </fieldset>
      {!!form.campus && !loading && !failed && !employees.length && <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">此校區尚無可選員工，請先在「員工權限」設定公司及校區。</p>}
      {editing !== null && !eligible && !loading && !failed && <p role="alert" className="mt-2 text-sm text-amber-700 dark:text-amber-300">這位員工目前已停用或不屬於此校區；可以取消啟用並儲存停用，但不能重新啟用。</p>}
      {error && <p role="alert" className="mt-3 break-words rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>}
    </form>
    <div className="mt-4 grid gap-3 lg:grid-cols-2">{rules.data?.map(row => <article key={row.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700"><p className="text-sm font-semibold">{row.user_name} · {row.campus_name}</p><p className="mt-1 text-sm text-gray-500 dark:text-gray-400">營收 × {row.completed_order_percent}% · {row.is_active ? '啟用中' : '已停用'}</p><button type="button" aria-label={`編輯獎金比例 ${row.user_name} ${row.campus_name}`} disabled={save.isPending || loading || failed} onClick={() => edit(row)} className="mt-2 min-h-11 text-sm font-semibold text-violet-700 disabled:opacity-40 dark:text-violet-300">編輯獎金比例</button></article>)}</div>
    {!loading && !failed && !rules.data?.length && <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">尚無員工獎金比例。</p>}
  </details>
}
