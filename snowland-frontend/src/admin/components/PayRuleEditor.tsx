import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { savePayRule, type PayRule, type PayrollCoach } from '../api/operations'
import { useNotification } from '../context'

const fields = [
  ['hourly_rate', '每小時薪資', '1'], ['specified_fee', '每組指定教練費', '1'],
  ['referral_percent', '介紹費百分比', '0.01'], ['assistance_hour_factor', '每組裝備協助時數', '0.01'],
  ['supervisor_allowance', '每期主管加給', '1'],
] as const
const names: Record<string, string> = { snowboard: '單板', ski: '雙板', photo: '攝影' }
const blank = () => ({ coach: '', discipline: 'snowboard', certification_level: '', hourly_rate: '', specified_fee: '0', referral_percent: '10', assistance_hour_factor: '0.5', supervisor_allowance: '0', is_active: true })
const inputClass = 'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white'

export default function PayRuleEditor({ rules, coaches, loading, failed }: { rules: PayRule[]; coaches: PayrollCoach[]; loading: boolean; failed: boolean }) {
  const qc = useQueryClient(); const notify = useNotification()
  const [form, setForm] = useState(blank)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const editor = useRef<HTMLFormElement>(null)
  const canManage = coaches.some(c => c.id === Number(form.coach) && c.can_manage)
  const editableCoaches = coaches.filter(c => c.can_manage)
  const reset = () => { setForm(blank()); setEditingId(null); setError('') }
  // A scope change must not leave another campus' stale draft ready to save.
  useEffect(() => { if (form.coach && !coaches.some(c => c.id === Number(form.coach))) reset() }, [coaches, form.coach])
  const save = useMutation({
    mutationFn: async () => {
      if (!canManage || loading || failed) throw new Error('請先確認教練與薪資規則已載入')
      return savePayRule({ id: editingId ?? undefined, coach: Number(form.coach), course_type: editingId === null ? null : rules.find(r => r.id === editingId)?.course_type,
        discipline: form.discipline, certification_level: form.certification_level.trim(), hourly_rate: form.hourly_rate,
        specified_fee: Number(form.specified_fee), referral_percent: form.referral_percent,
        assistance_hour_factor: form.assistance_hour_factor, supervisor_allowance: Number(form.supervisor_allowance), is_active: form.is_active })
    },
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ['admin', 'pay-rules'] }); notify.success('薪資規則已儲存；既有薪資單不會自動改動'); reset() },
    onError: (e: any) => {
      const data = e?.response?.data
      const values = data && typeof data === 'object' ? Object.values(data).flat().filter(v => typeof v === 'string') : []
      const message = data?.msg || values.join('；') || e?.message || '規則儲存失敗'
      setError(message); notify.error(message)
    },
  })
  const edit = (rule: PayRule) => {
    setEditingId(rule.id); setError('')
    setForm({ coach: String(rule.coach), discipline: rule.discipline, certification_level: rule.certification_level,
      hourly_rate: String(rule.hourly_rate), specified_fee: String(rule.specified_fee), referral_percent: String(rule.referral_percent),
      assistance_hour_factor: String(rule.assistance_hour_factor), supervisor_allowance: String(rule.supervisor_allowance), is_active: rule.is_active })
    editor.current?.scrollIntoView({ block: 'start' })
  }
  return <section className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
    <h2 className="font-semibold text-gray-900 dark:text-white">教練薪資規則</h2>
    <p className="mb-4 mt-1 text-xs text-gray-500 dark:text-gray-400">修改請先點下方「編輯規則」，會帶入已儲存的設定。儲存後，草稿薪資單須重新計算才會套用；已確認或發放的薪資單不變。</p>
    {failed && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-300">薪資規則載入失敗，請重新整理；暫停儲存避免覆蓋資料。</p>}
    <form ref={editor} className="scroll-mt-20" onSubmit={e => { e.preventDefault(); setError(''); save.mutate() }}>
      <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">{editingId === null ? '新增規則' : `編輯規則 #${editingId}`}</h3>
      <fieldset disabled={save.isPending || loading || failed} className="grid items-end gap-3 md:grid-cols-4">
        <label className="text-sm">教練<select aria-label="薪資規則教練" className={inputClass} required disabled={editingId !== null} value={form.coach} onChange={e => setForm({ ...blank(), coach: e.target.value })}><option value="">請選教練</option>{editableCoaches.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label className="text-sm">工作類型<select className={inputClass} disabled={editingId !== null} value={form.discipline} onChange={e => setForm({ ...form, discipline: e.target.value })}>{Object.entries(names).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
        <label className="text-sm">證照級別（可留空）<input className={inputClass} maxLength={30} disabled={editingId !== null} value={form.certification_level} onChange={e => setForm({ ...form, certification_level: e.target.value })} /></label>
        {fields.map(([key, label, step]) => <label key={key} className="text-sm">{label}<input aria-label={label} className={inputClass} required type="number" min="0" max={key === 'referral_percent' ? 100 : undefined} step={step} value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} /></label>)}
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} />啟用此規則</label>
        <button disabled={!canManage} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{save.isPending ? '儲存中…' : editingId === null ? '新增規則' : '儲存修改'}</button>
        {editingId !== null && <button type="button" className="min-h-11 text-sm text-gray-600 dark:text-gray-300" onClick={reset}>取消編輯</button>}
      </fieldset>
      {editingId !== null && <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">教練、工作類型、證照與適用課程保留原值。如需另一組設定，請取消編輯後新增。</p>}
      {error && <p role="alert" className="mt-3 break-words rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>}
    </form>
    <div className="mt-5 grid gap-3 lg:grid-cols-2">{rules.map(r => <article key={r.id} className="rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-700">
      <p className="font-semibold text-gray-900 dark:text-white">{r.coach_name} · {names[r.discipline] || r.discipline} · {r.certification_level || '未指定證照'} · {r.is_active ? '啟用中' : '已停用'}</p>
      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{r.course_type === null ? '所有同類型課程' : `指定課程：${r.course_type_name || r.course_type}`} · NT$ {Number(r.hourly_rate).toLocaleString()}／時</p>
      <button type="button" aria-label={`編輯規則 ${r.coach_name} ${names[r.discipline] || r.discipline} ${r.certification_level || '未指定證照'}`} disabled={!coaches.some(c => c.id === r.coach && c.can_manage) || save.isPending || loading || failed} onClick={() => edit(r)} className="mt-2 min-h-11 text-sm font-semibold text-violet-700 disabled:opacity-40 dark:text-violet-300">編輯規則</button>
      {!coaches.some(c => c.id === r.coach && c.can_manage) && <p className="text-xs text-gray-500 dark:text-gray-400">共用教練請由總部設定。</p>}
    </article>)}</div>
    {!loading && !failed && !rules.length && <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">尚無薪資規則，請先新增。</p>}
  </section>
}
