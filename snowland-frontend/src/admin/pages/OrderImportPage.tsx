import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, Download, Upload } from 'lucide-react'
import { currentClientCode } from '@/utils/tenant'
import {
  commitOrderImport, downloadOrderImportTemplate, previewOrderImport, type ImportBatch, type ImportIssue,
} from '../api/orderImport'

const card = 'rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800'
const primary = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-violet-700 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-800 disabled:cursor-not-allowed disabled:opacity-50'
const secondary = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium dark:border-gray-600 disabled:opacity-50'
const money = new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', maximumFractionDigits: 0 })
const filters = [['all', '全部'], ['issues', '有問題'], ['full', '已滿堂']] as const
type Filter = typeof filters[number][0]

function errorMessage(error: unknown, fallback: string) {
  const response = error as { response?: { data?: { detail?: unknown }, status?: number } }
  const detail = response?.response?.data?.detail
  if (response?.response?.status === 403) return '目前沒有匯入權限，或此學校已停用匯入。'
  return typeof detail === 'string' ? detail : fallback
}

function IssueBadge({ issue }: { issue: ImportIssue }) {
  if (issue.level === 'error') return <span className="font-semibold text-red-700 dark:text-red-300">錯誤</span>
  if (issue.code === 'full') return <span className="font-semibold text-amber-800 dark:text-amber-300">已滿堂</span>
  if (issue.code === 'closed') return <span className="font-semibold text-orange-800 dark:text-orange-300">停收</span>
  if (issue.level === 'warning') return <span className="font-semibold text-amber-800 dark:text-amber-300">請核對</span>
  return <span className="text-gray-600 dark:text-gray-300">{issue.code === 'already_imported' ? '已匯入' : '通過'}</span>
}

function PreviewDetails({ batch }: { batch: ImportBatch }) {
  const [filter, setFilter] = useState<Filter>('all')
  const { summary } = batch
  const visible = batch.row_results.filter(issue => filter === 'all'
    || (filter === 'issues' && issue.level !== 'ok') || (filter === 'full' && issue.code === 'full'))
  return <section className={card} aria-labelledby="import-preview">
    <h2 id="import-preview" className="text-lg font-semibold">預覽匯入內容</h2>
    <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {[
        ['訂單', summary.orders], ['堂次', summary.lessons], ['已核對金額', money.format(summary.amount)],
        ['錯誤', summary.errors], ['已滿堂', summary.full], ['停收', summary.closed],
      ].map(([label, value]) => <div key={label} className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
        <dt className="text-sm text-gray-600 dark:text-gray-300">{label}</dt><dd className="mt-1 text-lg font-semibold">{value}</dd>
      </div>)}
    </dl>
    {summary.skipped_examples > 0 && <p className="mt-3 text-sm text-gray-600 dark:text-gray-300">已跳過 {summary.skipped_examples} 列範例。</p>}
    <div className="my-4 flex flex-wrap gap-2" role="group" aria-label="篩選預覽">
      {filters.map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value}
        onClick={() => setFilter(value)} className={filter === value ? primary : secondary}>{label}</button>)}
    </div>
    <div className="max-h-[32rem] overflow-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="w-full min-w-[36rem] text-left text-sm">
        <thead className="sticky top-0 bg-gray-50 dark:bg-gray-900"><tr>
          {['列號', '匯入訂單編號', '狀態', '欄位', '驗證結果'].map(label => <th key={label} scope="col" className="px-3 py-2">{label}</th>)}
        </tr></thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          {visible.map((issue, index) => <tr key={index}>
            <td className="px-3 py-2 align-top">{issue.row_number}</td>
            <td className="max-w-40 break-words px-3 py-2 align-top">{issue.group_key || '—'}</td>
            <td className="whitespace-nowrap px-3 py-2 align-top"><IssueBadge issue={issue} /></td>
            <td className="px-3 py-2 align-top">{issue.columns.join('、') || '—'}</td>
            <td className="px-3 py-2 align-top">{issue.message_zh}</td>
          </tr>)}
          {visible.length === 0 && <tr><td colSpan={5} className="p-4 text-center text-gray-600 dark:text-gray-300">
            {summary.lessons === 0 ? '這份檔案沒有正式資料列。' : '沒有符合篩選條件的資料。'}
          </td></tr>}
        </tbody>
      </table>
    </div>
    {batch.order_results.length > 0 && <details open className="mt-4">
      <summary className="min-h-11 cursor-pointer py-2 font-medium">逐單金額與會員綁定</summary>
      <ul className="max-h-64 space-y-2 overflow-auto text-sm">
        {batch.order_results.map(order => <li key={order.row_number} className="break-words">
          第 {order.row_number} 列 · {order.group_key} · 本單各堂加總＝{order.amount == null ? '待補齊各堂金額' : money.format(order.amount)}
          {order.member && <> · {order.member.message_zh}</>}
        </li>)}
      </ul>
    </details>}
  </section>
}

