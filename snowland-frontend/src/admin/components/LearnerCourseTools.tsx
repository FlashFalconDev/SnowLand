import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { currentClientCode } from '@/utils/tenant'
import adminApi from '../api/axios'

type Detail<T> = { data: T }
type Person = { id: number; name: string }
type Technical = { discipline: string; level: number; scores: { title: string; rating: string }[]; next_steps: string[] }
type PreCourseSummary = {
  status: 'empty' | 'incomplete' | 'filled'
  status_label: string
  empty_label: string
  items: { key: string; label: string; value: string | null; filled: boolean }[]
}
type History = Person & {
  pre_course_summary?: PreCourseSummary
  records: { date: string; course_name: string; coach_notes: string; technical_assessment: Technical[]; learning_progress: Record<string, string> }[]
}
type Asset = { id: number; type: 'photo' | 'video'; url: string; tagged_member_ids: number[]; can_delete: boolean }
type Album = { assets: Asset[]; members: Person[]; photo_limit_bytes: number; video_limit_bytes: number }
type AlbumUpload = { file: File } & (
  { status: 'ready' | 'uploaded' }
  | { status: 'invalid' | 'failed'; error: string }
  | { status: 'uploading'; progress: number | null }
)
type LinkOptions = { profiles: Person[]; current_id: number | null }
const actionClass = 'min-h-11 rounded-lg border border-violet-300 px-3 text-sm font-semibold text-violet-700 disabled:opacity-50 dark:text-violet-200'
const fieldClass = 'min-h-11 max-w-full rounded border border-slate-300 bg-white px-2 dark:border-gray-600 dark:bg-gray-800'

async function get<T>(path: string) {
  return (await adminApi.get(path) as unknown as Detail<T>).data
}

function LearnerPreCourseSummary({ summary }: { summary: PreCourseSummary }) {
  if (!summary.items.length) return null
  return <section aria-label="課前自評摘要" className="mt-2 rounded-lg bg-slate-50 p-3 dark:bg-slate-800">
    <h4 className="font-semibold">課前自評摘要</h4>
    <dl className="mt-2 grid gap-x-4 gap-y-2 sm:grid-cols-2">
      {summary.items.map(item => <div key={item.key} className="min-w-0 break-words">
        <dt className="text-xs text-slate-600 dark:text-slate-300">{item.label}</dt>
        <dd>{item.filled ? item.value : summary.empty_label}</dd>
      </div>)}
    </dl>
  </section>
}

export function CoachLearnerHistory({ reservationId }: { reservationId: number }) {
  const [open, setOpen] = useState(false)
  const query = useQuery({
    queryKey: ['coach-learner-history', currentClientCode(), reservationId],
    queryFn: () => get<History[]>(`/coach/learner-history/${reservationId}/`),
    enabled: open,
  })
  return <div className="mt-3">
    <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className={actionClass}>{open ? '收起學員歷程' : '查看學員歷程'}</button>
    {open && <section aria-label="學員歷程" className="mt-3 space-y-3 rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-700">
      <p className="text-gray-500 dark:text-gray-300">過往評量僅供本次教學參考（唯讀）。</p>
      {query.isPending && <p role="status">載入學員歷程中…</p>}
      {query.isError && <p role="alert">無法查看學員歷程。<button type="button" className={actionClass} onClick={() => void query.refetch()}>重新載入</button></p>}
      {query.isSuccess && !query.data.length && <p>本堂課尚無學員資料。</p>}
      {query.data?.map(learner => <article key={learner.id} className="rounded border border-gray-200 p-3 dark:border-gray-700">
        <h3 className="font-semibold">{learner.name}</h3>
        {learner.pre_course_summary && <LearnerPreCourseSummary summary={learner.pre_course_summary} />}
        {!learner.records.length && <p className="mt-1 text-gray-500 dark:text-gray-300">尚無已連結的過往評量。</p>}
        {learner.records.map((record, index) => <div key={index} className="mt-2 border-t border-gray-200 pt-2 dark:border-gray-700">
          <p className="font-semibold">{record.date} · {record.course_name}</p>
          {record.technical_assessment.map(item => <div key={item.discipline} className="mt-1">
            <b>{item.discipline === 'ski' ? '雙板' : '單板'} · 等級 {item.level}</b>
            {item.scores.length > 0 && <p>{item.scores.map(score => `${score.title}：${score.rating}`).join('、')}</p>}
            {item.next_steps.length > 0 && <p>下次練習：{item.next_steps.join('、')}</p>}
          </div>)}
          {Object.entries(record.learning_progress || {}).map(([label, value]) => <p key={label}>{label}：{String(value)}</p>)}
          {record.coach_notes && <p className="mt-1 whitespace-pre-wrap break-words">教練建議：{record.coach_notes}</p>}
        </div>)}
      </article>)}
    </section>}
  </div>
}

