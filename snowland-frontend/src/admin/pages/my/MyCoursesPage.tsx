/**
 * 教練我的所有課程
 * 顯示教練被指派的所有 Reservation，可篩選狀態與日期
 */
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Calendar, MapPin, User, Loader2, AlertCircle, BookOpen } from 'lucide-react'
import { fetchMyCourses } from '../../api/extras'

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

function getMonthKey(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

function getMonthRange(monthKey: string) {
  const [year, month] = monthKey.split('-').map(Number)
  const endDay = new Date(year, month, 0).getDate()
  return {
    start: `${year}-${String(month).padStart(2, '0')}-01`,
    end: `${year}-${String(month).padStart(2, '0')}-${String(endDay).padStart(2, '0')}`,
  }
}

function parseTimeMinutes(value?: string) {
  if (!value) return 0
  const [hour, minute] = value.split(':').map(Number)
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return 0
  return hour * 60 + minute
}

function getBookingHours(booking: { start_time: string; end_time: string }) {
  const start = parseTimeMinutes(booking.start_time)
  const end = parseTimeMinutes(booking.end_time)
  return Math.max((end - start) / 60, 0)
}

function getCourseKind(courseType: string) {
  const normalized = (courseType || '').toLowerCase()
  if (normalized.includes('snowboard') || normalized.includes('單板')) return 'snowboard'
  if (normalized.includes('ski') || normalized.includes('雙板')) return 'ski'
  return 'other'
}

function formatHours(value: number) {
  return Number.isInteger(value) ? `${value}` : value.toFixed(1)
}

export default function MyCoursesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedReservationId = Number(searchParams.get('reservation_id') || 0)
  const [statusFilter, setStatusFilter] = useState(() => searchParams.get('status') || '')
  const [dateFrom, setDateFrom] = useState(() => searchParams.get('date_from') || '')
  const [dateTo, setDateTo] = useState(() => searchParams.get('date_to') || '')
  const [statsMonth, setStatsMonth] = useState(() => getMonthKey())

  useEffect(() => {
    setStatusFilter(searchParams.get('status') || '')
    setDateFrom(searchParams.get('date_from') || '')
    setDateTo(searchParams.get('date_to') || '')
  }, [searchParams])

  const { data: items = [], isLoading, error } = useQuery({
    queryKey: ['admin', 'my-courses', statusFilter, dateFrom, dateTo],
    queryFn: () => fetchMyCourses({ status: statusFilter || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }),
  })

  const statsRange = useMemo(() => getMonthRange(statsMonth), [statsMonth])
  const { data: statsItems = [] } = useQuery({
    queryKey: ['admin', 'my-course-monthly-stats', statsMonth],
    queryFn: () => fetchMyCourses({ date_from: statsRange.start, date_to: statsRange.end }),
  })

  useEffect(() => {
    if (!selectedReservationId || isLoading) return
    document.getElementById(`my-course-${selectedReservationId}`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    })
  }, [selectedReservationId, isLoading, items.length])

  const monthlyStats = useMemo(() => {
    const stats = {
      totalHours: 0,
      snowboardHours: 0,
      skiHours: 0,
      specifiedHours: 0,
      lessons: 0,
    }
    statsItems.forEach((item) => {
      item.bookings.forEach((booking) => {
        if (!booking.date?.startsWith(statsMonth)) return
        const hours = getBookingHours(booking)
        stats.totalHours += hours
        stats.lessons += 1
        if (item.is_preferred_coach) stats.specifiedHours += hours
        const kind = getCourseKind(item.course_type)
        if (kind === 'snowboard') stats.snowboardHours += hours
        if (kind === 'ski') stats.skiHours += hours
      })
    })
    return stats
  }, [statsItems, statsMonth])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">我的所有課程</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">您被指派的所有課程紀錄</p>
        <p className="mt-1 text-xs text-yellow-600 dark:text-yellow-400">可查看過往與未來課程；日期篩選可縮小列表範圍</p>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-white">月份課程統計</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">依課程日期統計時數，指定為學生指定教練的課程。</p>
          </div>
          <input
            type="month"
            value={statsMonth}
            onChange={(e) => setStatsMonth(e.target.value)}
            className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 dark:border-gray-600 dark:bg-gray-700 dark:text-white sm:w-auto"
          />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
            <div className="text-xs text-gray-500 dark:text-gray-400">總課程時數</div>
            <div className="mt-1 text-xl font-bold text-gray-900 dark:text-white">{formatHours(monthlyStats.totalHours)} 小時</div>
            <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{monthlyStats.lessons} 個時段</div>
          </div>
          <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
            <div className="text-xs text-gray-500 dark:text-gray-400">單板時數</div>
            <div className="mt-1 text-xl font-bold text-gray-900 dark:text-white">{formatHours(monthlyStats.snowboardHours)} 小時</div>
          </div>
          <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
            <div className="text-xs text-gray-500 dark:text-gray-400">雙板時數</div>
            <div className="mt-1 text-xl font-bold text-gray-900 dark:text-white">{formatHours(monthlyStats.skiHours)} 小時</div>
          </div>
          <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
            <div className="text-xs text-gray-500 dark:text-gray-400">指定教練時數</div>
            <div className="mt-1 text-xl font-bold text-gray-900 dark:text-white">{formatHours(monthlyStats.specifiedHours)} 小時</div>
          </div>
        </div>
      </div>

      {/* 篩選 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col sm:flex-row gap-3">
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
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <span>日期：</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white"
            />
            <span>至</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white"
            />
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
                <div className="flex items-start justify-between mb-3">
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
                      <div className="text-xs text-gray-500">能力：{item.ability_level || '—'} · {item.language}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-gray-500">費用</div>
                    <div className="font-bold" style={{ color: PRIMARY }}>NT$ {(item.total_fee || 0).toLocaleString()}</div>
                  </div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
                    <Calendar size={12} />{item.bookings.length} 個時段
                  </div>
                  <div className="space-y-1">
                    {item.bookings.map((b) => (
                      <div key={b.id} className="text-sm text-gray-700 dark:text-gray-300 flex items-center gap-3">
                        <span className="font-medium">{b.date}</span>
                        <span className="text-gray-500">{b.start_time?.substring(0, 5)} - {b.end_time?.substring(0, 5)}</span>
                        {b.is_scheduled && <span className="text-xs text-green-600 dark:text-green-400">✓ 已排定</span>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
