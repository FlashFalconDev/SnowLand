import { useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Download, History, LifeBuoy, Upload } from 'lucide-react'
import ConfirmModal from '@/components/ui/ConfirmModal'
import { currentClientCode } from '@/utils/tenant'
import adminApi from '../api/axios'
import { prepareFrontendBuild, type BuildEntry } from './frontendBuild'

interface Release {
  id: number; filename: string; size: number; created_at: string; is_current: boolean; is_backup: boolean
}
interface Deployment {
  id: number; status: string; operation: string; message: string; backup_id: number | null; updated_at: string
}
interface ReleaseLibrary {
  versions: Release[]; storage_ready: boolean; publish_ready: boolean; publish_reason: string
  target_label: string; deployment: Deployment | null
}
const endpoint = '/frontend-releases/'
const activeStatuses = new Set(['queued', 'backing_up', 'publishing', 'invalidating', 'cleaning'])
const button = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium disabled:opacity-50 dark:border-gray-600'
const primary = `${button} border-violet-600 bg-violet-600 text-white`
const panel = 'rounded-xl border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-700 dark:bg-gray-800'
function size(bytes: number) { return bytes < 1024 ? `${bytes} B` : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(2)} MB` }
function errorMessage(error: unknown) {
  const detail = isAxiosError(error) ? error.response?.data?.detail : undefined
  if (typeof detail === 'string') return detail
  if (isAxiosError(error) && error.response?.status === 413) return '伺服器拒絕了上傳大小，請檢查發布用的檔案上傳限制。'
  return '操作未完成，請重新整理確認工作狀態，避免重複送出。'
}

export default function FrontendSupportPage() {
  const clientCode = currentClientCode()
  const queryKey = ['admin', clientCode, 'frontend-releases']
  const queryClient = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const [entries, setEntries] = useState<BuildEntry[]>([])
  const [bytes, setBytes] = useState(0)
  const [confirmPublish, setConfirmPublish] = useState(false)
  const [restoreTarget, setRestoreTarget] = useState<Release | null>(null)
  const [error, setError] = useState('')
  const [uploadPercent, setUploadPercent] = useState(0)
  const library = useQuery<ReleaseLibrary>({
    queryKey, queryFn: () => adminApi.get(endpoint) as unknown as Promise<ReleaseLibrary>, retry: false,
    refetchInterval: query => activeStatuses.has(query.state.data?.deployment?.status || '') ? 1500 : false,
  })
  const upload = useMutation({
    mutationFn: () => {
      const body = new FormData()
      for (const entry of entries) { body.append('files', entry.file, entry.file.name); body.append('paths', entry.path) }
      setUploadPercent(0)
      return adminApi.post(endpoint, body, {
        headers: { 'Content-Type': 'multipart/form-data' }, timeout: 600_000,
        onUploadProgress: event => { if (event.total) setUploadPercent(Math.round(event.loaded / event.total * 100)) },
      })
    },
    onSuccess: async () => {
      setEntries([]); setBytes(0)
      if (fileInput.current) fileInput.current.value = ''
      await queryClient.invalidateQueries({ queryKey })
    },
    onError: failure => { setError(errorMessage(failure)); void queryClient.invalidateQueries({ queryKey }) },
  })
  const restore = useMutation({
    mutationFn: (id: number) => adminApi.post(`${endpoint}${id}/restore/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
    onError: failure => { setError(errorMessage(failure)); void queryClient.invalidateQueries({ queryKey }) },
  })
  const job = library.data?.deployment
  const busy = upload.isPending || restore.isPending || activeStatuses.has(job?.status || '')
  const ready = library.isSuccess && library.data.storage_ready && library.data.publish_ready
  const versions = library.data?.versions || []
  const stale = !!job && activeStatuses.has(job.status) && Date.now() - Date.parse(job.updated_at) > 15 * 60_000

  function submit(event: FormEvent) {
    event.preventDefault()
    if (entries.length && ready && !busy) setConfirmPublish(true)
  }

  return (
    <div className="space-y-5 text-gray-900 dark:text-gray-100">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-bold"><LifeBuoy size={24} className="text-violet-500" />支援</h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">直接選擇 SnowLand 建置完成的 dist 資料夾。發布前會備份目前網站，更新檔案並清除快取後才顯示完成。</p>
        {library.data?.target_label && <p className="mt-2 break-words text-sm">發布目標：{library.data.target_label}</p>}
      </header>
      <section className={panel} aria-labelledby="release-upload-title">
        <h2 id="release-upload-title" className="text-base font-semibold">上傳資料夾並發布網站</h2>
        <p id="release-folder-hint" className="mt-1 text-sm text-gray-600 dark:text-gray-300">選擇 dist 資料夾本身，內含 index.html 與所有建置檔案，不必先壓縮。最多 3,000 個檔案、總計 1 GB。</p>
        {library.isSuccess && !library.data.storage_ready && <p role="alert" className="mt-3 text-sm text-amber-700 dark:text-amber-300">版本備份儲存尚未設定，暫時無法發布或還原。</p>}
        {library.isSuccess && !library.data.publish_ready && <p role="alert" className="mt-3 text-sm text-amber-700 dark:text-amber-300">{library.data.publish_reason}</p>}
        <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-3">
          <label className="block min-w-0 max-w-full text-sm font-medium">選擇 dist 資料夾
            <input ref={fileInput} type="file" multiple {...({ webkitdirectory: '', directory: '' } as Record<string, string>)}
              disabled={busy || !ready} aria-describedby="release-folder-hint"
              onChange={event => {
                setError('')
                try { const build = prepareFrontendBuild(Array.from(event.target.files || [])); setEntries(build.entries); setBytes(build.bytes) }
                catch (failure) {
                  setEntries([]); setBytes(0)
                  setError(failure instanceof Error ? failure.message : '無法讀取建置資料夾。')
                  event.target.value = ''
                }
              }} className="mt-1 block min-h-11 max-w-full text-sm file:mr-2 file:min-h-11 file:rounded-lg file:border-0 file:bg-violet-50 file:px-3 file:text-violet-800 disabled:opacity-50" />
          </label>
          <button type="submit" className={primary} disabled={!entries.length || busy || !ready}><Upload size={16} />{upload.isPending ? `檔案上傳中 ${uploadPercent}%` : busy ? '發布工作進行中…' : '上傳 dist 並發布'}</button>
        </form>
        {!!entries.length && <p className="mt-3 text-sm" role="status">已選擇 {entries.length.toLocaleString()} 個檔案，共 {size(bytes)}。</p>}
        {upload.isPending && <progress className="mt-3 w-full" aria-label="檔案上傳進度" value={uploadPercent} max={100} />}
        {error && <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
      </section>
      {job && <section className={panel} aria-labelledby="deployment-title">
        <h2 id="deployment-title" className="font-semibold">最近發布工作</h2>
        <p role={job.status === 'failed' ? 'alert' : 'status'} className={`mt-2 text-sm ${job.status === 'failed' ? 'text-red-700 dark:text-red-300' : ''}`}>{job.message || '等待開始發布'}</p>
        {stale && <p role="alert" className="mt-2 text-sm text-amber-700 dark:text-amber-300">工作已長時間沒有更新，請管理員確認伺服器狀態；這不代表發布完成，請勿重複送出。</p>}
      </section>}
      <section className={panel} aria-labelledby="release-history-title">
        <h2 id="release-history-title" className="flex items-center gap-2 text-base font-semibold"><History size={18} />發布與備份紀錄</h2>
        {library.isPending && <p role="status" className="mt-3 text-sm">載入中…</p>}
        {library.isError && <div className="mt-3 flex flex-wrap items-center gap-3"><p role="alert" className="text-sm">版本紀錄載入失敗。</p><button type="button" className={button} onClick={() => void library.refetch()}>重新載入</button></div>}
        {library.isSuccess && !versions.length && <p className="mt-3 text-sm text-gray-600 dark:text-gray-300">尚無發布或備份紀錄。</p>}
        <ul className="mt-3 divide-y divide-gray-200 dark:divide-gray-700">
          {versions.map(version => <li key={version.id} className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0"><p className="break-words font-medium">{version.filename}{version.is_backup ? '（網站備份）' : ''}</p>
              <p className="text-xs text-gray-600 dark:text-gray-300">{new Date(version.created_at).toLocaleString('zh-TW')} · {size(version.size)}</p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {library.data?.storage_ready && <a className={button} href={`/api/admin/${clientCode}${endpoint}${version.id}/download/`}><Download size={16} />下載版本</a>}
              {version.is_current ? <span className="inline-flex items-center px-2 text-sm font-medium text-violet-700 dark:text-violet-300">已發布版本</span> :
                <button type="button" className={button} disabled={busy || !ready} onClick={() => setRestoreTarget(version)}>還原此版本</button>}
            </div>
          </li>)}
        </ul>
      </section>
      <ConfirmModal isOpen={confirmPublish} title="確認發布 SnowLand 網站" confirmText="備份並發布"
        message={`將以 ${entries.length} 個檔案更新「${library.data?.target_label || ''}」。系統會先備份目前網站，再發布及清除快取。`}
        onCancel={() => setConfirmPublish(false)} onConfirm={() => { setConfirmPublish(false); if (!busy && ready && entries.length) { setError(''); upload.mutate() } }} />
      <ConfirmModal isOpen={!!restoreTarget} title="確認還原網站" confirmText="備份並還原"
        message={`將「${restoreTarget?.filename || ''}」實際還原至「${library.data?.target_label || ''}」。目前網站會先備份。`}
        onCancel={() => setRestoreTarget(null)} onConfirm={() => { const id = restoreTarget?.id; setRestoreTarget(null); if (id && ready && !busy) { setError(''); restore.mutate(id) } }} />
    </div>
  )
}
