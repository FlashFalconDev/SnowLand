import adminApi from './axios'

export type LineChannel = {
  enabled: boolean
  verified: boolean
  runtime_ready: boolean
  legacy: boolean
  display_name: string
  webhook_path: string
}

export type MetaPage = { id: string; name: string; instagram_name: string }
export type MetaBinding = {
  platform_ready: boolean
  page_id: string
  page_name: string
  instagram_name: string
  available_pages?: MetaPage[]
}

export type InstagramConnection = {
  expected_username: string
  username: string
  enabled: boolean
  connected: boolean
  missing_configuration: string[]
  token_expires_at: string | null
  last_synced_at: string | null
  last_error: string
}

export const lineChannelPath = '/instagram-sync/line-channel/'
export const metaChannelPath = '/instagram-sync/meta-channel/'
export const instagramPostsPath = '/instagram-sync/'

function statusQuery<T>(tenant: string, channel: string, path: string) {
  return {
    queryKey: ['admin', tenant, channel],
    queryFn: async () => (await adminApi.get(path) as unknown as { data: T }).data,
  }
}

export const lineStatusQuery = (tenant: string) => statusQuery<LineChannel>(tenant, 'line-channel', lineChannelPath)
export const metaStatusQuery = (tenant: string) => statusQuery<MetaBinding>(tenant, 'meta-channel', metaChannelPath)
export const instagramStatusQuery = (tenant: string) => statusQuery<InstagramConnection>(tenant, 'instagram-sync', instagramPostsPath)
