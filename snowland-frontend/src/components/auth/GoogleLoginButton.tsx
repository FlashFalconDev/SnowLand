import { useEffect, useRef, useState } from 'react'

interface GoogleLoginButtonProps {
  onLogin?: () => void
}

const GOOGLE_CLIENT_ID = (import.meta.env.VITE_GOOGLE_CLIENT_ID || '').trim()

declare global {
  interface Window {
    google: any
  }
}

let googleSdkInitialized = false
let activeCredentialHandler: ((response: any) => void) | null = null

export default function GoogleLoginButton({ onLogin }: GoogleLoginButtonProps) {
  const googleButtonRef = useRef<HTMLDivElement>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleCredentialResponse = async (response: any) => {
    setIsLoading(true)
    setError(null)

    try {
      const requestBody = JSON.stringify({
        credential: response.credential, // Google JWT token
      })

      // 走相對路徑（同 origin），由 vite proxy / nginx 轉到後端
      const clientCode = localStorage.getItem('client_code') || 'snowland'
      const res = await fetch(`/booking/${clientCode}/api/google-login/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: requestBody,
      })

      const responseText = await res.text()

      const data = JSON.parse(responseText)

      if (data.code === 100 && data.data) {
        // 保存用戶資訊
        const userData = {
          email: data.data.email,
          name: data.data.name,
          picture: data.data.picture,
        }
        localStorage.setItem('user', JSON.stringify(userData))

        if (onLogin) {
          onLogin()
        }

        // 跳轉到預約頁面
        const preLoginUrl = localStorage.getItem('pre_login_url') || '/snowland'
        localStorage.removeItem('pre_login_url')
        window.location.href = preLoginUrl
      } else {
        throw new Error(data.msg || '登入失敗')
      }
    } catch (err: any) {
      console.error('登入錯誤:', err)
      setError(err.message || '登入失敗,請重試')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) {
      setError('Google 登入尚未完成設定')
      return
    }

    let cancelled = false
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    activeCredentialHandler = handleCredentialResponse

    // 等待 Google SDK 載入
    const initializeGoogleSignIn = () => {
      if (cancelled) return
      if (window.google) {
        if (!googleSdkInitialized) {
          window.google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: (response: any) => activeCredentialHandler?.(response),
            auto_select: false,
          })
          googleSdkInitialized = true
        }

        // 渲染 Google 登入按鈕
        if (googleButtonRef.current) {
          window.google.accounts.id.renderButton(
            googleButtonRef.current,
            {
              theme: 'outline',
              size: 'large',
              width: googleButtonRef.current.offsetWidth,
              text: 'signin_with',
              locale: 'zh_TW',
            }
          )
        }
      } else {
        // Google SDK 還沒載入,等待一下再試
        retryTimer = setTimeout(initializeGoogleSignIn, 100)
      }
    }

    initializeGoogleSignIn()
    return () => {
      cancelled = true
      if (retryTimer) clearTimeout(retryTimer)
    }
  }, [])

  return (
    <div className="w-full">
      {/* Google 按鈕容器 */}
      <div ref={googleButtonRef} className="w-full flex justify-center"></div>

      {/* 載入狀態 */}
      {isLoading && (
        <div className="mt-4 text-center text-sm text-gray-600">
          登入中,請稍候...
        </div>
      )}

      {/* 錯誤訊息 */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}
    </div>
  )
}
