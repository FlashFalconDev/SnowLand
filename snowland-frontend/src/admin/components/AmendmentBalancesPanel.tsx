import {useEffect,useId,useRef,useState} from 'react'
import {useQuery,useQueryClient} from '@tanstack/react-query'
import {Link} from 'react-router-dom'
import {
  fetchAmendmentBalances, fetchAmendmentTopupLink, processAmendmentBalance, processAmendmentWorkflow,
  type AmendmentBalance, type AmendmentBalanceAction, type AmendmentWorkflowAction, type Order,
} from '../api/orders'
import {useNotification} from '../context'
import AmendmentNoticeStatus from '../../components/AmendmentNoticeStatus'
import { formatPaymentValue, parsePaymentValue, type PaymentCurrency } from '../../utils/settlementPreview'

const AMENDMENT_BALANCES_TITLE = '差額回報與核對'
const labels:Record<string,string>={topup_due:'待補款',topup_reported:'補款待核對',refund_account_due:'待填退款帳戶',refund_due:'待退款',settled:'差額已結清',no_difference:'無待收退差額',included_in_order:'併入原單付款',superseded:'已由新版取代',cancelled:'已併入取消結算'}
const button='min-h-11 rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:opacity-40 dark:border-gray-600'
const workflowLabels: Record<AmendmentWorkflowAction, string> = {
  mark_topup_notified: '登記已通知補款', record_topup: '核對外部補款', request_refund: '申請退款',
  approve_refund: '核准退款', reject_refund: '駁回退款', record_refund: '記錄已在系統外退款',
}
const refundStages = {
  request_refund: '退款待審核', approve_refund: '退款已核准，待外部退款',
  reject_refund: '退款已駁回', record_refund: '已記錄外部退款',
}
type ReviewAction = AmendmentBalanceAction['action'] | AmendmentWorkflowAction
type WorkflowAccess = { enabled: boolean; charge: boolean; request: boolean; review: boolean }

export function amendmentBalanceLabel(balance: NonNullable<Order['amendment_balance']>) {
  return (balance.refund_action && refundStages[balance.refund_action])
    || ((balance.settlement?.amount ?? balance.amount) > 0 ? '待補款' : '待退款')
}

