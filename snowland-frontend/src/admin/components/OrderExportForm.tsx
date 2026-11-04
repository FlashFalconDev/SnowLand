import { useState } from 'react'
import { exportOrders } from '../api/orders'

export default function OrderExportForm({ search, status, paymentStatus }: {
  search: string; status: string; paymentStatus: string
}) {
  const [basis, setBasis] = useState<'created' | 'lesson'>('created')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [sort, setSort] = useState<'asc' | 'desc'>('asc')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const fieldClass = 'block min-h-11 rounded-lg border border-gray-300 bg-white px-2 dark:border-gray-600 dark:bg-gray-800'

  return <form className="mt-4 border-t border-gray-200 pt-4 text-sm dark:border-gray-700 dark:text-gray-100"
    onSubmit={async event => {
      event.preventDefault()
      if (busy) return
      setBusy(true)
      setError('')
      try {
        const file = await exportOrders({ date_basis: basis, start, end, sort, search, status, payment_status: paymentStatus })
        const url = URL.createObjectURL(file)
        const link = document.createElement('a')
        link.href = url
        link.download = `SnowLand-orders-${start}-${end}.csv`
        link.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      } catch (failure) {
        const data = (failure as { response?: { data?: unknown } }).response?.data
        const response = data instanceof Blob ? await data.text().then(value => JSON.parse(value)).catch(() => null) : data
        setError(typeof response?.msg === 'string' ? response.msg : '訂單匯出失敗，請再試一次。')
      } finally {
        setBusy(false)
      }
    }}>
    <div className="flex flex-wrap items-end gap-3">
      <label>匯出依據<select className={fieldClass} value={basis} onChange={event => setBasis(event.target.value === 'lesson' ? 'lesson' : 'created')}><option value="created">下單日期</option><option value="lesson">上課日期</option></select></label>
      <label>開始日期<input className={fieldClass} required type="date" value={start} max={end || undefined} onChange={event => setStart(event.target.value)} /></label>
      <label>結束日期<input className={fieldClass} required type="date" value={end} min={start || undefined} onChange={event => setEnd(event.target.value)} /></label>
      <label>匯出排序<select className={fieldClass} value={sort} onChange={event => setSort(event.target.value === 'desc' ? 'desc' : 'asc')}><option value="asc">早到晚</option><option value="desc">晚到早</option></select></label>
      <button type="submit" disabled={busy || !start || !end} className="min-h-11 rounded-lg bg-violet-700 px-4 font-medium text-white disabled:opacity-50">{busy ? '匯出中…' : '匯出訂單 CSV'}</button>
    </div>
    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">每堂課列一筆，含開始及結束時間。依下單日期匯出時，也會保留尚未排課的訂單。</p>
    {error && <p role="alert" className="mt-2 text-red-600 dark:text-red-300">{error}</p>}
  </form>
}
