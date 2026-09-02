import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  Edit,
  ExternalLink,
  Image as ImageIcon,
  Loader2,
  Plus,
  Search,
  Star,
  Trash2,
  X,
} from 'lucide-react'
import { useNotification } from '../../context'
import {
  createSiteContent,
  deleteSiteContent,
  fetchSiteContents,
  updateSiteContent,
  type SiteContentItem,
  type SiteContentStatus,
  type SiteContentType,
  type SiteContentWriteData,
} from '../../api/siteContent'

const PRIMARY = '#8b5cf6'
const QUERY_KEY = ['admin', 'site-content']
const CMS_STRUCTURE_LOCATION_KEY = 'cms.structure'
const inputClass = 'w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-[#8b5cf6] focus:ring-2 focus:ring-[#8b5cf6]/15 dark:border-gray-700 dark:bg-gray-900 dark:text-white'

type ContentGroup = string

type LocationInfo = {
  key: string
  label: string
  hint: string
  type: SiteContentType
}

type GroupInfo = {
  id: ContentGroup
  label: string
  description: string
  locations: LocationInfo[]
}

const CONTENT_TYPES: { value: SiteContentType; label: string }[] = [
  { value: 'setting', label: '區塊設定' },
  { value: 'offer', label: '限定優惠' },
  { value: 'article', label: '文章/攻略' },
  { value: 'faq', label: '常見問題' },
  { value: 'review', label: '學生評價' },
  { value: 'media', label: '攝影作品' },
  { value: 'social', label: '社群動態' },
  { value: 'page', label: '頁面內容' },
]

const STATUS_OPTIONS: { value: SiteContentStatus; label: string; helper: string }[] = [
  { value: 'draft', label: '草稿', helper: '後台保存，前台不顯示' },
  { value: 'active', label: '進行中', helper: '前台會顯示' },
  { value: 'ended', label: '已結束', helper: '可顯示歷史活動' },
  { value: 'hidden', label: '隱藏', helper: '暫時關閉' },
]

const DEFAULT_GROUPS: GroupInfo[] = [
  {
    id: 'homepage',
    label: '首頁',
    description: '首頁會看到的主視覺、評價、教練區塊與優惠卡',
    locations: [
      { key: 'homepage.hero', label: '首頁主視覺', hint: '首頁第一屏標題、圖片與主要文案', type: 'setting' },
      { key: 'homepage.reviews', label: '學生評價', hint: '首頁下方的評論卡片', type: 'review' },
      { key: 'homepage.coaches', label: '教練團隊區塊', hint: '首頁教練區塊文字或設定', type: 'setting' },
      { key: 'homepage.offers', label: '首頁限定優惠', hint: '首頁的優惠圖片卡', type: 'offer' },
    ],
  },
  {
    id: 'courses',
    label: '滑雪課程',
    description: '官網導覽列的滑雪課程與相關資訊',
    locations: [
      { key: 'course.tomamu', label: '星野滑雪課程', hint: '星野 Tomamu 課程頁內容、價目表與說明', type: 'page' },
      { key: 'course.off-piste-guide', label: '野雪嚮導', hint: '野雪嚮導課程頁內容', type: 'page' },
      { key: 'course.hokkaido', label: '北海道其他雪場課程', hint: '其他雪場課程頁內容', type: 'page' },
      { key: 'course.how-to-book', label: '預約流程', hint: '滑雪課程預約流程說明', type: 'page' },
      { key: 'course.info', label: '價目表與說明資訊', hint: '每年會微調的課程價目表與補充說明', type: 'page' },
      { key: 'course.open-dates', label: '雪場開放日期', hint: '每年雪場開放期間', type: 'page' },
      { key: 'course.lift-ticket', label: '雪票價格', hint: '每年雪票價格', type: 'page' },
    ],
  },
  {
    id: 'photography',
    label: '海外攝影',
    description: '冬季雪地、夏季旅拍、作品集與預約攝影流程',
    locations: [
      { key: 'photography.winter', label: '冬季雪地攝影', hint: '冬季雪地攝影頁內容', type: 'page' },
      { key: 'photography.summer', label: '夏季旅拍攝影', hint: '夏季旅拍攝影頁內容', type: 'page' },
      { key: 'photography.gallery', label: '攝影作品', hint: '攝影作品集圖片與連結', type: 'media' },
      { key: 'photography.how-to-book', label: '預約攝影流程', hint: '攝影預約流程說明', type: 'page' },
    ],
  },
  {
    id: 'guides',
    label: '滑雪攻略',
    description: '行前須知、裝備、常見問題與攻略文章',
    locations: [
      { key: 'guides.skiresorts', label: '雪場攻略', hint: '雪場介紹、區域攻略與相關文章入口', type: 'page' },
      { key: 'guides.preparation', label: '行前須知', hint: '出發前提醒與注意事項', type: 'page' },
      { key: 'guides.packing', label: '滑雪裝備', hint: '裝備清單與租借提醒', type: 'page' },
      { key: 'guides.faq', label: '常見問題', hint: 'FAQ 問答內容', type: 'faq' },
      { key: 'guides.articles', label: '精選文章', hint: '攻略文章列表', type: 'article' },
    ],
  },
  {
    id: 'news',
    label: '最新消息',
    description: '最新消息、社群貼文與優惠活動',
    locations: [
      { key: 'news.offers', label: '限定優惠總頁', hint: '限定優惠入口頁與活動列表說明', type: 'page' },
      { key: 'news.articles', label: '最新消息', hint: '最新消息文章列表', type: 'article' },
      { key: 'offers.earlybird', label: '早早鳥 / 早鳥優惠', hint: '每年調整活動時間與文案', type: 'offer' },
      { key: 'offers.referral', label: '舊生推薦優惠', hint: '推薦碼、折扣條件與說明', type: 'offer' },
      { key: 'offers.promo', label: '限時活動', hint: '短期促銷活動', type: 'offer' },
      { key: 'news.social', label: 'IG / FB 動態', hint: '社群貼文卡片', type: 'social' },
      { key: 'news.instagram', label: 'Instagram', hint: 'Instagram 手動同步貼文', type: 'social' },
      { key: 'news.facebook', label: 'Facebook', hint: 'Facebook 手動同步貼文', type: 'social' },
    ],
  },
  {
    id: 'about',
    label: '關於 Snowland',
    description: '滑雪學校介紹、教練團隊、招募與聯絡頁',
    locations: [
      { key: 'about.snowland', label: '滑雪學校介紹', hint: '品牌介紹頁面', type: 'page' },
      { key: 'about.coaches', label: '教練團隊', hint: '教練團隊頁面文字與說明；教練卡片由教練管理同步', type: 'setting' },
      { key: 'about.join-us', label: '成為教練', hint: '教練招募資訊', type: 'page' },
      { key: 'about.contact', label: '聯絡我們', hint: '聯絡頁文字、信箱與提示', type: 'page' },
    ],
  },
]

const buildLocationMap = (groups: GroupInfo[]) => groups.flatMap((group) => group.locations).reduce<Record<string, LocationInfo>>((map, location) => {
  map[location.key] = location
  return map
}, {})

const DEFAULT_LOCATION_MAP = buildLocationMap(DEFAULT_GROUPS)

const getDefaultLocationByGroup = (groups: GroupInfo[]) => groups.reduce<Record<string, string>>((map, group) => {
  map[group.id] = group.locations[0]?.key || ''
  return map
}, {})

const createSlug = (value: string, fallback: string) => {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return slug || fallback
}

const normalizeCmsStructureGroups = (metadata?: Record<string, unknown>): GroupInfo[] => {
  const rawGroups = Array.isArray(metadata?.groups) ? metadata.groups : []
  const groups = rawGroups
    .map((group, groupIndex): GroupInfo | null => {
      if (!isRecord(group)) return null
      const label = typeof group.label === 'string' && group.label.trim() ? group.label.trim() : `頁面 ${groupIndex + 1}`
      const id = typeof group.id === 'string' && group.id.trim() ? createSlug(group.id, `page-${groupIndex + 1}`) : createSlug(label, `page-${groupIndex + 1}`)
      const rawLocations = Array.isArray(group.locations) ? group.locations : []
      const locations = rawLocations
        .map((location, locationIndex): LocationInfo | null => {
          if (!isRecord(location)) return null
          const locationLabel = typeof location.label === 'string' && location.label.trim() ? location.label.trim() : `區塊 ${locationIndex + 1}`
          const key = typeof location.key === 'string' && location.key.trim()
            ? location.key.trim()
            : `${id}.${createSlug(locationLabel, `section-${locationIndex + 1}`)}`
          const type = CONTENT_TYPES.some((contentType) => contentType.value === location.type) ? location.type as SiteContentType : 'page'
          return {
            key,
            label: locationLabel,
            hint: typeof location.hint === 'string' ? location.hint : '',
            type,
          }
        })
        .filter((location): location is LocationInfo => Boolean(location))
      return {
        id,
        label,
        description: typeof group.description === 'string' ? group.description : '',
        locations: locations.length ? locations : [{
          key: `${id}.main`,
          label: '主要內容',
          hint: '',
          type: 'page',
        }],
      }
    })
    .filter((group): group is GroupInfo => Boolean(group))

  if (!groups.length) return DEFAULT_GROUPS

  const groupIds = new Set(groups.map((group) => group.id))
  const looksLikeLegacyDefaultStructure = (
    groupIds.has('offers')
    && groupIds.has('media')
    && groupIds.has('pages')
    && !groupIds.has('courses')
    && !groupIds.has('photography')
    && !groupIds.has('about')
  )

  return looksLikeLegacyDefaultStructure ? DEFAULT_GROUPS : groups
}

