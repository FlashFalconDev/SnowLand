import api from './axios'
import { CourseCategory, Resort, CourseType, CourseTemplate } from '@/types/booking'
import type { CourseSession } from '@/types/booking'

const DISCOUNT_PREVIEW_TIMEOUT_MS = 30000
const RESERVATION_SUBMIT_TIMEOUT_MS = 120000

export interface SiteContentItem {
  id: number
  content_type: string
  location_key: string
  title: string
  subtitle: string
  summary: string
  body: string
  image_url: string
  link_url: string
  source: string
  external_id: string
  tags: string[]
  metadata: Record<string, any>
  status: string
  start_at: string | null
  end_at: string | null
  display_order: number
  is_pinned: boolean
}

export const fetchSiteContent = async (params?: {
  content_type?: string
  location_key?: string
  tag?: string
  limit?: number
  include_ended?: boolean
}): Promise<SiteContentItem[]> => {
  return api.get('/site-content/', { params })
}

// 從 Django 獲取課程大類
export const fetchCourseCategories = async (serviceType?: 'ski' | 'photo'): Promise<CourseCategory[]> => {
  const params = serviceType ? { service_type: serviceType } : undefined
  return api.get('/course-categories/', { params })
}

// 從 Django 獲取雪場列表
export const fetchResorts = async (): Promise<Resort[]> => {
  return api.get('/resorts/')
}

// 從 Django 獲取課程類型
export const fetchCourseTypes = async (categoryId?: number, resort?: string): Promise<CourseType[]> => {
  const params: { category_id?: number; resort?: string } = {}
  if (categoryId) params.category_id = categoryId
  if (resort) params.resort = resort
  return api.get('/course-types/', { params })
}

// 從 Django 獲取教練列表（這個 API 已經存在）
export const fetchCoaches = async (params: {
  resort: string
  courseType: string
  abilityLevel?: string
  courseTemplate?: number | string
  courseDates?: string
  timeSlot?: number | string
}): Promise<{ coach_list: any[]; courses?: any[] }> => {
  return await api.get('/coaches/', { params }) as unknown as { coach_list: any[]; courses?: any[] }
}

// 從 Django 獲取課程模板
export const fetchCourseTemplates = async (params?: {
  course_type_id?: number
  resort?: string
}): Promise<CourseTemplate[]> => {
  return api.get('/course-templates/', { params })
}

// 從 Django 獲取課程時段（可選帶 date 檢查容量+合規範）
export const fetchCourseSessions = async (templateId?: number, date?: string): Promise<CourseSession[]> => {
  const params: any = {}
  if (templateId) params.template_id = templateId
  if (date) params.date = date
  return await api.get('/course-sessions/', { params }) as unknown as CourseSession[]
}

// 取得某模板某月的可預約日期清單
export const fetchAvailableDates = async (
  templateId: number,
  month?: string  // YYYY-MM
): Promise<{
  template_id: number
  month: string
  booking_open_date: string | null
  booking_close_date: string | null
  course_start_date: string | null
  course_end_date: string | null
  available_dates: string[]
}> => {
  const params = month ? { month } : {}
  return (await api.get(`/course-templates/${templateId}/available-dates/`, { params })) as any
}

// 計算課程價格
export interface CalculatePriceParams {
  template_id: number        // 課程模板ID
  resort: string             // 雪場名稱
  people_count: number       // 人數
  course_date: string        // 日期 YYYY-MM-DD
  coach?: number | 'any' | null
  language?: string | null
  equipment_option?: string | null
  bookings_count?: number
}

export interface CalculatePriceResponse {
  price: number
  course_fee?: number
  coach_fee?: number
  language_fee?: number
  equipment_rental_fee?: number
  total_price?: number
  course_type_id?: number
  course_type_name?: string
  course_template_name?: string
  duration_hours?: number
}

export const calculatePrice = async (params: CalculatePriceParams): Promise<CalculatePriceResponse> => {
  return api.get('/calculate-price/', { params })
}

// 創建預約
export interface CreateReservationParams {
  staff_link?: string
  contact?: {
    name?: string
    email?: string
    phone?: string
    messengerType?: string
    messenger_type?: string
    messengerId?: string
    messenger_id?: string
    referralSource?: string
    referral_source?: string
    referrer?: string
  }
  discount_code?: string
  discountCode?: string
  cart: Array<{
    coach: number | 'any'
    coachName: string
    peopleCount: number
    abilityLevel: string
    abilityLevelName: string
    abilityLevelCounts?: Record<string, number>
    equipment: boolean
    equipmentOption: string | null
    equipmentAssistanceTimeSlotId?: number | null
    equipmentAssistanceTimeLabel?: string
    language: string | null
    resort: string
    resortName: string
    courseCategory: string
    courseFee?: number
    coachFee?: number
    languageFee?: number
    equipmentRentalFee?: number
    courses: Array<{
      date: string
      courseTypeId: number
      courseTypeName: string
      courseTemplateId: number
      courseTemplateName: string
      durationHours: number
      timeSlotStart: string
      timeSlotEnd: string
      price: number | null
    }>
    totalPrice: number | null
  }>
}

export async function resolveStaffBookingLink(token: string): Promise<{ token: string; title: string; campus: { id: number; name: string }; created_by: string }> {
  return await api.get(`/staff-booking-link/${token}/`) as unknown as { token: string; title: string; campus: { id: number; name: string }; created_by: string }
}

export interface DiscountPreviewDiscount {
  id: number
  code: string
  name: string
  amount: number
  is_auto_apply: boolean
  new_customer_only: boolean
  apply_scope: 'all' | 'ski' | 'photo' | 'bundle'
  amount_apply_mode: 'order' | 'item' | 'course' | 'hour'
}

export interface DiscountPreviewResponse {
  code: number
  msg: string
  subtotal: number
  discount_total: number
  total: number
  item_subtotals: number[]
  item_discount_amounts: number[]
  applied_discounts: DiscountPreviewDiscount[]
  discount_code_error?: string
  is_new_customer?: boolean
}

export const previewDiscounts = async (data: CreateReservationParams): Promise<DiscountPreviewResponse> => {
  return api.post('/discount-preview/', data, { timeout: DISCOUNT_PREVIEW_TIMEOUT_MS })
}

export interface CreateReservationResponse {
  code: number
  msg: string
  reservation_group_ids: number[]
  scheduling_failed?: boolean
  pending_coach_confirmation?: boolean
  conflict_details?: any
  requires_payment?: boolean
  payment_url?: string  // 單一預約組的付款URL
  payment_urls?: Array<{  // 多個預約組的付款URLs
    reservation_group_id: number
    payment_url: string
  }>
}

export const createReservation = async (data: CreateReservationParams): Promise<CreateReservationResponse> => {
  return api.post('/create-reservation/', data, { timeout: RESERVATION_SUBMIT_TIMEOUT_MS })
}

// 進階排課（將多天課程拆分為單日單元）
export const superSchedule = async (data: CreateReservationParams): Promise<CreateReservationResponse> => {
  return api.post('/super-schedule/', data, { timeout: RESERVATION_SUBMIT_TIMEOUT_MS })
}

// 取消（刪除）排課失敗的訂單，使用者改其他日期時呼叫
export const cancelFailedReservations = async (
  reservationGroupIds: number[],
): Promise<{ code: number; msg: string; deleted_count: number }> => {
  return api.post(
    '/cancel-failed-reservations/',
    { reservation_group_ids: reservationGroupIds },
    { timeout: RESERVATION_SUBMIT_TIMEOUT_MS },
  )
}
