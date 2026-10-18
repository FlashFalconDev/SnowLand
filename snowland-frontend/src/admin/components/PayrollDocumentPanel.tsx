import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { generatePayrollDocument, uploadPayrollSignature, type PayrollStatement } from '../api/operations'
import { payrollCalculation, payrollDescription } from '@/utils/payrollLineText'

export default function PayrollDocumentPanel({statement,coachView=false}:{statement:PayrollStatement;coachView?:boolean}) {
  const qc = useQueryClient(); const input = useRef<HTMLInputElement>(null)
  const [file,setFile] = useState<File|null>(null); const [preview,setPreview] = useState(''); const [name,setName] = useState('')
  const [accepted,setAccepted] = useState(false); const [error,setError] = useState(''); const [progress,setProgress] = useState(0)
  useEffect(()=>{if(!file){setPreview('');return}const url=URL.createObjectURL(file);setPreview(url);return()=>URL.revokeObjectURL(url)},[file])
  const mutation = useMutation({mutationFn:()=>coachView&&file?uploadPayrollSignature(statement.id,file,name.trim(),statement.document_digest,setProgress):generatePayrollDocument(statement.id),
    onSuccess:async()=>{setError('');setFile(null);setAccepted(false);await qc.invalidateQueries({queryKey:['admin','payroll']});await qc.invalidateQueries({queryKey:['coach','payroll']})},
    onError:(e:any)=>setError(e?.response?.data?.msg||'操作未完成，請重新載入核對結果後再試')})
  if(!['confirmed','paid'].includes(statement.status))return null
  const doc=statement.document_snapshot
  return <section className="my-4 rounded-lg border border-gray-200 p-4 text-sm dark:border-gray-700"><h3 className="font-semibold">報酬單與簽名</h3>
    {!statement.document_digest?<><p className="mt-2 text-gray-500 dark:text-gray-400">尚未產生報酬單。請由總部確認並啟用文件內容後，再產生這張文件。</p>{!coachView&&<button disabled={mutation.isPending} onClick={()=>mutation.mutate()} className="mt-3 min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-white disabled:opacity-40">{mutation.isPending?'產生中…':'產生報酬單'}</button>}</>:<>
      <details className="mt-3 rounded-lg border border-gray-200 p-3 dark:border-gray-600"><summary className="cursor-pointer font-semibold">查看 {doc.title}</summary><article className="mt-3 space-y-3">
        <h4 className="font-semibold">{doc.title}</h4><p>{doc.coach_name} · {doc.campus_name} · {doc.period_start}～{doc.period_end}</p>
        <p className="whitespace-pre-wrap break-words">{doc.body}</p><div>{doc.lines?.map((line,index)=><div key={index} className="break-words border-t border-gray-200 py-2 dark:border-gray-600"><p>{payrollDescription(line.description)}</p><p>{payrollCalculation(line,doc.currency||'TWD')}</p></div>)}</div>
        <p className="font-semibold">應付合計 {doc.currency} {doc.total_amount?.toLocaleString()}</p><p className="text-xs text-gray-500 dark:text-gray-400">此為產生時保存的內容，後台範本變更不影響本文件。文件簽署與發款是不同流程。</p>
      </article></details>
      {statement.signed_at?<div className="mt-3"><p className="font-semibold">已簽署：{statement.signer_name} · {new Date(statement.signed_at).toLocaleString('zh-TW')}</p><img src={statement.signature_file_url} alt="已保存的本人簽名" className="mt-2 max-h-40 max-w-full rounded-lg border border-gray-300 bg-white object-contain" onError={()=>setError('簽名圖片載入失敗，請重新載入確認權限')} /><p className="mt-2 text-xs text-gray-500 dark:text-gray-400">簽名及原始文件已保留，不能直接覆蓋。</p></div>:coachView&&<div className="mt-3 space-y-3">
        <p>請先展開上方文件，核對後選擇本人的簽名圖片。PNG／JPEG／WebP，5 MB以內；上傳後不能自行覆蓋。</p>
        <label className="block">簽署姓名<input aria-label="報酬單簽署姓名" maxLength={100} disabled={mutation.isPending} value={name} onChange={e=>setName(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 bg-white p-2 text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white" /></label>
        <input ref={input} aria-label="選擇報酬單簽名圖片" type="file" accept="image/png,image/jpeg,image/webp" disabled={mutation.isPending} className="block w-full text-sm file:mr-2 file:min-h-11 file:rounded-lg file:border-0 file:bg-violet-100 file:px-3 file:text-violet-800 dark:file:bg-violet-900 dark:file:text-violet-100" onChange={e=>{setError('');setAccepted(false);const selected=e.target.files?.[0];if(!selected)return;if(!['image/png','image/jpeg','image/webp'].includes(selected.type)||selected.size>5*1024*1024){setError('請選擇5 MB以內的PNG、JPEG或WebP圖片');setFile(null);e.target.value='';return}setFile(selected)}} />
        {preview&&<figure><img src={preview} alt="尚未送出的簽名預覽" className="max-h-40 max-w-full rounded-lg bg-white object-contain" /><figcaption className="mt-1 text-xs text-amber-700 dark:text-amber-300">尚未儲存。確認無誤後再送出。</figcaption></figure>}
        <label className="flex items-start gap-2"><input type="checkbox" className="mt-1" checked={accepted} disabled={mutation.isPending} onChange={e=>setAccepted(e.target.checked)} />本人已核對報酬單內容，確認使用這張簽名圖片簽署</label>
        <div className="flex flex-wrap gap-3"><button disabled={!file||!name.trim()||!accepted||mutation.isPending} onClick={()=>mutation.mutate()} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-white disabled:opacity-40">{mutation.isPending?`上傳中 ${progress}%…`:'確認並上傳簽名'}</button>{file&&<button disabled={mutation.isPending} onClick={()=>{setFile(null);setAccepted(false);if(input.current)input.current.value=''}} className="min-h-11 rounded-lg border border-gray-300 px-3 dark:border-gray-600">取消選圖</button>}</div>
      </div>}
    </>}
    {error&&<p role="alert" className="mt-3 break-words text-red-600 dark:text-red-300">{error}</p>}
  </section>
}
