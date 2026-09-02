import GoogleLoginButton from '@/components/auth/GoogleLoginButton'
import { Mountain, Award, CalendarCheck, Bot } from 'lucide-react'
import { useClientInfo } from '@/hooks/useClient'
import { useEffect } from 'react'

export default function LoginPage() {
  // 🔥 使用 hook 獲取客戶資訊
  const { clientName } = useClientInfo()

  // 🔥 更新頁面標題
  useEffect(() => {
    document.title = `${clientName} - 登入`
  }, [clientName])

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo和標題 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-primary-500 to-purple-500 mb-4 shadow-lg">
            <Mountain size={40} className="text-white" />
          </div>
          <h1 className="text-4xl font-bold text-gray-800 mb-2">
            {clientName}預約系統
          </h1>
          <p className="text-gray-600">
            請登入以開始預約您的滑雪課程
          </p>
        </div>

        {/* 登入卡片 */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">
              歡迎回來
            </h2>
            <p className="text-sm text-gray-600">
              使用您的Google帳號快速登入
            </p>
          </div>

          <GoogleLoginButton />

          {/* 說明文字 */}
          <div className="mt-6 text-center">
            <p className="text-xs text-gray-500">
              點擊「使用 Google 登入」即表示您同意我們的
              <br />
              服務條款和隱私政策
            </p>
          </div>
        </div>

        {/* 特色說明 */}
        <div className="mt-8 grid grid-cols-3 gap-4 text-center">
          {[
            { Icon: Award, text: '專業教練' },
            { Icon: CalendarCheck, text: '彈性預約' },
            { Icon: Bot, text: 'AI排課' },
          ].map((feature) => (
            <div key={feature.text} className="bg-white/60 backdrop-blur-sm rounded-lg p-3">
              <div className="flex justify-center mb-1">
                <feature.Icon size={24} className="text-primary-600" />
              </div>
              <div className="text-xs font-medium text-gray-700">{feature.text}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
