/**
 * BookingFlowPage — 整合版預約流程
 *
 * UI 來自官網（kkrisw/snowland）的 4 步驟品牌設計
 * 後端邏輯來自你的系統：Zustand store + Django API + 多租戶
 *
 * 流程：
 *   Step 1: 服務選擇（滑雪課程 / 攝影服務）
 *   Step 2: 配置（雪場 → 人數 → 能力 → 課程 → 日期 → 時段 → 教練 → 裝備）
 *   Step 3: 確認訂單 + 付款
 *   Step 4: 完成
 */

import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Calendar,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  Languages,
  Loader2,
  MapPin,
  Package,
  Pencil,
  Plus,
  Search,
  ShoppingCart,
  Trash2,
  User,
  Users,
} from 'lucide-react'
// @ts-ignore
import SiteHeader from '@/components/site/SiteHeader'
// @ts-ignore
import SiteFooter from '@/components/site/SiteFooter'
import LoginPage from '@/pages/LoginPage'
import CartModal from '@/components/booking/CartModal'
import SchedulingFailedModal from '@/components/booking/SchedulingFailedModal'
import ConfirmModal from '@/components/ui/ConfirmModal'
import Toast, { ToastType } from '@/components/ui/Toast'
import LoadingOverlay from '@/components/ui/LoadingOverlay'
import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import { useSiteLink } from '@/hooks/useSiteBasePath'
import { fetchAdminMe } from '@/admin/api/auth'
import { hasAdminPermission } from '@/admin/permissions'
import type { CartItem, Course } from '@/types/booking'
import {
  fetchCourseCategories,
  fetchCourseTypes,
  fetchResorts,
  fetchCoaches,
  fetchCourseTemplates,
  fetchCourseSessions,
  fetchAvailableDates,
  fetchSiteContent,
  calculatePrice,
  previewDiscounts,
  createReservation,
  resolveStaffBookingLink,
  superSchedule,
  cancelFailedReservations,
  type DiscountPreviewResponse,
} from '@/api/booking'

// ========== 類型 ==========
type ServiceType = 'ski' | 'photo'
type MainStep = 1 | 2 | 3 | 4
type CompletionFlow = 'payment' | 'bank_submitted' | 'bank_later' | 'coach' | 'staff' | 'collecting_class'

type BankInfo = {
  bank_name: string
  bank_branch: string
  bank_account_number: string
  bank_account_holder: string
}

type SubmittedReservation = {
  reservation_group_ids: number[]
  payment_access_tokens: Record<number, string>
  total_amount: number
  payment_infos: { reservation_group_id: number; total_amount: number; bank_info: BankInfo }[]
  payment_methods: string[]
  payment_expires_at: string | null
}

type SelectOption = {
  value: string
  label: string
}

const emptyBankInfo: BankInfo = {
  bank_name: '',
  bank_branch: '',
  bank_account_number: '',
  bank_account_holder: '',
}

const memberContactName = (name?: string, email?: string) => {
  const value = (name || '').trim()
  return value.toLowerCase() === (email || '').trim().toLowerCase() ? '' : value
}

const MESSENGER_OPTIONS: SelectOption[] = [
  { value: 'LINE', label: 'LINE' },
  { value: 'WhatsApp', label: 'WhatsApp' },
  { value: 'WeChat', label: 'WeChat' },
]

const REFERRAL_SOURCE_OPTIONS: SelectOption[] = [
  { value: '朋友介紹', label: '朋友介紹' },
  { value: '舊生推薦', label: '舊生推薦' },
  { value: 'Instagram', label: 'Instagram' },
  { value: 'Facebook', label: 'Facebook' },
  { value: 'Google 搜尋', label: 'Google 搜尋' },
  { value: '小紅書', label: '小紅書' },
  { value: 'Dcard / PTT', label: 'Dcard / PTT' },
  { value: 'YouTube', label: 'YouTube' },
  { value: '講座 / 限時活動', label: '講座 / 限時活動' },
  { value: '抽獎活動', label: '抽獎活動' },
  { value: '其他', label: '其他' },
]

const normalizeSelectOptions = (value: unknown, fallback: SelectOption[]): SelectOption[] => {
  if (!Array.isArray(value)) return fallback
  const seen = new Set<string>()
  const options = value
    .map((item) => {
      if (typeof item === 'string') {
        const text = item.trim()
        return text ? { value: text, label: text } : null
      }
      if (item && typeof item === 'object') {
        const maybeOption = item as { value?: unknown; label?: unknown }
        const optionValue = String(maybeOption.value || maybeOption.label || '').trim()
        const optionLabel = String(maybeOption.label || maybeOption.value || '').trim()
        return optionValue ? { value: optionValue, label: optionLabel || optionValue } : null
      }
      return null
    })
    .filter((item): item is SelectOption => Boolean(item))
    .filter((item) => {
      if (seen.has(item.value)) return false
      seen.add(item.value)
      return true
    })
  return options.length ? options : fallback
}

const getReservationGroupIdsFromResponse = (response: any) => {
  const ids = new Set<number>()

  if (Array.isArray(response?.reservation_group_ids)) {
    response.reservation_group_ids.forEach((id: unknown) => {
      const numericId = Number(id)
      if (Number.isFinite(numericId) && numericId > 0) ids.add(numericId)
    })
  }

  if (Array.isArray(response?.payment_urls)) {
    response.payment_urls.forEach((item: any) => {
      const numericId = Number(item?.reservation_group_id)
      if (Number.isFinite(numericId) && numericId > 0) ids.add(numericId)
    })
  }

  if (ids.size === 0 && response?.payment_url) {
    const queryString = String(response.payment_url).split('?')[1] || ''
    const numericId = Number(new URLSearchParams(queryString).get('reservation_group'))
    if (Number.isFinite(numericId) && numericId > 0) ids.add(numericId)
  }

  return Array.from(ids)
}

const getPaymentAccessTokensFromResponse = (response: any): Record<number, string> => {
  const tokens: Record<number, string> = {}
  const urls = [response?.payment_url, ...(response?.payment_urls || []).map((item: any) => item?.payment_url)]
  urls.forEach((url: unknown) => {
    if (typeof url !== 'string') return
    const params = new URLSearchParams(url.split('?')[1] || '')
    const groupId = Number(params.get('reservation_group'))
    const token = params.get('access_token')
    if (Number.isFinite(groupId) && groupId > 0 && token) tokens[groupId] = token
  })
  return tokens
}

