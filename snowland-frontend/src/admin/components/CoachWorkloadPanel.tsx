import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { payrollMonthRange } from '@/utils/payrollDates'
import { formatAbilityLevel } from '@/utils/learningProgress'
import { fetchCoachWorkload, type CoachWorkloadRow } from '../api/schedule'

const formatHours = (seconds: number) => `${(seconds / 3600).toLocaleString('zh-TW', { maximumFractionDigits: 2 })} 小時`
const formatShare = (seconds: number, total: number) => (total ? seconds / total : 0).toLocaleString('zh-TW', { style: 'percent', maximumFractionDigits: 1 })
const inputClass = 'mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 dark:border-gray-600 dark:bg-gray-900'

function CoachSettings({ settings }: { settings: NonNullable<CoachWorkloadRow['settings']> }) {
  return (
    <div className="mt-3 space-y-3 text-sm text-gray-700 dark:text-gray-300">
      <dl className="grid gap-2 sm:grid-cols-2">
        <div><dt className="font-semibold">接課狀態</dt><dd>{settings.availability}</dd></div>
        <div><dt className="font-semibold">自動排課</dt><dd>{settings.auto_assignment_enabled ? '參與' : '停用'}</dd></div>
        <div><dt className="font-semibold">可用校區</dt><dd>{settings.campuses.join('、') || '未設定'}</dd></div>
        <div><dt className="font-semibold">授課語言</dt><dd>{settings.languages.join('、') || '未設定'}</dd></div>
        <div><dt className="font-semibold">客人可指定</dt><dd>{settings.customer_selectable ? '可指定' : '不開放'}</dd></div>
        <div><dt className="font-semibold">教練端課表可見範圍</dt><dd>{settings.schedule_visibility}</dd></div>
      </dl>
      <p>教練分派權重 {settings.assignment_score}（未設定雪場權重時使用）</p>
      <div>
        <h4 className="font-semibold">雪場設定</h4>
        {settings.resorts.length ? <ul className="mt-1 space-y-1">
          {settings.resorts.map(resort => <li key={resort.id}>{resort.name} · 優先順序 {resort.priority} · 分派權重 {resort.weight} · 雪場自動排課{resort.auto_assignment_enabled ? '開啟' : '關閉'}</li>)}
        </ul> : <p>目前範圍內未設定雪場</p>}
      </div>
      <div>
        <h4 className="font-semibold">課程資格</h4>
        {settings.courses.length ? <ul className="mt-1 space-y-1">
          {settings.courses.map(course => <li key={course.id}>{course.name} · 接課順序 {course.order} · 可接程度 {course.ability_levels.map(formatAbilityLevel).join('、') || '未設定'} · 價格等級 {course.price_level}</li>)}
        </ul> : <p>未設定課程資格</p>}
      </div>
    </div>
  )
}

