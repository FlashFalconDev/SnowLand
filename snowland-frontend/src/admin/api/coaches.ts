/**
 * 教練管理 API
 *
 * 後端：API/admin_views.py CoachAdminViewSet
 * 路徑：/api/admin/<client_code>/coaches/
 */
import adminApi from './axios'

// ============== Types ==============
export type AvailabilityStatus = 'active' | 'passive' | 'unavailable'
export type AbilityLevel = 'no_exp' | 'level1' | 'level2' | 'level3' | 'level4' | 'level5' | 'level6'
export type Language = 'zh' | 'en' | 'yue'
export type PriceLevel = 'Lv1' | 'Lv2' | 'Lv3' | 'director'
export type CertificationCategory = 'ski' | 'snowboard' | 'photo' | 'other'

export interface CoachCertification {
  category: CertificationCategory
  certificate: string
  level: string
  note?: string
  show_on_website: boolean
}

export interface CoachResortNested {
  resort_id: number
  resort_name: string
  resort_priority: number
  assignment_score: number
}

export interface CoachCourseLevelNested {
  course_type_id: number
  course_type_name: string
  ability_levels: AbilityLevel[]
  price_level: PriceLevel
  course_order: number
}

export interface Coach {
  id: number
  name: string
  user_id?: number | null
  user_email?: string | null
  user_name?: string
  user_username?: string
  languages: Language[]
  availability_status: AvailabilityStatus
  assignment_score: number
  img: string
  website_enabled: boolean
  website_slug: string
  website_sort_order: number
  website_card_bio: string
  certifications: CoachCertification[]
  resorts: CoachResortNested[]
  course_levels: CoachCourseLevelNested[]
  created_at: string
}

export interface CoachWriteData {
  name: string
  user_id?: number | null
  languages: Language[]
  availability_status: AvailabilityStatus
  assignment_score: number
  img: string
  website_enabled: boolean
  website_slug: string
  website_sort_order: number
  website_card_bio: string
  certifications?: CoachCertification[]
  resorts_input?: { resort_id: number; resort_priority?: number; assignment_score?: number }[]
  course_levels_input?: {
    course_type_id: number
    ability_levels: AbilityLevel[]
    price_level: PriceLevel
    course_order?: number
  }[]
}

interface ListResponse {
  code: number
  msg: string
  data: { list: Coach[]; total: number }
}

interface DetailResponse {
  code: number
  msg: string
  data: Coach
}

// ============== API Calls ==============

export async function fetchCoaches(): Promise<Coach[]> {
  const res = (await adminApi.get('/coaches/')) as unknown as ListResponse
  return res.data?.list || []
}

export async function fetchCoach(id: number): Promise<Coach> {
  const res = (await adminApi.get(`/coaches/${id}/`)) as unknown as DetailResponse
  return res.data
}

export async function createCoach(data: CoachWriteData): Promise<Coach> {
  const res = (await adminApi.post('/coaches/', data)) as unknown as DetailResponse
  return res.data
}

export async function updateCoach(id: number, data: CoachWriteData): Promise<Coach> {
  const res = (await adminApi.patch(`/coaches/${id}/`, data)) as unknown as DetailResponse
  return res.data
}

export async function deleteCoach(id: number): Promise<void> {
  await adminApi.delete(`/coaches/${id}/`)
}
