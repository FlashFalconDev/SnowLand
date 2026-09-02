/**
 * 教練管理（營運後台）
 * 對應 Django Coach + CoachResort + CoachCourseLevel
 *
 * 資料來源：真實 API（/api/admin/<client>/coaches/）
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Plus, Edit, Trash2, X, Loader2, AlertCircle, Globe2 } from 'lucide-react'
import { useNotification } from '../context'
import {
  fetchCoaches, createCoach, updateCoach, deleteCoach,
  type Coach, type CoachWriteData,
  type AvailabilityStatus, type AbilityLevel, type Language, type PriceLevel,
  type CoachCertification, type CertificationCategory,
} from '../api/coaches'
import { fetchResorts, type Resort } from '../api/resorts'
import { fetchCourseCategories, fetchCourseTypes, type CourseCategory, type CourseType } from '../api/courses'
import { fetchStaff, type StaffMember } from '../api/extras'

const PRIMARY = '#8b5cf6'

const STATUS_OPTIONS: { value: AvailabilityStatus; label: string; cls: string }[] = [
  { value: 'active', label: '主動接課', cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  { value: 'passive', label: '需確認接課', cls: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' },
  { value: 'unavailable', label: '不可接課', cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
]

const LANGUAGE_OPTIONS: { value: Language; label: string }[] = [
  { value: 'zh', label: '中文' },
  { value: 'en', label: '英文' },
  { value: 'yue', label: '粵語' },
]

const ABILITY_OPTIONS: { value: AbilityLevel; label: string }[] = [
  { value: 'no_exp', label: '等級0' },
  { value: 'level1', label: '等級1' },
  { value: 'level2', label: '等級2' },
  { value: 'level3', label: '等級3' },
  { value: 'level4', label: '等級4' },
  { value: 'level5', label: '等級5' },
  { value: 'level6', label: '等級6' },
]

const PRICE_LEVEL_OPTIONS: { value: PriceLevel; label: string }[] = [
  { value: 'Lv1', label: 'Lv1' },
  { value: 'Lv2', label: 'Lv2' },
  { value: 'Lv3', label: 'Lv3' },
  { value: 'director', label: '校長 / 總監' },
]

const PRICE_LEVEL_PILL: Record<PriceLevel, string> = {
  director: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  Lv3: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  Lv2: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  Lv1: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
}

const PRICE_LEVEL_RANK: Record<PriceLevel, number> = {
  Lv1: 1,
  Lv2: 2,
  Lv3: 3,
  director: 4,
}

const CERTIFICATION_CATEGORY_SHORT_LABEL: Record<CertificationCategory, string> = {
  snowboard: '單板',
  ski: '雙板',
  photo: '攝影',
  other: '其他',
}

const CERTIFICATION_CATEGORY_OPTIONS: { value: CertificationCategory; label: string }[] = [
  { value: 'snowboard', label: '單板 Snowboard' },
  { value: 'ski', label: '雙板 Ski' },
  { value: 'photo', label: '雪地攝影 Photography' },
  { value: 'other', label: '其他' },
]

type SelectOption = { value: string; label: string }

const CERTIFICATE_SYSTEM_OPTIONS: Record<CertificationCategory, SelectOption[]> = {
  snowboard: [
    { value: 'CASI', label: 'CASI（單板）' },
    { value: 'KSAI', label: 'KSAI（單板）' },
    { value: 'AASI', label: 'AASI（單板）' },
    { value: 'JSBA', label: 'JSBA（單板）' },
    { value: 'ASI Snowboard', label: 'ASI Snowboard（單板）' },
    { value: 'SBINZ', label: 'SBINZ（單板）' },
    { value: 'NZSIA Snowboard', label: 'NZSIA Snowboard（單板）' },
    { value: 'BASI Snowboard', label: 'BASI Snowboard（單板）' },
  ],
  ski: [
    { value: 'CSIA', label: 'CSIA（雙板）' },
    { value: 'KSIA', label: 'KSIA（雙板）' },
    { value: 'SIA Ski', label: 'SIA Ski（雙板）' },
    { value: 'SAJ', label: 'SAJ（雙板）' },
    { value: 'PSIA', label: 'PSIA（雙板）' },
    { value: 'PSIC', label: 'PSIC（雙板）' },
    { value: 'APSI Ski', label: 'APSI Ski（雙板）' },
    { value: 'NZSIA Ski', label: 'NZSIA Ski（雙板）' },
    { value: 'BASI Ski', label: 'BASI Ski（雙板）' },
  ],
  photo: [
    { value: 'Snow Photography', label: '雪地攝影' },
    { value: 'Action Photography', label: '滑雪側拍' },
    { value: 'Family Photography', label: '全家福攝影' },
  ],
  other: [
    { value: 'First Aid', label: '急救證照 / First Aid' },
    { value: 'Outdoor Guide', label: '戶外嚮導證照' },
    { value: 'Other Certificate', label: '其他證照' },
  ],
}

const CERTIFICATE_LEVEL_OPTIONS: Record<CertificationCategory, SelectOption[]> = {
  snowboard: [
    { value: 'Level 1', label: 'Level 1 / 一級' },
    { value: 'Level 2', label: 'Level 2 / 二級' },
    { value: 'Level 3', label: 'Level 3 / 三級' },
    { value: 'Level 4', label: 'Level 4 / 四級' },
    { value: 'Trainer', label: 'Trainer / 培訓官' },
    { value: 'Examiner', label: 'Examiner / 考官' },
  ],
  ski: [
    { value: 'Level 1', label: 'Level 1 / 一級' },
    { value: 'Level 2', label: 'Level 2 / 二級' },
    { value: 'Level 3', label: 'Level 3 / 三級' },
    { value: 'Level 4', label: 'Level 4 / 四級' },
    { value: 'Trainer', label: 'Trainer / 培訓官' },
    { value: 'Examiner', label: 'Examiner / 考官' },
  ],
  photo: [
    { value: 'Photographer', label: '攝影師' },
    { value: 'Lead Photographer', label: '主攝' },
    { value: 'Assistant Photographer', label: '助理攝影' },
  ],
  other: [
    { value: 'Certified', label: '合格 / Certified' },
    { value: 'Level 1', label: 'Level 1 / 一級' },
    { value: 'Level 2', label: 'Level 2 / 二級' },
    { value: 'Level 3', label: 'Level 3 / 三級' },
  ],
}

const QUERY_KEY = ['admin', 'coaches']

const withCurrentOption = (options: SelectOption[], currentValue: string) => {
  if (!currentValue || options.some((option) => option.value === currentValue)) return options
  return [{ value: currentValue, label: `${currentValue}（既有資料）` }, ...options]
}

const normalizeCertificationLevel = (level: string) => {
  const aliases: Record<string, string> = {
    Lv1: 'Level 1',
    Lv2: 'Level 2',
    Lv3: 'Level 3',
    Lv4: 'Level 4',
    LV1: 'Level 1',
    LV2: 'Level 2',
    LV3: 'Level 3',
    LV4: 'Level 4',
  }
  return aliases[level] || level
}

const resolveCertificationCategoryFromLabel = (label: string): CertificationCategory => {
  const source = label.toLowerCase()
  if (source.includes('snowboard') || source.includes('單板')) return 'snowboard'
  if (source.includes('ski') || source.includes('雙板')) return 'ski'
  if (source.includes('photo') || source.includes('photography') || source.includes('攝影')) return 'photo'
  return 'other'
}

const certificationLevelToPriceLevel = (level: string): PriceLevel | null => {
  const normalized = normalizeCertificationLevel(level).toLowerCase()
  if (!normalized) return null
  if (normalized.includes('examiner') || normalized.includes('trainer')) return 'Lv3'
  if (normalized.includes('level 4') || normalized.includes('lv4')) return 'Lv3'
  if (normalized.includes('level 3') || normalized.includes('lv3')) return 'Lv3'
  if (normalized.includes('level 2') || normalized.includes('lv2')) return 'Lv2'
  if (normalized.includes('level 1') || normalized.includes('lv1')) return 'Lv1'
  return null
}

const inferPriceLevelFromCertifications = (
  certifications: CoachCertification[] = [],
  category: CertificationCategory,
): PriceLevel => {
  let best: PriceLevel = 'Lv1'
  for (const cert of certifications) {
    if (cert.category !== category) continue
    const candidate = certificationLevelToPriceLevel(cert.level)
    if (candidate && PRICE_LEVEL_RANK[candidate] > PRICE_LEVEL_RANK[best]) {
      best = candidate
    }
  }
  return best
}

const formatCertification = (cert: CoachCertification) => {
  const categoryLabel = CERTIFICATION_CATEGORY_OPTIONS.find((opt) => opt.value === cert.category)?.label || ''
  return [categoryLabel, cert.certificate, normalizeCertificationLevel(cert.level), cert.note].filter(Boolean).join(' ')
}

const getApiErrorMessage = (error: any, fallback: string) => {
  const data = error?.response?.data
  if (!data) return fallback
  if (typeof data.msg === 'string') return data.msg
  if (typeof data.detail === 'string') return data.detail
  if (typeof data === 'object') {
    const first = Object.entries(data)[0]
    if (first) {
      const [field, value] = first
      return `${field}: ${Array.isArray(value) ? value.join('、') : String(value)}`
    }
  }
  return fallback
}

export default function CoachesPage() {
  const notify = useNotification()
  const qc = useQueryClient()

  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<AvailabilityStatus | ''>('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)

  // 列表查詢
  const { data: coaches = [], isLoading, error } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchCoaches,
  })

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: CoachWriteData) => createCoach(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['admin', 'staff'] })
      notify.success('教練建立成功')
      setCreating(false)
    },
    onError: (e: any) => notify.error(getApiErrorMessage(e, '建立失敗')),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: CoachWriteData }) => updateCoach(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['admin', 'staff'] })
      notify.success('教練資料已更新')
      setEditingId(null)
    },
    onError: (e: any) => notify.error(getApiErrorMessage(e, '更新失敗')),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteCoach(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['admin', 'staff'] })
      notify.success('教練已刪除')
    },
    onError: (e: any) => notify.error(getApiErrorMessage(e, '刪除失敗')),
  })

  const filtered = coaches.filter((c) => {
    if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false
    if (statusFilter && c.availability_status !== statusFilter) return false
    return true
  })

  const editing = creating
    ? makeEmptyCoach()
    : editingId
    ? coaches.find((c) => c.id === editingId) || null
    : null

  const handleSave = (writeData: CoachWriteData, id: number | null) => {
    if (id == null || id === 0) {
      createMutation.mutate(writeData)
    } else {
      updateMutation.mutate({ id, data: writeData })
    }
  }

  const handleDelete = (id: number) => {
    if (!confirm('確定要刪除此教練？')) return
    deleteMutation.mutate(id)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">教練管理</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">管理教練接課狀態、雪場、課程等級</p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2"
          style={{ backgroundColor: PRIMARY }}
        >
          <Plus size={16} />
          新增教練
        </button>
      </div>

      {/* 篩選列 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜尋教練姓名..."
              className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 focus:border-[#8b5cf6]"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as AvailabilityStatus | '')}
            className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
          >
            <option value="">全部接課狀態</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* 列表 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} />
          </div>
        ) : error ? (
          <div className="p-8 text-center">
            <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
            <p className="text-sm text-red-600 dark:text-red-400">
              載入失敗：{(error as any).message || '無法連接後端'}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
              請確認 Django 後端有開啟 API：<code className="font-mono">/api/admin/&lt;client&gt;/coaches/</code>
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
                <tr>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">教練</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden md:table-cell">語言</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden lg:table-cell">雪場</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden lg:table-cell">課程等級</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">接課狀態</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden md:table-cell">官網</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden md:table-cell">分派分數</th>
                  <th className="px-5 py-3 text-right font-medium text-gray-600 dark:text-gray-300">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {filtered.map((coach) => {
                  const statusOpt = STATUS_OPTIONS.find((s) => s.value === coach.availability_status) || STATUS_OPTIONS[0]
                  return (
                    <tr key={coach.id} className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded-full bg-gray-100 dark:bg-gray-700 overflow-hidden flex-shrink-0">
                            {coach.img ? (
                              <img src={coach.img} alt={coach.name} className="w-full h-full object-cover" loading="lazy" />
                            ) : (
                              <div
                                className="w-full h-full flex items-center justify-center text-white text-sm font-medium"
                                style={{ backgroundColor: PRIMARY }}
                              >
                                {coach.name.charAt(0)}
                              </div>
                            )}
                          </div>
                          <div className="min-w-0">
                            <div className="font-medium text-gray-900 dark:text-white truncate">{coach.name}</div>
                            {coach.user_email && (
                              <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{coach.user_email}</div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-gray-600 dark:text-gray-300 hidden md:table-cell whitespace-nowrap">
                        {coach.languages.map((l) => LANGUAGE_OPTIONS.find((x) => x.value === l)?.label).join(' / ')}
                      </td>
                      <td className="px-5 py-4 text-gray-600 dark:text-gray-300 hidden lg:table-cell">
                        <div className="flex flex-wrap gap-1">
                          {coach.resorts.length === 0 ? (
                            <span className="text-gray-400">—</span>
                          ) : (
                            coach.resorts.map((r) => (
                              <span key={r.resort_id} className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs">
                                {r.resort_name}
                              </span>
                            ))
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-4 hidden lg:table-cell">
                        <div className="flex flex-wrap gap-1">
                          {coach.course_levels.map((cl, i) => (
                            <span key={i} className={`px-2 py-0.5 rounded text-xs font-medium ${PRICE_LEVEL_PILL[cl.price_level]}`}>
                              {PRICE_LEVEL_OPTIONS.find((p) => p.value === cl.price_level)?.label}
                            </span>
                          ))}
                        </div>
                        {coach.certifications?.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {coach.certifications.slice(0, 2).map((cert, i) => (
                              <span key={`${cert.category}-${i}`} className="px-2 py-0.5 rounded text-xs font-medium bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300">
                                {formatCertification(cert)}
                              </span>
                            ))}
                            {coach.certifications.length > 2 && (
                              <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-300">
                                +{coach.certifications.length - 2}
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="px-5 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-1 text-xs font-medium rounded-full ${statusOpt.cls}`}>
                          {statusOpt.label}
                        </span>
                      </td>
                      <td className="px-5 py-4 hidden md:table-cell">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full ${
                            coach.website_enabled
                              ? 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300'
                              : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-300'
                          }`}
                        >
                          <Globe2 size={12} />
                          {coach.website_enabled ? '上線' : '不顯示'}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-gray-600 dark:text-gray-300 hidden md:table-cell">
                        <span className="font-mono">{coach.assignment_score}</span>
                      </td>
                      <td className="px-5 py-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => setEditingId(coach.id)}
                            className="p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                            title="編輯"
                          >
                            <Edit size={16} />
                          </button>
                          <button
                            onClick={() => handleDelete(coach.id)}
                            disabled={deleteMutation.isPending}
                            className="p-2 text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors disabled:opacity-50"
                            title="刪除"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-5 py-16 text-center text-sm text-gray-500 dark:text-gray-400">
                      {coaches.length === 0 ? '尚未建立任何教練' : '沒有符合條件的教練'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            共 <span className="font-medium">{filtered.length}</span> 位教練
          </div>
        </div>
      </div>

      {/* 編輯 / 新增抽屜 */}
      {editing && (
        <CoachEditDrawer
          coach={editing}
          isCreating={creating}
          isSaving={createMutation.isPending || updateMutation.isPending}
          onClose={() => {
            setEditingId(null)
            setCreating(false)
          }}
          onSave={(data) => handleSave(data, creating ? null : editing.id)}
        />
      )}
    </div>
  )
}

