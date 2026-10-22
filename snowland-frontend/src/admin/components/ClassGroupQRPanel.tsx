import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { saveClassGroupQR } from '../api/orders'
import ClassGroupQRImage from '../../components/ClassGroupQRImage'

export default function ClassGroupQRPanel({ orderId, url }: { orderId: number; url: string }) {
  const qc = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [current, setCurrent] = useState(url)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [progress, setProgress] = useState(0)
  const [removing, setRemoving] = useState(false)
  useEffect(() => { setCurrent(url) }, [orderId, url])
  useEffect(() => { setFile(null); setError(''); setMessage(''); setRemoving(false); if (input.current) input.current.value = '' }, [orderId])
  useEffect(() => {
    if (!file) { setPreview(''); return }
    const local = URL.createObjectURL(file); setPreview(local)
    return () => URL.revokeObjectURL(local)
  }, [file])
  const clear = () => { setFile(null); if (input.current) input.current.value = '' }
  const mutation = useMutation({
    mutationFn: (image: File | null) => saveClassGroupQR(orderId, image, setProgress),
    onMutate: () => { setError(''); setMessage(''); setProgress(0) },
    onSuccess: response => { setCurrent(response.data.line_group_qr_url); setMessage(response.msg); clear(); setRemoving(false); qc.invalidateQueries({ queryKey: ['admin', 'orders'] }) },
    onError: (failure: any) => { setError(failure?.response?.data?.msg || '無法確認 QR 碼儲存結果，請重新載入訂單確認'); qc.invalidateQueries({ queryKey: ['admin', 'orders'] }) },
  })
  return <div className="mt-5 border-t border-gray-200 pt-4 dark:border-gray-700">
    <h4 className="text-sm font-semibold text-gray-900 dark:text-white">群組 QR 碼圖片</h4>
    <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">群組 Email 通知會自動附圖，站內通知也可查看；儲存圖片不會立即寄信。</p>
    <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">可單獨上傳，或搭配上方邀請連結使用。圖片僅供有權管理人員及已付款的綁定會員查看。PNG／JPEG／WebP，5 MB 以內、長寬不超過 4096 像素。</p>
    {current && <ClassGroupQRImage url={current} />}
    {preview && <figure className="mt-3"><img src={preview} alt="待上傳的群組 QR 碼預覽" className="h-48 w-48 max-w-full rounded-lg bg-white p-2 object-contain" /><figcaption className="mt-1 text-xs text-amber-700 dark:text-amber-300">新圖片尚未儲存，請按上傳圖片。</figcaption></figure>}
    <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" aria-label="選擇群組 QR 碼圖片" disabled={mutation.isPending} className="mt-3 block w-full text-sm text-gray-700 file:mr-3 file:min-h-11 file:rounded-lg file:border-0 file:bg-violet-100 file:px-3 file:text-violet-800 dark:text-gray-200 dark:file:bg-violet-900 dark:file:text-violet-100" onChange={event => {
      setMessage(''); setError(''); setRemoving(false)
      const selected = event.target.files?.[0]
      if (!selected) return
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(selected.type) || selected.size > 5 * 1024 * 1024) { setError('請選擇 5 MB 以內的 PNG、JPEG 或 WebP 圖片'); clear(); return }
      setFile(selected)
    }} />
    <div className="mt-3 flex flex-wrap gap-2">
      <button type="button" disabled={!file || mutation.isPending} onClick={() => file && mutation.mutate(file)} className="min-h-11 rounded-lg bg-violet-600 px-4 text-sm font-medium text-white disabled:opacity-50">{mutation.isPending ? `處理中 ${progress}%…` : '上傳圖片'}</button>
      {file && <button type="button" disabled={mutation.isPending} onClick={() => { clear(); setError('') }} className="min-h-11 rounded-lg border border-gray-300 px-3 text-sm text-gray-700 dark:border-gray-600 dark:text-gray-200">取消選圖</button>}
      {current && !removing && <button type="button" disabled={mutation.isPending} onClick={() => { setRemoving(true); setMessage(''); setError('') }} className="min-h-11 rounded-lg border border-red-300 px-3 text-sm text-red-600 dark:border-red-800 dark:text-red-300">移除 QR 碼</button>}
    </div>
    {removing && <div className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200"><p>確定移除這張 QR 碼圖片？上方群組連結不受影響。</p><div className="mt-2 flex gap-2"><button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate(null)} className="min-h-11 rounded-lg bg-red-600 px-3 text-white">確認移除圖片</button><button type="button" disabled={mutation.isPending} onClick={() => setRemoving(false)} className="min-h-11 rounded-lg border border-current px-3">保留圖片</button></div></div>}
    {error && <div role="alert" className="mt-3 text-sm text-red-600 dark:text-red-300">{error}<button type="button" disabled={mutation.isPending} onClick={() => qc.invalidateQueries({ queryKey: ['admin', 'orders'] })} className="ml-2 min-h-11 underline">重新載入訂單</button></div>}
    {message && <p role="status" className="mt-3 text-sm text-green-700 dark:text-green-300">{message}</p>}
  </div>
}
