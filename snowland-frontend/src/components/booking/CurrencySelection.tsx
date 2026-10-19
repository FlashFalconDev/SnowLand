import { useEffect, useId, useState } from 'react'

export interface PaymentCurrencyQuote { currency: 'TWD' | 'JPY'; rate: string }
interface Choice { code: 'TWD' | 'JPY'; rate: string }
const twd: Choice = {code:'TWD',rate:'1.00000000'}

export default function CurrencySelection({clientCode,value,onChange,onReadyChange,reloadKey=0}: {
  clientCode: string
  value: PaymentCurrencyQuote
  onChange: (value: PaymentCurrencyQuote) => void
  onReadyChange: (ready: boolean) => void
  reloadKey?: number
}) {
  const [choices,setChoices]=useState<Choice[]>([twd])
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [retry,setRetry]=useState(0)
  const helpId=useId()
  useEffect(()=>{
    let active=true
    const controller=new AbortController()
    const timer=setTimeout(()=>controller.abort(),10000)
    setLoading(true);setError('');setChoices([twd])
    fetch(`/booking/${encodeURIComponent(clientCode)}/api/currency-options/`,{credentials:'include',signal:controller.signal})
      .then(async response=>{
        if(!response.ok)throw Error('currency unavailable')
        const payload=await response.json()
        if(!Array.isArray(payload.currencies))throw Error('invalid currency choices')
        const rows=payload.currencies.filter((row:any)=>row && ['TWD','JPY'].includes(row.code)
          && typeof row.rate==='string' && /^[0-9]{1,9}(?:\.[0-9]{1,8})?$/.test(row.rate) && Number(row.rate)>0)
        if(!rows.some((row:Choice)=>row.code==='TWD'&&Number(row.rate)===1)
          || new Set(rows.map((row:Choice)=>row.code)).size!==rows.length)throw Error('invalid currency choices')
        if(active)setChoices(rows)
      })
      .catch(()=>{if(active)setError('日幣選項暫時無法載入，目前可改用台幣。')})
      .finally(()=>{clearTimeout(timer);if(active)setLoading(false)})
    return()=>{active=false;clearTimeout(timer);controller.abort()}
  },[clientCode,retry,reloadKey])
  const selected=choices.find(row=>row.code===value.currency)
  const ready=value.currency==='TWD'||(!loading&&!error&&selected?.rate===value.rate)
  useEffect(()=>{onReadyChange(ready)},[ready,onReadyChange])
  return <section aria-label="付款幣別設定" className="mb-4 space-y-3 rounded-sm border border-[#dbe3ec] bg-white p-4">
    <label className="block text-sm font-semibold text-[#1f2937]">付款幣別
      <select value={value.currency} disabled={loading} aria-describedby={helpId} onChange={event=>{
        const choice=choices.find(row=>row.code===event.target.value)
        if(choice)onChange({currency:choice.code,rate:choice.rate})
      }} className="mt-2 min-h-11 w-full rounded-sm border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#1f2937] disabled:opacity-60">
        {choices.map(row=><option key={row.code} value={row.code}>{row.code==='JPY'?'日幣 JPY（銀行匯款）':'台幣 TWD'}</option>)}
        {value.currency==='JPY'&&!selected&&<option value="JPY" disabled>日幣 JPY（{loading?'確認中':'目前不可用'}）</option>}
      </select>
    </label>
    <p id={helpId} className="text-xs leading-5 text-[#64748b]">{value.currency==='JPY'
      ? `本次匯率 1 TWD＝${value.rate} JPY。日幣金額由後端換算，成立訂單後鎖定；後續改匯率不影響本單。`
      : '以下課程以台幣定價；可用幣別依學校收款設定提供，訂單成立後不能換幣別。'}</p>
    {loading&&<p role="status" className="text-xs text-[#64748b]">正在確認可用幣別…</p>}
    {error&&<p role="alert" className="text-sm text-[#b42318]">{error}<button type="button" onClick={()=>setRetry(n=>n+1)} className="ml-2 min-h-11 rounded-sm border border-[#d4dbe4] px-3 font-semibold">重新載入幣別</button></p>}
    {!loading&&!error&&!ready&&<p role="alert" className="text-sm text-[#92400e]">{selected
      ? <>匯率已更新，請重新確認。<button type="button" onClick={()=>onChange({currency:selected.code,rate:selected.rate})} className="mt-2 min-h-11 w-full rounded-sm border border-[#e0b760] px-3 font-semibold">確認使用新匯率 1 TWD＝{selected.rate} JPY</button></>
      : '目前不提供日幣付款，請改選台幣；原有課程與聯絡資料仍保留。'}</p>}
  </section>
}
