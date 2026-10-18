/**
 * 排課管理（接 API）
 */
import { useState, useMemo, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Filter, Calendar as CalendarIcon, Loader2, AlertCircle } from 'lucide-react'
import { assignSharedClassCoach, fetchGroupCandidates, fetchScheduleCalendar, fetchSharedClassCoaches, fetchSharedClassOpeningOptions, fetchSharedClassSchedule, openSharedClass, rescheduleSharedClass, type GroupCandidate, type ScheduleBooking } from '../api/schedule'
import { fetchAdminMe } from '../api/auth'
import { fetchOrder, type Order } from '../api/orders'
import { OrderDetailDrawer } from './OrdersPage'

const PRIMARY = '#8b5cf6'
const EQUIPMENT_COLOR = '#d97706'
const PHOTO_COLOR = '#0ea5e9'
type ScheduleViewMode = 'day' | 'week' | '2weeks' | '3weeks' | '4weeks' | 'month'

const VIEW_OPTIONS: { value: ScheduleViewMode; label: string; days?: number }[] = [
  { value: 'day', label: '日', days: 1 },
  { value: 'week', label: '週', days: 7 },
  { value: '2weeks', label: '2週', days: 14 },
  { value: '3weeks', label: '3週', days: 21 },
  { value: '4weeks', label: '4週', days: 28 },
  { value: 'month', label: '月' },
]

const WEEKDAY_LABELS = ['日', '一', '二', '三', '四', '五', '六']

const STATUS_CLS: Record<string, string> = {
  scheduled: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  completed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  auto_assigned: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  manually_assigned: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  auto_assignment_failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  manual_assignment_needed: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  pending_coach_confirmation: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
  form_filled: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  created: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300',
  equipment_assistance: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
}
const STATUS_LABEL: Record<string, string> = {
  scheduled: '已排定', pending: '待確認', completed: '已完成',
  auto_assigned: '自動排定', manually_assigned: '人工排定',
  auto_assignment_failed: '排課失敗',
  manual_assignment_needed: '需人工處理',
  pending_coach_confirmation: '等教練確認',
  form_filled: '已填表',
  created: '待確認',
  equipment_assistance: '裝備協助',
}

function getEventColor(eventType?: string) {
  if (eventType === 'equipment_assistance') return EQUIPMENT_COLOR
  if (eventType === 'photo') return PHOTO_COLOR
  return PRIMARY
}

function getCalendarEventTitle(booking: ScheduleBooking) {
  if (booking.event_type === 'equipment_assistance') return '裝備協助'
  if (booking.event_type === 'photo') return '攝影'
  return booking.coach_name || '未排教練'
}

function getEventDetailCoachLabel(booking: ScheduleBooking) {
  if (booking.event_type === 'photo') {
    return booking.coach_name ? `攝影師：${booking.coach_name}` : '攝影師：未指定'
  }
  return `教練：${booking.coach_name || '未排定'}`
}

function hasKnownAbilityLevel(level: string) {
  return level === 'no_exp' || /^level[1-6]$/.test(level)
}

function candidateStatus(candidate: GroupCandidate) {
  if (!hasKnownAbilityLevel(candidate.ability_level)) return '先確認學員程度'
  if (candidate.shared_class_id) {
    if (candidate.shared_class_status === 'cancelled') return '班級已取消'
    if (candidate.shared_class_status === 'collecting') return `湊班中，尚差 ${Math.max((candidate.minimum_students ?? 0) - candidate.registered_students, 0)} 人`
    if (candidate.paid_students === undefined) return '已成班'
    return `已成班，${candidate.paid_students}/${candidate.registered_students} 人已付款`
  }
  if (candidate.assigned_students > 0) return '已有排課，請先核對'
  return '候選名單，尚未建立班級'
}

function formatDateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function parseDateKey(dateStr: string) {
  const [year, month, day] = dateStr.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function startOfDay(date: Date) {
  const next = new Date(date)
  next.setHours(0, 0, 0, 0)
  return next
}

function addDays(date: Date, amount: number) {
  const next = new Date(date)
  next.setDate(next.getDate() + amount)
  return next
}

function startOfWeek(date: Date) {
  const next = startOfDay(date)
  next.setDate(next.getDate() - next.getDay())
  return next
}

function getViewDays(mode: ScheduleViewMode) {
  return VIEW_OPTIONS.find((option) => option.value === mode)?.days || 0
}

function getRangeStart(anchorDate: Date, mode: ScheduleViewMode) {
  if (mode === 'month') return new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1)
  if (mode === 'day') return startOfDay(anchorDate)
  return startOfWeek(anchorDate)
}

function getRangeEnd(rangeStart: Date, anchorDate: Date, mode: ScheduleViewMode) {
  if (mode === 'month') return new Date(anchorDate.getFullYear(), anchorDate.getMonth() + 1, 0)
  return addDays(rangeStart, Math.max(getViewDays(mode), 1) - 1)
}

function getRangeLabel(mode: ScheduleViewMode, rangeStart: Date, rangeEnd: Date) {
  if (mode === 'month') return `${rangeStart.getFullYear()} 年 ${rangeStart.getMonth() + 1} 月`
  if (mode === 'day') return formatDateKey(rangeStart)
  return `${formatDateKey(rangeStart)} ~ ${formatDateKey(rangeEnd)}`
}

