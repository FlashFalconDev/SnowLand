/**
 * 教練我的所有課程
 * 顯示教練被指派的所有 Reservation，可篩選狀態與日期
 */
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { Calendar, MapPin, User, Loader2, AlertCircle, BookOpen } from 'lucide-react'
import { fetchMyCourses, fetchMyCourseSummary, type CoursePayrollTotals } from '../../api/extras'
import { formatAbilityLevel } from '@/utils/learningProgress'
import { calculateCoachCourseStats, getTaipeiMonthKey } from '@/utils/coachCourseStats'
import { useSiteLink } from '@/hooks/useSiteBasePath'
import { CoachLearnerHistory } from '../../components/LearnerCourseTools'

const PRIMARY = '#8b5cf6'

const STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  created: { label: '待排課', cls: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300' },
  cancelled: { label: '已取消', cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  auto_assigned: { label: '已自動排定', cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  manually_assigned: { label: '人工排定', cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  pending_coach_confirmation: { label: '待我確認', cls: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' },
  manual_assignment_needed: { label: '需人工安排', cls: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' },
  completed: { label: '已完成', cls: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
  form_filled: { label: '已填表單', cls: 'bg-blue-100 text-blue-700' },
}

function getMonthRange(monthKey: string) {
  const month = Number(monthKey.slice(5))
  const endDay = new Date(`${monthKey}-01T00:00:00Z`)
  endDay.setUTCMonth(month, 0)
  return {
    start: `${monthKey}-01`,
    end: `${monthKey}-${String(endDay.getUTCDate()).padStart(2, '0')}`,
  }
}

const hoursFormat = new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 2 })
const amountFormat = new Intl.NumberFormat('zh-TW')

function PayrollSummary({ label, totals }: { label: string; totals: CoursePayrollTotals }) {
  const { photo } = totals.disciplines
  const disciplines = [
    { label: '單板', totals: totals.disciplines.snowboard },
    { label: '雙板', totals: totals.disciplines.ski },
  ]
  if (photo.hours || photo.specified_count) disciplines.push({ label: '攝影', totals: photo })
  return (
    <section aria-label={label} className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{label}</h3>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
        總計薪時數 <strong className="text-lg text-gray-900 dark:text-white">{hoursFormat.format(totals.total_hours)}</strong> 小時
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-3 border-t border-gray-200 pt-3 dark:border-gray-600">
        {disciplines.map(({ label, totals }) => (
          <div key={label}>
            <dt className="text-sm font-medium text-gray-900 dark:text-white">{label}</dt>
            <dd className="mt-1 text-sm text-gray-600 dark:text-gray-300">{hoursFormat.format(totals.hours)} 小時</dd>
            <dd className="mt-1 text-xs text-gray-600 dark:text-gray-300">
              指定費 {totals.specified_count} 堂 · NT$ {amountFormat.format(totals.specified_amount)}
            </dd>
          </div>
        ))}
      </dl>
      {totals.unresolved_specified_count > 0 && (
        <p className="mt-3 text-xs text-amber-700 dark:text-amber-300">
          {totals.unresolved_specified_count} 組的指定費缺少可用的計薪規則，請向行政確認。
        </p>
      )}
    </section>
  )
}

export default function MyCoursesPage() {
  const evaluationsUrl = useSiteLink('/console/my/evaluations')
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedReservationId = Number(searchParams.get('reservation_id') || 0)
  const [statusFilter, setStatusFilter] = useState(() => searchParams.get('status') || '')
  const [dateFrom, setDateFrom] = useState(() => searchParams.get('date_from') || '')
  const [dateTo, setDateTo] = useState(() => searchParams.get('date_to') || '')
  const [statsMonth, setStatsMonth] = useState(() => getTaipeiMonthKey())

  useEffect(() => {
    setStatusFilter(searchParams.get('status') || '')
    setDateFrom(searchParams.get('date_from') || '')
    setDateTo(searchParams.get('date_to') || '')
  }, [searchParams])

  const { data: items = [], isLoading, error } = useQuery({
    queryKey: ['admin', 'my-courses', statusFilter, dateFrom, dateTo],
    queryFn: () => fetchMyCourses({ status: statusFilter || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }),
  })

  const summary = useQuery({
    queryKey: ['admin', 'my-course-monthly-stats', statsMonth],
    queryFn: () => fetchMyCourseSummary(statsMonth),
    enabled: Boolean(statsMonth),
  })
  const scheduledStats = useQuery({
    queryKey: ['admin', 'my-course-scheduled-stats', statsMonth],
    queryFn: async () => {
      const range = getMonthRange(statsMonth)
      const courses = await fetchMyCourses({ date_from: range.start, date_to: range.end })
      return calculateCoachCourseStats(courses, statsMonth)
    },
    enabled: summary.data?.mode === 'scheduled' && Boolean(statsMonth),
  })

  useEffect(() => {
    if (!selectedReservationId || isLoading) return
    document.getElementById(`my-course-${selectedReservationId}`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    })
  }, [selectedReservationId, isLoading, items.length])

  const monthlyStats = scheduledStats.data
  const payrollStats = summary.data?.mode === 'payroll' ? summary.data : null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">我的所有課程</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">您被指派的所有課程紀錄</p>
        <p className="mt-1 text-xs text-yellow-600 dark:text-yellow-400">過往課程都能查看；未來課程依教練設定顯示（一般教練為未來 10 天）。</p>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-white">月份課程統計</h2>
            {payrollStats && (
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">依台北時間的上課日期與目前計薪規則統計，正式金額以薪資單為準。</p>
            )}
          </div>
          <input
            type="month"
            aria-label="統計月份"
            value={statsMonth}
            onChange={(e) => setStatsMonth(e.target.value)}
            className="min-h-11 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 dark:border-gray-600 dark:bg-gray-700 dark:text-white sm:w-auto"
          />
        </div>
        {!statsMonth ? (
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">請選擇統計月份。</p>
        ) : summary.isError || scheduledStats.isError ? (
          <p className="mt-4 text-sm text-red-600 dark:text-red-400" role="alert">月份課程統計載入失敗。</p>
        ) : summary.isLoading || scheduledStats.isLoading ? (
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400" role="status">載入月份課程統計中…</p>
        ) : payrollStats ? (
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <PayrollSummary label="已完課（實績）" totals={payrollStats.actual} />
            <PayrollSummary label="未完課（預估）" totals={payrollStats.estimated} />
          </div>
        ) : monthlyStats && (
          <>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">依課程日期統計時數，同一團體班的同時段只計一次。指定時數為學生指定教練的課程。</p>
            <dl className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[
                { label: '總課程時數', hours: monthlyStats.totalHours },
                { label: '單板時數', hours: monthlyStats.snowboardHours },
                { label: '雙板時數', hours: monthlyStats.skiHours },
                { label: '指定教練時數', hours: monthlyStats.specifiedHours },
              ].map(({ label, hours }) => (
                <div key={label} className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
                  <dt className="text-xs text-gray-500 dark:text-gray-400">{label}</dt>
                  <dd className="mt-1 text-xl font-bold text-gray-900 dark:text-white">{Number.isInteger(hours) ? hours : hours.toFixed(1)} 小時</dd>
                  {label === '總課程時數' && (
                    <dd className="mt-1 text-xs text-gray-500 dark:text-gray-400">{monthlyStats.lessons} 個時段</dd>
                  )}
                </div>
              ))}
            </dl>
          </>
        )}
      </div>

      {/* 篩選 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col gap-3 lg:flex-row">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
          >
            <option value="">全部狀態</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
          <div className="grid w-full grid-cols-1 gap-2 text-sm text-gray-600 dark:text-gray-400 sm:flex sm:w-auto sm:items-center">
            <label className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
              <span>開始日期</span>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white sm:w-36"
              />
            </label>
            <label className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
              <span>結束日期</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white sm:w-36"
              />
            </label>
            {(dateFrom || dateTo || statusFilter) && (
              <button
                onClick={() => { setStatusFilter(''); setDateFrom(''); setDateTo(''); setSearchParams({}) }}
                className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 underline"
              >清除</button>
            )}
          </div>
        </div>
      </div>

      {/* 列表 */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} /></div>
      ) : error ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
          <p className="text-sm text-red-600">載入失敗</p>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-16 text-center">
          <BookOpen size={48} className="mx-auto mb-3 text-gray-300" />
          <p className="text-sm text-gray-500">沒有符合條件的課程</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const s = STATUS_LABEL[item.status] || { label: item.status, cls: 'bg-gray-100 text-gray-700' }
            const isSelected = selectedReservationId === item.id
            return (
              <div
                key={item.id}
                id={`my-course-${item.id}`}
                className={`bg-white dark:bg-gray-800 rounded-xl border p-5 ${isSelected ? 'border-[#8b5cf6] ring-2 ring-[#8b5cf6]/35' : 'border-gray-200 dark:border-gray-700'}`}
              >
                <div className="mb-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <BookOpen size={16} style={{ color: PRIMARY }} />
                      <span className="font-semibold text-gray-900 dark:text-white">{item.course_type}</span>
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${s.cls}`}>{s.label}</span>
                      {item.is_preferred_coach && (
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                          指定教練
                        </span>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600 dark:text-gray-300">
                      <div className="flex items-center gap-1"><MapPin size={12} className="text-gray-400" />{item.resort}</div>
                      <div className="flex items-center gap-1"><User size={12} className="text-gray-400" />{item.user_name} · {item.number_of_people} 人</div>
                      <div className="text-xs text-gray-500">能力：{formatAbilityLevel(item.ability_level)} · 年齡：{item.age_ranges.filter(Boolean).join('、') || '未填'} · 教學語言：{item.language_label || '未填'}</div>
                    </div>
                  </div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
                    <Calendar size={12} />{item.bookings.length} 個時段
                  </div>
                  <div className="space-y-1">
                    {item.bookings.map((b) => (
                      <div key={b.id} className="text-sm text-gray-700 dark:text-gray-300 flex flex-wrap items-center gap-3">
                        <span className="font-medium">{b.date}</span>
                        <span className="text-gray-500">{b.start_time?.substring(0, 5)} - {b.end_time?.substring(0, 5)}</span>
                        {b.is_scheduled && <span className="text-xs text-green-600 dark:text-green-400">✓ 已排定</span>}
                        {b.album_available && <Link className="inline-flex min-h-11 items-center font-semibold text-violet-700 dark:text-violet-200" to={`${evaluationsUrl}?booking=${b.id}`}>開啟課程相簿</Link>}
                      </div>
                    ))}
                  </div>
                </div>
                {['auto_assigned', 'manually_assigned', 'form_filled', 'completed'].includes(item.status) && <CoachLearnerHistory reservationId={item.id} />}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
