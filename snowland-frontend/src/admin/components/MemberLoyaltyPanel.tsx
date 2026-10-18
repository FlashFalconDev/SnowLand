import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchCustomerLoyalty, saveCustomerLoyalty, type LoyaltyReview } from '../api/customers'
import { useNotification } from '../context'

const fieldClass = 'mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white p-3 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white'

export default function MemberLoyaltyPanel({ userId }: { userId: number }) {
  const query = useQuery({ queryKey: ['admin', 'customer-loyalty', userId], queryFn: () => fetchCustomerLoyalty(userId) })
  if (query.isPending) return <p role="status" className="text-sm text-gray-500 dark:text-gray-400">載入舊生審核資料…</p>
  if (query.isError || !query.data) return <div role="alert" className="text-sm text-red-600 dark:text-red-300">舊生審核資料載入失敗。<button type="button" className="min-h-11 underline" onClick={() => query.refetch()}>重新載入審核資料</button></div>
  return <LoyaltyForm key={query.data.updated_at} userId={userId} data={query.data} onReload={() => query.refetch()} />
}

function LoyaltyForm({ userId, data, onReload }: { userId: number; data: LoyaltyReview; onReload: () => unknown }) {
  const [verified, setVerified] = useState(data.alumni_verified)
  const [points, setPoints] = useState(String(data.previous_points))
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [stale, setStale] = useState(false)
  const notify = useNotification(); const qc = useQueryClient()
  const validPoints = /^\d+$/.test(points) && Number(points) <= 2147483647
  const nextTotal = data.points - data.previous_points + Number(points)
  const valid = validPoints && nextTotal >= 0 && nextTotal <= 2147483647 && (verified || Number(points) === 0)
  const changed = verified !== data.alumni_verified || Number(points) !== data.previous_points
  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    if (busy || !valid || !changed || !reason.trim() || stale) return
    setBusy(true); setError('')
    try {
      const result = await saveCustomerLoyalty(userId, { alumni_verified: verified, previous_points: Number(points), reason: reason.trim(), expected_updated_at: data.updated_at })
      qc.setQueryData(['admin', 'customer-loyalty', userId], result)
      await qc.invalidateQueries({ queryKey: ['admin', 'customers'] })
      notify.success('舊生資格與歷史點數已儲存，會員重新載入即可查看')
    } catch (e: any) {
      const body = e?.response?.data
      setError(body?.msg || Object.values(body || {}).flat().filter(value => typeof value === 'string').join('；') || '儲存失敗，請重試')
      if (e?.response?.status === 409) setStale(true)
    } finally { setBusy(false) }
  }
  return <section className="rounded-xl border border-gray-200 p-4 text-gray-900 dark:border-gray-600 dark:text-white">
    <h3 className="font-semibold">舊生審核與補登點數</h3>
    <p className="mt-2 text-sm leading-6 text-gray-500 dark:text-gray-400">先核對舊季上課紀錄，再確認舊生身分。歷史點數填「累計總額」，不是本次加多少；重複儲存不會重加。此處不設定自動推薦回饋。</p>
    <p className="mt-3 text-sm">目前：{data.alumni_verified ? '舊生已確認' : '舊生尚未確認'} · 總點數 {data.points.toLocaleString()}（含歷史 {data.previous_points.toLocaleString()}）</p>
    <form onSubmit={save} className="mt-3 space-y-3">
      <fieldset disabled={busy} className="space-y-3 disabled:opacity-60">
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={verified} onChange={e => setVerified(e.target.checked)} />已核對並確認為舊生</label>
        <label className="block text-sm">歷史點數累計總額<input aria-label="歷史點數累計總額" inputMode="numeric" value={points} onChange={e => setPoints(e.target.value)} maxLength={10} className={fieldClass} /></label>
        {!verified && Number(points) > 0 && <p role="alert" className="text-sm text-amber-700 dark:text-amber-300">請先確認舊生身分；若要撤銷舊生資格，請將歷史點數改為 0。</p>}
        {valid && <p className="text-sm text-violet-700 dark:text-violet-300">儲存後總點數：{nextTotal.toLocaleString()}；其他點數維持 {data.points - data.previous_points}。</p>}
        {!validPoints && <p role="alert" className="text-sm text-red-600 dark:text-red-300">請輸入 0 至 2,147,483,647 的整數。</p>}
        {validPoints && (nextTotal < 0 || nextTotal > 2147483647) && <p role="alert" className="text-sm text-red-600 dark:text-red-300">點數總額超出可儲存範圍，請先核對目前點數。</p>}
        <label className="block text-sm">核對依據／修改原因<textarea aria-label="舊生核對依據" value={reason} onChange={e => setReason(e.target.value)} maxLength={1000} required rows={2} className={fieldClass} placeholder="例如：已核對上季訂單，補登原有點數" /></label>
        <button disabled={!valid || !changed || !reason.trim() || stale} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{busy ? '儲存中…' : '儲存舊生審核'}</button>
      </fieldset>
    </form>
    {error && <p role="alert" className="mt-3 break-words rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>}
    {stale && <button type="button" onClick={onReload} className="mt-2 min-h-11 text-sm text-violet-700 underline dark:text-violet-300">重新載入最新審核資料</button>}
    {!!data.history.length && <details className="mt-4"><summary className="min-h-11 cursor-pointer text-sm font-semibold">最近審核紀錄（{data.history.length} 筆）</summary><div className="space-y-3">{data.history.map(item => <article key={item.id} className="rounded-lg bg-gray-50 p-3 text-sm dark:bg-gray-700"><p>{new Date(item.created_at).toLocaleString('zh-TW')} · {item.reviewed_by}</p><p className="mt-1">總點數 {item.before.points} → {item.after.points}</p><p className="mt-1 break-words text-gray-500 dark:text-gray-300">{item.reason}</p></article>)}</div></details>}
  </section>
}