const toDateKey = (date: Date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const parseDateKey = (dateKey: string) => new Date(`${dateKey}T00:00:00`)

const addMonthsToDate = (date: Date, months: number) => {
  const next = new Date(date.getFullYear(), date.getMonth() + months, 1)
  return next
}

const buildCalendarMonthCells = (monthDate: Date) => {
  const year = monthDate.getFullYear()
  const month = monthDate.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const cells: Array<string | null> = []

  for (let i = 0; i < firstDay.getDay(); i += 1) cells.push(null)
  for (let day = 1; day <= lastDay.getDate(); day += 1) {
    cells.push(toDateKey(new Date(year, month, day)))
  }
  while (cells.length % 7 !== 0) cells.push(null)

  return cells
}

const formatDateKey = (dateKey: string) => dateKey.replace(/-/g, '/')

const formatCurrency = (value?: number | null) => {
  if (value === null || value === undefined) return '價格待確認'
  return `NT$ ${Number(value || 0).toLocaleString()}`
}

const getWeekdayLabel = (dateKey?: string) => {
  if (!dateKey) return ''
  const date = parseDateKey(dateKey)
  const weekdays = ['日', '一', '二', '三', '四', '五', '六']
  return `週${weekdays[date.getDay()]}`
}

const getCartDateSummary = (courses: Course[]) => {
  const dates = Array.from(new Set(courses.map((course) => course.date).filter(Boolean))).sort()
  if (dates.length === 0) return '未選日期'
  if (dates.length === 1) return `${formatDateKey(dates[0])} ${getWeekdayLabel(dates[0])}`
  return `${formatDateKey(dates[0])} - ${formatDateKey(dates[dates.length - 1])}`
}

type CartCourseSegment = {
  key: string
  courses: Array<Course & { originalIndex: number }>
}

const getCourseSegmentKey = (course: Course) =>
  course.segmentId ||
  [
    'legacy',
    course.courseTemplateId,
    course.timeSlotId,
    course.timeSlotStart,
    course.timeSlotEnd,
    course.courseTemplateName,
  ].join(':')

const groupCartCoursesBySegment = (courses: Course[]): CartCourseSegment[] => {
  const segments: CartCourseSegment[] = []
  const segmentIndexByKey = new Map<string, number>()

  courses.forEach((course, originalIndex) => {
    const key = getCourseSegmentKey(course)
    const existingIndex = segmentIndexByKey.get(key)
    const courseWithIndex = { ...course, originalIndex }

    if (existingIndex === undefined) {
      segmentIndexByKey.set(key, segments.length)
      segments.push({ key, courses: [courseWithIndex] })
      return
    }

    segments[existingIndex].courses.push(courseWithIndex)
  })

  return segments
}

const formatCourseSegmentDates = (courses: Course[]) => {
  const dates = [...courses].map((course) => course.date).filter(Boolean).sort()
  if (dates.length === 0) return '未選日期'
  if (dates.length === 1) return `${formatDateKey(dates[0])} ${getWeekdayLabel(dates[0])}`
  return `${dates.map((date) => `${formatDateKey(date)} ${getWeekdayLabel(date)}`).join('、')}`
}

const formatCalendarMonth = (date: Date) => `${date.getFullYear()} 年 ${date.getMonth() + 1} 月`

const formatCalendarMonthKey = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`

const getCalendarStartDateKey = (dateInfo: any) => {
  const today = toDateKey(new Date())
  const candidates = [today, dateInfo?.course_start_date, dateInfo?.booking_open_date]
    .filter(Boolean) as string[]
  return candidates.sort().pop() || today
}

const isBookableDateKey = (dateKey: string, dateInfo: any) => {
  const today = toDateKey(new Date())
  if (dateKey < today) return false
  if (dateInfo?.booking_open_date && today < dateInfo.booking_open_date) return false
  if (dateInfo?.booking_close_date && today > dateInfo.booking_close_date) return false
  if (dateInfo?.course_start_date && dateKey < dateInfo.course_start_date) return false
  if (dateInfo?.course_end_date && dateKey > dateInfo.course_end_date) return false
  if (Array.isArray(dateInfo?.available_dates) && dateInfo?.month === dateKey.slice(0, 7)) {
    return dateInfo.available_dates.includes(dateKey)
  }
  return true
}

const isCourseTemplateOpenForBooking = (template: any) => {
  const today = toDateKey(new Date())
  if (template?.is_active === false) return false
  if (template?.booking_open_date && today < template.booking_open_date) return false
  if (template?.booking_close_date && today > template.booking_close_date) return false
  if (template?.course_end_date && today > template.course_end_date) return false
  return true
}

const getPriceErrorMessage = (error: any, fallback: string) => {
  const raw = error?.response?.data?.error || error?.response?.data?.msg || error?.message
  if (typeof raw !== 'string' || !raw.trim()) return fallback
  if (raw.includes('找不到對應的價格設定')) {
    return '此課程目前尚未設定此雪場價格，請返回選擇其他課程，或聯絡客服協助。'
  }
  return raw
}

const DAY_MS = 24 * 60 * 60 * 1000

const addDaysToDateKey = (dateKey: string, days: number) => {
  const date = parseDateKey(dateKey)
  date.setDate(date.getDate() + days)
  return toDateKey(date)
}

const getDateKeyOffset = (dateKey: string, baseDateKey: string) =>
  Math.round((parseDateKey(dateKey).getTime() - parseDateKey(baseDateKey).getTime()) / DAY_MS)

const normalizeSuggestionPeriod = (period?: string) => {
  const text = String(period || '').toLowerCase()
  if (/上午|morning/.test(text)) return 'morning'
  if (/下午|afternoon/.test(text)) return 'afternoon'
  if (/全天|全日|all/.test(text)) return 'all_day'
  return ''
}

const isTimeoutError = (error: any) =>
  error?.code === 'ECONNABORTED' || /timeout/i.test(String(error?.message || ''))

const getTimeMinutes = (time?: string | null) => {
  const [hour = '0', minute = '0'] = String(time || '00:00').split(':')
  return Number(hour) * 60 + Number(minute)
}

const isUsableSession = (session: any) => session && session.is_active !== false && !session.is_full

const chooseReplacementSession = (sessions: any[], original: Course, period?: string) => {
  const usableSessions = sessions.filter(isUsableSession)
  const requestedPeriod = normalizeSuggestionPeriod(period)
  const matchingByTime = usableSessions.find((session) =>
    session.start_time === original.timeSlotStart && session.end_time === original.timeSlotEnd,
  )

  if (requestedPeriod === 'morning') {
    return usableSessions.find((session) => getTimeMinutes(session.start_time) < 12 * 60) || matchingByTime || usableSessions[0]
  }

  if (requestedPeriod === 'afternoon') {
    return usableSessions.find((session) => getTimeMinutes(session.start_time) >= 12 * 60) || matchingByTime || usableSessions[0]
  }

  if (requestedPeriod === 'all_day') {
    return [...usableSessions]
      .sort((a, b) => (
        (getTimeMinutes(b.end_time) - getTimeMinutes(b.start_time)) -
        (getTimeMinutes(a.end_time) - getTimeMinutes(a.start_time))
      ))[0] || matchingByTime || usableSessions[0]
  }

  return usableSessions.find((session) => Number(session.id) === Number(original.timeSlotId)) ||
    matchingByTime ||
    usableSessions[0]
}

const getCartEditSignature = (cart: CartItem[]) =>
  cart.map((group) => [
    group.id,
    group.peopleCount,
    group.abilityLevel,
    group.coach,
    group.language,
    group.equipmentOption,
    group.courses.map((course) => [
      course.date,
      course.segmentId || '',
      course.courseTemplateId,
      course.timeSlotId,
      course.timeSlotStart,
      course.timeSlotEnd,
    ].join('@')).join('|'),
  ].join(':')).join('||')

const isPhotoCartGroup = (group: CartItem) =>
  /攝影|photography/i.test([
    group.courseCategory,
    ...group.courses.map((course) => `${course.courseTypeName} ${course.courseTemplateName}`),
  ].join(' '))

const abilityLevels = [
  {
    id: 'no_exp',
    name: '等級 0',
    ski: '從未滑過雪。',
    snowboard: '從未滑過雪。',
  },
  {
    id: 'level1',
    name: '等級 1',
    ski: '可以全制動剎車，開始學習轉向。',
    snowboard: '可以單邊側滑。',
  },
  {
    id: 'level2',
    name: '等級 2',
    ski: '可以在綠線初級雪道上進行連續全制動轉向。',
    snowboard: '可以用腳側和腳跟側斜滑落葉飄。',
  },
  {
    id: 'level3',
    name: '等級 3',
    ski: '可以進行連續半制動轉向，並能在簡單的紅線中級雪道滑行。',
    snowboard: '可以在綠線初級雪道連續轉向。',
  },
  {
    id: 'level4',
    name: '等級 4',
    ski: '可以在紅線中級雪道連續的併腿轉向。',
    snowboard: '可以在紅線中級雪道連續轉向。',
  },
  {
    id: 'level5',
    name: '等級 5',
    ski: '可以在黑線及非壓雪的鬆線上穩定併腿轉向。',
    snowboard: '可以在黑線高階雪道滑行。',
  },
  {
    id: 'level6',
    name: '等級 6',
    ski: '可以在樹林、鬆雪地形、紅線坡度上連續選滑。',
    snowboard: '可以在樹林、鬆雪地形、紅線坡度上連續選滑。',
  },
]

const abilityLevelOrder = abilityLevels.map((level) => level.id)

const getAssignedAbilityCount = (counts: Record<string, number> = {}) =>
  abilityLevelOrder.reduce((sum, level) => sum + (Number(counts[level]) || 0), 0)

const getTemplateStudentLevelRule = (
  template: any,
  counts: Record<string, number> = {},
  fallbackLevel = 'no_exp',
) => {
  const requiredRank = abilityLevelOrder.indexOf(String(template?.minimum_student_level || ''))
  const selectedLevels = abilityLevelOrder.filter((level) => Number(counts[level]) > 0)
  const actualLevels = selectedLevels.length ? selectedLevels : [fallbackLevel || 'no_exp']
  return {
    requiredRank,
    insufficient: requiredRank > 0 && actualLevels.some((level) => abilityLevelOrder.indexOf(level) < requiredRank),
  }
}

// 教練語言
const coachLanguages = [
  { id: null, name: 'ALL' },
  { id: 'zh', name: '中文' },
  { id: 'en', name: 'English' },
  { id: 'ja', name: '日本語' },
  { id: 'yue', name: '粵語' },
]

const languageAliases: Record<string, string> = {
  zh: 'zh',
  中文: 'zh',
  en: 'en',
  英文: 'en',
  English: 'en',
  ja: 'ja',
  日本語: 'ja',
  日文: 'ja',
  yue: 'yue',
  粵語: 'yue',
  廣東話: 'yue',
}

const normalizeLanguageCode = (value: unknown) => {
  if (!value) return ''
  const key = String(value).trim()
  return languageAliases[key] || key
}

const getCoachLanguageCodes = (coach: any) => {
  const raw = Array.isArray(coach?.languages)
    ? coach.languages
    : String(coach?.languages || '').split(/[,\s/]+/)
  return raw.map(normalizeLanguageCode).filter(Boolean)
}

const getLanguageLabel = (value: unknown) => {
  const code = normalizeLanguageCode(value)
  return coachLanguages.find((lang) => lang.id === code)?.name || String(value || '')
}

const equipmentOptionLabels: Record<string, string> = {
  self_rent: '自行租借',
  own_equipment: '自備裝備',
  class_time_help: '課程時間內協助',
  extra_time_help: '加購協助時段',
}

const getEquipmentOptionLabel = (option?: string | null, needsEquipment?: boolean) => {
  if (option && equipmentOptionLabels[option]) return equipmentOptionLabels[option]
  return needsEquipment ? '需要協助' : '不需協助'
}

const languageRequiresCoach = (value: unknown) => ['en', 'yue'].includes(normalizeLanguageCode(value))

const templateHasCoachRestriction = (template: any) => Boolean(
  template?.minimum_coach_price_level ||
  (Array.isArray(template?.allowed_coaches) && template.allowed_coaches.length > 0),
)

const coachPriceLevelOrder = ['Lv1', 'Lv2', 'Lv3', 'director']

const coachPriceLevelLabels: Record<string, string> = {
  Lv1: 'Lv1',
  Lv2: 'Lv2',
  Lv3: 'Lv3',
  director: '校長 / 總監',
}

const coachAbilityLabels: Record<string, string> = {
  no_exp: '等級 0',
  level1: '等級 1',
  level2: '等級 2',
  level3: '等級 3',
  level4: '等級 4',
  level5: '等級 5',
  entry: '等級 1',
  basic: '等級 2',
  intermediate: '等級 3',
  advanced: '等級 4',
  expert: '等級 6',
  level6: '等級 6',
}

const getCoachPriceLevel = (coach: any) => String(coach?.price_level || 'Lv1').trim() || 'Lv1'

const getCoachPriceLevelLabel = (level: unknown) => {
  const key = String(level || '').trim()
  return coachPriceLevelLabels[key] || key || 'Lv1'
}

const getCoachAbilityLabel = (level: unknown) => {
  const key = String(level || '').trim()
  return coachAbilityLabels[key] || key
}

const coachAbilityAliases: Record<string, string[]> = {
  no_exp: ['no_exp'],
  level1: ['level1', 'entry'],
  level2: ['level2', 'basic'],
  level3: ['level3', 'intermediate'],
  level4: ['level4', 'advanced'],
  level5: ['level5', 'expert'],
  level6: ['level6', 'expert'],
}

const getStudentAbilitySummary = (counts: Record<string, number> = {}) => {
  const selected = abilityLevelOrder.filter((level) => (Number(counts[level]) || 0) > 0)
  if (selected.length === 0) return ''
  return selected
    .map((level) => {
      const count = Number(counts[level]) || 0
      const label = abilityLevels.find((item) => item.id === level)?.name || getCoachAbilityLabel(level)
      return count > 1 ? `${label} ${count}人` : label
    })
    .join('、')
}

const getCoachMatchedStudentAbilitySummary = (coach: any, counts: Record<string, number> = {}) => {
  const selected = abilityLevelOrder.filter((level) => (Number(counts[level]) || 0) > 0)
  if (selected.length === 0) return ''
  const coachLevels = Array.isArray(coach?.ability_levels)
    ? coach.ability_levels.map((level: unknown) => String(level || '').trim()).filter(Boolean)
    : []
  const matched = coachLevels.length === 0
    ? selected
    : selected.filter((level) => {
      const aliases = coachAbilityAliases[level] || [level]
      return aliases.some((alias) => coachLevels.includes(alias))
    })
  return getStudentAbilitySummary(
    (matched.length > 0 ? matched : selected).reduce<Record<string, number>>((result, level) => {
      result[level] = counts[level]
      return result
    }, {}),
  )
}

const getCoachCertificationText = (coach: any) => {
  if (coach?.certification_text) return coach.certification_text
  if (!Array.isArray(coach?.certifications)) return ''
  return coach.certifications
    .map((item: any) => item?.text || [item?.certificate, item?.level, item?.note].filter(Boolean).join(' '))
    .filter(Boolean)
    .join(' / ')
}

const isCourseCategoryForService = (category: any, serviceType: ServiceType) =>
  category?.service_type === serviceType

const mainSteps = [
  { id: 1, title: '服務選擇' },
  { id: 2, title: '課程設定' },
  { id: 3, title: '資料確認' },
  { id: 4, title: '報名完成' },
]

const SKI_STEP2_FIELDS = [
  'category', 'resort', 'courseType', 'people', 'ability', 'template',
  'date', 'timeSlot', 'coach', 'equipment',
]

const PHOTO_STEP2_FIELDS = [
  'category', 'resort', 'courseType', 'template', 'date', 'timeSlot',
]

const getLessonDurationKey = (durationHours?: number | null) => {
  if (!durationHours) return 'any'
  return Number(durationHours) >= 5 ? 'full_day' : 'half_day'
}

const getSessionPeriodKey = (durationHours?: number | null, startTime?: string | null) => {
  if (durationHours && getLessonDurationKey(durationHours) === 'full_day') return 'all_day'
  if (!startTime) return 'any'
  return Number(startTime.substring(0, 2)) < 12 ? 'morning' : 'afternoon'
}

const filterEquipmentTimeSlotsForSelection = (
  slots: any[],
  equipmentOption: string | null,
  selectedTemplate: any,
  selectedSession: any,
) => {
  const internalOption = equipmentOption === 'extra_time_help' ? 'purchaseAssistanceTime' : equipmentOption
  const durationKey = getLessonDurationKey(selectedTemplate?.duration_hours)
  const periodKey = getSessionPeriodKey(selectedTemplate?.duration_hours, selectedSession?.start_time)

  return slots
    .filter((slot) => slot.is_active !== false)
    .filter((slot) => !slot.equipment_option || slot.equipment_option === internalOption)
    .filter((slot) => {
      const templateIds = Array.isArray(slot.course_template_ids) ? slot.course_template_ids.map(Number) : []
      return templateIds.length === 0 || templateIds.includes(Number(selectedTemplate?.id))
    })
    .filter((slot) => !slot.lesson_duration || slot.lesson_duration === 'any' || slot.lesson_duration === durationKey)
    .filter((slot) => !slot.session_period || slot.session_period === 'any' || slot.session_period === periodKey)
    .sort((a, b) => (a.display_order || 0) - (b.display_order || 0))
}

const formatEquipmentSlotTime = (slot: any) => {
  if (slot?.start_time && slot?.end_time) {
    return `${String(slot.start_time).substring(0, 5)} - ${String(slot.end_time).substring(0, 5)}`
  }
  if (slot?.start_time) return String(slot.start_time).substring(0, 5)
  return ''
}

const getEquipmentSlotDayLabel = (slot: any) => (
  slot?.day_type === 'previous_day' ? '課程前一日' : '課程當日'
)

const shiftDateKey = (dateKey: string, dayOffset: number) => {
  const date = parseDateKey(dateKey)
  date.setDate(date.getDate() + dayOffset)
  return toDateKey(date)
}

const getEquipmentAssistanceDateKey = (slot: any, courseDateKey: string) => (
  slot?.day_type === 'previous_day' ? shiftDateKey(courseDateKey, -1) : courseDateKey
)

const getEquipmentSlotScheduleLines = (slot: any, courseDateKeys: string[] = []) => {
  const timeText = formatEquipmentSlotTime(slot)
  return [...courseDateKeys].sort().map((courseDateKey) => {
    const assistanceDateKey = getEquipmentAssistanceDateKey(slot, courseDateKey)
    return `${formatDateKey(assistanceDateKey)}${timeText ? ` ${timeText}` : ''}`
  })
}

const getFirstCourseDateKeys = (courseDateKeys: string[] = []) => {
  const first = [...courseDateKeys].sort()[0]
  return first ? [first] : []
}

const getEquipmentSlotLabel = (slot: any, courseDateKeys: string[] = []) => {
  const dayLabel = getEquipmentSlotDayLabel(slot)
  const timeText = formatEquipmentSlotTime(slot)
  const label = String(slot?.label || '').trim()
  const scheduleLines = getEquipmentSlotScheduleLines(slot, courseDateKeys)

  if (scheduleLines.length === 1) return `${dayLabel}：${scheduleLines[0]}`
  if (scheduleLines.length > 1) return `${dayLabel}：${scheduleLines.join('、')}`

  if (timeText) {
    if (!label || label === dayLabel) return `${dayLabel} ${timeText}`
    if (label.includes(timeText)) return label
    return `${label} ${timeText}`
  }

  return label || dayLabel
}

const getPurchasedEquipmentSlotLabel = (slot: any, courseDateKeys: string[] = []) => {
  const firstDayLabel = getEquipmentSlotLabel(slot, getFirstCourseDateKeys(courseDateKeys))
  return courseDateKeys.length > 1 ? `${firstDayLabel}（費用只加第一天）` : firstDayLabel
}

export default function BookingFlowPage() {
  const navigate = useNavigate()
  const { user, loading: authLoading } = useAuth()
  const membershipUrl = useSiteLink('/membership')
  const bookingUrl = useSiteLink('/booking')
  const [searchParams] = useSearchParams()
  const requestedService = searchParams.get('service')
  const staffPreparing = searchParams.get('staff_prepare') === '1'
  const staffConsoleUrl = useSiteLink('/console/booking-links')
  const [staffOperator, setStaffOperator] = useState(false)
  const [staffOperatorLoading, setStaffOperatorLoading] = useState(staffPreparing)
  const staffPrepareMode = staffPreparing && staffOperator

  useEffect(() => {
    if (!staffPreparing) return
    let cancelled = false
    fetchAdminMe().then(result => {
      if (!cancelled) setStaffOperator(hasAdminPermission(result.user, 'orders'))
    }).finally(() => { if (!cancelled) setStaffOperatorLoading(false) })
    return () => { cancelled = true }
  }, [staffPreparing])

  // ===== 流程狀態 =====
  const [currentStep, setCurrentStep] = useState<MainStep>(() =>
    searchParams.get('resume_checkout') === '1' && useBookingStore.getState().cart.length > 0 ? 3 : 1,
  )
  const [serviceType, setServiceType] = useState<ServiceType | ''>(
    requestedService === 'photo' || requestedService === 'ski' ? requestedService : ''
  )
  const [step2Index, setStep2Index] = useState(0) // Step 2 的子欄位索引
  const lastPositionedStep = useRef('')
  const [appendTargetGroupId, setAppendTargetGroupId] = useState<string | null>(null)
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null)

  // UI 狀態
  const [isCartOpen, setIsCartOpen] = useState(() => searchParams.get('rebook') === '1' && useBookingStore.getState().cart.length > 0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: ToastType; isOpen: boolean }>({
    message: '', type: 'info', isOpen: false,
  })
  const [loadingMessage, setLoadingMessage] = useState('')
  const [loadingDetail, setLoadingDetail] = useState('')
  const [loadingSteps, setLoadingSteps] = useState<string[]>([])
  const [loadingStepIndex, setLoadingStepIndex] = useState(0)

  // ===== Zustand store =====
  const store = useBookingStore()
  const {
    cart, replaceCart, clearCart, removeFromCart, removeCourseFromGroup,
    selectedCourseCategory, selectedCourseCategoryName, selectedCourseType,
    selectedResort, selectedResortName, selectedCampusId, selectedCampusName,
    peopleCount, hasUnder6, under7CanSelfSki, abilityLevelCounts,
    selectedAbilityLevel, selectedCoach, selectedLanguage,
    selectedCourseTemplate, selectedDate, selectedTimeSlot,
    needEquipment, equipmentOption,
    equipmentAssistanceTimeSlotId, equipmentAssistanceTimeLabel,
    setSelectedCourseCategory, setSelectedCourseType,
    setSelectedResort, setPeopleCount, setHasUnder6, setUnder7CanSelfSki, setAbilityLevelCount,
    setSelectedAbilityLevel, setSelectedCoach, setSelectedLanguage,
    setSelectedCourseTemplate, setSelectedDate, setSelectedTimeSlot,
    setNeedEquipment, setEquipmentOption, setEquipmentAssistanceTimeSlot,
    startNewReservationGroup, addCourseToCurrentGroup, setCurrentGroupFees, finishCurrentGroupAndAddToCart,
  } = store

  // ===== API 資料 =====
  const [courseCategories, setCourseCategories] = useState<any[]>([])
  const [courseTypes, setCourseTypes] = useState<any[]>([])
  const [resorts, setResorts] = useState<any[]>([])
  const [coaches, setCoaches] = useState<any[]>([])
  const [templates, setTemplates] = useState<any[]>([])
  const [sessions, setSessions] = useState<any[]>([])
  const [isCoachesLoading, setIsCoachesLoading] = useState(false)
  const [isTemplatesLoading, setIsTemplatesLoading] = useState(false)
  const [selectedCourseDateKeys, setSelectedCourseDateKeys] = useState<string[]>([])
  const [calendarMonth, setCalendarMonth] = useState(() => new Date())
  const [dateInfo, setDateInfo] = useState<{
    month?: string
    booking_open_date: string | null
    booking_close_date: string | null
    course_start_date: string | null
    course_end_date: string | null
    available_dates: string[]
    shared_class_dates?: Record<string, Array<{
      start_time: string
      end_time: string
      status: 'collecting' | 'ready'
      registered_students: number
      minimum_students: number
      remaining_capacity: number
    }>>
  } | null>(null)
  const [coachSearchTerm, setCoachSearchTerm] = useState('')
  const [coachLevelFilter, setCoachLevelFilter] = useState('all')

  // 聯絡資料
  const [contactInfo, setContactInfo] = useState({
    name: memberContactName(user?.name, user?.email),
    email: user?.email || '',
    phone: '',
    messengerType: '',
    messengerId: '',
  })
  const [discountCode, setDiscountCode] = useState('')
  const [discountPreviewResult, setDiscountPreviewResult] = useState<{
    key: string
    preview: DiscountPreviewResponse
  } | null>(null)
  const [isDiscountPreviewLoading, setIsDiscountPreviewLoading] = useState(false)
  const [referrer, setReferrer] = useState('')
  const [referrerDetail, setReferrerDetail] = useState('')
  const [messengerOptions, setMessengerOptions] = useState<SelectOption[]>(MESSENGER_OPTIONS)
  const [referralSourceOptions, setReferralSourceOptions] = useState<SelectOption[]>(REFERRAL_SOURCE_OPTIONS)
  const staffLinkToken = searchParams.get('staff_link') || ''
  const [staffLinkInfo, setStaffLinkInfo] = useState<{ title: string; campus: { id: number; name: string }; created_by: string; cart_snapshot: CartItem[] } | null>(null)
  const [staffLinkStatus, setStaffLinkStatus] = useState<'none' | 'loading' | 'valid' | 'invalid'>(staffLinkToken ? 'loading' : 'none')
  const staffSelectedCart = Boolean(staffLinkInfo?.cart_snapshot?.length)
  const [paymentMethod, setPaymentMethod] = useState<'bank' | 'card'>('bank')
  const [acceptedPolicy, setAcceptedPolicy] = useState(false)

  // 預約送出後的付款階段資訊
  const [submittedReservation, setSubmittedReservation] = useState<SubmittedReservation | null>(null)
  const [submittedCart, setSubmittedCart] = useState<CartItem[]>([])
  const [createdReservationIds, setCreatedReservationIds] = useState<number[]>([])
  const [paymentAccessTokens, setPaymentAccessTokens] = useState<Record<number, string>>({})
  const [paymentInfoError, setPaymentInfoError] = useState('')
  const [completionNotice, setCompletionNotice] = useState('')
  const [completionFlow, setCompletionFlow] = useState<CompletionFlow>('payment')
  const [senderAccount, setSenderAccount] = useState('')
  const referralSourceValue = useMemo(() => {
    const source = referrer.trim()
    const detail = referrerDetail.trim()
    if (!source) return ''
    if (!detail) return source
    return `${source}：${detail}`
  }, [referrer, referrerDetail])
  const discountPreviewKey = JSON.stringify([cart, contactInfo, discountCode.trim(), referralSourceValue])
  const discountPreview = discountPreviewResult?.key === discountPreviewKey
    ? discountPreviewResult.preview
    : null

  // 排課失敗 modal 狀態
  const [schedulingFailed, setSchedulingFailed] = useState<{
    isOpen: boolean
    message: string
    conflictDetails: any
    reservationGroupIds: number[]
  }>({ isOpen: false, message: '', conflictDetails: null, reservationGroupIds: [] })
  const failedCartSignatureRef = useRef('')

  // 進階排課確認 modal
  const [superConfirmOpen, setSuperConfirmOpen] = useState(false)

  // 同步 user 資訊
  useEffect(() => {
    if (user) {
      setContactInfo((prev) => ({
        ...prev,
        name: prev.name || memberContactName(user.name, user.email),
        email: prev.email || user.email || '',
      }))
    }
  }, [user])

  const activeStep2Fields = serviceType === 'photo'
    ? PHOTO_STEP2_FIELDS
    : templates.some((template: any) => template.id === selectedCourseTemplate && template.shared_class_enabled)
      ? SKI_STEP2_FIELDS.filter((field) => field !== 'coach')
      : SKI_STEP2_FIELDS
  const currentSkiField = activeStep2Fields[step2Index]

  // 載入後台可編輯的訂單表單選項；沒有設定時使用預設值。
  useEffect(() => {
    let cancelled = false
    fetchSiteContent({ content_type: 'setting', location_key: 'booking.form.options', limit: 1 })
      .then((items) => {
        if (cancelled) return
        const metadata = items?.[0]?.metadata || {}
        setMessengerOptions(normalizeSelectOptions(metadata.messenger_options, MESSENGER_OPTIONS))
        setReferralSourceOptions(normalizeSelectOptions(metadata.referral_source_options, REFERRAL_SOURCE_OPTIONS))
      })
      .catch((e) => {
        console.error(e)
        if (!cancelled) {
          setMessengerOptions(MESSENGER_OPTIONS)
          setReferralSourceOptions(REFERRAL_SOURCE_OPTIONS)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!staffLinkToken) {
      setStaffLinkInfo(null)
      setStaffLinkStatus('none')
      return
    }
    let cancelled = false
    setStaffLinkInfo(null)
    setStaffLinkStatus('loading')
    resolveStaffBookingLink(staffLinkToken)
      .then((info) => {
        if (!cancelled) {
          setStaffLinkInfo(info)
          if (info.cart_snapshot?.length) {
            replaceCart(info.cart_snapshot)
            setCurrentStep(3)
          }
          setStaffLinkStatus('valid')
        }
      })
      .catch(() => { if (!cancelled) setStaffLinkStatus('invalid') })
    return () => { cancelled = true }
  }, [staffLinkToken, replaceCart])

  // 載入課程大類與雪場列表
  useEffect(() => {
    if (serviceType) {
      fetchCourseCategories(serviceType)
        .then((data: any) => setCourseCategories(Array.isArray(data) ? data : []))
        .catch((e) => { console.error(e); setCourseCategories([]) })
    } else {
      setCourseCategories([])
    }
  }, [serviceType])

  useEffect(() => {
    if (serviceType && resorts.length === 0) {
      fetchResorts().then(setResorts).catch(console.error)
    }
  }, [serviceType, resorts.length])

  // 載入課程類型（當大類+雪場選好）
  useEffect(() => {
    if (selectedCourseCategory && selectedResort) {
      fetchCourseTypes(selectedCourseCategory, selectedResort)
        .then((data: any) => setCourseTypes(Array.isArray(data) ? data : []))
        .catch((e) => { console.error(e); setCourseTypes([]) })
    } else {
      setCourseTypes([])
    }
  }, [selectedCourseCategory, selectedResort])

  // 載入教練（日期與時段選好後，排除該時段已忙碌的教練）
  useEffect(() => {
    let cancelled = false
    const coachStepIndex = activeStep2Fields.findIndex((field) => field === 'coach')
    const selectedDates = [...selectedCourseDateKeys].sort()
    if (
      serviceType === 'ski' &&
      selectedResort &&
      selectedCourseType &&
      selectedAbilityLevel &&
      selectedCourseTemplate &&
      selectedDates.length > 0 &&
      selectedTimeSlot &&
      coachStepIndex >= 0 &&
      step2Index >= coachStepIndex
    ) {
      setIsCoachesLoading(true)
      fetchCoaches({
        resort: selectedResort,
        courseType: selectedCourseType.toString(),
        abilityLevel: selectedAbilityLevel,
        courseTemplate: selectedCourseTemplate,
        courseDates: selectedDates.join(','),
        timeSlot: selectedTimeSlot,
      }).then((data: any) => {
        if (cancelled) return
        setCoaches(Array.isArray(data) ? data : (data?.coach_list || []))
      }).catch((e) => {
        if (cancelled) return
        console.error(e)
        setCoaches([])
      }).finally(() => {
        if (!cancelled) setIsCoachesLoading(false)
      })
    } else {
      setCoaches([])
      setIsCoachesLoading(false)
    }

    return () => {
      cancelled = true
    }
  }, [
    serviceType, selectedResort, selectedCourseType, selectedAbilityLevel,
    selectedCourseTemplate, selectedCourseDateKeys, selectedTimeSlot,
    step2Index,
  ])

  // 載入課程模板（當課程類型+雪場選好）
  useEffect(() => {
    let cancelled = false
    const templateStepIndex = serviceType === 'photo' ? 3 : 5
    if (selectedResort && selectedCourseType && step2Index >= templateStepIndex) {
      setIsTemplatesLoading(true)
      fetchCourseTemplates({ resort: selectedResort, course_type_id: selectedCourseType })
        .then((data: any) => {
          if (cancelled) return
          const list = Array.isArray(data) ? data : []
          setTemplates(list.filter(isCourseTemplateOpenForBooking))
        })
        .catch((e) => {
          if (cancelled) return
          console.error(e)
          setTemplates([])
        })
        .finally(() => {
          if (!cancelled) setIsTemplatesLoading(false)
        })
    } else {
      setTemplates([])
      setIsTemplatesLoading(false)
    }

    return () => {
      cancelled = true
    }
  }, [serviceType, selectedResort, selectedCourseType, step2Index])

  // 載入時段（當課程模板選好；若已選日期，會帶 date 一起檢查容量）
  useEffect(() => {
    if (selectedCourseTemplate) {
      const levels = Object.entries(abilityLevelCounts).filter(([, count]) => Number(count) > 0)
      fetchCourseSessions(selectedCourseTemplate, selectedDate || undefined, {
        campus_id: selectedCampusId, resort: selectedResort,
        ability_level: levels.length === 1 ? levels[0][0] : null,
        language: selectedLanguage || 'zh', people_count: peopleCount,
      })
        .then((data: any) => setSessions(data))
        .catch((e) => { console.error(e); setSessions([]) })
    }
  }, [selectedCourseTemplate, selectedDate, selectedCampusId, selectedResort, abilityLevelCounts, selectedLanguage, peopleCount])

  // 載入可預約日期資訊（當模板或日曆月份改變）
  useEffect(() => {
    let cancelled = false
    if (selectedCourseTemplate) {
      const levels = Object.entries(abilityLevelCounts).filter(([, count]) => Number(count) > 0)
      fetchAvailableDates(selectedCourseTemplate, formatCalendarMonthKey(calendarMonth), {
        campus_id: selectedCampusId, resort: selectedResort,
        ability_level: levels.length === 1 ? levels[0][0] : null,
        language: selectedLanguage || 'zh',
      })
        .then((data: any) => {
          if (!cancelled) setDateInfo(data)
        })
        .catch((e) => {
          if (cancelled) return
          console.error(e)
          setDateInfo(null)
        })
    } else {
      setDateInfo(null)
    }

    return () => {
      cancelled = true
    }
  }, [selectedCourseTemplate, calendarMonth, selectedCampusId, selectedResort, abilityLevelCounts, selectedLanguage])

  useEffect(() => {
    if (currentStep !== 3 || submittedReservation || cart.length === 0) {
      setDiscountPreviewResult(null)
      setIsDiscountPreviewLoading(false)
      return
    }

    let cancelled = false
    setIsDiscountPreviewLoading(true)
    const timer = window.setTimeout(async () => {
      try {
        const preview = await previewDiscounts({
          cart,
          contact: { ...contactInfo, referralSource: referralSourceValue },
          discount_code: discountCode.trim() || undefined,
        })
        if (!cancelled) setDiscountPreviewResult({ key: discountPreviewKey, preview })
      } catch (e) {
        console.error(e)
        if (!cancelled) setDiscountPreviewResult(null)
      } finally {
        if (!cancelled) setIsDiscountPreviewLoading(false)
      }
    }, 350)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [cart, contactInfo, currentStep, discountCode, discountPreviewKey, referralSourceValue, submittedReservation])

  useEffect(() => {
    if (!failedCartSignatureRef.current) return
    if (getCartEditSignature(cart) === failedCartSignatureRef.current) return

    failedCartSignatureRef.current = ''
    setSchedulingFailed({ isOpen: false, message: '', conflictDetails: null, reservationGroupIds: [] })
  }, [cart])

  // ===== Helpers =====
  const showToast = (message: string, type: ToastType = 'info') => {
    setToast({ message, type, isOpen: true })
  }

  const startLoading = (message: string, detail = '', steps: string[] = []) => {
    setLoadingMessage(message)
    setLoadingDetail(detail)
    setLoadingSteps(steps)
    setLoadingStepIndex(0)
  }

  const stopLoading = () => {
    setLoadingMessage('')
    setLoadingDetail('')
    setLoadingSteps([])
    setLoadingStepIndex(0)
  }

  useEffect(() => {
    if (!loadingMessage || loadingSteps.length <= 1) return

    const timer = window.setInterval(() => {
      setLoadingStepIndex((index) => Math.min(index + 1, loadingSteps.length - 1))
    }, 4200)

    return () => window.clearInterval(timer)
  }, [loadingMessage, loadingSteps.length])

  const filteredCoaches = useMemo(() => {
    let list = coaches
    if (selectedLanguage) {
      list = list.filter((c: any) => getCoachLanguageCodes(c).includes(selectedLanguage))
    }
    if (coachLevelFilter !== 'all') {
      list = list.filter((c: any) => getCoachPriceLevel(c) === coachLevelFilter)
    }
    if (coachSearchTerm) {
      const keyword = coachSearchTerm.trim().toLowerCase()
      list = list.filter((c: any) => String(c.name || '').toLowerCase().includes(keyword))
    }
    return list
  }, [coaches, selectedLanguage, coachLevelFilter, coachSearchTerm])

  const coachLevelOptions = useMemo(() => {
    const levels = Array.from(new Set(coaches.map(getCoachPriceLevel).filter(Boolean)))
    return coachPriceLevelOrder
      .filter((level) => levels.includes(level))
      .concat(levels.filter((level) => !coachPriceLevelOrder.includes(level)))
      .map((level) => ({
        value: level,
        label: getCoachPriceLevelLabel(level),
      }))
  }, [coaches])

  useEffect(() => {
    if (coachLevelFilter === 'all') return
    if (!coachLevelOptions.some((option) => option.value === coachLevelFilter)) {
      setCoachLevelFilter('all')
    }
  }, [coachLevelFilter, coachLevelOptions])

  const serviceCourseCategories = useMemo(
    () => courseCategories.filter((category: any) => serviceType && isCourseCategoryForService(category, serviceType)),
    [courseCategories, serviceType],
  )

  const selectedCourseCategoryInfo = useMemo(
    () => serviceCourseCategories.find((category: any) => category.id === selectedCourseCategory),
    [serviceCourseCategories, selectedCourseCategory],
  )

  const selectedCategoryResortNames = useMemo(
    () => (
      Array.isArray(selectedCourseCategoryInfo?.available_resorts)
        ? selectedCourseCategoryInfo.available_resorts.map((name: any) => String(name)).filter(Boolean)
        : []
    ),
    [selectedCourseCategoryInfo],
  )

  const resortsForSelectedCategory = useMemo(() => {
    if (!selectedCourseCategoryInfo) return []
    const resortMap = new Map<string, any>()
    resorts.forEach((resort: any) => {
      if (resort?.name) resortMap.set(String(resort.name), resort)
      if (resort?.display_name) resortMap.set(String(resort.display_name), resort)
    })

    const seen = new Set<string>()
    return selectedCategoryResortNames
      .map((name: string) => {
        const resort = resortMap.get(name)
        const resolved = resort || {
          name,
          display_name: name,
          auto_scheduling_enabled: true,
          equipment_rental_items: [],
          equipment_time_slots: [],
        }
        if (staffLinkInfo?.campus?.id && Array.isArray(resolved.campuses)) {
          return { ...resolved, campuses: resolved.campuses.filter((campus: any) => campus.id === staffLinkInfo.campus.id) }
        }
        return resolved
      })
      .filter((resort: any) => {
        const key = String(resort.name || resort.display_name)
        if (!key || seen.has(key)) return false
        seen.add(key)
        return true
      })
  }, [resorts, selectedCategoryResortNames, selectedCourseCategoryInfo, staffLinkInfo])

  const handleSelectService = (type: ServiceType) => {
    if (serviceType === type) return
    setServiceType(type)
    setStep2Index(0)
    setSelectedCourseCategory(null as any, null as any)
    setSelectedResort(null, null)
    setSelectedCourseType(null)
    setPeopleCount(1)
    setHasUnder6(false)
    setSelectedCoach(null)
    setSelectedLanguage(null)
    setSelectedCourseTemplate(null)
    setSelectedDate(null)
    setSelectedCourseDateKeys([])
    setSelectedTimeSlot(null)
    setNeedEquipment(false)
    setEquipmentOption(null)
    setEquipmentAssistanceTimeSlot(null)
    setCourseCategories([])
    setCourseTypes([])
    setCoaches([])
    setTemplates([])
    setSessions([])
    setDateInfo(null)
  }

  const handleSelectCourseCategory = (id: number, name: string) => {
    setSelectedCourseCategory(id, name)
    setSelectedResort(null, null)
    setSelectedCourseType(null)
    setSelectedCoach(null)
    setSelectedCourseTemplate(null)
    setSelectedDate(null)
    setSelectedCourseDateKeys([])
    setSelectedTimeSlot(null)
    setEquipmentAssistanceTimeSlot(null)
    setCourseTypes([])
    setCoaches([])
    setTemplates([])
    setSessions([])
    setDateInfo(null)
  }

  const handleSelectResort = (resort: string, resortName: string, campusId?: number, campusName?: string) => {
    setSelectedResort(resort, resortName, campusId, campusName)
    setSelectedCourseType(null)
    setSelectedCoach(null)
    setSelectedCourseTemplate(null)
    setSelectedDate(null)
    setSelectedCourseDateKeys([])
    setSelectedTimeSlot(null)
    setEquipmentAssistanceTimeSlot(null)
    setCourseTypes([])
    setCoaches([])
    setTemplates([])
    setSessions([])
    setDateInfo(null)
  }

  useEffect(() => {
    if (!selectedCourseCategoryInfo || !selectedResort) return
    if (selectedCategoryResortNames.includes(selectedResort)) return

    setSelectedResort(null, null)
    setSelectedCourseType(null)
    setSelectedCoach(null)
    setSelectedCourseTemplate(null)
    setSelectedDate(null)
    setSelectedCourseDateKeys([])
    setSelectedTimeSlot(null)
    setEquipmentAssistanceTimeSlot(null)
    setCourseTypes([])
    setCoaches([])
    setTemplates([])
    setSessions([])
    setDateInfo(null)
  }, [
    selectedCourseCategoryInfo, selectedCategoryResortNames, selectedResort,
    setSelectedResort, setSelectedCourseType, setSelectedCoach, setSelectedCourseTemplate,
    setSelectedDate, setSelectedTimeSlot, setEquipmentAssistanceTimeSlot,
  ])

  const handleSelectCourseType = (id: number) => {
    setSelectedCourseType(id)
    setSelectedCoach(null)
    setSelectedCourseTemplate(null)
    setSelectedDate(null)
    setSelectedCourseDateKeys([])
    setSelectedTimeSlot(null)
    setEquipmentAssistanceTimeSlot(null)
    setCoaches([])
    setTemplates([])
    setSessions([])
    setDateInfo(null)
  }

  const handleSelectLanguage = (lang: string | null) => {
    setSelectedLanguage(lang)
    setSelectedCoach(null)
  }

  const handleSelectCourseTemplate = (id: number) => {
    const template = templates.find((item: any) => Number(item.id) === Number(id))
    const minimumGroupSize = template?.shared_class_enabled ? 1 : Number(template?.minimum_group_size || 1)
    if (template && peopleCount < minimumGroupSize) {
      setToast({
        message: `此課程至少 ${minimumGroupSize} 人才能預約`,
        type: 'warning',
        isOpen: true,
      })
      return
    }
    const studentLevelRule = getTemplateStudentLevelRule(template, abilityLevelCounts, selectedAbilityLevel)
    if (studentLevelRule.insufficient) {
      setToast({
        message: `此課程只開放等級 ${studentLevelRule.requiredRank} 以上學員，請調整學員等級或選擇其他課程`,
        type: 'warning',
        isOpen: true,
      })
      return
    }
    setSelectedCourseTemplate(id)
    if (template) {
      setCalendarMonth(parseDateKey(getCalendarStartDateKey(template)))
    }
    if (!appendTargetGroupId) setSelectedCoach(null)
    setSelectedDate(null)
    setSelectedCourseDateKeys([])
    setSelectedTimeSlot(null)
    setEquipmentAssistanceTimeSlot(null)
    setSessions([])
    setDateInfo(null)
  }

  const handleToggleCourseDate = (dateKey: string) => {
    if (!isBookableDateKey(dateKey, dateInfo)) return
    const selectedTemplate = templates.find((template: any) => template.id === selectedCourseTemplate)
    const nextDates = selectedTemplate?.shared_class_enabled
      ? (selectedCourseDateKeys.includes(dateKey) ? [] : [dateKey])
      : selectedCourseDateKeys.includes(dateKey)
      ? selectedCourseDateKeys.filter((item) => item !== dateKey)
      : [...selectedCourseDateKeys, dateKey]
    const sortedDates = [...nextDates].sort()

    setSelectedCourseDateKeys(sortedDates)
    setSelectedDate(sortedDates[0] || null)
    if (!appendTargetGroupId) setSelectedCoach(null)
    setSelectedTimeSlot(null)
    setEquipmentAssistanceTimeSlot(null)
  }

  const handleSelectTimeSlot = (sessionId: number | string | null) => {
    setSelectedTimeSlot(sessionId as any)
    if (!appendTargetGroupId) setSelectedCoach(null)
    setEquipmentAssistanceTimeSlot(null)
  }

  const selectedCourseDates = useMemo(
    () => [...selectedCourseDateKeys].sort(),
    [selectedCourseDateKeys],
  )
  const unavailableSelectedDates = useMemo(() => {
    const available = new Set(dateInfo?.available_dates || [])
    const today = toDateKey(new Date())
    return selectedCourseDates.filter((dateKey) => {
      if (dateKey < today) return true
      if (dateInfo?.booking_open_date && today < dateInfo.booking_open_date) return true
      if (dateInfo?.booking_close_date && today > dateInfo.booking_close_date) return true
      if (dateInfo?.course_start_date && dateKey < dateInfo.course_start_date) return true
      if (dateInfo?.course_end_date && dateKey > dateInfo.course_end_date) return true
      if (Array.isArray(dateInfo?.available_dates) && dateInfo?.month === dateKey.slice(0, 7)) {
        return !available.has(dateKey)
      }
      return false
    })
  }, [dateInfo, selectedCourseDates])

  const equipmentTimeSlots = useMemo(() => {
    const resort = resorts.find((r: any) => r.name === selectedResort)
    const selectedTemplateInfo = templates.find((t: any) => t.id === selectedCourseTemplate)
    const selectedSessionInfo = sessions.find((s: any) => s.id === selectedTimeSlot)
    return filterEquipmentTimeSlotsForSelection(
      ((resort?.equipment_time_slots || []) as any[]),
      equipmentOption,
      selectedTemplateInfo,
      selectedSessionInfo,
    )
  }, [resorts, selectedResort, templates, selectedCourseTemplate, sessions, selectedTimeSlot, equipmentOption])

  const selectedTemplateForCoachRule = useMemo(
    () => templates.find((t: any) => t.id === selectedCourseTemplate) || null,
    [templates, selectedCourseTemplate],
  )
  const selectedTemplateHasCoachRestriction = templateHasCoachRestriction(selectedTemplateForCoachRule)

  useEffect(() => {
    if (equipmentOption !== 'extra_time_help' || !equipmentAssistanceTimeSlotId) return
    const selectedSlot = equipmentTimeSlots.find((slot: any) => Number(slot.id) === Number(equipmentAssistanceTimeSlotId))
    if (!selectedSlot) return
    const nextLabel = getPurchasedEquipmentSlotLabel(selectedSlot, selectedCourseDates)
    if (nextLabel && nextLabel !== equipmentAssistanceTimeLabel) {
      setEquipmentAssistanceTimeSlot(equipmentAssistanceTimeSlotId, nextLabel)
    }
  }, [
    equipmentOption, equipmentAssistanceTimeSlotId, equipmentAssistanceTimeLabel,
    equipmentTimeSlots, selectedCourseDates, setEquipmentAssistanceTimeSlot,
  ])

  // ===== 步驟導航 =====
  useEffect(() => {
    if (currentStep !== 2 || currentSkiField !== 'courseType') return
    if (!selectedCourseCategory || !selectedResort) return
    if (courseTypes.length !== 1) return

    const onlyCourseType = courseTypes[0]
    if (!onlyCourseType?.id) return
    if (selectedCourseType !== onlyCourseType.id) {
      handleSelectCourseType(onlyCourseType.id)
    }
    const nextIndex = activeStep2Fields.findIndex((field) => field === 'courseType') + 1
    if (nextIndex > 0 && nextIndex < activeStep2Fields.length) {
      setStep2Index(nextIndex)
    }
  }, [
    currentStep, currentSkiField, selectedCourseCategory, selectedResort,
    selectedCourseType, courseTypes, activeStep2Fields,
  ])

  const canGoNext = useMemo(() => {
    if (currentStep === 1) return !!serviceType
    if (currentStep === 2) {
      if (!serviceType) return false
      switch (currentSkiField) {
        case 'category': return !!selectedCourseCategory && serviceCourseCategories.some((category: any) => category.id === selectedCourseCategory)
        case 'resort': return !!selectedResort && !!selectedCampusId && resortsForSelectedCategory.some((resort: any) => resort.name === selectedResort && resort.campuses?.some((campus: any) => campus.id === selectedCampusId))
        case 'courseType': return !!selectedCourseType
        case 'people': return peopleCount > 0 && !(hasUnder6 && !under7CanSelfSki && peopleCount > 1)
        case 'ability': return getAssignedAbilityCount(abilityLevelCounts) === peopleCount
        case 'coach': return !!selectedTemplateForCoachRule?.shared_class_enabled || selectedTemplateHasCoachRestriction || !languageRequiresCoach(selectedLanguage) || !!selectedCoach
        case 'template': return !!selectedCourseTemplate
        case 'date': return !!selectedDate && selectedCourseDates.length > 0 && unavailableSelectedDates.length === 0
        case 'timeSlot': return !!selectedTimeSlot
        case 'equipment':
          return !!equipmentOption && (
            equipmentOption !== 'extra_time_help' ||
            equipmentTimeSlots.some((slot: any) => slot.id === equipmentAssistanceTimeSlotId)
          )
        default: return false
      }
    }
    if (currentStep === 3) {
      if (createdReservationIds.length > 0 && !submittedReservation) return false
      // 3a 送出訂單前：要求電話 + 通訊軟體 + 通訊 ID + 同意條款
      if (!submittedReservation) {
        if (cart.some(group => group.totalPrice == null) && !discountPreview) return false
        return cart.length > 0 && !!contactInfo.name.trim() && !!contactInfo.phone && !!contactInfo.messengerType && !!contactInfo.messengerId.trim() && (!!referralSourceValue || !!staffLinkInfo) && acceptedPolicy
      }
      // 3b 付款階段：銀行可先稍後匯款；若要送出已匯款資訊才需要 5 碼後綴。
      if (!submittedReservation.payment_methods.includes(paymentMethod === 'bank' ? 'bank_transfer' : 'newebpay')) return false
      if (paymentMethod === 'bank') return senderAccount.length === 5
      return true
    }
    return false
  }, [
    currentStep, currentSkiField, serviceType,
    selectedCourseCategory, selectedCourseType, serviceCourseCategories, resortsForSelectedCategory,
    selectedResort, selectedCampusId, peopleCount, hasUnder6, under7CanSelfSki, abilityLevelCounts, selectedAbilityLevel, selectedCoach, selectedLanguage,
    selectedTemplateHasCoachRestriction,
    selectedCourseTemplate, selectedDate, selectedCourseDates, unavailableSelectedDates, selectedTimeSlot,
    equipmentOption, equipmentAssistanceTimeSlotId, equipmentTimeSlots,
    cart, discountPreview,
    contactInfo.name, contactInfo.phone, contactInfo.messengerType, contactInfo.messengerId, referralSourceValue, staffLinkInfo, acceptedPolicy,
    submittedReservation, createdReservationIds, paymentMethod, senderAccount,
  ])

  const handleNext = async () => {
    if (!canGoNext) return

    if (currentStep === 1) {
      setCurrentStep(2)
      setStep2Index(0)
      return
    }

    if (currentStep === 2) {
      // Step 2 還有子欄位
      const isAppendingCourseToGroup = Boolean(appendTargetGroupId)
      const shouldFinishAppendAfterTimeSlot = isAppendingCourseToGroup && activeStep2Fields[step2Index] === 'timeSlot'
      if (!shouldFinishAppendAfterTimeSlot && step2Index < activeStep2Fields.length - 1) {
        setStep2Index(step2Index + 1)
        return
      }
      // Step 2 完成 → 加入購物車 → Step 3
      const addedToCart = await addCurrentToCart()
      if (addedToCart) setCurrentStep(3)
      return
    }

    if (currentStep === 3) {
      if (!submittedReservation) {
        await submitBooking()
      } else {
        await submitPayment()
      }
    }
  }

  const handleBack = () => {
    if (currentStep === 2 && step2Index > 0) {
      setStep2Index(step2Index - 1)
    } else if (currentStep === 2 && step2Index === 0) {
      setCurrentStep(1)
    } else if (currentStep === 3) {
      // 已送出訂單後不能回上一步（避免重複下單）
      if (submittedReservation || createdReservationIds.length > 0) return
      // A resumed cart has no in-progress course configuration to return to.
      if (!serviceType) {
        setCurrentStep(1)
        setStep2Index(0)
        return
      }
      setCurrentStep(2)
      setStep2Index(activeStep2Fields.length - 1)
    }
  }

  const handleRemoveCartGroup = (groupId: string) => {
    if (submittedReservation) return
    removeFromCart(groupId)
    showToast('已從訂單明細移除這組預約', 'success')
  }

  const handleRemoveCartCourse = (groupId: string, courseIndex: number) => {
    if (submittedReservation) return
    removeCourseFromGroup(groupId, courseIndex)
    showToast('已移除這堂課程', 'success')
  }

  const handleEditCartGroup = (groupId: string) => {
    if (submittedReservation) return
    const group = cart.find((item) => item.id === groupId)
    if (!group) return

    setAppendTargetGroupId(null)
    setEditingGroupId(groupId)
    setServiceType(isPhotoCartGroup(group) ? 'photo' : 'ski')
    setCurrentStep(2)
    setStep2Index(0)
    showToast('原課程已保留，完成新設定後才會替換；未完成不會變更購物車。', 'info')
  }

  const resetDraftSelection = () => {
    setEditingGroupId(null)
    setAppendTargetGroupId(null)
    setServiceType('')
    setStep2Index(0)
    setSelectedCourseCategory(null as any, null as any)
    setSelectedResort(null, null)
    setSelectedCourseType(null)
    setPeopleCount(1)
    setHasUnder6(false)
    setUnder7CanSelfSki(false)
    setSelectedCoach(null)
    setSelectedLanguage(null)
    setSelectedCourseTemplate(null)
    setSelectedDate(null)
    setSelectedCourseDateKeys([])
    setSelectedTimeSlot(null)
    setNeedEquipment(false)
    setEquipmentOption(null)
    setEquipmentAssistanceTimeSlot(null)
    setCourseCategories([])
    setCourseTypes([])
    setCoaches([])
    setTemplates([])
    setSessions([])
    setDateInfo(null)
    setCoachSearchTerm('')
    setCoachLevelFilter('all')
  }

  const handleAddCartGroup = () => {
    if (submittedReservation) return
    if (cart.some((group) => group.courses?.some((course) => course.sharedClassEnabled))) {
      showToast('團體湊班需單獨結帳，請先完成這筆報名。', 'warning')
      return
    }
    resetDraftSelection()
    setCurrentStep(1)
    showToast('請新增下一組預約，原本的訂單明細已保留', 'info')
  }

  const handleAddCourseToGroup = (groupId: string) => {
    setEditingGroupId(null)
    if (submittedReservation) return
    const group = cart.find((item) => item.id === groupId)
    const firstCourse = group?.courses?.[0]
    if (!group || !firstCourse) return
    if (firstCourse.sharedClassEnabled) {
      showToast('團體湊班每筆只能報名一堂課，請先完成這筆報名。', 'warning')
      return
    }

    const nextServiceType: ServiceType = isPhotoCartGroup(group) ? 'photo' : 'ski'
    const nextFields = nextServiceType === 'photo' ? PHOTO_STEP2_FIELDS : SKI_STEP2_FIELDS
    const templateStepIndex = nextFields.findIndex((field) => field === 'template')

    setAppendTargetGroupId(group.id)
    setServiceType(nextServiceType)
    setSelectedCourseCategory(null as any, group.courseCategory as any)
    setSelectedResort(group.resort || null, group.resortName || group.resort || null, group.campusId || null, group.campusName || null)
    setSelectedCourseType(firstCourse.courseTypeId || null)
    setPeopleCount(group.peopleCount || 1)
    setHasUnder6(false)
    setUnder7CanSelfSki(false)
    setSelectedAbilityLevel(group.abilityLevel || 'no_exp')
    Object.entries(group.abilityLevelCounts || {}).forEach(([level, count]) => {
      setAbilityLevelCount(level, Number(count) || 0)
    })
    setSelectedCoach(
      group.coach === 'any' ? null : Number(group.coach),
      group.coach === 'any' ? null : group.coachName,
    )
    setSelectedLanguage(group.language || 'zh')
    setSelectedCourseTemplate(null)
    setSelectedDate(null)
    setSelectedCourseDateKeys([])
    setSelectedTimeSlot(null)
    setNeedEquipment(Boolean(group.equipment || group.equipmentOption))
    setEquipmentOption(group.equipmentOption || null)
    setEquipmentAssistanceTimeSlot(group.equipmentAssistanceTimeSlotId, group.equipmentAssistanceTimeLabel || '')
    setCourseTypes([])
    setCoaches([])
    setTemplates([])
    setSessions([])
    setDateInfo(null)
    setCoachSearchTerm('')
    setCoachLevelFilter('all')
    setCalendarMonth(new Date())
    setCurrentStep(2)
    setStep2Index(templateStepIndex >= 0 ? templateStepIndex : 0)
    showToast(`正在加課到第 ${cart.findIndex((item) => item.id === groupId) + 1} 組，請選擇課程、日期與時段；人數、程度與教練會沿用此組。`, 'info')
  }

  const addCurrentToCart = async () => {
    if (!selectedCourseTemplate || selectedCourseDates.length === 0 || !selectedTimeSlot) return false
    if (editingGroupId && !cart.some(group => group.id === editingGroupId)) {
      showToast('原課程已移除，請從購物車重新選擇要修改的課程。', 'warning')
      return false
    }
    const otherCartGroups = cart.filter(group => group.id !== editingGroupId)
    const isSharedClass = templates.some((template: any) => template.id === selectedCourseTemplate && template.shared_class_enabled)
    if (isSharedClass && (otherCartGroups.length > 0 || appendTargetGroupId)) {
      showToast('團體湊班需單獨結帳，請先完成或清空原有預約。', 'warning')
      return false
    }
    if (otherCartGroups.some((group) => group.courses?.some((course) => course.sharedClassEnabled))) {
      showToast('團體湊班需單獨結帳，請先完成這筆報名。', 'warning')
      return false
    }
    const courseDates = [...selectedCourseDates]
    if (courseDates.length === 0) return false
    const appendTargetGroup = appendTargetGroupId
      ? cart.find((group) => group.id === appendTargetGroupId)
      : null
    if (appendTargetGroupId && !appendTargetGroup) {
      showToast('找不到要加課的預約組，請重新選擇。', 'error')
      setAppendTargetGroupId(null)
      return false
    }
    if (unavailableSelectedDates.length > 0) {
      showToast(`以下日期目前不可預約：${unavailableSelectedDates.map(formatDateKey).join('、')}`, 'warning')
      return false
    }

    if (serviceType === 'photo') {
      setPeopleCount(1)
      setSelectedCoach(null)
      setSelectedLanguage(null)
      setNeedEquipment(false)
      setEquipmentOption(null)
      setEquipmentAssistanceTimeSlot(null)
    }

    // 計算價格
    const coursesToAdd: Array<{
      date: string
      courseTypeId: number
      courseTypeName: string
      templateName: string
      durationHours: number
      price: number | null
    }> = []
    let courseFee = 0
    let coachFee = 0
    let languageFee = 0
    let equipmentRentalFee = 0
    try {
      setLoadingMessage('計算價格中...')
      const firstCourseDate = courseDates[0]
      for (const courseDate of courseDates) {
        const shouldChargeExtraEquipment = (
          equipmentOption === 'extra_time_help' &&
          courseDate === firstCourseDate &&
          !(appendTargetGroup?.equipmentRentalFee && appendTargetGroup.equipmentRentalFee > 0)
        )
        const priceEquipmentOption = serviceType === 'photo'
          ? null
          : equipmentOption === 'extra_time_help'
          ? shouldChargeExtraEquipment ? equipmentOption : null
          : equipmentOption
        const fetchedSessions = courseDate === selectedDate
          ? sessions
          : await fetchCourseSessions(selectedCourseTemplate, courseDate)
        const daySessions = Array.isArray(fetchedSessions)
          ? fetchedSessions
          : ((fetchedSessions as any)?.data || [])
        const daySession = (daySessions || []).find((item: any) => Number(item.id) === Number(selectedTimeSlot))
        if (!daySession || daySession.is_full || daySession.is_active === false) {
          throw new Error(`${formatDateKey(courseDate)} 的此時段不可預約`)
        }
        const priceData = await calculatePrice({
          template_id: selectedCourseTemplate,
          resort: selectedResort!,
          people_count: serviceType === 'photo' ? 1 : peopleCount,
          course_date: courseDate,
          coach: serviceType === 'photo' ? 'any' : (selectedCoach || 'any'),
          language: serviceType === 'photo' ? 'zh' : (selectedLanguage || 'zh'),
          equipment_option: priceEquipmentOption,
          bookings_count: 1,
        })
        const singleCourseFee = priceData.course_fee ?? priceData.price ?? 0
        coursesToAdd.push({
          date: courseDate,
          courseTypeId: priceData.course_type_id || 0,
          courseTypeName: priceData.course_type_name || '',
          templateName: priceData.course_template_name || '',
          durationHours: priceData.duration_hours || 0,
          price: priceData.course_fee ?? priceData.price,
        })
        courseFee += singleCourseFee
        coachFee += priceData.coach_fee || 0
        languageFee += priceData.language_fee || 0
        equipmentRentalFee += priceData.equipment_rental_fee || 0
      }
    } catch (e) {
      console.error(e)
      showToast(getPriceErrorMessage(e, '價格計算失敗，請重新選擇日期或時段'), 'error')
      if ((e as any)?.response?.data?.error?.includes?.('找不到對應的價格設定')) {
        const templateStepIndex = activeStep2Fields.findIndex((field) => field === 'template')
        if (templateStepIndex >= 0) setStep2Index(templateStepIndex)
      }
      return false
    } finally {
      setLoadingMessage('')
    }

    // 找時段資訊
    const session = sessions.find((s: any) => s.id === selectedTimeSlot)
    const segmentId = `${appendTargetGroup?.id || `group-${Date.now()}`}-segment-${Date.now()}`

    if (appendTargetGroup) {
      const addedCourses: Course[] = coursesToAdd.map((course) => ({
        segmentId,
        date: course.date,
        courseTypeId: course.courseTypeId,
        courseTypeName: course.courseTypeName,
        courseTemplateId: selectedCourseTemplate,
        courseTemplateName: course.templateName,
        sharedClassEnabled: isSharedClass,
        durationHours: course.durationHours,
        timeSlotId: selectedTimeSlot,
        timeSlotStart: session?.start_time || '',
        timeSlotEnd: session?.end_time || '',
        price: course.price,
      }))
      const nextCart = cart.map((group) => {
        if (group.id !== appendTargetGroup.id) return group
        const nextCourses = [...(group.courses || []), ...addedCourses]
        const nextCourseFee = Number(group.courseFee || 0) + courseFee
        const nextCoachFee = Number(group.coachFee || 0) + coachFee
        const nextLanguageFee = Number(group.languageFee || 0) + languageFee
        const nextEquipmentRentalFee = Number(group.equipmentRentalFee || 0) + equipmentRentalFee

        return {
          ...group,
          courses: nextCourses,
          courseFee: nextCourseFee,
          coachFee: nextCoachFee,
          languageFee: nextLanguageFee,
          equipmentRentalFee: nextEquipmentRentalFee,
          totalPrice: nextCourses.some((course) => course.price === null)
            ? null
            : nextCourseFee + nextCoachFee + nextLanguageFee + nextEquipmentRentalFee,
        }
      })

      replaceCart(nextCart)
      setAppendTargetGroupId(null)
      setSelectedDate(null)
      setSelectedCourseDateKeys([])
      setSelectedTimeSlot(null)
      setEquipmentAssistanceTimeSlot(null)
      showToast('已加課到同一組預約，送出時會一起排課。', 'success')
      return true
    }

    // 開啟新預約組 + 加入課程
    startNewReservationGroup()
    coursesToAdd.forEach((course) => {
      addCourseToCurrentGroup({
        segmentId,
        date: course.date,
        courseTypeId: course.courseTypeId,
        courseTypeName: course.courseTypeName,
        courseTemplateId: selectedCourseTemplate,
        courseTemplateName: course.templateName,
        sharedClassEnabled: isSharedClass,
        durationHours: course.durationHours,
        timeSlotId: selectedTimeSlot,
        timeSlotStart: session?.start_time || '',
        timeSlotEnd: session?.end_time || '',
        price: course.price,
      })
    })
    setCurrentGroupFees({ courseFee, coachFee, languageFee, equipmentRentalFee })
    finishCurrentGroupAndAddToCart(editingGroupId || undefined)
    setEditingGroupId(null)
    return true
  }

  // 走相對路徑（同 origin），由 vite proxy / nginx 轉到後端
  const getBackendURL = () => ''

  const fetchSubmittedReservationInfo = async (reservationGroupIds: number[], accessTokens: Record<number, string>): Promise<SubmittedReservation> => {
    const paymentInfos = await Promise.all(
      reservationGroupIds.map(async (reservationGroupId) => {
        const piRes = await fetch(
          `${getBackendURL()}/booking/snowland/api/payment-info/?${new URLSearchParams({ reservation_group: String(reservationGroupId), ...(accessTokens[reservationGroupId] ? { access_token: accessTokens[reservationGroupId] } : {}) })}`,
          { credentials: 'include' },
        )
        const pi = await piRes.json().catch(() => ({}))
        if (!piRes.ok) {
          throw new Error(pi.error || '取得付款資訊失敗')
        }
        return pi
      }),
    )

    return {
      reservation_group_ids: reservationGroupIds,
      payment_access_tokens: accessTokens,
      total_amount: paymentInfos.reduce((sum, pi) => sum + Number(pi.total_amount || 0), 0),
      payment_infos: paymentInfos.map((pi, index) => ({
        reservation_group_id: reservationGroupIds[index],
        total_amount: Number(pi.total_amount || 0),
        bank_info: pi.bank_info || { ...emptyBankInfo },
      })),
      payment_methods: (paymentInfos[0]?.payment_methods || []).filter((method: string) =>
        paymentInfos.every((pi) => pi.payment_methods?.includes(method))
        && (method !== 'newebpay' || reservationGroupIds.length === 1),
      ),
      payment_expires_at: paymentInfos.map((pi) => pi.payment_expires_at).filter(Boolean).sort()[0] || null,
    }
  }

  const loadPaymentForCreatedOrder = async (reservationGroupIds: number[], accessTokens: Record<number, string>) => {
    try {
      const paymentInfo = await fetchSubmittedReservationInfo(reservationGroupIds, accessTokens)
      setSubmittedReservation(paymentInfo)
      setPaymentMethod(paymentInfo.payment_methods.includes('bank_transfer') ? 'bank' : 'card')
      setPaymentInfoError('')
      showToast('訂單已建立，請完成付款', 'success')
    } catch {
      setPaymentInfoError('付款資訊暫時無法取得。')
      showToast('訂單已建立，但付款資訊暫時無法取得', 'warning')
    }
  }

  const retryPaymentInfo = async () => {
    if (createdReservationIds.length === 0 || isSubmitting) return
    setIsSubmitting(true)
    await loadPaymentForCreatedOrder(createdReservationIds, paymentAccessTokens)
    setIsSubmitting(false)
  }

  // Step 3a：送出訂單；成功後抓付款資訊，停留在 Step 3 進入付款區塊
  const submitBooking = async () => {
    if (cart.length === 0) {
      showToast('購物車是空的', 'warning')
      return
    }
    setIsSubmitting(true)
    setCompletionNotice('')
    const totalCartCourses = cart.reduce((sum, group) => sum + (group.courses?.length || 0), 0)
    startLoading(
      '正在建立預約',
      `目前共 ${cart.length} 組預約、${totalCartCourses} 堂課。多組排課需要逐一確認教練與時段。`,
      ['確認課程與價格', '套用優惠', '建立訂單', '自動安排教練', '整理付款資訊'],
    )
    try {
      const response = await createReservation({
        cart,
        accepted_policy: acceptedPolicy,
        contact: { ...contactInfo, referralSource: referralSourceValue },
        discount_code: discountCode.trim() || undefined,
        staff_link: staffLinkToken || undefined,
      })
      if (response.code !== 200) {
        showToast(`預約失敗：${response.msg}`, 'error')
        return
      }

      // 排課失敗：訂單保留（不可付款），開 modal 讓使用者選下一步
      if (response.scheduling_failed) {
        failedCartSignatureRef.current = getCartEditSignature(cart)
        setSchedulingFailed({
          isOpen: true,
          message: response.msg || '自動排課失敗，訂單保留待處理',
          conflictDetails: response.conflict_details,
          reservationGroupIds: response.reservation_group_ids || [],
        })
        return
      }

      const reservationGroupIds = getReservationGroupIdsFromResponse(response)
      if (reservationGroupIds.length === 0) {
        showToast('預約成功，但無法取得付款編號', 'error')
        return
      }

      setCreatedReservationIds(reservationGroupIds)
      const accessTokens = getPaymentAccessTokensFromResponse(response)
      setPaymentAccessTokens(accessTokens)
      setSubmittedCart(cart)
      clearCart()

      if (response.requires_payment === false || response.pending_coach_confirmation) {
        setSubmittedReservation(null)
        setCompletionFlow(response.shared_class_status === 'collecting' ? 'collecting_class' : 'coach')
        setCompletionNotice(response.msg || '訂單已建立，目前等待教練確認接課，確認前不需要付款。')
        showToast(response.msg || '訂單已建立，等待教練確認', 'success')
        setCurrentStep(4)
        return
      }

      setLoadingStepIndex(4)
      setLoadingMessage('正在整理付款資訊')
      setLoadingDetail('預約已建立，正在準備付款資訊。')
      await loadPaymentForCreatedOrder(reservationGroupIds, accessTokens)
    } catch (e: any) {
      if (e?.response?.status === 401) {
        const params = new URLSearchParams({ resume_checkout: '1' })
        if (staffLinkToken) params.set('staff_link', staffLinkToken)
        localStorage.setItem('pre_login_url', `${bookingUrl}?${params}`)
        params.set('return_to', 'booking')
        navigate(`${membershipUrl}?${params}`)
      } else if (isTimeoutError(e)) {
        showToast('預約處理時間較久，系統可能仍在建立訂單。請先不要重複送出，稍後確認訂單或聯絡客服。', 'warning')
      } else {
        showToast(`預約失敗：${getPriceErrorMessage(e, '請重新確認課程或聯絡客服')}`, 'error')
      }
    } finally {
      setIsSubmitting(false)
      stopLoading()
    }
  }

  // Step 3b：處理付款
  const submitPayment = async () => {
    if (!submittedReservation) return
    if (!submittedReservation.payment_methods.includes(paymentMethod === 'bank' ? 'bank_transfer' : 'newebpay')) {
      showToast('此訂單目前沒有可用的付款方式，請聯絡客服', 'warning')
      return
    }

    if (paymentMethod === 'bank') {
      if (senderAccount.length !== 5) {
        showToast('請輸入匯款帳戶後五碼', 'warning')
        return
      }
      setIsSubmitting(true)
      setLoadingMessage('提交匯款資訊中...')
      try {
        for (const reservationGroupId of submittedReservation.reservation_group_ids) {
          const res = await fetch(`${getBackendURL()}/booking/snowland/api/process-payment/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
              reservation_group_id: reservationGroupId,
              payment_type: 'bank_transfer',
              sender_account: senderAccount,
              access_token: submittedReservation.payment_access_tokens[reservationGroupId] || '',
            }),
          })
          const data = await res.json().catch(() => ({}))
          if (!res.ok) {
            showToast(data.error || `預約 #${reservationGroupId} 提交失敗`, 'error')
            return
          }
        }
        showToast(
          submittedReservation.reservation_group_ids.length > 1 ? '多筆匯款資訊已提交，等待確認' : '匯款資訊已提交，等待確認',
          'success',
        )
        setCompletionNotice('匯款資料已送出，等待客服核對；目前尚未確認付款成功。')
        setCompletionFlow('bank_submitted')
        setCurrentStep(4)
      } catch (e: any) {
        showToast(`提交失敗：${e.message || '未知錯誤'}`, 'error')
      } finally {
        setIsSubmitting(false)
        setLoadingMessage('')
      }
      return
    }

    // 藍新支付
    if (submittedReservation.reservation_group_ids.length > 1) {
      showToast('多筆預約目前請使用銀行轉帳，信用卡請分開結帳', 'warning')
      return
    }

    setIsSubmitting(true)
    setLoadingMessage('跳轉到藍新付款頁面...')
    try {
      const res = await fetch(`${getBackendURL()}/booking/snowland/api/process-payment/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          reservation_group_id: submittedReservation.reservation_group_ids[0],
          payment_type: 'newebpay',
          access_token: submittedReservation.payment_access_tokens[submittedReservation.reservation_group_ids[0]] || '',
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        showToast(data.error || '付款請求失敗', 'error')
        return
      }
      if (data.html) {
        const w = window.open('', '_blank')
        if (w) {
          w.document.write(data.html)
          w.document.close()
          showToast('已開啟藍新付款視窗', 'success')
          setCompletionNotice('')
          setCompletionFlow('payment')
          setCurrentStep(4)
        } else {
          showToast('請允許彈出視窗以完成付款', 'warning')
        }
      }
    } catch (e: any) {
      showToast(`跳轉失敗：${e.message || '未知錯誤'}`, 'error')
    } finally {
      setIsSubmitting(false)
      setLoadingMessage('')
    }
  }

  const handleBankTransferLater = () => {
    if (!submittedReservation || paymentMethod !== 'bank' || !submittedReservation.payment_methods.includes('bank_transfer')) return
    showToast('訂單已保留至付款資訊顯示的期限；匯款後再補後五碼給客服對帳。', 'success')
    setCompletionNotice('訂單已建立，尚未回報匯款。請於付款期限內完成匯款。')
    setCompletionFlow('bank_later')
    setCurrentStep(4)
  }

  const cancelFailedOrderBeforeRetry = async (ids: number[]) => {
    if (ids.length === 0) throw new Error('找不到原訂單編號，請聯絡客服處理，避免重複建立訂單。')
    const result = await cancelFailedReservations(ids)
    if (result.code !== 200 || result.deleted_count !== ids.length) {
      throw new Error('原訂單尚未確認取消，請查看會員訂單或聯絡客服，暫勿重複送出。')
    }
  }

  const finishAfterSchedulingFailure = () => {
    setSchedulingFailed((p) => ({ ...p, isOpen: false }))
    clearCart()
    setCompletionFlow('staff')
    setCompletionNotice('訂單已保留，暫不需要付款；課服將協助安排課程。')
    setCurrentStep(4)
    showToast('訂單已保留，課服將主動聯繫您', 'success')
  }

  const replaceCartAfterSchedulingFailure = async (suggested: { date: string; period?: string }) => {
    const ids = schedulingFailed.reservationGroupIds
    setLoadingMessage('正在更新購物車日期...')

    try {
      if (cart.length === 0) {
        showToast('購物車是空的，無法批次改日期', 'warning')
        return
      }

      const originalDates = cart
        .flatMap((group) => group.courses.map((course) => course.date))
        .filter(Boolean)
        .sort()
      const baseDate = originalDates[0] || suggested.date
      const nextCart: CartItem[] = []

      for (const group of cart) {
        const groupDates = group.courses.map((course) => course.date).filter(Boolean).sort()
        const groupBaseDate = groupDates[0] || baseDate
        const firstTargetDate = addDaysToDateKey(suggested.date, getDateKeyOffset(groupBaseDate, baseDate))
        const nextCourses: Course[] = []
        const isPhotoGroup = isPhotoCartGroup(group)
        let courseFee = 0
        let coachFee = 0
        let languageFee = 0
        let equipmentRentalFee = 0

        for (const course of group.courses) {
          const targetDate = addDaysToDateKey(suggested.date, getDateKeyOffset(course.date, baseDate))
          const fetchedSessions = await fetchCourseSessions(course.courseTemplateId, targetDate)
          const daySessions = Array.isArray(fetchedSessions)
            ? fetchedSessions
            : ((fetchedSessions as any)?.data || [])
          const nextSession = chooseReplacementSession(daySessions, course, suggested.period)

          if (!nextSession) {
            throw new Error(`${formatDateKey(targetDate)} 找不到可預約時段，請改選其他建議日期。`)
          }

          const priceEquipmentOption = isPhotoGroup
            ? null
            : group.equipmentOption === 'extra_time_help' && targetDate !== firstTargetDate
            ? null
            : group.equipmentOption
          const priceData = await calculatePrice({
            template_id: course.courseTemplateId,
            resort: group.resort,
            people_count: isPhotoGroup ? 1 : group.peopleCount,
            course_date: targetDate,
            coach: isPhotoGroup ? 'any' : (group.coach || 'any'),
            language: isPhotoGroup ? 'zh' : (group.language || 'zh'),
            equipment_option: priceEquipmentOption,
            bookings_count: 1,
          })
          const singleCourseFee = priceData.course_fee ?? priceData.price ?? 0

          courseFee += Number(singleCourseFee || 0)
          coachFee += Number(priceData.coach_fee || 0)
          languageFee += Number(priceData.language_fee || 0)
          equipmentRentalFee += Number(priceData.equipment_rental_fee || 0)

          nextCourses.push({
            ...course,
            date: targetDate,
            courseTypeId: priceData.course_type_id || course.courseTypeId,
            courseTypeName: priceData.course_type_name || course.courseTypeName,
            courseTemplateName: priceData.course_template_name || course.courseTemplateName,
            durationHours: priceData.duration_hours || course.durationHours,
            timeSlotId: Number(nextSession.id),
            timeSlotStart: nextSession.start_time || course.timeSlotStart,
            timeSlotEnd: nextSession.end_time || course.timeSlotEnd,
            price: priceData.course_fee ?? priceData.price ?? course.price,
          })
        }

        const nextCourseDates = Array.from(new Set(nextCourses.map((course) => course.date))).sort()
        const resortInfo = resorts.find((resort: any) =>
          resort.name === group.resort || resort.display_name === group.resortName,
        )
        const selectedEquipmentSlot = group.equipmentAssistanceTimeSlotId
          ? ((resortInfo?.equipment_time_slots || []) as any[]).find((slot) =>
              Number(slot.id) === Number(group.equipmentAssistanceTimeSlotId),
            )
          : null
        const nextEquipmentAssistanceTimeLabel = group.equipmentOption === 'extra_time_help' && selectedEquipmentSlot
          ? getPurchasedEquipmentSlotLabel(selectedEquipmentSlot, nextCourseDates)
          : group.equipmentAssistanceTimeLabel

        nextCart.push({
          ...group,
          equipmentAssistanceTimeLabel: nextEquipmentAssistanceTimeLabel,
          courses: nextCourses,
          courseFee,
          coachFee,
          languageFee,
          equipmentRentalFee,
          totalPrice: nextCourses.some((course) => course.price === null)
            ? null
            : courseFee + coachFee + languageFee + equipmentRentalFee,
        })
      }

      await cancelFailedOrderBeforeRetry(ids)
      replaceCart(nextCart)
      failedCartSignatureRef.current = ''
      setSchedulingFailed({ isOpen: false, message: '', conflictDetails: null, reservationGroupIds: [] })
      setCurrentStep(3)
      showToast(
        `已將購物車內 ${cart.length} 組預約批次改到 ${formatDateKey(suggested.date)}${suggested.period ? ` ${suggested.period}` : ''}`,
        'success',
      )
    } catch (e: any) {
      setSchedulingFailed((p) => ({ ...p, isOpen: true }))
      showToast(getPriceErrorMessage(e, '批次改日期失敗，請改選其他日期'), 'error')
    } finally {
      setLoadingMessage('')
    }
  }

  const moveToDateSelectionAfterSchedulingFailure = async (suggested?: { date: string; period?: string }) => {
    const ids = schedulingFailed.reservationGroupIds
    try {
      await cancelFailedOrderBeforeRetry(ids)
    } catch (e: any) {
      showToast(getPriceErrorMessage(e, '原訂單取消失敗，請勿重複送出'), 'error')
      return
    }

    setSchedulingFailed({ isOpen: false, message: '', conflictDetails: null, reservationGroupIds: [] })
    failedCartSignatureRef.current = ''
    // 原失敗訂單已取消；舊購物車課程不可與改期課程一起再次送出。
    clearCart()
    setAppendTargetGroupId(null)
    setSelectedCourseDateKeys([])
    setSelectedDate(null)
    setSelectedTimeSlot(null)
    setEquipmentAssistanceTimeSlot(null)
    setCurrentStep(2)
    const dateStepIndex = activeStep2Fields.findIndex((f) => f === 'date')
    const timeStepIndex = activeStep2Fields.findIndex((f) => f === 'timeSlot')

    if (suggested?.date) {
      setSelectedCourseDateKeys([suggested.date])
      setSelectedDate(suggested.date)
      setSelectedTimeSlot(null)
      setEquipmentAssistanceTimeSlot(null)
      setCalendarMonth(parseDateKey(suggested.date))
      setStep2Index(timeStepIndex >= 0 ? timeStepIndex : Math.max(dateStepIndex, 0))
      showToast(
        `已選擇 ${formatDateKey(suggested.date)}${suggested.period ? ` ${suggested.period}` : ''}，請確認可預約時段`,
        'info',
      )
      return
    }

    if (dateStepIndex >= 0) setStep2Index(dateStepIndex)
    showToast('原失敗訂單已取消，請重新選日期加入購物車；舊課程已清除，避免重複送出。', 'info')
  }

  // ===== Render =====

  if (authLoading || staffOperatorLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f7f8fa]">
        <div className="text-center">
          <div className="w-10 h-10 border-2 border-[#2b5f8f] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm text-[#6b7280] font-display">載入中...</p>
        </div>
      </div>
    )
  }

  if (!user && !staffPrepareMode) {
    return (
      <div className="w-full font-sans">
        <SiteHeader forceTransparent={false} forceDarkText={true} forceLogoColor={true} forceCompact />
        <div className="pt-24">
          <LoginPage />
        </div>
        <SiteFooter />
      </div>
    )
  }

  if (staffLinkToken && staffLinkStatus !== 'valid') {
    return (
      <div className="min-h-screen bg-[#f7f8fa] font-sans text-[#1f2937]">
        <SiteHeader forceTransparent={false} forceDarkText={true} forceLogoColor={true} memberAuthenticated forceCompact />
        <main className="mx-auto flex min-h-[60vh] max-w-xl items-center px-6 pt-24 pb-16">
          <div role={staffLinkStatus === 'invalid' ? 'alert' : 'status'} className="w-full rounded-sm border border-[#dbe3ec] bg-white p-8 shadow-[0_10px_24px_rgba(15,23,42,0.04)]">
            <h1 className="text-xl font-semibold">{staffLinkStatus === 'invalid' ? '代客訂課連結已失效' : '正在確認代客訂課連結'}</h1>
            <p className="mt-3 text-sm text-[#64748b]">{staffLinkStatus === 'invalid' ? '請向工作人員索取新連結，或改用一般訂課。' : '請稍候，確認校區後即可開始預約。'}</p>
            {staffLinkStatus === 'invalid' && <a href={window.location.pathname} className="mt-6 inline-flex rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white">改用一般訂課</a>}
          </div>
        </main>
        <SiteFooter />
      </div>
    )
  }

  return (
    <div className="w-full font-sans min-h-screen bg-[#f7f8fa]">
      <SiteHeader
        forceTransparent={false}
        forceDarkText={true}
        forceLogoColor={true}
        memberAuthenticated={Boolean(user)}
        memberAvatarSrc={user?.picture || ''}
        forceCompact
      />

      <main className="pt-24 pb-16">
        <div className="max-w-5xl mx-auto px-6 md:px-10">

          {/* Header + 進度條 */}
          <div className="mb-10 md:mb-14">
            <div className="flex items-center justify-between mb-8">
              <div>
                <p className="text-xs font-semibold tracking-[0.3em] uppercase text-[#94a3b8] font-display">
                  Booking
                </p>
                <h1 className="mt-2 text-2xl md:text-3xl font-semibold text-[#1f2937] font-display">
                  課程預約
                </h1>
              </div>
              {!staffSelectedCart && <button
                onClick={() => setIsCartOpen(true)}
                className="relative inline-flex items-center justify-center rounded-full bg-white border border-[#e5e9f2] px-4 py-2.5 text-sm font-semibold text-[#1f2937] hover:border-[#2b5f8f] transition-colors"
              >
                <ShoppingCart size={16} className="mr-2" />
                購物車
                {cart.length > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-brand-orange text-xs font-bold text-white">
                    {cart.length}
                  </span>
                )}
              </button>}
            </div>

          {staffPrepareMode && <div className="mb-5 rounded-sm border border-[#b6d6ec] bg-[#eaf4fb] px-4 py-3 text-sm text-[#1e4e73]" role="status"><b>代客選課模式</b> · 只準備課程，不會送出訂單或收款。選好後請回後台建立連結。</div>}

            {/* Steps progress */}
            <div className="flex items-center justify-between">
              {mainSteps.map((step, idx) => (
                <div key={step.id} className="flex items-center flex-1">
                  <div
                    className={`flex flex-col items-center ${idx === 0 ? '' : 'flex-1'}`}
                  >
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold transition-colors ${
                        currentStep >= (step.id as MainStep)
                          ? 'bg-[#2b5f8f] text-white'
                          : 'bg-[#e5e9f2] text-[#94a3b8]'
                      }`}
                    >
                      {currentStep > step.id ? <Check size={16} /> : step.id}
                    </div>
                    <p
                      className={`mt-2 text-xs md:text-sm font-medium font-display ${
                        currentStep >= (step.id as MainStep) ? 'text-[#1f2937]' : 'text-[#94a3b8]'
                      }`}
                    >
                      {step.title}
                    </p>
                  </div>
                  {idx < mainSteps.length - 1 && (
                    <div
                      className={`flex-1 h-0.5 mx-2 transition-colors ${
                        currentStep > step.id ? 'bg-[#2b5f8f]' : 'bg-[#e5e9f2]'
                      }`}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Step Content */}
          {staffLinkInfo && <div className="mb-4 rounded-sm border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800"><b>工作人員協助訂課</b> · {staffLinkInfo.created_by} · 訂單固定歸屬「{staffLinkInfo.campus.name}」{staffSelectedCart && ' · 課程已由工作人員選定，請確認資料後送出'}</div>}
          {editingGroupId && currentStep === 2 && <div role="status" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-sm border border-[#b6d6ec] bg-[#eef4fa] px-4 py-3 text-sm text-[#2b5f8f]"><p>正在修改這組課程。原課程已保留，完成新設定後才會替換。</p><button type="button" onClick={() => { resetDraftSelection(); setCurrentStep(3); }} className="min-h-11 rounded-full border border-[#2b5f8f] px-4 py-2 font-semibold">取消修改，保留原課程</button></div>}
          <AnimatePresence mode="wait">
            <motion.div
              key={`step-${currentStep}-${step2Index}-${submittedReservation ? 'payment' : 'details'}`}
              variants={{ initial: { opacity: 0, x: 20 }, enter: { opacity: 1, x: 0 }, exit: { opacity: 0, x: -20 } }}
              initial="initial"
              animate="enter"
              exit="exit"
              transition={{ duration: 0.3 }}
              onAnimationComplete={(phase) => {
                const stepKey = `${currentStep}-${step2Index}-${submittedReservation ? 'payment' : 'details'}`
                if (phase === 'enter' && lastPositionedStep.current !== stepKey) {
                  lastPositionedStep.current = stepKey
                  window.scrollTo(0, 0)
                }
              }}
              className="bg-white border border-[#e5e9f2] rounded-sm p-6 md:p-10 shadow-[0_10px_24px_rgba(15,23,42,0.04)]"
            >
              {currentStep === 1 && (
                <Step1ServiceSelection
                  selected={serviceType}
                  onSelect={handleSelectService}
                />
              )}

              {currentStep === 2 && serviceType && (
                <Step2SkiConfiguration
                  field={currentSkiField}
                  courseCategories={serviceCourseCategories}
                  courseTypes={courseTypes}
                  resorts={resortsForSelectedCategory}
                  coaches={filteredCoaches}
                  templates={templates}
                  sessions={sessions}
                  dateInfo={dateInfo}
                  isCoachesLoading={isCoachesLoading}
                  isTemplatesLoading={isTemplatesLoading}
                  onWarn={(msg: string) => showToast(msg, 'warning')}
                  coachSearchTerm={coachSearchTerm}
                  setCoachSearchTerm={setCoachSearchTerm}
                  coachLevelFilter={coachLevelFilter}
                  setCoachLevelFilter={setCoachLevelFilter}
                  coachLevelOptions={coachLevelOptions}
                  state={{
                    serviceType,
                    selectedCourseCategory, selectedCourseCategoryName, selectedCourseType,
                    selectedResort, selectedResortName, selectedCampusId, selectedCampusName,
                    peopleCount, hasUnder6, under7CanSelfSki, abilityLevelCounts, selectedAbilityLevel,
                    selectedCoach, selectedLanguage,
                    selectedCourseTemplate, selectedDate, selectedTimeSlot,
                    selectedCourseDates, unavailableSelectedDates, calendarMonth,
                    needEquipment, equipmentOption,
                    equipmentAssistanceTimeSlotId, equipmentAssistanceTimeLabel,
                  }}
                  actions={{
                    setSelectedCourseCategory: handleSelectCourseCategory,
                    setSelectedResort: handleSelectResort,
                    setSelectedCourseType: handleSelectCourseType,
                    setPeopleCount, setHasUnder6, setUnder7CanSelfSki, setAbilityLevelCount,
                    setSelectedAbilityLevel, setSelectedCoach, setSelectedLanguage: handleSelectLanguage,
                    setSelectedCourseTemplate: handleSelectCourseTemplate, setSelectedTimeSlot: handleSelectTimeSlot,
                    setCalendarMonth, toggleCourseDate: handleToggleCourseDate,
                    setNeedEquipment, setEquipmentOption, setEquipmentAssistanceTimeSlot,
                  }}
                />
              )}

              {currentStep === 3 && createdReservationIds.length > 0 && !submittedReservation ? (
                <div role="alert" className="mx-auto max-w-2xl rounded-sm border border-amber-300 bg-amber-50 p-6 text-[#1f2937]">
                  <h2 className="text-xl font-semibold">訂單已建立</h2>
                  <p className="mt-2 text-sm leading-6">{paymentInfoError || '正在取得付款資訊…'}請勿再次送出訂單。</p>
                  <p className="mt-2 text-sm">預約編號：{createdReservationIds.join('、')}</p>
                  <div className="mt-5 flex flex-wrap gap-3">
                    <button type="button" onClick={retryPaymentInfo} disabled={isSubmitting} className="rounded-full bg-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{isSubmitting ? '載入中…' : '重新取得付款資訊'}</button>
                    <a href={membershipUrl} className="rounded-full border border-[#2b5f8f] px-5 py-2.5 text-sm font-semibold text-[#2b5f8f]">查看會員訂單</a>
                  </div>
                </div>
              ) : currentStep === 3 && staffPrepareMode ? (
                <section className="mx-auto max-w-2xl space-y-4 rounded-sm border border-[#dbe3ec] bg-white p-5 shadow-sm">
                  <h2 className="text-xl font-semibold text-[#1f2937]">確認替客人選的課程</h2>
                  <p className="text-sm text-[#64748b]">這裡只準備課程，不會替客人送單或扣款。確認後回後台建立連結，客人登入後再填資料及付款。</p>
                  {cart.map(group => <div key={group.id} className="rounded-sm border border-[#e2e8f0] p-4 text-sm text-[#1f2937]"><b>{group.resortName} · {group.peopleCount} 人</b>{group.courses.map(course => <p key={`${course.courseTemplateId}-${course.date}-${course.timeSlotStart}`} className="mt-1 text-[#64748b]">{course.courseTemplateName} · {course.date} {course.timeSlotStart}–{course.timeSlotEnd}</p>)}<p className="mt-2 font-semibold">小計 {formatCurrency(group.totalPrice)}</p><button type="button" onClick={() => handleEditCartGroup(group.id)} className="mt-2 text-sm font-semibold text-[#2b5f8f]">修改這組課程</button></div>)}
                  <div className="flex flex-wrap gap-3"><button type="button" onClick={handleAddCartGroup} className="rounded-full border border-[#2b5f8f] px-4 py-2 text-sm font-semibold text-[#2b5f8f]">增加新組別課程</button><a href={staffConsoleUrl} className="rounded-full bg-[#2b5f8f] px-4 py-2 text-sm font-semibold text-white">回後台建立連結</a></div>
                </section>
              ) : currentStep === 3 && (
                <Step3Confirmation
                  cart={submittedReservation ? submittedCart : cart}
                  contactInfo={contactInfo}
                  setContactInfo={setContactInfo}
                  discountCode={discountCode}
                  setDiscountCode={setDiscountCode}
                  discountPreview={discountPreview}
                  isDiscountPreviewLoading={isDiscountPreviewLoading}
                  referrer={referrer}
                  setReferrer={setReferrer}
                  referrerDetail={referrerDetail}
                  setReferrerDetail={setReferrerDetail}
                  messengerOptions={messengerOptions}
                  referralSourceOptions={referralSourceOptions}
                  paymentMethod={paymentMethod}
                  setPaymentMethod={setPaymentMethod}
                  acceptedPolicy={acceptedPolicy}
                  setAcceptedPolicy={setAcceptedPolicy}
                  submittedReservation={submittedReservation}
                  staffSelectedCart={staffSelectedCart}
                  senderAccount={senderAccount}
                  setSenderAccount={setSenderAccount}
                  onRemoveGroup={handleRemoveCartGroup}
                  onRemoveCourse={handleRemoveCartCourse}
                  onEditGroup={handleEditCartGroup}
                  onAddGroup={handleAddCartGroup}
                  onAddCourseToGroup={handleAddCourseToGroup}
                />
              )}

              {currentStep === 4 && <Step4Complete notice={completionNotice} flow={completionFlow} />}
            </motion.div>
          </AnimatePresence>

          {/* Navigation buttons */}
          {currentStep < 4 && !(staffPrepareMode && currentStep === 3) && (
            <div className="flex justify-between mt-8">
              {(currentStep > 1 || (currentStep === 2 && step2Index > 0)) && !(currentStep === 3 && (submittedReservation || createdReservationIds.length > 0 || staffSelectedCart)) ? (
                <button
                  onClick={handleBack}
                  className="inline-flex items-center justify-center rounded-full border border-[#d4dbe4] bg-white px-6 py-3 text-sm font-semibold text-[#1f2937] hover:border-[#2b5f8f] transition-colors"
                >
                  <ChevronLeft size={16} className="mr-1" />
                  上一步
                </button>
              ) : (
                <div />
              )}

              {currentStep === 3 && createdReservationIds.length > 0 && !submittedReservation ? (
                <div />
              ) : currentStep === 3 && submittedReservation && paymentMethod === 'bank' && submittedReservation.payment_methods.includes('bank_transfer') ? (
                <div className="flex flex-col sm:flex-row gap-3">
                  <button
                    onClick={handleBankTransferLater}
                    disabled={isSubmitting}
                    className="inline-flex items-center justify-center rounded-full border border-[#2b5f8f] bg-white px-6 py-3 text-sm font-semibold text-[#2b5f8f] transition-colors hover:bg-[#f0f6fb] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    稍後匯款
                  </button>
                  <button
                    onClick={handleNext}
                    disabled={!canGoNext || isSubmitting}
                    className={`inline-flex items-center justify-center rounded-full px-8 py-3 text-sm font-semibold transition-colors ${
                      canGoNext && !isSubmitting
                        ? 'bg-[#2b5f8f] text-white hover:bg-[#8ec8f0]'
                        : 'bg-[#e5e9f2] text-[#94a3b8] cursor-not-allowed'
                    }`}
                  >
                    確認已匯款
                  </button>
                </div>
              ) : (
                <button
                  onClick={handleNext}
                  disabled={!canGoNext || isSubmitting}
                  className={`inline-flex items-center justify-center rounded-full px-8 py-3 text-sm font-semibold transition-colors ${
                    canGoNext && !isSubmitting
                      ? 'bg-[#2b5f8f] text-white hover:bg-[#8ec8f0]'
                      : 'bg-[#e5e9f2] text-[#94a3b8] cursor-not-allowed'
                  }`}
                >
                  {currentStep === 3
                    ? (!submittedReservation
                      ? '送出訂單'
                      : !submittedReservation.payment_methods.length
                        ? '暫無可用付款方式'
                        : (paymentMethod === 'bank' ? '確認已匯款' : '前往藍新付款'))
                    : '下一步'}
                  {currentStep < 3 && <ChevronRight size={16} className="ml-1" />}
                </button>
              )}
            </div>
          )}

        </div>
      </main>

      <SiteFooter />

      {!staffSelectedCart && <CartModal
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        onEditGroup={(groupId) => { setIsCartOpen(false); handleEditCartGroup(groupId) }}
        onConfirm={() => {
          if (cart.some(group => group.totalPrice == null || !Number.isFinite(group.totalPrice)
            || group.courses.some(course => course.price == null || !Number.isFinite(course.price)))) {
            showToast('請先修改課程，確認新日期、時段及價格。', 'warning')
            return
          }
          setEditingGroupId(null)
          // 確定預約 → 關閉購物車，跳到 Step 3 填聯絡資料 + 付款
          setIsCartOpen(false)
          if (cart.length === 0) {
            showToast('購物車是空的', 'warning')
            return
          }
          setCurrentStep(3)
        }}
      />}

      <SchedulingFailedModal
        isOpen={schedulingFailed.isOpen}
        message={schedulingFailed.message}
        conflictDetails={schedulingFailed.conflictDetails}
        isSuggestionBookable={(date) => isBookableDateKey(date, dateInfo)}
        onClose={finishAfterSchedulingFailure}
        onWaitForStaff={finishAfterSchedulingFailure}
        onChangeDate={staffSelectedCart ? undefined : () => moveToDateSelectionAfterSchedulingFailure()}
        onSelectSuggestion={staffSelectedCart ? undefined : (date, period) => replaceCartAfterSchedulingFailure({ date, period })}
        onTrySuperSchedule={staffSelectedCart ? undefined : () => {
          // 先彈確認 modal，避免使用者誤按
          setSchedulingFailed((p) => ({ ...p, isOpen: false }))
          setSuperConfirmOpen(true)
        }}
      />

      <ConfirmModal
        isOpen={superConfirmOpen}
        title="嘗試進階排課？"
        message={
          <div className="space-y-3">
            <p>進階排課會嘗試把課程拆成單日安排，以提高排課成功率。</p>
            <div className="rounded-sm border border-amber-200 bg-amber-50 p-3 text-xs text-[#7c2d12]">
              <p className="mb-2 font-semibold">注意事項：</p>
              <ul className="list-disc space-y-1 pl-5">
                <li>課程期間每日授課教練可能不同。</li>
                <li>所有教練皆依 SnowLand 教學標準進行授課，課程內容與學習進度將完整交接。</li>
                <li>若您希望由同一位教練全程授課，建議改選其他日期或時段，以利安排固定教練。</li>
              </ul>
            </div>
          </div>
        }
        variant="info"
        confirmText="繼續進階排課"
        cancelText="取消"
        onCancel={() => {
          setSuperConfirmOpen(false)
          // 取消 → 回到原本的失敗 modal
          setSchedulingFailed((p) => ({ ...p, isOpen: true }))
        }}
        onConfirm={async () => {
          setSuperConfirmOpen(false)
          setIsSubmitting(true)
          setCompletionNotice('')
          let oldOrderCancelled = false
          const totalCartCourses = cart.reduce((sum, group) => sum + (group.courses?.length || 0), 0)
          startLoading(
            '正在嘗試進階排課',
            `系統會把 ${totalCartCourses} 堂課拆開檢查可用教練，以提高成功率。`,
            ['拆分每日課程', '查詢可接課教練', '確認每日時段', '建立進階預約', '整理付款資訊'],
          )
          try {
            await cancelFailedOrderBeforeRetry(schedulingFailed.reservationGroupIds)
            oldOrderCancelled = true
            setSchedulingFailed({ isOpen: false, message: '', conflictDetails: null, reservationGroupIds: [] })
            failedCartSignatureRef.current = ''
            const response = await superSchedule({
              cart,
              accepted_policy: acceptedPolicy,
              contact: { ...contactInfo, referralSource: referralSourceValue },
              discount_code: discountCode.trim() || undefined,
            })
            if (response.code !== 200) {
              showToast(`進階排課失敗：${response.msg}`, 'error')
              return
            }
            if (response.scheduling_failed) {
              failedCartSignatureRef.current = getCartEditSignature(cart)
              setSchedulingFailed({
                isOpen: true,
                message: response.msg || '進階排課仍失敗',
                conflictDetails: response.conflict_details,
                reservationGroupIds: response.reservation_group_ids || [],
              })
              return
            }
            const reservationGroupIds = getReservationGroupIdsFromResponse(response)
            if (reservationGroupIds.length === 0) {
              showToast('進階排課完成，但無法取得付款編號', 'error')
              return
            }
            setCreatedReservationIds(reservationGroupIds)
            const accessTokens = getPaymentAccessTokensFromResponse(response)
            setPaymentAccessTokens(accessTokens)
            setSubmittedCart(cart)
            clearCart()
            if (response.requires_payment === false || response.pending_coach_confirmation) {
              setSubmittedReservation(null)
              setCompletionFlow('coach')
              setCompletionNotice(response.msg || '訂單已建立，目前等待教練確認接課，確認前不需要付款。')
              showToast(response.msg || '訂單已建立，等待教練確認', 'success')
              setCurrentStep(4)
              return
            }
            setLoadingStepIndex(4)
            setLoadingMessage('正在整理付款資訊')
            setLoadingDetail('進階排課已完成，正在準備付款資訊。')
            await loadPaymentForCreatedOrder(reservationGroupIds, accessTokens)
          } catch (e: any) {
            if (!oldOrderCancelled) setSchedulingFailed((p) => ({ ...p, isOpen: true }))
            if (isTimeoutError(e)) {
              showToast('進階排課處理時間較久，系統可能仍在建立訂單。請先不要重複送出，稍後確認訂單或聯絡客服。', 'warning')
            } else {
              showToast(`進階排課失敗：${getPriceErrorMessage(e, '請重新確認課程或聯絡客服')}`, 'error')
            }
          } finally {
            setIsSubmitting(false)
            stopLoading()
          }
        }}
      />

      <Toast
        message={toast.message}
        type={toast.type}
        isOpen={toast.isOpen}
        onClose={() => setToast({ ...toast, isOpen: false })}
      />

      <LoadingOverlay
        isLoading={!!loadingMessage}
        message={loadingMessage}
        detail={loadingDetail}
        steps={loadingSteps}
        activeStep={loadingStepIndex}
      />
    </div>
  )
}

// ============== Step 1: 服務選擇 ==============
function Step1ServiceSelection({
  selected, onSelect,
}: {
  selected: ServiceType | ''
  onSelect: (s: ServiceType) => void
}) {
  const options = [
    { id: 'ski' as ServiceType, title: '滑雪課程', desc: '專業私人教練小班制教學' },
    { id: 'photo' as ServiceType, title: '攝影服務', desc: '雪地與旅拍專業攝影' },
  ]

  return (
    <div>
      <div className="text-center mb-10">
        <h2 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
          請選擇服務類型
        </h2>
        <p className="mt-3 text-sm text-[#6b7280]">
          可預約滑雪課程與攝影服務
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 max-w-3xl mx-auto">
        {options.map((opt) => (
          <button
            key={opt.id}
            onClick={() => onSelect(opt.id)}
            className={`group relative p-8 rounded-sm border-2 text-left transition-all ${
              selected === opt.id
                ? 'border-[#2b5f8f] bg-[#e9eef3]'
                : 'border-[#e5e9f2] bg-white hover:border-[#2b5f8f]'
            }`}
          >
            <h3 className="text-lg font-semibold text-[#1f2937] font-display">
              {opt.title}
            </h3>
            <p className="mt-3 text-sm text-[#6b7280] leading-relaxed">
              {opt.desc}
            </p>
            {selected === opt.id && (
              <div className="absolute top-4 right-4 flex h-6 w-6 items-center justify-center rounded-full bg-[#2b5f8f] text-white">
                <Check size={14} />
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

// ============== Step 2: 滑雪配置（子欄位切換） ==============
function Step2SkiConfiguration({
  field, courseCategories, courseTypes, resorts, coaches, templates, sessions, dateInfo, onWarn,
  isCoachesLoading, isTemplatesLoading,
  coachSearchTerm, setCoachSearchTerm,
  coachLevelFilter, setCoachLevelFilter, coachLevelOptions,
  state, actions,
}: any) {
  const selectedResortInfo = resorts.find((r: any) => r.name === state.selectedResort)
  const selectedCourseTypeInfo = courseTypes.find((courseType: any) => courseType.id === state.selectedCourseType)
  const selectedTemplateInfo = templates.find((t: any) => t.id === state.selectedCourseTemplate)
  const selectedSessionInfo = sessions.find((s: any) => s.id === state.selectedTimeSlot)
  const currentTemplateHasCoachRestriction = templateHasCoachRestriction(selectedTemplateInfo)
  const canSelectAnyCoach = currentTemplateHasCoachRestriction || !languageRequiresCoach(state.selectedLanguage)
  const maxPeople = [state.selectedCourseCategoryName, selectedCourseTypeInfo?.name, selectedTemplateInfo?.name]
    .some((text) => String(text || '').includes('野雪') || String(text || '').includes('嚮導'))
    ? 8
    : 6
  useEffect(() => {
    if (state.peopleCount > maxPeople) {
      actions.setPeopleCount(maxPeople)
    }
  }, [actions, maxPeople, state.peopleCount])
  const equipmentTimeSlots = filterEquipmentTimeSlotsForSelection(
    ((selectedResortInfo?.equipment_time_slots || []) as any[]),
    state.equipmentOption,
    selectedTemplateInfo,
    selectedSessionInfo,
  )

  const courseTextForAbility = [
    state.selectedCourseCategoryName,
    selectedCourseTypeInfo?.name,
    selectedTemplateInfo?.name,
  ].join(' ')
  const isSnowboardCourse = /單板|snowboard/i.test(courseTextForAbility)
  const abilityDescriptionKey = isSnowboardCourse ? 'snowboard' : 'ski'
  const assignedAbilityCount = getAssignedAbilityCount(state.abilityLevelCounts || {})
  const remainingAbilityCount = Math.max((state.peopleCount || 0) - assignedAbilityCount, 0)

  const titles: Record<string, string> = {
    category: '選擇課程大類',
    resort: '選擇雪場',
    courseType: '選擇課程類型',
    people: '幾位學員一起上課？',
    ability: '滑雪能力等級',
    coach: '選擇教練',
    template: '選擇課程',
    date: '選擇上課日期',
    timeSlot: '選擇時段',
    equipment: '裝備租借',
  }

  return (
    <div>
      <div className="text-center mb-10">
        <h2 className="text-xl md:text-2xl font-semibold text-[#1f2937] font-display">
          {titles[field]}
        </h2>
      </div>

      {field === 'category' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-3xl mx-auto">
          {courseCategories.map((category: any) => (
            <button
              key={category.id}
              onClick={() => actions.setSelectedCourseCategory(category.id, category.name)}
              className={`p-5 rounded-sm border-2 text-left transition-colors ${
                state.selectedCourseCategory === category.id
                  ? 'border-[#2b5f8f] bg-[#e9eef3]'
                  : 'border-[#e5e9f2] bg-white hover:border-[#2b5f8f]'
              }`}
            >
              <p className="font-semibold text-[#1f2937] font-display">{category.name}</p>
            </button>
          ))}
          {courseCategories.length === 0 && (
            <p className="col-span-2 text-center text-sm text-[#6b7280] py-8">
              載入課程大類中...
            </p>
          )}
        </div>
      )}

      {field === 'resort' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-3xl mx-auto">
          {resorts.map((r: any) => {
            const campus = (r.campuses || []).find((item: any) => item.code !== 'main') || r.campuses?.[0]
            return campus ? <button
              key={r.name}
              onClick={() => actions.setSelectedResort(r.name, r.display_name, campus.id, campus.name)}
              className={`p-4 rounded-sm border-2 text-left transition-colors ${
                state.selectedResort === r.name && state.selectedCampusId === campus.id
                  ? 'border-[#2b5f8f] bg-[#e9eef3]'
                  : 'border-[#e5e9f2] bg-white hover:border-[#2b5f8f]'
              }`}
            >
              <p className="font-semibold text-[#1f2937] font-display">{r.display_name}</p>
              <p className="text-sm text-[#6b7280] mt-1">由 {campus.name} 服務</p>
            </button> : null
          })}
          {resorts.length === 0 && (
            <p className="col-span-2 text-center text-sm text-[#6b7280] py-8">
              此課程大類尚未設定可用雪場，請先到後台課程大類設定。
            </p>
          )}
        </div>
      )}

      {field === 'courseType' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-3xl mx-auto">
          {courseTypes.map((courseType: any) => (
            <button
              key={courseType.id}
              onClick={() => actions.setSelectedCourseType(courseType.id)}
              className={`p-5 rounded-sm border-2 text-left transition-colors ${
                state.selectedCourseType === courseType.id
                  ? 'border-[#2b5f8f] bg-[#e9eef3]'
                  : 'border-[#e5e9f2] bg-white hover:border-[#2b5f8f]'
              }`}
            >
              <p className="font-semibold text-[#1f2937] font-display">{courseType.name}</p>
            </button>
          ))}
          {courseTypes.length === 0 && (
            <p className="col-span-2 text-center text-sm text-[#6b7280] py-8">
              此大類在目前雪場尚未設定可預約課程
            </p>
          )}
        </div>
      )}

      {field === 'people' && (
        <div className="max-w-2xl mx-auto">
          <div className="grid grid-cols-3 gap-3 mb-8">
            {Array.from({ length: maxPeople }, (_, index) => index + 1).map((n) => (
              <button
                key={n}
                onClick={() => actions.setPeopleCount(n)}
                className={`py-4 rounded-sm border-2 text-lg font-semibold transition-colors ${
                  state.peopleCount === n
                    ? 'border-[#2b5f8f] bg-[#e9eef3] text-[#2b5f8f]'
                    : 'border-[#e5e9f2] bg-white text-[#1f2937] hover:border-[#2b5f8f]'
                }`}
              >
                {n} 人
              </button>
            ))}
          </div>
          {maxPeople > 6 && (
            <p className="mb-5 text-center text-xs text-[#64748b]">
              野雪嚮導可選最多 8 人
            </p>
          )}
          {state.peopleCount >= 5 && state.peopleCount <= 6 && (
            <div className="mb-5 rounded-sm border border-[#f5c16c] bg-[#fff7e6] p-4 text-sm leading-6 text-[#92400e]">
              <p className="font-semibold">5-6 人團體提醒</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>採小班制教學，每位教練最多指導 6 人。</li>
                <li>為維護教學品質，建議每團人數以 4 人內為佳。</li>
                <li>若為 5-6 人團體，請事先與客服確認適合安排。</li>
                <li>每一組請分開選擇並加入購物車。</li>
              </ul>
            </div>
          )}
          {state.serviceType !== 'photo' && (
          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={state.hasUnder6}
                onChange={(e) => actions.setHasUnder6(e.target.checked)}
                className="h-5 w-5 rounded text-[#2b5f8f] focus:ring-[#2b5f8f]"
              />
              <span className="text-sm font-medium text-[#1f2937]">
                有未滿 7 歲學員
              </span>
            </label>

            {state.hasUnder6 && (
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!state.under7CanSelfSki}
                    onChange={(e) => actions.setUnder7CanSelfSki(e.target.checked)}
                    className="h-5 w-5 rounded text-[#2b5f8f] focus:ring-[#2b5f8f]"
                  />
                  <span className="text-sm text-[#1f2937]">
                    學員已具備獨立滑行、煞車及基本安全控制能力
                  </span>
                </label>

                {state.peopleCount > 1 && !state.under7CanSelfSki && (
                  <div className="rounded-sm border border-[#f59e0b] bg-[#fff7e6] p-3 text-sm text-[#92400e]">
                    未滿 7 歲且尚無法自主滑行時，請安排 1 對 1 教練課程。
                  </div>
                )}

                <div className="rounded-sm border border-[#f5c16c] bg-[#fff7e6] p-4 text-sm leading-6 text-[#1f2937]">
                  <p className="font-semibold text-[#92400e]">未滿 7 歲學員上課規範</p>
                  <p className="mt-2">
                    為確保學員安全與教學品質，未滿 7 歲學員原則上需安排 1 對 1 教練授課。
                  </p>
                  <p className="mt-2">
                    若小朋友已具備獨立滑行、煞車及基本安全控制能力，經評估後方可與較大兒童或成人共同上課。
                  </p>
                  <p className="mt-2">
                    如對課程安排有任何疑問，歡迎事先與客服聯繫，我們將協助評估最適合的上課方式。
                  </p>
                  <p className="mt-2">
                    提醒您：訂單成立後，如經教學團隊評估未滿 7 歲學員尚不適合與其他學員共同上課，為維護學員安全，SnowLand 保留調整課程安排或取消訂單之權利。
                  </p>
                  <p className="mt-2">
                    感謝您的理解與配合，讓每位學員都能在安全、愉快的環境中享受滑雪樂趣。
                  </p>
                </div>
              </div>
            )}
          </div>
          )}
        </div>
      )}

      {field === 'ability' && (
        <div className="max-w-4xl mx-auto space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-[#d4dbe4] bg-[#f8fafc] px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-[#1f2937]">
                請分配每位學員的能力等級
              </p>
              <p className="mt-1 text-xs text-[#64748b]">
                目前依{isSnowboardCourse ? '單板' : '雙板'}標準顯示說明
              </p>
            </div>
            <div className={`text-sm font-semibold ${
              assignedAbilityCount === state.peopleCount ? 'text-emerald-700' : 'text-[#92400e]'
            }`}>
              已分配 {assignedAbilityCount} / {state.peopleCount} 人
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {abilityLevels.map((level) => {
              const count = Number(state.abilityLevelCounts?.[level.id] || 0)
              const maxSelectable = state.peopleCount || 0

              return (
                <div
                  key={level.id}
                  className={`grid gap-3 rounded-sm border-2 bg-white p-4 transition-colors md:grid-cols-[140px_1fr_120px] md:items-center ${
                    count > 0
                      ? 'border-[#2b5f8f] bg-[#f8fbfd]'
                      : 'border-[#e5e9f2]'
                  }`}
                >
                  <div>
                    <p className="font-semibold text-[#1f2937] font-display">{level.name}</p>
                    {count > 0 && (
                      <p className="mt-1 text-xs font-semibold text-[#2b5f8f]">{count} 人</p>
                    )}
                  </div>
                  <p className="text-sm leading-6 text-[#4b5563]">
                    {level[abilityDescriptionKey]}
                  </p>
                  <select
                    value={count}
                    onChange={(e) => actions.setAbilityLevelCount(level.id, Number(e.target.value))}
                    className="h-10 rounded-sm border border-[#d4dbe4] bg-white px-3 text-sm text-[#1f2937] focus:border-[#2b5f8f] focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/20"
                  >
                    {Array.from({ length: maxSelectable + 1 }, (_, index) => (
                      <option key={index} value={index}>{index} 人</option>
                    ))}
                  </select>
                </div>
              )
            })}
          </div>

          {assignedAbilityCount !== state.peopleCount && (
            <div className="rounded-sm border border-[#f59e0b] bg-[#fff7e6] p-3 text-sm text-[#92400e]">
              {assignedAbilityCount < state.peopleCount
                ? `還有 ${remainingAbilityCount} 位學員尚未分配能力等級。`
                : `能力等級分配超過總人數 ${assignedAbilityCount - state.peopleCount} 人，請調整。`}
            </div>
          )}
        </div>
      )}

      {field === 'coach' && (
        <div className="max-w-4xl mx-auto">
          {languageRequiresCoach(state.selectedLanguage) && (
            <div className="mb-4 rounded-sm border border-[#bfdbfe] bg-[#eff6ff] p-3 text-sm text-[#1e3a8a]">
              English / 粵語需要指定一位符合語言的教練，指定費會依教練等級計算。
            </div>
          )}
          {/* Language filter + search */}
          <div className="flex flex-wrap items-center gap-3 mb-6">
            {coachLanguages.map((lang) => (
              <button
                key={lang.name}
                onClick={() => actions.setSelectedLanguage(lang.id)}
                className={`px-4 py-2 rounded-full text-xs font-semibold transition-colors ${
                  state.selectedLanguage === lang.id
                    ? 'bg-[#2b5f8f] text-white'
                    : 'bg-white border border-[#d4dbe4] text-[#1f2937] hover:border-[#2b5f8f]'
                }`}
              >
                {lang.name}
              </button>
            ))}
          </div>

          {coachLevelOptions?.length > 0 && (
            <div className="flex flex-wrap items-center gap-3 mb-6">
              <span className="text-xs font-semibold text-[#64748b]">教練等級</span>
              <button
                onClick={() => setCoachLevelFilter('all')}
                className={`px-4 py-2 rounded-full text-xs font-semibold transition-colors ${
                  coachLevelFilter === 'all'
                    ? 'bg-[#2b5f8f] text-white'
                    : 'bg-white border border-[#d4dbe4] text-[#1f2937] hover:border-[#2b5f8f]'
                }`}
              >
                全部
              </button>
              {coachLevelOptions.map((option: any) => (
                <button
                  key={option.value}
                  onClick={() => setCoachLevelFilter(option.value)}
                  className={`px-4 py-2 rounded-full text-xs font-semibold transition-colors ${
                    coachLevelFilter === option.value
                      ? 'bg-[#2b5f8f] text-white'
                      : 'bg-white border border-[#d4dbe4] text-[#1f2937] hover:border-[#2b5f8f]'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}

          <div className="relative mb-6">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-[#94a3b8]" />
            <input
              type="text"
              placeholder="搜尋教練姓名..."
              value={coachSearchTerm}
              onChange={(e) => setCoachSearchTerm(e.target.value)}
              className="w-full pl-11 pr-4 py-3 rounded-sm border border-[#e2e8f0] bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
            />
          </div>

          {/* Any coach option */}
          <button
            onClick={() => actions.setSelectedCoach(null)}
            disabled={!canSelectAnyCoach}
            className={`w-full mb-6 p-4 rounded-sm border-2 text-left transition-colors ${
              !canSelectAnyCoach
                ? 'border-[#e5e9f2] bg-gray-100 text-gray-400 cursor-not-allowed'
                :
              state.selectedCoach === null
                ? 'border-[#2b5f8f] bg-[#e9eef3]'
                : 'border-[#e5e9f2] bg-white hover:border-[#2b5f8f]'
            }`}
          >
            <p className="font-semibold text-[#1f2937] font-display">不指定教練</p>
            <p className="mt-1 text-xs text-[#6b7280]">
              {!canSelectAnyCoach
                ? '指定 English / 粵語時不可選擇不指定教練'
                  : currentTemplateHasCoachRestriction
                    ? '由系統依課程等級與優先名單安排教練，仍會計入指定費'
                : '由系統依照時間、等級與雪場安排合適教練'}
            </p>
          </button>

          {isCoachesLoading ? (
            <div className="rounded-sm border border-[#bfdbfe] bg-[#eff6ff] p-4">
              <div className="flex items-center gap-3">
                <Loader2 size={18} className="animate-spin text-[#2b5f8f]" />
                <div>
                  <p className="text-sm font-semibold text-[#1e3a8a]">正在查詢可接課教練</p>
                  <p className="mt-1 text-xs text-[#3b638d]">系統正在依照日期、時段、雪場與課程條件比對教練。</p>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
                {[0, 1, 2].map((item) => (
                  <div key={item} className="rounded-sm border border-[#dbeafe] bg-white p-4">
                    <div className="h-28 animate-pulse rounded-sm bg-[#e2e8f0]" />
                    <div className="mt-3 h-4 w-24 animate-pulse rounded bg-[#e2e8f0]" />
                    <div className="mt-3 h-16 animate-pulse rounded bg-[#eef2f7]" />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {coaches.map((coach: any) => {
                const certificationText = getCoachCertificationText(coach)
                const priceLevelLabel = coach.price_level_label || getCoachPriceLevelLabel(coach.price_level)
                const matchedStudentAbilityText = getCoachMatchedStudentAbilitySummary(coach, state.abilityLevelCounts || {})
                const selectedStudentAbilityText = getStudentAbilitySummary(state.abilityLevelCounts || {})

                return (
                  <button
                    key={coach.pk}
                    onClick={() => actions.setSelectedCoach(coach.pk, coach.name)}
                    className={`p-4 rounded-sm border-2 text-left transition-all hover:-translate-y-1 ${
                      state.selectedCoach === coach.pk
                        ? 'border-[#2b5f8f] bg-[#e9eef3]'
                        : 'border-[#e5e9f2] bg-white hover:border-[#2b5f8f]'
                    }`}
                  >
                    {coach.image && (
                      <img
                        src={coach.image}
                        alt={coach.name}
                        className="w-full aspect-[5/4] object-cover mb-3 rounded-sm"
                        loading="lazy"
                      />
                    )}
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-semibold text-[#1f2937] font-lora">{coach.name}</p>
                      {coach.requires_confirmation && (
                        <span className="shrink-0 rounded-full bg-[#fff7ed] px-2 py-0.5 text-[11px] font-semibold text-[#c2410c]">
                          需確認
                        </span>
                      )}
                    </div>
                    {coach.requires_confirmation && (
                      <p className="mt-2 rounded-sm border border-[#fed7aa] bg-[#fff7ed] px-3 py-2 text-xs leading-5 text-[#9a3412]">
                        指定此教練需經客服確認後才成立，可能依實際行程調整。
                      </p>
                    )}
                    <div className="mt-3 rounded-sm border border-[#bfdbfe] bg-[#eff6ff] px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-[#2b5f8f]">
                        搭配學生等級
                      </p>
                      <p className="mt-1 text-sm font-semibold leading-6 text-[#1e3a8a]">
                        {matchedStudentAbilityText || selectedStudentAbilityText || '尚未分配能力等級'}
                      </p>
                    </div>
                    <div className="mt-3 space-y-2 text-xs leading-5 text-[#64748b]">
                      <p>
                        <span className="font-semibold text-[#334155]">語言：</span>
                        {getCoachLanguageCodes(coach).map(getLanguageLabel).join(' / ') || '未設定'}
                      </p>
                      <p>
                        <span className="font-semibold text-[#334155]">教練等級：</span>
                        {priceLevelLabel}
                      </p>
                      {certificationText && (
                        <p>
                          <span className="font-semibold text-[#334155]">證照等級：</span>
                          {certificationText}
                        </p>
                      )}
                    </div>
                  </button>
                )
              })}
              {coaches.length === 0 && (
                <p className="col-span-full text-center text-sm text-[#6b7280] py-8">
                  {languageRequiresCoach(state.selectedLanguage)
                    ? '目前沒有符合語言與等級條件的可指定教練'
                    : '目前沒有符合篩選條件的教練，您可選擇「不指定教練」'}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {field === 'template' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl mx-auto">
          {isTemplatesLoading ? (
            <div className="col-span-full rounded-sm border border-[#bfdbfe] bg-[#eff6ff] p-4">
              <div className="flex items-center gap-3">
                <Loader2 size={18} className="animate-spin text-[#2b5f8f]" />
                <div>
                  <p className="text-sm font-semibold text-[#1e3a8a]">正在載入開放課程</p>
                  <p className="mt-1 text-xs text-[#3b638d]">系統正在確認這個雪場目前可預約的課程。</p>
                </div>
              </div>
            </div>
          ) : (
            <>
              {templates.map((t: any) => {
                const minimumGroupSize = t.shared_class_enabled ? 1 : Number(t.minimum_group_size || 1)
                const studentLevelRule = getTemplateStudentLevelRule(
                  t, state.abilityLevelCounts || {}, state.selectedAbilityLevel,
                )
                const unavailable = state.peopleCount < minimumGroupSize || studentLevelRule.insufficient
                return (
                <button
                  key={t.id}
                  onClick={() => actions.setSelectedCourseTemplate(t.id)}
                  disabled={unavailable}
                  className={`p-5 rounded-sm border-2 text-left transition-colors ${
                    state.selectedCourseTemplate === t.id
                      ? 'border-[#2b5f8f] bg-[#e9eef3]'
                      : unavailable
                      ? 'cursor-not-allowed border-[#e5e9f2] bg-[#f8fafc] opacity-60'
                      : 'border-[#e5e9f2] bg-white hover:border-[#2b5f8f]'
                  }`}
                >
                  <p className="font-semibold text-[#1f2937] font-display">{t.name}</p>
                  <p className="mt-2 text-xs text-[#64748b]">
                    {[t.course_type_name, `${t.duration_hours} 小時`].filter(Boolean).join(' · ')}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium">
                    <span className="rounded-sm bg-[#e9eef3] px-2 py-1 text-[#2b5f8f]">
                      {t.billing_mode === 'per_person' ? '每人計價' : '包班計價'}
                    </span>
                    {t.shared_class_enabled ? (
                      <span className="rounded-sm bg-sky-50 px-2 py-1 text-sky-800">
                        可單人報名・滿 {t.shared_class_minimum_students || 3} 人成班後付款・教練由學校安排
                      </span>
                    ) : Number(t.minimum_group_size || 1) > 1 && (
                      <span className={`rounded-sm px-2 py-1 ${
                        state.peopleCount < Number(t.minimum_group_size || 1)
                          ? 'bg-red-50 text-red-700'
                          : 'bg-emerald-50 text-emerald-700'
                      }`}>
                        單筆至少 {t.minimum_group_size} 人
                      </span>
                    )}
                    {studentLevelRule.requiredRank > 0 && (
                      <span className={`rounded-sm px-2 py-1 ${
                        studentLevelRule.insufficient
                          ? 'bg-red-50 text-red-700'
                          : 'bg-emerald-50 text-emerald-700'
                      }`}>
                        學員需等級 {studentLevelRule.requiredRank} 以上
                      </span>
                    )}
                  </div>
                </button>
                )
              })}
              {templates.length === 0 && (
                <p className="col-span-2 text-center text-sm text-[#6b7280] py-8">
                  目前沒有開放預約的課程，請返回選擇其他雪場或課程類型。
                </p>
              )}
            </>
          )}
        </div>
      )}

      {field === 'date' && (
        <div className="max-w-2xl mx-auto">
          {/* 日期限制提示（顯示「實際可預約範圍」，會考慮今天）*/}
          {dateInfo && (dateInfo.course_start_date || dateInfo.course_end_date) && (() => {
            const today = new Date().toISOString().split('T')[0]
            // 開始日期：取「課程開始」和「今天」之中比較晚的
            const effectiveStart = dateInfo.course_start_date && dateInfo.course_start_date > today
              ? dateInfo.course_start_date
              : today
            const expired = dateInfo.course_end_date && dateInfo.course_end_date < today
            return (
              <div className={`mb-4 p-3 rounded-sm text-xs ${expired ? 'bg-red-50 border border-red-200 text-red-700' : 'bg-[#e9eef3] border border-[#2b5f8f]/20 text-[#1f2937]'}`}>
                <div className={`font-medium mb-1 ${expired ? 'text-red-700' : 'text-[#2b5f8f]'}`}>
                  {expired ? '⚠️ 課程已結束' : '📅 可預約期間'}
                </div>
                <div>
                  {effectiveStart} 至 {dateInfo.course_end_date || '不限'}
                </div>
              </div>
            )
          })()}

          <div className="rounded-sm border border-[#e2e8f0] bg-white p-4">
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => actions.setCalendarMonth(addMonthsToDate(state.calendarMonth, -1))}
                className="flex h-9 w-9 items-center justify-center rounded-sm border border-[#d4dbe4] text-[#1f2937] hover:border-[#2b5f8f]"
              >
                <ChevronLeft size={18} />
              </button>
              <p className="font-semibold text-[#1f2937] font-display">
                {formatCalendarMonth(state.calendarMonth)}
              </p>
              <button
                type="button"
                onClick={() => actions.setCalendarMonth(addMonthsToDate(state.calendarMonth, 1))}
                className="flex h-9 w-9 items-center justify-center rounded-sm border border-[#d4dbe4] text-[#1f2937] hover:border-[#2b5f8f]"
              >
                <ChevronRight size={18} />
              </button>
            </div>

            <div className="mt-4 grid grid-cols-7 gap-1 text-center text-xs font-semibold text-[#64748b]">
              {['日', '一', '二', '三', '四', '五', '六'].map((day) => (
                <div key={day} className="py-2">{day}</div>
              ))}
            </div>

            <div className="grid grid-cols-7 gap-1">
              {buildCalendarMonthCells(state.calendarMonth).map((dateKey, index) => {
                if (!dateKey) return <div key={`empty-${index}`} className="h-11" />

                const selected = state.selectedCourseDates?.includes(dateKey)
                const disabled = !isBookableDateKey(dateKey, dateInfo)
                const today = dateKey === toDateKey(new Date())
                const dayNumber = Number(dateKey.split('-')[2])
                const sharedSlots = selectedTemplateInfo?.shared_class_enabled
                  ? (dateInfo?.shared_class_dates?.[dateKey] || []) : []
                const visibleSlot = sharedSlots.find((slot: { remaining_capacity: number }) => slot.remaining_capacity > 0)
                  || sharedSlots[0]
                const sharedLabel = visibleSlot
                  ? (visibleSlot.status === 'ready' ? '已成班' : `${visibleSlot.registered_students}/${visibleSlot.minimum_students} 湊班`)
                  : ''

                return (
                  <button
                    key={dateKey}
                    type="button"
                    disabled={disabled}
                    onClick={() => actions.toggleCourseDate(dateKey)}
                    aria-label={`${dateKey}${sharedLabel ? `，${sharedLabel}` : ''}${disabled ? '，不可預約' : ''}`}
                    className={`flex ${selectedTemplateInfo?.shared_class_enabled ? 'min-h-14 flex-col' : 'h-11'} items-center justify-center rounded-sm border text-sm font-semibold transition-colors ${
                      selected
                        ? 'border-[#2b5f8f] bg-[#2b5f8f] text-white'
                        : disabled
                        ? 'cursor-not-allowed border-[#edf0f5] bg-[#f8fafc] text-[#cbd5e1]'
                        : today
                        ? 'border-[#2b5f8f] bg-white text-[#2b5f8f]'
                        : 'border-[#e2e8f0] bg-white text-[#1f2937] hover:border-[#2b5f8f] hover:bg-[#e9eef3]'
                    }`}
                  >
                    {dayNumber}
                    {sharedLabel && <span className={`mt-0.5 text-[9px] leading-tight ${selected ? 'text-white' : 'text-[#2b5f8f]'}`}>{sharedLabel}</span>}
                  </button>
                )
              })}
            </div>
            {selectedTemplateInfo?.shared_class_enabled && <p className="mt-3 text-xs text-[#64748b]">標示人數的日期已有同程度團體班；沒有標示的日期也可選，報名後開始湊班。選好日期後可查看各時段剩餘名額。</p>}
          </div>

          {state.selectedCourseDates?.length > 0 && (
            <div className="mt-4 rounded-sm border border-[#e2e8f0] bg-[#f8fafc] p-3">
              <p className="text-xs font-semibold text-[#1f2937]">將加入的日期</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {state.selectedCourseDates.map((dateKey: string) => {
                  const blocked = state.unavailableSelectedDates?.includes(dateKey)
                  return (
                    <button
                      key={dateKey}
                      type="button"
                      onClick={() => actions.toggleCourseDate(dateKey)}
                      className={`rounded-full px-3 py-1 text-xs font-medium ${
                        blocked ? 'bg-red-50 text-red-700 ring-1 ring-red-200' : 'bg-white text-[#2b5f8f] ring-1 ring-[#2b5f8f]/20 hover:bg-[#e9eef3]'
                      }`}
                    >
                      {formatDateKey(dateKey)}
                    </button>
                  )
                })}
              </div>
              {state.unavailableSelectedDates?.length > 0 && (
                <p className="mt-3 text-xs text-red-600">
                  有日期不在可預約範圍內，請取消該日期。
                </p>
              )}
            </div>
          )}

          {dateInfo && (() => {
            const today = new Date().toISOString().split('T')[0]
            const courseEnded = dateInfo.course_end_date && dateInfo.course_end_date < today
            const bookingClosed = dateInfo.booking_close_date && dateInfo.booking_close_date < today
            const bookingNotOpen = dateInfo.booking_open_date && dateInfo.booking_open_date > today
            if (!courseEnded && !bookingClosed && !bookingNotOpen) return null
            return (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-sm text-sm text-red-700">
                ⚠️ 目前無法預約：
                <ul className="mt-1 ml-4 list-disc space-y-0.5">
                  {courseEnded && <li>課程已於 {dateInfo.course_end_date} 結束</li>}
                  {bookingClosed && <li>預約已於 {dateInfo.booking_close_date} 截止</li>}
                  {bookingNotOpen && <li>預約將於 {dateInfo.booking_open_date} 開放</li>}
                </ul>
              </div>
            )
          })()}

          <p className="mt-3 text-xs text-[#6b7280] text-center">
            {selectedTemplateInfo?.shared_class_enabled
              ? '團體湊班一次選一天；要預約其他日期請另外下單。'
              : '可直接點選一個或多個上課日期'}
          </p>
        </div>
      )}

      {field === 'timeSlot' && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-w-3xl mx-auto">
          {sessions.map((s: any) => (
            <button
              key={s.id}
              onClick={() => !s.is_full && actions.setSelectedTimeSlot(s.id)}
              disabled={s.is_full}
              className={`p-4 rounded-sm border-2 text-center transition-colors relative ${
                s.is_full
                  ? 'border-[#e5e9f2] bg-gray-100 text-gray-400 cursor-not-allowed'
                  : state.selectedTimeSlot === s.id
                  ? 'border-[#2b5f8f] bg-[#e9eef3] text-[#2b5f8f]'
                  : 'border-[#e5e9f2] bg-white text-[#1f2937] hover:border-[#2b5f8f]'
              }`}
            >
              <p className="font-semibold text-sm">
                {s.start_time?.substring(0, 5)} - {s.end_time?.substring(0, 5)}
              </p>
              {selectedTemplateInfo?.shared_class_enabled && !s.is_full && <p className="mt-1 text-xs">
                {s.shared_class
                  ? s.shared_class.status === 'ready'
                    ? `已成班・剩 ${s.shared_class.remaining_capacity} 位`
                    : `湊班 ${s.shared_class.registered_students}/${s.shared_class.minimum_students} 人・剩 ${s.shared_class.remaining_capacity} 位`
                  : '新班・報名後開始湊班'}
              </p>}
              {s.is_full && (
                <span className="absolute top-1 right-1 px-1.5 py-0.5 bg-red-100 text-red-700 rounded text-xs font-semibold">
                  已滿
                </span>
              )}
            </button>
          ))}
          {sessions.length === 0 && (
            <p className="col-span-full text-center text-sm text-[#6b7280] py-8">
              {state.selectedDate ? '此日期沒有可用時段' : '載入時段中...'}
            </p>
          )}
        </div>
      )}

          {field === 'equipment' && (
        <div className="max-w-3xl mx-auto space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { id: 'self_rent', title: '自行租借不須協助', desc: '您已自行安排裝備' },
            { id: 'own_equipment', title: '自備裝備不須協助', desc: '您會攜帶個人裝備' },
            { id: 'class_time_help', title: '課程時間內協助', desc: '使用原課程時間協助租借，不另選時段' },
            { id: 'extra_time_help', title: '加購半小時協助時間', desc: '另計費用，費用只加在第一天課程' },
          ].map((opt) => (
            <button
              key={opt.id}
              onClick={() => {
                actions.setEquipmentOption(opt.id)
                actions.setNeedEquipment(opt.id.includes('help'))
                if (opt.id !== 'extra_time_help') actions.setEquipmentAssistanceTimeSlot(null)
              }}
              className={`p-5 rounded-sm border-2 text-left transition-colors ${
                state.equipmentOption === opt.id
                  ? 'border-[#2b5f8f] bg-[#e9eef3]'
                  : 'border-[#e5e9f2] bg-white hover:border-[#2b5f8f]'
              }`}
            >
              <p className="font-semibold text-[#1f2937] font-display">{opt.title}</p>
              <p className="mt-2 text-xs text-[#64748b]">{opt.desc}</p>
            </button>
          ))}
          </div>
          {state.equipmentOption === 'extra_time_help' && (
            <div className="rounded-sm border border-[#d4dbe4] bg-white p-4">
              <p className="mb-1 text-sm font-semibold text-[#1f2937]">加購半小時協助時段</p>
              <p className="mb-3 text-xs leading-5 text-[#64748b]">
                多天課程只會把加購協助費加在第一天，其他日期仍保留原課程時間。
              </p>
              {equipmentTimeSlots.length === 0 ? (
                <p className="text-sm text-red-600">後台尚未設定裝備協助時段。</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {equipmentTimeSlots.map((slot) => {
                    const label = getPurchasedEquipmentSlotLabel(slot, state.selectedCourseDates || [])
                    return (
                      <button
                        key={slot.id}
                        type="button"
                        onClick={() => actions.setEquipmentAssistanceTimeSlot(slot.id, label)}
                        className={`p-3 rounded-sm border-2 text-left text-sm transition-colors ${
                          state.equipmentAssistanceTimeSlotId === slot.id
                            ? 'border-[#2b5f8f] bg-[#e9eef3] text-[#2b5f8f]'
                            : 'border-[#e5e9f2] bg-white text-[#1f2937] hover:border-[#2b5f8f]'
                        }`}
                      >
                        <span className="font-semibold">{label}</span>
                        {slot.description && <span className="block mt-1 text-xs text-[#64748b]">{slot.description}</span>}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ============== Step 3: 確認訂單 ==============
function Step3Confirmation({
  cart, contactInfo, setContactInfo,
  discountCode, setDiscountCode,
  discountPreview, isDiscountPreviewLoading,
  referrer, setReferrer,
  referrerDetail, setReferrerDetail,
  messengerOptions, referralSourceOptions,
  paymentMethod, setPaymentMethod,
  acceptedPolicy, setAcceptedPolicy,
  submittedReservation, senderAccount, setSenderAccount,
  staffSelectedCart,
  onRemoveGroup, onRemoveCourse, onEditGroup, onAddGroup, onAddCourseToGroup,
}: any) {
  const cancellationPolicyUrl = useSiteLink('/cancellation-policy')
  const cartSubtotal = submittedReservation?.total_amount ?? discountPreview?.subtotal ?? cart.reduce((sum: number, g: any) => sum + (g.totalPrice || 0), 0)
  const pricePending = !submittedReservation && !discountPreview && cart.some((group: CartItem) => group.totalPrice == null)
  const totalCourses = cart.reduce((sum: number, g: any) => sum + (g.courses?.length || 0), 0)
  const discountTotal = submittedReservation ? 0 : (discountPreview?.discount_total || 0)
  const total = submittedReservation
    ? submittedReservation.total_amount
    : (discountPreview?.total ?? Math.max(cartSubtotal - discountTotal, 0))
  const isPaid = !!submittedReservation
  const canEditCart = !isPaid && !staffSelectedCart
  const isSharedClassCart = cart.some((group: CartItem) =>
    group.courses?.some((course) => course.sharedClassEnabled),
  )

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-8">
      {/* Left - 聯絡資料 + 訂單明細 */}
      <div>
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-xl font-semibold text-[#1f2937] font-display">
            訂單明細
          </h2>
          {canEditCart && !isSharedClassCart && (
            <button
              type="button"
              onClick={() => onAddGroup?.()}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-[#2b5f8f] bg-white px-4 py-2 text-sm font-semibold text-[#2b5f8f] hover:bg-[#f0f6fb]"
            >
              <Plus size={16} />
              增加新組別課程
            </button>
          )}
        </div>

        {cart.length === 0 ? (
          <p className="text-sm text-[#6b7280] py-8 text-center">購物車是空的</p>
        ) : (
          <div className="space-y-4 mb-8">
            <div className={`rounded-sm border px-4 py-3 ${isSharedClassCart ? 'border-[#b6d6ec] bg-[#eaf4fb] text-sm font-semibold text-[#1e4e73]' : 'border-[#dbe3ec] bg-[#f8fafc] text-xs text-[#64748b]'}`}>
              <span>
                {isSharedClassCart
                  ? '團體湊班為單獨報名；滿成班人數後，系統才會請您付款。若排課尚待確認，會先暫停付款。'
                  : isPaid
                    ? `已建立 ${cart.length} 組預約、${totalCourses} 堂課。以下是送出時的課程內容。`
                    : staffSelectedCart
                      ? `工作人員已選好 ${cart.length} 組預約、${totalCourses} 堂課。請核對內容，若需修改請聯絡工作人員。`
                      : `共 ${cart.length} 組預約、${totalCourses} 堂課。同一組請按「新增同組其他課程」，會以同一位教練排課；「增加新組別課程」會獨立排課。`}
              </span>
            </div>
            {cart.map((group: any, groupIndex: number) => {
              const courseSegments = groupCartCoursesBySegment(group.courses || [])
              return (
              <article key={group.id} className="border border-[#dbe3ec] bg-white rounded-sm shadow-sm">
                <div className="flex flex-col gap-3 border-b border-[#edf1f6] px-4 py-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-xs font-semibold text-[#94a3b8] uppercase tracking-wider">
                      預約組 {groupIndex + 1}
                      {courseSegments.length > 1 && (
                        <span className="ml-2 rounded-full bg-[#eff6ff] px-2 py-0.5 text-[#2b5f8f]">
                          {courseSegments.length} 項課程
                        </span>
                      )}
                    </p>
                    <h3 className="mt-1 text-base font-semibold text-[#1f2937]">
                      {group.courseCategory || '課程預約'}
                    </h3>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#64748b]">
                      <span className="inline-flex items-center gap-1">
                        <MapPin size={13} />
                        {group.resortName || group.resort || '未指定雪場'}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Calendar size={13} />
                        {getCartDateSummary(group.courses || [])}
                      </span>
                      <span>{courseSegments.length} 項課程</span>
                    </div>
                  </div>
                  {canEditCart && (
                    <div className="flex shrink-0 flex-wrap gap-2">
                      {!isSharedClassCart && (
                        <button
                          type="button"
                          onClick={() => onAddCourseToGroup?.(group.id)}
                          className="inline-flex items-center gap-1 rounded-full border border-[#2b5f8f] bg-[#2b5f8f] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#8ec8f0]"
                        >
                          <Plus size={13} />
                          新增同組其他課程
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => onEditGroup?.(group.id)}
                        className="inline-flex items-center gap-1 rounded-full border border-[#d4dbe4] px-3 py-1.5 text-xs font-semibold text-[#2b5f8f] hover:border-[#2b5f8f]"
                      >
                        <Pencil size={13} />
                        修改
                      </button>
                      <button
                        type="button"
                        onClick={() => onRemoveGroup?.(group.id)}
                        className="inline-flex items-center gap-1 rounded-full border border-[#f1c7c7] px-3 py-1.5 text-xs font-semibold text-[#b42318] hover:bg-[#fff1f1]"
                      >
                        <Trash2 size={13} />
                        刪除
                      </button>
                    </div>
                  )}
                </div>

                {canEditCart && group.rebookSource && <p className="mx-4 mt-4 rounded-sm bg-[#eef4fa] p-3 text-sm leading-6 text-[#1e4e73]">將沿用上次可管理的 {group.rebookSource.learnerCount} 位學員姓名、年齡區間與滑雪程度；其他成人需重新邀請。保險資料與聲明簽名須重新確認。</p>}
                {canEditCart && group.rebookLearnersReset && <p role="status" className="mx-4 mt-4 rounded-sm bg-amber-50 p-3 text-sm leading-6 text-amber-900">人數已變更，本次不自動沿用學員；訂單成立後請重新填寫或邀請綁定。</p>}
                <div className="grid grid-cols-2 gap-2 px-4 py-4 sm:grid-cols-3 lg:grid-cols-5">
                  <div className="rounded-sm bg-[#f8fafc] px-3 py-2">
                    <p className="flex items-center gap-1 text-[11px] font-semibold text-[#94a3b8]">
                      <Users size={13} /> 人數
                    </p>
                    <p className="mt-1 text-sm font-semibold text-[#1f2937]">{group.peopleCount || 1} 人</p>
                  </div>
                  <div className="rounded-sm bg-[#f8fafc] px-3 py-2">
                    <p className="text-[11px] font-semibold text-[#94a3b8]">程度</p>
                    <p className="mt-1 text-sm font-semibold text-[#1f2937]">{group.abilityLevelName || getCoachAbilityLabel(group.abilityLevel) || '未指定'}</p>
                  </div>
                  <div className="rounded-sm bg-[#f8fafc] px-3 py-2">
                    <p className="flex items-center gap-1 text-[11px] font-semibold text-[#94a3b8]">
                      <Languages size={13} /> 語言
                    </p>
                    <p className="mt-1 text-sm font-semibold text-[#1f2937]">{getLanguageLabel(group.language || 'zh')}</p>
                  </div>
                  <div className="rounded-sm bg-[#f8fafc] px-3 py-2">
                    <p className="flex items-center gap-1 text-[11px] font-semibold text-[#94a3b8]">
                      <User size={13} /> 教練
                    </p>
                    <p className="mt-1 break-words text-sm font-semibold leading-relaxed text-[#1f2937]">
                      {group.courses?.[0]?.sharedClassEnabled ? '由學校安排' : (group.coachName || '不指定')}
                    </p>
                  </div>
                  <div className="rounded-sm bg-[#f8fafc] px-3 py-2">
                    <p className="flex items-center gap-1 text-[11px] font-semibold text-[#94a3b8]">
                      <Package size={13} /> 裝備
                    </p>
                    <p className="mt-1 text-sm font-semibold text-[#1f2937]">
                      {getEquipmentOptionLabel(group.equipmentOption, group.equipment)}
                    </p>
                  </div>
                </div>

                <div className="space-y-2 px-4 pb-4">
                  {courseSegments.map((segment, segmentIndex) => {
                    const firstCourse = segment.courses[0]
                    const segmentTotal = segment.courses.some((course) => course.price === null)
                      ? null
                      : segment.courses.reduce((sum, course) => sum + Number(course.price || 0), 0)
                    const removeSegment = () => {
                      const indexes = segment.courses
                        .map((course) => course.originalIndex)
                        .sort((a, b) => b - a)
                      if (indexes.length >= (group.courses || []).length) {
                        onRemoveGroup?.(group.id)
                        return
                      }
                      indexes.forEach((index) => onRemoveCourse?.(group.id, index))
                    }

                    return (
                      <div key={segment.key} className="grid gap-3 rounded-sm border border-[#edf1f6] bg-[#fbfdff] px-3 py-3 sm:grid-cols-[1fr_auto] sm:items-center">
                        <div>
                          <p className="mb-1 text-xs font-semibold text-[#2b5f8f]">
                            第 {segmentIndex + 1} 項課程
                          </p>
                          <p className="text-sm font-semibold text-[#1f2937]">
                            {firstCourse?.courseTemplateName || firstCourse?.courseTypeName}
                          </p>
                          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#64748b]">
                            <span className="inline-flex items-center gap-1">
                              <Calendar size={13} />
                              {formatCourseSegmentDates(segment.courses)}
                            </span>
                            <span className="inline-flex items-center gap-1">
                              <Clock size={13} />
                              {firstCourse?.timeSlotStart || '--:--'} - {firstCourse?.timeSlotEnd || '--:--'}
                            </span>
                            {segment.courses.length > 1 && (
                              <span>{segment.courses.length} 天</span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center justify-between gap-3 sm:justify-end">
                          <span className="text-sm font-semibold text-[#2b5f8f]">{formatCurrency(segmentTotal)}</span>
                          {canEditCart && courseSegments.length > 1 && (
                            <button
                              type="button"
                              onClick={removeSegment}
                              aria-label="刪除此課程項目"
                              className="inline-flex h-8 w-8 items-center justify-center rounded-full text-[#94a3b8] hover:bg-[#fff1f1] hover:text-[#b42318]"
                            >
                              <Trash2 size={15} />
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}

                  {(group.equipmentAssistanceTimeLabel || group.equipmentOption === 'class_time_help') && (
                    <div className="rounded-sm border border-[#dbeafe] bg-[#eff6ff] px-3 py-2 text-sm text-[#1e3a8a]">
                      <span className="font-semibold">裝備協助：</span>
                      {group.equipmentAssistanceTimeLabel || '課程時間內協助'}
                    </div>
                  )}

                  {(group.coachFee || group.languageFee || group.equipmentRentalFee) ? (
                    <div className="space-y-1 border-t border-[#edf1f6] pt-3">
                      {group.coachFee > 0 && <div className="flex justify-between text-xs text-[#64748b]"><span>教練指定費</span><span>{formatCurrency(group.coachFee)}</span></div>}
                      {group.languageFee > 0 && <div className="flex justify-between text-xs text-[#64748b]"><span>語言加價</span><span>{formatCurrency(group.languageFee)}</span></div>}
                      {group.equipmentRentalFee > 0 && <div className="flex justify-between text-xs text-[#64748b]"><span>加購協助費</span><span>{formatCurrency(group.equipmentRentalFee)}</span></div>}
                    </div>
                  ) : null}

                  <div className="flex items-center justify-between border-t border-[#edf1f6] pt-3">
                    <span className="text-sm font-semibold text-[#64748b]">小計</span>
                    <span className="text-base font-bold text-[#1f2937]">{formatCurrency(group.totalPrice)}</span>
                  </div>
                </div>
              </article>
              )
            })}
          </div>
        )}

        <h3 className="text-lg font-semibold text-[#1f2937] font-display mb-4">
          聯絡資訊
        </h3>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-[#94a3b8] uppercase tracking-wider mb-1">
              姓名 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={contactInfo.name}
              aria-label="聯絡人姓名"
              required
              readOnly={isPaid}
              onChange={(e) => setContactInfo({ ...contactInfo, name: e.target.value })}
              placeholder="請填寫實際聯絡人姓名"
              className="w-full px-4 py-3 rounded-sm border border-[#e2e8f0] bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#94a3b8] uppercase tracking-wider mb-1">
              Email
            </label>
            <input
              type="email"
              value={contactInfo.email}
              readOnly={isPaid}
              onChange={(e) => setContactInfo({ ...contactInfo, email: e.target.value })}
              className="w-full px-4 py-3 rounded-sm border border-[#e2e8f0] bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#94a3b8] uppercase tracking-wider mb-1">
              聯絡電話 <span className="text-red-500">*</span>
            </label>
            <input
              type="tel"
              value={contactInfo.phone}
              readOnly={isPaid}
              onChange={(e) => setContactInfo({ ...contactInfo, phone: e.target.value })}
              className="w-full px-4 py-3 rounded-sm border border-[#e2e8f0] bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
              placeholder="0912345678"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#94a3b8] uppercase tracking-wider mb-1">
              通訊軟體 <span className="text-red-500">*</span>
            </label>
            <select
              value={contactInfo.messengerType}
              disabled={isPaid}
              onChange={(e) => {
                const messengerType = e.target.value
                setContactInfo({
                  ...contactInfo,
                  messengerType,
                  messengerId: messengerType ? contactInfo.messengerId : '',
                })
              }}
              className="w-full px-4 py-3 rounded-sm border border-[#e2e8f0] bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
            >
              <option value="">請選擇通訊軟體</option>
              {messengerOptions.map((option: SelectOption) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#94a3b8] uppercase tracking-wider mb-1">
              通訊軟體 ID <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={contactInfo.messengerId}
              readOnly={isPaid}
              onChange={(e) => setContactInfo({ ...contactInfo, messengerId: e.target.value })}
              disabled={!contactInfo.messengerType}
              className="w-full px-4 py-3 rounded-sm border border-[#e2e8f0] bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
              placeholder={contactInfo.messengerType ? `請輸入 ${contactInfo.messengerType} ID` : '請先選擇通訊軟體'}
            />
          </div>
        </div>
      </div>

      {/* Right - 金額與政策 */}
      <div className="bg-[#f7f8fa] p-6 rounded-sm">
        <h3 className="text-lg font-semibold text-[#1f2937] font-display mb-6">
          金額明細
        </h3>

        <div className="space-y-3 mb-6">
          <div className="flex justify-between text-sm">
            <span className="text-[#6b7280]">{isPaid ? '本筆應付' : '課程費用'}</span>
            <span className="text-[#1f2937]">{pricePending ? '價格待確認' : `NT$ ${cartSubtotal.toLocaleString()}`}</span>
          </div>

          {!isPaid && <div>
            <label className="block text-xs font-semibold text-[#94a3b8] uppercase tracking-wider mb-1">
              折扣碼
            </label>
            <input
              type="text"
              value={discountCode}
              onChange={(e) => setDiscountCode(e.target.value)}
              disabled={isPaid}
              className="w-full px-3 py-2 rounded-sm border border-[#e2e8f0] bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
            />
            {!isPaid && isDiscountPreviewLoading && (
              <p className="mt-1 text-xs text-[#64748b]">折扣試算中...</p>
            )}
            {!isPaid && discountPreview?.discount_code_error && discountCode.trim() && (
              <p className="mt-1 text-xs text-red-600">{discountPreview.discount_code_error}</p>
            )}
          </div>}

          <div>
            <label className="block text-xs font-semibold text-[#94a3b8] uppercase tracking-wider mb-1">
              從哪裡得知 / 活動來源 <span className="text-red-500">*</span>
            </label>
            <select
              value={referrer}
              disabled={isPaid}
              onChange={(e) => {
                setReferrer(e.target.value)
                setReferrerDetail('')
              }}
              className="w-full px-3 py-2 rounded-sm border border-[#e2e8f0] bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
            >
              <option value="">請選擇來源</option>
              {referralSourceOptions.map((option: SelectOption) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            {referrer && (
              <input
                type="text"
                value={referrerDetail}
                readOnly={isPaid}
                onChange={(e) => setReferrerDetail(e.target.value)}
                placeholder={referrer === '其他' ? '請填寫來源' : '補充說明（例如：推薦人姓名、活動名稱）'}
                className="mt-2 w-full px-3 py-2 rounded-sm border border-[#e2e8f0] bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
              />
            )}
          </div>

          {!isPaid && discountPreview?.applied_discounts?.map((discount: any) => (
            <div key={discount.id} className="flex justify-between text-sm text-emerald-700">
              <span>{discount.name || discount.code}</span>
              <span>-NT$ {Number(discount.amount || 0).toLocaleString()}</span>
            </div>
          ))}
          {!isPaid && discountTotal > 0 && (
            <div className="flex justify-between text-sm font-semibold text-emerald-700">
              <span>折扣合計</span>
              <span>-NT$ {discountTotal.toLocaleString()}</span>
            </div>
          )}
        </div>

        <div className="border-t border-[#d4dbe4] pt-4 mb-6">
          <div className="flex justify-between items-baseline">
            <span className="text-sm font-semibold text-[#1f2937]">{isSharedClassCart && !isPaid ? '成班後應付' : '總金額'}</span>
            <span className="text-2xl font-bold text-[#2b5f8f]">
              {pricePending ? '價格待確認' : `NT$ ${total.toLocaleString()}`}
            </span>
          </div>
        </div>

        {pricePending && <p role="status" className="mb-4 text-sm text-amber-800">{isDiscountPreviewLoading ? '正在確認最新價格…' : '尚未取得最新價格，請按課程「修改」重新確認日期、時段與價格後再送出。'}</p>}

        <h4 className="text-sm font-semibold text-[#1f2937] mb-3">付款方式</h4>
        {isSharedClassCart && !isPaid && (
          <p className="mb-3 text-xs leading-5 text-[#64748b]">目前只需報名，不必先付款；滿成班人數後才會提供付款資訊。若排課尚待確認，會先暫停付款。</p>
        )}
        {!isPaid && !isSharedClassCart && (
          <p className="mb-6 text-xs leading-5 text-[#64748b]">送出訂單後，系統會依訂單所在地與已開通的付款服務，顯示可用付款方式及收款帳戶。</p>
        )}
        {isPaid && submittedReservation.payment_methods.length === 0 && (
          <p className="mb-6 rounded-sm border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">此訂單目前沒有可用的付款方式，請聯絡客服確認收款資訊；請勿自行匯款。</p>
        )}
        {isPaid && submittedReservation.payment_methods.length > 0 && <div className="space-y-2 mb-6">
          {[
            { id: 'bank', method: 'bank_transfer', label: '銀行轉帳' },
            { id: 'card', method: 'newebpay', label: '藍新信用卡支付' },
          ].filter((p) => submittedReservation.payment_methods.includes(p.method)).map((p) => (
            <label key={p.id} className={`flex cursor-pointer items-center gap-3 rounded-sm border p-3 transition-colors hover:border-[#2b5f8f] ${paymentMethod === p.id ? 'border-[#2b5f8f]' : 'border-[#e5e9f2]'}`}>
              <input
                type="radio"
                name="payment"
                value={p.id}
                checked={paymentMethod === p.id}
                onChange={(e) => setPaymentMethod(e.target.value as any)}
                className="text-[#2b5f8f] focus:ring-[#2b5f8f]"
              />
              <span className="text-sm text-[#1f2937]">{p.label}</span>
            </label>
          ))}
        </div>}

        {/* 階段 3a：尚未送出訂單 → 顯示同意條款 */}
        {!isPaid && (
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={acceptedPolicy}
              onChange={(e) => setAcceptedPolicy(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded text-[#2b5f8f] focus:ring-[#2b5f8f]"
            />
            <span className="text-xs text-[#6b7280] leading-relaxed">
              我已閱讀並同意{' '}
              <a href={cancellationPolicyUrl} className="text-[#2b5f8f] underline">取消及更改政策</a>
            </span>
          </label>
        )}

        {/* 階段 3b：已送出訂單 → 顯示付款資訊 */}
        {isPaid && paymentMethod === 'bank' && submittedReservation.payment_methods.includes('bank_transfer') && (
          <div className="mt-2 p-4 bg-white border border-[#2b5f8f]/30 rounded-sm">
            <h4 className="text-sm font-semibold text-[#2b5f8f] mb-3">匯款資訊</h4>
            <div className="mb-4 rounded-sm border border-[#f5c16c] bg-[#fff7e6] p-3 text-xs leading-5 text-[#92400e]">
              {submittedReservation.payment_expires_at
                ? `請於 ${new Date(submittedReservation.payment_expires_at).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' })} 前完成匯款。`
                : '請於訂單付款期限內完成匯款。'}若尚未匯款，可按「稍後匯款」；若已匯款，請填寫匯款帳戶後五碼並按「確認已匯款」。
            </div>
            {submittedReservation.payment_infos.length > 1 && <p className="mb-3 text-sm font-semibold text-[#92400e]">每筆預約請分別匯至下方對應帳戶，不要將總金額匯入單一帳戶。</p>}
            <div className="space-y-4 text-sm">
              {submittedReservation.payment_infos.map((info: SubmittedReservation['payment_infos'][number]) => (
                <div key={info.reservation_group_id} className="space-y-2 border-t border-[#e5e9f2] pt-3">
                  {submittedReservation.payment_infos.length > 1 && <p className="font-semibold text-[#1f2937]">預約 #{info.reservation_group_id}</p>}
                  <div className="flex justify-between"><span className="text-[#6b7280]">銀行</span><span className="text-[#1f2937] font-medium">{info.bank_info.bank_name || '—'}</span></div>
                  <div className="flex justify-between"><span className="text-[#6b7280]">分行</span><span className="text-[#1f2937] font-medium">{info.bank_info.bank_branch || '—'}</span></div>
                  <div className="flex justify-between"><span className="text-[#6b7280]">帳號</span><span className="text-[#1f2937] font-mono font-semibold">{info.bank_info.bank_account_number || '—'}</span></div>
                  <div className="flex justify-between"><span className="text-[#6b7280]">戶名</span><span className="text-[#1f2937] font-medium">{info.bank_info.bank_account_holder || '—'}</span></div>
                  <div className="flex justify-between"><span className="text-[#1f2937] font-semibold">匯款金額</span><span className="text-[#2b5f8f] text-base font-bold">NT$ {info.total_amount.toLocaleString()}</span></div>
                </div>
              ))}
            </div>

            <div className="mt-4">
              <label className="block text-xs font-semibold text-[#94a3b8] uppercase tracking-wider mb-1">
                匯款帳戶後五碼（已匯款再填）
              </label>
              <input
                type="text"
                value={senderAccount}
                onChange={(e) => setSenderAccount(e.target.value.replace(/\D/g, '').slice(0, 5))}
                maxLength={5}
                placeholder="請輸入您匯款帳戶的後五碼"
                className="w-full px-3 py-2 rounded-sm border border-[#e2e8f0] bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#2b5f8f]/30"
              />
              <p className="mt-1 text-xs text-[#6b7280]">只有按「確認已匯款」時需要填寫，用於客服對帳。</p>
            </div>
          </div>
        )}

        {isPaid && paymentMethod === 'card' && submittedReservation.payment_methods.includes('newebpay') && (
          <div className="mt-2 p-4 bg-white border border-[#2b5f8f]/30 rounded-sm text-center">
            <p className="text-sm text-[#1f2937] mb-1">
              {submittedReservation.reservation_group_ids.length > 1
                ? '多筆預約目前請使用銀行轉帳，或分開結帳使用信用卡'
                : '將於下一步開啟藍新付款視窗'}
            </p>
            <p className="text-xl font-bold text-[#2b5f8f]">NT$ {total.toLocaleString()}</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ============== Step 4: 完成 ==============
function Step4Complete({ notice = '', flow = 'payment' }: { notice?: string; flow?: CompletionFlow }) {
  const navigate = useNavigate()
  const ordersUrl = useSiteLink('/membership/orders')
  return (
    <div className="text-center py-10 md:py-16">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-[#e9eef3] text-[#2b5f8f] mb-6">
        <Check size={40} />
      </div>
      <h2 className="text-2xl md:text-3xl font-semibold text-[#1f2937] font-display mb-4">
        {flow === 'collecting_class' ? '報名已保留，等待成班' : flow === 'staff' ? '訂單已保留，待課服安排' : flow === 'coach' ? '訂單已建立，待教練確認' : '預約送出成功'}
      </h2>
      <div className="max-w-md mx-auto mb-8 space-y-3 text-left text-sm text-[#6b7280] leading-relaxed">
        <p className="text-center">
          {notice || '感謝您的預約，系統已收到您的訂單。'}
        </p>
        <div className="rounded-sm border border-[#e2e8f0] bg-[#f8fafc] p-4">
          <p className="font-semibold text-[#1f2937] mb-2">接下來請留意：</p>
          <ul className="space-y-1.5 list-disc pl-5">
            {flow === 'collecting_class' ? (
              <>
                <li>目前正在湊班，尚未達到成班人數。</li>
                <li>成班且課程安排確認後，會通知您付款；現在不需要匯款。</li>
                <li>可在會員訂單查看最新報名狀態。</li>
              </>
            ) : flow === 'staff' ? (
              <>
                <li>課服會協助確認可用教練或與您討論其他日期。</li>
                <li>課程安排確認前不需要付款，請留意課服通知。</li>
              </>
            ) : flow === 'coach' ? (
              <>
                <li>此訂單目前需等待教練確認接課。</li>
                <li>確認完成前不需要付款，客服會再通知後續付款與安排。</li>
              </>
            ) : flow === 'bank_submitted' ? (
              <>
                <li>客服核對匯款後，會更新訂單的付款狀態。</li>
                <li>請在會員訂單查看最新狀態；無須再次填寫匯款後五碼。</li>
              </>
            ) : flow === 'bank_later' ? (
              <>
                <li>匯款後，請提供匯款帳戶後五碼給客服對帳。</li>
                <li>客服確認付款後，會再與您確認課程安排。</li>
              </>
            ) : (
              <>
                <li>請確認 Email 是否收到預約確認信。</li>
                <li>請在付款視窗完成信用卡付款，並於會員訂單確認付款狀態。</li>
                <li>客服確認訂單後，會再與您確認後續安排。</li>
              </>
            )}
          </ul>
        </div>
        <p className="text-center">
          如有任何問題，歡迎加入 SnowLand 官方客服聯繫。
        </p>
      </div>
      <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
        <a
          href={ordersUrl}
          className="inline-flex items-center justify-center rounded-full border border-[#2b5f8f] bg-white px-8 py-3 text-sm font-semibold text-[#2b5f8f] hover:bg-[#f0f6fb] transition-colors"
        >
          查看我的訂單
        </a>
        <a
          href="https://line.me/R/ti/p/@snowlandcz?from=page&searchId=snowlandcz"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center justify-center rounded-full border border-[#2b5f8f] bg-white px-8 py-3 text-sm font-semibold text-[#2b5f8f] hover:bg-[#f0f6fb] transition-colors"
        >
          加入官方客服
        </a>
        <button
          onClick={() => navigate('..')}
          className="inline-flex items-center justify-center rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white hover:bg-[#8ec8f0] transition-colors"
        >
          返回首頁
        </button>
      </div>
    </div>
  )
}
