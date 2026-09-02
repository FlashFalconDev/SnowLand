import { useState, useEffect } from 'react'
import { useBookingStore } from '@/store/bookingStore'
import { fetchCourseTemplates } from '@/api/booking'
import { Users, MapPin } from 'lucide-react'

interface CourseTemplateGridProps {
  onNext: () => void
  onBack: () => void
}

interface CourseTemplate {
  id: number
  name: string
  duration_hours: number
  max_capacity: number
  course_type_name: string
  category_name: string
  resorts: Array<{ id: number; name: string; display_name: string }>
}

export default function CourseTemplateGrid({
  onNext,
  onBack,
}: CourseTemplateGridProps) {
  const [templates, setTemplates] = useState<CourseTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedCourseType = useBookingStore((state) => state.selectedCourseType)
  const selectedResort = useBookingStore((state) => state.selectedResort)
  const setSelectedCourseTemplate = useBookingStore(
    (state) => state.setSelectedCourseTemplate
  )

  useEffect(() => {
    const loadTemplates = async () => {
      if (!selectedCourseType || !selectedResort) return

      try {
        setLoading(true)
        setError(null)
        const data = await fetchCourseTemplates({
          course_type_id: selectedCourseType,
          resort: selectedResort,
        })
        setTemplates(data)
      } catch (err) {
        console.error('載入課程模板失敗:', err)
        setError('載入課程模板失敗，請稍後再試')
      } finally {
        setLoading(false)
      }
    }

    loadTemplates()
  }, [selectedCourseType, selectedResort])

  const handleSelectTemplate = (templateId: number) => {
    setSelectedCourseTemplate(templateId)
    onNext()
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-2xl font-bold text-gray-800">選擇課程時長</h3>
        <p className="mt-2 text-gray-600">選擇最適合您的課程方案</p>
      </div>

      {loading && (
        <div className="py-12 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-r-transparent"></div>
          <p className="mt-4 text-gray-600">載入課程模板中...</p>
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-600">{error}</div>
      )}

      {!loading && !error && templates.length === 0 && (
        <div className="flex flex-col items-center gap-6 py-12">
          <div className="rounded-lg bg-yellow-50 px-6 py-4 text-center">
            <p className="text-lg font-medium text-yellow-800">
              😔 目前沒有可用的課程模板
            </p>
            <p className="mt-2 text-sm text-yellow-700">
              請返回重新選擇課程類型或雪場
            </p>
          </div>
          <button
            onClick={onBack}
            className="rounded-lg bg-primary-500 px-8 py-3 text-lg font-semibold text-white transition-all duration-300 hover:bg-primary-600 hover:shadow-lg"
          >
            ← 返回上一步
          </button>
        </div>
      )}

      {!loading && !error && templates.length > 0 && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <button
              key={template.id}
              onClick={() => handleSelectTemplate(template.id)}
              className="group relative overflow-hidden rounded-2xl border-2 border-gray-200 bg-white p-6 text-left transition-all hover:scale-105 hover:border-primary-500 hover:shadow-xl"
            >
              <div className="flex flex-col gap-4">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-primary-400 to-purple-400 text-2xl font-bold text-white shadow-lg">
                    {template.duration_hours}h
                  </div>
                  <div className="rounded-full bg-primary-100 px-3 py-1 text-xs font-semibold text-primary-700">
                    {template.category_name}
                  </div>
                </div>

                {/* Content */}
                <div>
                  <h3 className="text-xl font-bold text-gray-800">
                    {template.name}
                  </h3>
                  <p className="mt-1 text-sm text-gray-600">
                    {template.course_type_name}
                  </p>
                </div>

                {/* Info */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Users size={16} className="text-primary-500" />
                    <span>最多 {template.max_capacity} 人</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <MapPin size={16} className="text-primary-500" />
                    <span>
                      {template.resorts.map((r) => r.display_name).join('、')}
                    </span>
                  </div>
                </div>
              </div>

              {/* Hover Effect */}
              <div className="absolute -right-8 -bottom-8 h-32 w-32 rounded-full bg-primary-200/20 transition-all group-hover:scale-150" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
