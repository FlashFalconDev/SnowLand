/**
 * 課程定價設定
 *
 * Keep this page simple for daily operators:
 * 1. Set season ranges.
 * 2. Pick a course template.
 * 3. Set its price.
 */
import { useMemo, useState, type ReactNode } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  Calendar,
  ChevronRight,
  DollarSign,
  Edit,
  Loader2,
  MapPin,
  Plus,
  Trash2,
  X,
} from 'lucide-react'
import { useNotification } from '../context'
import {
  createCoursePricing,
  createSeason,
  deleteCoursePricing,
  deleteSeason,
  fetchCoursePricings,
  fetchSeasons,
  updateCoursePricing,
  updateSeason,
  type CoursePricing,
  type CoursePricingTier,
  type CoursePricingWriteData,
  type SeasonSetting,
  type SeasonSettingWriteData,
  type SeasonType,
} from '../api/pricing'
import { fetchCourseCategories, type CourseCategory, type CourseTemplate, type CourseType } from '../api/courses'
import { fetchResorts, type Resort } from '../api/resorts'

const PRIMARY = '#8b5cf6'
const PRICING_KEY = ['admin', 'course-pricing']
const SEASONS_KEY = ['admin', 'seasons']
const COURSE_CATEGORIES_KEY = ['admin', 'course-categories']
const RESORTS_KEY = ['admin', 'resorts']

export default function PricingPage() {
  const notify = useNotification()

  const { data: pricings = [], isLoading: pricingLoading, error: pricingError } = useQuery({
    queryKey: PRICING_KEY,
    queryFn: fetchCoursePricings,
  })

  const { data: seasons = [], isLoading: seasonsLoading } = useQuery({
    queryKey: SEASONS_KEY,
    queryFn: fetchSeasons,
  })

  const { data: courseCategories = [] } = useQuery({
    queryKey: COURSE_CATEGORIES_KEY,
    queryFn: fetchCourseCategories,
  })

  const { data: resorts = [] } = useQuery({
    queryKey: RESORTS_KEY,
    queryFn: fetchResorts,
  })

  const courseTypes: CourseType[] = useMemo(() => {
    return courseCategories.flatMap((category: CourseCategory) => category.types || [])
  }, [courseCategories])

  const allTemplates: CourseTemplate[] = useMemo(() => {
    return courseTypes.flatMap((ct: CourseType) => ct.templates || [])
  }, [courseTypes])

  if (pricingLoading || seasonsLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} />
      </div>
    )
  }

  if (pricingError) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
        <AlertCircle size={20} className="mt-0.5 shrink-0 text-red-600 dark:text-red-400" />
        <p className="text-sm text-red-700 dark:text-red-300">無法載入課程定價資料</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <SeasonsSection seasons={seasons} notify={notify} />
      <PricingSection
        pricings={pricings}
        allTemplates={allTemplates}
        courseCategories={courseCategories}
        courseTypes={courseTypes}
        resorts={resorts}
        notify={notify}
      />
    </div>
  )
}

