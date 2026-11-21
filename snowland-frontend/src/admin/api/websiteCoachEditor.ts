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
export interface PhotoUploadConfig { enabled: boolean; max_bytes: number }
export async function fetchPhotoUploadConfig(): Promise<PhotoUploadConfig> {
  const result = await adminApi.get('/website-coach-editor/photo-upload-config/') as unknown as {data: PhotoUploadConfig}
  return result.data
}
export async function uploadWebsiteCoachPhoto(id: number, file: File, onProgress: (percent: number) => void): Promise<string> {
  const form = new FormData(); form.append('photo', file)
  const result = await adminApi.post(`/website-coach-editor/${id}/upload-photo/`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: event => onProgress(event.total ? Math.min(99, Math.round(event.loaded * 100 / event.total)) : 0),
  }) as unknown as {data: {url: string}}
  return result.data.url
}
export async function updateWebsiteCoach(id: number, data: WebsiteCoachWrite): Promise<WebsiteCoach> {
  const result = await adminApi.patch(`/website-coach-editor/${id}/`, data) as unknown as {data: WebsiteCoach}
  return result.data
}
