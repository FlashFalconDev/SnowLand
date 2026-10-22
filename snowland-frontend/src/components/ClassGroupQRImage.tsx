import { useEffect, useState } from 'react'

export default function ClassGroupQRImage({ url, appearance = 'auto' }: { url: string; appearance?: 'auto' | 'light' }) {
  const [failed, setFailed] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => { setFailed(false); setRetry(0) }, [url])
  if (!url) return null
  return <figure className="mt-4">
    {failed ? <div role="alert" className={`text-sm ${appearance === 'light' ? 'text-red-700' : 'text-red-600 dark:text-red-300'}`}>群組 QR 碼載入失敗。<button type="button" onClick={() => { setFailed(false); setRetry(value => value + 1) }} className="ml-2 min-h-11 underline">重新載入圖片</button></div>
      : <img src={`${url}${url.includes('?') ? '&' : '?'}retry=${retry}`} alt="上課聯絡群組 QR 碼" width="240" height="240" onError={() => setFailed(true)} className="h-60 w-60 max-w-full rounded-lg border border-gray-200 bg-white p-3 object-contain" />}
    <figcaption className={`mt-2 text-sm leading-6 ${appearance === 'light' ? 'text-[#64748b]' : 'text-gray-500 dark:text-gray-400'}`}>使用通訊軟體掃描，或將圖片存到手機後辨識加入群組。</figcaption>
  </figure>
}
