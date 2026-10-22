import { useQuery } from '@tanstack/react-query'
import { fetchReviewCoachChoices } from '../api/siteContent'

export default function ReviewPlacementFields({ metadata, onChange }: { metadata: Record<string, unknown>; onChange: (metadata: Record<string, unknown>) => void }) {
  const { data: coaches = [], isLoading, error, refetch } = useQuery({ queryKey: ['admin', 'review-coaches'], queryFn: fetchReviewCoachChoices })
  const ids = Array.isArray(metadata.coach_ids) ? metadata.coach_ids.filter((value): value is number => Number.isInteger(value) && typeof value === 'number') : []
  const stale = !isLoading && !error && ids.some(id => !coaches.some(coach => coach.id === id))
  return <fieldset className="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
    <legend className="px-1 text-sm font-semibold text-gray-900 dark:text-white">評價顯示位置與教練歸檔</legend>
    <label className="flex min-h-11 items-center gap-2 text-sm text-gray-800 dark:text-gray-200">
      <input type="checkbox" checked={metadata.show_on_homepage !== false} onChange={event => onChange({ ...metadata, show_on_homepage: event.target.checked })} />在首頁顯示這則評價
    </label>
    <p className="mb-3 text-xs leading-5 text-gray-500 dark:text-gray-400">取消首頁展示，仍可在下方所選教練的介紹頁顯示。內容狀態須為「進行中」，且在有效期間內才會公開。</p>
    <p className="mb-2 text-sm font-medium text-gray-800 dark:text-gray-200">歸檔至教練（可複選，也可不選）</p>
    {isLoading ? <p role="status" className="text-sm text-gray-500 dark:text-gray-400">正在載入教練清單…</p>
      : error ? <div role="alert" className="text-sm text-red-600 dark:text-red-300">教練清單載入失敗，可先儲存文字或首頁展示。<button type="button" className="ml-2 min-h-11 underline" onClick={() => refetch()}>重試教練清單</button></div>
      : !coaches.length ? <p className="text-sm text-gray-500 dark:text-gray-400">尚無教練資料，請先由管理員在教練管理建立。</p>
      : <div className="grid max-h-52 grid-cols-1 gap-1 overflow-y-auto sm:grid-cols-2">{coaches.map(coach => <label key={coach.id} className="flex min-h-11 items-start gap-2 rounded-lg px-2 py-2 text-sm text-gray-800 dark:text-gray-200">
        <input type="checkbox" className="mt-1" checked={ids.includes(coach.id)} onChange={event => onChange({ ...metadata, coach_ids: event.target.checked ? [...ids.filter(id => id !== coach.id), coach.id] : ids.filter(id => id !== coach.id) })} />
        <span className="min-w-0 break-words">{coach.name}{!coach.website_enabled && <span className="block text-xs text-gray-500 dark:text-gray-400">官網已下架，仍可保留歸檔</span>}</span>
      </label>)}</div>}
    {stale && <button type="button" className="mt-2 min-h-11 text-sm text-red-600 underline dark:text-red-300" onClick={() => onChange({ ...metadata, coach_ids: ids.filter(id => coaches.some(coach => coach.id === id)) })}>移除已不存在的教練歸檔</button>}
  </fieldset>
}
