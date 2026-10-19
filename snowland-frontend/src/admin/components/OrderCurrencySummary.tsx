import { settlementAmount, settlementRateLabel, type OrderSettlement } from '../../components/booking/SettlementSummary'

export default function OrderCurrencySummary({settlement,receivedSettlement,confirmationRequired=false,confirmed=false,onConfirmChange,busy=false}: {
  settlement?: OrderSettlement
  receivedSettlement?: OrderSettlement | null
  confirmationRequired?: boolean
  confirmed?: boolean
  onConfirmChange?: (value:boolean) => void
  busy?: boolean
}) {
  if(settlement?.currency!=='JPY')return null
  return <section aria-label="日幣收款核對" className="mb-4 space-y-3 rounded-lg border border-violet-200 bg-violet-50 p-4 text-sm text-gray-900 dark:border-violet-800 dark:bg-gray-800 dark:text-white">
    <h4 className="font-semibold text-violet-800 dark:text-violet-200">付款幣別：日幣 JPY</h4>
    <div className="flex flex-wrap justify-between gap-2"><span>本單日幣計價</span><strong>{settlementAmount(settlement,settlement.base_amount)}</strong></div>
    <p className="text-xs leading-6 text-gray-600 dark:text-gray-300">台幣計價基準 NT$ {settlement.base_amount.toLocaleString('zh-TW')}；成立時匯率 1 TWD＝{settlementRateLabel(settlement.rate)} JPY。以下台幣明細不是要客人另付一筆台幣。</p>
    {receivedSettlement?.currency==='JPY'
      ? <p className="rounded-lg bg-emerald-50 p-3 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">行政已核對收款（原訂單款項）：<strong>{settlementAmount(receivedSettlement,receivedSettlement.base_amount)}</strong>。修改後補退差額請看個別紀錄，實際入帳以銀行紀錄為準。</p>
      : <p className="text-xs leading-6 text-gray-600 dark:text-gray-300">尚無日幣核款快照；客人回報後五碼，不等於行政已核對收款。</p>}
    {confirmationRequired&&<label className="flex min-h-11 items-start gap-3 rounded-lg border border-violet-300 bg-white p-3 dark:border-violet-700 dark:bg-gray-900">
      <input type="checkbox" checked={confirmed} disabled={busy} onChange={event=>onConfirmChange?.(event.target.checked)} className="mt-1 h-4 w-4 shrink-0" />
      <span>我已核對銀行實收為 <b>{settlementAmount(settlement,settlement.base_amount)}</b>，確認標記「已付款」。<span className="mt-1 block text-xs leading-6 text-gray-600 dark:text-gray-300">若實收金額不同，請保留「待確認付款」先核對差額；這個操作不會自動換匯或扣款。</span></span>
    </label>}
  </section>
}
