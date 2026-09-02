import { useEffect, useRef, useState } from 'react'

interface GoogleLoginButtonProps {
  onLogin?: () => void
}

// 🔥 Google Client ID (請在 Google Cloud Console 設定)
const GOOGLE_CLIENT_ID = '754789081671-np8lbocgau68d4rers83v649bnm993vp.apps.googleusercontent.com'

declare global {
  interface Window {
    google: any
  }
}

export default function GoogleLoginButton({ onLogin }: GoogleLoginButtonProps) {
  const googleButtonRef = useRef<HTMLDivElement>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleCredentialResponse = async (response: any) => {
    console.log('=== Google Login Response ===')
    console.log('Response:', response)
    setIsLoading(true)
    setError(null)

    try {
      console.log('Sending credential to backend:', response.credential)

      const requestBody = JSON.stringify({
        credential: response.credential, // Google JWT token
      })

      console.log('Request body:', requestBody)

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

      console.log('Response status:', res.status)
      const responseText = await res.text()
      console.log('Response text:', responseText)

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
    // 等待 Google SDK 載入
    const initializeGoogleSignIn = () => {
      if (window.google) {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleCredentialResponse,
          auto_select: false,
        })

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
        setTimeout(initializeGoogleSignIn, 100)
      }
    }

    initializeGoogleSignIn()
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
