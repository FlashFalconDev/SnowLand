import Modal from '@/components/ui/Modal'
import { useBookingStore } from '@/store/bookingStore'
import { CheckCircle, Circle, Mountain, TrendingUp, Activity, Medal, Trophy, Lightbulb, type LucideIcon } from 'lucide-react'

interface AbilityLevelModalProps {
  isOpen: boolean
  onClose: () => void
  onNext: () => void
  onBack: () => void
}

const ABILITY_LEVELS: Array<{ value: string; label: string; Icon: LucideIcon }> = [
  { value: 'no_exp', label: '無經驗', Icon: Circle },
  { value: 'entry', label: '入門', Icon: Mountain },
  { value: 'basic', label: '初階', Icon: TrendingUp },
  { value: 'intermediate', label: '中階', Icon: Activity },
  { value: 'advanced', label: '高階', Icon: Medal },
  { value: 'expert', label: '專家', Icon: Trophy },
]

export default function AbilityLevelModal({
  isOpen,
  onClose,
  onNext,
  onBack,
}: AbilityLevelModalProps) {
  const setSelectedAbilityLevel = useBookingStore(
    (state) => state.setSelectedAbilityLevel
  )

  const handleSelect = (level: string) => {
    setSelectedAbilityLevel(level)
    onNext()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="請選擇您的滑雪能力等級">
      <button
        onClick={onBack}
        className="mb-4 rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200"
      >
        ← 返回
      </button>

      <div className="grid gap-2 sm:grid-cols-2">
        {ABILITY_LEVELS.map((level) => (
          <button
            key={level.value}
            onClick={() => handleSelect(level.value)}
            className="group relative overflow-hidden rounded-lg border-2 border-gray-200 bg-white p-3 text-left transition-all duration-300 hover:border-primary-500 hover:shadow-md"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary-100 to-primary-200">
                <level.Icon size={24} className="text-primary-600" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-gray-800">
                  {level.label}
                </h3>
              </div>
              <CheckCircle size={18} className="text-gray-300 transition-colors group-hover:text-primary-500" />
            </div>
          </button>
        ))}
      </div>

      <div className="mt-4 rounded-lg bg-blue-50 p-3">
        <p className="flex items-center gap-2 text-xs text-blue-800">
          <Lightbulb size={14} className="flex-shrink-0" />
          <span>請根據實際能力選擇，我們會為您匹配最合適的教練和課程</span>
        </p>
      </div>
    </Modal>
  )
}
