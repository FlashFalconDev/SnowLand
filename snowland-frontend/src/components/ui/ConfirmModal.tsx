import { X, AlertTriangle, Sparkles } from 'lucide-react'

type Variant = 'default' | 'danger' | 'info'

interface ConfirmModalProps {
  isOpen: boolean
  title: string
  message: string | React.ReactNode
  confirmText?: string
  cancelText?: string
  variant?: Variant
  onConfirm: () => void
  onCancel: () => void
}

const VARIANT_STYLES: Record<Variant, {
  icon: React.ReactNode
  headerBg: string
  iconBg: string
  confirmBg: string
}> = {
  default: {
    icon: <AlertTriangle size={22} className="text-[#2b5f8f]" />,
    headerBg: 'bg-[#e9eef3]',
    iconBg: 'bg-white',
    confirmBg: 'bg-[#2b5f8f] hover:opacity-90',
  },
  danger: {
    icon: <AlertTriangle size={22} className="text-red-600" />,
    headerBg: 'bg-red-50',
    iconBg: 'bg-white',
    confirmBg: 'bg-red-600 hover:bg-red-700',
  },
  info: {
    icon: <Sparkles size={22} className="text-purple-600" />,
    headerBg: 'bg-purple-50',
    iconBg: 'bg-white',
    confirmBg: 'bg-gradient-to-r from-purple-500 to-blue-500 hover:opacity-90',
  },
}

export default function ConfirmModal({
  isOpen, title, message,
  confirmText = '確定',
  cancelText = '取消',
  variant = 'default',
  onConfirm, onCancel,
}: ConfirmModalProps) {
  if (!isOpen) return null
  const s = VARIANT_STYLES[variant]

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl overflow-hidden">
        <div className={`${s.headerBg} px-6 py-4 flex items-start justify-between gap-3`}>
          <div className="flex items-start gap-3">
            <div className={`flex h-10 w-10 items-center justify-center rounded-full flex-shrink-0 ${s.iconBg}`}>
              {s.icon}
            </div>
            <h2 className="text-base font-semibold text-[#1f2937] mt-1.5">{title}</h2>
          </div>
          <button
            onClick={onCancel}
            className="p-1 text-gray-400 hover:text-gray-600 rounded-full hover:bg-white/60"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5">
          <div className="text-sm text-[#374151] leading-relaxed">
            {message}
          </div>
        </div>

        <div className="px-6 py-4 bg-gray-50 flex justify-end gap-3 border-t border-gray-100">
          <button
            onClick={onCancel}
            className="px-5 py-2 rounded-full border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className={`px-5 py-2 rounded-full text-sm font-semibold text-white transition-colors ${s.confirmBg}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
