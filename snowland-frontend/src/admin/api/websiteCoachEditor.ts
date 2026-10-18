import adminApi from './axios'

export interface WebsiteCoach {
  id: number
  name: string
  can_manage: boolean
  img: string
  website_enabled: boolean
  website_slug: string
  website_sort_order: number
  website_card_bio: string
  website_profile?: Record<string, unknown>
}
export type WebsiteCoachWrite = Omit<WebsiteCoach, 'id' | 'name' | 'can_manage'>

export async function fetchWebsiteCoachEditor(): Promise<WebsiteCoach[]> {
  const result = await adminApi.get('/website-coach-editor/') as unknown as {data: {list: WebsiteCoach[]}}
  return result.data?.list || []
}
export async function updateWebsiteCoach(id: number, data: WebsiteCoachWrite): Promise<WebsiteCoach> {
  const result = await adminApi.patch(`/website-coach-editor/${id}/`, data) as unknown as {data: WebsiteCoach}
  return result.data
}
