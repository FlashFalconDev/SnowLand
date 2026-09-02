import { useState, useEffect } from 'react'
import Modal from '@/components/ui/Modal'
import { CourseType } from '@/types/booking'
import { useBookingStore } from '@/store/bookingStore'
import { BookOpen } from 'lucide-react'
import { fetchCourseTypes } from '@/api/booking'

interface CourseTypeModalProps {
  isOpen: boolean
  onClose: () => void
  onNext: () => void
  onBack: () => void
}

export default function CourseTypeModal({
  isOpen,
  onClose,
  onNext,
  onBack,
}: CourseTypeModalProps) {
  const [courseTypes, setCourseTypes] = useState<CourseType[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const setSelectedCourseType = useBookingStore(
    (state) => state.setSelectedCourseType
  )
  const selectedCourseCategory = useBookingStore(
    (state) => state.selectedCourseCategory
  )
  const selectedResort = useBookingStore(
    (state) => state.selectedResort
  )

  useEffect(() => {
    const loadCourseTypes = async () => {
      if (!selectedCourseCategory) return

      try {
        setLoading(true)
        setError(null)
        // 傳遞課程大類和雪場參數，只獲取該雪場有的課程類型
        const data = await fetchCourseTypes(selectedCourseCategory, selectedResort || undefined)
        setCourseTypes(data)
      } catch (err) {
        console.error('載入課程類型失敗:', err)
        setError('載入課程類型失敗，請稍後再試')
      } finally {
        setLoading(false)
      }
    }

    if (isOpen) {
      loadCourseTypes()
    }
  }, [isOpen, selectedCourseCategory, selectedResort])

  const handleSelect = (courseTypeId: number) => {
    setSelectedCourseType(courseTypeId)
    onNext()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="請選擇課程類型">
      <button
        onClick={onBack}
        className="mb-4 rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200"
      >
        ← 返回
      </button>

      {loading && (
        <div className="py-12 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-r-transparent"></div>
          <p className="mt-4 text-gray-600">載入中...</p>
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-red-600">
          {error}
        </div>
      )}

      {!loading && !error && courseTypes.length === 0 && (
        <div className="flex flex-col items-center gap-6 py-12">
          <div className="rounded-lg bg-yellow-50 px-6 py-4 text-center">
            <p className="text-lg font-medium text-yellow-800">
              😔 目前沒有符合條件的課程類型
            </p>
            <p className="mt-2 text-sm text-yellow-700">
              請返回重新選擇雪場或課程大類
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

      {!loading && !error && courseTypes.length > 0 && (
        <div className="grid gap-3">
          {courseTypes.map((courseType) => (
          <button
            key={courseType.id}
            onClick={() => handleSelect(courseType.id)}
            className="group relative overflow-hidden rounded-lg border-2 border-gray-200 bg-white p-4 text-left transition-all duration-300 hover:border-primary-500 hover:shadow-lg"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-100 text-primary-600">
                <BookOpen size={20} />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-gray-800">
                  {courseType.name}
                </h3>
              </div>
            </div>
          </button>
          ))}
        </div>
      )}
    </Modal>
  )
}