export default function CoachWorkloadPanel() {
  const [month] = useState(payrollMonthRange)
  const [filters, setFilters] = useState({ start: month.first, end: month.last, resort_id: '' })
  const [applied, setApplied] = useState(filters)
  const [formError, setFormError] = useState('')
  const [sort, setSort] = useState('most')
  const report = useQuery({
    queryKey: ['admin', 'coach-workload', applied],
    queryFn: () => fetchCoachWorkload(applied),
  })
  const data = report.data
  const coaches = data?.coaches ?? []
  const ranked = sort === 'least' ? [...coaches].sort((a, b) => a.assigned_seconds - b.assigned_seconds) : coaches
  const total = coaches.reduce((sum, coach) => sum + coach.assigned_seconds, 0)
  const highest = coaches[0]?.assigned_seconds ?? 0
  const lowest = coaches[coaches.length - 1]?.assigned_seconds ?? 0
  const resorts = data?.resorts ?? []

  return (
    <section aria-labelledby="coach-workload-title" className="space-y-4 rounded-xl border border-gray-200 bg-white p-4 text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-white sm:p-5">
      <div>
        <h2 id="coach-workload-title" className="text-lg font-semibold">教練排課統計</h2>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">依上課日期和目前選取的校區統計，起訖日都算入。</p>
      </div>
      <form className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5" onSubmit={event => {
        event.preventDefault()
        if (!filters.start || !filters.end || filters.end < filters.start) {
          setFormError('請填寫有效起訖日期，結束日須在開始日之後或同一天。')
          return
        }
        if (Date.parse(filters.end) - Date.parse(filters.start) >= 366 * 86400000) {
          setFormError('請選擇 366 天內的起訖日期。')
          return
        }
        setFormError('')
        if (filters.start === applied.start && filters.end === applied.end && filters.resort_id === applied.resort_id) {
          void report.refetch()
        } else {
          setApplied(filters)
        }
      }}>
        <label className="text-sm">開始日期<input className={inputClass} type="date" value={filters.start} onChange={event => setFilters({ ...filters, start: event.target.value })} /></label>
        <label className="text-sm">結束日期<input className={inputClass} type="date" value={filters.end} onChange={event => setFilters({ ...filters, end: event.target.value })} /></label>
        <label className="text-sm">統計雪場<select className={inputClass} value={filters.resort_id} onChange={event => setFilters({ ...filters, resort_id: event.target.value })}>
          <option value="">全部雪場</option>
          {resorts.map(resort => <option key={resort.id} value={resort.id}>{resort.display_name}</option>)}
        </select></label>
        <label className="text-sm">時數排序<select className={inputClass} value={sort} onChange={event => setSort(event.target.value)}>
          <option value="most">由多到少</option>
          <option value="least">由少到多</option>
        </select></label>
        <button type="submit" className="min-h-11 self-end rounded-lg bg-violet-700 px-4 text-sm font-semibold text-white hover:bg-violet-800">查詢統計</button>
      </form>
      {formError && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{formError}</p>}
      {report.isFetching && <p role="status" className="text-sm text-gray-600 dark:text-gray-300">正在查詢排課統計…</p>}
      {report.isError && <p role="alert" className="text-sm text-red-700 dark:text-red-300">無法載入排課統計，請確認校區權限或重試。</p>}
      <details className="rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-700">
        <summary className="min-h-8 cursor-pointer font-semibold">時數怎麼算？排課設定怎麼看？</summary>
        <ul className="space-y-2 pb-2 pl-4 text-gray-700 dark:text-gray-300">
          <li>總排課時數包含已排、待教練確認和完課的滑雪課程。指定、待確認、已完課是其中的明細，同一團體班只計一次。統計按課表時段長度計算，供排課比較使用。平均值包含表中零時數的教練。</li>
          <li>新單或 AI 排課會檢查自動排課開關、校區、雪場、語言、可接程度、課程限定名單或最低等級、休假及時段。符合條件後，再依可直接接課、課程接課順序和分派權重挑選。順序和權重數字越小越優先。</li>
          <li>教練拒接後，系統排除已拒接者，依接課狀態、雪場優先順序及分派權重重派。同順位才比較系統已排時數，計算範圍與此報表的自選日期各自獨立。</li>
          <li>客人可指定、教練端課表可見範圍各自控制名單與顯示。有教練名冊權限的使用者可展開個別教練，查看目前設定。</li>
        </ul>
      </details>
      {data && !report.isError && (data.has_visible_dates ? <>
        <p className="text-sm text-gray-600 dark:text-gray-300">統計區間 {data.start} 至 {data.end}</p>
        <dl className="grid grid-cols-2 gap-2 rounded-lg bg-gray-50 p-3 text-sm dark:bg-gray-900 sm:grid-cols-4">
          <div><dt>教練人數</dt><dd className="font-semibold">{coaches.length} 位</dd></div>
          <div><dt>總排課時數</dt><dd className="font-semibold">{formatHours(total)}</dd></div>
          <div><dt>平均排課時數</dt><dd className="font-semibold">{formatHours(coaches.length ? total / coaches.length : 0)}</dd></div>
          <div><dt>最高與最低差距</dt><dd className="font-semibold">{formatHours(highest - lowest)}</dd></div>
        </dl>
        {ranked.length ? <div className="space-y-2" aria-label="教練時數比較">
          {ranked.map(coach => <article key={coach.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="break-words font-semibold">{coach.name || `教練 #${coach.id}`}</h3>
              <p className="text-sm font-semibold tabular-nums">{formatHours(coach.assigned_seconds)} · {coach.lesson_count} 堂 · 占 {formatShare(coach.assigned_seconds, total)}</p>
            </div>
            <div aria-hidden="true" className="mt-2 h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
              <div className="h-full rounded-full bg-violet-600 dark:bg-violet-400" style={{ width: `${highest ? coach.assigned_seconds / highest * 100 : 0}%` }} />
            </div>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">已完課 {formatHours(coach.completed_seconds)} · 待確認 {formatHours(coach.pending_seconds)} · 客人指定 {formatHours(coach.specified_seconds)}{coach.leave_days !== null && ` · 核准休假 ${coach.leave_days} 天`}</p>
            {coach.settings && <details className="mt-2 text-sm">
              <summary className="min-h-8 cursor-pointer font-medium text-violet-700 dark:text-violet-300">查看 {coach.name || `教練 #${coach.id}`} 的排課設定</summary>
              <CoachSettings settings={coach.settings} />
            </details>}
          </article>)}
        </div> : <p className="text-sm text-gray-600 dark:text-gray-300">這個篩選範圍沒有可比較的教練。</p>}
      </> : <p className="text-sm text-gray-600 dark:text-gray-300">選取的區間沒有您可查看的排課日期。</p>)}
    </section>
  )
}
