import adminApi from './axios'

export interface AboutSchema {
  version: number; page_key: 'about' | 'join-us'; title: string
  sections: { id: string; label: string; fields: { key: string; kind: 'text' | 'image' | 'link'; label: string; value: string; source_heading?: string; source_first?: boolean; source_contains?: string }[] }[]
}

export async function fetchAboutSchema(): Promise<AboutSchema> {
  const res = (await adminApi.get('/site-content/about-schema/')) as unknown as { data: AboutSchema }
  return res.data
}

export async function fetchJoinSchema(): Promise<AboutSchema> {
  const res = (await adminApi.get('/site-content/join-schema/')) as unknown as { data: AboutSchema }
  return res.data
}

export interface PhotographySchema {
  season: 'winter' | 'summer'; version: number; title: string
  sections: { id: string; label: string; fields: { key: string; kind: 'text' | 'image' | 'link'; label: string; value: string }[] }[]
}

export async function fetchPhotographySchema(season: 'winter' | 'summer'): Promise<PhotographySchema> {
  const res = (await adminApi.get('/site-content/photography-schema/', { params: { season } })) as unknown as { data: PhotographySchema }
  return res.data
}

export type SiteContentType =
  | 'page'
  | 'offer'
  | 'article'
  | 'faq'
  | 'review'
  | 'media'
  | 'social'
  | 'setting'

export type SiteContentStatus = 'draft' | 'active' | 'ended' | 'hidden'

export interface SiteContentItem {
  id: number
  content_type: SiteContentType
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
  metadata: Record<string, unknown>
  status: SiteContentStatus
  computed_status: SiteContentStatus
  start_at: string | null
  end_at: string | null
  display_order: number
  is_pinned: boolean
  created_at: string
  updated_at: string
}

export type SiteContentWriteData = Omit<SiteContentItem, 'id' | 'computed_status' | 'created_at' | 'updated_at'>

interface ListResp<T> { code: number; msg: string; data: { list: T[]; total: number } }
interface DetailResp<T> { code: number; msg: string; data: T }

export async function fetchCurrentWaiver(): Promise<{title:string;body:string;version:string;source_url:string;is_draft:boolean}> {
  const response = await adminApi.get('/site-content/waiver-current/') as unknown as DetailResp<{title:string;body:string;version:string;source_url:string;is_draft:boolean}>
  return response.data
}

export async function fetchReviewContentGroups(): Promise<unknown[]> {
  const res = (await adminApi.get('/site-content/review-locations/')) as unknown as {data: {groups: unknown[]}}
  return res.data?.groups || []
}

export interface ReviewCoachChoice { id: number; name: string; website_enabled: boolean }
export async function fetchReviewCoachChoices(): Promise<ReviewCoachChoice[]> {
  const res = (await adminApi.get('/site-content/review-coaches/')) as unknown as {data: {list: ReviewCoachChoice[]}}
  return res.data?.list || []
}

export async function fetchSiteContents(params?: {
  content_type?: SiteContentType
  location_key?: string
  status?: SiteContentStatus
  search?: string
}): Promise<SiteContentItem[]> {
  const res = (await adminApi.get('/site-content/', { params })) as unknown as ListResp<SiteContentItem>
  return res.data?.list || []
}

export async function createSiteContent(payload: SiteContentWriteData): Promise<SiteContentItem> {
  const res = (await adminApi.post('/site-content/', payload)) as unknown as DetailResp<SiteContentItem>
  return res.data
}

export async function updateSiteContent(id: number, payload: Partial<SiteContentWriteData>): Promise<SiteContentItem> {
  const res = (await adminApi.patch(`/site-content/${id}/`, payload)) as unknown as DetailResp<SiteContentItem>
  return res.data
}

export async function deleteSiteContent(id: number): Promise<void> {
  await adminApi.delete(`/site-content/${id}/`)
}
