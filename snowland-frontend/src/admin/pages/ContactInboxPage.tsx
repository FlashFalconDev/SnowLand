import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAdminMe } from '../api/auth'
import { fetchContactInbox, fetchContactSettings, updateContactMessage, updateContactSettings, retryContactNotification, type ContactMessage, type ContactSettings } from '../api/contactInbox'
import { contactError } from '../../components/site/ContactForm'

const input = 'min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-white'
const button = 'inline-flex min-h-11 items-center justify-center rounded-lg border border-gray-300 px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600'
const primary = button + ' border-violet-600 bg-violet-600 text-white'
const states = {new: '未處理', processing: '處理中', resolved: '已處理'}
const notices = {off: '未啟用通知信', pending: '通知待發送', sent: '通知已發送', failed: '通知發送失敗（留言已保留）'}

function InboxSettings() {
  const query = useQuery({queryKey: ['admin', 'contact-settings'], queryFn: fetchContactSettings})
  const me = useQuery({queryKey: ['admin', 'me'], queryFn: fetchAdminMe})
  const [draft, setDraft] = useState<ContactSettings>({enabled: false, notify_enabled: false, notify_emails: []})
  const [emails, setEmails] = useState('')
  const [error, setError] = useState(''), [saved, setSaved] = useState(false)
  useEffect(() => { if (query.data) {setDraft(query.data); setEmails(query.data.notify_emails.join('\n'))} }, [query.data])
  const mutation = useMutation({mutationFn: updateContactSettings, onSuccess: data => {setDraft(data);setEmails(data.notify_emails.join('\n'));setSaved(true);setError('')}, onError: failure => {setSaved(false);setError(contactError(failure))}})
  const editable = !!me.data?.user?.is_superuser || me.data?.user?.role === 'hq_admin'
  const dirty = () => {setSaved(false);setError('')}
  return <details className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
    <summary className="min-h-11 cursor-pointer font-semibold">表單與通知信設定{!editable && '（僅總部管理員可修改）'}</summary>
    {query.isLoading ? <p role="status">設定載入中…</p> : query.error ? <p role="alert">設定載入失敗。<button className={button} onClick={()=>query.refetch()}>重新載入設定</button></p> : <form onSubmit={event=>{event.preventDefault();setError('');setSaved(false);mutation.mutate({...draft,notify_emails:emails.split(/[\n,;]+/).map(v=>v.trim()).filter(Boolean)})}} className="mt-3 space-y-4">
      <fieldset disabled={!editable || mutation.isPending} className="space-y-3">
        <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={draft.enabled} onChange={e=>{setDraft({...draft,enabled:e.target.checked});dirty()}} />啟用官網聯絡表單</label>
        <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={draft.notify_enabled} onChange={e=>{setDraft({...draft,notify_enabled:e.target.checked});dirty()}} />有新留言時寄通知信</label>
        <label className="block text-sm">通知收件信箱（每行一個，最多10個）<textarea rows={3} value={emails} onChange={e=>{setEmails(e.target.value);dirty()}} className={input+' mt-2'} placeholder="service@example.com" /></label>
        <p className="text-xs leading-5 text-gray-500 dark:text-gray-400">通知信只提示有新留言，不含訪客姓名、聯絡資料或留言內容。寄信失敗不影響後台收件；SMTP須由部署環境設定。</p>
        <button className={primary} type="submit">{mutation.isPending?'儲存中…':'儲存收件設定'}</button>
      </fieldset>
      {error && <p role="alert" className="text-sm text-red-600 dark:text-red-300">{error}</p>}
      {saved && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-300">收件設定已儲存</p>}
    </form>}
  </details>
}

export default function ContactInboxPage() {
  const [page,setPage]=useState(1),[filter,setFilter]=useState(''),[search,setSearch]=useState(''),[keyword,setKeyword]=useState('')
  const [selected,setSelected]=useState<ContactMessage|null>(null)
  const [status,setStatus]=useState('new'),[note,setNote]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState('')
  const detail=useRef<HTMLElement|null>(null),qc=useQueryClient()
  const query=useQuery({queryKey:['admin','contact-inbox',page,filter,keyword],queryFn:()=>fetchContactInbox(page,filter,keyword)})
  const refresh=()=>qc.invalidateQueries({queryKey:['admin','contact-inbox']})
  const save=useMutation({mutationFn:({id,data}:{id:number;data:{status:string;admin_note:string}})=>updateContactMessage(id,data),onSuccess:row=>{setSelected(row);void refresh();setNotice('處理狀態與備註已儲存');setError('')},onError:failure=>{setNotice('');setError(contactError(failure))}})
  const retry=useMutation({mutationFn:retryContactNotification,onSuccess:()=>{void refresh();setNotice('通知已重試，請重新載入確認發送結果');setError('')},onError:failure=>{setNotice('');setError(contactError(failure))}})
  const open=(row:ContactMessage)=>{setSelected(row);setStatus(row.status);setNote(row.admin_note);setError('');setNotice('')}
  useEffect(()=>{if(selected)detail.current?.scrollIntoView({block:'start',behavior:'smooth'})},[selected?.id])
  const busy=save.isPending||retry.isPending
  const dirty=!!selected && (status!==selected.status || note!==selected.admin_note)
  const current=query.data?.list.find(row=>row.id===selected?.id)||selected
  return <div className="space-y-6 text-gray-900 dark:text-white">
    <header><h1 className="text-2xl font-bold">聯絡收件</h1><p className="mt-1 text-sm text-gray-500 dark:text-gray-400">官網留言統一進入總部收件箱，不依目前校區篩選。先查看留言，再標記處理狀態；此處不會直接回信。</p></header>
    <InboxSettings />
    <form className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 sm:flex-row" onSubmit={e=>{e.preventDefault();const next=search.trim();if(page===1&&next===keyword)void query.refetch();setPage(1);setKeyword(next);setSelected(null)}}>
      <input className={input} disabled={busy||dirty} aria-label="搜尋聯絡留言" placeholder="搜尋姓名、Email或主旨" value={search} onChange={e=>setSearch(e.target.value)} />
      <select className={input+' sm:max-w-40'} disabled={busy||dirty} aria-label="處理狀態篩選" value={filter} onChange={e=>{setFilter(e.target.value);setPage(1);setSelected(null)}}><option value="">全部狀態</option>{Object.entries(states).map(([v,label])=><option key={v} value={v}>{label}</option>)}</select>
      <button className={button+' shrink-0'} disabled={busy||dirty}>搜尋</button>
    </form>
    {query.isLoading ? <p role="status">留言載入中…</p> : query.error ? <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-700 dark:bg-red-950/30 dark:text-red-300">留言載入失敗，請確認收件權限或網路。<button className={button+' ml-2'} onClick={()=>query.refetch()}>重新載入留言</button></p> : <>
      <p className="text-sm text-gray-500 dark:text-gray-400">共 {query.data?.total||0} 則留言</p>
      <div className="grid gap-5 lg:grid-cols-2"><div className="space-y-3">
        {!query.data?.list.length && <p className="rounded-xl border border-gray-200 p-6 text-sm dark:border-gray-700">{keyword||filter?'沒有符合條件的留言，請調整搜尋或狀態。':'目前尚無留言。'}</p>}
        {query.data?.list.map(row=><button key={row.id} type="button" disabled={busy||dirty} aria-expanded={selected?.id===row.id} className={'block min-h-11 w-full rounded-xl border bg-white p-4 text-left dark:bg-gray-800 '+(selected?.id===row.id?'border-violet-500':'border-gray-200 dark:border-gray-700')} onClick={()=>open(row)}><span className="flex flex-wrap justify-between gap-2"><span className="break-words font-semibold">#{row.id} {row.subject}</span><span className="text-sm text-violet-600 dark:text-violet-300">{states[row.status]}</span></span><span className="mt-2 block break-all text-sm text-gray-500 dark:text-gray-400">{row.name} · {row.email}</span><time className="mt-2 block text-xs text-gray-500 dark:text-gray-400">{new Date(row.created_at).toLocaleString('zh-TW')}</time></button>)}
      </div>
      {selected && current && <section ref={detail} aria-label="留言詳情" className="min-w-0 scroll-mt-24 rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
        <h2 className="break-words text-lg font-semibold">#{selected.id} {selected.subject}</h2>
        <dl className="my-4 space-y-2 break-all text-sm"><div><dt className="text-gray-500 dark:text-gray-400">姓名</dt><dd>{selected.name}</dd></div><div><dt className="text-gray-500 dark:text-gray-400">Email</dt><dd>{selected.email}</dd></div><div><dt className="text-gray-500 dark:text-gray-400">電話</dt><dd>{selected.phone||'未提供'}</dd></div></dl>
        <p className="whitespace-pre-wrap break-words rounded-lg bg-gray-50 p-4 text-sm leading-7 dark:bg-gray-900">{selected.message}</p>
        <form className="mt-5 space-y-4" onSubmit={e=>{e.preventDefault();setNotice('');setError('');save.mutate({id:selected.id,data:{status,admin_note:note}})}}>
          <label className="block text-sm">處理狀態<select className={input+' mt-2'} value={status} disabled={busy} onChange={e=>{setStatus(e.target.value);setNotice('')}}>{Object.entries(states).map(([v,label])=><option key={v} value={v}>{label}</option>)}</select></label>
          <label className="block text-sm">內部備註（不會寄給訪客）<textarea rows={4} maxLength={10000} className={input+' mt-2'} disabled={busy} value={note} onChange={e=>{setNote(e.target.value);setNotice('')}} /></label>
          {dirty && <p role="status" className="text-sm text-amber-700 dark:text-amber-300">尚未儲存，請先儲存或取消修改，再切換留言。</p>}
          <div className="flex flex-wrap gap-3"><button type="submit" className={primary} disabled={busy}>{save.isPending?'儲存中…':'儲存處理結果'}</button><button type="button" className={button} disabled={busy} onClick={()=>setSelected(null)}>{dirty?'取消未儲存的修改':'關閉詳情'}</button></div>
        </form>
        <p className="mt-4 text-xs text-gray-500 dark:text-gray-400">{notices[current.notification_status]}{current.updated_by_name?' · 最後處理：'+current.updated_by_name:''}</p>
        {current.notification_status==='failed' && <button className={button+' mt-2'} disabled={busy} onClick={()=>{setError('');setNotice('');retry.mutate(selected.id)}}>重試通知信</button>}
        {error && <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-300">{error}</p>}{notice && <p role="status" className="mt-3 text-sm text-emerald-700 dark:text-emerald-300">{notice}</p>}
      </section>}
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3"><button className={button} disabled={page<=1||query.isFetching||busy||dirty} onClick={()=>{setPage(v=>v-1);setSelected(null)}}>上一頁</button><span className="text-sm">第 {page} 頁</span><button className={button} disabled={page*20>=(query.data?.total||0)||query.isFetching||busy||dirty} onClick={()=>{setPage(v=>v+1);setSelected(null)}}>下一頁</button></div>
    </>}
  </div>
}
