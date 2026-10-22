import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import adminApi from '../api/axios'
import { fetchAdminMe } from '../api/auth'

type Connection = {expected_username:string;username:string;enabled:boolean;connected:boolean;missing_configuration:string[];token_expires_at:string|null;last_synced_at:string|null;last_error:string}
const button='min-h-11 rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-600'
const section='rounded-xl border border-gray-200 bg-white p-5 text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100'
const errorText=(error:any)=>error?.response?.data?.msg||error?.response?.data?.detail||'操作未完成，請稍後再試。'
const date=(value:string|null)=>value?new Date(value).toLocaleString('zh-TW'):'尚無紀錄'

export default function SocialSyncPage(){
  const qc=useQueryClient(),me=useQuery({queryKey:['admin','me'],queryFn:fetchAdminMe})
  const hq=!!me.data?.user?.is_superuser||me.data?.user?.role==='hq_admin'
  const query=useQuery({queryKey:['admin','instagram-sync'],enabled:hq,queryFn:async()=>{
    const result=await adminApi.get('/instagram-sync/') as unknown as {data:Connection};return result.data
  }})
  const [username,setUsername]=useState(''),[message,setMessage]=useState(''),[error,setError]=useState('')
  useEffect(()=>{if(query.data)setUsername(query.data.expected_username)},[query.data])
  const action=useMutation({mutationFn:async(kind:'connect'|'sync'|'disconnect')=>{
    const result=await adminApi.post(`/instagram-sync/${kind}/`,kind==='connect'?{expected_username:username}: {},{timeout:kind==='sync'?45000:15000}) as unknown as {msg?:string;data?:{authorization_url?:string}}
    if(kind==='connect'){
      const target=new URL(result.data?.authorization_url||'')
      if(target.origin!=='https://www.instagram.com'||target.pathname!=='/oauth/authorize')throw Error('授權網址不正確')
      window.location.assign(target.href)
    }
    return result
  },onSuccess:async(result)=>{setError('');setMessage(result.msg||'正在前往 Instagram 官方授權頁…');await qc.invalidateQueries({queryKey:['admin','instagram-sync']});await qc.invalidateQueries({queryKey:['admin','site-content']})},onError:failure=>{setMessage('');setError(errorText(failure))}})
  if(me.isLoading)return <p role="status" className="p-5">正在確認管理權限…</p>
  if(me.error)return <p role="alert" className="p-5">管理權限載入失敗。<button className={button} onClick={()=>me.refetch()}>重新載入</button></p>
  if(!hq)return <section className={section}><h1 className="text-xl font-semibold">僅總部管理員可管理官方社群授權</h1><p className="mt-3 text-sm">請由總部管理員操作，不需提供帳號密碼。</p></section>
  const current=query.data
  const result=new URLSearchParams(window.location.search).get('ig')
  const callbackMessages:Record<string,string>={connected:'官方帳號授權已完成，請按「立即同步」檢查貼文。',declined:'您已取消官方授權，原有貼文保留。',invalid_state:'授權流程已逾時或驗證不符，請重新從本頁開始。',failed:'授權未完成，請查看下方原因後重新嘗試。'}
  return <div className="space-y-5"><header><h1 className="text-2xl font-semibold">官方社群同步</h1><p className="mt-2 text-sm text-gray-500 dark:text-gray-400">只讀取官方公開貼文，不發文、不讀取私訊。授權資料只保存在伺服器加密欄位。</p></header>
    {result&&callbackMessages[result]&&<p role="status" className="rounded-lg border border-violet-200 bg-violet-50 p-4 text-sm text-violet-900 dark:border-violet-800 dark:bg-violet-950 dark:text-violet-200">{callbackMessages[result]}</p>}
    <section className={section}><h2 className="text-lg font-semibold">Instagram 貼文</h2>
      {query.isLoading?<p role="status" className="mt-3">載入同步狀態…</p>:query.error?<p role="alert" className="mt-3">同步設定載入失敗，請先確認測試機已執行最新 migration。<button className={button} onClick={()=>query.refetch()}>重試</button></p>:current&&<>
        <p className="mt-3 text-sm">目前狀態：{current.enabled&&current.connected?'已授權，允許同步':'尚未連線或已停用'}{current.username&&`（@${current.username}）`}</p>
        {!!current.missing_configuration.length&&<div role="alert" className="mt-3 rounded-lg bg-amber-50 p-4 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200"><p className="font-semibold">系統應用程式尚未設定完成，暫不能開啟授權。</p><p className="mt-1 break-words">需由開發／部署端設定：{current.missing_configuration.join('、')}。</p><p className="mt-1">官方 IG 網址不是 API 授權；設定完成後，帳號管理者按下方按鈕在 Instagram 官方頁面登入並同意即可。不需在本頁填密碼或 Token。</p></div>}
        <form className="mt-5 space-y-4" onSubmit={event=>{event.preventDefault();setError('');setMessage('');action.mutate('connect')}}>
          <label className="block text-sm">要連線的官方 IG 帳號（不含 @）<input aria-label="官方 IG 帳號" required maxLength={30} pattern="[A-Za-z0-9_.]+" disabled={current.connected||action.isPending} value={username} onChange={event=>setUsername(event.target.value)} className="mt-2 min-h-11 w-full max-w-md rounded-lg border border-gray-300 bg-white px-3 text-gray-900 disabled:opacity-60 dark:border-gray-600 dark:bg-gray-900 dark:text-white"/></label>
          <div className="flex flex-wrap gap-3"><button type="submit" className={button+' border-violet-600 bg-violet-600 text-white'} disabled={action.isPending||!!current.missing_configuration.length||!username.trim()}>{current.connected?'重新授權官方帳號':'授權並啟用貼文同步'}</button><button type="button" className={button} disabled={action.isPending||!current.enabled||!current.connected||!!current.missing_configuration.length} onClick={()=>{setError('');setMessage('');action.mutate('sync')}}>立即同步</button><button type="button" className={button+' text-red-600 dark:text-red-300'} disabled={action.isPending||!current.connected} onClick={()=>{setError('');setMessage('');action.mutate('disconnect')}}>停用並移除本系統授權</button></div>
        </form>
        {action.isPending&&<p role="status" className="mt-3 text-sm">處理中，請勿重複操作…</p>}
        <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-gray-500 dark:text-gray-400">最後成功同步</dt><dd>{date(current.last_synced_at)}</dd></div><div><dt className="text-gray-500 dark:text-gray-400">授權有效期限</dt><dd>{date(current.token_expires_at)}</dd></div></dl>
        {current.last_error&&<p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">{current.last_error}</p>}
        <p className="mt-4 text-xs leading-6 text-gray-500 dark:text-gray-400">同步最近12則貼文，重跑不新增重複卡片；已隱藏的貼文不會自行恢復公開。同步失敗保留既有內容。自動同步需部署端啟用排程，每小時更新；顯示「已授權」不等於已確認正式排程運作。</p>
      </>}
      {message&&<p role="status" className="mt-4 text-sm text-emerald-700 dark:text-emerald-300">{message}</p>}{error&&<p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-300">{error}</p>}
    </section><section className={section}><h2 className="font-semibold">Google 商家評論</h2><p className="mt-2 text-sm text-gray-500 dark:text-gray-400">依目前安排先預留，尚未綁定商家，也不會顯示自動同步已啟用。</p></section>
  </div>
}
