import { useEffect, useState } from 'react'

export default function AuthCallbackPage() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('處理登入中...')

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // 檢查URL參數是否有錯誤
        const params = new URLSearchParams(window.location.search)
        const error = params.get('error')

        if (error) {
          setStatus('error')
          setMessage(`登入失敗：${error}`)
          setTimeout(() => {
            window.location.href = '/'
          }, 2000)
          return
        }

        // 走相對路徑（同 origin），避免跨站 cookie 問題
        const clientCode = localStorage.getItem('client_code') || 'snowland'
        const response = await fetch(`/booking/${clientCode}/api/google-login/`, {
          method: 'POST',
          credentials: 'include', // 重要：包含cookies
          headers: {
            'Content-Type': 'application/json',
          },
        })

        if (response.ok) {
          const data = await response.json()
          // 🔥 檢查 code 100 表示成功
          if (data.code === 100 && data.data) {
            const userData = {
              email: data.data.email,
              name: data.data.name,
              picture: data.data.picture,
            }
            // 保存用戶資訊到localStorage
            localStorage.setItem('user', JSON.stringify(userData))

            setStatus('success')
            setMessage('登入成功！正在跳轉...')

            // 🔥 跳轉回登入前的頁面
            const preLoginUrl = localStorage.getItem('pre_login_url')
            const clientCode = localStorage.getItem('client_code')
            localStorage.removeItem('pre_login_url')

            // 決定要跳轉到哪裡
            let redirectUrl = '/'
            if (preLoginUrl && preLoginUrl !== '/') {
              // 如果有記錄登入前的頁面，跳回去
              redirectUrl = preLoginUrl
            } else if (clientCode) {
              // 如果有 client_code，跳到該客戶的首頁
              redirectUrl = `/${clientCode}`
            }

            setTimeout(() => {
              window.location.href = redirectUrl
            }, 1000)
          } else {
            throw new Error('無法獲取用戶資訊')
          }
        } else {
          throw new Error('無法獲取用戶資訊')
        }
      } catch (err) {
        console.error('登入callback錯誤:', err)
        setStatus('error')
        setMessage('登入處理失敗，請重試')
        setTimeout(() => {
          window.location.href = '/'
        }, 2000)
      }
    }

    handleCallback()
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
        {status === 'loading' && (
          <>
            <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-primary-500 border-r-transparent mb-4"></div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">處理登入中</h2>
            <p className="text-gray-600">{message}</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
              <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">登入成功！</h2>
            <p className="text-gray-600">{message}</p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 mb-4">
              <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">登入失敗</h2>
            <p className="text-gray-600">{message}</p>
          </>
        )}
      </div>
    </div>
  )
}
