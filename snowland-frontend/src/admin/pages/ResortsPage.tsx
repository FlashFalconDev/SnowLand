/**
 * 雪場管理（接 API）
 */
import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Plus, Edit, Trash2, X, MapPin, DollarSign, Clock, Loader2, AlertCircle } from 'lucide-react'
import { useNotification } from '../context'
import {
  fetchResorts, createResort, updateResort, deleteResort,
  type Resort, type ResortWriteData, type FeeType, type ResortFee, type EquipmentPricingTier, type EquipmentRentalItem, type EquipmentAssistanceTimeSlot,
  type EquipmentOption, type LessonDuration, type SessionPeriod, type DayType,
} from '../api/resorts'
import { fetchCourseTemplates, type CourseTemplate } from '../api/courses'

const PRIMARY = '#8b5cf6'
const QUERY_KEY = ['admin', 'resorts']

const EQUIPMENT_SLOT_OPTIONS: { value: EquipmentOption; label: string }[] = [
  { value: 'purchaseAssistanceTime', label: '加購協助時間' },
  { value: 'assistDuringCourse', label: '課程時間內協助' },
  { value: 'rentWithoutyourself', label: '自行租借不須協助' },
  { value: 'ownWithoutAssistance', label: '自備裝備不須協助' },
]

const LESSON_DURATION_OPTIONS: { value: LessonDuration; label: string }[] = [
  { value: 'any', label: '不限' },
  { value: 'full_day', label: '全天' },
  { value: 'half_day', label: '半天' },
]

const SESSION_PERIOD_OPTIONS: { value: SessionPeriod; label: string }[] = [
  { value: 'any', label: '不限' },
  { value: 'all_day', label: '全天課' },
  { value: 'morning', label: '上午課' },
  { value: 'afternoon', label: '下午課' },
]

const DAY_TYPE_OPTIONS: { value: DayType; label: string }[] = [
  { value: 'same_day', label: '當天' },
  { value: 'previous_day', label: '前一日' },
]

const FEE_TYPE_GROUPS: { group: string; types: { value: FeeType; label: string }[] }[] = [
  { group: '教練費', types: [
    { value: 'coach_director', label: '校長 / 總監' },
    { value: 'coach_lv2', label: 'Lv2 教練' },
    { value: 'coach_general', label: '一般教練' },
  ]},
  { group: '語言加成', types: [
    { value: 'language_zh', label: '中文教學' },
    { value: 'language_en', label: '英文教學' },
    { value: 'language_yue', label: '粵語教學' },
  ]},
]

const FEE_LABELS = new Map(FEE_TYPE_GROUPS.flatMap((group) => group.types.map((type) => [type.value, type.label])))

function getFeeLabel(type: FeeType) {
  if (type === 'equipment_1to3') return '1-3 人租借'
  if (type === 'equipment_4to6') return '4-6 人租借'
  return FEE_LABELS.get(type) || type
}

function flattenApiError(value: unknown): string {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(flattenApiError).filter(Boolean).join('、')
  if (typeof value === 'object') {
    const data = value as Record<string, unknown>
    const direct = flattenApiError(data.msg || data.detail || data.error)
    if (direct) return direct
    return Object.entries(data)
      .filter(([key]) => key !== 'code' && key !== 'data')
      .map(([key, item]) => {
        const message = flattenApiError(item)
        return message ? `${key}: ${message}` : ''
      })
      .filter(Boolean)
      .join('、')
  }
  return ''
}

function getApiErrorMessage(error: unknown, fallback: string) {
  const responseData = (error as { response?: { data?: unknown } })?.response?.data
  return flattenApiError(responseData) || (error as { message?: string })?.message || fallback
}

function makeRentalItemCode(name: string, index: number) {
  const normalized = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return normalized || `rental_item_${index + 1}`
}

function makeTimeSlotLabel(startTime?: string | null, endTime?: string | null) {
  if (startTime && endTime) return `${startTime} - ${endTime}`
  return startTime || endTime || ''
}

function uniqueArray<T extends string | number>(values: T[]) {
  return Array.from(new Set(values))
}

function normalizeNumberIds(values: unknown) {
  return Array.isArray(values) ? uniqueArray(values.map(Number).filter(Boolean)).sort((a, b) => a - b) : []
}

function getSlotValues<T extends string>(
  slot: EquipmentAssistanceTimeSlot,
  pluralKey: keyof EquipmentAssistanceTimeSlot,
  singleKey: keyof EquipmentAssistanceTimeSlot,
  fallback: T
): T[] {
  const plural = slot[pluralKey]
  if (Array.isArray(plural) && plural.length > 0) return uniqueArray(plural as T[])
  const single = slot[singleKey]
  return [((typeof single === 'string' && single) ? single : fallback) as T]
}