function CommitResults({ batch, clientCode }: { batch: ImportBatch, clientCode: string }) {
  const { summary } = batch
  const ungrouped = batch.row_results.filter(issue => !issue.group_key && issue.level === 'error')
  return <section className={card} aria-labelledby="import-result">
    <h2 id="import-result" className="flex items-center gap-2 text-lg font-semibold"><CheckCircle2 size={20} />匯入結果</h2>
    <p role="status" className="mt-2">成功 {summary.created ?? 0} 張，跳過 {summary.skipped ?? 0} 張，失敗 {summary.failed ?? 0} 張。</p>
    <ul className="mt-4 space-y-3 text-sm">
      {batch.commit_results?.map(order => <li key={order.row_number} className="break-words rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
        <p className="font-semibold">第 {order.row_number} 列 · {order.group_key} · {
          order.status === 'created' ? '匯入成功' : order.status === 'skipped' ? '已跳過' : '匯入失敗'
        }</p>
        {order.order_id && <Link className="inline-flex min-h-11 items-center font-semibold text-violet-700 underline dark:text-violet-300"
          to={'/' + clientCode + '/console/orders/edit?order_id=' + order.order_id}>{order.order_number}</Link>}
        {order.overbooked && <p className="text-amber-800 dark:text-amber-300">已記錄超賣匯入</p>}
        {order.issues.map((issue, index) => <p key={index}>第 {issue.row_number} 列 · {issue.message_zh}</p>)}
      </li>)}
      {ungrouped.map(issue => <li key={issue.row_number}>第 {issue.row_number} 列 · {issue.message_zh}</li>)}
    </ul>
    <p className="mt-4 text-sm">客人可用表內的聯絡信箱登入<Link className="mx-1 font-medium text-violet-700 underline dark:text-violet-300"
      to={'/' + clientCode + '/membership'}>會員專區</Link>查看訂單並填寫課前資料。可複製會員專區網址給客人。</p>
  </section>
}

