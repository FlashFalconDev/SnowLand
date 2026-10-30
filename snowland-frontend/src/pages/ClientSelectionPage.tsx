import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clientCodeFromPath } from '@/utils/tenant'

export default function ClientSelectionPage() {
  const navigate=useNavigate()
  const [code,setCode]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(false)
  const submit=async (event:React.FormEvent)=>{
    event.preventDefault();setError('')
    const value=code.trim()
    if (!value || clientCodeFromPath('/'+value)!==value) {setError('請輸入正確的學校代碼');return}
    setLoading(true)
    try {
      const response=await fetch(`/booking/${encodeURIComponent(value)}/api/client-info/`)
      if(!response.ok) throw new Error('找不到此學校或目前未開放，請確認學校提供的連結')
      const school=await response.json()
      if(school.internal_code!==value) throw new Error('學校資料不一致，請重新載入')
      localStorage.setItem('client_code',value)
      navigate('/'+value)
    } catch(error:any){setError(error.message)} finally{setLoading(false)}
  }
  return <main className="min-h-screen bg-slate-50 flex items-center justify-center p-6"><form onSubmit={submit} className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg"><h1 className="text-2xl font-bold">課程預約系統</h1><p className="mt-3 text-gray-600">請輸入學校提供的代碼，或使用學校的完整網站連結。</p><label className="mt-6 block">學校代碼<input value={code} onChange={event=>setCode(event.target.value)} required maxLength={50} autoComplete="off" className="mt-2 w-full rounded border p-3" /></label>{error&&<p role="alert" className="mt-3 text-red-700">{error}</p>}<button disabled={loading} className="mt-6 min-h-11 w-full rounded bg-violet-600 p-3 font-semibold text-white disabled:opacity-50">{loading?'確認中…':'繼續'}</button></form></main>
}
