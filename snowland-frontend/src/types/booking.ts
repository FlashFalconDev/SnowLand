// 課程大類
export interface CourseCategory {
  id: number
  name: string
  service_type: 'ski' | 'photo'
  display_order: number
  available_resorts: string[]
}

// 雪場
export interface Resort {
  name: string
  display_name: string
  auto_scheduling_enabled: boolean
  equipment_time_slots?: EquipmentAssistanceTimeSlot[]
}

export interface EquipmentAssistanceTimeSlot {
  id: number
  equipment_option?: 'purchaseAssistanceTime' | 'assistDuringCourse' | 'rentWithoutyourself' | 'ownWithoutAssistance'
  lesson_duration?: 'any' | 'full_day' | 'half_day'
  session_period?: 'any' | 'all_day' | 'morning' | 'afternoon'
  day_type?: 'same_day' | 'previous_day'
  course_template_ids?: number[]
  course_template_names?: string[]
  label: string
  start_time: string | null
  end_time: string | null
  is_active: boolean
  display_order?: number
  description?: string
}

// 課程類型
export interface CourseType {
  id: number
  name: string
  category_id: number
  display_order: number
  available_resorts: string[]
}

// 課程模板
export interface CourseTemplate {
  id: number
  name: string
  course_type_id: number
  course_type_name: string
  category_name: string
  display_order: number
  duration_hours: number
  max_capacity: number
  is_active: boolean
  resorts: string[]
  booking_open_date: string | null
  booking_close_date: string | null
  course_start_date: string | null
  course_end_date: string | null
  minimum_coach_price_level?: string
  minimum_coach_price_level_label?: string
  allowed_coaches?: number[]
}

// 課程時段
export interface CourseSession {
  id: number
  template_id: number
  start_time: string
  end_time: string
  is_active: boolean
}

// 教練
export interface Coach {
  pk: number
  name: string
  description: string
  specialties: string[]
  languages: string[]
  image: string
}

// 裝備選項類型
export type EquipmentOption = 'self_rent' | 'own_equipment' | 'class_time_help' | 'extra_time_help'

// 預約狀態
export interface BookingState {
  selectedCourseCategory: number | null
  selectedResort: string | null
  selectedCourseType: number | null
  peopleCount: number
  hasUnder6: boolean
  under7CanSelfSki: boolean
  abilityLevelCounts: Record<string, number>
  selectedAbilityLevel: string
  selectedCoach: number | null
  selectedCourseTemplate: number | null
  selectedDate: string | null
  selectedTimeSlot: number | null
  selectedLanguage: string | null
  needEquipment: boolean
  equipmentOption: EquipmentOption | null
  equipmentAssistanceTimeSlotId: number | null
  equipmentAssistanceTimeLabel: string
}

// 單堂課程
export interface Course {
  segmentId?: string
  date: string
  courseTypeId: number
  courseTypeName: string
  courseTemplateId: number
  courseTemplateName: string
  durationHours: number
  timeSlotId: number
  timeSlotStart: string
  timeSlotEnd: string
  price: number | null // null 表示計算中
}

// 預約組（一個預約可以包含多堂課）
export interface ReservationGroup {
  id: string // 唯一識別碼

  // 共享資訊（整組課程共用）
  coach: number | 'any'
  coachName: string
  peopleCount: number
  abilityLevel: string
  abilityLevelName: string
  abilityLevelCounts?: Record<string, number>
  equipment: boolean
  equipmentOption: EquipmentOption | null
  equipmentAssistanceTimeSlotId: number | null
  equipmentAssistanceTimeLabel: string
  language: string | null
  resort: string
  resortName: string
  courseCategory: string
  courseFee?: number
  coachFee?: number
  languageFee?: number
  equipmentRentalFee?: number

  // 課程列表
  courses: Course[]

  // 總價
  totalPrice: number | null
}

// 購物車項目（改為 ReservationGroup 的別名）
export interface CartItem extends ReservationGroup {}