const albumAccept = '.jpg,.jpeg,.png,.webp,.mp4,.mov,.webm,image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm'

function albumUploadError(file: File, album: Album) {
  const type = file.type.toLowerCase()
  if (/\.(heic|heif)$/i.test(file.name) || /^image\/hei[cf]$/.test(type)) {
    return 'HEIC 格式暫不支援，請先在手機「設定 → 相機 → 格式」改為「最相容」，或轉成 JPG 後再上傳'
  }
  if (!file.size) return '檔案是空的，請重新選擇。'
  const photoName = /\.(jpe?g|png|webp)$/i.test(file.name)
  const video = /\.(mp4|mov|webm)$/i.test(file.name) || (!photoName && /^video\/(mp4|quicktime|webm)$/.test(type))
  if (!video && !photoName && !/^image\/(jpeg|png|webp)$/.test(type)) {
    return '格式不支援。照片支援 JPEG、PNG、WebP，影片支援 MP4、MOV、WebM。'
  }
  const limit = video ? album.video_limit_bytes : album.photo_limit_bytes
  if (file.size > limit) return `${video ? '影片' : '照片'}不可超過 ${(limit / 1048576).toLocaleString('zh-TW')} MB。`
  return ''
}

function albumRequestError(error: unknown, fallback: string) {
  const response = (error as { response?: { status?: number; data?: { msg?: unknown; detail?: unknown } } } | null)?.response
  const message = response?.data?.msg || response?.data?.detail
  if (typeof message === 'string') return message
  return response?.status === 413 ? '檔案超過伺服器可接收的大小。' : fallback
}

