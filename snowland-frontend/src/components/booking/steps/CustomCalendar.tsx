import { useState, useEffect } from 'react'
import { useBookingStore } from '@/store/bookingStore'
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react'
import { fetchCourseTemplates } from '@/api/booking'
import { CourseTemplate } from '@/types/booking'

interface CustomCalendarProps {
  onNext: () => void
  onBack: () => void
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']
const MONTHS = [
  '一月',
  '二月',
  '三月',
  '四月',
  '五月',
  '六月',
  '七月',
  '八月',
  '九月',
  '十月',
  '十一月',
  '十二月',
]

export default function CustomCalendar({
  onNext,
  onBack,
}: CustomCalendarProps) {
  const today = new Date()
  const [currentYear, setCurrentYear] = useState(today.getFullYear())
  const [currentMonth, setCurrentMonth] = useState(today.getMonth())
  const [template, setTemplate] = useState<CourseTemplate | null>(null)
  const [loading, setLoading] = useState(false)

  const setSelectedDate = useBookingStore((state) => state.setSelectedDate)
  const selectedCourseTemplate = useBookingStore((state) => state.selectedCourseTemplate)
  const selectedCourseType = useBookingStore((state) => state.selectedCourseType)
  const selectedResort = useBookingStore((state) => state.selectedResort)

  // 載入課程模板資訊
  useEffect(() => {
    const loadTemplate = async () => {
      if (!selectedCourseTemplate || !selectedCourseType || !selectedResort) return

      try {
        setLoading(true)
        const templates = await fetchCourseTemplates({
          course_type_id: selectedCourseType,
          resort: selectedResort,
        })
        const found = templates.find((t) => t.id === selectedCourseTemplate)
        setTemplate(found || null)
      } catch (err) {
        console.error('載入課程模板失敗:', err)
      } finally {
        setLoading(false)
      }
    }

    loadTemplate()
  }, [selectedCourseTemplate, selectedCourseType, selectedResort])

  const getDaysInMonth = (year: number, month: number) => {
    return new Date(year, month + 1, 0).getDate()
  }

  const getFirstDayOfMonth = (year: number, month: number) => {
    return new Date(year, month, 1).getDay()
  }

  const handlePreviousMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11)
      setCurrentYear(currentYear - 1)
    } else {
      setCurrentMonth(currentMonth - 1)
    }
  }

  const handleNextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0)
      setCurrentYear(currentYear + 1)
    } else {
      setCurrentMonth(currentMonth + 1)
    }
  }

  const isDateSelectable = (date: Date) => {
    const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate())

    // 不允許選擇過去日期
    if (date < todayStart) return false

    // 如果沒有課程模板資訊，允許選擇
    if (!template) return true

    // 檢查預約開放期間
    if (template.booking_open_date) {
      const bookingOpen = new Date(template.booking_open_date)
      if (date < bookingOpen) return false
    }

    if (template.booking_close_date) {
      const bookingClose = new Date(template.booking_close_date)
      if (date > bookingClose) return false
    }

    // 檢查課程開設期間
    if (template.course_start_date) {
      const courseStart = new Date(template.course_start_date)
      if (date < courseStart) return false
    }

    if (template.course_end_date) {
      const courseEnd = new Date(template.course_end_date)
      if (date > courseEnd) return false
    }

    return true
  }

  const handleSelectDate = (day: number) => {
    const selectedDate = new Date(currentYear, currentMonth, day)

    // 檢查是否可選
    if (!isDateSelectable(selectedDate)) return

    // 格式化日期為 YYYY-MM-DD
    const formattedDate = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    setSelectedDate(formattedDate)
    onNext()
  }

  const renderCalendarDays = () => {
    const daysInMonth = getDaysInMonth(currentYear, currentMonth)
    const firstDay = getFirstDayOfMonth(currentYear, currentMonth)
    const days = []

    // 填充空白日期
    for (let i = 0; i < firstDay; i++) {
      days.push(
        <div key={`empty-${i}`} className="aspect-square p-2"></div>
      )
    }

    // 填充實際日期
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(currentYear, currentMonth, day)
      const isSelectable = isDateSelectable(date)
      const isToday =
        date.getFullYear() === today.getFullYear() &&
        date.getMonth() === today.getMonth() &&
        date.getDate() === today.getDate()

      days.push(
        <button
          key={day}
          onClick={() => handleSelectDate(day)}
          disabled={!isSelectable}
          className={`aspect-square rounded-lg p-2 text-center font-semibold transition-all ${
            !isSelectable
              ? 'cursor-not-allowed text-gray-300'
              : isToday
              ? 'bg-primary-100 text-primary-700 hover:bg-primary-200'
              : 'text-gray-700 hover:bg-primary-50 hover:text-primary-600 hover:scale-110'
          } ${
            isSelectable && 'hover:shadow-lg'
          }`}
        >
          {day}
          {isToday && (
            <div className="mt-1 flex justify-center">
              <div className="h-1.5 w-1.5 rounded-full bg-primary-500"></div>
            </div>
          )}
        </button>
      )
    }

    return days
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-2xl font-bold text-gray-800">選擇上課日期</h3>
        <p className="mt-2 text-gray-600">請選擇您想要上課的日期</p>
      </div>

      <div className="mx-auto max-w-lg rounded-2xl border-2 border-gray-200 bg-white p-6 shadow-lg">
        {/* Month Navigator */}
        <div className="mb-6 flex items-center justify-between">
          <button
            onClick={handlePreviousMonth}
            className="rounded-full p-2 transition-all hover:bg-gray-100"
          >
            <ChevronLeft size={24} className="text-gray-600" />
          </button>

          <div className="flex items-center gap-2">
            <Calendar size={20} className="text-primary-500" />
            <h4 className="text-xl font-bold text-gray-800">
              {currentYear} 年 {MONTHS[currentMonth]}
            </h4>
          </div>

          <button
            onClick={handleNextMonth}
            className="rounded-full p-2 transition-all hover:bg-gray-100"
          >
            <ChevronRight size={24} className="text-gray-600" />
          </button>
        </div>

        {/* Weekday Headers */}
        <div className="mb-2 grid grid-cols-7 gap-2">
          {WEEKDAYS.map((day) => (
            <div
              key={day}
              className="p-2 text-center text-sm font-semibold text-gray-600"
            >
              {day}
            </div>
          ))}
        </div>

        {/* Calendar Grid */}
        <div className="grid grid-cols-7 gap-2">{renderCalendarDays()}</div>
      </div>

      <div className="rounded-lg bg-blue-50 p-4">
        <p className="text-sm text-blue-800">
          💡 <strong>提示：</strong>
          {loading ? (
            '載入課程資訊中...'
          ) : template ? (
            <>
              可預約期間：
              {template.booking_open_date && template.booking_close_date
                ? `${template.booking_open_date} ~ ${template.booking_close_date}`
                : '不限'}
              ｜ 課程期間：
              {template.course_start_date && template.course_end_date
                ? `${template.course_start_date} ~ ${template.course_end_date}`
                : '不限'}
            </>
          ) : (
            '過去的日期無法選擇，今天的日期會有特別標記'
          )}
        </p>
      </div>
    </div>
  )
}