function makeEmptyCoach(): Coach {
  return {
    id: 0, name: '', user_id: null, user_email: '', user_name: '', user_username: '', languages: ['zh'],
    availability_status: 'active', assignment_score: 0, img: '',
    website_enabled: false, website_slug: '', website_sort_order: 0, website_card_bio: '',
    certifications: [],
    resorts: [], course_levels: [], created_at: '',
  }
}

// ============== 編輯抽屜 ==============
function CoachEditDrawer({
  coach, isCreating, isSaving, onClose, onSave,
}: {
  coach: Coach
  isCreating: boolean
  isSaving: boolean
  onClose: () => void
  onSave: (data: CoachWriteData) => void
}) {
  const [form, setForm] = useState<Coach>(() => ({
    ...coach,
    user_id: coach.user_id ?? null,
    user_email: coach.user_email || '',
    user_name: coach.user_name || '',
    user_username: coach.user_username || '',
    website_enabled: Boolean(coach.website_enabled),
    website_slug: coach.website_slug || '',
    website_sort_order: Number(coach.website_sort_order) || 0,
    website_card_bio: coach.website_card_bio || '',
    certifications: Array.isArray(coach.certifications) ? coach.certifications : [],
  }))
  const [memberSearch, setMemberSearch] = useState('')

  const { data: allResorts = [] } = useQuery<Resort[]>({
    queryKey: ['admin', 'resorts'],
    queryFn: fetchResorts,
  })

  const { data: allCourseTypes = [] } = useQuery<CourseType[]>({
    queryKey: ['admin', 'course-types-flat'],
    queryFn: fetchCourseTypes,
  })

  const { data: allCourseCategories = [] } = useQuery<CourseCategory[]>({
    queryKey: ['admin', 'course-categories'],
    queryFn: fetchCourseCategories,
  })

  const { data: memberCandidates = [] } = useQuery<StaffMember[]>({
    queryKey: ['admin', 'coach-member-search', memberSearch.trim()],
    queryFn: () => fetchStaff(memberSearch.trim() || undefined),
  })

  const getCourseCategory = (categoryId?: number | null) => {
    return allCourseCategories.find((category) => category.id === categoryId) || null
  }

  const getCourseTypeById = (courseTypeId: number) => {
    return allCourseTypes.find((courseType) => courseType.id === courseTypeId) || null
  }

  const getCourseTypeCategoryName = (courseType: CourseType | null) => {
    if (!courseType) return '未分類'
    return getCourseCategory(courseType.category)?.name || '未分類'
  }

  const getCourseTypeCertificationCategory = (courseType: CourseType | null): CertificationCategory => {
    if (!courseType) return 'other'
    return resolveCertificationCategoryFromLabel(`${getCourseTypeCategoryName(courseType)} ${courseType.name}`)
  }

  const applyCertificateLevelToCourse = (courseTypeId: number) => {
    const courseType = getCourseTypeById(courseTypeId)
    const category = getCourseTypeCertificationCategory(courseType)
    updateCourseLevel(courseTypeId, {
      price_level: inferPriceLevelFromCertifications(form.certifications || [], category),
    })
  }

  const selectedCourseLevelGroups = (() => {
    const selectedIds = new Set(form.course_levels.map((level) => level.course_type_id))
    const groups = allCourseCategories.map((category) => ({
      id: category.id,
      name: category.name,
      levels: form.course_levels.filter((level) => getCourseTypeById(level.course_type_id)?.category === category.id),
    })).filter((group) => group.levels.length > 0)

    const uncategorizedLevels = form.course_levels.filter((level) => {
      const courseType = getCourseTypeById(level.course_type_id)
      return !courseType || !allCourseCategories.some((category) => category.id === courseType.category)
    })
    if (uncategorizedLevels.length > 0) {
      groups.push({ id: -1, name: '未分類', levels: uncategorizedLevels })
    }

    if (groups.length === 0 && selectedIds.size > 0) {
      groups.push({ id: -1, name: '已選教學項目', levels: form.course_levels })
    }
    return groups
  })()

  const availableCourseTypeGroups = (() => {
    const isSelected = (courseType: CourseType) => (
      form.course_levels.some((level) => level.course_type_id === courseType.id)
    )
    const groups = allCourseCategories.map((category) => ({
      id: category.id,
      name: category.name,
      courseTypes: allCourseTypes.filter((courseType) => courseType.category === category.id && !isSelected(courseType)),
    })).filter((group) => group.courseTypes.length > 0)

    const uncategorized = allCourseTypes.filter((courseType) => (
      !isSelected(courseType) &&
      !allCourseCategories.some((category) => category.id === courseType.category)
    ))
    if (uncategorized.length > 0) {
      groups.push({ id: -1, name: '未分類', courseTypes: uncategorized })
    }
    return groups
  })()

  const currentMember: StaffMember | null = form.user_id ? {
    id: form.user_id,
    username: form.user_username || '',
    email: form.user_email || '',
    name: form.user_name || form.user_username || form.user_email || `User #${form.user_id}`,
    is_superuser: false,
    is_manager: false,
    is_coach: true,
    has_coach_record: true,
    coach_id: form.id || null,
    coach_name: form.name || null,
    date_joined: '',
    last_login: null,
  } : null
  const memberOptions = currentMember && !memberCandidates.some((u) => u.id === currentMember.id)
    ? [currentMember, ...memberCandidates]
    : memberCandidates

  const handleSelectMember = (userId: number | null) => {
    if (!userId) {
      setForm({ ...form, user_id: null, user_email: '', user_name: '', user_username: '' })
      return
    }
    const user = memberOptions.find((item) => item.id === userId)
    setForm({
      ...form,
      user_id: userId,
      user_email: user?.email || '',
      user_name: user?.name || '',
      user_username: user?.username || '',
    })
  }

  const toggleLanguage = (lang: Language) => {
    setForm((f) => ({
      ...f,
      languages: f.languages.includes(lang) ? f.languages.filter((l) => l !== lang) : [...f.languages, lang],
    }))
  }

  const toggleResort = (resort: Resort) => {
    setForm((f) => {
      const exists = f.resorts.find((r) => r.resort_id === resort.id)
      if (exists) return { ...f, resorts: f.resorts.filter((r) => r.resort_id !== resort.id) }
      return {
        ...f,
        resorts: [...f.resorts, {
          resort_id: resort.id,
          resort_name: resort.display_name,
          resort_priority: f.resorts.length + 1,
          assignment_score: f.assignment_score,
        }],
      }
    })
  }

  const updateResortAssignmentScore = (resortId: number, assignmentScore: number) => {
    setForm((f) => ({
      ...f,
      resorts: f.resorts.map((resort) => (
        resort.resort_id === resortId
          ? { ...resort, assignment_score: Math.max(0, assignmentScore) }
          : resort
      )),
    }))
  }

  const addCourseLevel = (ct: CourseType) => {
    if (form.course_levels.find((cl) => cl.course_type_id === ct.id)) return
    setForm((f) => ({
      ...f,
      course_levels: [...f.course_levels, {
        course_type_id: ct.id,
        course_type_name: ct.name,
        ability_levels: ['no_exp', 'level1', 'level2'],
        price_level: inferPriceLevelFromCertifications(
          f.certifications || [],
          getCourseTypeCertificationCategory(ct),
        ),
        course_order: f.course_levels.length + 1,
      }],
    }))
  }

  const removeCourseLevel = (courseTypeId: number) => {
    setForm((f) => ({
      ...f,
      course_levels: f.course_levels.filter((cl) => cl.course_type_id !== courseTypeId),
    }))
  }

  const updateCourseLevel = (courseTypeId: number, patch: Partial<typeof form.course_levels[0]>) => {
    setForm((f) => ({
      ...f,
      course_levels: f.course_levels.map((cl) =>
        cl.course_type_id === courseTypeId ? { ...cl, ...patch } : cl,
      ),
    }))
  }

  const toggleCourseAbility = (courseTypeId: number, ability: AbilityLevel) => {
    setForm((f) => ({
      ...f,
      course_levels: f.course_levels.map((cl) => {
        if (cl.course_type_id !== courseTypeId) return cl
        const has = cl.ability_levels.includes(ability)
        return {
          ...cl,
          ability_levels: has
            ? cl.ability_levels.filter((a) => a !== ability)
            : [...cl.ability_levels, ability],
        }
      }),
    }))
  }

  const addCertification = () => {
    setForm((f) => ({
      ...f,
      certifications: [
        ...(f.certifications || []),
        { category: 'snowboard', certificate: '', level: '', note: '', show_on_website: true },
      ],
    }))
  }

  const updateCertification = (index: number, patch: Partial<CoachCertification>) => {
    setForm((f) => ({
      ...f,
      certifications: (f.certifications || []).map((cert, i) => {
        if (i !== index) return cert
        const next = { ...cert, ...patch }
        if (next.category === 'photo') {
          next.show_on_website = false
        }
        return next
      }),
    }))
  }

  const updateCertificationCategory = (index: number, category: CertificationCategory) => {
    setForm((f) => ({
      ...f,
      certifications: (f.certifications || []).map((cert, i) => (
        i === index
          ? {
            ...cert,
            category,
            certificate: '',
            level: '',
            show_on_website: category !== 'photo',
          }
          : cert
      )),
    }))
  }

  const removeCertification = (index: number) => {
    setForm((f) => ({
      ...f,
      certifications: (f.certifications || []).filter((_, i) => i !== index),
    }))
  }

  const handleSubmit = () => {
    if (!form.name.trim()) {
      alert('請輸入教練姓名')
      return
    }
    if (form.website_enabled && !form.website_slug.trim()) {
      alert('顯示於官網時請填寫官網代號')
      return
    }
    const writeData: CoachWriteData = {
      name: form.name,
      user_id: form.user_id || null,
      languages: form.languages,
      availability_status: form.availability_status,
      assignment_score: form.assignment_score,
      img: form.img || '',
      website_enabled: form.website_enabled,
      website_slug: form.website_slug.trim(),
      website_sort_order: Number(form.website_sort_order) || 0,
      website_card_bio: form.website_card_bio || '',
      certifications: (form.certifications || [])
        .map((cert) => ({
          category: cert.category,
          certificate: (cert.certificate || '').trim(),
          level: normalizeCertificationLevel((cert.level || '').trim()),
          note: (cert.note || '').trim(),
          show_on_website: cert.category !== 'photo' && cert.show_on_website !== false,
        }))
        .filter((cert) => cert.certificate || cert.level || cert.note),
      resorts_input: form.resorts.map((r) => ({
        resort_id: r.resort_id,
        resort_priority: r.resort_priority,
        assignment_score: Number(r.assignment_score ?? form.assignment_score) || 0,
      })),
      course_levels_input: form.course_levels.map((cl) => ({
        course_type_id: cl.course_type_id,
        ability_levels: cl.ability_levels,
        price_level: cl.price_level,
        course_order: cl.course_order,
      })),
    }
    onSave(writeData)
  }

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 animate-fadeIn" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white dark:bg-gray-800 shadow-2xl flex flex-col animate-slideIn">
        <div
          className="px-6 py-4 flex items-center justify-between text-white"
          style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}
        >
          <h2 className="text-lg font-semibold">{isCreating ? '新增教練' : `編輯教練：${coach.name}`}</h2>
          <button onClick={onClose} className="text-white/80 hover:text-white">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* 基本資料 */}
          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">基本資料</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  姓名 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 focus:border-[#8b5cf6]"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">大頭照 URL</label>
                <input
                  type="text"
                  value={form.img}
                  onChange={(e) => setForm({ ...form, img: e.target.value })}
                  placeholder="/coach-images/xxx.jpg"
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm font-mono dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">預設分派權重分數</label>
                <input
                  type="number"
                  min={0}
                  value={form.assignment_score}
                  onChange={(e) => {
                    const v = Math.max(0, Number(e.target.value) || 0)
                    setForm({ ...form, assignment_score: v })
                  }}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                />
                <p className="mt-1 text-xs text-gray-500">沒有另外設定雪場分數時使用，分數越低越優先。</p>
              </div>
              <div className="col-span-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/50 p-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">綁定會員帳號</label>
                <p className="mb-3 text-xs text-gray-500 dark:text-gray-400">
                  綁定後，此會員登入後才能使用教練「我的課程 / 我的月曆 / 請假」功能；儲存時會同步開啟教練權限。
                </p>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_1.4fr]">
                  <input
                    type="text"
                    value={memberSearch}
                    onChange={(e) => setMemberSearch(e.target.value)}
                    placeholder="搜尋會員姓名、帳號或 Email"
                    className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                  />
                  <select
                    value={form.user_id || ''}
                    onChange={(e) => handleSelectMember(e.target.value ? Number(e.target.value) : null)}
                    className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                  >
                    <option value="">不綁定會員</option>
                    {memberOptions.map((member) => {
                      const boundToOtherCoach = !!member.coach_id && member.coach_id !== form.id
                      const memberLabel = `${member.name || member.username || member.email}${member.email ? ` (${member.email})` : ''}`
                      return (
                        <option key={member.id} value={member.id} disabled={boundToOtherCoach}>
                          {memberLabel}{boundToOtherCoach ? ` - 已綁定 ${member.coach_name}` : ''}
                        </option>
                      )
                    })}
                  </select>
                </div>
                {form.user_id && (
                  <p className="mt-2 text-xs text-gray-600 dark:text-gray-300">
                    目前綁定：{form.user_name || form.user_username || form.user_email || `User #${form.user_id}`}
                    {form.user_email ? `（${form.user_email}）` : ''}
                  </p>
                )}
                {form.user_id && memberOptions.find((member) => member.id === form.user_id)?.is_coach === false && (
                  <p className="mt-2 text-xs text-amber-600 dark:text-amber-300">
                    此會員尚未開教練權限，儲存後會自動開啟。
                  </p>
                )}
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-sky-100 bg-sky-50/70 p-4 dark:border-sky-900/40 dark:bg-sky-950/20">
            <div className="mb-3 flex items-center gap-2">
              <Globe2 size={16} className="text-sky-600 dark:text-sky-300" />
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">官網設定</h3>
            </div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200">
              <input
                type="checkbox"
                checked={form.website_enabled}
                onChange={(e) => setForm({ ...form, website_enabled: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
              />
              顯示在官網老師頁
            </label>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  官網代號 {form.website_enabled && <span className="text-red-500">*</span>}
                </label>
                <input
                  type="text"
                  value={form.website_slug}
                  onChange={(e) => setForm({ ...form, website_slug: e.target.value })}
                  placeholder="cash"
                  className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm font-mono dark:text-white focus:outline-none focus:ring-2 focus:ring-sky-500/30"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">官網排序</label>
                <input
                  type="number"
                  min={0}
                  value={form.website_sort_order}
                  onChange={(e) => setForm({ ...form, website_sort_order: Math.max(0, Number(e.target.value) || 0) })}
                  className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-sky-500/30"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">官網卡片簡介</label>
                <textarea
                  value={form.website_card_bio}
                  onChange={(e) => setForm({ ...form, website_card_bio: e.target.value })}
                  rows={3}
                  maxLength={160}
                  className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-sky-500/30"
                />
              </div>
            </div>
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">教練證照類別 / 等級</h3>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  官網教練卡只顯示非攝影類證照；雪地攝影類會保留在後台但不顯示於官網。
                </p>
              </div>
              <button
                type="button"
                onClick={addCertification}
                className="px-3 py-1.5 text-xs font-medium rounded-lg border border-[#8b5cf6] text-[#8b5cf6] hover:bg-[#8b5cf6]/10 flex items-center gap-1"
              >
                <Plus size={12} />
                新增證照
              </button>
            </div>

            {form.certifications.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/40 px-4 py-5 text-center text-sm text-gray-500 dark:text-gray-400">
                尚未設定證照
              </div>
            ) : (
              <div className="space-y-3">
                {form.certifications.map((cert, index) => {
                  const isPhoto = cert.category === 'photo'
                  const certificateOptions = withCurrentOption(
                    CERTIFICATE_SYSTEM_OPTIONS[cert.category] || [],
                    cert.certificate,
                  )
                  const levelValue = normalizeCertificationLevel(cert.level)
                  const levelOptions = withCurrentOption(
                    CERTIFICATE_LEVEL_OPTIONS[cert.category] || [],
                    levelValue,
                  )
                  const categoryLabel = CERTIFICATION_CATEGORY_OPTIONS.find((option) => option.value === cert.category)?.label || '證照'
                  return (
                    <div key={index} className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          {categoryLabel} 證照 {index + 1}
                        </span>
                        <button
                          type="button"
                          onClick={() => removeCertification(index)}
                          className="p-1 text-gray-400 hover:text-red-500"
                          title="移除證照"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">類別</label>
                          <select
                            value={cert.category}
                            onChange={(e) => updateCertificationCategory(index, e.target.value as CertificationCategory)}
                            className="w-full px-2 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white"
                          >
                            {CERTIFICATION_CATEGORY_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">發照體系 / 名稱</label>
                          <select
                            value={cert.certificate}
                            onChange={(e) => updateCertification(index, { certificate: e.target.value })}
                            className="w-full px-2 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white"
                          >
                            <option value="">請選擇{categoryLabel}證照</option>
                            {certificateOptions.map((option) => (
                              <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">等級</label>
                          <select
                            value={levelValue}
                            onChange={(e) => updateCertification(index, { level: e.target.value })}
                            className="w-full px-2 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white"
                          >
                            <option value="">請選擇等級</option>
                            {levelOptions.map((option) => (
                              <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">備註</label>
                          <input
                            value={cert.note || ''}
                            onChange={(e) => updateCertification(index, { note: e.target.value })}
                            placeholder="可留空"
                            className="w-full px-2 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white"
                          />
                        </div>
                      </div>
                      <label className={`mt-3 flex items-center gap-2 text-xs ${isPhoto ? 'text-gray-400' : 'text-gray-600 dark:text-gray-300'}`}>
                        <input
                          type="checkbox"
                          checked={!isPhoto && cert.show_on_website !== false}
                          disabled={isPhoto}
                          onChange={(e) => updateCertification(index, { show_on_website: e.target.checked })}
                          className="h-4 w-4 rounded border-gray-300 text-[#8b5cf6] focus:ring-[#8b5cf6]"
                        />
                        顯示在官網教練卡
                        {isPhoto && <span>攝影類不顯示</span>}
                      </label>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">接課狀態</h3>
            <div className="grid grid-cols-3 gap-2">
              {STATUS_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setForm({ ...form, availability_status: opt.value })}
                  className={`px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                    form.availability_status === opt.value
                      ? 'border-[#8b5cf6] text-white'
                      : 'border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-gray-300'
                  }`}
                  style={form.availability_status === opt.value ? { backgroundColor: PRIMARY } : undefined}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">教學語言（可複選）</h3>
            <div className="flex gap-2">
              {LANGUAGE_OPTIONS.map((lang) => (
                <button
                  key={lang.value}
                  type="button"
                  onClick={() => toggleLanguage(lang.value)}
                  className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
                    form.languages.includes(lang.value)
                      ? 'border-[#8b5cf6] text-white'
                      : 'border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-gray-300'
                  }`}
                  style={form.languages.includes(lang.value) ? { backgroundColor: PRIMARY } : undefined}
                >
                  {lang.label}
                </button>
              ))}
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">可接課雪場</h3>
            {allResorts.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">尚未建立任何雪場（請先去「雪場管理」新增）</p>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {allResorts.map((r) => {
                  const selectedResort = form.resorts.find((x) => x.resort_id === r.id)
                  const checked = !!selectedResort
                  return (
                    <div
                      key={r.id}
                      className={`rounded-lg border p-3 transition-colors ${
                        checked
                          ? 'border-[#8b5cf6] bg-[#8b5cf6]/10'
                          : 'border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600'
                      }`}
                    >
                      <label className="flex cursor-pointer items-center gap-2">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleResort(r)}
                          className="h-4 w-4"
                        />
                        <span className="text-sm font-medium text-gray-900 dark:text-white">{r.display_name}</span>
                      </label>
                      {checked && (
                        <div className="mt-3 grid grid-cols-[1fr_96px] items-end gap-3">
                          <div>
                            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                              此雪場分派分數
                            </label>
                            <p className="text-[11px] text-gray-500 dark:text-gray-400">
                              分數越低越優先；不確定就沿用預設。
                            </p>
                          </div>
                          <input
                            type="number"
                            min={0}
                            value={Number(selectedResort?.assignment_score ?? form.assignment_score) || 0}
                            onChange={(e) => updateResortAssignmentScore(r.id, Number(e.target.value) || 0)}
                            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-[#8b5cf6] focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">教學項目（依課程大類分組）</h3>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
              先分單板、雙板或其他大類，再設定可教的全天/半天課程；教練等級會依證照帶入，仍可手動調整。
            </p>

            {/* 已加入的教學項目 */}
            {form.course_levels.length === 0 ? (
              <p className="text-xs text-gray-500 mb-3">尚未加入任何教學項目</p>
            ) : (
              <div className="space-y-4 mb-4">
                {selectedCourseLevelGroups.map((group) => (
                  <div key={group.id} className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                    <div className="px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                      <div className="text-sm font-semibold text-gray-900 dark:text-white">{group.name}</div>
                    </div>
                    <div className="p-3 space-y-3 bg-gray-50 dark:bg-gray-700/50">
                      {group.levels.map((cl) => {
                        const courseType = getCourseTypeById(cl.course_type_id)
                        const displayName = courseType?.name || cl.course_type_name
                        const certificationCategory = getCourseTypeCertificationCategory(courseType)
                        const inferredLevel = inferPriceLevelFromCertifications(form.certifications || [], certificationCategory)
                        const isUsingCertificateLevel = cl.price_level === inferredLevel

                        return (
                          <div key={cl.course_type_id} className="p-4 bg-white dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600 space-y-3">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="text-sm font-medium text-gray-900 dark:text-white">{displayName}</span>
                                  <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                                    {CERTIFICATION_CATEGORY_SHORT_LABEL[certificationCategory]}
                                  </span>
                                  {isUsingCertificateLevel && (
                                    <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                                      已依證照
                                    </span>
                                  )}
                                </div>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                  建議等級：{PRICE_LEVEL_OPTIONS.find((p) => p.value === inferredLevel)?.label || inferredLevel}
                                </p>
                              </div>
                              <button
                                type="button"
                                onClick={() => removeCourseLevel(cl.course_type_id)}
                                className="p-1 text-gray-400 hover:text-red-500"
                                title="移除教學項目"
                              >
                                <X size={14} />
                              </button>
                            </div>

                            <div>
                              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">可教學員程度</label>
                              <div className="flex flex-wrap gap-1">
                                {ABILITY_OPTIONS.map((a) => {
                                  const checked = cl.ability_levels.includes(a.value)
                                  return (
                                    <button
                                      key={a.value}
                                      type="button"
                                      onClick={() => toggleCourseAbility(cl.course_type_id, a.value)}
                                      className={`px-2 py-1 rounded text-xs transition-colors ${
                                        checked
                                          ? 'text-white'
                                          : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100'
                                      }`}
                                      style={checked ? { backgroundColor: PRIMARY } : undefined}
                                    >
                                      {a.label}
                                    </button>
                                  )
                                })}
                              </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              <div>
                                <div className="flex items-center justify-between gap-2 mb-1">
                                  <label className="block text-xs text-gray-500 dark:text-gray-400">教練等級</label>
                                  <button
                                    type="button"
                                    onClick={() => applyCertificateLevelToCourse(cl.course_type_id)}
                                    className="text-xs text-[#8b5cf6] hover:underline"
                                  >
                                    套用證照等級
                                  </button>
                                </div>
                                <select
                                  value={cl.price_level}
                                  onChange={(e) => updateCourseLevel(cl.course_type_id, { price_level: e.target.value as PriceLevel })}
                                  className="w-full px-2 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white"
                                >
                                  {PRICE_LEVEL_OPTIONS.map((p) => (
                                    <option key={p.value} value={p.value}>{p.label}</option>
                                  ))}
                                </select>
                              </div>
                              <div>
                                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">接課順序（數字越小越優先）</label>
                                <input
                                  type="number"
                                  min={0}
                                  value={cl.course_order}
                                  onChange={(e) => {
                                    const v = Math.max(0, Number(e.target.value) || 0)
                                    updateCourseLevel(cl.course_type_id, { course_order: v })
                                  }}
                                  className="w-full px-2 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white"
                                />
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* 加入新教學項目 */}
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-2">新增可教課程類型</label>
              <div className="space-y-3">
                {allCourseTypes.length === 0 ? (
                  <p className="text-xs text-gray-500">尚未建立任何課程類型</p>
                ) : availableCourseTypeGroups.length === 0 ? (
                  <p className="text-xs text-gray-500">所有課程類型都已加入</p>
                ) : availableCourseTypeGroups.map((group) => (
                  <div key={group.id} className="rounded-lg border border-gray-200 dark:border-gray-700 p-3">
                    <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">{group.name}</div>
                    <div className="flex flex-wrap gap-2">
                      {group.courseTypes.map((ct) => {
                        const certificationCategory = getCourseTypeCertificationCategory(ct)
                        const inferredLevel = inferPriceLevelFromCertifications(form.certifications || [], certificationCategory)
                        return (
                          <button
                            key={ct.id}
                            type="button"
                            onClick={() => addCourseLevel(ct)}
                            className="px-3 py-1.5 text-xs border border-gray-300 dark:border-gray-600 rounded-full text-gray-700 dark:text-gray-300 hover:border-[#8b5cf6] hover:text-[#8b5cf6] flex items-center gap-1.5"
                          >
                            <Plus size={10} />
                            <span>{ct.name}</span>
                            <span className="text-gray-400">/</span>
                            <span>{inferredLevel}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <button
            onClick={onClose}
            disabled={isSaving}
            className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSaving}
            className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 flex items-center gap-2 disabled:opacity-50"
            style={{ backgroundColor: PRIMARY }}
          >
            {isSaving && <Loader2 size={14} className="animate-spin" />}
            {isCreating ? '建立教練' : '儲存變更'}
          </button>
        </div>
      </div>
    </>
  )
}
