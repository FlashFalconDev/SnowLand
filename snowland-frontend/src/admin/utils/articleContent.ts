import type { SiteContentItem, SiteContentWriteData } from '../api/siteContent'

// One physical article, exposed under the page name customers actually select.
export const toEditorSiteContent = (item: SiteContentItem): SiteContentItem =>
  item.location_key === 'guides.article-pages' && item.external_id === 'packing-checklist'
    ? { ...item, location_key: 'guides.packing' } : item

export const toStoredSiteContent = (data: SiteContentWriteData): SiteContentWriteData =>
  data.location_key === 'guides.packing'
    ? { ...data, content_type: 'article', location_key: 'guides.article-pages', external_id: 'packing-checklist' } : data
