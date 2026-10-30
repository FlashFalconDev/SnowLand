import { currentClientCode } from '@/utils/tenant'
import { useState, useEffect, useRef } from 'react'

interface User {
  email: string
  name?: string
  picture?: string
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [logoutError, setLogoutError] = useState('')
  const [loggingOut, setLoggingOut] = useState(false)
  const logoutPending = useRef(false)
  const authRevision = useRef(0)

  useEffect(() => {
    checkAuth()
    return () => { authRevision.current += 1 }
  }, [])

  const checkAuth = async () => {
    if (logoutPending.current) return
    const revision = ++authRevision.current
    try {
      // 檢查是否剛登出
      const justLoggedOut = localStorage.getItem('just_logged_out')
      if (justLoggedOut) {
        // 清除標記
        localStorage.removeItem('just_logged_out')
        // 不檢查後端，直接設為未登入
        setUser(null)
        setLoading(false)
        return
      }

      // 選校首頁沒有租戶，不發送任何校內認證請求。
      if (window.location.pathname === '/') {
        setUser(null)
        return
      }

      // 只以後端 session 判定登入；localStorage 可能是已過期的舊資料。
      const clientCode = currentClientCode()
      const response = await fetch(`/booking/${clientCode}/api/google-login/`, {
        credentials: 'include', // 重要：包含cookies
      })
      if (revision !== authRevision.current || logoutPending.current) return

      if (response.ok) {
        const data = await response.json()
        if (revision !== authRevision.current || logoutPending.current) return
        if (data.code === 200 && data.user) {
          const userData = {
            email: data.user.email,
            name: data.user.name,
            picture: data.user.picture,
          }
          setUser(userData)
          localStorage.setItem('user', JSON.stringify(userData))
          return
        }
      }
      localStorage.removeItem('user')
      setUser(null)

      // 後台以自己的權限 API 為準；本機免登入模式也只作用於後台。
      if (window.location.pathname.includes('/console')) {
        const adminResponse = await fetch(`/api/admin/${clientCode}/me/`, { credentials: 'include' })
        if (revision !== authRevision.current || logoutPending.current) return
        if (adminResponse.ok) {
          const adminData = await adminResponse.json()
          if (revision !== authRevision.current || logoutPending.current) return
          if (adminData.code === 200 && adminData.data) {
            setUser({ email: adminData.data.email, name: adminData.data.name })
          }
        }
      }
    } catch (error) {
      if (revision !== authRevision.current || logoutPending.current) return
      console.error('檢查登入狀態失敗:', error)
    } finally {
      if (revision === authRevision.current && !logoutPending.current) setLoading(false)
    }
  }

  const logout = async (redirectTo?: string) => {
    if (logoutPending.current) return
    logoutPending.current = true
    authRevision.current += 1
    setLoggingOut(true)
    setLogoutError('')
    // 預設跳回 client 首頁；後台呼叫時可傳 redirectTo 留在後台
    const computeFallback = () => {
      try { return `/${currentClientCode()}` } catch { return '/' }
    }

    try {
      // 一律走相對路徑
      const csrf = document.cookie.split(';').map(value => value.trim()).find(value => value.startsWith('csrftoken='))
      const response = await fetch(`/control/api/logout/`, {
        method: 'POST',
        credentials: 'include',
        headers: csrf ? { 'X-CSRFToken': csrf.slice('csrftoken='.length) } : {},
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok || result.code !== 200) throw new Error('logout not confirmed')
      // 確認後端 session 已登出才清除前端狀態；整頁跳轉也會清掉查詢快取。
      localStorage.removeItem('user')
      localStorage.setItem('just_logged_out', 'true')
      setUser(null)
      window.location.href = redirectTo || computeFallback()
    } catch {
      setLogoutError('無法確認登出，請重試；確認成功前，請勿將裝置交給他人。')
    } finally {
      logoutPending.current = false
      setLoggingOut(false)
    }
  }

  return { user, loading, logout, checkAuth, logoutError, loggingOut }
}
