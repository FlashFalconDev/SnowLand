import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import AmendmentNoticeStatus from '../../components/AmendmentNoticeStatus'
import { confirmOrderAmendment, fetchOrderAmendmentOptions, previewOrderAmendment, type OrderAmendmentEditorItem, type OrderAmendmentItem, type OrderAmendmentQuote, type OrderAmendmentResult } from '../api/orders'

const field='mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100'
const button='min-h-11 rounded-lg border border-gray-300 px-4 py-2 text-sm disabled:opacity-40 dark:border-gray-600'
const money=(n:number)=>`NT$ ${n.toLocaleString('zh-TW')}`
const levels=['no_exp','level1','level2','level3','level4','level5','level6']
function errorMessage(e:any):string {
  const body=e?.response?.data
  if(body) return Object.entries(body).map(([key,value])=>`${['detail','msg','changes','non_field_errors'].includes(key)?'':`${key}：`}${Array.isArray(value)?value.join('、'):typeof value==='object'?JSON.stringify(value):String(value)}`).join('\n')
  return '無法確認伺服器結果。請保留此視窗，使用相同識別碼重試，不要另開一筆修改。'
}
function initialDraft(item:OrderAmendmentEditorItem):OrderAmendmentItem {
  return {reservation_id:item.reservation_id,number_of_people:item.number_of_people,language:item.language,equipment:item.equipment,
    equipment_assistance_time_slot_id:item.equipment_assistance_time_slot_id,is_preferred_coach:item.is_preferred_coach,preferred_coach_id:item.preferred_coach_id,
    discount_amount:item.discount_amount,ability_level_counts:{...item.ability_level_counts},retained_member_ids:item.members.map(member=>member.id),courses:item.courses.map(course=>({...course}))}
}
export default function OrderAmendmentDialog({orderId,onClose}:{orderId:number;onClose:()=>void}) {
  const {data,isLoading,error:loadError,refetch}=useQuery({queryKey:['admin','order-amendment-options',orderId],queryFn:()=>fetchOrderAmendmentOptions(orderId),retry:false,gcTime:0})
  const [selected,setSelected]=useState<number|null>(null),[draft,setDraft]=useState<OrderAmendmentItem|null>(null)
  const [quote,setQuote]=useState<OrderAmendmentQuote|null>(null),[result,setResult]=useState<OrderAmendmentResult|null>(null)
  const [reason,setReason]=useState(''),[reviewed,setReviewed]=useState(false),[reschedule,setReschedule]=useState(false)
  const [pending,setPending]=useState(false),[error,setError]=useState(''),[uncertain,setUncertain]=useState(false)
  const key=useRef(crypto.randomUUID()),busy=useRef(false),dialog=useRef<HTMLDivElement>(null),qc=useQueryClient()
  const item=data?.items.find(row=>row.reservation_id===selected)
  useEffect(()=>{const focus=document.activeElement as HTMLElement|null,overflow=document.body.style.overflow;document.body.style.overflow='hidden';dialog.current?.focus();return()=>{document.body.style.overflow=overflow;focus?.focus()}},[])
  useEffect(()=>{if(result)dialog.current?.focus()},[result])
  const choose=(id:number)=>{const row=data?.items.find(value=>value.reservation_id===id);if(!row)return;setSelected(id);setDraft(initialDraft(row));setQuote(null);setReviewed(false);setError('');key.current=crypto.randomUUID()}
  const edit=(patch:Partial<OrderAmendmentItem>)=>{setDraft(value=>value?{...value,...patch}:value);setQuote(null);setReviewed(false);setError('');key.current=crypto.randomUUID()}
  const preview=async()=>{
    if(!draft||busy.current)return
    const counts=Object.values(draft.ability_level_counts||{}).reduce((a,b)=>a+b,0)
    if(counts!==draft.number_of_people){setError('各程度人數加總必須等於新的人數。');return}
    if((draft.retained_member_ids?.length||0)>(draft.number_of_people||0)){setError('請取消勾選退出學員，保留人數不能超過新的人數。');return}
    busy.current=true;setPending(true);setError('')
    try{setQuote(await previewOrderAmendment(orderId,[draft]));setReviewed(false)}catch(e){setError(errorMessage(e))}finally{busy.current=false;setPending(false)}
  }
  const confirm=async()=>{
    if(!draft||!quote||!reviewed||!reason.trim()||busy.current)return
    busy.current=true;setPending(true);setError('')
    try{
      const saved=await confirmOrderAmendment(orderId,{changes:[draft],quote_token:quote.quote_token,request_key:key.current,reason:reason.trim(),confirmed:true,reschedule})
      setResult(saved);setUncertain(false);qc.invalidateQueries({queryKey:['admin','orders']})
      qc.invalidateQueries({queryKey:['admin','bookings']})
      qc.invalidateQueries({queryKey:['admin','group-candidates']})
    }catch(e:any){setError(errorMessage(e));if(e?.response?.status&&e.response.status<500){setUncertain(false);setQuote(null);setReviewed(false);key.current=crypto.randomUUID()}else setUncertain(true)}finally{busy.current=false;setPending(false)}
  }
  return <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-2 sm:p-4">
    <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="amendment-title" tabIndex={-1} className="flex max-h-[calc(100dvh-16px)] w-full max-w-3xl flex-col overflow-hidden rounded-xl bg-white text-gray-800 shadow-xl outline-none dark:bg-gray-800 dark:text-gray-100" onKeyDown={event=>{
      if(event.key==='Escape'&&!pending&&!uncertain){onClose();return}
      if(event.key!=='Tab')return
      const elements=Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')).filter(element=>element.getClientRects().length>0)
      const first=elements[0],last=elements[elements.length-1]
      if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.current)){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
    }}>
      <header className="border-b border-gray-200 px-5 py-4 dark:border-gray-700"><h2 id="amendment-title" className="text-lg font-semibold">修改課程與核對差額</h2><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">先選課程 → 調整內容 → 預覽差額 → 確認保存。原付款與修改紀錄都會保留。</p></header>
      <div className="space-y-5 overflow-y-auto p-4 sm:p-5">
        {isLoading?<p role="status">正在讀取原訂單與可用設定…</p>:loadError?<div role="alert">{errorMessage(loadError)}<button onClick={()=>refetch()} className={`${button} ml-2`}>重新載入</button></div>:result?<section role="status" className="space-y-3 rounded-lg bg-green-50 p-4 text-green-900 dark:bg-green-950 dark:text-green-100"><h3 className="font-semibold">已保存第 {result.version} 版</h3><p>新訂單金額：{money(result.new_total)}</p><p>{result.balance_amount>0?`待補款 ${money(result.balance_amount)}`:result.balance_amount<0?`待退款 ${money(-result.balance_amount)}`:'沒有待收退差額'}</p><p className="text-sm">{result.notice}</p><AmendmentNoticeStatus receipt={result.notification}/><p className="text-sm">會員可在訂單詳情回報差額，行政請至「差額回報與核對」處理。這裡不會自動扣款或退款。</p></section>:<>
          <label className="block text-sm font-medium">要修改哪一組課程？<select className={field} value={selected||''} disabled={pending||uncertain||!data?.items.some(row=>!row.blocked_reason)} onChange={event=>choose(Number(event.target.value))}><option value="">請選擇課程</option>{data?.items.map(row=><option key={row.reservation_id} value={row.reservation_id} disabled={!!row.blocked_reason}>{row.resort}／{row.course_type} · {row.number_of_people}人{row.blocked_reason?`（${row.blocked_reason}）`:''}</option>)}</select></label>
          {Boolean(data?.items.length)&&data?.items.every(row=>row.blocked_reason)&&<p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-100">目前沒有可直接修改的課程：{Array.from(new Set(data.items.map(row=>row.blocked_reason))).join('；')}。原訂單與歷史紀錄會保留。</p>}
          {draft&&item&&<fieldset disabled={pending||uncertain} className="min-w-0 space-y-5 disabled:opacity-60">
            <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm">新的人數<input className={field} type="number" min="1" step="1" value={draft.number_of_people} onChange={event=>edit({number_of_people:Number(event.target.value)})}/></label><label className="text-sm">上課語言<select className={field} value={draft.language} onChange={event=>edit({language:event.target.value as OrderAmendmentItem['language']})}><option value="zh">中文</option><option value="en">英文</option><option value="yue">粵語</option></select></label></div>
            <section className="rounded-lg border border-gray-200 p-3 dark:border-gray-600"><h3 className="text-sm font-semibold">核對學員程度人數</h3><div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">{levels.map((level,index)=><label key={level} className="text-xs">等級 {index}<input className={field} type="number" min="0" step="1" value={draft.ability_level_counts?.[level]||0} onChange={event=>edit({ability_level_counts:{...draft.ability_level_counts,[level]:Number(event.target.value)}})}/></label>)}</div></section>
            <section className="rounded-lg border border-gray-200 p-3 dark:border-gray-600"><h3 className="text-sm font-semibold">保留哪些原學員？</h3><p className="mt-1 text-xs leading-6 text-gray-500 dark:text-gray-400">取消勾選的人會退出本課程，舊資料與簽署仍留底。增加人數會建立空白學員欄位，請稍後補資料，不會猜測姓名或代簽。</p>{item.members.map(member=><label key={member.id} className="mt-2 flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={draft.retained_member_ids?.includes(member.id)||false} onChange={event=>edit({retained_member_ids:event.target.checked?[...(draft.retained_member_ids||[]),member.id]:(draft.retained_member_ids||[]).filter(id=>id!==member.id)})}/>{member.name}</label>)}</section>
            {draft.courses.map((course,index)=><section key={course.booking_id} className="space-y-3 rounded-lg bg-gray-50 p-3 dark:bg-gray-900"><h3 className="text-sm font-semibold">第 {index+1} 堂</h3><label className="block text-sm">課程模板<select className={field} value={course.template_id||''} onChange={event=>edit({courses:draft.courses.map((value,i)=>i===index?{...value,template_id:Number(event.target.value)}:value)})}><option value="">請核對課程模板</option>{item.templates.map(template=><option key={template.id} value={template.id}>{template.name} · {template.duration_hours}小時{template.is_active?'':'（已停用）'}</option>)}</select></label><div className="grid gap-3 sm:grid-cols-3">{(['date','start_time','end_time'] as const).map((key,i)=><label key={key} className="min-w-0 text-sm">{['日期','開始時間','結束時間'][i]}<input className={`${field} min-w-0 max-w-full`} type={key==='date'?'date':'time'} value={course[key]} onChange={event=>edit({courses:draft.courses.map((value,j)=>j===index?{...value,[key]:event.target.value}:value)})}/></label>)}</div></section>)}
            <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm">裝備服務<select className={field} value={draft.equipment||''} onChange={event=>edit({equipment:(event.target.value||null) as OrderAmendmentItem['equipment']})}><option value="">未選擇</option><option value="ownWithoutAssistance">自備裝備、不需協助</option><option value="rentWithoutyourself">自行租借、不需協助</option><option value="assistDuringCourse">課程時間內協助</option><option value="purchaseAssistanceTime">加購裝備協助</option></select></label>{draft.equipment==='purchaseAssistanceTime'&&<label className="text-sm">裝備協助時段<select className={field} value={draft.equipment_assistance_time_slot_id||''} onChange={event=>edit({equipment_assistance_time_slot_id:Number(event.target.value)||null})}><option value="">請選擇適用時段</option>{item.equipment_slots.map(slot=><option key={slot.id} value={slot.id}>{slot.name}</option>)}</select></label>}<label className="text-sm">人工折抵金額<input className={field} type="number" min="0" step="1" value={draft.discount_amount} onChange={event=>edit({discount_amount:Number(event.target.value)})}/></label></div>
            <label className="block text-sm">客人是否指定教練？<select className={field} value={draft.is_preferred_coach?String(draft.preferred_coach_id||''): 'none'} onChange={event=>edit({is_preferred_coach:event.target.value!=='none',preferred_coach_id:event.target.value==='none'?null:Number(event.target.value)})}><option value="none">不指定（原人工排定教練符合條件時保留）</option>{item.coaches.filter(coach=>coach.customer_selectable||coach.id===item.preferred_coach_id).map(coach=><option key={coach.id} value={coach.id}>{coach.name}{coach.customer_selectable?'':'（原指定，現已隱藏）'}</option>)}</select></label>
            <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={reschedule} onChange={event=>{setReschedule(event.target.checked);setReviewed(false)}}/>沒有保留教練時，嘗試依新條件自動排課</label>
            <label className="block text-sm">修改原因（必填）<textarea className={field} maxLength={1000} value={reason} onChange={event=>{setReason(event.target.value);setReviewed(false)}}/></label>
          </fieldset>}
          {quote&&<section className="space-y-3 rounded-lg border border-violet-300 bg-violet-50 p-4 dark:border-violet-700 dark:bg-violet-950"><h3 className="font-semibold">請核對這次修改</h3><dl className="grid grid-cols-2 gap-2 text-sm"><dt>原訂單金額</dt><dd className="text-right">{money(quote.previous_total)}</dd><dt>新訂單金額</dt><dd className="text-right">{money(quote.new_total)}</dd><dt>本次價差</dt><dd className="text-right font-semibold">{quote.difference_amount>0?'+':''}{money(quote.difference_amount)}</dd></dl><p className="text-xs leading-6">這是本次改價，尚未實際收退。若原單已有未結清差額，保存後會合併計算；未付款訂單直接更新應付總額。</p><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" disabled={pending} checked={reviewed} onChange={event=>setReviewed(event.target.checked)}/>已核對課程、學員、原價、新價及差額</label></section>}
        </>}
        {error&&<p role="alert" className="whitespace-pre-wrap break-words rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>}
      </div>
      <footer className="flex flex-wrap justify-end gap-2 border-t border-gray-200 p-4 dark:border-gray-700"><button className={button} disabled={pending||uncertain} onClick={onClose}>{result?'完成':'取消'}</button>{!result&&<><button className={button} disabled={pending||!draft||uncertain} onClick={preview}>{pending?'處理中…':'預覽差額'}</button><button className={`${button} border-violet-600 bg-violet-600 text-white`} disabled={pending||!quote||!reviewed||!reason.trim()} onClick={confirm}>{uncertain?'以相同識別碼查詢／重試':'確認保存修改'}</button></>}</footer>
    </div>
  </div>
}
