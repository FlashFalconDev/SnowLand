import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { payrollReviewAction, type PayrollStatement } from '../api/operations'
import { useNotification } from '../context'

export default function PayrollReviewActions({ statement, coachView = false }: { statement: PayrollStatement; coachView?: boolean }) {
  const qc = useQueryClient(); const notify = useNotification()
  const end = new Date(`${statement.period_end}T12:00:00`)
  const deadline = new Date(end.getFullYear(), end.getMonth()+1, 5)
  const [date, setDate] = useState(`${deadline.getFullYear()}-${String(deadline.getMonth()+1).padStart(2,'0')}-05`)
  const [accepted, setAccepted] = useState(false)
  const [withdraw, setWithdraw] = useState(false)
  const [error, setError] = useState('')
  const settlementReady=!!statement.settlement_snapshot?.version&&statement.settlement_snapshot.base_amount===statement.total_amount
  const mutation = useMutation({
    mutationFn: (action: 'publish' | 'withdraw' | 'confirm') => payrollReviewAction(statement.id, action,
      action === 'publish' ? { confirmation_deadline: date, settlement_reviewed_at:statement.settlement_snapshot?.reviewed_at } : action === 'confirm' ? { review_token: statement.review_token } : {}),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'payroll'] })
      await qc.invalidateQueries({ queryKey: ['coach', 'payroll'] })
      setAccepted(false); setWithdraw(false); setError(''); notify.success('薪資單狀態已更新；未進行發款')
    },
    onError: async (e: any) => { setError(e?.response?.data?.msg || '操作失敗，請重新載入確認狀態'); if (e?.response?.status === 409) { await qc.invalidateQueries({ queryKey: ['admin', 'payroll'] }); await qc.invalidateQueries({ queryKey: ['coach', 'payroll'] }) } },
  })
  return <div className="my-4 space-y-3 rounded-lg border border-gray-200 p-4 text-sm text-gray-900 dark:border-gray-700 dark:text-gray-100">
    {statement.confirmation_deadline && <p>確認截止：{statement.confirmation_deadline}（{statement.confirmation_timezone === 'Asia/Taipei' ? '台北時間' : statement.confirmation_timezone}當日結束）。截止日後由排程自動確認，不會自動發款或代簽文件。</p>}
    {statement.confirmed_at && <p>{statement.confirmation_method === 'automatic' ? '逾期自動確認' : '教練已確認'} · {new Date(statement.confirmed_at).toLocaleString('zh-TW')}</p>}
    {!coachView && statement.status === 'draft' && <>
      <p className="font-semibold">送交教練核對</p><p className="text-xs text-gray-500 dark:text-gray-400">預設次月5日，可調整截止日。先核對時數、金額與應扣款；送出後明細鎖定。期限前可撤回草稿修正，教練確認後不能撤回。</p>
      <label className="block">確認截止日<input aria-label="薪資確認截止日" type="date" required value={date} onChange={e=>setDate(e.target.value)} disabled={mutation.isPending} className="mt-1 block rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white" /></label>
      <label className="flex items-start gap-2"><input type="checkbox" checked={accepted} disabled={mutation.isPending} onChange={e=>setAccepted(e.target.checked)} className="mt-1" />我已核對明細及應扣款，送交教練確認</label>
      {!settlementReady&&<p role="status" className="text-amber-700 dark:text-amber-300">請先於「稅金與發放幣別」保存最新核對結果，再送交教練。</p>}
      <button disabled={!accepted || !date || mutation.isPending || !settlementReady} onClick={()=>mutation.mutate('publish')} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 font-semibold text-white disabled:opacity-40">{mutation.isPending ? '送出中…' : '送交教練確認'}</button>
    </>}
    {!coachView && statement.status === 'review' && <>{!withdraw ? <button disabled={mutation.isPending} onClick={()=>setWithdraw(true)} className="min-h-11 rounded-lg border border-gray-300 px-3 py-2 dark:border-gray-600">撤回草稿</button> : <div><p>撤回後教練將暫時看不到此單，重新送出後須核對新版本。</p><div className="mt-2 flex flex-wrap gap-3"><button disabled={mutation.isPending} onClick={()=>setWithdraw(false)} className="min-h-11 px-3">保留待確認</button><button disabled={mutation.isPending} onClick={()=>mutation.mutate('withdraw')} className="min-h-11 rounded-lg bg-violet-600 px-3 text-white">確認撤回</button></div></div>}</>}
    {coachView && statement.status === 'review' && <><p>請核對下方時數及金額。有疑問請先聯絡管理員，勿勾選確認。</p><label className="flex items-start gap-2"><input type="checkbox" className="mt-1" checked={accepted} disabled={mutation.isPending} onChange={e=>setAccepted(e.target.checked)} />我已核對這張薪資單，內容正確</label><button disabled={!accepted || mutation.isPending} onClick={()=>mutation.mutate('confirm')} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 font-semibold text-white disabled:opacity-40">{mutation.isPending ? '確認中…' : '確認薪資內容'}</button></>}
    {error && <p role="alert" className="break-words rounded-lg bg-red-50 p-3 text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>}
  </div>
}
