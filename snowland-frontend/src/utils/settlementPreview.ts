export const paymentCurrencyNames = { TWD: '台幣 TWD', JPY: '日幣 JPY', USD: '美元 USD', HKD: '港幣 HKD', CNY: '人民幣 CNY' } as const
export type PaymentCurrency = keyof typeof paymentCurrencyNames
export type ForeignPaymentCurrency = Exclude<PaymentCurrency, 'TWD'>
export const twoDecimalCurrencies = ['USD', 'HKD', 'CNY'] as const

const hasCents = (currency: PaymentCurrency) => currency !== 'TWD' && currency !== 'JPY'

function formatMinorUnits(amount: bigint, currency: PaymentCurrency) {
  if(!hasCents(currency)) return amount.toLocaleString('zh-TW')
  const absolute = amount < BigInt(0) ? -amount : amount
  const hundred = BigInt(100)
  return `${amount < BigInt(0) ? '-' : ''}${(absolute/hundred).toLocaleString('zh-TW')}.${String(absolute%hundred).padStart(2,'0')}`
}

export function formatPaymentValue(amount: number, currency: PaymentCurrency = 'TWD') {
  const label = currency === 'TWD' ? 'NT$' : currency === 'JPY' ? '日幣 JPY ¥' : currency
  return `${label} ${formatMinorUnits(BigInt(amount),currency)}`
}

export function parsePaymentValue(value: string, currency: PaymentCurrency): number|null {
  if(!(hasCents(currency) ? /^\d+(?:\.\d{1,2})?$/ : /^\d+$/).test(value)) return null
  const [whole, cents = ''] = value.split('.')
  const parsed = Number(hasCents(currency) ? whole + cents.padEnd(2,'0') : whole)
  return Number.isSafeInteger(parsed) ? parsed : null
}

/** Estimate only from server-priced items. Final order values remain server-owned. */
export function sumJpyAmounts(amounts: unknown, currency: PaymentCurrency = 'JPY'): string|null {
  if(!Array.isArray(amounts)||!amounts.length||amounts.some(value=>!Number.isSafeInteger(value)||value<0))return null
  return formatMinorUnits(amounts.reduce((total,value)=>total+BigInt(value),BigInt(0)),currency)
}

export function quoteJpyPreview(subtotals: unknown,discounts: unknown,rate: unknown,allowRoundedZero=false,currency: PaymentCurrency = 'JPY'): {amounts:number[];totalLabel:string}|null {
  if(!Array.isArray(subtotals)||!subtotals.length||!Array.isArray(discounts)||discounts.length!==subtotals.length
    ||typeof rate!=='string'||! /^[0-9]{1,9}(?:\.[0-9]{1,8})?$/.test(rate))return null
  const [whole,fraction='']=rate.split('.')
  const numerator=BigInt(whole+fraction.padEnd(8,'0'))*BigInt(hasCents(currency)?100:1),divisor=BigInt(100000000),limit=BigInt(Number.MAX_SAFE_INTEGER)
  if(numerator<=BigInt(0))return null
  const amounts:number[]=[]
  let total=BigInt(0)
  for(let index=0;index<subtotals.length;index++){
    const base=subtotals[index],discount=discounts[index]
    if(!Number.isSafeInteger(base)||!Number.isSafeInteger(discount)||base<0||discount<0||discount>base)return null
    const net=base-discount
    const amount=(BigInt(net)*numerator+divisor/BigInt(2))/divisor
    if(amount>limit||(net>0&&amount===BigInt(0)&&!allowRoundedZero))return null
    amounts.push(Number(amount));total+=amount
  }
  return{amounts,totalLabel:formatMinorUnits(total,currency)}
}
