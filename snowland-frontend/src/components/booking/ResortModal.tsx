import { useState, useEffect } from 'react'
import Modal from '@/components/ui/Modal'
import { Resort } from '@/types/booking'
import { useBookingStore } from '@/store/bookingStore'
import { MapPin } from 'lucide-react'
import { fetchResorts } from '@/api/booking'

interface ResortModalProps {
  isOpen: boolean
  onClose: () => void
  onNext: () => void
  onBack: () => void
}

export default function ResortModal({
  isOpen,
  onClose,
  onNext,
  onBack,
}: ResortModalProps) {
  const [resorts, setResorts] = useState<Resort[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const setSelectedResort = useBookingStore((state) => state.setSelectedResort)

  useEffect(() => {
    const loadResorts = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await fetchResorts()
        setResorts(data)
      } catch (err) {
        console.error('載入雪場列表失敗:', err)
        setError('載入雪場列表失敗，請稍後再試')
      } finally {
        setLoading(false)
      }
    }

    if (isOpen) {
      loadResorts()
    }
  }, [isOpen])

  const handleSelect = (resortName: string, resortDisplayName: string) => {
    setSelectedResort(resortName, resortDisplayName)
    onNext()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="請選擇雪場">
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

      {!loading && !error && (
        <div className="grid gap-3">
          {resorts.map((resort) => (
          <button
            key={resort.name}
            onClick={() => handleSelect(resort.name, resort.display_name)}
            className="group relative overflow-hidden rounded-lg border-2 border-gray-200 bg-white p-4 text-left transition-all duration-300 hover:border-primary-500 hover:shadow-lg"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-100 text-primary-600">
                <MapPin size={20} />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-gray-800">
                  {resort.display_name}
                </h3>
                {resort.auto_scheduling_enabled && (
                  <span className="mt-1 inline-block rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                    自動排課
                  </span>
                )}
              </div>
            </div>
          </button>
          ))}
        </div>
      )}
    </Modal>
  )
}
