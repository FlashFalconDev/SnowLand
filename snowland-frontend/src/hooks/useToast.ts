import { useState, useCallback } from 'react'
import { ToastType } from '@/components/ui/Toast'

interface ToastOptions {
  message: string
  type?: ToastType
  duration?: number
}

export function useToast() {
  const [toast, setToast] = useState<ToastOptions | null>(null)

  const showToast = useCallback((options: ToastOptions) => {
    setToast(options)
  }, [])

  const hideToast = useCallback(() => {
    setToast(null)
  }, [])

  const success = useCallback((message: string, duration?: number) => {
    showToast({ message, type: 'success', duration })
  }, [showToast])

  const error = useCallback((message: string, duration?: number) => {
    showToast({ message, type: 'error', duration })
  }, [showToast])

  const warning = useCallback((message: string, duration?: number) => {
    showToast({ message, type: 'warning', duration })
  }, [showToast])

  const info = useCallback((message: string, duration?: number) => {
    showToast({ message, type: 'info', duration })
  }, [showToast])

  return {
    toast,
    showToast,
    hideToast,
    success,
    error,
    warning,
    info,
  }
}