const makeEmptyForm = (locationKey?: string, location?: LocationInfo): SiteContentWriteData => {
  const key = locationKey || location?.key || 'custom.main'
  return {
    content_type: location?.type || DEFAULT_LOCATION_MAP[key]?.type || 'page',
    location_key: key,
    title: '',
    subtitle: '',
    summary: '',
    body: '',
    image_url: '',
    link_url: '',
    source: '',
    external_id: '',
    tags: [],
    metadata: {},
    status: 'draft',
    start_at: null,
    end_at: null,
    display_order: 0,
    is_pinned: false,
  }
}

const formatDateTime = (value?: string | null) => {
  if (!value) return ''
  return value.replace('T', ' ').slice(0, 16)
}

const toDateTimeInput = (value?: string | null) => {
  if (!value) return ''
  return value.slice(0, 16)
}

const fromDateTimeInput = (value: string) => value ? value : null
const getTypeLabel = (value: string) => CONTENT_TYPES.find((item) => item.value === value)?.label || value
const getStatusLabel = (value: string) => STATUS_OPTIONS.find((item) => item.value === value)?.label || value
const getLocationLabel = (key: string) => DEFAULT_LOCATION_MAP[key]?.label || key
const getLocationHint = (key: string) => DEFAULT_LOCATION_MAP[key]?.hint || ''

type CmsContentBlock =
  | { id: string; type: 'heading'; text: string; level: 2 | 3 }
  | { id: string; type: 'paragraph'; text: string }
  | { id: string; type: 'image'; src: string; alt: string }
  | { id: string; type: 'list'; items: string[]; ordered: boolean }

const isRecord = (value: unknown): value is Record<string, unknown> => Boolean(value && typeof value === 'object' && !Array.isArray(value))

