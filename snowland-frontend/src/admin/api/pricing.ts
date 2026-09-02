/**
 * 課程定價 / 季節區間 API
 */
import adminApi from './axios'

// ===== CoursePricing =====

export interface CoursePricing {
  id: number
  templates: number[]
  template_names: string[]
  resort: number
  resort_name: string
  base_price_off_peak: number
  peak_season_surcharge: number
  additional_person_fee: number
  max_capacity: number
  people_tiers: CoursePricingTier[]
  is_active: boolean
}

export interface CoursePricingTier {
  id?: number
  min_people: number
  max_people: number
  price: number
  is_active: boolean
  display_order?: number
}

export interface CoursePricingWriteData {
  templates: number[]
  resort: number
  base_price_off_peak: number
  peak_season_surcharge: number
  additional_person_fee: number
  max_capacity: number
  people_tiers?: CoursePricingTier[]
  is_active: boolean
}

interface PricingListResp { code: number; msg: string; data: { list: CoursePricing[]; total: number } }
interface PricingDetailResp { code: number; msg: string; data: CoursePricing }

export async function fetchCoursePricings(): Promise<CoursePricing[]> {
  const res = (await adminApi.get('/course-pricing/')) as unknown as PricingListResp
  return res.data?.list || []
}

export async function createCoursePricing(data: CoursePricingWriteData): Promise<CoursePricing> {
  const res = (await adminApi.post('/course-pricing/', data)) as unknown as PricingDetailResp
  return res.data
}

export async function updateCoursePricing(id: number, data: CoursePricingWriteData): Promise<CoursePricing> {
  const res = (await adminApi.put(`/course-pricing/${id}/`, data)) as unknown as PricingDetailResp
  return res.data
}

export async function deleteCoursePricing(id: number): Promise<void> {
  await adminApi.delete(`/course-pricing/${id}/`)
}

// ===== SeasonSetting =====

export type SeasonType = 'peak' | 'off'

export interface SeasonSetting {
  id: number
  name: string
  season_type: SeasonType
  start_date: string  // YYYY-MM-DD
  end_date: string    // YYYY-MM-DD
}

export interface SeasonSettingWriteData {
  name: string
  season_type: SeasonType
  start_date: string
  end_date: string
}

interface SeasonListResp { code: number; msg: string; data: { list: SeasonSetting[]; total: number } }
interface SeasonDetailResp { code: number; msg: string; data: SeasonSetting }

export async function fetchSeasons(): Promise<SeasonSetting[]> {
  const res = (await adminApi.get('/seasons/')) as unknown as SeasonListResp
  return res.data?.list || []
}

export async function createSeason(data: SeasonSettingWriteData): Promise<SeasonSetting> {
  const res = (await adminApi.post('/seasons/', data)) as unknown as SeasonDetailResp
  return res.data
}

export async function updateSeason(id: number, data: SeasonSettingWriteData): Promise<SeasonSetting> {
  const res = (await adminApi.put(`/seasons/${id}/`, data)) as unknown as SeasonDetailResp
  return res.data
}

export async function deleteSeason(id: number): Promise<void> {
  await adminApi.delete(`/seasons/${id}/`)
}
