/**
 * 教練我的月曆
 */
import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, Loader2 } from 'lucide-react'
import { fetchMyCalendar, type MyCalendarBooking } from '../../api/extras'
import { useSiteLink } from '@/hooks/useSiteBasePath'
import { formatAbilityLevel } from '@/utils/learningProgress'

const PRIMARY = '#8b5cf6'
const EQUIPMENT_COLOR = '#d97706'

function getEventColor(eventType?: string) {
  return eventType === 'equipment_assistance' ? EQUIPMENT_COLOR : PRIMARY
}

const LANGUAGE_LABELS: Record<string, string> = {
  zh: '中文',
  en: '英文',
  yue: '粵語',
}

const EQUIPMENT_LABELS: Record<string, string> = {
  rentWithoutyourself: '自行租借不須協助',
  ownWithoutAssistance: '自備裝備不須協助',
  assistDuringCourse: '課程時間內協助',
  purchaseAssistanceTime: '加購協助時間',
}

const getLanguageLabel = (booking: MyCalendarBooking) =>
  booking.language_label || LANGUAGE_LABELS[booking.language || ''] || booking.language || '-'

const getEquipmentLabel = (booking: MyCalendarBooking) =>
  booking.equipment_label || EQUIPMENT_LABELS[booking.equipment || ''] || ''

const getCoachRequestLabel = (booking: MyCalendarBooking) =>
  booking.is_preferred_coach ? '指定教練' : '未指定教練'

