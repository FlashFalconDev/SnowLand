import { useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Download, History, LifeBuoy, Upload } from 'lucide-react'
import ConfirmModal from '@/components/ui/ConfirmModal'
import { currentClientCode } from '@/utils/tenant'
import adminApi from '../api/axios'

interface Release {
  id: number
  filename: string
  size: number
  created_at: string
  is_current: boolean
}

interface ReleaseLibrary {
  versions: Release[]
  storage_ready: boolean
}

const endpoint = '/frontend-releases/'
const maxArchiveMB = 768
const maxBytes = maxArchiveMB * 1024 * 1024
const button = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium disabled:opacity-50 dark:border-gray-600'
const primary = `${button} border-violet-600 bg-violet-600 text-white`
const panel = 'rounded-xl border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-700 dark:bg-gray-800'

function formatArchiveSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function errorMessage(error: unknown) {
  const detail = isAxiosError(error) ? error.response?.data?.detail : undefined
  if (typeof detail === 'string') return detail
  if (isAxiosError(error) && error.response?.status === 413) return '伺服器拒絕了檔案大小，請縮小 ZIP 後再試。'
  return '操作未完成，請重新整理確認版本狀態後再試。'
}

export default function FrontendSupportPage() {
  const clientCode = currentClientCode()
  const queryKey = ['admin', clientCode, 'frontend-releases']
  const queryClient = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const [archive, setArchive] = useState<File | null>(null)
  const [restoreTarget, setRestoreTarget] = useState<Release | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const library = useQuery({
    queryKey,
    queryFn: () => adminApi.get(endpoint) as unknown as Promise<ReleaseLibrary>,
    retry: false,
  })
  const upload = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData()
      body.append('archive', file)
      return adminApi.post(endpoint, body, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 600_000 })
    },
    onSuccess: async () => {
      setArchive(null)
      if (fileInput.current) fileInput.current.value = ''
      await queryClient.invalidateQueries({ queryKey })
      setMessage('ZIP 已儲存，可在版本紀錄查看。')
    },
    onError: (failure) => setError(errorMessage(failure)),
  })
  const restore = useMutation({
    mutationFn: (id: number) => adminApi.post(`${endpoint}${id}/restore/`),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey })
      setMessage('目前測試版本已切換。')
    },
    onError: (failure) => setError(errorMessage(failure)),
  })
  const busy = upload.isPending || restore.isPending
  const ready = library.isSuccess && library.data.storage_ready
  const versions = library.data?.versions || []
  const current = versions.find((version) => version.is_current)

  function submit(event: FormEvent) {
    event.preventDefault()
    setMessage('')
    if (!archive || busy || !ready) return
    if (!archive.name.toLowerCase().endsWith('.zip') || archive.size > maxBytes) {
      setError(`請選擇 ${maxArchiveMB} MB 以內的 ZIP 檔案。`)
      return
    }
    setError('')
    upload.mutate(archive)
  }

  return (
    <div className="space-y-5 text-gray-900 dark:text-gray-100">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-bold"><LifeBuoy size={24} className="text-violet-500" />支援</h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">管理 FlashFalcon 的前端測試版本。上傳與回復只作用於此版本庫。</p>
      </header>

      <section className={panel} aria-labelledby="release-upload-title">
        <h2 id="release-upload-title" className="text-base font-semibold">上傳前端版本</h2>
        <p id="release-archive-hint" className="mt-1 text-sm text-gray-600 dark:text-gray-300">請將前端建置產物壓成 ZIP，讓 index.html 位於 ZIP 最上層。檔案上限 {maxArchiveMB} MB。</p>
        {library.isSuccess && !ready && <p role="alert" className="mt-3 text-sm text-amber-700 dark:text-amber-300">版本儲存尚未設定，暫時無法上傳或回復。</p>}
        <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-3">
          <label className="block min-w-0 max-w-full text-sm font-medium">
            ZIP 檔案
            <input ref={fileInput} type="file" accept=".zip" aria-describedby="release-archive-hint" disabled={busy || !ready}
              onChange={(event) => { setArchive(event.target.files?.[0] || null); setError(''); setMessage('') }}
              className="mt-1 block min-h-11 max-w-full text-sm file:mr-2 file:min-h-11 file:rounded-lg file:border-0 file:bg-violet-50 file:px-3 file:text-violet-800 disabled:opacity-50" />
          </label>
          <button type="submit" className={primary} disabled={!archive || busy || !ready}><Upload size={16} />{upload.isPending ? '上傳並驗證中…' : '上傳版本'}</button>
        </form>
        {message && <p role="status" className="mt-3 text-sm text-emerald-700 dark:text-emerald-300">{message}</p>}
        {error && <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
      </section>

      <section className={panel} aria-labelledby="release-history-title">
        <h2 id="release-history-title" className="flex items-center gap-2 text-base font-semibold"><History size={18} />版本紀錄</h2>
        {library.isPending && <p role="status" className="mt-3 text-sm">載入中…</p>}
        {library.isError && <div className="mt-3 flex flex-wrap items-center gap-3"><p role="alert" className="text-sm">版本紀錄載入失敗。</p><button type="button" className={button} onClick={() => void library.refetch()}>重新載入</button></div>}
        {library.isSuccess && <>
          <p className="mt-2 break-words text-sm text-gray-600 dark:text-gray-300">目前測試版本：{current?.filename || '尚未選擇'}</p>
          {versions.length === 0 && <p className="mt-3 text-sm text-gray-600 dark:text-gray-300">尚無版本，請先上傳 ZIP。</p>}
          <ul className="mt-3 divide-y divide-gray-200 dark:divide-gray-700">
            {versions.map((version) => (
              <li key={version.id} className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="break-words font-medium">{version.filename}</p>
                  <p className="text-xs text-gray-600 dark:text-gray-300">
                    #{version.id} · {new Date(version.created_at).toLocaleString('zh-TW')} · {formatArchiveSize(version.size)}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {ready && <a className={button} href={`/api/admin/${clientCode}${endpoint}${version.id}/download/`}><Download size={16} />下載 ZIP</a>}
                  {version.is_current ? <span className="inline-flex items-center px-2 text-sm font-medium text-violet-700 dark:text-violet-300">目前版本</span> :
                    <button type="button" className={button} disabled={busy || !ready} onClick={() => setRestoreTarget(version)}>{current ? '回復此版本' : '設為目前版本'}</button>}
                </div>
              </li>
            ))}
          </ul>
        </>}
        {restore.isPending && <p role="status" className="mt-2 text-sm">切換版本中…</p>}
      </section>

      <ConfirmModal isOpen={!!restoreTarget} title="切換目前測試版本" confirmText="確認切換"
        message={`將「${restoreTarget?.filename || ''}」設為目前測試版本。歷史版本會保留。`}
        onCancel={() => setRestoreTarget(null)}
        onConfirm={() => {
          if (!restoreTarget || busy) return
          setError('')
          setMessage('')
          restore.mutate(restoreTarget.id)
          setRestoreTarget(null)
        }} />
    </div>
  )
}
