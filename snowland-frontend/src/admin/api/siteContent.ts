import adminApi from './axios'

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
