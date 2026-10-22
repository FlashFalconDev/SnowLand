export function payrollDescription(value: string) {
  const names: Record<string,string> = {snowboard:'單板',ski:'雙板',photo:'攝影'}
  return value.replace(/\b(snowboard|ski|photo)\b/g, key=>names[key])
}

export function payrollCalculation(line:{line_type:string;quantity:string;unit_amount:string;total_amount:number},currency:string) {
  const unit = line.line_type === 'referral' ? '%' : ['course','assistance'].includes(line.line_type) ? ' 小時' : ' 項'
  return `${line.quantity}${unit} × ${currency} ${Number(line.unit_amount).toLocaleString('zh-TW')} = ${currency} ${line.total_amount.toLocaleString('zh-TW')}`
}