const createBlockId = () => `block-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const normalizeContentBlocks = (metadata: Record<string, unknown> | undefined, body = '', imageUrl = ''): CmsContentBlock[] => {
  const rawBlocks = Array.isArray(metadata?.blocks) ? metadata.blocks : []
  const blocks = rawBlocks
    .map((block): CmsContentBlock | null => {
      if (!isRecord(block)) return null
      const id = typeof block.id === 'string' && block.id ? block.id : createBlockId()
      if (block.type === 'heading') {
        return {
          id,
          type: 'heading',
          text: typeof block.text === 'string' ? block.text : '',
          level: block.level === 3 ? 3 : 2,
        }
      }
      if (block.type === 'paragraph') {
        return { id, type: 'paragraph', text: typeof block.text === 'string' ? block.text : '' }
      }
      if (block.type === 'image') {
        return {
          id,
          type: 'image',
          src: typeof block.src === 'string' ? block.src : '',
          alt: typeof block.alt === 'string' ? block.alt : '',
        }
      }
      if (block.type === 'list') {
        return {
          id,
          type: 'list',
          items: Array.isArray(block.items) ? block.items.map((item) => String(item)) : [],
          ordered: Boolean(block.ordered),
        }
      }
      return null
    })
    .filter((block): block is CmsContentBlock => Boolean(block))

  if (blocks.length) return blocks

  const fallbackBlocks: CmsContentBlock[] = []
  if (imageUrl) {
    fallbackBlocks.push({ id: createBlockId(), type: 'image', src: imageUrl, alt: '' })
  }
  body
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean)
    .forEach((text) => {
      fallbackBlocks.push({ id: createBlockId(), type: 'paragraph', text })
    })
  return fallbackBlocks
}

const blocksToPlainText = (blocks: CmsContentBlock[]) => {
  return blocks
    .map((block) => {
      if (block.type === 'heading' || block.type === 'paragraph') return block.text
      if (block.type === 'list') return block.items.join('\n')
      if (block.type === 'image') return block.alt
      return ''
    })
    .filter(Boolean)
    .join('\n\n')
}

const getFirstBlockImage = (blocks: CmsContentBlock[]) => {
  for (const block of blocks) {
    if (block.type === 'image' && block.src) return block.src
  }
  return ''
}

const getContentPreviewText = (item: SiteContentItem) => {
  const blocks = normalizeContentBlocks(item.metadata, item.body, item.image_url)
  return item.summary || item.subtitle || blocksToPlainText(blocks) || item.body || '尚未填寫內容'
}

type SitePreviewRoute = {
  path: string
  hash?: string
}

const SITE_PREVIEW_ROUTES: Record<string, SitePreviewRoute> = {
  'homepage.hero': { path: '/' },
  'homepage.reviews': { path: '/', hash: 'homepage-reviews' },
  'homepage.coaches': { path: '/', hash: 'homepage-coaches' },
  'homepage.offers': { path: '/', hash: 'homepage-offers' },
  'course.tomamu': { path: '/course/tomamu' },
  'course.off-piste-guide': { path: '/course/off-piste-guide' },
  'course.hokkaido': { path: '/course/hokkaido' },
  'course.how-to-book': { path: '/course/how-to-book' },
  'course.info': { path: '/course/tomamu' },
  'course.lift-ticket': { path: '/course/tomamu' },
  'course.open-dates': { path: '/course/tomamu' },
  'photography.winter': { path: '/photography/winter' },
  'photography.summer': { path: '/photography/summer' },
  'photography.gallery': { path: '/Gallery' },
  'photography.how-to-book': { path: '/photography/how-to-book' },
  'offers.earlybird': { path: '/specialoffers/earlybird' },
  'offers.referral': { path: '/specialoffers/referral' },
  'offers.promo': { path: '/specialoffers/promo' },
  'news.offers': { path: '/specialoffers' },
  'news.social': { path: '/news' },
  'news.instagram': { path: '/news' },
  'news.facebook': { path: '/news' },
  'news.articles': { path: '/news' },
  'guides.skiresorts': { path: '/guides/skiresorts' },
  'guides.preparation': { path: '/guides/preparation' },
  'guides.packing': { path: '/guides/packing-checklist' },
  'guides.faq': { path: '/faq' },
  'guides.articles': { path: '/guides' },
  'about.snowland': { path: '/about' },
  'about.coaches': { path: '/coach' },
  'about.join-us': { path: '/join-us' },
  'about.contact': { path: '/contact' },
}

const getTenantBasePath = () => {
  if (typeof window === 'undefined') return '/snowland'
  const firstPathSegment = window.location.pathname.split('/').filter(Boolean)[0]
  return firstPathSegment ? `/${firstPathSegment}` : '/snowland'
}

const buildOfficialPreviewUrl = (locationKey: string) => {
  const route = SITE_PREVIEW_ROUTES[locationKey] || { path: '/' }
  const basePath = getTenantBasePath()
  const path = route.path.startsWith('/') ? route.path : `/${route.path}`
  const url = `${basePath}${path === '/' ? '/' : path}`
  const query = `cmsPreview=${encodeURIComponent(locationKey)}`
  return `${url}${url.includes('?') ? '&' : '?'}${query}${route.hash ? `#${route.hash}` : ''}`
}

export default function SiteContentPage({ initialGroup = 'homepage' }: { initialGroup?: ContentGroup }) {
  const notify = useNotification()
  const qc = useQueryClient()
  const [activeGroup, setActiveGroup] = useState<ContentGroup>(initialGroup)
  const [editing, setEditing] = useState<SiteContentItem | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [structureOpen, setStructureOpen] = useState(false)
  const [createLocation, setCreateLocation] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [activeLocationKey, setActiveLocationKey] = useState('homepage.reviews')

  const { data: contents = [], isLoading, error } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => fetchSiteContents(),
  })

  const refresh = () => qc.invalidateQueries({ queryKey: QUERY_KEY })
  const structureItem = contents.find((item) => item.content_type === 'setting' && item.location_key === CMS_STRUCTURE_LOCATION_KEY) || null
  const groups = useMemo(() => normalizeCmsStructureGroups(structureItem?.metadata), [structureItem])
  const locationMap = useMemo(() => buildLocationMap(groups), [groups])
  const defaultLocationByGroup = useMemo(() => getDefaultLocationByGroup(groups), [groups])
  const contentItems = useMemo(() => contents.filter((item) => item.location_key !== CMS_STRUCTURE_LOCATION_KEY), [contents])

  useEffect(() => {
    const targetGroup = groups.find((group) => group.id === initialGroup) || groups[0]
    if (!targetGroup) return
    setActiveGroup(targetGroup.id)
    setActiveLocationKey(targetGroup.locations[0]?.key || '')
    setSelectedId(null)
    setSearch('')
  }, [initialGroup, groups])

  useEffect(() => {
    const currentGroup = groups.find((group) => group.id === activeGroup)
    if (!currentGroup) {
      const firstGroup = groups[0]
      if (firstGroup) {
        setActiveGroup(firstGroup.id)
        setActiveLocationKey(firstGroup.locations[0]?.key || '')
      }
      return
    }
    if (!currentGroup.locations.some((location) => location.key === activeLocationKey)) {
      setActiveLocationKey(currentGroup.locations[0]?.key || '')
      setSelectedId(null)
    }
  }, [activeGroup, activeLocationKey, groups])

  const createMutation = useMutation({
    mutationFn: createSiteContent,
    onSuccess: () => {
      notify.success('已新增官網內容')
      refresh()
      setDrawerOpen(false)
      setCreateLocation(null)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || e.response?.data?.detail || '新增失敗'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<SiteContentWriteData> }) => updateSiteContent(id, data),
    onSuccess: () => {
      notify.success('已更新官網內容')
      refresh()
      setDrawerOpen(false)
      setEditing(null)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || e.response?.data?.detail || '更新失敗'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteSiteContent,
    onSuccess: () => {
      notify.success('已刪除官網內容')
      refresh()
      setSelectedId(null)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || e.response?.data?.detail || '刪除失敗'),
  })

  const structureMutation = useMutation({
    mutationFn: (nextGroups: GroupInfo[]) => {
      const payload: SiteContentWriteData = {
        content_type: 'setting',
        location_key: CMS_STRUCTURE_LOCATION_KEY,
        title: '官網內容結構',
        subtitle: '',
        summary: '',
        body: '',
        image_url: '',
        link_url: '',
        source: 'admin',
        external_id: 'cms-structure',
        tags: [],
        metadata: { groups: nextGroups },
        status: 'hidden',
        start_at: null,
        end_at: null,
        display_order: 0,
        is_pinned: false,
      }
      return structureItem ? updateSiteContent(structureItem.id, payload) : createSiteContent(payload)
    },
    onSuccess: () => {
      notify.success('已更新頁面與區塊設定')
      refresh()
      setStructureOpen(false)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || e.response?.data?.detail || '更新頁面結構失敗'),
  })

  const groupInfo = groups.find((group) => group.id === activeGroup) || groups[0]
  const groupLocationKeys = groupInfo.locations.map((location) => location.key)
  const activeLocation = groupInfo.locations.find((location) => location.key === activeLocationKey) || groupInfo.locations[0]
  const groupContents = useMemo(() => {
    return contentItems
      .filter((item) => groupLocationKeys.includes(item.location_key))
      .sort((a, b) => {
        if (a.location_key !== b.location_key) {
          return groupLocationKeys.indexOf(a.location_key) - groupLocationKeys.indexOf(b.location_key)
        }
        return (a.display_order || 0) - (b.display_order || 0)
      })
  }, [contentItems, groupLocationKeys])

  const locationContents = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return groupContents
      .filter((item) => item.location_key === activeLocation.key)
      .filter((item) => {
        if (!keyword) return true
        return [
          item.title,
          item.subtitle,
          item.summary,
          item.body,
          locationMap[item.location_key]?.label || getLocationLabel(item.location_key),
          item.tags?.join(' '),
        ].some((value) => String(value || '').toLowerCase().includes(keyword))
      })
  }, [activeLocation.key, groupContents, locationMap, search])

  const selectedItem = useMemo(() => {
    return locationContents.find((item) => item.id === selectedId) || locationContents[0] || null
  }, [selectedId, locationContents])

  const openCreate = (locationKey?: string) => {
    setEditing(null)
    setCreateLocation(locationKey || null)
    setDrawerOpen(true)
  }

  const openEdit = (item: SiteContentItem) => {
    setEditing(item)
    setSelectedId(item.id)
    setDrawerOpen(true)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
        <AlertCircle size={18} className="mr-2 inline" />
        無法載入官網內容
      </div>
    )
  }

  return (
    <div className="rounded-2xl bg-[#f5f7fb] p-5 text-slate-900 shadow-sm dark:bg-[#0f1724] dark:text-slate-100 dark:shadow-none">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[0.18em] text-[#8b5cf6]">官網內容</p>
          <h1 className="mt-1 text-2xl font-bold text-slate-950 dark:text-white">網站頁面編輯</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-400">
            左邊切換頁面並設定資料，右邊會載入實際官網頁面方便對照。
          </p>
        </div>
        <button
          onClick={() => openCreate(activeLocation?.key)}
          className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-sm"
          style={{ backgroundColor: PRIMARY }}
        >
          <Plus size={16} />新增內容
        </button>
      </div>

      <div className="mt-5 overflow-x-auto">
        <div
          className="grid min-w-[1200px] gap-5"
          style={{ gridTemplateColumns: 'minmax(640px, 1.08fr) minmax(520px, 0.92fr)' }}
        >
        <section className="min-w-0 space-y-4">
          <div className="rounded-2xl bg-white p-4 shadow-sm dark:border dark:border-slate-700/70 dark:bg-[#172131] dark:shadow-none">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-bold text-slate-950 dark:text-white">1. 選擇官網頁面</div>
                <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">先決定要改哪一個前台頁面。</div>
              </div>
              <label className="relative hidden w-72 sm:block">
                <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="搜尋目前區塊內容"
                  className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-[#8b5cf6] focus:ring-2 focus:ring-[#8b5cf6]/15 dark:border-slate-700 dark:bg-[#0f1724] dark:text-slate-100 dark:placeholder:text-slate-500"
                />
              </label>
            </div>

            <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
              {groups.map((group) => {
                const count = contentItems.filter((item) => group.locations.some((location) => location.key === item.location_key)).length
                const active = activeGroup === group.id
                return (
                  <button
                    key={group.id}
                    type="button"
                    onClick={() => {
                      setActiveGroup(group.id)
                      setActiveLocationKey(defaultLocationByGroup[group.id])
                      setSelectedId(null)
                      setSearch('')
                    }}
                    className={`min-w-[132px] rounded-xl border px-3 py-3 text-left transition-colors ${
                      active
                        ? 'border-[#8b5cf6] bg-[#f5f3ff] text-[#4c1d95] dark:bg-[#2b2354] dark:text-white'
                        : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-[#111827] dark:text-slate-300 dark:hover:bg-[#1f2937]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-bold">{group.label}</span>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${active ? 'bg-[#8b5cf6] text-white' : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300'}`}>
                        {count}
                      </span>
                    </div>
                  </button>
                )
              })}
              <button
                type="button"
                onClick={() => setStructureOpen(true)}
                className="min-w-[132px] rounded-xl border border-dashed border-slate-300 px-3 py-3 text-left text-sm font-bold text-slate-600 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-[#1f2937]"
              >
                + 管理頁面
              </button>
            </div>

            <div className="mt-5">
              <div className="text-sm font-bold text-slate-950 dark:text-white">2. 選擇頁面區塊</div>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {groupInfo.locations.map((location) => {
                  const count = groupContents.filter((item) => item.location_key === location.key).length
                  const active = activeLocation.key === location.key
                  return (
                    <button
                      key={location.key}
                      type="button"
                      onClick={() => {
                        setActiveLocationKey(location.key)
                        setSelectedId(null)
                        setSearch('')
                      }}
                      className={`rounded-xl border px-3 py-3 text-left transition-colors ${
                        active
                          ? 'border-[#8b5cf6] bg-[#f5f3ff] text-[#4c1d95] dark:bg-[#2b2354] dark:text-white'
                          : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-[#111827] dark:text-slate-300 dark:hover:bg-[#1f2937]'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-sm font-bold">{location.label}</span>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${active ? 'bg-[#8b5cf6] text-white' : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300'}`}>
                          {count}
                        </span>
                      </div>
                      <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500 dark:text-slate-400">{location.hint}</div>
                    </button>
                  )
                })}
              </div>
            </div>

            <label className="relative mt-4 block sm:hidden">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="搜尋目前區塊內容"
                className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-[#8b5cf6] focus:ring-2 focus:ring-[#8b5cf6]/15 dark:border-slate-700 dark:bg-[#0f1724] dark:text-slate-100 dark:placeholder:text-slate-500"
              />
            </label>
          </div>

          <section className="rounded-2xl bg-white shadow-sm dark:border dark:border-slate-700/70 dark:bg-[#172131] dark:shadow-none">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-700">
              <div>
                <div className="text-sm font-bold text-slate-950 dark:text-white">3. 需要設定的資料</div>
                <h3 className="mt-1 text-lg font-bold text-slate-950 dark:text-white">{activeLocation.label}</h3>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{activeLocation.hint}</p>
              </div>
              <button
                type="button"
                onClick={() => openCreate(activeLocation.key)}
                className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-white shadow-sm"
                style={{ backgroundColor: PRIMARY }}
              >
                <Plus size={15} />新增資料
              </button>
            </div>

            {locationContents.length === 0 ? (
              <div className="px-5 py-14 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500">
                  <ImageIcon size={20} />
                </div>
                <div className="mt-3 text-sm font-bold text-slate-950 dark:text-white">這個區塊還沒有內容</div>
                <button
                  type="button"
                  onClick={() => openCreate(activeLocation.key)}
                  className="mt-4 inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white"
                  style={{ backgroundColor: PRIMARY }}
                >
                  <Plus size={15} />新增第一筆
                </button>
              </div>
            ) : (
              <div className="grid gap-3 p-5">
                {locationContents.map((item) => (
                  <ContentTile
                    key={item.id}
                    item={item}
                    selected={selectedItem?.id === item.id}
                    onSelect={() => setSelectedId(item.id)}
                    onEdit={() => openEdit(item)}
                    onDelete={() => {
                      if (confirm(`確定刪除「${item.title || locationMap[item.location_key]?.label || getLocationLabel(item.location_key)}」？`)) {
                        deleteMutation.mutate(item.id)
                      }
                    }}
                  />
                ))}
              </div>
            )}
          </section>
        </section>

        <PreviewSidePanel
          item={selectedItem}
          groupLabel={groupInfo.label}
          location={activeLocation}
          onEdit={selectedItem ? () => openEdit(selectedItem) : undefined}
        />
        </div>
      </div>

      {drawerOpen && (
        <ContentDrawer
          groups={groups}
          group={activeGroup}
          initialLocation={createLocation}
          item={editing}
          onClose={() => {
            setDrawerOpen(false)
            setEditing(null)
            setCreateLocation(null)
          }}
          onSubmit={(data) => {
            if (editing) updateMutation.mutate({ id: editing.id, data })
            else createMutation.mutate(data)
          }}
          isSaving={createMutation.isPending || updateMutation.isPending}
        />
      )}
      {structureOpen && (
        <StructureDrawer
          groups={groups}
          activeGroupId={activeGroup}
          onClose={() => setStructureOpen(false)}
          onSubmit={(nextGroups) => structureMutation.mutate(nextGroups)}
          isSaving={structureMutation.isPending}
        />
      )}
    </div>
  )
}