const money=(value:number,currency?:PaymentCurrency)=>formatPaymentValue(Math.abs(value),currency)
const errorText=(error:any)=>String(error?.response?.data?.detail||error?.response?.data?.expected_amount||error?.response?.data?.external_reference||error?.response?.data?.note||error?.response?.data?.confirmed||error?.response?.data?.action||'無法確認核對結果，請保留視窗，用相同識別碼查詢／重試。')
function BalanceReviewDialog({orderId,row,action,onClose}:{orderId:number;row:AmendmentBalance;action:ReviewAction;onClose:()=>void}) {
  const [note,setNote]=useState(''),[confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[uncertain,setUncertain]=useState(false),[error,setError]=useState('')
  const [amount, setAmount] = useState('')
  const [reference, setReference] = useState('')
  const key=useRef(crypto.randomUUID()),locked=useRef(false),dialog=useRef<HTMLDivElement>(null),qc=useQueryClient(),notify=useNotification()
  const rejecting=action==='reject_topup'
  const settlement=row.settlement,nativeBalance=settlement?settlement.balance_amount:row.balance_amount
  const currency = settlement?.currency ?? 'TWD'
  const legacy = action === 'confirm_topup' || action === 'confirm_refund' || action === 'reject_topup'
  const recordsCash = action === 'record_topup' || action === 'record_refund'
  const needsConfirmation = recordsCash || action === 'confirm_topup' || action === 'confirm_refund' || action === 'reject_refund'
  const enteredAmount = action === 'request_refund' ? parsePaymentValue(amount.trim(), currency) : Math.abs(nativeBalance)
  const valid = note.trim() && (!needsConfirmation || confirmed) && (!recordsCash || reference.trim())
    && enteredAmount === Math.abs(nativeBalance)
  const heading = legacy
    ? (rejecting ? '退回補款回報' : action === 'confirm_topup' ? '核對補款已收款' : '記錄系統外已完成退款')
    : workflowLabels[action]
  const acknowledgement = action === 'reject_refund' ? '我確認這筆差額尚未在系統外退款'
    : action === 'confirm_topup' || action === 'record_topup' ? '我已查到這筆補款實際入帳'
      : '我已在系統外完成這筆實際退款'
  useEffect(()=>{const focus=document.activeElement as HTMLElement|null,overflow=document.body.style.overflow;document.body.style.overflow='hidden';dialog.current?.focus();return()=>{document.body.style.overflow=overflow;focus?.focus()}},[])
  const submit=async()=>{
    if(locked.current || !valid || enteredAmount === null)return
    locked.current=true;setBusy(true);setError('')
    const input = { amendment_id: row.id, expected_updated_at: row.updated_at, request_key: key.current,
      note: note.trim(), ...(needsConfirmation ? { confirmed } : {}) }
    try {
      const result = legacy
        ? await processAmendmentBalance(orderId, { ...input, action, ...(settlement ? { currency, expected_amount: enteredAmount } : {}) })
        : await processAmendmentWorkflow(orderId, { ...input, action, currency, expected_amount: enteredAmount,
          ...(recordsCash ? { external_reference: reference.trim() } : {}) })
      if (result.data?.id !== row.id) throw new Error('核對結果未確認')
      notify.success('msg' in result ? result.msg as string : '差額作業已登記')
      qc.invalidateQueries({queryKey:['admin','orders']})
      onClose()
    } catch(error:any) {
      setError(errorText(error))
      const unknown = !error?.response?.status || error.response.status >= 500
      setUncertain(unknown)
      if(!unknown)qc.invalidateQueries({queryKey:['admin','orders']})
    } finally { locked.current=false;setBusy(false) }
  }
  return <div className="fixed inset-0 z-[85] flex items-center justify-center bg-black/60 p-3"><div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="balance-review-title" tabIndex={-1} className="flex max-h-[calc(100dvh-24px)] w-full max-w-lg flex-col overflow-hidden rounded-xl bg-white text-gray-900 shadow-xl outline-none dark:bg-gray-800 dark:text-gray-100" onKeyDown={event=>{
    if(event.key==='Escape'&&!busy&&!uncertain)onClose()
    if(event.key!=='Tab')return
    const elements=Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),textarea:not(:disabled),input:not(:disabled)')),first=elements[0],last=elements[elements.length-1]
    if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.current)){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
  }}><h3 id="balance-review-title" className="border-b border-gray-200 px-5 py-4 font-semibold dark:border-gray-700">{heading}</h3>
    <div className="space-y-4 overflow-y-auto p-5 text-sm"><p>第 {row.version} 版 · {money(nativeBalance,settlement?.currency)}</p>{settlement&&<p>台幣差額基準 {money(row.balance_amount)}；訂單匯率1 TWD＝{settlement.rate} {settlement.currency}。請核對原幣實收退金額。</p>}
    <p className="rounded-lg bg-amber-50 p-3 leading-6 text-amber-900 dark:bg-amber-950 dark:text-amber-100">{action === 'mark_topup_notified' ? '請先將補款資訊通知客人，再登記通知紀錄。' : '實際收退款須在銀行或外部金流辦理，此處僅供記錄及核對。'}</p>
    {action === 'request_refund' && <label className="block">退款金額（{currency}，必填）
      <input className={`${button} mt-1 block w-full`} inputMode="decimal" disabled={busy || uncertain} value={amount} onChange={event => setAmount(event.target.value)} />
      <span className="mt-1 block text-xs">輸入完整差額 {money(nativeBalance, currency)}。同一筆差額不得分批退款。</span>
    </label>}
    <label className="block">{rejecting?'退回原因（會員可見）':action === 'request_refund' || action === 'reject_refund' ? '原因（必填）' : '核對依據／備註（必填）'}<textarea className="mt-2 min-h-24 w-full rounded-lg border border-gray-300 bg-white p-3 text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-white" maxLength={1000} disabled={busy||uncertain} value={note} onChange={event=>setNote(event.target.value)}/></label>
    {recordsCash && <label className="block">外部交易參考（必填）
      <input className={`${button} mt-1 block w-full`} maxLength={100} disabled={busy || uncertain} value={reference} onChange={event => setReference(event.target.value)} />
    </label>}
    {needsConfirmation&&<label className="flex min-h-11 items-center gap-3"><input type="checkbox" disabled={busy||uncertain} checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/>{acknowledgement}</label>}
    {error&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-red-800 dark:bg-red-950 dark:text-red-200">{error}</p>}</div>
    <footer className="flex flex-wrap justify-end gap-2 border-t border-gray-200 p-4 dark:border-gray-700"><button className={button} disabled={busy||uncertain} onClick={onClose}>取消</button><button className={`${button} border-purple-600 bg-purple-600 text-white`} disabled={busy||!valid} onClick={submit}>{busy?'處理中…':uncertain?'查詢／重試本次核對':legacy?(rejecting?'確認退回':'確認核對並留底'):heading}</button></footer></div></div>
}
function TopupLink({ orderId, amendmentId }: { orderId: number; amendmentId: number }) {
  const [link, setLink] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  async function getLink() {
    setBusy(true)
    setLink('')
    setMessage('')
    try {
      const path = await fetchAmendmentTopupLink(orderId, amendmentId)
      setLink(new URL(path, window.location.origin).href)
    } catch (error) {
      setMessage(errorText(error))
    } finally {
      setBusy(false)
    }
  }
  return <div className="space-y-2">
    <button className={button} disabled={busy} onClick={getLink}>{busy ? '取得中…' : '取得補款連結'}</button>
    {link && <div className="flex flex-wrap items-center gap-2">
      <input readOnly aria-label="補款連結" className={`${button} min-w-0 flex-1`} value={link} onFocus={event => event.target.select()} />
      <button className={button} onClick={async () => {
        try { await navigator.clipboard.writeText(link); setMessage('已複製補款連結') }
        catch { setMessage('請選取連結並手動複製') }
      }}>複製連結</button>
    </div>}
    {message && <p role="status">{message}</p>}
  </div>
}

