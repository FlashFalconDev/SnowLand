import { useState, useEffect } from 'react'
import Modal from '@/components/ui/Modal'
import { CourseCategory } from '@/types/booking'
import { useBookingStore } from '@/store/bookingStore'
import { fetchCourseCategories } from '@/api/booking'

interface CourseCategoryModalProps {
  isOpen: boolean
  onClose: () => void
  onNext: () => void
}

export default function CourseCategoryModal({
  isOpen,
  onClose,
  onNext,
}: CourseCategoryModalProps) {
  const [categories, setCategories] = useState<CourseCategory[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const setSelectedCourseCategory = useBookingStore(
    (state) => state.setSelectedCourseCategory
  )

  useEffect(() => {
    const loadCategories = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await fetchCourseCategories()
        setCategories(data)
      } catch (err) {
        console.error('載入課程大類失敗:', err)
        setError('載入課程大類失敗，請稍後再試')
      } finally {
        setLoading(false)
      }
    }

    if (isOpen) {
      loadCategories()
    }
  }, [isOpen])

  const handleSelect = (categoryId: number, categoryName: string) => {
    setSelectedCourseCategory(categoryId, categoryName)
    onNext()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="請選擇課程大類">
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

      {!loading && !error && (
        <div className="grid gap-3">
          {categories.map((category) => (
          <button
            key={category.id}
            onClick={() => handleSelect(category.id, category.name)}
            className="group relative overflow-hidden rounded-lg bg-gradient-to-br from-primary-50 to-primary-100 p-4 text-left transition-all duration-300 hover:scale-105 hover:shadow-lg"
          >
            <div className="relative z-10">
              <h3 className="text-lg font-bold text-primary-700">
                {category.name}
              </h3>
            </div>
            <div className="absolute inset-0 bg-gradient-to-br from-primary-400/0 to-primary-600/0 transition-all duration-300 group-hover:from-primary-400/10 group-hover:to-primary-600/10" />
          </button>
          ))}
        </div>
      )}
    </Modal>
  )
}