function groupEquipmentTimeSlots(slots: EquipmentAssistanceTimeSlot[] | undefined) {
  const grouped = new Map<string, EquipmentAssistanceTimeSlot>()
  for (const slot of slots || []) {
    const courseTemplateIds = normalizeNumberIds(slot.course_template_ids)
    const key = JSON.stringify({
      label: slot.label || '',
      start_time: slot.start_time || null,
      end_time: slot.end_time || null,
      is_active: slot.is_active ?? true,
      description: slot.description || '',
      course_template_ids: courseTemplateIds,
    })
    const existing = grouped.get(key)
    if (existing) {
      existing.equipment_options = uniqueArray([
        ...(existing.equipment_options || []),
        slot.equipment_option || 'purchaseAssistanceTime',
      ])
      existing.lesson_durations = uniqueArray([
        ...(existing.lesson_durations || []),
        slot.lesson_duration || 'any',
      ])
      existing.session_periods = uniqueArray([
        ...(existing.session_periods || []),
        slot.session_period || 'any',
      ])
      existing.day_types = uniqueArray([
        ...(existing.day_types || []),
        slot.day_type || 'same_day',
      ])
      continue
    }
    grouped.set(key, {
      ...slot,
      course_template_ids: courseTemplateIds,
      equipment_options: [slot.equipment_option || 'purchaseAssistanceTime'],
      lesson_durations: [slot.lesson_duration || 'any'],
      session_periods: [slot.session_period || 'any'],
      day_types: [slot.day_type || 'same_day'],
    })
  }
  return Array.from(grouped.values())
}

function normalizeResortForEditing(resort: Resort): Resort {
  return {
    ...resort,
    equipment_time_slots: groupEquipmentTimeSlots(resort.equipment_time_slots),
  }
}

function sanitizeEquipmentTimeSlotTemplateIds(
  slots: EquipmentAssistanceTimeSlot[] | undefined,
  resortId: number,
  courseTemplates: CourseTemplate[]
) {
  const validTemplateIds = new Set(
    courseTemplates
      .filter((template) => (template.resorts || []).includes(resortId))
      .map((template) => template.id)
  )

  return (slots || []).map((slot) => ({
    ...slot,
    course_template_ids: (slot.course_template_ids || [])
      .map(Number)
      .filter((id) => validTemplateIds.has(id)),
  }))
}

function prepareEquipmentTiers(tiers: EquipmentPricingTier[] | undefined): { tiers: EquipmentPricingTier[]; error?: string } {
  const prepared = (tiers || [])
    .map((tier) => ({
      min_people: Number(tier.min_people) || 0,
      max_people: Number(tier.max_people) || 0,
      price: Number(tier.price) || 0,
      is_active: tier.is_active ?? true,
      description: tier.description || '',
    }))
    .filter((tier) => tier.min_people > 0 || tier.max_people > 0 || tier.price > 0)

  const activeRanges: { start: number; end: number }[] = []
  for (const tier of prepared) {
    if (tier.min_people < 1 || tier.max_people < tier.min_people) {
      return { tiers: [], error: '請確認裝備租借人數級距' }
    }
    if (tier.price < 0) {
      return { tiers: [], error: '裝備租借價格不能小於 0' }
    }
    if (!tier.is_active) continue
    for (const range of activeRanges) {
      if (tier.min_people <= range.end && tier.max_people >= range.start) {
        return { tiers: [], error: '啟用中的人數範圍不能重疊' }
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
      description: tier.description,
    })),
  }
}

function prepareEquipmentRentalItems(items: EquipmentRentalItem[] | undefined): { items: EquipmentRentalItem[]; error?: string } {
  const prepared = (items || [])
    .map((item, index) => {
      const name = (item.name || '').trim()
      return {
        code: (item.code || '').trim() || makeRentalItemCode(name, index),
        name,
        daily_price: Number(item.daily_price) || 0,
        additional_day_price: Number(item.additional_day_price) || 0,
        is_active: item.is_active ?? true,
        description: item.description || '',
      }
    })
    .filter((item) => item.code || item.name || item.daily_price > 0 || item.additional_day_price > 0 || item.description)

  const activeCodes = new Set<string>()
  for (const item of prepared) {
    if (!item.name) return { items: [], error: '請填野雪裝備品項名稱' }
    if (item.daily_price < 0 || item.additional_day_price < 0) return { items: [], error: '野雪裝備價格不能小於 0' }
    if (!item.is_active) continue
    const key = item.code.toLowerCase()
    if (activeCodes.has(key)) return { items: [], error: '野雪裝備品項不能重複' }
    activeCodes.add(key)
  }

  return {
    items: prepared.map((item, index) => ({
      ...item,
      display_order: index,
    })),
  }
}

