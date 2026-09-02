/**
 * 全域通知 Context（從 console 移植簡化版）
 *   useNotification().success('儲存成功')
 *   useNotification().error('失敗')
 */
import React, { createContext, useContext, useState, useCallback } from 'react'

type NotificationType = 'success' | 'error' | 'warning' | 'info'

interface NotificationData {
  show: boolean
  type: NotificationType
  message: string
}

interface NotificationContextType {
  notification: NotificationData | null
  show: (type: NotificationType, message: string) => void
  hide: () => void
  success: (message: string) => void
  error: (message: string) => void
  warning: (message: string) => void
  info: (message: string) => void
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined)

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notification, setNotification] = useState<NotificationData | null>(null)

  const hide = useCallback(() => {
    setNotification((prev) => (prev ? { ...prev, show: false } : null))
  }, [])

  const show = useCallback(
    (type: NotificationType, message: string) => {
      setNotification({ show: true, type, message })
      // 自動關閉
      setTimeout(() => {
        setNotification((prev) => (prev ? { ...prev, show: false } : null))
      }, 3500)
    },
    [],
  )

  const success = useCallback((m: string) => show('success', m), [show])
  const error = useCallback((m: string) => show('error', m), [show])
  const warning = useCallback((m: string) => show('warning', m), [show])
  const info = useCallback((m: string) => show('info', m), [show])

  return (
    <NotificationContext.Provider value={{ notification, show, hide, success, error, warning, info }}>
      {children}
    </NotificationContext.Provider>
  )
}

export function useNotification() {
  const ctx = useContext(NotificationContext)
  if (!ctx) throw new Error('useNotification must be used within a NotificationProvider')
  return ctx
}
