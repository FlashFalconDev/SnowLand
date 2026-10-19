import { useSiteLocale } from '../../contexts/SiteLocale'
import { translateSiteText, type SiteLocale } from '../../utils/siteLocale'

export interface OrderSettlement {
  currency: 'TWD' | 'JPY'
  base_currency: 'TWD'
  base_amount: number
  amount: number
  rate: string
  locked_at?: string | null
}

export function settlementAmount(settlement: OrderSettlement | undefined, twdAmount: number, locale: SiteLocale = 'zh-Hant') {
  return settlement?.currency === 'JPY'
    ? `${translateSiteText(locale,'日幣 JPY')} ¥ ${settlement.amount.toLocaleString('zh-TW')}`
    : `${translateSiteText(locale,'台幣 NT$')} ${twdAmount.toLocaleString('zh-TW')}`
}

export function settlementRateLabel(rate: string) {
  return rate.includes('.') ? rate.replace(/0+$/,'').replace(/\.$/,'') : rate
}

export default function SettlementSummary({settlement,title='訂單日幣金額',paymentInstructions=false}: {settlement?: OrderSettlement; title?: string; paymentInstructions?: boolean}) {
  const {locale,t}=useSiteLocale()
  if (!settlement || settlement.currency !== 'JPY') return null
  const rate = settlementRateLabel(settlement.rate)
  return <section aria-label={t('付款幣別與金額')} className="my-4 space-y-2 rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] p-4 text-sm leading-6 text-[#1e4e73]">
    <p>{t(title)}：<strong>{settlementAmount(settlement,settlement.base_amount,locale)}</strong></p>
    <p>{t('台幣計價基準 NT$ {amount} · 訂單匯率 1 TWD＝{rate} JPY',{amount:settlement.base_amount.toLocaleString('zh-TW'),rate})}</p>
    <p>{t(settlement.locked_at ? '本訂單保留成立時匯率，不隨後續設定變動。' : '預估金額，成立訂單時由後端核定並保留匯率。')}{paymentInstructions&&t('請使用日幣匯款，不要將日幣數字當成台幣金額。')}</p>
  </section>
}