export default function OrderImportPage() {
  const [file, setFile] = useState<File | null>(null)
  const [batch, setBatch] = useState<ImportBatch | null>(null)
  const [action, setAction] = useState<'download' | 'preview' | 'commit' | null>(null)
  const [error, setError] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [allowOverbook, setAllowOverbook] = useState(false)
  const [reason, setReason] = useState('')
  const clientCode = currentClientCode()

  function selectFile(next: File | null) {
    setFile(next)
    setBatch(null)
    setConfirmed(false)
    setAllowOverbook(false)
    setReason('')
    setError('')
  }

  async function download() {
    setAction('download')
    setError('')
    try {
      const url = URL.createObjectURL(await downloadOrderImportTemplate())
      const link = document.createElement('a')
      link.href = url
      link.download = 'snowland-order-import-template.xlsx'
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setError(errorMessage(err, '範本下載失敗，請重試。'))
    } finally {
      setAction(null)
    }
  }

  async function preview() {
    if (!file || action) return
    if (!/\.(xlsx|csv)$/i.test(file.name)) {
      setError('請選擇 .xlsx 或 .csv 檔案。')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('檔案不可超過 5 MB。')
      return
    }
    setBatch(null)
    setConfirmed(false)
    setAllowOverbook(false)
    setReason('')
    setAction('preview')
    setError('')
    try {
      setBatch(await previewOrderImport(file))
    } catch (err) {
      setError(errorMessage(err, '預覽失敗，請重試或重新選擇檔案。'))
    } finally {
      setAction(null)
    }
  }

  async function commit() {
    if (!batch || !confirmed || (allowOverbook && !reason.trim()) || action) return
    setAction('commit')
    setError('')
    try {
      setBatch(await commitOrderImport(batch.batch_id, allowOverbook, reason.trim()))
    } catch (err) {
      setError(errorMessage(err, '暫時無法取得匯入結果。請用相同設定重試確認。'))
    } finally {
      setAction(null)
    }
  }

  return <div className="space-y-5 text-gray-900 dark:text-gray-100" aria-busy={action !== null}>
    <h1 className="text-2xl font-bold">匯入已購訂單</h1>
    <section className={card}>
      <h2 className="text-lg font-semibold">填寫並上傳範本</h2>
      <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">一列 = 一堂。相同匯入訂單編號會合成一張訂單。同單首列填聯絡及付款資料，教練欄只填行政已排定的教練。</p>
      <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">本堂已付金額填這堂分到的實收。整單已收款金額和備註填首列，各堂的標籤填堂次備註。舊版範本也能上傳。</p>
      <button type="button" className={secondary + ' mt-3'} disabled={Boolean(action)} onClick={download}>
        <Download size={16} />{action === 'download' ? '下載中…' : '下載 Excel 範本'}
      </button>
      <form className="mt-5 flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); void preview() }}>
        <div>
          <label htmlFor="order-import-file" className="block text-sm font-medium">選擇訂單檔案</label>
          <input id="order-import-file" type="file" accept=".xlsx,.csv" aria-describedby="import-file-limits"
            className="mt-2 block max-w-full text-sm" disabled={Boolean(action)}
            onChange={event => selectFile(event.target.files?.[0] ?? null)} />
          <p id="import-file-limits" className="mt-2 text-sm text-gray-600 dark:text-gray-300">Excel 或 CSV，最多 5 MB、2,000 列。</p>
        </div>
        <button type="submit" className={primary} disabled={!file || Boolean(action) || Boolean(batch)}>
          <Upload size={16} />{action === 'preview' ? '驗證中…' : '上傳並預覽'}
        </button>
        {file && <button type="button" className={secondary} disabled={Boolean(action)} onClick={() => {
          const input = document.getElementById('order-import-file') as HTMLInputElement
          input.value = ''
          selectFile(null)
        }}>重新選擇檔案</button>}
      </form>
    </section>

    {error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{error}</p>}
    {action === 'commit' && <p role="status" className="text-sm">正在重新驗證並逐單匯入，請保留此頁。</p>}
    {batch?.status === 'previewed' && <>
      <PreviewDetails key={batch.batch_id} batch={batch} />
      {batch.summary.committable > 0 && <section className={card}>
        <h2 className="text-lg font-semibold">確認匯入</h2>
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">確認後重新檢查名額與排課，逐單建立並立即佔位。驗證有誤的訂單會跳過。</p>
        <label className="mt-2 flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" checked={confirmed} disabled={Boolean(action)} onChange={event => setConfirmed(event.target.checked)} />
          我已核對預覽
        </label>
        {batch.summary.closed > 0 && <p className="mb-2 text-sm text-orange-800 dark:text-orange-300">停收時段仍可匯入已售訂單。</p>}
        {batch.summary.full > 0 && <div className="rounded-lg bg-amber-50 p-3 dark:bg-amber-950">
          <p className="text-sm text-amber-900 dark:text-amber-100">預設跳過名額不足的訂單。超賣匯入須填寫原因。</p>
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input type="checkbox" checked={allowOverbook} disabled={Boolean(action)}
              onChange={event => setAllowOverbook(event.target.checked)} />允許超賣匯入
          </label>
          {allowOverbook && <label className="block text-sm font-medium">超賣原因（必填）
            <textarea className="mt-2 block w-full rounded-lg border border-gray-300 px-3 py-2 dark:border-gray-600 dark:bg-gray-900"
              value={reason} onChange={event => setReason(event.target.value)} maxLength={1000} disabled={Boolean(action)} rows={2} />
          </label>}
        </div>}
        <button type="button" className={primary + ' mt-4'} onClick={commit}
          disabled={!confirmed || Boolean(action) || (allowOverbook && !reason.trim())}>
          {action === 'commit' ? '匯入中…' : '確認匯入已購訂單'}
        </button>
      </section>}
    </>}
    {batch && batch.status !== 'previewed' && <CommitResults batch={batch} clientCode={clientCode} />}
  </div>
}
