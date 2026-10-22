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
  can_manage: boolean
  course_type: number
  course_type_name: string
  name: string
  display_order: number
  duration_hours: number
  payroll_hours: string | null
  can_manage_payroll_hours: boolean
  max_capacity: number
  billing_mode: 'private' | 'per_person'
  minimum_group_size: number
  shared_class_enabled: boolean
  shared_class_minimum_students: number
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

export interface CourseTemplateEditorOptions {
  resorts: { id: number; name: string; display_name: string; can_select: boolean }[]
  coaches: { id: number; name: string; can_select: boolean }[]
}

export type PricingTemplate = Pick<CourseTemplate,
  'id' | 'name' | 'duration_hours' | 'max_capacity' | 'billing_mode' | 'resorts' |
  'booking_open_date' | 'booking_close_date' | 'course_start_date' | 'course_end_date'
>
export interface PricingCourseType { id: number; name: string; templates: PricingTemplate[] }
export interface PricingCourseCategory { id: number; name: string; types: PricingCourseType[] }
export interface PricingResort { id: number; display_name: string }
export interface PricingCatalog {
  list: PricingCourseCategory[]
  total: number
  resort_ids: number[]
  resorts: PricingResort[]
}

interface ListResp<T> { code: number; msg: string; data: { list: T[]; total: number } }
interface DetailResp<T> { code: number; msg: string; data: T }

export async function fetchCourseCategories(): Promise<CourseCategory[]> {
  const res = (await adminApi.get('/course-categories/')) as unknown as ListResp<CourseCategory>
  return res.data?.list || []
}

export async function fetchPricingCatalog(): Promise<PricingCatalog> {
  const res = (await adminApi.get('/course-pricing/catalog/')) as unknown as {
    code: number; msg: string; data: PricingCatalog
  }
  return res.data
}

export async function fetchCourseTypes(): Promise<CourseType[]> {
  const res = (await adminApi.get('/course-types/')) as unknown as ListResp<CourseType>
  return res.data?.list || []
}

export async function fetchCourseTemplates(): Promise<CourseTemplate[]> {
  const res = (await adminApi.get('/course-templates/')) as unknown as ListResp<CourseTemplate>
  return res.data?.list || []
}

export async function fetchCourseTemplateEditorOptions(): Promise<CourseTemplateEditorOptions> {
  const res = (await adminApi.get('/course-templates/editor-options/')) as unknown as {
    code: number; msg: string; data: CourseTemplateEditorOptions
  }
  return res.data
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
