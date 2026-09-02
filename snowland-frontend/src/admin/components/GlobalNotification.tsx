/**
 * 全域通知元件（從 console 移植）
 * 從右上角滑入，3.5 秒後自動關閉
 */
import React from 'react'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { useNotification } from '../context'

const iconMap = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const colorMap = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
}

const iconColorMap = {
  success: 'text-green-500',
  error: 'text-red-500',
  warning: 'text-yellow-500',
  info: 'text-blue-500',
}

export function GlobalNotification() {
  const { notification, hide } = useNotification()

  if (!notification?.show) return null

  const Icon = iconMap[notification.type]

  return (
    <div className="fixed top-4 right-4 z-[9999] animate-slide-in">
      <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg ${colorMap[notification.type]}`}>
        <Icon size={20} className={iconColorMap[notification.type]} />
        <span className="text-sm font-medium">{notification.message}</span>
        <button onClick={hide} className="p-1 hover:bg-black/10 rounded-lg transition-colors">
          <X size={16} />
        </button>
      </div>

      <style>{`
        @keyframes slide-in {
          from { opacity: 0; transform: translateX(100%); }
          to { opacity: 1; transform: translateX(0); }
        }
        .animate-slide-in { animation: slide-in 0.3s ease-out; }
      `}</style>
    </div>
  )
}