function PreviewSidePanel({
  item,
  groupLabel,
  location,
  onEdit,
}: {
  item: SiteContentItem | null
  groupLabel: string
  location: LocationInfo
  onEdit?: () => void
}) {
  const previewUrl = buildOfficialPreviewUrl(location.key)

  return (
    <aside className="sticky top-4 self-start rounded-2xl bg-white p-4 shadow-sm dark:border dark:border-slate-700/70 dark:bg-[#172131] dark:shadow-none">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-bold text-slate-950 dark:text-white">正式官網預覽</div>
          <div className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">
            已儲存內容：{groupLabel} / {location.label}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <a
            href={previewUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            <ExternalLink size={14} />開啟
          </a>
          {onEdit && (
            <button
              type="button"
              onClick={onEdit}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              <Edit size={14} />編輯
            </button>
          )}
        </div>
      </div>

      <div className="mt-4">
        <OfficialSiteFrame location={location} heightClassName="h-[620px]" />
      </div>

      <div className="mt-4 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-600 dark:bg-[#111827] dark:text-slate-300">
        <div className="font-bold text-slate-950 dark:text-white">目前設定位置</div>
        <div className="mt-1 text-slate-600 dark:text-slate-400">{location.hint}</div>
        <div className="mt-1 break-all text-slate-500 dark:text-slate-500">{previewUrl}</div>
        {item && (
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusPill status={item.computed_status || item.status} />
            <span className="rounded-full bg-white px-2 py-1 font-semibold text-slate-600 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700">
              {getTypeLabel(item.content_type)}
            </span>
          </div>
        )}
      </div>
    </aside>
  )
}

function OfficialSiteFrame({ location, heightClassName = 'h-[520px]' }: { location: LocationInfo; heightClassName?: string }) {
  const previewUrl = buildOfficialPreviewUrl(location.key)

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-[#0f1724] dark:shadow-none">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-[#111827]">
        <div className="min-w-0">
          <div className="truncate text-xs font-bold text-slate-900 dark:text-white">正式官網頁面</div>
          <div className="mt-0.5 truncate text-[11px] text-slate-500 dark:text-slate-400">{location.label}</div>
        </div>
        <a
          href={previewUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-[#172131] dark:text-slate-200 dark:hover:bg-slate-800"
        >
          <ExternalLink size={12} />新分頁
        </a>
      </div>
      <iframe
        key={previewUrl}
        title={`${location.label} 官網預覽`}
        src={previewUrl}
        className={`${heightClassName} w-full bg-white`}
      />
      <div className="border-t border-slate-200 bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-500 dark:border-slate-700 dark:bg-[#111827] dark:text-slate-400">
        這裡載入的是目前官網路由；資料儲存後重新載入即可對照前台結果。
      </div>
    </div>
  )
}

function ContentTile({
  item,
  selected,
  onSelect,
  onEdit,
  onDelete,
}: {
  item: SiteContentItem
  selected: boolean
  onSelect: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const text = getContentPreviewText(item)
  const period = `${formatDateTime(item.start_at) || '不限開始'} / ${formatDateTime(item.end_at) || '不限結束'}`

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect()
        }
      }}
      className={`overflow-hidden rounded-2xl border bg-white text-left outline-none transition dark:bg-[#111827] ${
        selected ? 'border-[#8b5cf6] shadow-md shadow-[#8b5cf6]/10 dark:shadow-[#8b5cf6]/15' : 'border-slate-200 hover:border-slate-300 hover:shadow-sm dark:border-slate-700 dark:hover:border-slate-600 dark:hover:shadow-none'
      }`}
    >
      <div className="grid gap-0 sm:grid-cols-[150px_minmax(0,1fr)]">
        <ContentTileMedia item={item} />
        <div className="min-w-0 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-base font-bold text-slate-950 dark:text-white">{item.title || '未命名內容'}</div>
              <div className="mt-1 text-xs font-semibold text-slate-500 dark:text-slate-400">{getTypeLabel(item.content_type)} · 排序 {item.display_order || 0}</div>
            </div>
            <StatusPill status={item.computed_status || item.status} />
          </div>
          <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600 dark:text-slate-300">{text}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">{period}</span>
            {item.is_pinned && <span className="rounded-full bg-[#fef3c7] px-2 py-1 text-xs font-semibold text-amber-800">置頂</span>}
          </div>
          <TagList tags={item.tags} />
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                onEdit()
              }}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              <Edit size={14} />編輯
            </button>
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                onDelete()
              }}
              className="inline-flex items-center gap-1 rounded-lg border border-red-100 px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50"
            >
              <Trash2 size={14} />刪除
            </button>
          </div>
        </div>
      </div>
    </article>
  )
}

