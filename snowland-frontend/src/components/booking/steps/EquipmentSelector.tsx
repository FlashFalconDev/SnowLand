import { useBookingStore } from '@/store/bookingStore'
import { Package, CheckCircle, UserCheck, Clock, Lightbulb, type LucideIcon } from 'lucide-react'

interface EquipmentSelectorProps {
  onNext: () => void
  onBack: () => void
}

type EquipmentOption = 'self_rent' | 'own_equipment' | 'class_time_help' | 'extra_time_help'

const EQUIPMENT_OPTIONS: Array<{
  value: EquipmentOption
  title: string
  description: string
  Icon: LucideIcon
  color: string
  iconBg: string
  fee?: string
}> = [
  {
    value: 'self_rent' as EquipmentOption,
    title: '自行租借不須協助',
    description: '我會自行到雪場租借裝備',
    Icon: Package,
    color: 'from-blue-50 to-cyan-50 border-blue-200 hover:border-blue-500',
    iconBg: 'from-blue-400 to-cyan-400',
  },
  {
    value: 'own_equipment' as EquipmentOption,
    title: '自備裝備不須協助',
    description: '我已準備好自己的裝備',
    Icon: CheckCircle,
    color: 'from-green-50 to-emerald-50 border-green-200 hover:border-green-500',
    iconBg: 'from-green-400 to-emerald-400',
  },
  {
    value: 'class_time_help' as EquipmentOption,
    title: '課程時間內協助',
    description: '需要教練在課程時間內協助租借',
    Icon: UserCheck,
    color: 'from-purple-50 to-pink-50 border-purple-200 hover:border-purple-500',
    iconBg: 'from-purple-400 to-pink-400',
  },
  {
    value: 'extra_time_help' as EquipmentOption,
    title: '加購協助時間',
    description: '需要教練額外時間協助租借',
    Icon: Clock,
    color: 'from-orange-50 to-red-50 border-orange-200 hover:border-orange-500',
    iconBg: 'from-orange-400 to-red-400',
    fee: '1~3人 1,000元, 4~6人 2,000元',
  },
]

export default function EquipmentSelector({
  onNext,
  onBack,
}: EquipmentSelectorProps) {
  const setEquipmentOption = useBookingStore((state) => state.setEquipmentOption)

  const handleSelect = (option: EquipmentOption) => {
    setEquipmentOption(option)
    onNext()
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-2xl font-bold text-gray-800">
          請選擇您的裝備需求
        </h3>
        <p className="mt-2 text-gray-600">
          請告訴我們您是否需要裝備協助
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {EQUIPMENT_OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={() => handleSelect(option.value)}
            className={`group relative overflow-hidden rounded-xl border-2 bg-gradient-to-br p-6 text-left transition-all hover:scale-105 hover:shadow-xl ${option.color}`}
          >
            <div className="flex items-start gap-4">
              <div className={`flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br shadow-lg ${option.iconBg}`}>
                <option.Icon size={32} className="text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-bold text-gray-800">
                  {option.title}
                </h3>
                <p className="mt-1 text-sm text-gray-600">
                  {option.description}
                </p>
                {option.fee && (
                  <p className="mt-2 text-xs font-semibold text-gray-700">
                    {option.fee}
                  </p>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>

      <div className="rounded-lg bg-blue-50 p-4">
        <p className="flex items-start gap-2 text-sm text-blue-800">
          <Lightbulb size={16} className="mt-0.5 flex-shrink-0" />
          <span>
            <strong>提示：</strong>
            租借裝備費用會根據人數和雪場收取，具體金額將在最後確認時顯示
          </span>
        </p>
      </div>
    </div>
  )
}
