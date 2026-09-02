import { useEffect } from 'react'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

interface ToastProps {
  message: string
  type?: ToastType
  duration?: number
  isOpen?: boolean
  onClose: () => void
}

export default function Toast({
  message,
  type = 'info',
  duration = 5000,
  isOpen = true,
  onClose,
}: ToastProps) {
  useEffect(() => {
    if (!message || !isOpen) return

    const timer = setTimeout(() => {
      onClose()
    }, duration)

    return () => clearTimeout(timer)
  }, [duration, onClose, message, isOpen])

  // 如果沒有訊息或未打開，不顯示
  if (!message || !isOpen) return null

  const getIcon = () => {
    switch (type) {
      case 'success':
        return <CheckCircle size={24} />
      case 'error':
        return <AlertCircle size={24} />
      case 'warning':
        return <AlertTriangle size={24} />
      case 'info':
        return <Info size={24} />
    }
  }

  const getColors = () => {
    switch (type) {
      case 'success':
        return 'bg-green-500 text-white'
      case 'error':
        return 'bg-red-500 text-white'
      case 'warning':
        return 'bg-yellow-500 text-white'
      case 'info':
        return 'bg-blue-500 text-white'
    }
  }

  return (
    <div className="fixed right-4 top-4 z-[9999] animate-slide-in-right">
      <div
        className={`flex min-w-[300px] max-w-md items-center gap-3 rounded-lg p-4 shadow-2xl ${getColors()}`}
      >
        <div className="flex-shrink-0">{getIcon()}</div>
        <p className="flex-1 text-sm font-medium">{message}</p>
        <button
          onClick={onClose}
          className="flex-shrink-0 rounded-full p-1 transition-colors hover:bg-white/20"
        >
          <X size={18} />
        </button>
      </div>
    </div>
  )
}