function SeasonsSection({
  seasons,
  notify,
}: {
  seasons: SeasonSetting[]
  notify: ReturnType<typeof useNotification>
}) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState<Partial<SeasonSetting> | null>(null)

  const createM = useMutation({
    mutationFn: (data: SeasonSettingWriteData) => createSeason(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SEASONS_KEY })
      notify.success('已新增季節區間')
      setEditing(null)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '新增失敗'),
  })

  const updateM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: SeasonSettingWriteData }) => updateSeason(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SEASONS_KEY })
      notify.success('已更新季節區間')
      setEditing(null)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '更新失敗'),
  })

  const deleteM = useMutation({
    mutationFn: (id: number) => deleteSeason(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SEASONS_KEY })
      notify.success('已刪除')
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '刪除失敗'),
  })

  const handleSave = (data: Partial<SeasonSetting>) => {
    if (!data.name || !data.season_type || !data.start_date || !data.end_date) {
      notify.error('請填寫季節名稱與日期')
      return
    }

    const payload: SeasonSettingWriteData = {
      name: data.name,
      season_type: data.season_type,
      start_date: data.start_date,
      end_date: data.end_date,
    }

    if (data.id) updateM.mutate({ id: data.id, data: payload })
    else createM.mutate(payload)
  }

  return (
    <section className="rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
      <SectionHeader
        icon={<Calendar size={18} style={{ color: PRIMARY }} />}
        title="旺 / 淡季"
        action={
          <PrimaryButton onClick={() => setEditing({ season_type: 'peak' })}>
            <Plus size={16} />
            新增區間
          </PrimaryButton>
        }
      />

      {seasons.length === 0 ? (
        <EmptyState>尚未設定旺淡季，系統會先用淡季價格計算。</EmptyState>
      ) : (
        <ul className="divide-y divide-gray-200 dark:divide-gray-700">
          {seasons.map((season) => (
            <li key={season.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <SeasonBadge type={season.season_type} />
                  <span className="font-medium text-gray-900 dark:text-white">{season.name}</span>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {season.start_date} ~ {season.end_date}
                  </span>
                </div>
              </div>
              <IconActions
                onEdit={() => setEditing(season)}
                onDelete={() => {
                  if (confirm(`確定刪除「${season.name}」？`)) deleteM.mutate(season.id)
                }}
              />
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <SeasonModal
          value={editing}
          onClose={() => setEditing(null)}
          onSave={handleSave}
        />
      )}
    </section>
  )
}

function SeasonModal({
  value,
  onClose,
  onSave,
}: {
  value: Partial<SeasonSetting>
  onClose: () => void
  onSave: (data: Partial<SeasonSetting>) => void
}) {
  const [form, setForm] = useState<Partial<SeasonSetting>>({
    id: value.id,
    name: value.name || '',
    season_type: (value.season_type as SeasonType) || 'peak',
    start_date: value.start_date || '',
    end_date: value.end_date || '',
  })

  return (
    <ModalFrame title={value.id ? '編輯季節區間' : '新增季節區間'} onClose={onClose} maxWidth="max-w-md">
      <div className="space-y-4 p-4">
        <Field label="名稱">
          <input
            type="text"
            value={form.name || ''}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="例如：2026 雪季旺季"
            className={inputClass}
          />
        </Field>
        <Field label="類型">
          <select
            value={form.season_type || 'peak'}
            onChange={(e) => setForm({ ...form, season_type: e.target.value as SeasonType })}
            className={inputClass}
          >
            <option value="peak">旺季</option>
            <option value="off">淡季</option>
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="開始日期">
            <input
              type="date"
              value={form.start_date || ''}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              className={inputClass}
            />
          </Field>
          <Field label="結束日期">
            <input
              type="date"
              value={form.end_date || ''}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              className={inputClass}
            />
          </Field>
        </div>
      </div>
      <ModalFooter onClose={onClose} onSave={() => onSave(form)} saveLabel="儲存" />
    </ModalFrame>
  )
}

function preparePeopleTiers(
  tiers: CoursePricingTier[] | undefined,
  maxCapacity: number,
): { tiers: CoursePricingTier[]; error?: string } {
  const prepared = (tiers || [])
    .map((tier) => ({
      min_people: Number(tier.min_people) || 0,
      max_people: Number(tier.max_people) || 0,
      price: Number(tier.price) || 0,
      is_active: tier.is_active ?? true,
    }))
    .filter((tier) => tier.min_people > 0 || tier.max_people > 0 || tier.price > 0)

  const activeRanges: { start: number; end: number }[] = []
  for (const tier of prepared) {
    if (tier.min_people < 1 || tier.max_people < tier.min_people) {
      return { tiers: [], error: '人數級距設定不正確' }
    }
    if (tier.max_people > maxCapacity) {
      return { tiers: [], error: '級距人數不可超過人數上限' }
    }
    if (tier.price < 0) {
      return { tiers: [], error: '價格不可小於 0' }
    }
    if (!tier.is_active) continue
    for (const range of activeRanges) {
      if (tier.min_people <= range.end && tier.max_people >= range.start) {
        return { tiers: [], error: '啟用中的人數級距不可重疊' }
      }
    }
    activeRanges.push({ start: tier.min_people, end: tier.max_people })
  }

  const sorted = [...prepared].sort((a, b) => a.min_people - b.min_people || a.max_people - b.max_people)
  return {
    tiers: sorted.map((tier, index) => ({
      min_people: tier.min_people,
      max_people: tier.max_people,
      price: tier.price,
      is_active: tier.is_active,
      display_order: index,
    })),
  }
}

function formatPeopleTiers(pricing: CoursePricing) {
  const tiers = (pricing.people_tiers || [])
    .filter((tier) => tier.is_active)
    .sort((a, b) => a.min_people - b.min_people || a.max_people - b.max_people)

  if (tiers.length === 0) return ''
  return tiers
    .map((tier) => `${tier.min_people}-${tier.max_people} 人 NT$ ${tier.price.toLocaleString()}`)
    .join(' / ')
}

function formatDate(value?: string | null) {
  if (!value) return ''
  return value.replace(/-/g, '/')
}

function formatDateRange(start?: string | null, end?: string | null) {
  if (!start && !end) return '未設定'
  if (start && end) return `${formatDate(start)} ~ ${formatDate(end)}`
  if (start) return `${formatDate(start)} 起`
  return `到 ${formatDate(end)}`
}

function getPriceStart(pricings: CoursePricing[]) {
  const candidates = pricings.flatMap((pricing) => {
    const tiers = (pricing.people_tiers || []).filter((tier) => tier.is_active).map((tier) => tier.price)
    return tiers.length > 0 ? tiers : [pricing.base_price_off_peak]
  })
  if (candidates.length === 0) return null
  return Math.min(...candidates)
}

function getUniqueResortCount(pricings: CoursePricing[]) {
  return new Set(pricings.map((pricing) => pricing.resort)).size
}

function PricingSection({
  pricings,
  allTemplates,
  courseCategories,
  courseTypes,
  resorts,
  notify,
}: {
  pricings: CoursePricing[]
  allTemplates: CourseTemplate[]
  courseCategories: CourseCategory[]
  courseTypes: CourseType[]
  resorts: Resort[]
  notify: ReturnType<typeof useNotification>
}) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState<Partial<CoursePricing> | null>(null)
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null)
  const [selectedTypeId, setSelectedTypeId] = useState<number | null>(null)
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null)

  const createM = useMutation({
    mutationFn: (data: CoursePricingWriteData) => createCoursePricing(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PRICING_KEY })
      notify.success('已新增價格')
      setEditing(null)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '新增失敗'),
  })

  const updateM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: CoursePricingWriteData }) => updateCoursePricing(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PRICING_KEY })
      notify.success('已更新價格')
      setEditing(null)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '更新失敗'),
  })

  const deleteM = useMutation({
    mutationFn: (id: number) => deleteCoursePricing(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PRICING_KEY })
      notify.success('已刪除')
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '刪除失敗'),
  })

  const byTemplate = useMemo(() => {
    const map = new Map<number, CoursePricing[]>()
    for (const pricing of pricings) {
      for (const templateId of pricing.templates) {
        if (!map.has(templateId)) map.set(templateId, [])
        map.get(templateId)!.push(pricing)
      }
    }
    return map
  }, [pricings])

  const selectedCategory = useMemo(() => {
    if (courseCategories.length === 0) return null
    return courseCategories.find((category) => category.id === selectedCategoryId) || courseCategories[0]
  }, [courseCategories, selectedCategoryId])

  const typeOptions = selectedCategory?.types || []
  const selectedType = useMemo(() => {
    if (typeOptions.length === 0) return null
    return typeOptions.find((courseType) => courseType.id === selectedTypeId) || typeOptions[0]
  }, [typeOptions, selectedTypeId])

  const templateOptions = selectedType?.templates || []
  const selectedTemplate = useMemo(() => {
    if (templateOptions.length === 0) return null
    return templateOptions.find((template) => template.id === selectedTemplateId) || templateOptions[0]
  }, [templateOptions, selectedTemplateId])

  const orphanPricings = useMemo(() => {
    const templateIds = new Set(allTemplates.map((template) => template.id))
    return pricings.filter((pricing) => !pricing.templates.some((templateId) => templateIds.has(templateId)))
  }, [pricings, allTemplates])

  const missingCount = allTemplates.filter((template) => (byTemplate.get(template.id) || []).length === 0).length

  const getTargetResorts = (template: CourseTemplate) => {
    if (template.resorts?.length) {
      const allowedIds = new Set(template.resorts)
      return resorts.filter((resort) => allowedIds.has(resort.id))
    }
    return resorts
  }

  const getTemplatePriceState = (template: CourseTemplate) => {
    const templatePricings = byTemplate.get(template.id) || []
    const activePricings = templatePricings.filter((pricing) => pricing.is_active)
    const targetResorts = getTargetResorts(template)
    const targetResortIds = new Set(targetResorts.map((resort) => resort.id))
    const activeTargetPricings = activePricings.filter((pricing) => targetResortIds.has(pricing.resort))
    const missingResorts = targetResorts.filter(
      (resort) => !activeTargetPricings.some((pricing) => pricing.resort === resort.id),
    )

    return {
      count: templatePricings.length,
      activeCount: getUniqueResortCount(activeTargetPricings),
      targetCount: targetResorts.length,
      missingResortCount: missingResorts.length,
      priceStart: getPriceStart(activePricings.length > 0 ? activePricings : templatePricings),
    }
  }

  const handleSave = (data: Partial<CoursePricing>) => {
    if (!data.templates || data.templates.length === 0) {
      notify.error('請選擇至少一個課程')
      return
    }
    if (!data.resort) {
      notify.error('請選擇雪場')
      return
    }
    if (data.base_price_off_peak == null || data.base_price_off_peak < 0) {
      notify.error('請填寫基本價格')
      return
    }
    if (data.additional_person_fee == null || data.additional_person_fee < 0) {
      notify.error('請填寫每多一人加價')
      return
    }
    if (!data.max_capacity || data.max_capacity < 1) {
      notify.error('請填寫人數上限')
      return
    }

    const tierResult = preparePeopleTiers(data.people_tiers, data.max_capacity)
    if (tierResult.error) {
      notify.error(tierResult.error)
      return
    }

    const payload: CoursePricingWriteData = {
      templates: data.templates,
      resort: data.resort,
      base_price_off_peak: data.base_price_off_peak,
      peak_season_surcharge: data.peak_season_surcharge || 0,
      additional_person_fee: data.additional_person_fee,
      max_capacity: data.max_capacity,
      people_tiers: tierResult.tiers,
      is_active: data.is_active ?? true,
    }

    if (data.id) updateM.mutate({ id: data.id, data: payload })
    else createM.mutate(payload)
  }

  const openNewForTemplate = (template: CourseTemplate, resort?: Resort) => {
    const source = (byTemplate.get(template.id) || []).find((pricing) => pricing.is_active) || (byTemplate.get(template.id) || [])[0]
    setEditing({
      is_active: true,
      templates: [template.id],
      resort: resort?.id,
      peak_season_surcharge: source?.peak_season_surcharge ?? 0,
      additional_person_fee: source?.additional_person_fee ?? 0,
      base_price_off_peak: source?.base_price_off_peak ?? 0,
      max_capacity: source?.max_capacity ?? template.max_capacity ?? 6,
      people_tiers: (source?.people_tiers || []).map((tier) => ({
        min_people: tier.min_people,
        max_people: tier.max_people,
        price: tier.price,
        is_active: tier.is_active,
        display_order: tier.display_order,
      })),
    })
  }

  const handleSelectCategory = (category: CourseCategory) => {
    const firstType = category.types?.[0] || null
    const firstTemplate = firstType?.templates?.[0] || null
    setSelectedCategoryId(category.id)
    setSelectedTypeId(firstType?.id ?? null)
    setSelectedTemplateId(firstTemplate?.id ?? null)
  }

  const handleSelectType = (courseType: CourseType) => {
    setSelectedTypeId(courseType.id)
    setSelectedTemplateId(courseType.templates?.[0]?.id ?? null)
  }

  const selectedTemplatePricings = selectedTemplate ? byTemplate.get(selectedTemplate.id) || [] : []
  const selectedTemplateActivePricings = selectedTemplatePricings.filter((pricing) => pricing.is_active)
  const selectedTargetResorts = selectedTemplate ? getTargetResorts(selectedTemplate) : []
  const selectedTargetResortIds = new Set(selectedTargetResorts.map((resort) => resort.id))
  const selectedTargetActivePricings = selectedTemplateActivePricings.filter((pricing) => (
    selectedTargetResortIds.has(pricing.resort)
  ))
  const selectedConfiguredResortCount = getUniqueResortCount(selectedTargetActivePricings)
  const extraPricings = selectedTemplatePricings.filter((pricing) => !selectedTargetResortIds.has(pricing.resort))
  const extraResortIds = new Set(extraPricings.map((pricing) => pricing.resort))
  const selectedMissingResortCount = selectedTargetResorts.filter(
    (resort) => !selectedTargetActivePricings.some((pricing) => pricing.resort === resort.id),
  ).length

  return (
    <section className="rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
      <SectionHeader
        icon={<DollarSign size={18} style={{ color: PRIMARY }} />}
        title="課程價格"
        subtitle={missingCount > 0 ? `先選課程，再看各雪場價格。還有 ${missingCount} 個課程沒有任何價格。` : '先選課程，再看各雪場價格。'}
        action={
          <PrimaryButton
            onClick={() => setEditing({ is_active: true, templates: [], peak_season_surcharge: 0, people_tiers: [] })}
          >
            <Plus size={16} />
            新增共用價格
          </PrimaryButton>
        }
      />

      {allTemplates.length === 0 || courseCategories.length === 0 ? (
        <EmptyState>尚未建立課程模板，請先到「課程類型」新增課程。</EmptyState>
      ) : (
        <div className="grid gap-4 p-4 xl:grid-cols-[260px_320px_minmax(0,1fr)]">
          <div className="rounded-xl border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-900/30">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">1. 找課程</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">先選大類，再選類型。</p>
              </div>
              <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                {allTemplates.length}
              </span>
            </div>
            <div className="space-y-2">
              {courseCategories.map((category) => {
                const categoryTemplateCount = (category.types || []).reduce(
                  (sum, courseType) => sum + (courseType.templates || []).length,
                  0,
                )
                const isCategorySelected = selectedCategory?.id === category.id

                return (
                  <div key={category.id} className="space-y-1">
                    <button
                      type="button"
                      onClick={() => handleSelectCategory(category)}
                      className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left transition ${
                        isCategorySelected
                          ? 'border-violet-500 bg-violet-50 text-violet-800 dark:bg-violet-900/30 dark:text-violet-100'
                          : 'border-gray-200 bg-white text-gray-800 hover:border-violet-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100'
                      }`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold">{category.name}</span>
                        <span className="text-xs opacity-70">{categoryTemplateCount} 個模板</span>
                      </span>
                      <ChevronRight size={16} className={isCategorySelected ? 'rotate-90 transition' : 'transition'} />
                    </button>
                    {isCategorySelected && (
                      <div className="space-y-1 pl-3">
                        {(category.types || []).map((courseType) => {
                          const isTypeSelected = selectedType?.id === courseType.id
                          return (
                            <button
                              key={courseType.id}
                              type="button"
                              onClick={() => handleSelectType(courseType)}
                              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition ${
                                isTypeSelected
                                  ? 'bg-violet-600 text-white'
                                  : 'bg-white text-gray-700 hover:bg-gray-100 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700'
                              }`}
                            >
                              <span className="truncate">{courseType.name}</span>
                              <span className={isTypeSelected ? 'text-white/80' : 'text-gray-400'}>
                                {(courseType.templates || []).length}
                              </span>
                            </button>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          <div className="rounded-xl border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-900/30">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">2. 選模板</h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {selectedType ? selectedType.name : '請先選類型'}
              </p>
            </div>
            {templateOptions.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
                這個類型還沒有課程模板
              </div>
            ) : (
              <div className="space-y-2">
                {templateOptions.map((template) => {
                  const state = getTemplatePriceState(template)
                  const isTemplateSelected = selectedTemplate?.id === template.id

                  return (
                    <button
                      key={template.id}
                      type="button"
                      onClick={() => setSelectedTemplateId(template.id)}
                      className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                        isTemplateSelected
                          ? 'border-violet-500 bg-violet-50 shadow-sm dark:bg-violet-900/30'
                          : 'border-gray-200 bg-white hover:border-violet-300 dark:border-gray-700 dark:bg-gray-800'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="break-words text-sm font-semibold text-gray-900 dark:text-white">
                            {template.name}
                          </div>
                          <div className="mt-1 flex flex-wrap gap-x-2 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
                            <span>{template.duration_hours} 小時</span>
                            <span>最多 {template.max_capacity} 人</span>
                            {state.priceStart !== null && <span>NT$ {state.priceStart.toLocaleString()} 起</span>}
                          </div>
                        </div>
                        <PricingStatus count={state.count} activeCount={state.activeCount} />
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                        <span className="rounded bg-blue-50 px-2 py-1 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200">
                          開課 {formatDateRange(template.course_start_date, template.course_end_date)}
                        </span>
                        {state.targetCount > 0 && state.missingResortCount > 0 && (
                          <span className="rounded bg-orange-50 px-2 py-1 text-orange-700 dark:bg-orange-900/30 dark:text-orange-200">
                            尚缺 {state.missingResortCount} 個雪場
                          </span>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          <div className="min-w-0 rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/30">
            {selectedTemplate ? (
              <>
                <div className="flex flex-col gap-3 border-b border-gray-200 p-3 dark:border-gray-700 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">3. 設定各雪場價格</h3>
                    <p className="mt-1 break-words text-sm font-medium text-gray-900 dark:text-white">
                      {selectedTemplate.name}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                      <span className="rounded bg-blue-50 px-2 py-1 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200">
                        報名 {formatDateRange(selectedTemplate.booking_open_date, selectedTemplate.booking_close_date)}
                      </span>
                      <span className="rounded bg-purple-50 px-2 py-1 text-purple-700 dark:bg-purple-900/30 dark:text-purple-200">
                        開課 {formatDateRange(selectedTemplate.course_start_date, selectedTemplate.course_end_date)}
                      </span>
                      <span className="rounded bg-gray-200 px-2 py-1 text-gray-700 dark:bg-gray-700 dark:text-gray-200">
                        {selectedConfiguredResortCount}/{selectedTargetResorts.length} 個雪場已設定
                      </span>
                      {selectedMissingResortCount > 0 && (
                        <span className="rounded bg-orange-100 px-2 py-1 text-orange-700 dark:bg-orange-900/40 dark:text-orange-200">
                          尚缺 {selectedMissingResortCount} 個
                        </span>
                      )}
                      {extraPricings.length > 0 && (
                        <span className="rounded bg-yellow-100 px-2 py-1 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200">
                          {extraResortIds.size} 個未綁定雪場已有價格
                        </span>
                      )}
                    </div>
                  </div>
                  <PrimaryButton onClick={() => openNewForTemplate(selectedTemplate)} small>
                    <Plus size={14} />
                    新增價格
                  </PrimaryButton>
                </div>

                {selectedTargetResorts.length === 0 ? (
                  <EmptyState>這個課程模板尚未綁定雪場，請先回「課程架構」設定適用雪場。</EmptyState>
                ) : (
                  <div className="space-y-3 p-3">
                    {selectedTargetResorts.map((resort) => {
                      const resortPricings = selectedTemplatePricings.filter((pricing) => pricing.resort === resort.id)
                      const activeResortPricings = resortPricings.filter((pricing) => pricing.is_active)

                      return (
                        <div
                          key={resort.id}
                          className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800"
                        >
                          <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                            <div className="flex min-w-0 items-center gap-2">
                              <MapPin size={16} className="shrink-0 text-violet-500" />
                              <div className="min-w-0">
                                <div className="truncate text-sm font-semibold text-gray-900 dark:text-white">
                                  {resort.display_name}
                                </div>
                                <div className="text-xs text-gray-500 dark:text-gray-400">
                                  {activeResortPricings.length > 0 ? `${activeResortPricings.length} 組啟用價格` : '尚未設定啟用價格'}
                                </div>
                              </div>
                            </div>
                            {resortPricings.length === 0 ? (
                              <button
                                type="button"
                                onClick={() => openNewForTemplate(selectedTemplate, resort)}
                                className="rounded-lg border border-violet-200 px-3 py-1.5 text-sm font-medium text-violet-700 hover:bg-violet-50 dark:border-violet-700 dark:text-violet-200 dark:hover:bg-violet-900/30"
                              >
                                設定這個雪場
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => openNewForTemplate(selectedTemplate, resort)}
                                className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-700"
                              >
                                新增另一組
                              </button>
                            )}
                          </div>

                          {resortPricings.length === 0 ? (
                            <div className="rounded-lg border border-dashed border-orange-200 bg-orange-50 px-3 py-3 text-sm text-orange-700 dark:border-orange-800 dark:bg-orange-900/20 dark:text-orange-200">
                              尚未設定價格。按「設定這個雪場」會先帶入同課程既有價格，減少重複填寫。
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {resortPricings.map((pricing) => (
                                <PricingRow
                                  key={pricing.id}
                                  pricing={pricing}
                                  compact
                                  onEdit={() => setEditing(pricing)}
                                  onDelete={() => {
                                    if (confirm(`確定刪除「${pricing.resort_name}」的價格？`)) deleteM.mutate(pricing.id)
                                  }}
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}

                    {extraPricings.length > 0 && (
                      <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-3 dark:border-yellow-800 dark:bg-yellow-900/20">
                        <div className="mb-2">
                          <div className="text-sm font-semibold text-yellow-900 dark:text-yellow-100">
                            已建立但未綁定在此課程模板的雪場價格
                          </div>
                          <p className="mt-1 text-xs text-yellow-800 dark:text-yellow-200">
                            這些價格已存入資料庫，但此課程模板目前沒有開放這些雪場，所以前台不會出現。若要使用，請到「課程架構」把雪場加到此模板。
                          </p>
                        </div>
                        <div className="space-y-2">
                          {extraPricings.map((pricing) => (
                            <PricingRow
                              key={pricing.id}
                              pricing={pricing}
                              compact
                              warningLabel="未綁定在模板雪場"
                              onEdit={() => setEditing(pricing)}
                              onDelete={() => {
                                if (confirm(`確定刪除「${pricing.resort_name}」的價格？`)) deleteM.mutate(pricing.id)
                              }}
                            />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <EmptyState>請先選擇課程模板。</EmptyState>
            )}
          </div>
        </div>
      )}

      {orphanPricings.length > 0 && (
        <div className="m-4 rounded-lg border border-yellow-200 bg-yellow-50 p-3 dark:border-yellow-800 dark:bg-yellow-900/20">
          <p className="text-xs text-yellow-800 dark:text-yellow-300">
            有 {orphanPricings.length} 筆價格找不到對應課程，可能是課程已刪除，建議整理。
          </p>
        </div>
      )}

      {editing && (
        <PricingModal
          value={editing}
          courseTypes={courseTypes}
          resorts={resorts}
          onClose={() => setEditing(null)}
          onSave={handleSave}
        />
      )}
    </section>
  )
}

function PricingStatus({ count, activeCount }: { count: number; activeCount: number }) {
  if (count === 0) {
    return (
      <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700 dark:bg-orange-900/40 dark:text-orange-300">
        未設定
      </span>
    )
  }
  if (activeCount === 0) {
    return (
      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
        已停用
      </span>
    )
  }
  return (
    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
      已設定
    </span>
  )
}

function PricingRow({
  pricing,
  template,
  onEdit,
  onDelete,
  compact = false,
  warningLabel,
}: {
  pricing: CoursePricing
  template?: CourseTemplate
  onEdit: () => void
  onDelete: () => void
  compact?: boolean
  warningLabel?: string
}) {
  const peopleTierText = formatPeopleTiers(pricing)
  const mainPrice = peopleTierText || `基本 NT$ ${pricing.base_price_off_peak.toLocaleString()}`

  return (
    <div className="flex flex-col gap-3 rounded-lg bg-gray-50 px-3 py-3 dark:bg-gray-900/40 lg:flex-row lg:items-center lg:justify-between">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="break-words text-sm font-medium text-gray-900 dark:text-white">{pricing.resort_name}</span>
          {!pricing.is_active && (
            <span className="rounded bg-gray-200 px-1.5 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300">
              停用
            </span>
          )}
          {warningLabel && (
            <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-xs text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-200">
              {warningLabel}
            </span>
          )}
          {!compact && pricing.template_names.length > 1 && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              共用於 {pricing.template_names.length} 個課程
            </span>
          )}
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <PriceMetric label={peopleTierText ? '人數級距' : '1 人基本價'} value={mainPrice} />
          <PriceMetric label="旺季加價" value={`NT$ ${pricing.peak_season_surcharge.toLocaleString()}`} />
          <PriceMetric label="每增加 1 人" value={`NT$ ${pricing.additional_person_fee.toLocaleString()}`} />
          <PriceMetric label="人數上限" value={`${pricing.max_capacity} 人`} />
        </div>
        {template && (
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            <span className="rounded bg-blue-50 px-2 py-1 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200">
              開課 {formatDateRange(template.course_start_date, template.course_end_date)}
            </span>
            <span className="rounded bg-purple-50 px-2 py-1 text-purple-700 dark:bg-purple-900/30 dark:text-purple-200">
              報名 {formatDateRange(template.booking_open_date, template.booking_close_date)}
            </span>
          </div>
        )}
      </div>
      <IconActions onEdit={onEdit} onDelete={onDelete} />
    </div>
  )
}

function PriceMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-gray-200 bg-white px-2.5 py-2 dark:border-gray-700 dark:bg-gray-800">
      <div className="text-[11px] font-medium text-gray-500 dark:text-gray-400">{label}</div>
      <div className="mt-0.5 break-words text-xs font-semibold text-gray-900 dark:text-white">{value}</div>
    </div>
  )
}

function PricingModal({
  value,
  courseTypes,
  resorts,
  onClose,
  onSave,
}: {
  value: Partial<CoursePricing>
  courseTypes: CourseType[]
  resorts: Resort[]
  onClose: () => void
  onSave: (data: Partial<CoursePricing>) => void
}) {
  const [form, setForm] = useState<Partial<CoursePricing>>({
    id: value.id,
    templates: value.templates || [],
    resort: value.resort,
    base_price_off_peak: value.base_price_off_peak ?? 0,
    peak_season_surcharge: value.peak_season_surcharge ?? 0,
    additional_person_fee: value.additional_person_fee ?? 0,
    max_capacity: value.max_capacity ?? 6,
    people_tiers: value.people_tiers || [],
    is_active: value.is_active ?? true,
  })
  const [pricingMode, setPricingMode] = useState<'basic' | 'tiered'>((value.people_tiers || []).length > 0 ? 'tiered' : 'basic')
  const selectedTemplateCount = form.templates?.length || 0

  const toggleTemplate = (id: number) => {
    const current = form.templates || []
    if (current.includes(id)) setForm({ ...form, templates: current.filter((templateId) => templateId !== id) })
    else setForm({ ...form, templates: [...current, id] })
  }

  const handlePricingModeChange = (mode: 'basic' | 'tiered') => {
    setPricingMode(mode)
    if (mode === 'basic') {
      setForm({ ...form, people_tiers: [] })
    }
  }

  const addPeopleTier = () => {
    const current = form.people_tiers || []
    const last = current[current.length - 1]
    const nextMin = last ? last.max_people + 1 : 1
    setForm({
      ...form,
      people_tiers: [
        ...current,
        {
          min_people: nextMin,
          max_people: Math.min(nextMin, form.max_capacity || nextMin),
          price: 0,
          is_active: true,
          display_order: current.length,
        },
      ],
    })
  }

  const updatePeopleTier = (index: number, patch: Partial<CoursePricingTier>) => {
    const current = form.people_tiers || []
    setForm({
      ...form,
      people_tiers: current.map((tier, tierIndex) => (tierIndex === index ? { ...tier, ...patch } : tier)),
    })
  }

  const removePeopleTier = (index: number) => {
    const current = form.people_tiers || []
    setForm({ ...form, people_tiers: current.filter((_, tierIndex) => tierIndex !== index) })
  }

  return (
    <ModalFrame title={value.id ? '設定價格' : '新增價格'} onClose={onClose} maxWidth="max-w-3xl">
      <div className="space-y-5 overflow-y-auto p-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="雪場">
            <select
              value={form.resort ?? ''}
              onChange={(e) => setForm({ ...form, resort: e.target.value ? Number(e.target.value) : undefined })}
              className={inputClass}
            >
              <option value="">請選擇雪場</option>
              {resorts.map((resort) => (
                <option key={resort.id} value={resort.id}>{resort.display_name}</option>
              ))}
            </select>
          </Field>

          <Field label="狀態">
            <select
              value={form.is_active ? 'active' : 'inactive'}
              onChange={(e) => setForm({ ...form, is_active: e.target.value === 'active' })}
              className={inputClass}
            >
              <option value="active">啟用</option>
              <option value="inactive">停用</option>
            </select>
          </Field>
        </div>

        <Field label="適用課程">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded bg-violet-50 px-2 py-1 font-medium text-violet-700 dark:bg-violet-900/30 dark:text-violet-200">
              已選 {selectedTemplateCount} 個課程
            </span>
            {selectedTemplateCount > 1 && (
              <span className="text-gray-500 dark:text-gray-400">這些課程會共用同一組價格。</span>
            )}
          </div>
          <div className="max-h-64 overflow-y-auto rounded-lg border border-gray-300 dark:border-gray-600">
            {courseTypes.length === 0 ? (
              <p className="p-3 text-sm text-gray-500 dark:text-gray-400">尚未建立課程類型</p>
            ) : (
              courseTypes.map((courseType) => (
                <div key={courseType.id} className="border-b border-gray-200 last:border-b-0 dark:border-gray-700">
                  <div className="bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-600 dark:bg-gray-900/40 dark:text-gray-400">
                    {courseType.name}
                  </div>
                  {(courseType.templates || []).length === 0 ? (
                    <p className="px-3 py-2 text-xs text-gray-400 dark:text-gray-500">這個類型還沒有課程</p>
                  ) : (
                    courseType.templates.map((template) => (
                      <label
                        key={template.id}
                        className="flex cursor-pointer items-center gap-2 px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-700/40"
                      >
                        <input
                          type="checkbox"
                          checked={form.templates?.includes(template.id) || false}
                          onChange={() => toggleTemplate(template.id)}
                          className="rounded"
                        />
                        <span className="text-sm text-gray-900 dark:text-white">{template.name}</span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{template.duration_hours} 小時</span>
                      </label>
                    ))
                  )}
                </div>
              ))
            )}
          </div>
        </Field>

        <div className="grid gap-3 md:grid-cols-2">
          <Field label="1 人基本價">
            <NumberInput
              value={form.base_price_off_peak}
              onChange={(value) => setForm({ ...form, base_price_off_peak: value })}
              prefix="NT$"
            />
          </Field>
          <Field label="旺季加價">
            <NumberInput
              value={form.peak_season_surcharge}
              onChange={(value) => setForm({ ...form, peak_season_surcharge: value })}
              prefix="NT$"
            />
          </Field>
          <Field label="每增加 1 人">
            <NumberInput
              value={form.additional_person_fee}
              onChange={(value) => setForm({ ...form, additional_person_fee: value })}
              prefix="NT$"
            />
          </Field>
          <Field label="人數上限">
            <NumberInput
              value={form.max_capacity}
              onChange={(value) => setForm({ ...form, max_capacity: value })}
              suffix="人"
            />
          </Field>
        </div>

        <div className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
          <Field label="計價方式">
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => handlePricingModeChange('basic')}
                className={`rounded-lg border px-3 py-2 text-left transition ${
                  pricingMode === 'basic'
                    ? 'border-violet-500 bg-violet-50 text-violet-800 dark:bg-violet-900/30 dark:text-violet-100'
                    : 'border-gray-200 bg-white text-gray-700 hover:border-violet-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200'
                }`}
              >
                <span className="block text-sm font-semibold">基本計價</span>
                <span className="mt-0.5 block text-xs opacity-75">1 人基本價加上每增加 1 人費用</span>
              </button>
              <button
                type="button"
                onClick={() => handlePricingModeChange('tiered')}
                className={`rounded-lg border px-3 py-2 text-left transition ${
                  pricingMode === 'tiered'
                    ? 'border-violet-500 bg-violet-50 text-violet-800 dark:bg-violet-900/30 dark:text-violet-100'
                    : 'border-gray-200 bg-white text-gray-700 hover:border-violet-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200'
                }`}
              >
                <span className="block text-sm font-semibold">人數級距</span>
                <span className="mt-0.5 block text-xs opacity-75">直接設定每個人數區間的總價</span>
              </button>
            </div>
          </Field>

          {pricingMode === 'tiered' && (
            <div className="mt-4 space-y-3 border-t border-gray-200 pt-3 dark:border-gray-700">
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-semibold text-gray-900 dark:text-white">人數級距價格</h4>
                <PrimaryButton onClick={addPeopleTier} small>
                  <Plus size={14} />
                  新增級距
                </PrimaryButton>
              </div>

              {(form.people_tiers || []).length === 0 ? (
                <p className="rounded-lg border border-dashed border-gray-300 p-3 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
                  尚未建立人數級距。
                </p>
              ) : (
                <div className="space-y-2">
                  <div className="hidden grid-cols-[1fr_1fr_1.3fr_72px_40px] gap-2 px-1 text-xs font-medium text-gray-500 dark:text-gray-400 sm:grid">
                    <span>最少人數</span>
                    <span>最多人數</span>
                    <span>區間總價</span>
                    <span>狀態</span>
                    <span />
                  </div>
                  {(form.people_tiers || []).map((tier, index) => (
                    <div key={index} className="grid grid-cols-1 items-end gap-2 rounded-lg border border-gray-200 p-2 dark:border-gray-700 sm:grid-cols-[1fr_1fr_1.3fr_72px_40px]">
                      <Field label="最少">
                        <NumberInput
                          value={tier.min_people}
                          onChange={(value) => updatePeopleTier(index, { min_people: value })}
                          suffix="人"
                        />
                      </Field>
                      <Field label="最多">
                        <NumberInput
                          value={tier.max_people}
                          onChange={(value) => updatePeopleTier(index, { max_people: value })}
                          suffix="人"
                        />
                      </Field>
                      <Field label="價格">
                        <NumberInput
                          value={tier.price}
                          onChange={(value) => updatePeopleTier(index, { price: value })}
                          prefix="NT$"
                        />
                      </Field>
                      <label className="flex h-10 cursor-pointer items-center gap-1 text-sm text-gray-700 dark:text-gray-300">
                        <input
                          type="checkbox"
                          checked={tier.is_active ?? true}
                          onChange={(e) => updatePeopleTier(index, { is_active: e.target.checked })}
                          className="rounded"
                        />
                        啟用
                      </label>
                      <button
                        type="button"
                        onClick={() => removePeopleTier(index)}
                        className="inline-flex h-10 w-10 items-center justify-center rounded text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400"
                        title="刪除級距"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <ModalFooter onClose={onClose} onSave={() => onSave(form)} saveLabel="儲存價格" />
    </ModalFrame>
  )
}

function SectionHeader({
  icon,
  title,
  subtitle,
  action,
}: {
  icon: ReactNode
  title: string
  subtitle?: string
  action: ReactNode
}) {
  return (
    <div className="flex flex-col gap-3 border-b border-gray-200 p-4 dark:border-gray-700 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-2">
        <div className="mt-0.5">{icon}</div>
        <div>
          <h2 className="font-semibold text-gray-900 dark:text-white">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{subtitle}</p>}
        </div>
      </div>
      <div className="flex w-full sm:w-auto">{action}</div>
    </div>
  )
}

function SeasonBadge({ type }: { type: SeasonType }) {
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium sm:ml-2 ${
        type === 'peak'
          ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300'
          : 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
      }`}
    >
      {type === 'peak' ? '旺季' : '淡季'}
    </span>
  )
}

function IconActions({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <div className="flex shrink-0 items-center justify-end gap-1">
      <button
        type="button"
        onClick={onEdit}
        className="rounded p-1.5 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
        title="編輯"
      >
        <Edit size={16} />
      </button>
      <button
        type="button"
        onClick={onDelete}
        className="rounded p-1.5 text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400"
        title="刪除"
      >
        <Trash2 size={16} />
      </button>
    </div>
  )
}

function PrimaryButton({
  children,
  onClick,
  small = false,
}: {
  children: ReactNode
  onClick: () => void
  small?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex w-full items-center justify-center gap-1.5 whitespace-nowrap rounded-lg font-medium text-white hover:opacity-90 sm:w-auto ${
        small ? 'px-2.5 py-1.5 text-xs' : 'px-3 py-1.5 text-sm'
      }`}
      style={{ backgroundColor: PRIMARY }}
    >
      {children}
    </button>
  )
}

function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">
      {children}
    </div>
  )
}

function ModalFrame({
  title,
  onClose,
  maxWidth,
  children,
}: {
  title: string
  onClose: () => void
  maxWidth: string
  children: ReactNode
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className={`flex max-h-[90vh] w-full flex-col rounded-xl bg-white shadow-xl dark:bg-gray-800 ${maxWidth}`}>
        <div className="flex items-center justify-between border-b border-gray-200 p-4 dark:border-gray-700">
          <h3 className="font-semibold text-gray-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="p-1 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

function ModalFooter({
  onClose,
  onSave,
  saveLabel,
}: {
  onClose: () => void
  onSave: () => void
  saveLabel: string
}) {
  return (
    <div className="flex justify-end gap-2 border-t border-gray-200 p-4 dark:border-gray-700">
      <button
        type="button"
        onClick={onClose}
        className="rounded-lg px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
      >
        取消
      </button>
      <button
        type="button"
        onClick={onSave}
        className="rounded-lg px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
        style={{ backgroundColor: PRIMARY }}
      >
        {saveLabel}
      </button>
    </div>
  )
}

const inputClass = 'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">{label}</label>
      {children}
    </div>
  )
}

function NumberInput({
  value,
  onChange,
  prefix,
  suffix,
}: {
  value: number | undefined
  onChange: (value: number) => void
  prefix?: string
  suffix?: string
}) {
  return (
    <div className="relative">
      {prefix && (
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs text-gray-500 dark:text-gray-400">
          {prefix}
        </span>
      )}
      <input
        type="number"
        min={0}
        value={value ?? 0}
        onChange={(e) => onChange(Number(e.target.value) || 0)}
        className={`w-full rounded-lg border border-gray-300 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white ${
          prefix ? 'pl-12' : 'pl-3'
        } ${suffix ? 'pr-10' : 'pr-3'}`}
      />
      {suffix && (
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-500 dark:text-gray-400">
          {suffix}
        </span>
      )}
    </div>
  )
}