export function CoachCourseAlbum({ bookingId, coachView = true }: { bookingId: number; coachView?: boolean }) {
  const client = currentClientCode()
  const path = `${coachView ? '/coach' : ''}/course-albums/${bookingId}/`
  const queryKey = ['course-album', client, path]
  const cache = useQueryClient()
  const query = useQuery({ queryKey, queryFn: () => get<Album>(path) })
  const [uploads, setUploads] = useState<AlbumUpload[]>([])
  const uploadController = useRef<AbortController>()
  useEffect(() => () => uploadController.current?.abort(), [client, path])
  const updateUpload = (index: number, item: AlbumUpload) => setUploads(items =>
    items.map((current, i) => i === index ? item : current))

  const upload = useMutation({
    mutationFn: async (status: 'ready' | 'failed') => {
      const controller = new AbortController()
      uploadController.current = controller
      let uploaded = 0
      for (const [index, item] of uploads.entries()) {
        if (controller.signal.aborted) break
        if (item.status !== status) continue
        const file = item.file
        updateUpload(index, { file, status: 'uploading', progress: null })
        const body = new FormData()
        body.append('file', file)
        try {
          await adminApi.post(path, body, {
            headers: { 'Content-Type': undefined }, timeout: 180000, signal: controller.signal,
            onUploadProgress: ({ loaded, total }) => {
              if (!controller.signal.aborted && total) {
                setUploads(items => items.map((current, i) => i === index && current.status === 'uploading'
                  ? { ...current, progress: Math.min(100, Math.round(100 * loaded / total)) } : current))
              }
            },
          })
          if (controller.signal.aborted) break
          updateUpload(index, { file, status: 'uploaded' })
          uploaded++
        } catch (error) {
          if (controller.signal.aborted) break
          const reason = albumRequestError(error, '上傳未完成，請檢查網路連線後重試。')
          const prefix = `「${file.name}」：`
          updateUpload(index, { file, status: 'failed', error: reason.startsWith(prefix) ? reason.slice(prefix.length) : reason })
        }
      }
      if (!controller.signal.aborted && uploaded > 0) await query.refetch()
    },
  })
  const tag = useMutation({
    mutationFn: (data: { asset_id: number; member_id: number; tagged: boolean }) => adminApi.patch(path, data),
    onSuccess: () => query.refetch(),
  })
  const remove = useMutation({
    mutationFn: (assetId: number) => adminApi.delete(path, { params: { asset_id: assetId } }),
    onSuccess: async (_, assetId) => {
      await cache.cancelQueries({ queryKey })
      cache.setQueryData<Album>(queryKey, album => album && ({
        ...album, assets: album.assets.filter(asset => asset.id !== assetId),
      }))
    },
  })
  const album = query.data
  const busy = upload.isPending || tag.isPending || remove.isPending
  return <section className="mb-4 rounded-lg border border-gray-200 p-4 dark:border-gray-700" aria-label="這堂課的共用相簿">
    <h3 className="font-semibold">這堂課的共用相簿</h3>
    {coachView && <p className="mt-1 text-sm text-gray-500 dark:text-gray-300">照片或影片只需上傳一次。同堂學員可查看，您也可以幫多人加上標籤。</p>}
    {query.isPending && <p role="status" className="mt-2">載入相簿中…</p>}
    {query.isError && <p role="alert" className="mt-2">{coachView ? '無法開啟相簿，請確認這堂課已結束且仍由您授課。' : '無法開啟相簿，請確認您有這堂課的評量權限。'}<button type="button" className={actionClass} onClick={() => void query.refetch()}>重新載入</button></p>}
    {album && <>
      {coachView && <>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="min-w-0 max-w-full text-sm">選擇共用照片或影片<input type="file" multiple accept={albumAccept} disabled={busy}
            className="mt-1 block min-h-11 max-w-full"
            onChange={event => {
              const files = Array.from(event.currentTarget.files ?? [])
              event.currentTarget.value = ''
              setUploads(files.map(file => {
                const error = albumUploadError(file, album)
                return error ? { file, status: 'invalid', error } : { file, status: 'ready' }
              }))
            }} /></label>
          <button type="button" className={actionClass} disabled={busy || !uploads.some(item => item.status === 'ready')} onClick={() => upload.mutate('ready')}>{upload.isPending ? '上傳中…' : '上傳到共用相簿'}</button>
          {uploads.some(item => item.status === 'failed') && <button type="button" className={actionClass} disabled={busy} onClick={() => upload.mutate('failed')}>重試失敗檔案</button>}
        </div>
        {uploads.length > 0 && <ul aria-label="檔案上傳進度" className="mt-2 space-y-2 text-sm">
          {uploads.map((item, index) => <li key={index} className="break-words rounded border border-gray-200 p-2 dark:border-gray-700">
            <p className="font-medium">{item.file.name}</p>
            {item.status === 'ready' && <p>等待上傳</p>}
            {item.status === 'uploading' && <>
              <progress max={100} value={item.progress ?? undefined} aria-label={`${item.file.name} 上傳進度`} className="w-full max-w-xs" />
              <p>{item.progress === 100 ? '傳送完成，正在檢查與儲存' : item.progress === null ? '正在傳送…' : `已傳送 ${item.progress}%`}</p>
            </>}
            {item.status === 'uploaded' && <p role="status" className="text-green-700 dark:text-green-300">已上傳</p>}
            {(item.status === 'invalid' || item.status === 'failed') && <p role="alert" className="text-red-700 dark:text-red-300">{item.error}</p>}
          </li>)}
        </ul>}
      </>}
      {tag.isError && <p role="alert" className="text-sm text-red-700 dark:text-red-300">標籤未儲存，請再試一次。</p>}
      {remove.isError && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{albumRequestError(remove.error, '無法刪除相簿附件，請再試一次。')}</p>}
      {remove.isSuccess && <p role="status" className="text-sm text-green-700 dark:text-green-300">已刪除相簿附件。</p>}
      {!album.assets.length && <p className="mt-3 text-sm text-gray-500 dark:text-gray-300">相簿目前沒有附件。</p>}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {album.assets.map(asset => <div key={asset.id} className="min-w-0 rounded border border-gray-200 p-2 dark:border-gray-700">
          {asset.can_delete && <div className="mb-2 flex justify-end">
            <button type="button" aria-label={asset.type === 'video' ? '刪除相簿影片' : '刪除相簿照片'} disabled={busy}
              className="min-h-11 rounded-lg border border-red-300 px-3 text-sm font-semibold text-red-700 disabled:opacity-50 dark:text-red-300"
              onClick={() => {
                if (window.confirm(`確定刪除這${asset.type === 'video' ? '部影片' : '張照片'}？學員也會從共用相簿看不到此附件。`)) remove.mutate(asset.id)
              }}>{remove.isPending && remove.variables === asset.id ? '刪除中…' : '刪除'}</button>
          </div>}
          {asset.type === 'video' ? <video src={asset.url} controls preload="metadata" className="aspect-video w-full object-contain" /> :
            <img src={asset.url} alt="共用課程照片" loading="lazy" className="aspect-video w-full object-contain" />}
          {coachView && <div className="mt-2 flex flex-wrap gap-2">{album.members.map(person => {
            const tagged = asset.tagged_member_ids.includes(person.id)
            return <button type="button" key={person.id} aria-pressed={tagged} disabled={busy} className={actionClass}
              onClick={() => tag.mutate({ asset_id: asset.id, member_id: person.id, tagged: !tagged })}>
              {tagged ? '移除標籤：' : '加標籤：'}{person.name}
            </button>
          })}</div>}
        </div>)}
      </div>
    </>}
  </section>
}