export default function MyCalendarPage() {
  const navigate = useNavigate()
  const myCoursesUrl = useSiteLink('/console/my/courses')
  const dayDetailRef = useRef<HTMLDivElement>(null)
  const today = new Date()
  const [currentMonth, setCurrentMonth] = useState(new Date(today.getFullYear(), today.getMonth(), 1))
  const [selectedDate, setSelectedDate] = useState<string | null>(null)

  const year = currentMonth.getFullYear()
  const month = currentMonth.getMonth()
  const monthStart = `${year}-${String(month + 1).padStart(2, '0')}-01`
  const monthEnd = `${year}-${String(month + 1).padStart(2, '0')}-${new Date(year, month + 1, 0).getDate()}`

  const { data: bookings = [], isLoading } = useQuery({
    queryKey: ['admin', 'my-calendar', monthStart, monthEnd],
    queryFn: () => fetchMyCalendar({ start: monthStart, end: monthEnd }),
  })

  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const cells: { date: Date | null; dateStr: string }[] = []
  for (let i = 0; i < firstDay; i++) cells.push({ date: null, dateStr: '' })
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(year, month, d)
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({ date, dateStr })
  }

  const getBookingsForDate = (dateStr: string) => bookings.filter((b) => b.date === dateStr)
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  const selectedBookings = selectedDate ? getBookingsForDate(selectedDate) : []
  const selectDate = (date: string) => {
    setSelectedDate(date)
    if (window.matchMedia('(max-width: 1023px)').matches) {
      requestAnimationFrame(() => dayDetailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }
  const openMyCourse = (booking: MyCalendarBooking) => {
    setSelectedDate(booking.date)
    const courseDate = booking.linked_course_date || booking.date
    const params = new URLSearchParams({
      date_from: courseDate,
      date_to: courseDate,
    })
    if (booking.reservation_id) params.set('reservation_id', String(booking.reservation_id))
    navigate(`${myCoursesUrl}?${params.toString()}`)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">我的月曆</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">您本月的課程行事曆</p>
        <p className="mt-1 text-xs text-yellow-600 dark:text-yellow-400">僅列已回報付款或已付款課程；尚未回報付款的不顯示。可查過往課程；未來依教練設定（一般為10天）。</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900 dark:text-white text-lg">{year} 年 {month + 1} 月</h3>
            <div className="flex items-center gap-2">
              <button onClick={() => { setCurrentMonth(new Date(today.getFullYear(), today.getMonth(), 1)); setSelectedDate(todayStr) }}
                className="min-h-11 px-3 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">今天</button>
              <button aria-label="月曆上一個月" onClick={() => setCurrentMonth(new Date(year, month - 1, 1))} className="min-h-11 min-w-11 p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"><ChevronLeft size={16} /></button>
              <button aria-label="月曆下一個月" onClick={() => setCurrentMonth(new Date(year, month + 1, 1))} className="min-h-11 min-w-11 p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"><ChevronRight size={16} /></button>
            </div>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} /></div>
          ) : (
            <>
              <div className="grid grid-cols-7 gap-px bg-gray-200 dark:bg-gray-700">
                {['日', '一', '二', '三', '四', '五', '六'].map((d) => (
                  <div key={d} className="bg-gray-50 dark:bg-gray-700 px-2 py-2 text-xs font-medium text-gray-600 dark:text-gray-300 text-center">{d}</div>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-px bg-gray-200 dark:bg-gray-700">
                {cells.map((cell, i) => {
                  if (!cell.date) return <div key={i} className="min-h-[68px] bg-gray-50 dark:bg-gray-900 sm:min-h-[100px]" />
                  const dayBookings = getBookingsForDate(cell.dateStr)
                  const isToday = cell.dateStr === todayStr
                  const isSelected = cell.dateStr === selectedDate

                  return (
                    <div
                      key={i}
                      onClick={() => selectDate(cell.dateStr)}
                      role="button"
                      aria-label={`${cell.dateStr}，${dayBookings.length} 項課程`}
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          selectDate(cell.dateStr)
                        }
                      }}
                      className={`min-h-[68px] bg-white p-1 text-left transition-colors hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-700 sm:min-h-[100px] sm:p-2 ${isSelected ? 'ring-2 ring-inset' : ''}`}
                      style={isSelected ? ({ '--tw-ring-color': PRIMARY } as any) : undefined}>
                      <div className="flex items-center justify-between">
                        <span className={`text-sm font-medium ${isToday ? 'text-white rounded-full w-6 h-6 flex items-center justify-center' : 'text-gray-900 dark:text-white'}`}
                          style={isToday ? { backgroundColor: PRIMARY } : undefined}>{cell.date.getDate()}</span>
                        {dayBookings.length > 0 && <span className="text-[10px] text-violet-600 dark:text-violet-300 sm:text-xs sm:text-gray-500">{dayBookings.length} 項</span>}
                      </div>
                      <div className="mt-1 hidden space-y-0.5 sm:block">
                        {dayBookings.slice(0, 2).map((b) => {
                          const eventColor = getEventColor(b.event_type)
                          return (
                            <button
                              key={b.id}
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                openMyCourse(b)
                              }}
                              className="block w-full text-xs px-1.5 py-0.5 rounded truncate text-left hover:ring-1 hover:ring-current focus:outline-none focus:ring-1 focus:ring-current"
                              style={{ backgroundColor: `${eventColor}1a`, color: eventColor }}
                              title="前往我的課程"
                            >
                              {b.start_time?.substring(0, 5)} {b.event_type === 'equipment_assistance' ? '裝備協助' : b.user_name}
                            </button>
                          )
                        })}
                        {dayBookings.length > 2 && <div className="text-xs text-gray-500 px-1">+ {dayBookings.length - 2} 更多</div>}
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>

        <div ref={dayDetailRef} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
            <CalendarIcon size={16} style={{ color: PRIMARY }} />
            <h3 className="font-semibold text-gray-900 dark:text-white text-sm">{selectedDate || '選擇一天查看'}</h3>
          </div>
          {!selectedDate ? (
            <div className="p-8 text-center text-sm text-gray-500">點選左側日期</div>
          ) : selectedBookings.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-500">當天沒有排課</div>
          ) : (
            <div className="p-3 space-y-2 max-h-[500px] overflow-y-auto">
              {selectedBookings.map((b) => {
                const isEquipment = b.event_type === 'equipment_assistance'
                const eventColor = getEventColor(b.event_type)
                const languageLabel = getLanguageLabel(b)
                const equipmentLabel = getEquipmentLabel(b)
                const coachRequestLabel = getCoachRequestLabel(b)
                return (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => openMyCourse(b)}
                    className="w-full p-3 bg-gray-50 dark:bg-gray-700 rounded-lg text-left transition-colors hover:bg-gray-100 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/40"
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="text-sm font-mono font-medium" style={{ color: eventColor }}>
                        {b.start_time?.substring(0, 5)} - {b.end_time?.substring(0, 5)}
                      </div>
                      {isEquipment && (
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">裝備協助</span>
                      )}
                    </div>
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{b.course_name}</div>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-300">
                      <div><span className="text-gray-400">上課語言</span> {languageLabel}</div>
                      <div><span className="text-gray-400">教練指定</span> {coachRequestLabel}</div>
                      {equipmentLabel && (
                        <div className="col-span-2"><span className="text-gray-400">裝備協助</span> {equipmentLabel}</div>
                      )}
                      <div className="col-span-2"><span className="text-gray-400">日期/時段</span> {b.date} {b.start_time?.substring(0, 5)} - {b.end_time?.substring(0, 5)}</div>
                      <div><span className="text-gray-400">課程</span> {b.course_type || '-'}</div>
                      <div><span className="text-gray-400">人數</span> {b.number_of_people} 人</div>
                      <div><span className="text-gray-400">雪場</span> {b.resort || '-'}</div>
                      <div><span className="text-gray-400">程度</span> {formatAbilityLevel(b.ability_level)}</div>
                    </div>
                    <div className="text-xs text-gray-500 mt-1 space-y-0.5">
                      <div>學員：{b.user_name}（{b.number_of_people} 人）</div>
                      <div>雪場：{b.resort}</div>
                      {isEquipment && b.equipment_assistance_time_label && <div>協助時段：{b.equipment_assistance_time_label}</div>}
                      {isEquipment && b.linked_course_date && <div>對應課程：{b.linked_course_date}</div>}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
