import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { clientCodeFromPath } from '@/utils/tenant'

interface ClientInfo {internal_code: string; name: string; logo_url: string; google_client_id?: string; booking_enabled?: boolean}
export function useClientInfo() {
  const {pathname} = useLocation()
  const clientCode = clientCodeFromPath(pathname)
  const [clientInfo, setClientInfo] = useState<ClientInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setClientInfo(null); setError(''); setIsLoading(Boolean(clientCode))
    if (!clientCode) return () => controller.abort()
    fetch(`/booking/${encodeURIComponent(clientCode)}/api/client-info/`, {signal:controller.signal})
      .then(async response => {
        if (!response.ok) throw new Error('找不到此學校或目前未開放')
        const data = await response.json()
        if (data.internal_code !== clientCode) throw new Error('學校資料不一致，請重新載入')
        if (!controller.signal.aborted) setClientInfo(data)
      }).catch(error => {if (!controller.signal.aborted) setError(error.message)})
      .finally(() => {if (!controller.signal.aborted) setIsLoading(false)})
    return () => controller.abort()
  }, [clientCode])
  const current = clientInfo?.internal_code === clientCode ? clientInfo : null
  return {clientCode, clientName:current?.name || '滑雪預約系統', clientInfo:current, isLoading, error}
}
