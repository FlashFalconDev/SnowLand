import { useClientInfo } from '../../hooks/useClient'
import { currentClientCode, tenantReturnPath } from '@/utils/tenant'
import { useEffect, useRef, useState } from 'react'
import { useSiteLocale } from '../../contexts/SiteLocale'

interface GoogleLoginButtonProps {
  onLogin?: () => void
}


declare global {
  interface Window {
    google: any
  }
}

let googleSdkInitialized = false
let googleSdkClientId = ''
let activeCredentialHandler: ((response: any) => void) | null = null

export default function GoogleLoginButton({ onLogin }: GoogleLoginButtonProps) {
  const {locale,t}=useSiteLocale()
  const {clientCode:schoolCode,clientInfo,isLoading:clientInfoLoading,error:clientInfoError}=useClientInfo()
  const GOOGLE_CLIENT_ID=clientInfo?.google_client_id || ''
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
      const clientCode = currentClientCode()
      if (clientCode !== schoolCode) return
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
      if (currentClientCode() !== clientCode) return

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
        const preLoginUrl = tenantReturnPath(localStorage.getItem('pre_login_url'), clientCode)
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
      setError(clientInfoLoading ? null : clientInfoError || 'Google 登入尚未完成設定')
      return
    }

    setError(null)
    let cancelled = false
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    let renderedWidth = 0
    activeCredentialHandler = handleCredentialResponse

    const renderGoogleButton = () => {
      const container = googleButtonRef.current
      if (!container || !window.google) return

      const width = Math.floor(container.getBoundingClientRect().width)
      if (width <= 0 || width === renderedWidth) return

      container.replaceChildren()
      window.google.accounts.id.renderButton(container, {
        theme: 'outline',
        size: 'large',
        width,
        text: 'signin_with',
        locale: locale==='zh-Hant'?'zh_TW':locale,
      })
      renderedWidth = width
    }
    const resizeObserver = new ResizeObserver(renderGoogleButton)
    if (googleButtonRef.current) resizeObserver.observe(googleButtonRef.current)

    // 等待 Google SDK 載入
    const initializeGoogleSignIn = () => {
      if (cancelled) return
      if (window.google) {
        if (!googleSdkInitialized || googleSdkClientId !== GOOGLE_CLIENT_ID) {
          window.google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: (response: any) => activeCredentialHandler?.(response),
            auto_select: false,
          })
          googleSdkInitialized = true
          googleSdkClientId = GOOGLE_CLIENT_ID
        }

        renderGoogleButton()
      } else {
        // Google SDK 還沒載入,等待一下再試
        retryTimer = setTimeout(initializeGoogleSignIn, 100)
      }
    }

    initializeGoogleSignIn()
    return () => {
      cancelled = true
      if (retryTimer) clearTimeout(retryTimer)
      resizeObserver.disconnect()
      if (activeCredentialHandler === handleCredentialResponse) activeCredentialHandler = null
    }
  }, [locale, GOOGLE_CLIENT_ID, clientInfoLoading, clientInfoError])

  return (
    <div className="w-full">
      {/* Google 按鈕容器 */}
      <div ref={googleButtonRef} className="w-full flex justify-center"></div>

      {/* 載入狀態 */}
      {isLoading && (
        <div className="mt-4 text-center text-sm text-gray-600">
          {t('登入中,請稍候...')}
        </div>
      )}

      {/* 錯誤訊息 */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {t(error)}
        </div>
      )}
    </div>
  )
}
