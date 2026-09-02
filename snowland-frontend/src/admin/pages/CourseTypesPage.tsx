/**
 * 課程類型管理（接 API）
 */
import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Edit, Trash2, Clock, Users, Calendar, Loader2, AlertCircle, X, MapPin } from 'lucide-react'
import {
  fetchCourseCategories, type CourseCategory, type CourseTemplate,
  createCategory, updateCategory, deleteCategory,
  createType, updateType, deleteType,
  createTemplate, updateTemplate, deleteTemplate,
  createSession, updateSession, deleteSession,
} from '../api/courses'
import { fetchCoaches as fetchAdminCoaches, type Coach } from '../api/coaches'
import { fetchResorts, type Resort } from '../api/resorts'
import { useNotification } from '../context'
import PromptModal, { type PromptField } from '../components/PromptModal'

const PRIMARY = '#8b5cf6'
const serviceTypeOptions = [
  { value: 'ski', label: '滑雪課程' },
  { value: 'photo', label: '攝影服務' },
]
const serviceTypeLabels: Record<string, string> = {
  ski: '滑雪',
  photo: '攝影',
}
type ServiceFilter = 'all' | 'ski' | 'photo'

const getTemplateCoachRuleText = (template?: CourseTemplate | null) => {
  if (!template) return ''
  const parts = []
  if (template.minimum_coach_price_level) {
    parts.push(template.minimum_coach_price_level_label || `${template.minimum_coach_price_level} 以上`)
  }
  if (template.allowed_coach_names?.length) {
    parts.push(`優先 ${template.allowed_coach_names.length} 位教練`)
  }
  return parts.join('，')
}