function prepareEquipmentTimeSlots(slots: EquipmentAssistanceTimeSlot[] | undefined): { slots: EquipmentAssistanceTimeSlot[]; error?: string } {
  const preparedRules = (slots || [])
    .map((slot) => {
      const startTime = slot.start_time || null
      const endTime = slot.end_time || null
      return {
        equipment_options: getSlotValues<EquipmentOption>(slot, 'equipment_options', 'equipment_option', 'purchaseAssistanceTime'),
        lesson_durations: getSlotValues<LessonDuration>(slot, 'lesson_durations', 'lesson_duration', 'any'),
        session_periods: getSlotValues<SessionPeriod>(slot, 'session_periods', 'session_period', 'any'),
        day_types: getSlotValues<DayType>(slot, 'day_types', 'day_type', 'same_day'),
        course_template_ids: (slot.course_template_ids || []).map(Number).filter(Boolean),
        label: (slot.label || '').trim() || makeTimeSlotLabel(startTime, endTime),
        start_time: startTime,
        end_time: endTime,
        is_active: slot.is_active ?? true,
        description: slot.description || '',
      }
    })
    .filter((slot) => slot.label || slot.start_time || slot.end_time || slot.description || slot.course_template_ids.length > 0)

  const prepared: EquipmentAssistanceTimeSlot[] = []
  for (const rule of preparedRules) {
    for (const equipmentOption of rule.equipment_options) {
      for (const lessonDuration of rule.lesson_durations) {
        for (const sessionPeriod of rule.session_periods) {
          for (const dayType of rule.day_types) {
            prepared.push({
              equipment_option: equipmentOption,
              lesson_duration: lessonDuration,
              session_period: sessionPeriod,
              day_type: dayType,
              course_template_ids: rule.course_template_ids,
              label: rule.label,
              start_time: rule.start_time,
              end_time: rule.end_time,
              is_active: rule.is_active,
              description: rule.description,
            })
          }
        }
      }
    }
  }

  const labels = new Set<string>()
  for (const slot of prepared) {
    if (!slot.label) return { slots: [], error: '請填可選協助時間的名稱或時間' }
    if (!slot.is_active) continue
    const key = [
      slot.equipment_option,
      slot.lesson_duration,
      slot.session_period,
      slot.day_type,
      slot.label.toLowerCase(),
    ].join('|')
    if (labels.has(key)) return { slots: [], error: '啟用中的可選協助時間不能重複' }
    labels.add(key)
  }

  return {
    slots: prepared.map((slot, index) => ({
      ...slot,
      display_order: index,
    })),
  }
}

