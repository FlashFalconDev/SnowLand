import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchInsuranceReminder, sendInsuranceReminder } from '../api/operations'
import { useNotification } from '../context'

export default function InsuranceReminderDialog({ id, field, onClose }: { id:number; field:'insurance'|'waiver'; onClose:()=>void }) {
  const {data,isLoading,isError,refetch,error:loadError} = useQuery({queryKey:['admin','insurance-reminder',id,field],queryFn:()=>fetchInsuranceReminder(id,field),gcTime:0,retry:false})
  const [pending,setPending]=useState(false), [error,setError]=useState(''), [unconfirmed,setUnconfirmed]=useState(false), [blocked,setBlocked]=useState(false)
  const [key]=useState(()=>crypto.randomUUID()), busy=useRef(false), dialog=useRef<HTMLDivElement>(null), notify=useNotification()
  const message=(e:any)=>String(e?.response?.data?.msg || e?.response?.data?.detail || Object.values(e?.response?.data||{})[0] || '無法確認寄送結果，請保留視窗查詢，不要反覆重寄。')
  useEffect(()=>{const focus=document.activeElement as HTMLElement|null, overflow=document.body.style.overflow;document.body.style.overflow='hidden';dialog.current?.focus();return()=>{document.body.style.overflow=overflow;focus?.focus()}},[])
  const send=async()=>{
    if (!data || busy.current) return
    busy.current=true;setPending(true);setError('')
    try {
      const result=await sendInsuranceReminder(id,{field,recipient_email:data.recipient_email,request_key:key})
      if(result.code===202){setUnconfirmed(true);setError(result.msg);return}
      notify.success(result.msg);onClose()
    } catch(e:any){
      const rejected=[400,401,403,404,409].includes(e?.response?.status)
      setBlocked(rejected);setUnconfirmed(!rejected);setError(message(e))
    }
    finally {busy.current=false;setPending(false)}
  }
  return <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 p-3">
    <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="insurance-reminder-title" tabIndex={-1} className="flex max-h-[calc(100dvh-24px)] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-xl outline-none dark:bg-gray-800" onKeyDown={event=>{
      if(event.key==='Escape'&&!pending){onClose();return}
      if(event.key!=='Tab')return
      const items=Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')),first=items[0],last=items[items.length-1]
      if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.current)){event.preventDefault();last?.focus()}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
    }}>
      <h2 id="insurance-reminder-title" className="bg-violet-600 px-5 py-4 font-semibold text-white">確認課前資料提醒信</h2>
      <div className="space-y-4 overflow-y-auto p-5 text-sm text-gray-800 dark:text-gray-100">
        {isLoading?<p role="status">正在確認待補資料與收件人…</p>:isError||!data?<p role="alert">{message(loadError)}<button className="ml-2 min-h-11 underline" onClick={()=>refetch()}>重試</button></p>:<>
          {data.local_test&&<p className="rounded-lg bg-amber-50 p-3 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200">本機測試：不會對外寄信，只記錄郵件測試結果。</p>}
          <p className="break-all">收件人：<strong>{data.recipient_email}</strong></p>
          <p className="text-xs leading-6 text-gray-500 dark:text-gray-400">優先使用已綁定家長／學員信箱，沒有時使用已填聯絡信箱或訂購人信箱。只提醒補資料，不會標記完成或自動投保。</p>
          <section className="rounded-lg bg-gray-50 p-4 dark:bg-gray-900"><h3 className="font-semibold">{data.subject}</h3><p className="mt-3 whitespace-pre-wrap break-words leading-7">{data.message}</p></section>
        </>}
        {error&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>}
      </div>
      <footer className="flex flex-wrap justify-end gap-2 border-t border-gray-200 p-4 dark:border-gray-700"><button disabled={pending} className="min-h-11 rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 disabled:opacity-40 dark:border-gray-600 dark:text-gray-100" onClick={onClose}>{blocked?'關閉':'取消'}</button>{!blocked&&<button disabled={pending||!data||isError} onClick={send} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{pending?'處理中…':unconfirmed?'查詢寄送結果':'確認寄出提醒信'}</button>}</footer>
    </div>
  </div>
}
