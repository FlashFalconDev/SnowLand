import { useState, useEffect } from 'react'

interface User {
  email: string
  name?: string
  picture?: string
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
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

      // 檢查localStorage是否有用戶資訊
      const savedUser = localStorage.getItem('user')
      if (savedUser) {
        setUser(JSON.parse(savedUser))
        setLoading(false)
        return
      }

      // 一律走相對路徑（同 origin），由 vite proxy 或 nginx 轉發至後端
      const clientCode = localStorage.getItem('client_code') || 'snowland'
      const response = await fetch(`/booking/${clientCode}/api/google-login/`, {
        credentials: 'include', // 重要：包含cookies
      })

      if (response.ok) {
        const data = await response.json()
        if (data.code === 200 && data.user) {
          const userData = {
            email: data.user.email,
            name: data.user.name,
            picture: data.user.picture,
          }
          setUser(userData)
          localStorage.setItem('user', JSON.stringify(userData))
        }
      }
    } catch (error) {
      console.error('檢查登入狀態失敗:', error)
    } finally {
      setLoading(false)
    }
  }

  const logout = async (redirectTo?: string) => {
    // 預設跳回 client 首頁；後台呼叫時可傳 redirectTo 留在後台
    const computeFallback = () => {
      const clientCode = localStorage.getItem('client_code')
      return clientCode ? `/${clientCode}` : '/'
    }

    try {
      // 一律走相對路徑
      await fetch(`/control/api/logout/`, {
        method: 'POST',
        credentials: 'include',
      })
    } catch (error) {
      console.error('登出失敗:', error)
    } finally {
      // 不論成功或失敗都清掉前端狀態並跳轉
      localStorage.removeItem('user')
      localStorage.setItem('just_logged_out', 'true')
      setUser(null)
      window.location.href = redirectTo || computeFallback()
    }
  }

  return { user, loading, logout, checkAuth }
}
