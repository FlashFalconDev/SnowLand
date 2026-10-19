export interface OrderSettlement {
  currency: 'TWD' | 'JPY'
  base_currency: 'TWD'
  base_amount: number
  amount: number
  rate: string
  locked_at?: string | null
}

export function settlementAmount(settlement: OrderSettlement | undefined, twdAmount: number) {
  return settlement?.currency === 'JPY'
    ? `日幣 JPY ¥ ${settlement.amount.toLocaleString('zh-TW')}`
    : `台幣 NT$ ${twdAmount.toLocaleString('zh-TW')}`
}

export default function SettlementSummary({settlement}: {settlement?: OrderSettlement}) {
  if (!settlement || settlement.currency !== 'JPY') return null
  const rate = settlement.rate.includes('.') ? settlement.rate.replace(/0+$/,'').replace(/\.$/,'') : settlement.rate
  return <section aria-label="付款幣別與金額" className="my-4 space-y-2 rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-4 text-sm leading-6 text-[#1e4e73]">
    <p>實際應付：<strong>{settlementAmount(settlement,settlement.base_amount)}</strong></p>
    <p>台幣計價基準 NT$ {settlement.base_amount.toLocaleString('zh-TW')} · 訂單匯率 1 TWD＝{rate} JPY</p>
    <p>{settlement.locked_at ? '本訂單保留成立時匯率，不隨後續設定變動。' : '預估金額，成立訂單時由後端核定並保留匯率。'}請使用日幣匯款，不要將日幣數字當成台幣金額。</p>
  </section>
}
