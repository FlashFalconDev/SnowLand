import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { calculateStaffIncentive, deleteStaffIncentiveDraft, fetchStaffIncentiveOptions, fetchStaffIncentiveRules, fetchStaffIncentiveStatements, updateStaffIncentive } from '../api/operations'
import { useNotification } from '../context'

const inputClass = 'mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white'
const buttonClass = 'min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40'
const statusNames = { draft: '草稿', confirmed: '已確認', paid: '已記錄發放／結清' }
const money = (value: number) => `NT$ ${value.toLocaleString()}`
const currentMonth = () => { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}` }

export default function StaffIncentiveStatementsPanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const rows = useQuery({ queryKey: ['admin', 'staff-incentive-statements'], queryFn: fetchStaffIncentiveStatements })
  const rules = useQuery({ queryKey: ['admin', 'staff-incentive-rules'], queryFn: fetchStaffIncentiveRules })
  const options = useQuery({ queryKey: ['admin', 'staff-incentive-options'], queryFn: fetchStaffIncentiveOptions })
  const [form, setForm] = useState({ campus: '', user: '', month: currentMonth() })
  const [detailId, setDetailId] = useState<number | null>(null)
  const [adjustment, setAdjustment] = useState({ amount: '0', note: '' })
  const [pending, setPending] = useState<'confirm' | 'record-paid' | 'delete' | null>(null)
  const [accepted, setAccepted] = useState(false)
  const [error, setError] = useState('')
  const errorRef = useRef<HTMLParagraphElement>(null)
  const detailRef = useRef<HTMLElement>(null)
  const detail = rows.data?.find(row => row.id === detailId)
  const failed = rows.isError || rules.isError || options.isError
  const loading = rows.isPending || rules.isPending || options.isPending
  const campuses = new Map((options.data?.campuses || []).map(c => [c.id, c.name]))
  for (const row of rows.data || []) if (!campuses.has(row.campus)) campuses.set(row.campus, `${row.campus_name}（歷史資料）`)
  const employees = new Map<number, string>()
  for (const row of [...(rules.data || []), ...(rows.data || [])]) if (row.campus === Number(form.campus)) employees.set(row.user, row.user_name)
  useEffect(() => { setPending(null); setAccepted(false); setAdjustment({ amount: String(detail?.adjustment ?? 0), note: detail?.adjustment_note || '' }) }, [detailId, detail?.adjustment, detail?.adjustment_note])
  useEffect(() => { if (error) errorRef.current?.scrollIntoView({ block: 'center' }) }, [error])
  const run = useMutation({
    mutationFn: async (operation: { action: 'calculate' | 'recalculate' | 'adjust' | 'confirm' | 'record-paid' | 'delete'; id?: number }) => {
      if (operation.action === 'calculate') return calculateStaffIncentive({ user: Number(form.user), campus: Number(form.campus), month: `${form.month}-01` })
      if (!operation.id) throw new Error('請先選擇月結單')
      if (operation.action === 'delete') { await deleteStaffIncentiveDraft(operation.id); return null }
      return updateStaffIncentive(operation.id, operation.action, operation.action === 'adjust'
        ? { amount: Number(adjustment.amount), note: adjustment.note.trim() }
        : ['confirm', 'record-paid'].includes(operation.action) ? { accepted, expected_updated_at: detail?.updated_at } : {})
    },
    onSuccess: async (result, operation) => {
      await qc.invalidateQueries({ queryKey: ['admin', 'staff-incentive-statements'] })
      setError(''); setPending(null); setAccepted(false)
      setDetailId(result?.id ?? null)
      notify.success(operation.action === 'delete' ? '草稿已刪除' : operation.action === 'record-paid' ? '已記錄發放／結清；沒有實際轉帳' : '員工獎金月結已更新')
      if (result) requestAnimationFrame(() => detailRef.current?.scrollIntoView({ block: 'start' }))
    },
    onError: (e: any) => {
      const data = e?.response?.data
      const values = data && typeof data === 'object' ? Object.values(data).flat().filter(v => typeof v === 'string') : []
      const message = data?.msg || values.join('；') || e?.message || '操作失敗，請重試'
      setError(message); notify.error(message)
    },
  })
  const busy = loading || failed || run.isPending
  const action = (name: 'recalculate' | 'adjust' | 'confirm' | 'record-paid' | 'delete') => { if (detail) { setError(''); run.mutate({ action: name, id: detail.id }) } }
  return <section className="mb-5 rounded-xl border border-gray-200 bg-white p-5 text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-white">
    <h2 className="font-semibold">行政員工獎金月結</h2>
    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">整張訂單完成且已付款，按最後一堂課所在月份結算校區營收；已發獎金的訂單退款後，下一期以原比例扣回，漏結的扣回會帶到後續月份。此功能只記帳，不會實際轉帳。</p>
    {failed && <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-300">月結資料載入失敗，暫停操作。<button type="button" className="ml-2 min-h-11 underline" onClick={() => { void rows.refetch(); void rules.refetch(); void options.refetch() }}>重新載入月結資料</button></p>}
    <form className="mt-4" onSubmit={e => { e.preventDefault(); setError(''); run.mutate({ action: 'calculate' }) }}>
      <fieldset disabled={busy} className="grid items-end gap-3 md:grid-cols-4">
        <label className="text-sm">月結校區<select aria-label="月結校區" className={inputClass} required value={form.campus} onChange={e => setForm({ ...form, campus: e.target.value, user: '' })}><option value="">請選校區</option>{[...campuses].map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <label className="text-sm">月結員工<select aria-label="月結員工" className={inputClass} required disabled={!form.campus} value={form.user} onChange={e => setForm({ ...form, user: e.target.value })}><option value="">請選員工</option>{[...employees].map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <label className="text-sm">結算月份<input aria-label="行政獎金結算月份" className={inputClass} required type="month" max={currentMonth()} value={form.month} onChange={e => setForm({ ...form, month: e.target.value })} /></label>
        <button className={buttonClass} disabled={!form.user || !form.campus}>{run.isPending ? '處理中…' : '計算行政獎金'}</button>
      </fieldset>
    </form>
    {!loading && form.campus && !employees.size && <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">請先展開上方「行政員工獎金比例設定」新增這個校區的員工比例。</p>}
    {error && <p ref={errorRef} role="alert" className="mt-3 break-words rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>}
    {loading ? <p role="status" className="mt-4 text-sm">載入月結中…</p> : <div className="mt-4 grid gap-3 lg:grid-cols-2">{rows.data?.map(row => <article key={row.id} className="min-w-0 rounded-lg border border-gray-200 p-3 dark:border-gray-700"><p className="break-words text-sm font-semibold">{row.user_name} · {row.campus_name}</p><p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{row.month.slice(0, 7)} · {statusNames[row.status]}</p><p className="mt-1 font-semibold">{money(row.total_amount)}{row.total_amount < 0 && <span className="ml-2 text-xs font-normal">本期應扣回</span>}</p><button type="button" className="mt-2 min-h-11 text-sm font-semibold text-violet-700 dark:text-violet-300" disabled={run.isPending} aria-label={`查看行政獎金 ${row.user_name} ${row.month.slice(0, 7)}`} onClick={() => { setDetailId(row.id); setError(''); requestAnimationFrame(() => detailRef.current?.scrollIntoView({ block: 'start' })) }}>查看月結明細</button></article>)}</div>}
    {!loading && !failed && !rows.data?.length && <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">尚無行政獎金月結，選擇校區、員工與月份後開始計算。</p>}
    {detail && <section ref={detailRef} className="mt-5 scroll-mt-20 rounded-lg border border-violet-200 p-4 dark:border-violet-800">
      <h3 className="break-words font-semibold">{detail.user_name} · {detail.campus_name} · {detail.month.slice(0, 7)}</h3>
      <p className="mt-1 text-sm">{statusNames[detail.status]} · 本期比例 {detail.percent}%</p>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-gray-500 dark:text-gray-400">完成訂單營收</dt><dd>{money(detail.revenue)}</dd></div><div><dt className="text-gray-500 dark:text-gray-400">本月獎金</dt><dd>{money(detail.earned_amount)}</dd></div><div><dt className="text-gray-500 dark:text-gray-400">已發獎金退款扣回</dt><dd>− {money(detail.refund_deduction)}</dd></div><div><dt className="text-gray-500 dark:text-gray-400">人工調整</dt><dd>{money(detail.adjustment)}</dd></div></dl>
      <p className="mt-3 font-semibold">本期合計 {money(detail.total_amount)}</p>
      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">先按每月營收總額四捨五入，再分攤至訂單明細；退款以原已發獎金為上限。確認後保留快照，新比例不回改舊單。</p>
      <div className="mt-3 grid gap-2 lg:grid-cols-2">{detail.lines.map(line => <article key={line.id} className="min-w-0 rounded-lg bg-gray-50 p-3 text-sm dark:bg-gray-900/50"><p className="font-medium">{line.line_type === 'refund' ? '退款扣回' : '完成訂單獎金'}</p><p className="break-all text-gray-500 dark:text-gray-400">{line.order_number}</p><p className="text-gray-500 dark:text-gray-400">{line.event_date}</p><p className="mt-1">計算基礎 {money(line.base_amount)} × {line.percent}%</p><p className="mt-1 font-semibold">{money(line.amount)}</p></article>)}</div>
      {detail.adjustment_note && <p className="mt-3 break-words text-sm">調整原因：{detail.adjustment_note}</p>}
      {detail.confirmed_at && <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">確認時間：{new Date(detail.confirmed_at).toLocaleString()}</p>}
      {detail.paid_at && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">記錄發放／結清時間：{new Date(detail.paid_at).toLocaleString()}（非銀行轉帳紀錄）</p>}
      {detail.status === 'draft' && <form className="mt-4 grid items-end gap-3 md:grid-cols-3" onSubmit={e => { e.preventDefault(); action('adjust') }}><label className="text-sm">本月人工調整（覆蓋前值）<input aria-label="行政獎金人工調整金額" className={inputClass} required type="number" step="1" min="-2147483648" max="2147483647" value={adjustment.amount} disabled={busy} onChange={e => setAdjustment({ ...adjustment, amount: e.target.value })} /></label><label className="text-sm">調整原因<input aria-label="行政獎金人工調整原因" className={inputClass} required maxLength={300} value={adjustment.note} disabled={busy} onChange={e => setAdjustment({ ...adjustment, note: e.target.value })} /></label><button className={buttonClass} disabled={busy || !adjustment.note.trim()}>儲存行政獎金調整</button></form>}
      <div className="mt-4 flex flex-wrap gap-3">{detail.status === 'draft' && <><button type="button" disabled={busy} className="min-h-11 text-sm font-semibold text-violet-700 dark:text-violet-300" onClick={() => action('recalculate')}>重算行政獎金</button><button type="button" disabled={busy} className={buttonClass} onClick={() => { setPending('confirm'); setAccepted(false) }}>確認這張行政獎金</button><button type="button" disabled={busy} className="min-h-11 text-sm text-red-600 dark:text-red-300" onClick={() => { setPending('delete'); setAccepted(false) }}>刪除行政獎金草稿</button></>}{detail.status === 'confirmed' && <button type="button" disabled={busy} className={buttonClass} onClick={() => { setPending('record-paid'); setAccepted(false) }}>{detail.total_amount < 0 ? '記錄行政獎金已結清' : '記錄行政獎金已發放'}</button>}</div>
      {pending && <div className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100"><p>{pending === 'delete' ? '刪除這張草稿及明細？不會改動原訂單。' : pending === 'confirm' ? '確認後不能修改或重新計算，請先核對金額與扣回明細。' : '僅記錄已在系統外完成的發放／結清，不會實際轉帳。'}</p>{pending !== 'delete' && <label className="mt-2 flex min-h-11 items-center gap-2"><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} />{pending === 'confirm' ? '我已核對這張行政獎金明細' : '我確認已在系統外完成發放或結清'}</label>}<div className="mt-2 flex flex-wrap gap-3"><button type="button" className={buttonClass} disabled={busy || (pending !== 'delete' && !accepted)} onClick={() => action(pending)}>確定{pending === 'delete' ? '刪除草稿' : pending === 'confirm' ? '確認行政獎金' : '記錄發放／結清'}</button><button type="button" className="min-h-11" disabled={busy} onClick={() => { setPending(null); setAccepted(false) }}>取消本次月結操作</button></div></div>}
    </section>}
  </section>
}
