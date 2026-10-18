import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { processOrderCancellation, type Order } from '../api/orders'
import { useNotification } from '../context'

type Decision = 'approved' | 'rejected' | 'refunded'
const names: Record<string, string> = { requested: '待審核', approved: '已核准，待完成退款', rejected: '已駁回', refunded: '已記錄退款完成' }
const decisions = { approved: '核准取消', rejected: '駁回申請', refunded: '記錄退款完成' }

export default function CancellationStatusPanel({ cancellation, readOnly }: { cancellation: NonNullable<Order['cancellation']>; readOnly: boolean }) {
  const qc = useQueryClient(); const notify = useNotification()
  const [decision, setDecision] = useState<Decision | null>(null)
  const [acknowledged, setAcknowledged] = useState(false)
  const [error, setError] = useState('')
  const [received,setReceived]=useState(''),[refund,setRefund]=useState(''),[reviewNote,setReviewNote]=useState('')
  const needsReview=!!cancellation.requires_cash_review&&cancellation.actual_received_amount==null
  const reviewValid=received!==''&&refund!==''&&/^\d+$/.test(received)&&/^\d+$/.test(refund)&&Number(received)<=2147483647&&Number(refund)<=Number(received)&&!!reviewNote.trim()&&acknowledged
  useEffect(() => { setDecision(null); setAcknowledged(false); setError('') }, [cancellation.id, cancellation.status])
  const process = useMutation({
    mutationFn: (next: Decision) => processOrderCancellation(cancellation.id, next, next==='approved'&&needsReview?{actual_received_amount:Number(received),refund_amount:Number(refund),cash_review_note:reviewNote.trim(),confirmed_received:acknowledged}:undefined),
    onSuccess: async (_, next) => {
      setDecision(null); setAcknowledged(false); setError('')
      await qc.invalidateQueries({ queryKey: ['admin', 'orders'] })
      await qc.invalidateQueries({ queryKey: ['admin', 'cancellations'] })
      notify.success(next === 'refunded' ? '已記錄退款完成；系統沒有實際轉帳' : next === 'approved' ? '取消已核准，請另行完成實際退款' : '取消申請已駁回')
    },
    onError: (e: any) => {
      const data = e?.response?.data
      const message = data?.msg || data?.detail || Object.values(data||{}).flat().filter(value=>typeof value==='string').join('；') || '更新未成功，請重新載入確認狀態後再操作'
      setError(message); notify.error(message)
      void qc.invalidateQueries({ queryKey: ['admin', 'orders'] })
    },
  })
  const choose = (next: Decision) => { setDecision(next); setAcknowledged(false); setError('');setReceived('');setRefund('');setReviewNote('') }
  return <section className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-900/20 dark:text-red-200" aria-label="取消與退款處理">
    <p className="font-semibold">取消狀態：{names[cancellation.status] || cancellation.status}</p>
    <p className="mt-1">{needsReview?'有未結清補／退差額，退款金額待行政核對實收款。':`${cancellation.status === 'refunded' ? '已記錄退款' : '預計退款'} NT$ ${(cancellation.refund_amount??0).toLocaleString()} · ${cancellation.calculation_mode === 'manual' ? '人工核對金額' : cancellation.calculation_mode === 'rule' ? '指定方案' : '依日期計算'}`}</p>
    {cancellation.actual_received_amount!=null&&<p className="mt-1 break-words">已核對實收款 NT$ {cancellation.actual_received_amount.toLocaleString()} · {cancellation.cash_review_note}</p>}
    <p className="mt-1 text-xs">這裡只管理取消與退款紀錄，不會自動將款項退回銀行或信用卡。</p>
    {!readOnly && <>
      <div className="mt-2 flex flex-wrap gap-2">{cancellation.status === 'requested' && <><button type="button" disabled={process.isPending} onClick={() => choose('rejected')} className="min-h-11 rounded-lg border border-red-300 px-3 py-2 text-sm disabled:opacity-40 dark:border-red-700">駁回申請</button><button type="button" disabled={process.isPending} onClick={() => choose('approved')} className="min-h-11 rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40">核准取消</button></>}{cancellation.status === 'approved' && <button type="button" disabled={process.isPending} onClick={() => choose(needsReview?'approved':'refunded')} className="min-h-11 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40" >{needsReview?'核對實收款':'記錄退款完成'}</button>}</div>
      {decision && <div className="mt-3 rounded-lg border border-red-200 bg-white p-3 dark:border-red-800 dark:bg-gray-900">
        <p>{decision === 'approved' ? '核准後會取消本訂單課程並釋出排課名額；不會實際退款。' : decision === 'rejected' ? '確定駁回這次取消申請？訂單付款及課程狀態不會變更。' : `請先在銀行或金流完成 NT$ ${(cancellation.refund_amount??0).toLocaleString()} 的退款，再記錄完成。`}</p>
        {decision==='approved'&&needsReview&&<div className="mt-3 space-y-3">
          <p>請合併核對原款、已收補款及已退差額；尚未入帳的補款不可算進實收款。</p>
          <label className="block">實際已收款（扣除已退款）<input inputMode="numeric" className="mt-1 min-h-11 w-full rounded border border-gray-300 bg-white px-3 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white" disabled={process.isPending} value={received} onChange={e=>setReceived(e.target.value)}/></label>
          <label className="block">本次取消退款金額<input inputMode="numeric" className="mt-1 min-h-11 w-full rounded border border-gray-300 bg-white px-3 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white" disabled={process.isPending} value={refund} onChange={e=>setRefund(e.target.value)}/></label>
          <label className="block">核對依據／退款原因<textarea maxLength={1000} value={reviewNote} disabled={process.isPending} onChange={e=>setReviewNote(e.target.value)} className="mt-1 min-h-24 w-full rounded border border-gray-300 bg-white p-3 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white"/></label>
          <label className="flex min-h-11 items-start gap-2"><input type="checkbox" checked={acknowledged} disabled={process.isPending} onChange={e=>setAcknowledged(e.target.checked)}/><span>我已查核銀行／金流實收紀錄，退款不超過實收款</span></label>
        </div>}
        {decision === 'refunded' && <label className="mt-2 flex min-h-11 items-start gap-2 py-2"><input type="checkbox" className="mt-1" checked={acknowledged} disabled={process.isPending} onChange={e => setAcknowledged(e.target.checked)} /><span>我已核對金額並在系統外完成實際退款</span></label>}
        <div className="mt-3 flex flex-wrap gap-2"><button type="button" disabled={process.isPending || (decision === 'refunded' && !acknowledged) || (decision==='approved'&&needsReview&&!reviewValid)} onClick={() => process.mutate(decision)} className="min-h-11 rounded-lg bg-red-600 px-3 py-2 font-semibold text-white disabled:opacity-40">{process.isPending ? '處理中…' : `確定${decisions[decision]}`}</button><button type="button" disabled={process.isPending} onClick={() => { setDecision(null); setAcknowledged(false); setError('') }} className="min-h-11 rounded-lg border border-gray-300 px-3 py-2 dark:border-gray-600">返回，不變更退款狀態</button></div>
      </div>}
      {error && <p role="alert" className="mt-3 break-words font-medium">{error}</p>}
    </>}
  </section>
}