export default function SchedulingPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: adminMe } = useQuery({ queryKey: ['admin', 'me'], queryFn: fetchAdminMe })
  const isCampusManager = adminMe?.user?.role === 'campus_manager'
  const isCampusOrderViewer = isCampusManager || adminMe?.user?.role === 'campus_principal'
  const canManageSharedClass = Boolean(adminMe?.user?.is_superuser || adminMe?.user?.role === 'hq_admin')
  const today = new Date()
  const [viewMode, setViewMode] = useState<ScheduleViewMode>('month')
  const [anchorDate, setAnchorDate] = useState(new Date(today.getFullYear(), today.getMonth(), today.getDate()))
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [resortFilter, setResortFilter] = useState('')
  const [coachFilter, setCoachFilter] = useState('')
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null)
  const [showAllCandidates, setShowAllCandidates] = useState(false)
  const [editingSharedClassId, setEditingSharedClassId] = useState<number | null>(null)
  const [selectedSharedCoachId, setSelectedSharedCoachId] = useState('')
  const [sharedClassMessage, setSharedClassMessage] = useState('')
  const [sharedClassError, setSharedClassError] = useState('')
  const [reschedulingClassId, setReschedulingClassId] = useState<number | null>(null)
  const [rescheduleDate, setRescheduleDate] = useState('')
  const [rescheduleSession, setRescheduleSession] = useState('')
  const [rescheduleError, setRescheduleError] = useState('')
  const [showOpeningForm, setShowOpeningForm] = useState(false)
  const [openingCampus, setOpeningCampus] = useState('')
  const [openingResort, setOpeningResort] = useState('')
  const [openingTemplate, setOpeningTemplate] = useState('')
  const [openingSession, setOpeningSession] = useState('')
  const [openingDate, setOpeningDate] = useState('')
  const [openingLevel, setOpeningLevel] = useState('')
  const [openingLanguage, setOpeningLanguage] = useState('zh')
  const [openingError, setOpeningError] = useState('')

  const todayStr = formatDateKey(today)
  const managerVisibleEnd = formatDateKey(addDays(today, 10))
  const isOutsideManagerWindow = (date: string) => isCampusManager && (date < todayStr || date > managerVisibleEnd)
  const rangeStartDate = getRangeStart(anchorDate, viewMode)
  const rangeEndDate = getRangeEnd(rangeStartDate, anchorDate, viewMode)
  const rangeStart = formatDateKey(rangeStartDate)
  const rangeEnd = formatDateKey(rangeEndDate)
  const rangeLabel = getRangeLabel(viewMode, rangeStartDate, rangeEndDate)

  const calendarMonth = new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1)
  const year = calendarMonth.getFullYear()
  const month = calendarMonth.getMonth()

  const { data: scheduleData, isLoading, error } = useQuery({
    queryKey: ['admin', 'bookings', rangeStart, rangeEnd],
    queryFn: () => fetchScheduleCalendar({ start: rangeStart, end: rangeEnd }),
  })
  const bookings = scheduleData?.bookings || []
  const dailySummary = scheduleData?.dailySummary || []
  const { data: groupCandidates = [], isLoading: candidatesLoading, error: candidatesError } = useQuery({
    queryKey: ['admin', 'group-candidates', rangeStart, rangeEnd],
    queryFn: () => fetchGroupCandidates({ start: rangeStart, end: rangeEnd }),
  })
  const { data: openingOptions } = useQuery({
    queryKey: ['admin', 'shared-class-opening-options'],
    queryFn: fetchSharedClassOpeningOptions,
    enabled: canManageSharedClass,
    retry: false,
  })
  const openingCampusInfo = openingOptions?.campuses?.find((campus) => campus.id === Number(openingCampus))
  const openingTemplates = openingOptions?.templates?.filter((template) => template.resort_ids.includes(Number(openingResort))) || []
  const openingTemplateInfo = openingTemplates.find((template) => template.id === Number(openingTemplate))
  const openingMutation = useMutation({
    onMutate: () => {
      setOpeningError('')
      setSharedClassMessage('')
    },
    mutationFn: () => openSharedClass({
      campus_id: Number(openingCampus), resort_id: Number(openingResort),
      template_id: Number(openingTemplate), session_id: Number(openingSession),
      date: openingDate, ability_level: openingLevel, language: openingLanguage,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'group-candidates'] })
      setAnchorDate(parseDateKey(openingDate))
      setSelectedDate(openingDate)
      setShowOpeningForm(false)
      setOpeningError('')
      setSharedClassMessage('已開班；客人可在訂課日曆看到這個時段並加入湊班。')
    },
    onError: (error: any) => setOpeningError(error?.response?.data?.msg || '開班失敗，請確認課程期間與校區雪場設定。'),
  })
  const visibleCandidates = groupCandidates.filter((candidate) => !resortFilter || candidate.resort_name === resortFilter)
  const selectedCandidates = selectedDate ? visibleCandidates.filter((candidate) => candidate.date === selectedDate) : []
  const { data: sharedCoachOptions, isLoading: sharedCoachesLoading, error: sharedCoachesError } = useQuery({
    queryKey: ['admin', 'shared-class-coaches', editingSharedClassId],
    queryFn: () => fetchSharedClassCoaches(editingSharedClassId!),
    enabled: editingSharedClassId !== null,
    retry: false,
  })
  const sharedCoachMutation = useMutation({
    onMutate: () => { setSharedClassError(''); setSharedClassMessage('') },
    mutationFn: () => assignSharedClassCoach(editingSharedClassId!, Number(selectedSharedCoachId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'group-candidates'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'bookings'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'orders'] })
      setEditingSharedClassId(null)
      setSelectedSharedCoachId('')
      setSharedClassError('')
      setSharedClassMessage('整班教練已更新，所有同班訂單同步改派。')
    },
    onError: (error: any) => setSharedClassError(error?.response?.data?.msg || '整班指派失敗，請重新確認教練與時段。'),
  })
  const { data: scheduleOptions, isLoading: scheduleOptionsLoading, error: scheduleOptionsError } = useQuery({
    queryKey: ['admin', 'shared-class-schedule', reschedulingClassId],
    queryFn: () => fetchSharedClassSchedule(reschedulingClassId!),
    enabled: reschedulingClassId !== null,
    retry: false,
  })
  const rescheduleMutation = useMutation({
    onMutate: () => { setRescheduleError(''); setSharedClassMessage('') },
    mutationFn: async () => {
      const date = rescheduleDate
      const [startTime, endTime] = rescheduleSession.split('|')
      const message = await rescheduleSharedClass(reschedulingClassId!, date, startTime, endTime)
      return { message, date }
    },
    onSuccess: ({ message, date }) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'group-candidates'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'bookings'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'orders'] })
      setReschedulingClassId(null)
      setRescheduleError('')
      setAnchorDate(parseDateKey(date))
      setSelectedDate(date)
      setSharedClassMessage(message)
    },
    onError: (error: any) => setRescheduleError(error?.response?.data?.msg || '整班改期失敗，請重新確認時段。'),
  })

  const { data: selectedOrder, isFetching: isOrderLoading } = useQuery<Order>({
    queryKey: ['admin', 'orders', selectedOrderId],
    queryFn: () => fetchOrder(selectedOrderId!),
    enabled: !!selectedOrderId,
  })

  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const cells: { date: Date | null; dateStr: string }[] = []
  for (let i = 0; i < firstDay; i++) cells.push({ date: null, dateStr: '' })
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(year, month, d)
    const dateStr = formatDateKey(date)
    cells.push({ date, dateStr })
  }

  const visibleDays = useMemo(() => {
    const days: { date: Date; dateStr: string }[] = []
    for (let date = new Date(rangeStartDate); date <= rangeEndDate; date = addDays(date, 1)) {
      days.push({ date: new Date(date), dateStr: formatDateKey(date) })
    }
    return days
  }, [rangeStart, rangeEnd])

  const allResorts = useMemo(() => Array.from(new Set([
    ...bookings.map((b) => b.resort),
    ...groupCandidates.map((candidate) => candidate.resort_name),
  ].filter(Boolean))), [bookings, groupCandidates])
  const allCoaches = useMemo(() => Array.from(new Set(bookings.map((b) => b.coach_name).filter(Boolean))), [bookings])
  const summaryByDate = useMemo(
    () => new Map(dailySummary.map((summary) => [summary.date, summary])),
    [dailySummary],
  )
  const candidatesByDate = useMemo(() => {
    const counts = new Map<string, number>()
    visibleCandidates.forEach((candidate) => counts.set(candidate.date, (counts.get(candidate.date) || 0) + 1))
    return counts
  }, [groupCandidates, resortFilter])

  const getBookingsForDate = (dateStr: string) => bookings.filter((b) => {
    if (b.date !== dateStr) return false
    if (resortFilter && b.resort !== resortFilter) return false
    if (coachFilter && b.coach_name !== coachFilter) return false
    return true
  })

  const selectedBookings = selectedDate ? getBookingsForDate(selectedDate) : []
  const selectedSummary = selectedDate ? summaryByDate.get(selectedDate) : null
  const dayDetailRef = useRef<HTMLDivElement>(null)
  const selectDate = (date: string) => {
    if (isOutsideManagerWindow(date)) return
    setSelectedDate(date)
    if (window.matchMedia('(max-width: 1023px)').matches) {
      requestAnimationFrame(() => dayDetailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }
  const selectedBookingGroups = useMemo(() => {
    const map = new Map<string, { key: string; groupId: number | null; bookings: ScheduleBooking[] }>()
    selectedBookings.forEach((booking) => {
      const groupId = booking.group_id ? Number(booking.group_id) : null
      const key = groupId ? `group-${groupId}` : `booking-${booking.id}`
      if (!map.has(key)) map.set(key, { key, groupId, bookings: [] })
      map.get(key)!.bookings.push(booking)
    })
    return Array.from(map.values()).map((group) => ({
      ...group,
      bookings: group.bookings.sort((a, b) => `${a.start_time || ''}`.localeCompare(`${b.start_time || ''}`)),
    }))
  }, [selectedBookings])
  const openBookingOrder = (booking: { date: string; group_id?: number | null; sn?: string }) => {
    setSelectedDate(booking.date)
    if (booking.group_id && (!adminMe?.user || isCampusOrderViewer)) {
      navigate(`/snowland/console/orders?search=${encodeURIComponent(booking.sn || String(booking.group_id))}`)
    } else if (booking.group_id) {
      setSelectedOrderId(Number(booking.group_id))
    }
  }
  const goToday = () => {
    setAnchorDate(new Date(today.getFullYear(), today.getMonth(), today.getDate()))
    setSelectedDate(todayStr)
  }
  const shiftView = (direction: -1 | 1) => {
    if (viewMode === 'month') {
      setAnchorDate(new Date(anchorDate.getFullYear(), anchorDate.getMonth() + direction, 1))
      return
    }
    setAnchorDate(addDays(anchorDate, direction * Math.max(getViewDays(viewMode), 1)))
  }
  const switchViewMode = (mode: ScheduleViewMode) => {
    setViewMode(mode)
    if (mode === 'month') {
      setAnchorDate(new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1))
    } else if (selectedDate) {
      setAnchorDate(parseDateKey(selectedDate))
    }
  }
  const renderEventButton = (booking: ScheduleBooking, compact = false) => {
    const eventColor = getEventColor(booking.event_type)
    return (
      <button
        key={booking.id}
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          openBookingOrder(booking)
        }}
        className={`block w-full rounded text-left transition focus:outline-none focus:ring-1 focus:ring-current ${
          compact
            ? 'truncate px-1.5 py-0.5 text-xs hover:ring-1'
            : 'border border-transparent px-2 py-1.5 text-xs hover:border-current'
        }`}
        style={{ backgroundColor: `${eventColor}1a`, color: eventColor }}
        title={!adminMe?.user || isCampusOrderViewer ? '查看訂單' : '開啟訂單詳細資訊'}
      >
        {compact ? (
          <>{booking.start_time?.substring(0, 5)} {getCalendarEventTitle(booking)}</>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono font-semibold">{booking.start_time?.substring(0, 5)} - {booking.end_time?.substring(0, 5)}</span>
              <span className="shrink-0 rounded-full bg-white/70 px-1.5 py-0.5 text-[10px] dark:bg-gray-900/40">
                {STATUS_LABEL[booking.status] || booking.status}
              </span>
            </div>
            <div className="mt-1 truncate text-sm font-semibold">{getCalendarEventTitle(booking)}</div>
            <div className="mt-0.5 truncate text-gray-600 dark:text-gray-300">{booking.course_name}</div>
            <div className="mt-0.5 truncate text-gray-500 dark:text-gray-400">
              {booking.resort || '未填雪場'} · {booking.user_name || '未填姓名'} · {booking.number_of_people} 人
            </div>
          </>
        )}
      </button>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">排課管理</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">切換日、週、多週或月視圖檢視排課</p>
        {isCampusManager && <p className="mt-2 rounded-lg border border-purple-200 bg-purple-50 px-3 py-2 text-sm text-purple-800 dark:border-purple-800 dark:bg-purple-900/20 dark:text-purple-200">校區主管只顯示所屬校區從今天起 10 天內的排課；其他日期不會顯示課程。</p>}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <Filter size={14} /><span>篩選：</span>
          </div>
          <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
            <select value={resortFilter} onChange={(e) => setResortFilter(e.target.value)}
              className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30">
              <option value="">全部雪場</option>
              {allResorts.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <select value={coachFilter} onChange={(e) => setCoachFilter(e.target.value)}
              className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30">
              <option value="">全部教練</option>
              {allCoaches.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="flex flex-wrap gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-900">
            {VIEW_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => switchViewMode(option.value)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  viewMode === option.value
                    ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
                    : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <section className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800" aria-label="團體班與合班候選">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-white">團體班與合班候選</h2>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">「跨訂單班級」顯示實際成班狀態及該班門檻；「候選名單」只供人工核對，不代表已建立班級。</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-medium text-violet-700 dark:bg-violet-900/30 dark:text-violet-200">本範圍 {visibleCandidates.length} 組</span>
            {canManageSharedClass && openingOptions?.enabled && <button type="button" onClick={() => { setShowOpeningForm(!showOpeningForm); setOpeningError(''); setSharedClassMessage('') }} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700">{showOpeningForm ? '收起開班表單' : '學校先開團體班'}</button>}
          </div>
        </div>
        {showOpeningForm && openingOptions?.enabled && <div className="mt-4 rounded-lg border border-violet-200 bg-violet-50 p-4 dark:border-violet-800 dark:bg-violet-900/20">
          <p className="text-sm text-gray-700 dark:text-gray-200">先選校區和雪場，再選課程、日期、時段與程度。開班不會產生訂單或收款；客人報名滿最低人數才開放付款。</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <label className="text-sm font-medium text-gray-900 dark:text-white">校區
              <select value={openingCampus} onChange={(event) => { setOpeningCampus(event.target.value); setOpeningResort(''); setOpeningTemplate(''); setOpeningSession('') }} className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white"><option value="">請選校區</option>{openingOptions.campuses?.map((campus) => <option key={campus.id} value={campus.id}>{campus.name}</option>)}</select>
            </label>
            <label className="text-sm font-medium text-gray-900 dark:text-white">雪場
              <select value={openingResort} onChange={(event) => { setOpeningResort(event.target.value); setOpeningTemplate(''); setOpeningSession('') }} disabled={!openingCampus} className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-gray-900 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-white"><option value="">請選雪場</option>{openingCampusInfo?.resorts.map((resort) => <option key={resort.id} value={resort.id}>{resort.name}</option>)}</select>
            </label>
            <label className="text-sm font-medium text-gray-900 dark:text-white">團體班課程
              <select value={openingTemplate} onChange={(event) => { setOpeningTemplate(event.target.value); setOpeningSession('') }} disabled={!openingResort} className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-gray-900 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-white"><option value="">請選課程</option>{openingTemplates.map((template) => <option key={template.id} value={template.id}>{template.name} · {template.minimum_students} 人成班</option>)}</select>
            </label>
            <label className="text-sm font-medium text-gray-900 dark:text-white">上課日期
              <input type="date" min={todayStr} value={openingDate} onChange={(event) => setOpeningDate(event.target.value)} className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white" />
            </label>
            <label className="text-sm font-medium text-gray-900 dark:text-white">時段
              <select value={openingSession} onChange={(event) => setOpeningSession(event.target.value)} disabled={!openingTemplate} className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-gray-900 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-white"><option value="">請選時段</option>{openingTemplateInfo?.sessions.map((session) => <option key={session.id} value={session.id}>{session.label}</option>)}</select>
            </label>
            <label className="text-sm font-medium text-gray-900 dark:text-white">學員程度
              <select value={openingLevel} onChange={(event) => setOpeningLevel(event.target.value)} className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white"><option value="">請選程度</option>{openingOptions.levels?.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
            </label>
            <label className="text-sm font-medium text-gray-900 dark:text-white">授課語言
              <select value={openingLanguage} onChange={(event) => setOpeningLanguage(event.target.value)} className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white">{openingOptions.languages?.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
            </label>
          </div>
          {openingTemplates.length === 0 && openingResort && <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">這個雪場尚未設定可開放的團體班課程，請先到「課程架構」設定。</p>}
          {openingError && <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-300">{openingError}</p>}
          <button type="button" disabled={!openingCampus || !openingResort || !openingTemplate || !openingDate || !openingSession || !openingLevel || openingMutation.isPending} onClick={() => openingMutation.mutate()} className="mt-3 min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">{openingMutation.isPending ? '開班中…' : '確認開班'}</button>
        </div>}
        {sharedClassMessage && <p role="status" className="mt-3 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800 dark:bg-green-900/30 dark:text-green-200">{sharedClassMessage}</p>}
        {candidatesLoading ? <p className="mt-4 text-sm text-gray-500">載入合班候選中…</p> : candidatesError ? (
          <p className="mt-4 text-sm text-red-600">合班候選載入失敗，請重新整理頁面。</p>
        ) : visibleCandidates.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">目前範圍沒有團體班或合班候選。</p>
        ) : <>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {(showAllCandidates ? visibleCandidates : visibleCandidates.slice(0, 6)).map((candidate) => (
              <div key={`${candidate.campus_id}-${candidate.resort_id}-${candidate.template_id}-${candidate.date}-${candidate.start_time}-${candidate.ability_level}-${candidate.shared_class_id || 'candidate'}`} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium text-gray-900 dark:text-white">{candidate.shared_class_id ? candidate.opening_mode === 'school' && candidate.registered_students === 0 ? '學校預開班' : '跨訂單班級' : '候選名單'} · {candidate.date} {candidate.start_time}–{candidate.end_time}</p>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{candidate.campus_name} · {candidate.resort_name} · {candidate.template_name} · {candidate.ability_level === 'no_exp' ? '等級 0' : candidate.ability_level.startsWith('level') ? `等級 ${candidate.ability_level.slice(5)}` : '程度待確認'}</p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${candidate.shared_class_status === 'ready' ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200' : candidate.shared_class_status === 'collecting' ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-200'}`}>
                    {candidateStatus(candidate)}
                  </span>
                </div>
                <p className="mt-2 text-sm text-gray-700 dark:text-gray-200">報名 {candidate.registered_students}{candidate.minimum_students !== null && `/${candidate.minimum_students}`} 人{candidate.paid_students !== undefined && ` · 已付款 ${candidate.paid_students} 人`}{candidate.assigned_students > 0 && ` · ${candidate.shared_class_id ? '已指派教練' : '已排課'} ${candidate.assigned_students} 人`} · {candidate.orders.length} 筆訂單</p>
                {candidate.shared_class_id && candidate.assigned_students > 0 && candidate.paid_students !== undefined && candidate.paid_students < candidate.registered_students && <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">未付款的訂單暫不顯示於正式排課月曆。</p>}
                <div className="mt-2 flex flex-wrap gap-2">
                  {candidate.orders.map((order) => <button key={`${order.group_id}-${candidate.ability_level}`} type="button" onClick={() => navigate(`/snowland/console/orders?search=${encodeURIComponent(order.order_number || String(order.group_id))}`)} className="rounded-md border border-gray-200 px-2 py-1 text-xs text-violet-700 hover:bg-violet-50 dark:border-gray-600 dark:text-violet-300 dark:hover:bg-gray-700" title={isCampusOrderViewer ? '查看校區訂單摘要' : '查看訂單'}>{order.order_number || `訂單 #${order.group_id}`} · {order.students} 人{order.already_assigned ? ` · ${candidate.shared_class_id && order.payment_status !== 'paid' ? '教練已指派' : '已排課'}` : ''}</button>)}
                </div>
                {canManageSharedClass && candidate.shared_class_id && candidate.orders.length > 0 && candidate.shared_class_status !== 'cancelled' && <div className="mt-3 border-t border-gray-200 pt-3 dark:border-gray-700">
                  <button type="button" onClick={() => {
                    const nextId = reschedulingClassId === candidate.shared_class_id ? null : candidate.shared_class_id
                    setReschedulingClassId(nextId)
                    setRescheduleDate(candidate.date)
                    setRescheduleSession(`${candidate.start_time}|${candidate.end_time}`)
                    setRescheduleError('')
                    setSharedClassMessage('')
                  }} className="min-h-11 rounded-lg border border-violet-500 px-3 py-2 text-sm font-medium text-violet-700 hover:bg-violet-50 dark:text-violet-300 dark:hover:bg-gray-700">
                    {reschedulingClassId === candidate.shared_class_id ? '收起整班改期' : '整班調整日期／時段'}
                  </button>
                  {reschedulingClassId === candidate.shared_class_id && <div className="mt-3 rounded-lg bg-gray-50 p-3 dark:bg-gray-900/50">
                    {scheduleOptionsLoading ? <p className="text-sm text-gray-600 dark:text-gray-300">正在讀取可選時段…</p> : scheduleOptionsError ? <p role="alert" className="text-sm text-red-600 dark:text-red-300">無法讀取班級時段，請稍後再試。</p> : <>
                      <p className="text-sm text-gray-700 dark:text-gray-200">會同步修改 {scheduleOptions?.affected_orders ?? candidate.orders.length} 筆訂單，不會改動已收金額。儲存後請通知客人確認新時間。</p>
                      <div className="mt-3 flex flex-wrap items-end gap-2">
                        <label className="min-w-40 flex-1 text-sm font-medium text-gray-900 dark:text-white">新日期
                          <input type="date" min={todayStr} value={rescheduleDate} disabled={rescheduleMutation.isPending} onChange={(event) => { setRescheduleDate(event.target.value); setRescheduleError('') }} className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white" />
                        </label>
                        <label className="min-w-40 flex-1 text-sm font-medium text-gray-900 dark:text-white">上課時段
                          <select value={rescheduleSession} disabled={rescheduleMutation.isPending} onChange={(event) => { setRescheduleSession(event.target.value); setRescheduleError('') }} className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white">
                            <option value="">請選擇</option>
                            {scheduleOptions?.sessions.map((session) => <option key={`${session.start_time}|${session.end_time}`} value={`${session.start_time}|${session.end_time}`}>{session.start_time}–{session.end_time}</option>)}
                          </select>
                        </label>
                        <button type="button" disabled={!rescheduleDate || !rescheduleSession || rescheduleMutation.isPending || (rescheduleDate === candidate.date && rescheduleSession === `${candidate.start_time}|${candidate.end_time}`)} onClick={() => rescheduleMutation.mutate()} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">{rescheduleMutation.isPending ? '儲存中…' : '儲存整班時段'}</button>
                      </div>
                      {rescheduleError && <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-300">{rescheduleError}</p>}
                    </>}
                  </div>}
                </div>}
                {canManageSharedClass && candidate.shared_class_id && candidate.shared_class_status === 'ready' && <div className="mt-3 border-t border-gray-200 pt-3 dark:border-gray-700">
                  <button type="button" onClick={() => {
                    setEditingSharedClassId(editingSharedClassId === candidate.shared_class_id ? null : candidate.shared_class_id)
                    setSelectedSharedCoachId('')
                    setSharedClassError('')
                    setSharedClassMessage('')
                  }} className="min-h-11 rounded-lg border border-violet-500 px-3 py-2 text-sm font-medium text-violet-700 hover:bg-violet-50 dark:text-violet-300 dark:hover:bg-gray-700">
                    {editingSharedClassId === candidate.shared_class_id ? '收起整班改派' : '整班指派／更換教練'}
                  </button>
                  {editingSharedClassId === candidate.shared_class_id && <div className="mt-3 rounded-lg bg-gray-50 p-3 dark:bg-gray-900/50">
                    {sharedCoachesLoading ? <p className="text-sm text-gray-600 dark:text-gray-300">正在查詢可接課教練…</p> : sharedCoachesError ? <p role="alert" className="text-sm text-red-600 dark:text-red-300">無法查詢教練，請稍後再試。</p> : <>
                      <p className="text-sm text-gray-700 dark:text-gray-200">目前教練：{sharedCoachOptions?.current_coach_name || '尚未指派'}。儲存後會同步更新這班所有訂單。</p>
                      {sharedCoachOptions?.coaches.length ? <div className="mt-3 flex flex-wrap items-end gap-2">
                        <label className="min-w-48 flex-1 text-sm font-medium text-gray-900 dark:text-white">選擇教練
                          <select value={selectedSharedCoachId} disabled={sharedCoachMutation.isPending} onChange={(event) => { setSelectedSharedCoachId(event.target.value); setSharedClassError('') }} className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white">
                            <option value="">請選擇</option>
                            {sharedCoachOptions.coaches.map((coach) => <option key={coach.id} value={coach.id}>{coach.name}{coach.availability_status === 'passive' ? '（需確認接課）' : ''}</option>)}
                          </select>
                        </label>
                        <button type="button" disabled={!selectedSharedCoachId || sharedCoachMutation.isPending} onClick={() => sharedCoachMutation.mutate()} className="min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">{sharedCoachMutation.isPending ? '儲存中…' : '儲存整班教練'}</button>
                      </div> : <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">目前沒有符合課程資格且無撞課／請假的教練，請先檢查教練設定或時段。</p>}
                      {sharedClassError && <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-300">{sharedClassError}</p>}
                    </>}
                  </div>}
                </div>}
              </div>
            ))}
          </div>
          {visibleCandidates.length > 6 && <button type="button" onClick={() => setShowAllCandidates(!showAllCandidates)} className="mt-3 text-sm font-medium text-violet-700 hover:underline dark:text-violet-300">{showAllCandidates ? '收起' : `查看全部 ${visibleCandidates.length} 組`}</button>}
        </>}
      </section>

      {error ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <AlertCircle size={32} className="mx-auto mb-3 text-red-500" /><p className="text-sm text-red-600">載入失敗</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-white text-lg">{rangeLabel}</h3>
              <div className="flex items-center gap-2">
                <button onClick={goToday}
                  className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">今天</button>
                <button onClick={() => shiftView(-1)} className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"><ChevronLeft size={16} /></button>
                <button onClick={() => shiftView(1)} className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"><ChevronRight size={16} /></button>
              </div>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} /></div>
            ) : (
              viewMode === 'month' ? (
              <>
                <p className="border-b border-gray-200 px-3 py-2 text-[11px] text-gray-500 dark:border-gray-700 dark:text-gray-400 sm:hidden">綠色數字＝可排教練；紫色數字＝已排課。點日期看明細。</p>
                <div className="grid grid-cols-7 gap-px bg-gray-200 dark:bg-gray-700">
                  {WEEKDAY_LABELS.map((d) => (
                    <div key={d} className="bg-gray-50 dark:bg-gray-700 px-2 py-2 text-xs font-medium text-gray-600 dark:text-gray-300 text-center">{d}</div>
                  ))}
                </div>

                <div className="grid grid-cols-7 gap-px bg-gray-200 dark:bg-gray-700">
                  {cells.map((cell, i) => {
                    if (!cell.date) return <div key={i} className="min-h-[68px] bg-gray-50 dark:bg-gray-900 sm:min-h-[100px]" />
                    if (isOutsideManagerWindow(cell.dateStr)) return (
                      <div key={i} aria-label={`${cell.dateStr}，超出可查看期間`} className="min-h-[68px] bg-gray-50 p-1 text-gray-400 dark:bg-gray-900 dark:text-gray-500 sm:min-h-[100px] sm:p-2">
                        <span className="text-sm font-medium">{cell.date.getDate()}</span>
                        <span className="mt-1 block text-[10px] leading-tight sm:text-xs">超出可查看期間</span>
                      </div>
                    )
                    const dayBookings = getBookingsForDate(cell.dateStr)
                    const daySummary = summaryByDate.get(cell.dateStr)
                    const dayCandidateCount = candidatesByDate.get(cell.dateStr) || 0
                    const isToday = cell.dateStr === todayStr
                    const isSelected = cell.dateStr === selectedDate

                    return (
                      <div
                        key={i}
                        onClick={() => selectDate(cell.dateStr)}
                        role="button"
                        aria-label={`${cell.dateStr}，已排 ${dayBookings.length} 項，團體班與候選 ${dayCandidateCount} 組，可排 ${daySummary?.free_coaches ?? 0} 位教練`}
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            selectDate(cell.dateStr)
                          }
                        }}
                        className={`min-h-[68px] bg-white p-1 text-left transition-colors hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-700 sm:min-h-[100px] sm:p-2 ${isSelected ? 'ring-2 ring-inset' : ''}`}
                        title="選擇日期"
                        style={isSelected ? ({ '--tw-ring-color': PRIMARY } as any) : undefined}>
                        <div className="flex items-center justify-between gap-1">
                          <span className={`text-sm font-medium ${isToday ? 'text-white rounded-full w-6 h-6 flex items-center justify-center' : 'text-gray-900 dark:text-white'}`}
                            style={isToday ? { backgroundColor: PRIMARY } : undefined}>{cell.date.getDate()}</span>
                          {dayBookings.length > 0 && <span className="text-[10px] font-semibold text-violet-500 sm:text-xs sm:font-normal sm:text-gray-500"><span className="sm:hidden">{dayBookings.length}</span><span className="hidden sm:inline">{dayBookings.length} 項</span></span>}
                        </div>
                        {daySummary && (
                          <div className="mt-1 flex flex-wrap gap-1 text-[10px] sm:text-[11px]">
                            <span className="rounded bg-emerald-100 px-1 py-0.5 font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 sm:px-1.5">
                              <span className="hidden sm:inline">可排 </span>{daySummary.free_coaches}
                            </span>
                            {daySummary.leave_coaches > 0 && (
                              <span className="rounded bg-amber-100 px-1 py-0.5 font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 sm:px-1.5">
                                <span className="sm:hidden">假</span><span className="hidden sm:inline">請假 </span>{daySummary.leave_coaches}
                              </span>
                            )}
                          </div>
                        )}
                        {dayCandidateCount > 0 && <div className="mt-1 rounded bg-amber-100 px-1 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-200 sm:px-1.5 sm:text-[11px]">班級／候選 {dayCandidateCount} 組</div>}
                        <div className="mt-1 hidden space-y-0.5 sm:block">
                          {dayBookings.slice(0, 2).map((b) => renderEventButton(b, true))}
                          {dayBookings.length > 2 && <div className="text-xs text-gray-500 px-1">+ {dayBookings.length - 2} 更多</div>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
              ) : (
                <div className={`grid gap-px bg-gray-200 dark:bg-gray-700 ${
                  viewMode === 'day' ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-7'
                }`}>
                  {visibleDays.map((cell) => {
                    if (isOutsideManagerWindow(cell.dateStr)) return (
                      <div key={cell.dateStr} aria-label={`${cell.dateStr}，超出可查看期間`} className="min-h-[140px] bg-gray-50 p-3 text-gray-400 dark:bg-gray-900 dark:text-gray-500">
                        <div className="text-lg font-semibold">{cell.date.getMonth() + 1}/{cell.date.getDate()}</div>
                        <p className="mt-3 text-sm">超出可查看期間</p>
                      </div>
                    )
                    const dayBookings = getBookingsForDate(cell.dateStr).sort((a, b) => `${a.start_time || ''}`.localeCompare(`${b.start_time || ''}`))
                    const daySummary = summaryByDate.get(cell.dateStr)
                    const dayCandidateCount = candidatesByDate.get(cell.dateStr) || 0
                    const isToday = cell.dateStr === todayStr
                    const isSelected = cell.dateStr === selectedDate
                    return (
                      <div
                        key={cell.dateStr}
                        onClick={() => selectDate(cell.dateStr)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') selectDate(cell.dateStr)
                        }}
                        className={`min-h-[210px] bg-white p-3 text-left transition-colors hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-700 ${isSelected ? 'ring-2 ring-inset' : ''}`}
                        style={isSelected ? ({ '--tw-ring-color': PRIMARY } as any) : undefined}
                      >
                        <div className="mb-3 flex items-start justify-between gap-2">
                          <div>
                            <div className="text-xs font-medium text-gray-500 dark:text-gray-400">
                              {WEEKDAY_LABELS[cell.date.getDay()]}
                            </div>
                            <div className={`mt-0.5 text-lg font-semibold ${isToday ? 'text-[#8b5cf6]' : 'text-gray-900 dark:text-white'}`}>
                              {cell.date.getMonth() + 1}/{cell.date.getDate()}
                            </div>
                          </div>
                          {daySummary && (
                            <div className="flex flex-col items-end gap-1 text-[11px]">
                              <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                                可排 {daySummary.free_coaches}
                              </span>
                              {daySummary.leave_coaches > 0 && (
                                <span className="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                                  請假 {daySummary.leave_coaches}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                        {dayCandidateCount > 0 && <div className="mb-2 rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">團體班與候選 {dayCandidateCount} 組，點日期查看</div>}
                        {dayBookings.length === 0 ? (
                          <div className="rounded-lg border border-dashed border-gray-200 px-3 py-6 text-center text-xs text-gray-500 dark:border-gray-600 dark:text-gray-400">
                            沒有排課
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {dayBookings.map((booking) => renderEventButton(booking))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            )}
          </div>

          <div ref={dayDetailRef} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
              <CalendarIcon size={16} style={{ color: PRIMARY }} />
              <div className="min-w-0">
                <h3 className="font-semibold text-gray-900 dark:text-white text-sm">{selectedDate || '選擇一天查看排程'}</h3>
                {selectedSummary && (
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    可排教練 {selectedSummary.free_coaches} / {selectedSummary.total_coaches} 位（啟用校區）
                    {selectedSummary.booked_coaches > 0 && `，已排教練 ${selectedSummary.booked_coaches} 位`}
                    {selectedSummary.leave_coaches > 0 && `，請假 ${selectedSummary.leave_coaches}`}
                  </p>
                )}
              </div>
            </div>

            {selectedCandidates.length > 0 && <div className="border-b border-gray-200 p-3 dark:border-gray-700">
              <h4 className="mb-2 text-xs font-semibold text-amber-800 dark:text-amber-200">當天團體班與合班候選</h4>
              <div className="space-y-2">
                {selectedCandidates.map((candidate) => <div key={`${candidate.campus_id}-${candidate.resort_id}-${candidate.template_id}-${candidate.start_time}-${candidate.ability_level}-${candidate.shared_class_id || 'candidate'}`} className="rounded-lg bg-amber-50 p-2 text-xs text-gray-700 dark:bg-amber-900/20 dark:text-gray-200">
                  <p className="font-medium">{candidate.shared_class_id ? '跨訂單班級' : '候選名單'} · {candidate.start_time}–{candidate.end_time} · {candidate.campus_name} · {candidate.resort_name} · {candidate.template_name} · {candidate.ability_level === 'no_exp' ? '等級 0' : candidate.ability_level.startsWith('level') ? `等級 ${candidate.ability_level.slice(5)}` : '程度待確認'}</p>
                  <p className="mt-1">{candidateStatus(candidate)}</p>
                  <p className="mt-1">報名 {candidate.registered_students} 人 · {candidate.orders.length} 筆訂單{candidate.paid_students !== undefined && ` · 已付款 ${candidate.paid_students} 人`}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {candidate.orders.map((order) => <button key={order.group_id} type="button" onClick={() => navigate(`/snowland/console/orders?search=${encodeURIComponent(order.order_number || String(order.group_id))}`)} className="rounded border border-amber-300 px-2 py-1 text-violet-700 hover:bg-white dark:border-amber-700 dark:text-violet-300 dark:hover:bg-gray-800">查看 {order.order_number || `#${order.group_id}`}</button>)}
                  </div>
                </div>)}
              </div>
            </div>}
            {!selectedDate ? (
              <div className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">點選左側日期查看當天排課</div>
            ) : isLoading ? (
              <div role="status" className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">正在載入當天排程…</div>
            ) : selectedBookings.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">當天沒有排課</div>
            ) : (
              <div className="p-3 space-y-3 max-h-[500px] overflow-y-auto">
                {selectedBookingGroups.map((group) => {
                  const firstBooking = group.bookings[0]
                  return (
                    <div key={group.key} className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700">
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-gray-900 dark:text-white">
                            {group.groupId ? `訂單 ${firstBooking?.sn || firstBooking?.order_number || `#${group.groupId}`}` : '未分組排課'}
                          </div>
                          <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            {firstBooking?.user_name || '—'} · 共 {group.bookings.length} 小單
                          </div>
                          {firstBooking?.campus_name && (
                            <div className="mt-1 text-xs text-gray-500 dark:text-gray-300">
                              {firstBooking.campus_name}{firstBooking.campus_is_active === false && <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">已停用</span>}
                            </div>
                          )}
                        </div>
                        {group.groupId && firstBooking && (
                          <button
                            type="button"
                            onClick={() => openBookingOrder(firstBooking)}
                            className="shrink-0 rounded border border-gray-200 px-2 py-1 text-xs font-medium text-gray-600 hover:bg-white dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
                          >
                            查看訂單
                          </button>
                        )}
                      </div>

                      <div className="space-y-2">
                        {group.bookings.map((b, index) => {
                          const isEquipment = b.event_type === 'equipment_assistance'
                          const eventColor = getEventColor(b.event_type)
                          return (
                            <button
                              key={b.id}
                              type="button"
                              onClick={() => openBookingOrder(b)}
                              className="w-full rounded-lg border border-gray-200 bg-white p-2 text-left transition-colors hover:border-[#8b5cf6] focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/40 dark:border-gray-600 dark:bg-gray-800 dark:hover:border-[#8b5cf6]"
                            >
                              <div className="mb-1 flex items-center justify-between gap-2">
                                <span className="text-xs font-semibold text-gray-500 dark:text-gray-400">小單 {index + 1}</span>
                                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CLS[b.status] || STATUS_CLS.pending}`}>{STATUS_LABEL[b.status] || b.status}</span>
                              </div>
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-sm font-mono font-medium" style={{ color: eventColor }}>{b.start_time?.substring(0, 5)} - {b.end_time?.substring(0, 5)}</span>
                                <span className="truncate text-xs text-gray-500 dark:text-gray-400">{b.resort}</span>
                              </div>
                              <div className="mt-1 text-sm font-medium text-gray-900 dark:text-white">{b.course_name}</div>
                              <div className="mt-1 space-y-0.5 text-xs text-gray-500 dark:text-gray-400">
                                <div>{getEventDetailCoachLabel(b)}</div>
                                <div>學員：{b.user_name || '—'}（{b.number_of_people} 人）</div>
                                {isEquipment && b.equipment_assistance_time_label && <div>協助時段：{b.equipment_assistance_time_label}</div>}
                                {isEquipment && b.linked_course_date && <div>對應課程：{b.linked_course_date}</div>}
                              </div>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
      {isOrderLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="flex items-center gap-2 rounded-lg bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-lg dark:bg-gray-800 dark:text-gray-200">
            <Loader2 size={16} className="animate-spin" />
            載入訂單資料...
          </div>
        </div>
      )}
      {selectedOrder && (
        <OrderDetailDrawer
          order={selectedOrder}
          onClose={() => setSelectedOrderId(null)}
        />
      )}
    </div>
  )
}
