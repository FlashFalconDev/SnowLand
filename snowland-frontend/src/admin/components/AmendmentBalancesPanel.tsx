import {useEffect,useRef,useState} from 'react'
import {useQuery,useQueryClient} from '@tanstack/react-query'
import {fetchAmendmentBalances,processAmendmentBalance,type AmendmentBalance,type AmendmentBalanceAction} from '../api/orders'
import {useNotification} from '../context'
import AmendmentNoticeStatus from '../../components/AmendmentNoticeStatus'

const labels:Record<string,string>={topup_due:'待補款',topup_reported:'補款待核對',refund_account_due:'待填退款帳戶',refund_due:'待退款',settled:'差額已結清',no_difference:'無待收退差額',included_in_order:'併入原單付款',superseded:'已由新版取代',cancelled:'已併入取消結算'}
const button='min-h-11 rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:opacity-40 dark:border-gray-600'
const money=(value:number,currency='TWD')=>`${currency==='JPY'?'日幣 JPY ¥':'NT$'} ${Math.abs(value).toLocaleString()}`
const errorText=(error:any)=>String(error?.response?.data?.detail||error?.response?.data?.note||error?.response?.data?.confirmed||error?.response?.data?.action||'無法確認核對結果，請保留視窗，用相同識別碼查詢／重試。')
function BalanceReviewDialog({orderId,row,action,onClose}:{orderId:number;row:AmendmentBalance;action:AmendmentBalanceAction['action'];onClose:()=>void}) {
  const [note,setNote]=useState(''),[confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[uncertain,setUncertain]=useState(false),[error,setError]=useState('')
  const key=useRef(crypto.randomUUID()),locked=useRef(false),dialog=useRef<HTMLDivElement>(null),qc=useQueryClient(),notify=useNotification()
  const rejecting=action==='reject_topup'
  const settlement=row.settlement,nativeBalance=settlement?.currency==='JPY'?settlement.balance_amount:row.balance_amount
  useEffect(()=>{const focus=document.activeElement as HTMLElement|null,overflow=document.body.style.overflow;document.body.style.overflow='hidden';dialog.current?.focus();return()=>{document.body.style.overflow=overflow;focus?.focus()}},[])
  const submit=async()=>{
    if(locked.current||!note.trim()||(!rejecting&&!confirmed))return
    locked.current=true;setBusy(true);setError('')
    try{const result=await processAmendmentBalance(orderId,{amendment_id:row.id,expected_updated_at:row.updated_at,request_key:key.current,action,note:note.trim(),...(!rejecting?{confirmed}: {}),...(settlement?.currency==='JPY'?{currency:'JPY' as const,expected_amount:Math.abs(nativeBalance)}:{})});if(result.data?.id!==row.id)throw new Error('核對結果未確認');notify.success(result.msg);qc.invalidateQueries({queryKey:['admin','orders']});onClose()}
    catch(error:any){setError(errorText(error));const unknown=!error?.response?.status||error.response.status>=500;setUncertain(unknown);if(!unknown)qc.invalidateQueries({queryKey:['admin','orders']})}finally{locked.current=false;setBusy(false)}
  }
  return <div className="fixed inset-0 z-[85] flex items-center justify-center bg-black/60 p-3"><div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="balance-review-title" tabIndex={-1} className="flex max-h-[calc(100dvh-24px)] w-full max-w-lg flex-col overflow-hidden rounded-xl bg-white text-gray-900 shadow-xl outline-none dark:bg-gray-800 dark:text-gray-100" onKeyDown={event=>{
    if(event.key==='Escape'&&!busy&&!uncertain)onClose()
    if(event.key!=='Tab')return
    const elements=Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),textarea:not(:disabled),input:not(:disabled)')),first=elements[0],last=elements[elements.length-1]
    if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.current)){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
  }}><h3 id="balance-review-title" className="border-b border-gray-200 px-5 py-4 font-semibold dark:border-gray-700">{rejecting?'退回補款回報':action==='confirm_topup'?'核對補款已收款':'記錄系統外已完成退款'}</h3>
    <div className="space-y-4 overflow-y-auto p-5 text-sm"><p>第 {row.version} 版 · {money(nativeBalance,settlement?.currency)}</p>{settlement?.currency==='JPY'&&<p>台幣差額基準 {money(row.balance_amount)}；訂單匯率1 TWD＝{settlement.rate} JPY。請核對日幣實收退金額。</p>}<p className="rounded-lg bg-amber-50 p-3 leading-6 text-amber-900 dark:bg-amber-950 dark:text-amber-100">這是人工核對紀錄，不會呼叫銀行、扣款或退款。請先在銀行或外部金流完成查核。</p><label className="block">{rejecting?'退回原因（會員可見）':'核對依據／備註（必填）'}<textarea className="mt-2 min-h-24 w-full rounded-lg border border-gray-300 bg-white p-3 text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-white" maxLength={1000} disabled={busy||uncertain} value={note} onChange={event=>setNote(event.target.value)}/></label>
    {!rejecting&&<label className="flex min-h-11 items-center gap-3"><input type="checkbox" disabled={busy||uncertain} checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/>{action==='confirm_topup'?'我已查到這筆補款實際入帳':'我已在系統外完成這筆實際退款'}</label>}
    {error&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-red-800 dark:bg-red-950 dark:text-red-200">{error}</p>}</div>
    <footer className="flex flex-wrap justify-end gap-2 border-t border-gray-200 p-4 dark:border-gray-700"><button className={button} disabled={busy||uncertain} onClick={onClose}>取消</button><button className={`${button} border-purple-600 bg-purple-600 text-white`} disabled={busy||!note.trim()||(!rejecting&&!confirmed)} onClick={submit}>{busy?'處理中…':uncertain?'查詢／重試本次核對':rejecting?'確認退回':'確認核對並留底'}</button></footer></div></div>
}
export default function AmendmentBalancesPanel({orderId,cancellationStatus}:{orderId:number;cancellationStatus?:string}) {
  const {data,isLoading,isFetching,error,refetch}=useQuery({queryKey:['admin','orders','amendment-balances',orderId],queryFn:()=>fetchAmendmentBalances(orderId),retry:false})
  const [review,setReview]=useState<{row:AmendmentBalance;action:AmendmentBalanceAction['action']}|null>(null)
  if(['requested','approved'].includes(cancellationStatus||''))return <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">本單正在取消／退款流程，差額回報暫停核對；請在下方「取消與退款處理」核對實收款，不要分開重複退差額。</p>
  if(isLoading)return <p role="status" className="text-sm text-gray-500 dark:text-gray-300">讀取差額核對紀錄…</p>
  if(error)return <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-100">差額紀錄載入失敗，不能當成沒有待處理差額。<button className={`${button} ml-2`} onClick={()=>refetch()}>重試</button></div>
  if(!data?.items.length)return null
  return <section className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-sm font-semibold text-gray-900 dark:text-white">差額回報與核對</h3><button className={button} disabled={isFetching} onClick={()=>refetch()}>{isFetching?'載入中…':'重新載入差額'}</button></div>{data.items.filter(row=>row.status!=='superseded').map(row=><article key={row.id} className="space-y-3 rounded-lg border border-gray-200 p-4 text-sm text-gray-800 dark:border-gray-600 dark:text-gray-100"><div className="flex flex-wrap justify-between gap-2"><strong>第 {row.version} 版 · {money(row.settlement?.balance_amount??row.balance_amount,row.settlement?.currency)}</strong><span>{labels[row.status]||row.status}</span></div>
    {row.settlement?.currency==='JPY'&&<p className="text-xs leading-6 text-gray-500 dark:text-gray-300">台幣差額基準 {money(row.balance_amount)}；沿用原訂單匯率1 TWD＝{row.settlement.rate} JPY，實收退請以日幣核對。</p>}
    <AmendmentNoticeStatus receipt={row.notification}/>
    {row.topup_reference&&<p>會員回報帳號末五碼：{row.topup_reference}</p>}
    {row.balance_amount<0&&row.refund_bank?.account_number&&<div className="space-y-1 break-all rounded-lg bg-gray-50 p-3 dark:bg-gray-900"><p>退款銀行：{row.refund_bank.bank_name}</p><p>退款帳號：{row.refund_bank.account_number}</p><p>戶名：{row.refund_bank.account_holder}</p></div>}
    {row.refund_bank?.overseas_details&&<p className="whitespace-pre-wrap break-words text-sm">海外退款資料：{row.refund_bank.overseas_details}</p>}
    {row.status==='topup_reported'&&<div className="flex flex-wrap gap-2"><button className={button} onClick={()=>setReview({row,action:'reject_topup'})}>退回重填</button><button className={`${button} border-purple-600 text-purple-700 dark:text-purple-300`} onClick={()=>setReview({row,action:'confirm_topup'})}>核對補款</button></div>}
    {row.status==='refund_due'&&<button className={`${button} border-purple-600 text-purple-700 dark:text-purple-300`} onClick={()=>setReview({row,action:'confirm_refund'})}>記錄已於系統外退款</button>}
    {row.events.length>0&&<details className="text-xs"><summary className="cursor-pointer py-2">查看處理紀錄（{row.events.length}）</summary><ul className="space-y-2">{row.events.map((event,index)=><li key={index} className="rounded bg-gray-50 p-2 leading-6 dark:bg-gray-900">{new Date(event.created_at).toLocaleString('zh-TW')} · {event.actor} · {labels[event.previous_status]} → {labels[event.status]}<p className="whitespace-pre-wrap break-words">{event.note||event.reference||'會員更新退款資料'}</p></li>)}</ul></details>}
  </article>)}{review&&<BalanceReviewDialog orderId={orderId} row={review.row} action={review.action} onClose={()=>setReview(null)}/>}</section>
}