function ContentTileMedia({ item }: { item: SiteContentItem }) {
  const imageUrl = item.image_url || getFirstBlockImage(normalizeContentBlocks(item.metadata, item.body, item.image_url))
  if (imageUrl) {
    return <img src={imageUrl} alt="" className="h-full min-h-[150px] w-full object-cover" />
  }

  if (item.content_type === 'review') {
    const initials = item.title.slice(0, 2) || 'SL'
    return (
      <div className="flex h-full min-h-[150px] flex-col items-center justify-center bg-[#eef4fb] px-4 text-center text-[#2f6fa7]">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-white text-sm font-bold shadow-sm">{initials}</div>
        <div className="mt-3 flex gap-0.5 text-[#f0a23a]">
          {Array.from({ length: 5 }).map((_, index) => <Star key={index} size={13} fill="currentColor" />)}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-[150px] items-center justify-center bg-slate-100 text-slate-400">
      <ImageIcon size={28} />
    </div>
  )
}

function TagList({ tags }: { tags: string[] }) {
  if (!tags?.length) return null
  return (
    <div className="mt-3 flex flex-wrap gap-1">
      {tags.slice(0, 3).map((tag) => (
        <span key={tag} className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
          {tag}
        </span>
      ))}
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const cls = status === 'active'
    ? 'bg-emerald-100 text-emerald-700'
    : status === 'ended'
    ? 'bg-slate-200 text-slate-700'
    : status === 'hidden'
    ? 'bg-red-100 text-red-700'
    : 'bg-amber-100 text-amber-800'
  return <span className={`inline-flex shrink-0 rounded-full px-2 py-1 text-xs font-semibold ${cls}`}>{getStatusLabel(status)}</span>
}

function ContentDrawer({
  groups,
  group,
  initialLocation,
  item,
  onClose,
  onSubmit,
  isSaving,
}: {
  groups: GroupInfo[]
  group: ContentGroup
  initialLocation: string | null
  item: SiteContentItem | null
  onClose: () => void
  onSubmit: (data: SiteContentWriteData) => void
  isSaving: boolean
}) {
  const groupInfo = groups.find((candidate) => candidate.id === group) || groups[0]
  const drawerLocationMap = useMemo(() => buildLocationMap(groups), [groups])
  const [form, setForm] = useState<SiteContentWriteData>(() => item ? {
    content_type: item.content_type,
    location_key: item.location_key,
    title: item.title || '',
    subtitle: item.subtitle || '',
    summary: item.summary || '',
    body: item.body || '',
    image_url: item.image_url || '',
    link_url: item.link_url || '',
    source: item.source || '',
    external_id: item.external_id || '',
    tags: item.tags || [],
    metadata: item.metadata || {},
    status: item.status || 'draft',
    start_at: item.start_at,
    end_at: item.end_at,
    display_order: item.display_order || 0,
    is_pinned: !!item.is_pinned,
  } : makeEmptyForm(initialLocation || groupInfo?.locations[0]?.key, initialLocation ? drawerLocationMap[initialLocation] : groupInfo?.locations[0]))
  const formLocation = drawerLocationMap[form.location_key] || groupInfo.locations[0]
  const draftBlocks = normalizeContentBlocks(form.metadata, form.body, form.image_url)
  const setDraftBlocks = (blocks: CmsContentBlock[]) => {
    setForm((prev) => ({
      ...prev,
      body: blocksToPlainText(blocks),
      image_url: prev.image_url || getFirstBlockImage(blocks),
      metadata: {
        ...(prev.metadata || {}),
        blocks,
      },
    }))
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    const normalizedBlocks = normalizeContentBlocks(form.metadata, form.body, form.image_url)
    onSubmit({
      ...form,
      body: blocksToPlainText(normalizedBlocks),
      image_url: form.image_url || getFirstBlockImage(normalizedBlocks),
      start_at: fromDateTimeInput(toDateTimeInput(form.start_at)),
      end_at: fromDateTimeInput(toDateTimeInput(form.end_at)),
      display_order: Number(form.display_order) || 0,
      tags: form.tags.map((tag) => tag.trim()).filter(Boolean),
      metadata: {
        ...(form.metadata || {}),
        blocks: normalizedBlocks,
      },
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50">
      <form onSubmit={handleSubmit} className="flex h-full w-full max-w-[1440px] flex-col bg-white shadow-xl dark:bg-gray-900">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-800">
          <div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">{item ? '編輯網站內容' : '新增網站內容'}</h2>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">左邊填資料，右邊會同步預覽前台效果。</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800">
            <X size={18} />
          </button>
        </div>

        <div className="grid min-h-0 flex-1 gap-0 overflow-hidden lg:grid-cols-12">
          <div className="space-y-5 overflow-y-auto p-6 lg:col-span-7">
            <FormSection title="1. 這段內容放在哪裡">
              <div className="grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">網站位置</span>
                  <select
                    value={form.location_key}
                    onChange={(event) => {
                      const locationKey = event.target.value
                      setForm((prev) => ({
                        ...prev,
                        location_key: locationKey,
                        content_type: drawerLocationMap[locationKey]?.type || prev.content_type,
                      }))
                    }}
                    className={inputClass}
                  >
                    {groupInfo.locations.map((location) => (
                      <option key={location.key} value={location.key}>
                        {location.label}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-xs text-gray-500">{drawerLocationMap[form.location_key]?.hint || getLocationHint(form.location_key)}</p>
                </label>

                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">狀態</span>
                  <select
                    value={form.status}
                    onChange={(event) => setForm((prev) => ({ ...prev, status: event.target.value as SiteContentStatus }))}
                    className={inputClass}
                  >
                    {STATUS_OPTIONS.map((status) => (
                      <option key={status.value} value={status.value}>{status.label} - {status.helper}</option>
                    ))}
                  </select>
                </label>
              </div>
            </FormSection>

            <FormSection title="2. 前台會看到的標題">
              <div className="grid gap-4 md:grid-cols-2">
                <TextInput label="標題" value={form.title} onChange={(value) => setForm((prev) => ({ ...prev, title: value }))} />
                <TextInput label="副標題" value={form.subtitle} onChange={(value) => setForm((prev) => ({ ...prev, subtitle: value }))} />
              </div>

              <label className="mt-4 block">
                <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">短文字</span>
                <textarea
                  value={form.summary}
                  onChange={(event) => setForm((prev) => ({ ...prev, summary: event.target.value }))}
                  className={`${inputClass} min-h-[76px]`}
                  placeholder="卡片上先看到的摘要"
                />
              </label>
            </FormSection>

            <FormSection title="3. 正文區塊（可圖字交錯）">
              <ContentBlocksEditor blocks={draftBlocks} onChange={setDraftBlocks} />
            </FormSection>

            <FormSection title="4. 連結與顯示順序">
              <div className="grid gap-4 md:grid-cols-2">
                <TextInput label="封面圖片（可空白，會抓第一張正文圖片）" value={form.image_url} placeholder="/homepage/example.jpg" onChange={(value) => setForm((prev) => ({ ...prev, image_url: value }))} />
                <TextInput label="點擊後連結" value={form.link_url} placeholder="/specialoffers/earlybird" onChange={(value) => setForm((prev) => ({ ...prev, link_url: value }))} />
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <TextInput
                  type="number"
                  label="排序"
                  value={String(form.display_order)}
                  onChange={(value) => setForm((prev) => ({ ...prev, display_order: Number(value) || 0 }))}
                />
                <label className="flex items-end gap-2 pb-2 text-sm text-gray-700 dark:text-gray-200">
                  <input
                    type="checkbox"
                    checked={form.is_pinned}
                    onChange={(event) => setForm((prev) => ({ ...prev, is_pinned: event.target.checked }))}
                    className="h-4 w-4 rounded border-gray-300 text-[#8b5cf6] focus:ring-[#8b5cf6]"
                  />
                  置頂顯示
                </label>
              </div>
            </FormSection>

            <FormSection title="5. 活動期間">
              <div className="grid gap-4 md:grid-cols-2">
                <TextInput
                  type="datetime-local"
                  label="開始時間"
                  value={toDateTimeInput(form.start_at)}
                  onChange={(value) => setForm((prev) => ({ ...prev, start_at: fromDateTimeInput(value) }))}
                />
                <TextInput
                  type="datetime-local"
                  label="結束時間"
                  value={toDateTimeInput(form.end_at)}
                  onChange={(value) => setForm((prev) => ({ ...prev, end_at: fromDateTimeInput(value) }))}
                />
              </div>
              <p className="mt-2 flex items-center gap-2 text-xs text-gray-500">
                <CalendarDays size={14} />
                不設定期間就會一直依狀態顯示；設定結束時間後，到期會自動變成已結束。
              </p>
            </FormSection>

            <details className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800/60">
              <summary className="cursor-pointer text-sm font-semibold text-gray-700 dark:text-gray-200">進階欄位</summary>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">內容類型</span>
                  <select
                    value={form.content_type}
                    onChange={(event) => setForm((prev) => ({ ...prev, content_type: event.target.value as SiteContentType }))}
                    className={inputClass}
                  >
                    {CONTENT_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>{type.label}</option>
                    ))}
                  </select>
                </label>
                <TextInput label="來源" value={form.source} placeholder="Google / Instagram / Facebook" onChange={(value) => setForm((prev) => ({ ...prev, source: value }))} />
                <TextInput label="外部 ID" value={form.external_id} placeholder="貼文 ID / 評論 ID，可空白" onChange={(value) => setForm((prev) => ({ ...prev, external_id: value }))} />
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">標籤</span>
                  <input
                    value={form.tags.join(', ')}
                    onChange={(event) => setForm((prev) => ({
                      ...prev,
                      tags: event.target.value.split(',').map((tag) => tag.trim()).filter(Boolean),
                    }))}
                    className={inputClass}
                    placeholder="例如：限時活動, 早鳥優惠"
                  />
                </label>
              </div>
            </details>
          </div>

          <div className="border-l border-gray-200 bg-gray-50 p-5 dark:border-gray-800 dark:bg-gray-950 lg:col-span-5">
            <div className="mb-3">
              <div className="text-sm font-semibold text-gray-900 dark:text-white">草稿預覽</div>
              <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                這裡照左邊目前資料即時產生；正式官網需儲存後才會更新。
              </p>
            </div>
            <DraftContentPreview form={form} location={formLocation} blocks={draftBlocks} />
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-800">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          >
            取消
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{ backgroundColor: PRIMARY }}
          >
            {isSaving && <Loader2 size={14} className="animate-spin" />}
            儲存變更
          </button>
        </div>
      </form>
    </div>
  )
}

function StructureDrawer({
  groups,
  activeGroupId,
  onClose,
  onSubmit,
  isSaving,
}: {
  groups: GroupInfo[]
  activeGroupId?: ContentGroup
  onClose: () => void
  onSubmit: (groups: GroupInfo[]) => void
  isSaving: boolean
}) {
  const [draftGroups, setDraftGroups] = useState<GroupInfo[]>(() => JSON.parse(JSON.stringify(groups)))
  const [selection, setSelection] = useState<
    { kind: 'group'; groupId: string } | { kind: 'location'; groupId: string; locationKey: string }
  >(() => ({ kind: 'group', groupId: activeGroupId || groups[0]?.id || '' }))
  const [openGroupIds, setOpenGroupIds] = useState<Set<string>>(() => {
    const defaultGroupId = activeGroupId || groups[0]?.id
    return new Set(defaultGroupId ? [defaultGroupId] : [])
  })

  const selectedGroupIndex = Math.max(0, draftGroups.findIndex((group) => group.id === selection.groupId))
  const selectedGroup = draftGroups[selectedGroupIndex] || draftGroups[0]
  const selectedLocationIndex = selection.kind === 'location' && selectedGroup
    ? selectedGroup.locations.findIndex((location) => location.key === selection.locationKey)
    : -1
  const selectedLocation = selectedLocationIndex >= 0 ? selectedGroup.locations[selectedLocationIndex] : null

  const selectGroup = (group: GroupInfo) => {
    setSelection({ kind: 'group', groupId: group.id })
  }

  const selectLocation = (group: GroupInfo, location: LocationInfo) => {
    setOpenGroupIds((current) => new Set([...current, group.id]))
    setSelection({ kind: 'location', groupId: group.id, locationKey: location.key })
  }

  const toggleGroup = (groupId: string) => {
    setOpenGroupIds((current) => {
      const next = new Set(current)
      if (next.has(groupId)) next.delete(groupId)
      else next.add(groupId)
      return next
    })
  }

  const expandAll = () => {
    setOpenGroupIds(new Set(draftGroups.map((group) => group.id)))
  }

  const collapseAll = () => {
    setOpenGroupIds(new Set())
  }

  const updateGroup = (groupIndex: number, patch: Partial<GroupInfo>) => {
    const oldId = draftGroups[groupIndex]?.id
    if (patch.id && oldId && patch.id !== oldId) {
      setOpenGroupIds((current) => {
        const next = new Set(current)
        if (next.delete(oldId)) next.add(patch.id as string)
        return next
      })
      setSelection((current) => current.groupId === oldId ? { ...current, groupId: patch.id as string } : current)
    }
    setDraftGroups((current) => current.map((group, index) => index === groupIndex ? { ...group, ...patch } : group))
  }

  const moveGroup = (groupIndex: number, offset: number) => {
    const nextIndex = groupIndex + offset
    if (nextIndex < 0 || nextIndex >= draftGroups.length) return
    setDraftGroups((current) => {
      const next = [...current]
      const [item] = next.splice(groupIndex, 1)
      next.splice(nextIndex, 0, item)
      return next
    })
  }

  const addGroup = () => {
    const label = `新頁面 ${draftGroups.length + 1}`
    const id = `custom-${Date.now()}`
    setOpenGroupIds((current) => new Set([...current, id]))
    setSelection({ kind: 'group', groupId: id })
    setDraftGroups((current) => ([
      ...current,
      {
        id,
        label,
        description: '',
        locations: [{
          key: `${id}.main`,
          label: '主要內容',
          hint: '',
          type: 'page',
        }],
      },
    ]))
  }

  const removeGroup = (groupIndex: number) => {
    const group = draftGroups[groupIndex]
    if (!group) return
    if (!confirm(`確定刪除頁面「${group.label}」？底下區塊設定會一起移除，但已建立的內容資料不會刪除。`)) return
    setOpenGroupIds((current) => {
      const next = new Set(current)
      next.delete(group.id)
      return next
    })
    setSelection((current) => current.groupId === group.id
      ? { kind: 'group', groupId: draftGroups[groupIndex === 0 ? 1 : 0]?.id || '' }
      : current)
    setDraftGroups((current) => current.filter((_, index) => index !== groupIndex))
  }

  const updateLocation = (groupIndex: number, locationIndex: number, patch: Partial<LocationInfo>) => {
    const oldKey = draftGroups[groupIndex]?.locations[locationIndex]?.key
    if (patch.key && oldKey && patch.key !== oldKey) {
      setSelection((current) => current.kind === 'location' && current.locationKey === oldKey
        ? { ...current, locationKey: patch.key as string }
        : current)
    }
    setDraftGroups((current) => current.map((group, index) => {
      if (index !== groupIndex) return group
      return {
        ...group,
        locations: group.locations.map((location, innerIndex) => innerIndex === locationIndex ? { ...location, ...patch } : location),
      }
    }))
  }

  const moveLocation = (groupIndex: number, locationIndex: number, offset: number) => {
    setDraftGroups((current) => current.map((group, index) => {
      if (index !== groupIndex) return group
      const nextIndex = locationIndex + offset
      if (nextIndex < 0 || nextIndex >= group.locations.length) return group
      const nextLocations = [...group.locations]
      const [item] = nextLocations.splice(locationIndex, 1)
      nextLocations.splice(nextIndex, 0, item)
      return { ...group, locations: nextLocations }
    }))
  }

  const addLocation = (groupIndex: number) => {
    const group = draftGroups[groupIndex]
    if (!group) return
    const locationLabel = `新區塊 ${group.locations.length + 1}`
    const locationKey = `${group.id}.${createSlug(locationLabel, `section-${group.locations.length + 1}`)}`
    setOpenGroupIds((current) => new Set([...current, group.id]))
    setSelection({ kind: 'location', groupId: group.id, locationKey })
    setDraftGroups((current) => current.map((group, index) => {
      if (index !== groupIndex) return group
      return {
        ...group,
        locations: [
          ...group.locations,
          {
            key: locationKey,
            label: locationLabel,
            hint: '',
            type: 'page',
          },
        ],
      }
    }))
  }

  const removeLocation = (groupIndex: number, locationIndex: number) => {
    const location = draftGroups[groupIndex]?.locations[locationIndex]
    if (!location) return
    if (!confirm(`確定移除區塊「${location.label}」？已建立的內容資料不會刪除，只是不再出現在這個選單。`)) return
    setSelection((current) => current.kind === 'location' && current.locationKey === location.key
      ? { kind: 'group', groupId: draftGroups[groupIndex]?.id || '' }
      : current)
    setDraftGroups((current) => current.map((group, index) => {
      if (index !== groupIndex) return group
      const nextLocations = group.locations.filter((_, innerIndex) => innerIndex !== locationIndex)
      return {
        ...group,
        locations: nextLocations.length ? nextLocations : [{
          key: `${group.id}.main`,
          label: '主要內容',
          hint: '',
          type: 'page',
        }],
      }
    }))
  }

  const resetDefaults = () => {
    if (!confirm('確定恢復預設頁面與區塊？目前自訂選單會被取代，但內容資料不會刪除。')) return
    const defaults = JSON.parse(JSON.stringify(DEFAULT_GROUPS)) as GroupInfo[]
    setDraftGroups(defaults)
    setOpenGroupIds(new Set(defaults[0]?.id ? [defaults[0].id] : []))
    setSelection({ kind: 'group', groupId: defaults[0]?.id || '' })
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    const normalizedGroups = normalizeCmsStructureGroups({ groups: draftGroups })
    const groupIds = normalizedGroups.map((group) => group.id)
    const locationKeys = normalizedGroups.flatMap((group) => group.locations.map((location) => location.key))
    if (new Set(groupIds).size !== groupIds.length) {
      alert('頁面識別碼不能重複，請調整後再儲存。')
      return
    }
    if (new Set(locationKeys).size !== locationKeys.length) {
      alert('區塊識別碼不能重複，請調整後再儲存。')
      return
    }
    onSubmit(normalizedGroups)
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50">
      <form onSubmit={handleSubmit} className="flex h-full w-full max-w-5xl flex-col bg-white shadow-xl dark:bg-gray-900">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-800">
          <div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">管理頁面與區塊</h2>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">這裡控制左側「選擇官網頁面 / 頁面區塊」的顯示、順序與分類。</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800">
            <X size={18} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={addGroup} className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-white" style={{ backgroundColor: PRIMARY }}>
                <Plus size={15} />新增頁面
              </button>
              <button type="button" onClick={resetDefaults} className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800">
                恢復預設
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={expandAll} className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800">
                全部展開
              </button>
              <button type="button" onClick={collapseAll} className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800">
                全部收起
              </button>
            </div>
          </div>

          <div className="mt-4 grid min-h-[520px] gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
            <section className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
                <div className="text-sm font-bold text-gray-900 dark:text-white">頁面架構</div>
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">左邊只調整順序與選取項目，右邊編輯細節。</div>
              </div>
              <div className="max-h-[640px] space-y-2 overflow-y-auto p-3">
                {draftGroups.map((group, groupIndex) => {
                  const groupOpen = openGroupIds.has(group.id)
                  const groupSelected = selection.kind === 'group' && selection.groupId === group.id
                  return (
                    <div key={`${group.id}-${groupIndex}`} className="rounded-lg border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-800/70">
                      <div className="flex items-center gap-1 p-2">
                        <button
                          type="button"
                          onClick={() => toggleGroup(group.id)}
                          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-gray-500 hover:bg-white dark:text-gray-300 dark:hover:bg-gray-900"
                          aria-label={groupOpen ? '收起頁面' : '展開頁面'}
                        >
                          {groupOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </button>
                        <button
                          type="button"
                          onClick={() => selectGroup(group)}
                          className={`min-w-0 flex-1 rounded-md px-2 py-2 text-left ${groupSelected ? 'bg-[#8b5cf6]/15 text-[#8b5cf6]' : 'text-gray-800 hover:bg-white dark:text-gray-100 dark:hover:bg-gray-900'}`}
                        >
                          <span className="block truncate text-sm font-bold">{groupIndex + 1}. {group.label}</span>
                          <span className="mt-0.5 block truncate text-xs opacity-75">{group.locations.length} 個區塊</span>
                        </button>
                      </div>
                      <div className="flex gap-1 px-3 pb-2">
                        <button type="button" onClick={() => moveGroup(groupIndex, -1)} disabled={groupIndex === 0} className="rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-600 disabled:opacity-40 dark:border-gray-700 dark:text-gray-300">上移</button>
                        <button type="button" onClick={() => moveGroup(groupIndex, 1)} disabled={groupIndex === draftGroups.length - 1} className="rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-600 disabled:opacity-40 dark:border-gray-700 dark:text-gray-300">下移</button>
                        <button type="button" onClick={() => addLocation(groupIndex)} className="rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-600 dark:border-gray-700 dark:text-gray-300">新增區塊</button>
                        <button type="button" onClick={() => removeGroup(groupIndex)} className="ml-auto rounded-md border border-red-200 px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-50 dark:border-red-900/70 dark:hover:bg-red-950/40">刪除</button>
                      </div>
                      {groupOpen && (
                        <div className="space-y-1 border-t border-gray-200 p-2 dark:border-gray-800">
                          {group.locations.map((location, locationIndex) => {
                            const locationSelected = selection.kind === 'location' && selection.locationKey === location.key
                            return (
                              <div key={`${location.key}-${locationIndex}`} className="flex items-center gap-1">
                                <button
                                  type="button"
                                  onClick={() => selectLocation(group, location)}
                                  className={`min-w-0 flex-1 rounded-md px-3 py-2 text-left ${locationSelected ? 'bg-[#8b5cf6]/15 text-[#8b5cf6]' : 'text-gray-700 hover:bg-white dark:text-gray-200 dark:hover:bg-gray-900'}`}
                                >
                                  <span className="block truncate text-xs font-bold">{locationIndex + 1}. {location.label}</span>
                                  <span className="mt-0.5 block truncate text-[11px] opacity-70">{getTypeLabel(location.type)}</span>
                                </button>
                                <button type="button" onClick={() => moveLocation(groupIndex, locationIndex, -1)} disabled={locationIndex === 0} className="rounded-md px-2 py-1 text-xs text-gray-500 hover:bg-white disabled:opacity-30 dark:text-gray-300 dark:hover:bg-gray-900">↑</button>
                                <button type="button" onClick={() => moveLocation(groupIndex, locationIndex, 1)} disabled={locationIndex === group.locations.length - 1} className="rounded-md px-2 py-1 text-xs text-gray-500 hover:bg-white disabled:opacity-30 dark:text-gray-300 dark:hover:bg-gray-900">↓</button>
                                <button type="button" onClick={() => removeLocation(groupIndex, locationIndex)} className="rounded-md px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40">刪</button>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </section>

            <section className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
              <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
                <div className="text-xs font-semibold uppercase tracking-[0.22em] text-gray-400">
                  {selection.kind === 'location' ? 'SECTION' : 'PAGE'}
                </div>
                <h3 className="mt-1 text-lg font-bold text-gray-900 dark:text-white">
                  {selection.kind === 'location' && selectedLocation ? selectedLocation.label : selectedGroup?.label || '尚未選擇'}
                </h3>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  {selection.kind === 'location'
                    ? '這裡設定這個區塊在 CMS 裡的名稱、類型與提示。'
                    : '這裡設定官網導覽大分類，底下區塊會顯示在左側選單。'}
                </p>
              </div>

              <div className="space-y-5 p-5">
                {selectedGroup && selection.kind === 'group' && (
                  <>
                    <div className="grid gap-4 md:grid-cols-2">
                      <TextInput label="頁面名稱" value={selectedGroup.label} onChange={(value) => updateGroup(selectedGroupIndex, { label: value })} />
                      <TextInput label="識別碼" value={selectedGroup.id} onChange={(value) => updateGroup(selectedGroupIndex, { id: createSlug(value, selectedGroup.id) })} />
                    </div>
                    <TextInput label="說明" value={selectedGroup.description} onChange={(value) => updateGroup(selectedGroupIndex, { description: value })} />
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-xs leading-relaxed text-gray-600 dark:border-gray-800 dark:bg-gray-800/60 dark:text-gray-300">
                      這個頁面底下目前有 <span className="font-bold text-gray-900 dark:text-white">{selectedGroup.locations.length}</span> 個區塊。要修改區塊細節，請從左邊點選區塊名稱。
                    </div>
                  </>
                )}

                {selectedGroup && selectedLocation && selection.kind === 'location' && (
                  <>
                    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_180px]">
                      <TextInput label="區塊名稱" value={selectedLocation.label} onChange={(value) => updateLocation(selectedGroupIndex, selectedLocationIndex, { label: value })} />
                      <label className="block">
                        <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">類型</span>
                        <select value={selectedLocation.type} onChange={(event) => updateLocation(selectedGroupIndex, selectedLocationIndex, { type: event.target.value as SiteContentType })} className={inputClass}>
                          {CONTENT_TYPES.map((type) => (
                            <option key={type.value} value={type.value}>{type.label}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <TextInput label="區塊識別碼" value={selectedLocation.key} onChange={(value) => updateLocation(selectedGroupIndex, selectedLocationIndex, { key: value.trim() })} />
                    <TextInput label="提示說明" value={selectedLocation.hint} onChange={(value) => updateLocation(selectedGroupIndex, selectedLocationIndex, { hint: value })} />
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-xs leading-relaxed text-gray-600 dark:border-gray-800 dark:bg-gray-800/60 dark:text-gray-300">
                      區塊識別碼會影響前台讀哪一份資料。一般只改「區塊名稱」和「提示說明」即可，識別碼確定要換再修改。
                    </div>
                  </>
                )}
              </div>
            </section>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-800">
          <button type="button" onClick={onClose} disabled={isSaving} className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200">
            取消
          </button>
          <button type="submit" disabled={isSaving} className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50" style={{ backgroundColor: PRIMARY }}>
            {isSaving && <Loader2 size={14} className="animate-spin" />}
            儲存頁面設定
          </button>
        </div>
      </form>
    </div>
  )
}

function ContentBlocksEditor({
  blocks,
  onChange,
}: {
  blocks: CmsContentBlock[]
  onChange: (blocks: CmsContentBlock[]) => void
}) {
  const addBlock = (type: CmsContentBlock['type']) => {
    const nextBlock: CmsContentBlock =
      type === 'heading'
        ? { id: createBlockId(), type: 'heading', text: '新的小標題', level: 2 }
        : type === 'image'
        ? { id: createBlockId(), type: 'image', src: '', alt: '' }
        : type === 'list'
        ? { id: createBlockId(), type: 'list', items: ['第一點'], ordered: false }
        : { id: createBlockId(), type: 'paragraph', text: '' }
    onChange([...blocks, nextBlock])
  }

  const updateBlock = (id: string, patch: Partial<CmsContentBlock>) => {
    onChange(blocks.map((block) => (block.id === id ? ({ ...block, ...patch } as CmsContentBlock) : block)))
  }

  const removeBlock = (id: string) => {
    onChange(blocks.filter((block) => block.id !== id))
  }

  const moveBlock = (index: number, offset: number) => {
    const nextIndex = index + offset
    if (nextIndex < 0 || nextIndex >= blocks.length) return
    const next = [...blocks]
    const [item] = next.splice(index, 1)
    next.splice(nextIndex, 0, item)
    onChange(next)
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => addBlock('heading')} className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800">
          + 小標題
        </button>
        <button type="button" onClick={() => addBlock('paragraph')} className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800">
          + 文字
        </button>
        <button type="button" onClick={() => addBlock('image')} className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800">
          + 圖片
        </button>
        <button type="button" onClick={() => addBlock('list')} className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800">
          + 條列
        </button>
      </div>

      {blocks.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-800/60 dark:text-gray-400">
          還沒有正文區塊。先加一段文字或圖片，右邊會立即看到草稿排版。
        </div>
      ) : (
        <div className="space-y-3">
          {blocks.map((block, index) => (
            <div key={block.id} className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800/60">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="text-xs font-bold text-gray-700 dark:text-gray-200">
                  {index + 1}. {block.type === 'heading' ? '小標題' : block.type === 'paragraph' ? '文字段落' : block.type === 'image' ? '圖片' : '條列清單'}
                </div>
                <div className="flex gap-1">
                  <button type="button" onClick={() => moveBlock(index, -1)} disabled={index === 0} className="rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-600 disabled:opacity-40 dark:border-gray-700 dark:text-gray-300">
                    上移
                  </button>
                  <button type="button" onClick={() => moveBlock(index, 1)} disabled={index === blocks.length - 1} className="rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-600 disabled:opacity-40 dark:border-gray-700 dark:text-gray-300">
                    下移
                  </button>
                  <button type="button" onClick={() => removeBlock(block.id)} className="rounded-md border border-red-200 px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-50 dark:border-red-900/70 dark:hover:bg-red-950/40">
                    刪除
                  </button>
                </div>
              </div>

              {block.type === 'heading' && (
                <div className="grid gap-3 md:grid-cols-[120px_minmax(0,1fr)]">
                  <label className="block">
                    <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">層級</span>
                    <select value={block.level} onChange={(event) => updateBlock(block.id, { level: Number(event.target.value) as 2 | 3 })} className={inputClass}>
                      <option value={2}>大標</option>
                      <option value={3}>小標</option>
                    </select>
                  </label>
                  <TextInput label="標題文字" value={block.text} onChange={(value) => updateBlock(block.id, { text: value })} />
                </div>
              )}

              {block.type === 'paragraph' && (
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">文字內容</span>
                  <textarea value={block.text} onChange={(event) => updateBlock(block.id, { text: event.target.value })} className={`${inputClass} min-h-[110px]`} placeholder="輸入這一段文字" />
                </label>
              )}

              {block.type === 'image' && (
                <div className="grid gap-3 md:grid-cols-2">
                  <TextInput label="圖片路徑" value={block.src} placeholder="/homepage/example.jpg" onChange={(value) => updateBlock(block.id, { src: value })} />
                  <TextInput label="圖片說明（可空白）" value={block.alt} placeholder="圖片替代文字" onChange={(value) => updateBlock(block.id, { alt: value })} />
                </div>
              )}

              {block.type === 'list' && (
                <div className="space-y-3">
                  <label className="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
                    <input type="checkbox" checked={block.ordered} onChange={(event) => updateBlock(block.id, { ordered: event.target.checked })} className="h-4 w-4 rounded border-gray-300 text-[#8b5cf6] focus:ring-[#8b5cf6]" />
                    使用數字清單
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">每行一點</span>
                    <textarea
                      value={block.items.join('\n')}
                      onChange={(event) => updateBlock(block.id, { items: event.target.value.split('\n') })}
                      className={`${inputClass} min-h-[100px]`}
                      placeholder={'第一點\n第二點\n第三點'}
                    />
                  </label>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function DraftContentPreview({
  form,
  location,
  blocks,
}: {
  form: SiteContentWriteData
  location: LocationInfo
  blocks: CmsContentBlock[]
}) {
  const previewUrl = buildOfficialPreviewUrl(location.key)
  const visibleBlocks = blocks.filter((block) => {
    if (block.type === 'heading' || block.type === 'paragraph') return block.text.trim()
    if (block.type === 'image') return block.src.trim()
    if (block.type === 'list') return block.items.some((item) => item.trim())
    return false
  })

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-[#0f1724]">
      <div className="flex items-center justify-between gap-3 border-b border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
        <div className="min-w-0">
          <div className="truncate text-sm font-bold text-gray-900 dark:text-white">左側草稿排版</div>
          <div className="mt-1 truncate text-xs text-gray-500 dark:text-gray-400">{location.label}</div>
        </div>
        <a href={previewUrl} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-white dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800">
          <ExternalLink size={13} />正式頁
        </a>
      </div>

      <div className="max-h-[680px] overflow-y-auto bg-[#f7f8fa]">
        <div className="border-b border-[#e2e8f0] bg-white px-5 py-4">
          <div className="text-xs font-bold tracking-[0.24em] text-[#2b5f8f]">SNOWLAND</div>
        </div>
        <article className="px-5 py-10">
          <div className="mx-auto max-w-2xl">
            <div className="text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#94a3b8]">{form.subtitle || 'SnowLand'}</p>
              <h1 className="mt-4 text-2xl font-semibold tracking-wide text-[#1f2937]">{form.title || '未命名內容'}</h1>
              {form.summary && <p className="mt-5 text-sm leading-7 text-[#64748b]">{form.summary}</p>}
            </div>

            {visibleBlocks.length === 0 ? (
              <div className="mt-10 rounded-lg border border-dashed border-[#cbd5e1] bg-white p-8 text-center text-sm text-[#64748b]">
                左邊新增正文區塊後，這裡會照順序預覽。
              </div>
            ) : (
              <div className="mt-10 space-y-6">
                {visibleBlocks.map((block, index) => (
                  <DraftBlock key={block.id} block={block} index={index} />
                ))}
              </div>
            )}
          </div>
        </article>
      </div>
    </div>
  )
}

function DraftBlock({ block, index }: { block: CmsContentBlock; index: number }) {
  if (block.type === 'heading') {
    const HeadingTag = block.level === 3 ? 'h3' : 'h2'
    return <HeadingTag className={block.level === 3 ? 'text-lg font-semibold text-[#1f2937]' : 'text-xl font-semibold text-[#111827]'}>{block.text}</HeadingTag>
  }
  if (block.type === 'paragraph') {
    return <p className="whitespace-pre-line text-sm leading-7 text-[#475569]">{block.text}</p>
  }
  if (block.type === 'image') {
    return (
      <figure className="overflow-hidden rounded-sm bg-[#e2e8f0]">
        <img src={block.src} alt={block.alt || `內容圖片 ${index + 1}`} className="h-auto w-full" />
        {block.alt && <figcaption className="bg-white px-3 py-2 text-xs text-[#64748b]">{block.alt}</figcaption>}
      </figure>
    )
  }
  if (block.type === 'list') {
    const ListTag = block.ordered ? 'ol' : 'ul'
    return (
      <ListTag className={`${block.ordered ? 'list-decimal' : 'list-disc'} space-y-2 pl-5 text-sm leading-7 text-[#475569]`}>
        {block.items.filter((item) => item.trim()).map((item, itemIndex) => (
          <li key={`${block.id}-${itemIndex}`}>{item}</li>
        ))}
      </ListTag>
    )
  }
  return null
}

function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
      <h3 className="mb-4 text-sm font-semibold text-gray-900 dark:text-white">{title}</h3>
      {children}
    </section>
  )
}

function TextInput({
  label,
  value,
  onChange,
  type = 'text',
  placeholder = '',
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  placeholder?: string
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={inputClass}
      />
    </label>
  )
}