export default function ResortsPage() {
  const notify = useNotification()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)

  const { data: resorts = [], isLoading, error } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchResorts,
  })
  const { data: courseTemplates = [] } = useQuery({
    queryKey: ['admin', 'course-templates'],
    queryFn: fetchCourseTemplates,
  })

  const createMutation = useMutation({
    mutationFn: (data: ResortWriteData) => createResort(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: QUERY_KEY }); notify.success('雪場建立成功'); setCreating(false) },
    onError: (e: unknown) => notify.error(getApiErrorMessage(e, '建立失敗')),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ResortWriteData }) => updateResort(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: QUERY_KEY }); notify.success('雪場已更新'); setEditingId(null) },
    onError: (e: unknown) => notify.error(getApiErrorMessage(e, '更新失敗')),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteResort(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: QUERY_KEY }); notify.success('雪場已刪除') },
    onError: (e: unknown) => notify.error(getApiErrorMessage(e, '刪除失敗')),
  })

  const filtered = resorts.filter((r) => !search || r.display_name.includes(search) || r.name.includes(search))

  const editing = creating
    ? ({ id: 0, name: '', display_name: '', auto_scheduling_enabled: true, fees: [], equipment_tiers: [], equipment_rental_items: [], equipment_time_slots: [] } as Resort)
    : editingId ? resorts.find((r) => r.id === editingId) || null : null

  const handleSave = (data: Resort) => {
    const tierResult = prepareEquipmentTiers(data.equipment_tiers)
    if (tierResult.error) { notify.error(tierResult.error); return }
    const rentalItemResult = prepareEquipmentRentalItems(data.equipment_rental_items)
    if (rentalItemResult.error) { notify.error(rentalItemResult.error); return }
    const slotResult = prepareEquipmentTimeSlots(
      sanitizeEquipmentTimeSlotTemplateIds(data.equipment_time_slots, data.id, courseTemplates)
    )
    if (slotResult.error) { notify.error(slotResult.error); return }

    const writeData: ResortWriteData = {
      name: data.name,
      display_name: data.display_name,
      auto_scheduling_enabled: data.auto_scheduling_enabled,
      fees_input: data.fees,
      equipment_tiers_input: tierResult.tiers,
      equipment_rental_items_input: rentalItemResult.items,
      equipment_time_slots_input: slotResult.slots,
    }
    if (creating) createMutation.mutate(writeData)
    else if (editingId) updateMutation.mutate({ id: editingId, data: writeData })
  }

  const handleDelete = (id: number) => {
    if (!confirm('確定要刪除此雪場？')) return
    deleteMutation.mutate(id)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">雪場管理</h1>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 flex items-center gap-2"
          style={{ backgroundColor: PRIMARY }}
        >
          <Plus size={16} />新增雪場
        </button>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="搜尋雪場名稱..."
            className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} />
        </div>
      ) : error ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
          <p className="text-sm text-red-600 dark:text-red-400">載入失敗</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((resort) => (
            <div key={resort.id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden hover:shadow-md transition-shadow">
              <div className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900/50 rounded-lg flex items-center justify-center">
                      <MapPin size={20} className="text-blue-600 dark:text-blue-400" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900 dark:text-white">{resort.display_name}</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400 font-mono">/{resort.name}</p>
                    </div>
                  </div>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full whitespace-nowrap ${
                    resort.auto_scheduling_enabled
                      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                  }`}>
                    {resort.auto_scheduling_enabled ? '自動排課' : '手動'}
                  </span>
                </div>

                <div className="space-y-2 mb-4">
                  {resort.fees.length === 0 && (resort.equipment_tiers || []).length === 0 && (resort.equipment_rental_items || []).length === 0 ? (
                    <p className="text-xs text-gray-400">尚未設定費用</p>
                  ) : resort.fees.slice(0, 3).map((fee, i) => {
                    const label = getFeeLabel(fee.fee_type)
                    return (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-300">{label}</span>
                        <span className="font-medium text-gray-900 dark:text-white">NT$ {fee.price.toLocaleString()}</span>
                      </div>
                    )
                  })}
                  {resort.fees.length > 3 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">+ 其他 {resort.fees.length - 3} 項費用</p>
                  )}
                  {(resort.equipment_tiers || []).filter((tier) => tier.is_active).slice(0, 2).map((tier) => (
                    <div key={`equipment-${tier.id || `${tier.min_people}-${tier.max_people}`}`} className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-300">裝備 {tier.min_people}-{tier.max_people} 人</span>
                      <span className="font-medium text-gray-900 dark:text-white">NT$ {tier.price.toLocaleString()}</span>
                    </div>
                  ))}
                  {(resort.equipment_tiers || []).filter((tier) => tier.is_active).length > 2 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      + 其他 {(resort.equipment_tiers || []).filter((tier) => tier.is_active).length - 2} 個裝備級距
                    </p>
                  )}
                  {(resort.equipment_rental_items || []).filter((item) => item.is_active).slice(0, 2).map((item) => (
                    <div key={`rental-${item.id || item.code}`} className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-300 truncate pr-2">野雪裝備：{item.name}</span>
                      <span className="font-medium text-gray-900 dark:text-white">NT$ {item.daily_price.toLocaleString()}</span>
                    </div>
                  ))}
                  {(resort.equipment_rental_items || []).filter((item) => item.is_active).length > 2 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      + 其他 {(resort.equipment_rental_items || []).filter((item) => item.is_active).length - 2} 個租借品項
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 pt-3 border-t border-gray-100 dark:border-gray-700">
                  <button onClick={() => setEditingId(resort.id)} className="flex-1 px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center justify-center gap-1">
                    <Edit size={14} />編輯
                  </button>
                  <button onClick={() => handleDelete(resort.id)} className="p-1.5 text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
          {filtered.length === 0 && !isLoading && (
            <div className="col-span-full text-center py-16 text-gray-500 dark:text-gray-400">
              {resorts.length === 0 ? '尚未建立任何雪場' : '沒有符合條件的雪場'}
            </div>
          )}
        </div>
      )}

      {editing && (
        <ResortEditDrawer
          resort={editing} isCreating={creating}
          courseTemplates={courseTemplates}
          isSaving={createMutation.isPending || updateMutation.isPending}
          onClose={() => { setEditingId(null); setCreating(false) }}
          onSave={handleSave}
        />
      )}
    </div>
  )
}

function ResortEditDrawer({ resort, isCreating, courseTemplates, isSaving, onClose, onSave }: {
  resort: Resort; isCreating: boolean; isSaving: boolean
  courseTemplates: CourseTemplate[]
  onClose: () => void; onSave: (data: Resort) => void
}) {
  const [form, setForm] = useState<Resort>(() => normalizeResortForEditing(resort))
  useEffect(() => {
    setForm(normalizeResortForEditing(resort))
  }, [resort.id])
  const availableCourseTemplates = courseTemplates.filter((template) => (template.resorts || []).includes(form.id))

  const updateFee = (type: FeeType, price: number) => {
    setForm((f) => {
      const exists = f.fees.find((x) => x.fee_type === type)
      if (price === 0 || !price) return { ...f, fees: f.fees.filter((x) => x.fee_type !== type) }
      if (exists) return { ...f, fees: f.fees.map((x) => (x.fee_type === type ? { ...x, price } : x)) }
      return { ...f, fees: [...f.fees, { fee_type: type, price, is_active: true } as ResortFee] }
    })
  }

  const getFeePrice = (type: FeeType) => form.fees.find((x) => x.fee_type === type)?.price || 0

  const addBackcountryRentalPresets = () => {
    const presets: EquipmentRentalItem[] = [
      {
        code: 'avalanche_safety',
        name: 'Avalanche Safety 雪崩三寶',
        daily_price: 1000,
        additional_day_price: 800,
        is_active: true,
        description: 'Transceiver / Shovel / Probe',
      },
      {
        code: 'snowshoe_pole',
        name: 'Snowshoe + pole 大腳雪鞋 + 伸縮雪杖',
        daily_price: 600,
        additional_day_price: 400,
        is_active: true,
        description: '',
      },
      {
        code: 'bc_backpack',
        name: 'BC Backpack 背包',
        daily_price: 300,
        additional_day_price: 200,
        is_active: true,
        description: '',
      },
    ]
    const current = form.equipment_rental_items || []
    const existingCodes = new Set(current.map((item) => item.code))
    const merged = [
      ...current,
      ...presets.filter((item) => !existingCodes.has(item.code)),
    ].map((item, index) => ({ ...item, display_order: index }))
    setForm({ ...form, equipment_rental_items: merged })
  }

  const addEquipmentRentalItem = () => {
    const cur = form.equipment_rental_items || []
    setForm({
      ...form,
      equipment_rental_items: [
        ...cur,
        {
          code: '',
          name: '',
          daily_price: 0,
          additional_day_price: 0,
          is_active: true,
          display_order: cur.length,
          description: '',
        },
      ],
    })
  }

  const updateEquipmentRentalItem = (index: number, patch: Partial<EquipmentRentalItem>) => {
    const cur = form.equipment_rental_items || []
    setForm({
      ...form,
      equipment_rental_items: cur.map((item, i) => (i === index ? { ...item, ...patch } : item)),
    })
  }

  const removeEquipmentRentalItem = (index: number) => {
    const cur = form.equipment_rental_items || []
    setForm({ ...form, equipment_rental_items: cur.filter((_, i) => i !== index) })
  }

  const addEquipmentTier = () => {
    const cur = form.equipment_tiers || []
    const last = cur[cur.length - 1]
    const nextMin = last ? last.max_people + 1 : 1
    setForm({
      ...form,
      equipment_tiers: [
        ...cur,
        {
          min_people: nextMin,
          max_people: nextMin,
          price: 0,
          is_active: true,
          display_order: cur.length,
          description: '',
        },
      ],
    })
  }

  const updateEquipmentTier = (index: number, patch: Partial<EquipmentPricingTier>) => {
    const cur = form.equipment_tiers || []
    setForm({
      ...form,
      equipment_tiers: cur.map((tier, i) => (i === index ? { ...tier, ...patch } : tier)),
    })
  }

  const removeEquipmentTier = (index: number) => {
    const cur = form.equipment_tiers || []
    setForm({ ...form, equipment_tiers: cur.filter((_, i) => i !== index) })
  }

  const addEquipmentTimeSlot = () => {
    const cur = form.equipment_time_slots || []
    setForm({
      ...form,
      equipment_time_slots: [
        ...cur,
        {
          equipment_option: 'purchaseAssistanceTime',
          equipment_options: ['purchaseAssistanceTime'],
          lesson_duration: 'any',
          lesson_durations: ['any'],
          session_period: 'any',
          session_periods: ['any'],
          day_type: 'same_day',
          day_types: ['same_day'],
          course_template_ids: [],
          label: '',
          start_time: null,
          end_time: null,
          is_active: true,
          display_order: cur.length,
          description: '',
        },
      ],
    })
  }

  const updateEquipmentTimeSlot = (index: number, patch: Partial<EquipmentAssistanceTimeSlot>) => {
    const cur = form.equipment_time_slots || []
    setForm({
      ...form,
      equipment_time_slots: cur.map((slot, i) => (i === index ? { ...slot, ...patch } : slot)),
    })
  }

  const toggleEquipmentTimeSlotValue = <T extends string>(
    index: number,
    field: keyof EquipmentAssistanceTimeSlot,
    value: T,
    fallback: T
  ) => {
    const cur = form.equipment_time_slots || []
    const slot = cur[index]
    if (!slot) return
    const current = getSlotValues<T>(slot, field, field, fallback)
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value]
    updateEquipmentTimeSlot(index, { [field]: next.length > 0 ? next : [value] } as Partial<EquipmentAssistanceTimeSlot>)
  }

  const removeEquipmentTimeSlot = (index: number) => {
    const cur = form.equipment_time_slots || []
    setForm({ ...form, equipment_time_slots: cur.filter((_, i) => i !== index) })
  }

  const toggleEquipmentTimeSlotTemplate = (index: number, templateId: number) => {
    const cur = form.equipment_time_slots || []
    const slot = cur[index]
    if (!slot) return
    const ids = new Set((slot.course_template_ids || []).map(Number))
    if (ids.has(templateId)) ids.delete(templateId)
    else ids.add(templateId)
    updateEquipmentTimeSlot(index, { course_template_ids: Array.from(ids) })
  }

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 animate-fadeIn" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white dark:bg-gray-800 shadow-2xl flex flex-col animate-slideIn">
        <div className="px-6 py-4 flex items-center justify-between text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
          <h2 className="text-lg font-semibold">{isCreating ? '新增雪場' : `編輯：${resort.display_name}`}</h2>
          <button onClick={onClose} className="text-white/80 hover:text-white"><X size={20} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">基本資料</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">系統代號 <span className="text-red-500">*</span></label>
                <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="tomamu"
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm font-mono dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">顯示名稱 <span className="text-red-500">*</span></label>
                <input type="text" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="星野 Tomamu"
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
              </div>
            </div>
            <label className="flex items-center gap-3 mt-4 cursor-pointer">
              <input type="checkbox" checked={form.auto_scheduling_enabled} onChange={(e) => setForm({ ...form, auto_scheduling_enabled: e.target.checked })}
                className="w-4 h-4 rounded border-gray-300" style={{ accentColor: PRIMARY }} />
              <span className="text-sm text-gray-700 dark:text-gray-300">啟用自動排課</span>
            </label>
          </section>

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <DollarSign size={16} style={{ color: PRIMARY }} />費用設定（單位：NT$）
            </h3>
            {FEE_TYPE_GROUPS.map((group) => (
              <div key={group.group} className="mb-5">
                <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">{group.group}</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {group.types.map((t) => (
                    <div key={t.value} className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                      <label className="text-sm text-gray-700 dark:text-gray-300 flex-1">{t.label}</label>
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-gray-500">NT$</span>
                        <input type="number" value={getFeePrice(t.value) || ''} onChange={(e) => updateFee(t.value, Number(e.target.value))}
                          placeholder="0"
                          className="w-24 px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm text-right dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </section>

          <section>
            <div className="flex items-center justify-between gap-3 mb-3">
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <DollarSign size={16} style={{ color: PRIMARY }} />野雪裝備租借品項
                </h3>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">只填客人看得懂的名稱與價格，其他後台欄位系統會自動處理。</p>
              </div>
              <div className="flex flex-wrap gap-2 justify-end">
                <button
                  type="button"
                  onClick={addBackcountryRentalPresets}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  套用預設品項
                </button>
                <button
                  type="button"
                  onClick={addEquipmentRentalItem}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-white rounded-lg hover:opacity-90"
                  style={{ backgroundColor: PRIMARY }}
                >
                  <Plus size={14} />
                  新增裝備
                </button>
              </div>
            </div>

            {(form.equipment_rental_items || []).length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400">還沒有租借品項，可直接套用預設。</p>
            ) : (
              <div className="space-y-3">
                {(form.equipment_rental_items || []).map((item, index) => (
                  <div key={index} className="grid grid-cols-1 sm:grid-cols-[1.6fr_1fr_1fr_auto_auto] gap-2 items-end p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">品項名稱</label>
                      <input
                        type="text"
                        value={item.name || ''}
                        onChange={(e) => updateEquipmentRentalItem(index, { name: e.target.value })}
                        placeholder="Avalanche Safety 雪崩三寶"
                        className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">第一天價格</label>
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-gray-500">NT$</span>
                        <input
                          type="number"
                          min={0}
                          value={item.daily_price || ''}
                          onChange={(e) => updateEquipmentRentalItem(index, { daily_price: Number(e.target.value) || 0 })}
                          className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm text-right dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">第二天起/天</label>
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-gray-500">NT$</span>
                        <input
                          type="number"
                          min={0}
                          value={item.additional_day_price || ''}
                          onChange={(e) => updateEquipmentRentalItem(index, { additional_day_price: Number(e.target.value) || 0 })}
                          className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm text-right dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                        />
                      </div>
                    </div>
                    <label className="flex items-center gap-1 h-8 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={item.is_active ?? true}
                        onChange={(e) => updateEquipmentRentalItem(index, { is_active: e.target.checked })}
                        className="rounded"
                      />
                      啟用
                    </label>
                    <button
                      type="button"
                      onClick={() => removeEquipmentRentalItem(index)}
                      className="h-8 w-8 inline-flex items-center justify-center text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 rounded"
                      title="刪除品項"
                    >
                      <Trash2 size={16} />
                    </button>
                    <div className="sm:col-span-5">
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">備註（可不填）</label>
                      <input
                        type="text"
                        value={item.description || ''}
                        onChange={(e) => updateEquipmentRentalItem(index, { description: e.target.value })}
                        placeholder="Transceiver / Shovel / Probe"
                        className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section>
            <div className="flex items-center justify-between gap-3 mb-3">
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <DollarSign size={16} style={{ color: PRIMARY }} />租借陪同協助費
                </h3>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">這裡是教練陪客人租裝備的服務費，依人數收費。</p>
              </div>
              <button
                type="button"
                onClick={addEquipmentTier}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-white rounded-lg hover:opacity-90"
                style={{ backgroundColor: PRIMARY }}
              >
                <Plus size={14} />
                新增人數價格
              </button>
            </div>

            {(form.equipment_tiers || []).length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400">尚未設定協助費。</p>
            ) : (
              <div className="space-y-3">
                {(form.equipment_tiers || []).map((tier, index) => (
                  <div key={index} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_1.3fr_auto_auto] gap-2 items-end p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">最少人數</label>
                      <input
                        type="number"
                        min={1}
                        value={tier.min_people || ''}
                        onChange={(e) => updateEquipmentTier(index, { min_people: Number(e.target.value) || 0 })}
                        className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm text-right dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">最多人數</label>
                      <input
                        type="number"
                        min={1}
                        value={tier.max_people || ''}
                        onChange={(e) => updateEquipmentTier(index, { max_people: Number(e.target.value) || 0 })}
                        className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm text-right dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">協助費</label>
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-gray-500">NT$</span>
                        <input
                          type="number"
                          min={0}
                          value={tier.price || ''}
                          onChange={(e) => updateEquipmentTier(index, { price: Number(e.target.value) || 0 })}
                          className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm text-right dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                        />
                      </div>
                    </div>
                    <label className="flex items-center gap-1 h-8 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={tier.is_active ?? true}
                        onChange={(e) => updateEquipmentTier(index, { is_active: e.target.checked })}
                        className="rounded"
                      />
                      啟用
                    </label>
                    <button
                      type="button"
                      onClick={() => removeEquipmentTier(index)}
                      className="h-8 w-8 inline-flex items-center justify-center text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 rounded"
                      title="移除級距"
                    >
                      <Trash2 size={16} />
                    </button>
                    <div className="sm:col-span-5">
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">備註（可不填）</label>
                      <input
                        type="text"
                        value={tier.description || ''}
                        onChange={(e) => updateEquipmentTier(index, { description: e.target.value })}
                        placeholder="例：加購租借陪同時使用"
                        className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section>
            <div className="flex items-center justify-between gap-3 mb-3">
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <Clock size={16} style={{ color: PRIMARY }} />可選協助時間
                </h3>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">客人選「加購協助」時，只會看到這裡開放的時間。</p>
              </div>
              <button
                type="button"
                onClick={addEquipmentTimeSlot}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-white rounded-lg hover:opacity-90"
                style={{ backgroundColor: PRIMARY }}
              >
                <Plus size={14} />
                新增時間
              </button>
            </div>

            {(form.equipment_time_slots || []).length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400">尚未設定可選協助時間。</p>
            ) : (
              <div className="space-y-3">
                {(form.equipment_time_slots || []).map((slot, index) => (
                  <div key={index} className="grid grid-cols-1 sm:grid-cols-[1.2fr_1fr_1fr_1fr_auto_auto] gap-2 items-end p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">協助日期</label>
                      <div className="flex flex-wrap gap-1">
                        {DAY_TYPE_OPTIONS.map((opt) => {
                          const checked = getSlotValues<DayType>(slot, 'day_types', 'day_type', 'same_day').includes(opt.value)
                          return (
                            <label
                              key={opt.value}
                              className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs cursor-pointer ${
                                checked
                                  ? 'border-[#8b5cf6] bg-[#8b5cf6]/10 text-[#7c3aed] dark:text-[#c4b5fd]'
                                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300'
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => toggleEquipmentTimeSlotValue<DayType>(index, 'day_types', opt.value, 'same_day')}
                                className="sr-only"
                              />
                              {opt.label}
                            </label>
                          )
                        })}
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">開始時間</label>
                      <input
                        type="time"
                        value={slot.start_time || ''}
                        onChange={(e) => updateEquipmentTimeSlot(index, { start_time: e.target.value || null })}
                        className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">結束時間</label>
                      <input
                        type="time"
                        value={slot.end_time || ''}
                        onChange={(e) => updateEquipmentTimeSlot(index, { end_time: e.target.value || null })}
                        className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">按鈕文字</label>
                      <input
                        type="text"
                        value={slot.label || ''}
                        onChange={(e) => updateEquipmentTimeSlot(index, { label: e.target.value })}
                        placeholder={makeTimeSlotLabel(slot.start_time, slot.end_time) || '可不填'}
                        className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                      />
                    </div>
                    <label className="flex items-center gap-1 h-8 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={slot.is_active ?? true}
                        onChange={(e) => updateEquipmentTimeSlot(index, { is_active: e.target.checked })}
                        className="rounded"
                      />
                      啟用
                    </label>
                    <button
                      type="button"
                      onClick={() => removeEquipmentTimeSlot(index)}
                      className="h-8 w-8 inline-flex items-center justify-center text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 rounded"
                      title="移除時段"
                    >
                      <Trash2 size={16} />
                    </button>
                    <details className="sm:col-span-6 rounded-lg border border-gray-200 dark:border-gray-600 bg-white/70 dark:bg-gray-800/70">
                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-gray-600 dark:text-gray-300">
                        進階限制（通常不用改）
                      </summary>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 p-3 border-t border-gray-200 dark:border-gray-600">
                        <div>
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">適用方案</label>
                          <div className="flex flex-wrap gap-1">
                            {EQUIPMENT_SLOT_OPTIONS.map((opt) => {
                              const checked = getSlotValues<EquipmentOption>(slot, 'equipment_options', 'equipment_option', 'purchaseAssistanceTime').includes(opt.value)
                              return (
                                <label
                                  key={opt.value}
                                  className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs cursor-pointer ${
                                    checked
                                      ? 'border-[#8b5cf6] bg-[#8b5cf6]/10 text-[#7c3aed] dark:text-[#c4b5fd]'
                                      : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300'
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => toggleEquipmentTimeSlotValue<EquipmentOption>(index, 'equipment_options', opt.value, 'purchaseAssistanceTime')}
                                    className="sr-only"
                                  />
                                  {opt.label}
                                </label>
                              )
                            })}
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">全天/半天</label>
                          <div className="flex flex-wrap gap-1">
                            {LESSON_DURATION_OPTIONS.map((opt) => {
                              const checked = getSlotValues<LessonDuration>(slot, 'lesson_durations', 'lesson_duration', 'any').includes(opt.value)
                              return (
                                <label
                                  key={opt.value}
                                  className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs cursor-pointer ${
                                    checked
                                      ? 'border-[#8b5cf6] bg-[#8b5cf6]/10 text-[#7c3aed] dark:text-[#c4b5fd]'
                                      : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300'
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => toggleEquipmentTimeSlotValue<LessonDuration>(index, 'lesson_durations', opt.value, 'any')}
                                    className="sr-only"
                                  />
                                  {opt.label}
                                </label>
                              )
                            })}
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">上午/下午</label>
                          <div className="flex flex-wrap gap-1">
                            {SESSION_PERIOD_OPTIONS.map((opt) => {
                              const checked = getSlotValues<SessionPeriod>(slot, 'session_periods', 'session_period', 'any').includes(opt.value)
                              return (
                                <label
                                  key={opt.value}
                                  className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs cursor-pointer ${
                                    checked
                                      ? 'border-[#8b5cf6] bg-[#8b5cf6]/10 text-[#7c3aed] dark:text-[#c4b5fd]'
                                      : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300'
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => toggleEquipmentTimeSlotValue<SessionPeriod>(index, 'session_periods', opt.value, 'any')}
                                    className="sr-only"
                                  />
                                  {opt.label}
                                </label>
                              )
                            })}
                          </div>
                        </div>
                        <div className="sm:col-span-3">
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">
                            只給特定課程使用（不勾代表全部課程都可用）
                          </label>
                          {availableCourseTemplates.length === 0 ? (
                            <p className="text-xs text-gray-500 dark:text-gray-400">此雪場目前沒有可綁定的課程項目</p>
                          ) : (
                            <div className="max-h-28 overflow-y-auto rounded border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 p-2">
                              {availableCourseTemplates.map((template) => (
                                <label key={template.id} className="mr-3 mb-1 inline-flex items-center gap-1 text-xs text-gray-700 dark:text-gray-300">
                                  <input
                                    type="checkbox"
                                    checked={(slot.course_template_ids || []).map(Number).includes(template.id)}
                                    onChange={() => toggleEquipmentTimeSlotTemplate(index, template.id)}
                                    className="rounded"
                                  />
                                  {template.course_type_name} {template.name} ({template.duration_hours}H)
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </details>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <button onClick={onClose} disabled={isSaving} className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50">取消</button>
          <button onClick={() => onSave(form)} disabled={isSaving} className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 flex items-center gap-2 disabled:opacity-50" style={{ backgroundColor: PRIMARY }}>
            {isSaving && <Loader2 size={14} className="animate-spin" />}
            {isCreating ? '建立雪場' : '儲存變更'}
          </button>
        </div>
      </div>
    </>
  )
}