export function EvaluationLearnerLink({ evaluationId }: { evaluationId: number }) {
  const [open, setOpen] = useState(false)
  const [profile, setProfile] = useState('')
  const [verified, setVerified] = useState(false)
  const path = `/evaluations/${evaluationId}/learner-profile/`
  const query = useQuery({ queryKey: ['evaluation-learner-link', currentClientCode(), evaluationId], queryFn: () => get<LinkOptions>(path), enabled: open })
  const save = useMutation({
    mutationFn: () => adminApi.patch(path, { profile_id: Number(profile), verified }),
    onSuccess: () => { setVerified(false); return query.refetch() },
  })
  const current = query.data?.profiles.find(row => row.id === query.data?.current_id)?.name
  return <div className="mt-3 text-sm">
    <button type="button" aria-expanded={open} className={actionClass} onClick={() => setOpen(!open)}>核對並連結學員歷程</button>
    {open && <div className="mt-2 space-y-2">
      {query.isPending && <p role="status">載入可連結學員中…</p>}
      {query.isError && <p role="alert">無法載入可連結學員。</p>}
      {current && <p>目前連結：{current}</p>}
      {query.isSuccess && !query.data.profiles.length && <p>這個學員或家長尚未建立學員檔案。</p>}
      {!!query.data?.profiles.length && <>
        <label className="block">選擇同一位學員 <select value={profile} onChange={event => { setProfile(event.target.value); setVerified(false); save.reset() }} className={fieldClass}>
          <option value="">請選擇</option>
          {query.data.profiles.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select></label>
        <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={verified} onChange={event => setVerified(event.target.checked)} />已核對為同一位學員</label>
        <button type="button" className={actionClass} disabled={!profile || !verified || save.isPending} onClick={() => save.mutate()}>儲存學員連結</button>
      </>}
      {save.isSuccess && <p role="status">學員歷程連結已儲存。</p>}
      {save.isError && <p role="alert">{(save.error as { response?: { data?: { msg?: string } } }).response?.data?.msg || '連結未儲存，請重試。'}</p>}
    </div>}
  </div>
}