export default function CourseTypesPage() {
  const notify = useNotification()
  const qc = useQueryClient()
  const QUERY_KEY = ['admin', 'course-categories']
  const refresh = () => qc.invalidateQueries({ queryKey: QUERY_KEY })

  const { data: categories = [], isLoading, error } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchCourseCategories,
  })

  const { data: allResorts = [] } = useQuery({
    queryKey: ['admin', 'resorts'],
    queryFn: fetchResorts,
  })
  const { data: allCoaches = [] } = useQuery({
    queryKey: ['admin', 'coaches'],
    queryFn: fetchAdminCoaches,
  })

  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null)
  const [selectedTypeId, setSelectedTypeId] = useState<number | null>(null)
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null)
  const [editingTemplate, setEditingTemplate] = useState<CourseTemplate | null>(null)
  const [creatingTemplateForType, setCreatingTemplateForType] = useState<number | null>(null)
  const [serviceFilter, setServiceFilter] = useState<ServiceFilter>('all')

  // 統一的 PromptModal 狀態
  const [modal, setModal] = useState<{
    title: string
    description?: string
    fields: PromptField[]
    onSubmit: (vals: Record<string, string>) => Promise<void>
  } | null>(null)

  // ===== CRUD handlers (用 PromptModal 取代 prompt) =====
  const handleAddCategory = () => {
    setModal({
      title: '新增課程類別',
      fields: [
        { name: 'name', label: '類別名稱', required: true, placeholder: '例如：單板 Snowboard' },
        {
          name: 'service_type',
          label: '服務類型',
          type: 'select',
          defaultValue: serviceFilter === 'all' ? 'ski' : serviceFilter,
          required: true,
          options: serviceTypeOptions,
        },
      ],
      onSubmit: async (vals) => {
        try {
          await createCategory({ name: vals.name.trim(), service_type: vals.service_type as 'ski' | 'photo' })
          notify.success('已新增類別')
          refresh()
          setModal(null)
        } catch (e: any) {
          notify.error(e.response?.data?.msg || '新增失敗')
        }
      },
    })
  }

  const handleEditCategory = (id: number, currentName: string, currentServiceType: 'ski' | 'photo') => {
    setModal({
      title: '編輯類別',
      fields: [
        { name: 'name', label: '類別名稱', required: true, defaultValue: currentName },
        {
          name: 'service_type',
          label: '服務類型',
          type: 'select',
          defaultValue: currentServiceType,
          required: true,
          options: serviceTypeOptions,
        },
      ],
      onSubmit: async (vals) => {
        try {
          await updateCategory(id, { name: vals.name.trim(), service_type: vals.service_type })
          notify.success('已更新')
          refresh()
          setModal(null)
        } catch (e: any) {
          notify.error(e.response?.data?.msg || '更新失敗')
        }
      },
    })
  }

  const handleDeleteCategory = async (id: number, name: string) => {
    if (!confirm(`確定刪除類別「${name}」？所有底下的類型/模板都會一併刪除。`)) return
    try {
      await deleteCategory(id)
      notify.success('已刪除')
      if (selectedCategoryId === id) {
        setSelectedCategoryId(null)
        setSelectedTypeId(null)
        setSelectedTemplateId(null)
      }
      refresh()
    } catch (e: any) {
      notify.error(e.response?.data?.msg || '刪除失敗')
    }
  }

  const handleAddType = (categoryId: number) => {
    setModal({
      title: '新增課程類型',
      fields: [{ name: 'name', label: '類型名稱', required: true, placeholder: '例如：單板課程' }],
      onSubmit: async (vals) => {
        try {
          await createType({ category: categoryId, name: vals.name.trim() })
          notify.success('已新增類型')
          refresh()
          setModal(null)
        } catch (e: any) {
          notify.error(e.response?.data?.msg || '新增失敗')
        }
      },
    })
  }

  const handleEditType = (id: number, currentName: string) => {
    setModal({
      title: '編輯課程類型',
      fields: [{ name: 'name', label: '類型名稱', required: true, defaultValue: currentName }],
      onSubmit: async (vals) => {
        try {
          await updateType(id, { name: vals.name.trim() })
          notify.success('已更新')
          refresh()
          setModal(null)
        } catch (e: any) {
          notify.error(e.response?.data?.msg || '更新失敗')
        }
      },
    })
  }

  const handleDeleteType = async (id: number, name: string) => {
    if (!confirm(`確定刪除類型「${name}」？`)) return
    try {
      await deleteType(id)
      notify.success('已刪除')
      if (selectedTypeId === id) {
        setSelectedTypeId(null)
        setSelectedTemplateId(null)
      }
      refresh()
    } catch (e: any) {
      notify.error(e.response?.data?.msg || '刪除失敗')
    }
  }

  const handleAddTemplate = (typeId: number) => {
    setCreatingTemplateForType(typeId)
  }

  const handleCreateTemplate = async (data: {
    name: string
    display_order: number
    duration_hours: number
    max_capacity: number
    resorts: number[]
    course_start_date: string | null
    course_end_date: string | null
    booking_open_date: string | null
    booking_close_date: string | null
    minimum_coach_price_level: string
    allowed_coaches: number[]
  }) => {
    if (creatingTemplateForType == null) return
    try {
      await createTemplate({
        course_type: creatingTemplateForType,
        is_active: true,
        ...data,
      })
      notify.success('已新增模板')
      refresh()
      setCreatingTemplateForType(null)
    } catch (e: any) {
      notify.error(e.response?.data?.msg || '新增失敗')
    }
  }

  const handleEditTemplate = (tmpl: CourseTemplate) => {
    setEditingTemplate(tmpl)
  }

  const handleSaveTemplate = async (data: {
    name: string
    display_order: number
    duration_hours: number
    max_capacity: number
    resorts: number[]
    course_start_date: string | null
    course_end_date: string | null
    booking_open_date: string | null
    booking_close_date: string | null
    minimum_coach_price_level: string
    allowed_coaches: number[]
  }) => {
    if (!editingTemplate) return
    try {
      await updateTemplate(editingTemplate.id, data)
      notify.success('已更新')
      refresh()
      setEditingTemplate(null)
    } catch (e: any) {
      notify.error(e.response?.data?.msg || '更新失敗')
    }
  }

  const handleDeleteTemplate = async (id: number, name: string) => {
    if (!confirm(`確定刪除模板「${name}」？`)) return
    try {
      await deleteTemplate(id)
      notify.success('已刪除')
      if (selectedTemplateId === id) setSelectedTemplateId(null)
      refresh()
    } catch (e: any) {
      notify.error(e.response?.data?.msg || '刪除失敗')
    }
  }

  const handleAddSession = (templateId: number) => {
    setModal({
      title: '新增課程時段',
      fields: [
        { name: 'start_time', label: '開始時間', type: 'time', defaultValue: '09:00', required: true },
        { name: 'end_time', label: '結束時間', type: 'time', defaultValue: '12:00', required: true },
      ],
      onSubmit: async (vals) => {
        try {
          await createSession({
            template: templateId,
            start_time: `${vals.start_time}:00`,
            end_time: `${vals.end_time}:00`,
            is_active: true,
          })
          notify.success('已新增時段')
          refresh()
          setModal(null)
        } catch (e: any) {
          notify.error(e.response?.data?.msg || '新增失敗')
        }
      },
    })
  }

  const handleDeleteSession = async (id: number) => {
    if (!confirm('確定刪除此時段？')) return
    try {
      await deleteSession(id)
      notify.success('已刪除')
      refresh()
    } catch (e: any) {
      notify.error(e.response?.data?.msg || '刪除失敗')
    }
  }

  const handleToggleSession = async (id: number, currentActive: boolean) => {
    try {
      await updateSession(id, { is_active: !currentActive })
      refresh()
    } catch (e: any) {
      notify.error(e.response?.data?.msg || '切換失敗')
    }
  }

  const visibleCategories = useMemo(
    () => categories.filter((cat) => serviceFilter === 'all' || cat.service_type === serviceFilter),
    [categories, serviceFilter],
  )
  const selectedCategory = visibleCategories.find((cat) => cat.id === selectedCategoryId) || visibleCategories[0] || null
  const selectedTypes = selectedCategory?.types || []
  const selectedType = selectedTypes.find((type) => type.id === selectedTypeId) || selectedTypes[0] || null
  const selectedTemplates = useMemo(
    () => [...(selectedType?.templates || [])].sort(
      (a, b) => (a.display_order || 0) - (b.display_order || 0)
        || a.duration_hours - b.duration_hours
        || a.id - b.id
    ),
    [selectedType],
  )
  const selectedTemplate = selectedTemplates.find((tmpl) => tmpl.id === selectedTemplateId) || null

  const selectCategory = (category: CourseCategory) => {
    const firstType = (category.types || [])[0] || null
    setSelectedCategoryId(category.id)
    setSelectedTypeId(firstType?.id || null)
    setSelectedTemplateId(null)
  }

  const selectType = (type: typeof selectedTypes[number]) => {
    setSelectedTypeId(type.id)
    setSelectedTemplateId(null)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">課程架構</h1>
        </div>
        <button onClick={handleAddCategory} className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 flex items-center gap-2" style={{ backgroundColor: PRIMARY }}>
          <Plus size={16} />新增類別
        </button>
      </div>

      <div className="flex flex-wrap justify-end gap-2 rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
          {[
            { id: 'all', label: '全部' },
            { id: 'ski', label: '滑雪課程' },
            { id: 'photo', label: '攝影服務' },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setServiceFilter(item.id as ServiceFilter)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                serviceFilter === item.id
                  ? 'border-transparent text-white'
                  : 'border-gray-200 bg-white text-gray-600 hover:border-[#8b5cf6] dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300'
              }`}
              style={serviceFilter === item.id ? { backgroundColor: PRIMARY } : undefined}
            >
              {item.label}
            </button>
          ))}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} /></div>
      ) : error ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
          <p className="text-sm text-red-600">載入失敗</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-[280px_320px_1fr] gap-6">
          <section className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">1. 課程大類</h3>
              <span className="text-xs text-gray-400">{visibleCategories.length}</span>
            </div>
            <div className="p-3 space-y-2 max-h-[680px] overflow-y-auto">
              {visibleCategories.length === 0 ? (
                <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center dark:border-gray-600">
                  <p className="text-sm text-gray-500 dark:text-gray-400">目前篩選下尚未建立課程大類</p>
                  <button
                    onClick={handleAddCategory}
                    className="mt-3 inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-white"
                    style={{ backgroundColor: PRIMARY }}
                  >
                    <Plus size={12} />新增大類
                  </button>
                </div>
              ) : visibleCategories.map((cat) => {
                const active = selectedCategory?.id === cat.id
                return (
                  <div key={cat.id} className="group flex items-start gap-2">
                    <button
                      onClick={() => selectCategory(cat)}
                      className={`flex-1 rounded-lg border px-3 py-3 text-left transition-colors ${
                        active
                          ? 'border-transparent text-white'
                          : 'border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-gray-200 hover:border-[#8b5cf6]'
                      }`}
                      style={active ? { backgroundColor: PRIMARY } : undefined}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm flex-1">{cat.name}</span>
                        <span className={`text-[11px] px-1.5 py-0.5 rounded ${
                          active ? 'bg-white/20 text-white' : 'bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-300'
                        }`}>
                          {serviceTypeLabels[cat.service_type] || cat.service_type}
                        </span>
                      </div>
                      <div className={`mt-1 text-xs ${active ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'}`}>
                        {(cat.types || []).length} 個課程類型
                      </div>
                    </button>
                    <div className="flex flex-col opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleEditCategory(cat.id, cat.name, cat.service_type)}
                        className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 rounded"
                        title="編輯大類"
                      >
                        <Edit size={12} />
                      </button>
                      <button
                        onClick={() => handleDeleteCategory(cat.id, cat.name)}
                        className="p-1.5 text-gray-400 hover:text-red-500 rounded"
                        title="刪除大類"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <section className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">2. 課程類型</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{selectedCategory?.name || '尚未選擇大類'}</p>
              </div>
              {selectedCategory && (
                <button
                  onClick={() => handleAddType(selectedCategory.id)}
                  className="px-2.5 py-1.5 text-xs text-white rounded-lg flex items-center gap-1"
                  style={{ backgroundColor: PRIMARY }}
                >
                  <Plus size={12} />新增
                </button>
              )}
            </div>
            <div className="p-3 space-y-2 max-h-[680px] overflow-y-auto">
              {!selectedCategory ? (
                <div className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">請先選擇課程大類</div>
              ) : selectedTypes.length === 0 ? (
                <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center dark:border-gray-600">
                  <p className="text-sm text-gray-500 dark:text-gray-400">此大類尚未建立課程類型</p>
                  <button
                    onClick={() => handleAddType(selectedCategory.id)}
                    className="mt-3 inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-white"
                    style={{ backgroundColor: PRIMARY }}
                  >
                    <Plus size={12} />新增課程類型
                  </button>
                </div>
              ) : selectedTypes.map((type) => {
                const active = selectedType?.id === type.id
                return (
                  <div key={type.id} className="group flex items-start gap-2">
                    <button
                      onClick={() => selectType(type)}
                      className={`flex-1 rounded-lg border px-3 py-3 text-left transition-colors ${
                        active
                          ? 'border-transparent text-white'
                          : 'border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-gray-200 hover:border-[#8b5cf6]'
                      }`}
                      style={active ? { backgroundColor: PRIMARY } : undefined}
                    >
                      <div className="font-semibold text-sm">{type.name}</div>
                      <div className={`mt-1 text-xs ${active ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'}`}>
                        {(type.templates || []).length} 個課程模板
                      </div>
                    </button>
                    <div className="flex flex-col opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleEditType(type.id, type.name)}
                        className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 rounded"
                        title="編輯類型"
                      >
                        <Edit size={12} />
                      </button>
                      <button
                        onClick={() => handleDeleteType(type.id, type.name)}
                        className="p-1.5 text-gray-400 hover:text-red-500 rounded"
                        title="刪除類型"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <section className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white">3. 課程模板</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">{selectedType?.name || '尚未選擇課程類型'}</p>
              </div>
              {selectedType && (
                <button
                  onClick={() => handleAddTemplate(selectedType.id)}
                  className="px-3 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 flex items-center gap-2"
                  style={{ backgroundColor: PRIMARY }}
                >
                  <Plus size={14} />新增模板
                </button>
              )}
            </div>

            {!selectedType ? (
              <div className="flex items-center justify-center h-full min-h-[360px] p-12 text-center">
                <div>
                  <Calendar size={48} className="mx-auto text-gray-300 dark:text-gray-600 mb-3" />
                  <p className="text-sm text-gray-500 dark:text-gray-400">請先選擇課程類型</p>
                </div>
              </div>
            ) : (
              <div className="p-5 space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {selectedTemplates.length === 0 ? (
                    <div className="col-span-full rounded-lg border border-dashed border-gray-300 dark:border-gray-600 p-8 text-center text-sm text-gray-500 dark:text-gray-400">
                      <p>此課程類型尚未建立模板</p>
                      <button
                        onClick={() => handleAddTemplate(selectedType.id)}
                        className="mt-3 inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-white"
                        style={{ backgroundColor: PRIMARY }}
                      >
                        <Plus size={12} />新增模板
                      </button>
                    </div>
                  ) : selectedTemplates.map((tmpl) => (
                    <div key={tmpl.id} className="group flex items-start gap-2">
                      <button
                        onClick={() => setSelectedTemplateId(tmpl.id)}
                        className={`flex-1 rounded-lg border px-4 py-3 text-left transition-colors ${
                          selectedTemplateId === tmpl.id
                            ? 'border-transparent text-white'
                            : 'border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-gray-200 hover:border-[#8b5cf6]'
                        }`}
                        style={selectedTemplateId === tmpl.id ? { backgroundColor: PRIMARY } : undefined}
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm flex-1">{tmpl.name}</span>
                          <span className={`text-[11px] px-1.5 py-0.5 rounded ${
                            selectedTemplateId === tmpl.id ? 'bg-white/20 text-white' : 'bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-300'
                          }`}>
                            順序 {tmpl.display_order || 0}
                          </span>
                          {!tmpl.is_active && <span className="text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500">停用</span>}
                        </div>
                        <div className={`mt-1 text-xs ${selectedTemplateId === tmpl.id ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'}`}>
                          {tmpl.duration_hours} 小時 · 最多 {tmpl.max_capacity} 人
                        </div>
                        {getTemplateCoachRuleText(tmpl) && (
                          <div className={`mt-2 text-[11px] font-medium ${selectedTemplateId === tmpl.id ? 'text-white' : 'text-[#8b5cf6]'}`}>
                            教練條件：{getTemplateCoachRuleText(tmpl)}
                          </div>
                        )}
                      </button>
                      <button
                        onClick={() => handleDeleteTemplate(tmpl.id, tmpl.name)}
                        className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 rounded transition-opacity"
                        title="刪除模板"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  ))}
                </div>

                {selectedTemplate ? (
                  <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                    <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                      <h4 className="font-semibold text-gray-900 dark:text-white">{selectedTemplate.name}</h4>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleEditTemplate(selectedTemplate)}
                          className="p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                          title="編輯模板"
                        >
                          <Edit size={14} />
                        </button>
                        <button
                          onClick={() => handleDeleteTemplate(selectedTemplate.id, selectedTemplate.name)}
                          className="p-2 text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg"
                          title="刪除模板"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    <div className="p-5 space-y-5">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                          <div className="flex items-center gap-2 mb-2"><Clock size={16} style={{ color: PRIMARY }} /><span className="text-xs text-gray-500 dark:text-gray-400">課程時長</span></div>
                          <div className="text-xl font-bold text-gray-900 dark:text-white">{selectedTemplate.duration_hours} 小時</div>
                        </div>
                        <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                          <div className="flex items-center gap-2 mb-2"><Users size={16} style={{ color: PRIMARY }} /><span className="text-xs text-gray-500 dark:text-gray-400">最大人數</span></div>
                          <div className="text-xl font-bold text-gray-900 dark:text-white">{selectedTemplate.max_capacity} 人</div>
                        </div>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">適用雪場</h4>
                        <div className="flex flex-wrap gap-2">
                          {selectedTemplate.resort_names.map((r) => (
                            <span key={r} className="px-3 py-1 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded-full text-xs font-medium">{r}</span>
                          ))}
                        </div>
                      </div>
                      {(selectedTemplate.course_start_date || selectedTemplate.course_end_date) && (
                        <div>
                          <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
                            <Calendar size={14} style={{ color: PRIMARY }} />開課期間
                          </h4>
                          <div className="text-sm text-gray-600 dark:text-gray-300">
                            {selectedTemplate.course_start_date || '不限'} 至 {selectedTemplate.course_end_date || '不限'}
                          </div>
                        </div>
                      )}
                      {getTemplateCoachRuleText(selectedTemplate) && (
                        <div>
                          <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
                            <Users size={14} style={{ color: PRIMARY }} />教練條件
                          </h4>
                          <div className="rounded-lg border border-[#8b5cf6]/20 bg-[#f5f3ff] px-3 py-2 text-sm font-medium text-[#6d28d9] dark:bg-[#2f254f]/40 dark:text-[#ddd6fe]">
                            {getTemplateCoachRuleText(selectedTemplate)}
                          </div>
                        </div>
                      )}
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">課程時段</h4>
                          <button
                            onClick={() => handleAddSession(selectedTemplate.id)}
                            className="text-xs hover:opacity-80 flex items-center gap-1"
                            style={{ color: PRIMARY }}
                          >
                            <Plus size={12} />新增時段
                          </button>
                        </div>
                        <div className="space-y-2">
                          {selectedTemplate.sessions.map((s) => (
                            <div key={s.id} className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg group">
                              <Clock size={16} className="text-gray-400" />
                              <span className="text-sm font-medium text-gray-900 dark:text-white">{s.start_time?.substring(0, 5)} - {s.end_time?.substring(0, 5)}</span>
                              <button
                                onClick={() => handleToggleSession(s.id, s.is_active)}
                                className={`ml-auto px-2 py-0.5 text-xs font-medium rounded-full transition-colors ${s.is_active ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                                title="點擊切換啟用狀態"
                              >
                                {s.is_active ? '啟用中' : '停用'}
                              </button>
                              <button
                                onClick={() => handleDeleteSession(s.id)}
                                className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-opacity"
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>
                          ))}
                          {selectedTemplate.sessions.length === 0 && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 text-center py-4">尚未設定時段</p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : selectedTemplates.length > 0 ? (
                  <div className="rounded-lg border border-dashed border-gray-300 dark:border-gray-600 p-8 text-center text-sm text-gray-500 dark:text-gray-400">
                    選擇上方模板查看詳細設定
                  </div>
                ) : null}
              </div>
            )}
          </section>
        </div>
      )}

      {/* 統一輸入 Modal */}
      <PromptModal
        open={!!modal}
        title={modal?.title || ''}
        description={modal?.description}
        fields={modal?.fields || []}
        onCancel={() => setModal(null)}
        onSubmit={async (vals) => { await modal?.onSubmit(vals) }}
      />

      {editingTemplate && (
        <TemplateEditDrawer
          template={editingTemplate}
          allResorts={allResorts}
          allCoaches={allCoaches}
          onClose={() => setEditingTemplate(null)}
          onSave={handleSaveTemplate}
        />
      )}

      {creatingTemplateForType !== null && (
        <TemplateEditDrawer
          template={null}
          allResorts={allResorts}
          allCoaches={allCoaches}
          onClose={() => setCreatingTemplateForType(null)}
          onSave={handleCreateTemplate}
        />
      )}
    </div>
  )
}

// ===== 課程模板編輯 Drawer（含多選雪場 + 日期）=====
function TemplateEditDrawer({ template, allResorts, allCoaches, onClose, onSave }: {
  template: CourseTemplate | null
  allResorts: Resort[]
  allCoaches: Coach[]
  onClose: () => void
  onSave: (data: {
    name: string
    display_order: number
    duration_hours: number
    max_capacity: number
    resorts: number[]
    course_start_date: string | null
    course_end_date: string | null
    booking_open_date: string | null
    booking_close_date: string | null
    minimum_coach_price_level: string
    allowed_coaches: number[]
  }) => Promise<void>
}) {
  const isCreate = template === null
  const [name, setName] = useState(template?.name || '')
  const [displayOrder, setDisplayOrder] = useState(String(template?.display_order ?? 0))
  const [duration, setDuration] = useState(String(template?.duration_hours ?? 3))
  const [capacity, setCapacity] = useState(String(template?.max_capacity ?? 6))
  const [resortIds, setResortIds] = useState<number[]>(template?.resorts || [])
  const [courseStart, setCourseStart] = useState(template?.course_start_date || '')
  const [courseEnd, setCourseEnd] = useState(template?.course_end_date || '')
  const [bookingOpen, setBookingOpen] = useState(template?.booking_open_date || '')
  const [bookingClose, setBookingClose] = useState(template?.booking_close_date || '')
  const [minimumCoachLevel, setMinimumCoachLevel] = useState(template?.minimum_coach_price_level || '')
  const [allowedCoachIds, setAllowedCoachIds] = useState<number[]>(template?.allowed_coaches || [])
  const [saving, setSaving] = useState(false)

  const toggleResort = (id: number) => {
    setResortIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }

  const toggleCoach = (id: number) => {
    setAllowedCoachIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) { alert('請填寫模板名稱'); return }
    setSaving(true)
    try {
      await onSave({
        name: name.trim(),
        display_order: Number(displayOrder) || 0,
        duration_hours: parseInt(duration, 10),
        max_capacity: parseInt(capacity, 10),
        resorts: resortIds,
        course_start_date: courseStart || null,
        course_end_date: courseEnd || null,
        booking_open_date: bookingOpen || null,
        booking_close_date: bookingClose || null,
        minimum_coach_price_level: minimumCoachLevel,
        allowed_coaches: allowedCoachIds,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 animate-fadeIn" onClick={onClose} />
      <form
        onSubmit={handleSubmit}
        className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white dark:bg-gray-800 shadow-2xl flex flex-col animate-slideIn"
      >
        <div className="px-6 py-4 flex items-center justify-between text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
          <h2 className="text-lg font-semibold">{isCreate ? '新增模板' : `編輯模板：${template!.name}`}</h2>
          <button type="button" onClick={onClose} className="text-white/80 hover:text-white"><X size={20} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">基本資料</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">模板名稱 <span className="text-red-500">*</span></label>
                <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">顯示順序</label>
                  <input type="number" value={displayOrder} onChange={(e) => setDisplayOrder(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
                  <p className="mt-1 text-xs text-gray-500">數字小排前面</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">課程時長（小時）</label>
                  <input type="number" value={duration} onChange={(e) => setDuration(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">最大人數</label>
                  <input type="number" value={capacity} onChange={(e) => setCapacity(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
                </div>
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <MapPin size={16} style={{ color: PRIMARY }} />適用雪場
            </h3>
            {allResorts.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">尚未建立任何雪場</p>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {allResorts.map((r) => {
                  const checked = resortIds.includes(r.id)
                  return (
                    <label key={r.id} className={`flex items-center gap-3 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${checked ? 'border-transparent text-white' : 'border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600'}`}
                      style={checked ? { backgroundColor: PRIMARY } : undefined}>
                      <input type="checkbox" checked={checked} onChange={() => toggleResort(r.id)}
                        className="w-4 h-4" style={{ accentColor: '#fff' }} />
                      <span className="text-sm">{r.display_name}</span>
                    </label>
                  )
                })}
              </div>
            )}
          </section>

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <Users size={16} style={{ color: PRIMARY }} />教練條件
            </h3>
            <div className="space-y-4 rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-700/40">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">最低教練等級</label>
                <select
                  value={minimumCoachLevel}
                  onChange={(e) => setMinimumCoachLevel(e.target.value)}
                  className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                >
                  <option value="">不限制</option>
                  <option value="Lv1">Lv1 以上</option>
                  <option value="Lv2">Lv2 以上</option>
                  <option value="Lv3">Lv3 以上</option>
                  <option value="director">校長 / 總監</option>
                </select>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">進階課程可選 Lv2 以上；一般課程可保持不限制。</p>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">自動排課優先教練</label>
                  {allowedCoachIds.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setAllowedCoachIds([])}
                      className="text-xs font-medium text-gray-500 hover:text-red-500"
                    >
                      清空
                    </button>
                  )}
                </div>
                {allCoaches.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-gray-300 p-4 text-center text-sm text-gray-500 dark:border-gray-600 dark:text-gray-400">
                    尚未建立教練；可先只設定最低等級。
                  </p>
                ) : (
                  <div className="grid max-h-56 grid-cols-2 gap-2 overflow-y-auto pr-1">
                    {allCoaches.map((coach) => {
                      const checked = allowedCoachIds.includes(coach.id)
                      return (
                        <label
                          key={coach.id}
                          className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm cursor-pointer transition-colors ${
                            checked
                              ? 'border-[#8b5cf6] bg-[#f5f3ff] text-[#6d28d9] dark:bg-[#2f254f] dark:text-[#ddd6fe]'
                              : 'border-gray-200 bg-white text-gray-700 hover:border-[#8b5cf6] dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleCoach(coach.id)}
                            className="h-4 w-4"
                            style={{ accentColor: PRIMARY }}
                          />
                          <span className="truncate">{coach.name || `教練 #${coach.id}`}</span>
                        </label>
                      )
                    })}
                  </div>
                )}
                <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">名單內教練會優先被自動排課；前台仍會顯示所有符合等級、雪場、語言與能力的教練。</p>
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <Calendar size={16} style={{ color: PRIMARY }} />開課與預約期間
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">課程開始日期</label>
                <input type="date" value={courseStart} onChange={(e) => setCourseStart(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
                <p className="mt-1 text-xs text-gray-500">學員只能預約此日後</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">課程結束日期</label>
                <input type="date" value={courseEnd} onChange={(e) => setCourseEnd(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
                <p className="mt-1 text-xs text-gray-500">雪季結束日</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">開放預約日期</label>
                <input type="date" value={bookingOpen} onChange={(e) => setBookingOpen(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
                <p className="mt-1 text-xs text-gray-500">此日前無法預約</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">關閉預約日期</label>
                <input type="date" value={bookingClose} onChange={(e) => setBookingClose(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
                <p className="mt-1 text-xs text-gray-500">此日後無法預約</p>
              </div>
            </div>
          </section>
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <button type="button" onClick={onClose} disabled={saving}
            className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50">取消</button>
          <button type="submit" disabled={saving}
            className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 flex items-center gap-2 disabled:opacity-50"
            style={{ backgroundColor: PRIMARY }}>
            {saving && <Loader2 size={14} className="animate-spin" />}{isCreate ? '建立模板' : '儲存變更'}
          </button>
        </div>
      </form>
    </>
  )
}
