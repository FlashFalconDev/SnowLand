import { useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { currentClientCode } from '@/utils/tenant'
import adminApi from '../api/axios'

type Detail<T> = { data: T }
type Person = { id: number; name: string }
type Technical = { discipline: string; level: number; scores: { title: string; rating: string }[]; next_steps: string[] }
type History = Person & { records: { date: string; course_name: string; coach_notes: string; technical_assessment: Technical[]; learning_progress: Record<string, string> }[] }
type Asset = { id: number; type: 'photo' | 'video'; url: string; tagged_member_ids: number[] }
type Album = { assets: Asset[]; members: Person[]; photo_limit_bytes: number; video_limit_bytes: number }
type LinkOptions = { profiles: Person[]; current_id: number | null }
const actionClass = 'min-h-11 rounded-lg border border-violet-300 px-3 text-sm font-semibold text-violet-700 disabled:opacity-50 dark:text-violet-200'
const fieldClass = 'min-h-11 max-w-full rounded border border-slate-300 bg-white px-2 dark:border-gray-600 dark:bg-gray-800'

async function get<T>(path: string) {
  return (await adminApi.get(path) as unknown as Detail<T>).data
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

export function CoachCourseAlbum({ bookingId }: { bookingId: number }) {
  const path = `/coach/course-albums/${bookingId}/`
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState('')
  const query = useQuery({ queryKey: ['coach-course-album', currentClientCode(), bookingId], queryFn: () => get<Album>(path) })
  const limit = file && query.data ? (file.type.startsWith('video/') || /\.(mp4|mov|webm)$/i.test(file.name) ? query.data.video_limit_bytes : query.data.photo_limit_bytes) : 0
  const tooLarge = !!file && !!limit && file.size > limit
  const upload = useMutation({
    mutationFn: () => {
      const body = new FormData()
      body.append('file', file!)
      return adminApi.post(path, body, { headers: { 'Content-Type': undefined }, timeout: 180000 })
    },
    onSuccess: async () => { setMessage('已上傳到共用相簿'); setFile(null); if (input.current) input.current.value = ''; await query.refetch() },
  })
  const tag = useMutation({
    mutationFn: (data: { asset_id: number; member_id: number; tagged: boolean }) => adminApi.patch(path, data),
    onSuccess: () => query.refetch(),
  })
  return <section className="mb-4 rounded-lg border border-gray-200 p-4 dark:border-gray-700" aria-label="這堂課的共用相簿">
    <h3 className="font-semibold">這堂課的共用相簿</h3>
    <p className="mt-1 text-sm text-gray-500 dark:text-gray-300">照片或影片只需上傳一次。同堂學員可查看，您也可以幫多人加上標籤。</p>
    {query.isPending && <p role="status" className="mt-2">載入相簿中…</p>}
    {query.isError && <p role="alert" className="mt-2">無法開啟相簿，請確認這堂課已結束且仍由您授課。<button type="button" className={actionClass} onClick={() => void query.refetch()}>重新載入</button></p>}
    {query.data && <>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="min-w-0 text-sm">選擇共用照片或影片<input type="file" ref={input} accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm" disabled={upload.isPending}
          className="mt-1 block min-h-11 max-w-full"
          onChange={event => { setFile(event.target.files?.[0] || null); setMessage(''); upload.reset() }} /></label>
        <button type="button" className={actionClass} disabled={!file || tooLarge || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending ? '上傳中…' : '上傳到共用相簿'}</button>
      </div>
      {tooLarge && <p role="alert" className="text-sm text-red-700 dark:text-red-300">檔案超過 {Math.round(limit / 1048576)} MB。</p>}
      {upload.isError && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{(upload.error as { response?: { data?: { msg?: string } } }).response?.data?.msg || '上傳未完成，請再試一次。'}</p>}
      {message && <p role="status" className="text-sm text-green-700 dark:text-green-300">{message}</p>}
      {tag.isError && <p role="alert" className="text-sm text-red-700 dark:text-red-300">標籤未儲存，請再試一次。</p>}
      {!query.data.assets.length && <p className="mt-3 text-sm text-gray-500 dark:text-gray-300">相簿目前沒有附件。</p>}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {query.data.assets.map(asset => <div key={asset.id} className="min-w-0 rounded border border-gray-200 p-2 dark:border-gray-700">
          {asset.type === 'video' ? <video src={asset.url} controls preload="metadata" className="aspect-video w-full object-contain" /> :
            <img src={asset.url} alt="共用課程照片" loading="lazy" className="aspect-video w-full object-contain" />}
          <div className="mt-2 flex flex-wrap gap-2">{query.data.members.map(person => {
            const tagged = asset.tagged_member_ids.includes(person.id)
            return <button type="button" key={person.id} aria-pressed={tagged} disabled={tag.isPending} className={actionClass}
              onClick={() => tag.mutate({ asset_id: asset.id, member_id: person.id, tagged: !tagged })}>
              {tagged ? '移除標籤：' : '加標籤：'}{person.name}
            </button>
          })}</div>
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
