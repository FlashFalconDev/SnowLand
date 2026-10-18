import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAdminMe } from '../api/auth'
import { fetchPayrollDocumentSettings, savePayrollDocumentSettings } from '../api/operations'
import { useNotification } from '../context'

export default function PayrollDocumentSettingsPanel() {
  const qc = useQueryClient(); const notify = useNotification()
  const query = useQuery({queryKey:['admin','payroll-document-settings'],queryFn:fetchPayrollDocumentSettings})
  const me = useQuery({queryKey:['admin','payroll-document-me'],queryFn:fetchAdminMe})
  const canManage = me.data?.user?.is_superuser || me.data?.user?.role === 'hq_admin'
  const [form,setForm] = useState({title:'勞務報酬單',body:'',is_active:false})
  const [dirty,setDirty] = useState(false); const [error,setError] = useState('')
  useEffect(()=>{if(query.data && !dirty) setForm(query.data)},[query.data,dirty])
  const mutation = useMutation({mutationFn:()=>savePayrollDocumentSettings(form),onSuccess:data=>{qc.setQueryData(['admin','payroll-document-settings'],data);setDirty(false);setError('');notify.success('報酬單內容已儲存，舊文件不變')},onError:(e:any)=>setError(e?.response?.data?.msg||Object.values(e?.response?.data||{}).flat().filter(v=>typeof v==='string').join('；')||'儲存失敗')})
  const input = 'mt-1 w-full rounded-lg border border-gray-300 bg-white p-2 text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white'
  return <details className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800"><summary className="cursor-pointer font-semibold">報酬單文件設定 · {query.data?.is_active?'已啟用':'未啟用'}</summary>
    <p className="my-3 text-xs text-gray-500 dark:text-gray-400">公司共用內容，只限總部修改。填入已確認的正式內容並啟用後，後續確認薪資會產生文件快照；舊文件不變。不會自動補寫法律條文或推算未設定的稅額。</p>
    {query.isError?<p role="alert" className="text-red-600 dark:text-red-300">文件設定載入失敗，請重新整理。</p>:<form onSubmit={e=>{e.preventDefault();mutation.mutate()}}><fieldset disabled={!canManage||query.isLoading||mutation.isPending} className="space-y-3 text-sm">
      <label className="block">文件標題<input aria-label="報酬單文件標題" required maxLength={100} className={input} value={form.title} onChange={e=>{setDirty(true);setForm({...form,title:e.target.value})}} /></label>
      <label className="block">正式文件內容<textarea aria-label="報酬單正式文件內容" required={form.is_active} rows={6} maxLength={30000} className={input} value={form.body} onChange={e=>{setDirty(true);setForm({...form,body:e.target.value})}} /></label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={form.is_active} onChange={e=>{setDirty(true);setForm({...form,is_active:e.target.checked})}} />啟用報酬單文件</label>
      {canManage&&<button className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 font-semibold text-white disabled:opacity-40">{mutation.isPending?'儲存中…':'儲存文件設定'}</button>}
    </fieldset></form>}
    {!canManage&&<p className="mt-2 text-xs text-gray-500 dark:text-gray-400">此內容由總部維護。</p>}{error&&<p role="alert" className="mt-3 break-words text-sm text-red-600 dark:text-red-300">{error}</p>}
  </details>
}
