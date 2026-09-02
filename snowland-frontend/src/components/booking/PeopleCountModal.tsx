import { useState } from 'react'
import Modal from '@/components/ui/Modal'
import { useBookingStore } from '@/store/bookingStore'
import { Users, Minus, Plus } from 'lucide-react'

interface PeopleCountModalProps {
  isOpen: boolean
  onClose: () => void
  onNext: (count: number, hasUnder6: boolean) => void
  onBack: () => void
}

export default function PeopleCountModal({
  isOpen,
  onClose,
  onNext,
  onBack,
}: PeopleCountModalProps) {
  const peopleCount = useBookingStore((state) => state.peopleCount)
  const setPeopleCount = useBookingStore((state) => state.setPeopleCount)
  const hasUnder6 = useBookingStore((state) => state.hasUnder6)
  const setHasUnder6 = useBookingStore((state) => state.setHasUnder6)

  const [localCount, setLocalCount] = useState(peopleCount)
  const [localHasUnder6, setLocalHasUnder6] = useState(hasUnder6)

  const handleDecrease = () => {
    if (localCount > 1) {
      setLocalCount(localCount - 1)
    }
  }

  const handleIncrease = () => {
    if (localCount < 6) {
      setLocalCount(localCount + 1)
    }
  }

  const handleConfirm = () => {
    setPeopleCount(localCount)
    setHasUnder6(localHasUnder6)
    onNext(localCount, localHasUnder6)
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="請選擇人數">
      <button
        onClick={onBack}
        className="mb-4 rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200"
      >
        ← 返回
      </button>

      <div className="flex flex-col items-center gap-4 py-4">
        <div className="flex items-center gap-4">
          <button
            onClick={handleDecrease}
            disabled={localCount <= 1}
            className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-200 text-gray-700 transition-all duration-300 hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Minus size={20} />
          </button>

          <div className="flex h-20 w-28 items-center justify-center rounded-xl border-4 border-primary-500 bg-primary-50">
            <span className="text-4xl font-bold text-primary-700">
              {localCount}
            </span>
          </div>

          <button
            onClick={handleIncrease}
            disabled={localCount >= 6}
            className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-500 text-white transition-all duration-300 hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus size={20} />
          </button>
        </div>

        <p className="text-xs text-gray-600">
          最多 6 人，最少 1 人
        </p>

        {/* 6歲以下勾選框 */}
        <label className="flex cursor-pointer items-center gap-2 rounded-lg border-2 border-gray-200 bg-gray-50 px-4 py-2 transition-all hover:border-primary-300">
          <input
            type="checkbox"
            checked={localHasUnder6}
            onChange={(e) => setLocalHasUnder6(e.target.checked)}
            className="h-5 w-5 cursor-pointer rounded border-gray-300 text-primary-600 focus:ring-2 focus:ring-primary-500"
          />
          <span className="text-sm font-medium text-gray-700">
            有6歲以下學員
          </span>
        </label>

        <button
          onClick={handleConfirm}
          className="w-full rounded-lg bg-primary-500 px-6 py-3 font-semibold text-white transition-all duration-300 hover:bg-primary-600 hover:shadow-lg"
        >
          確認人數：{localCount} 人
        </button>
      </div>
    </Modal>
  )
}
