/** Estimate only from server-priced items. Final order values remain server-owned. */
export function sumJpyAmounts(amounts: unknown): string|null {
  if(!Array.isArray(amounts)||!amounts.length||amounts.some(value=>!Number.isSafeInteger(value)||value<0))return null
  return amounts.reduce((total,value)=>total+BigInt(value),BigInt(0)).toLocaleString('zh-TW')
}

export function quoteJpyPreview(subtotals: unknown,discounts: unknown,rate: unknown): {amounts:number[];totalLabel:string}|null {
  if(!Array.isArray(subtotals)||!subtotals.length||!Array.isArray(discounts)||discounts.length!==subtotals.length
    ||typeof rate!=='string'||! /^[0-9]{1,9}(?:\.[0-9]{1,8})?$/.test(rate))return null
  const [whole,fraction='']=rate.split('.')
  const numerator=BigInt(whole+fraction.padEnd(8,'0')),divisor=BigInt(100000000),limit=BigInt(Number.MAX_SAFE_INTEGER)
  if(numerator<=BigInt(0))return null
  const amounts:number[]=[]
  let total=BigInt(0)
  for(let index=0;index<subtotals.length;index++){
    const base=subtotals[index],discount=discounts[index]
    if(!Number.isSafeInteger(base)||!Number.isSafeInteger(discount)||base<0||discount<0||discount>base)return null
    const net=base-discount
    const amount=(BigInt(net)*numerator+divisor/BigInt(2))/divisor
    if(amount>limit||(net>0&&amount===BigInt(0)))return null
    amounts.push(Number(amount));total+=amount
  }
  return{amounts,totalLabel:total.toLocaleString('zh-TW')}
}
