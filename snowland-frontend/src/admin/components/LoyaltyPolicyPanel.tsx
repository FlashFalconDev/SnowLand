import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { currentClientCode } from '@/utils/tenant'
import { fetchLoyaltyPolicy, saveLoyaltyPolicy, type LoyaltyPolicy } from '../api/customers'

const input = 'mt-1 block min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 dark:border-gray-600 dark:bg-gray-900'
const button = 'min-h-11 rounded-lg border px-4 text-sm disabled:opacity-50'

export default function LoyaltyPolicyPanel() {
  const [open, setOpen] = useState(false)
  const cache = useQueryClient()
  const queryKey = ['admin', 'loyalty-policy', currentClientCode()]
  const query = useQuery({queryKey, queryFn:fetchLoyaltyPolicy, enabled:open})
  return <section className="rounded-xl border border-gray-200 bg-white p-4 text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-white">
    <button type="button" aria-expanded={open} className={button} onClick={()=>setOpen(!open)}>會員積分與紅利設定</button>
    {open && (query.data ? <LoyaltyPolicyEditor initial={query.data}
      onSaved={policy=>cache.setQueryData(queryKey,policy)} reload={async()=> (await query.refetch()).data} />
      : query.isError ? <p role="alert" className="mt-3">設定載入失敗。<button type="button" className={button} onClick={()=>void query.refetch()}>重試</button></p>
      : <p role="status" className="mt-3">正在載入會員制度…</p>)}
  </section>
}

function LoyaltyPolicyEditor({initial, reload, onSaved}:{
  initial:LoyaltyPolicy; reload:()=>Promise<LoyaltyPolicy|undefined>; onSaved:(policy:LoyaltyPolicy)=>void
}) {
  const [draft, setDraft] = useState(initial)
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const patch = (fields:Partial<LoyaltyPolicy>) => setDraft(previous=>({...previous,...fields}))
  const save = async (event:React.FormEvent) => {
    event.preventDefault()
    setPending(true); setError(''); setMessage('')
    try {
      const saved = await saveLoyaltyPolicy(draft)
      setDraft(saved)
      onSaved(saved)
      setMessage('設定已儲存')
    } catch (failure) {
      const body = (failure as {response?:{data?:Record<string,unknown>}}).response?.data
      const errors = Object.values(body || {}).flat().filter(value=>typeof value === 'string')
      setError(errors.join('、') || '設定未儲存，請確認格式或重新載入後再試')
    } finally {
      setPending(false)
    }
  }
  return <form className="mt-4 space-y-4 text-sm" onSubmit={save}>
    <p>此設定適用於本校新訂單。已建立的訂單保留當時的規則與折抵比例。</p>
    <fieldset disabled={pending} className="space-y-4">
      <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={draft.enabled}
        onChange={event=>patch({enabled:event.target.checked})} />開放本校會員積分與紅利</label>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label>入點時機<select className={input} value={draft.earn_on} onChange={event=>patch({earn_on:event.target.value as LoyaltyPolicy['earn_on']})}>
          <option value="completed">訂單完課後</option><option value="paid">確認付款後</option>
        </select></label>
        <label>退款扣回規則<select className={input} value={draft.refund_rule} onChange={event=>patch({refund_rule:event.target.value as LoyaltyPolicy['refund_rule']})}>
          <option value="proportional">按實際退款重新計算</option><option value="keep">保留已發的點數及紅利</option>
        </select></label>
        {([['points_per_twd','每消費 NT$1 累積的積分'],['rewards_per_twd','每消費 NT$1 累積的紅利'],['twd_per_reward','每點紅利折抵的新台幣金額']] as const).map(([key,label])=>
          <label key={key}>{label}<input className={input} required type="number" min="0" max="100" step="0.0001"
            value={draft[key]} onChange={event=>patch({[key]:event.target.value})} /></label>)}
        {([['referrer_rewards','推薦人獲得的紅利'],['new_member_rewards','新會員首單折抵的紅利']] as const).map(([key,label])=>
          <label key={key}>{label}<input className={input} required type="number" min="0" max="1000000" step="1"
            value={draft[key]} onChange={event=>patch({[key]:Number(event.target.value)})} /></label>)}
      </div>
      <fieldset className="space-y-2">
        <legend className="font-semibold">會員等級門檻</legend>
        {draft.levels.map((level,index)=><div key={index} className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
          <label>等級名稱<input className={input} required maxLength={40} value={level.label}
            onChange={event=>patch({levels:draft.levels.map((row,i)=>i===index?{...row,label:event.target.value}:row)})}/></label>
          <label>最低積分<input className={input} required type="number" min="1" max="2147483647" value={level.minimum_points}
            onChange={event=>patch({levels:draft.levels.map((row,i)=>i===index?{...row,minimum_points:Number(event.target.value)}:row)})}/></label>
          <button type="button" className={button} onClick={()=>patch({levels:draft.levels.filter((_,i)=>i!==index)})}>移除</button>
        </div>)}
        <button type="button" className={button} disabled={draft.levels.length>=10}
          onClick={()=>patch({levels:[...draft.levels,{label:'',minimum_points:1}]})}>新增等級</button>
      </fieldset>
      <button type="submit" className="min-h-11 rounded-lg bg-violet-600 px-4 font-semibold text-white">儲存會員制度</button>
    </fieldset>
    {message && <p role="status" className="text-emerald-700 dark:text-emerald-300">{message}</p>}
    {error && <p role="alert" className="text-red-700 dark:text-red-300">{error} <button type="button" className={button} onClick={async()=>{
      const fresh = await reload()
      if (fresh) { setDraft(fresh); setError('') }
    }}>重新載入設定</button></p>}
  </form>
}
