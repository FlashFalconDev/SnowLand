/**
 * 課程類型 API
 */
import adminApi from './axios'

export interface CourseSession {
  id: number
  template: number
  start_time: string
  end_time: string
  is_active: boolean
}

export interface CourseTemplate {
  id: number
  course_type: number
  course_type_name: string
  name: string
  display_order: number
  duration_hours: number
  max_capacity: number
  billing_mode: 'private' | 'per_person'
  minimum_group_size: number
  minimum_student_level: string
  is_active: boolean
  resorts: number[]
  resort_names: string[]
  booking_open_date?: string | null
  booking_close_date?: string | null
  course_start_date?: string | null
  course_end_date?: string | null
  minimum_coach_price_level?: string
  minimum_coach_price_level_label?: string
  allowed_coaches?: number[]
  allowed_coach_names?: string[]
  sessions: CourseSession[]
}

export interface CourseType {
  id: number
  category: number
  name: string
  display_order: number
  available_resorts: number[]
  available_resort_names: string[]
  templates: CourseTemplate[]
}

export interface CourseCategory {
  id: number
  name: string
  service_type: 'ski' | 'photo'
  display_order: number
  available_resorts: number[]
  available_resort_names: string[]
  types: CourseType[]
}

interface ListResp<T> { code: number; msg: string; data: { list: T[]; total: number } }
interface DetailResp<T> { code: number; msg: string; data: T }

export async function fetchCourseCategories(): Promise<CourseCategory[]> {
  const res = (await adminApi.get('/course-categories/')) as unknown as ListResp<CourseCategory>
  return res.data?.list || []
}

export async function fetchCourseTypes(): Promise<CourseType[]> {
  const res = (await adminApi.get('/course-types/')) as unknown as ListResp<CourseType>
  return res.data?.list || []
}

export async function fetchCourseTemplates(): Promise<CourseTemplate[]> {
  const res = (await adminApi.get('/course-templates/')) as unknown as ListResp<CourseTemplate>
  return res.data?.list || []
}

// ============== Category CRUD ==============
export async function createCategory(payload: { name: string; service_type?: 'ski' | 'photo'; display_order?: number; available_resorts?: number[] }) {
  const res = (await adminApi.post('/course-categories/', payload)) as unknown as DetailResp<CourseCategory>
  return res.data
}
export async function updateCategory(id: number, payload: any) {
  const res = (await adminApi.patch(`/course-categories/${id}/`, payload)) as unknown as DetailResp<CourseCategory>
  return res.data
}
export async function deleteCategory(id: number) {
  await adminApi.delete(`/course-categories/${id}/`)
}

// ============== Type CRUD ==============
export async function createType(payload: { category: number; name: string; display_order?: number; available_resorts?: number[] }) {
  const res = (await adminApi.post('/course-types/', payload)) as unknown as DetailResp<CourseType>
  return res.data
}
export async function updateType(id: number, payload: any) {
  const res = (await adminApi.patch(`/course-types/${id}/`, payload)) as unknown as DetailResp<CourseType>
  return res.data
}
export async function deleteType(id: number) {
  await adminApi.delete(`/course-types/${id}/`)
}

// ============== Template CRUD ==============
export async function createTemplate(payload: any) {
  const res = (await adminApi.post('/course-templates/', payload)) as unknown as DetailResp<CourseTemplate>
  return res.data
}
export async function updateTemplate(id: number, payload: any) {
  const res = (await adminApi.patch(`/course-templates/${id}/`, payload)) as unknown as DetailResp<CourseTemplate>
  return res.data
}
export async function deleteTemplate(id: number) {
  await adminApi.delete(`/course-templates/${id}/`)
}

// ============== Session CRUD ==============
export async function createSession(payload: { template: number; start_time: string; end_time: string; is_active?: boolean }) {
  const res = (await adminApi.post('/course-sessions/', payload)) as unknown as DetailResp<CourseSession>
  return res.data
}
export async function updateSession(id: number, payload: any) {
  const res = (await adminApi.patch(`/course-sessions/${id}/`, payload)) as unknown as DetailResp<CourseSession>
  return res.data
}
export async function deleteSession(id: number) {
  await adminApi.delete(`/course-sessions/${id}/`)
}
