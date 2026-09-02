import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'

interface ClientInfo {
  internal_code: string
  name: string
  sales: string
  program: string
}

/**
 * Hook：獲取當前選擇的客戶資訊
 * 從 localStorage 讀取，如果沒有則從後端 API 獲取
 */
export function useClientInfo() {
  const { clientCode: clientCodeFromUrl } = useParams<{ clientCode: string }>()
  const [clientCode, setClientCode] = useState<string | null>(null)
  const [clientName, setClientName] = useState<string>('滑雪預約系統')
  const [clientInfo, setClientInfo] = useState<ClientInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchClientInfo = async () => {
      // 1. 優先從 URL 獲取 client_code
      const code = clientCodeFromUrl || localStorage.getItem('client_code')

      if (!code) {
        setIsLoading(false)
        return
      }

      setClientCode(code)

      // 2. 檢查 localStorage 是否有客戶名稱
      const cachedName = localStorage.getItem('client_name')
      const cachedInfoStr = localStorage.getItem('client_info')

      if (cachedName && cachedInfoStr) {
        try {
          const cachedInfo = JSON.parse(cachedInfoStr)
          // 確保快取的資料是當前 client_code 的
          if (cachedInfo.internal_code === code) {
            setClientName(cachedName)
            setClientInfo(cachedInfo)
            setIsLoading(false)
            return
          }
        } catch (err) {
          console.error('Failed to parse cached client_info:', err)
        }
      }

      // 3. 從後端 API 獲取客戶資訊
      try {
        // 🔥 使用簡單的映射表（暫時方案）
        // 理想情況下應該調用後端 API
        const clientMapping: Record<string, ClientInfo> = {
          snowland: {
            internal_code: 'snowland',
            name: '雪域創遊',
            sales: '張三',
            program: '標準方案'
          },
          testski: {
            internal_code: 'testski',
            name: '測試滑雪學校',
            sales: '李四',
            program: '進階方案'
          }
        }

        const info = clientMapping[code]
        if (info) {
          setClientName(info.name)
          setClientInfo(info)
          // 存入 localStorage
          localStorage.setItem('client_name', info.name)
          localStorage.setItem('client_info', JSON.stringify(info))
        } else {
          // 找不到對應的客戶，使用預設值
          setClientName(`${code} 預約系統`)
        }
      } catch (err) {
        console.error('Failed to fetch client info:', err)
        setClientName(`${code} 預約系統`)
      } finally {
        setIsLoading(false)
      }
    }

    fetchClientInfo()
  }, [clientCodeFromUrl])

  return {
    clientCode,
    clientName,
    clientInfo,
    isLoading,
  }
}