export default function AmendmentBalancesPanel({ order, canReconcile, canRefund, paymentsHref, refundsHref, workflowAccess }: {
  order: Pick<Order, 'id' | 'amendment_balance' | 'cancellation' | 'is_test' | 'user'>
  canReconcile: boolean
  canRefund: boolean
  paymentsHref?: string
  refundsHref?: string
  workflowAccess?: WorkflowAccess
}) {
  const orderId = order.id
  const balance = order.amendment_balance
  const cancellationPaused = ['requested', 'approved'].includes(order.cancellation?.status ?? '')
  const panelId = useId()
  const panelRef = useRef<HTMLElement>(null)
  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['admin', 'orders', 'amendment-balances', orderId],
    queryFn: () => fetchAmendmentBalances(orderId),
    enabled: canReconcile,
    retry: false,
  })
  const [review,setReview]=useState<{row:AmendmentBalance;action:ReviewAction}|null>(null)
  const rows = data?.items.filter(row => row.status !== 'superseded') ?? []
  const showRecords = canReconcile && (cancellationPaused || isLoading || error || rows.length > 0)
  if (!balance && !showRecords) return null

  function focusPanel() {
    const panel = panelRef.current
    if (!panel) return
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    panel.focus({ preventScroll: true })
    panel.scrollIntoView({ block: 'start', behavior: reducedMotion ? 'auto' : 'smooth' })
  }

  let content
  if (cancellationPaused) {
    content = <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
      本單正在取消／退款流程，差額回報暫停核對，請勿分開重複退差額。{' '}
      {canRefund && '請在此訂單的「取消與退款處理」區核對實收款。'}
      {refundsHref && <Link className="font-semibold underline" to={refundsHref}>前往「取消與退款」核對實收款</Link>}
      {!canRefund && !refundsHref && '請由具退款權限的人員核對實收款。'}
    </p>
  } else if (!canReconcile) {
    content = <p className="text-sm text-gray-700 dark:text-gray-300">
      {paymentsHref ? <Link className="font-semibold text-violet-700 underline dark:text-violet-300" to={paymentsHref}>前往「對帳與差額」處理此訂單</Link> : '請由具付款權限的人員在「對帳與差額」處理此訂單。'}
    </p>
  } else if (isLoading) {
    content = <p role="status" className="text-sm text-gray-500 dark:text-gray-300">讀取差額核對紀錄…</p>
  } else if (error) {
    content = <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-100">差額紀錄載入失敗，不能當成沒有待處理差額。<button type="button" className={`${button} ml-2`} onClick={() => refetch()}>重試</button></div>
  } else if (!rows.length) {
    content = <p role="status" className="text-sm text-gray-500 dark:text-gray-300">目前沒有可顯示的差額紀錄，請重新載入差額再確認。</p>
  } else {
    content = rows.map(row => {
      const amount = row.settlement?.balance_amount ?? row.balance_amount
      const refundPending = ['refund_account_due', 'refund_due'].includes(row.status) && amount < 0
      const waitingTopup = row.status === 'topup_due' && amount > 0
      const reportedTopup = row.status === 'topup_reported' && amount > 0
      const hasRefundRequest = row.refund_action === 'request_refund' || row.refund_action === 'approve_refund'
      const charge = workflowAccess?.enabled && workflowAccess.charge
      const actions: AmendmentWorkflowAction[] = []
      if (waitingTopup && charge && !row.topup_notified) actions.push('mark_topup_notified')
      if (charge && (reportedTopup || (waitingTopup && (order.is_test || order.user === null)))) actions.push('record_topup')
      if (refundPending && workflowAccess?.enabled) {
        if (workflowAccess.request && (!row.refund_action || row.refund_action === 'reject_refund')) actions.push('request_refund')
        if (workflowAccess.review && hasRefundRequest) {
          actions.push(row.refund_action === 'request_refund' ? 'approve_refund' : 'record_refund', 'reject_refund')
        }
      }
      return <article key={row.id} className="space-y-3 rounded-lg border border-gray-200 p-4 text-sm text-gray-800 dark:border-gray-600 dark:text-gray-100">
      <div className="flex flex-wrap justify-between gap-2"><strong>第 {row.version} 版 · {money(amount, row.settlement?.currency)}</strong><span>{(row.refund_action && refundStages[row.refund_action]) || labels[row.status] || row.status}</span></div>
      {row.settlement&&<p className="text-xs leading-6 text-gray-500 dark:text-gray-300">台幣差額基準 {money(row.balance_amount)}；沿用原訂單匯率1 TWD＝{row.settlement.rate} {row.settlement.currency}，請核對原幣實收退金額。</p>}
      <AmendmentNoticeStatus receipt={row.notification}/>
      {waitingTopup && order.user !== null && !order.is_test && <p>會員回報補款後，即可在此核對實際入帳。</p>}
      {row.topup_notified && <p>已登記補款通知</p>}
      {waitingTopup && charge && !order.is_test && <TopupLink orderId={orderId} amendmentId={row.id} />}
      {row.topup_reference&&<p>會員回報帳號末五碼：{row.topup_reference}</p>}
      {row.balance_amount<0&&row.refund_bank?.account_number&&<div className="space-y-1 break-all rounded-lg bg-gray-50 p-3 dark:bg-gray-900"><p>退款銀行：{row.refund_bank.bank_name}</p><p>退款帳號：{row.refund_bank.account_number}</p><p>戶名：{row.refund_bank.account_holder}</p></div>}
      {row.refund_bank?.overseas_details&&<p className="whitespace-pre-wrap break-words text-sm">海外退款資料：{row.refund_bank.overseas_details}</p>}
      {reportedTopup && !order.is_test && <div className="flex flex-wrap gap-2"><button className={button} onClick={()=>setReview({row,action:'reject_topup'})}>退回重填</button>{!charge && <button className={button} onClick={()=>setReview({row,action:'confirm_topup'})}>核對補款</button>}</div>}
      {row.status==='refund_due' && !order.is_test && !workflowAccess?.enabled && !row.refund_action && <button className={button} onClick={()=>setReview({row,action:'confirm_refund'})}>記錄已於系統外退款</button>}
      {!!actions.length && <div className="flex flex-wrap gap-2">
        {actions.map(action => <button key={action} className={`${button} border-purple-600 text-purple-700 dark:text-purple-300`}
          onClick={() => setReview({row, action})}>{workflowLabels[action]}</button>)}
      </div>}
      {row.events.length>0&&<details className="text-xs"><summary className="cursor-pointer py-2">查看處理紀錄（{row.events.length}）</summary><ul className="space-y-2">{row.events.map((event,index)=><li key={index} className="rounded bg-gray-50 p-2 leading-6 dark:bg-gray-900">{new Date(event.created_at).toLocaleString('zh-TW')} · {event.actor} · {workflowLabels[event.action as AmendmentWorkflowAction] || `${labels[event.previous_status]} → ${labels[event.status]}`}{event.settlement && ` · ${money(event.settlement.amount, event.settlement.currency)}`}
        <p className="whitespace-pre-wrap break-words">{event.note||event.reference||'會員更新退款資料'}</p>
        {event.external_reference && <p className="break-all">外部交易參考　{event.external_reference}</p>}
      </li>)}</ul></details>}
    </article>
    })
  }

  return <>
    {balance && <section className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
      <h3 className="font-semibold">訂單修改差額尚未結清</h3>
      <p className="mt-2">{amendmentBalanceLabel(balance)} {money(balance.settlement?.amount ?? balance.amount, balance.settlement?.currency)}</p>
      <p className="mt-1 text-xs leading-6">{cancellationPaused ? '取消流程已暫停這筆差額。' : '訂單付款狀態僅反映原訂單。差額需另行核對才會結清。'}</p>
      <button type="button" aria-controls={panelId} onClick={focusPanel} className={`${button} mt-2 border-amber-600 font-semibold hover:bg-amber-100 dark:border-amber-500 dark:hover:bg-amber-900`}>
        {AMENDMENT_BALANCES_TITLE}
      </button>
    </section>}
    <section ref={panelRef} id={panelId} aria-labelledby={`${panelId}-title`} tabIndex={-1}
      className="scroll-mt-2 space-y-3 rounded-lg p-3 focus:outline focus:outline-2 focus:outline-violet-500">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={`${panelId}-title`} className="text-sm font-semibold text-gray-900 dark:text-white">{AMENDMENT_BALANCES_TITLE}</h3>
        {canReconcile && !cancellationPaused && !isLoading && !error && <button type="button" className={button} disabled={isFetching} onClick={() => refetch()}>{isFetching ? '載入中…' : '重新載入差額'}</button>}
      </div>
      {order.is_test && workflowAccess?.enabled && <p role="status" className="text-sm">測試訂單僅供後台演練。請使用合成交易資料。</p>}
      {content}
      {canReconcile && !cancellationPaused && review && <BalanceReviewDialog orderId={orderId} row={review.row} action={review.action} onClose={() => setReview(null)} />}
    </section>
  </>
}
