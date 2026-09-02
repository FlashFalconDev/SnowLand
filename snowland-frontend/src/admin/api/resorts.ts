/**
 * 雪場管理 API
 */
import adminApi from './axios'

export type FeeType =
  | 'coach_director' | 'coach_lv2' | 'coach_general'
  | 'language_zh' | 'language_en' | 'language_yue'
  | 'equipment_1to3' | 'equipment_4to6'

export interface ResortFee {
  fee_type: FeeType
  price: number
  is_active: boolean
  description?: string
}

export interface EquipmentPricingTier {
  id?: number
  min_people: number
  max_people: number
  price: number
  is_active: boolean
  display_order?: number
  description?: string
}

export interface EquipmentRentalItem {
  id?: number
  code: string
  name: string
  daily_price: number
  additional_day_price: number
  is_active: boolean
  display_order?: number
  description?: string
}

export type EquipmentOption = 'purchaseAssistanceTime' | 'assistDuringCourse' | 'rentWithoutyourself' | 'ownWithoutAssistance'
export type LessonDuration = 'any' | 'full_day' | 'half_day'
export type SessionPeriod = 'any' | 'all_day' | 'morning' | 'afternoon'
export type DayType = 'same_day' | 'previous_day'

export interface EquipmentAssistanceTimeSlot {
  id?: number
  equipment_option?: EquipmentOption
  equipment_options?: EquipmentOption[]
  lesson_duration?: LessonDuration
  lesson_durations?: LessonDuration[]
  session_period?: SessionPeriod
  session_periods?: SessionPeriod[]
  day_type?: DayType
  day_types?: DayType[]
  course_template_ids?: number[]
  course_template_names?: string[]
  label: string
  start_time?: string | null
  end_time?: string | null
  is_active: boolean
  display_order?: number
  description?: string
}

export interface Resort {
  id: number
  name: string
  display_name: string
  auto_scheduling_enabled: boolean
  fees: ResortFee[]
  equipment_tiers: EquipmentPricingTier[]
  equipment_rental_items: EquipmentRentalItem[]
  equipment_time_slots: EquipmentAssistanceTimeSlot[]
}

export interface ResortWriteData {
  name: string
  display_name: string
  auto_scheduling_enabled: boolean
  fees_input?: ResortFee[]
  equipment_tiers_input?: EquipmentPricingTier[]
  equipment_rental_items_input?: EquipmentRentalItem[]
  equipment_time_slots_input?: EquipmentAssistanceTimeSlot[]
}

interface ListResp { code: number; msg: string; data: { list: Resort[]; total: number } }
interface DetailResp { code: number; msg: string; data: Resort }

export async function fetchResorts(): Promise<Resort[]> {
  const res = (await adminApi.get('/resorts/')) as unknown as ListResp
  return res.data?.list || []
}

export async function createResort(data: ResortWriteData): Promise<Resort> {
  const res = (await adminApi.post('/resorts/', data)) as unknown as DetailResp
  return res.data
}

export async function updateResort(id: number, data: ResortWriteData): Promise<Resort> {
  const res = (await adminApi.put(`/resorts/${id}/`, data)) as unknown as DetailResp
  return res.data
}

export async function deleteResort(id: number): Promise<void> {
  await adminApi.delete(`/resorts/${id}/`)
}
