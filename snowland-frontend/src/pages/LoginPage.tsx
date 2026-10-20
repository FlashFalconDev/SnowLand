import GoogleLoginButton from '@/components/auth/GoogleLoginButton'
import { Mountain, Award, CalendarCheck, Bot } from 'lucide-react'
import { useClientInfo } from '@/hooks/useClient'
import { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useSiteLink } from '@/hooks/useSiteBasePath'
import { useSiteLocale } from '@/contexts/SiteLocale'

export default function LoginPage({ returnTo = 'booking' }: { returnTo?: 'booking' | 'console' }) {
  const { t, locale } = useSiteLocale()
  // 🔥 使用 hook 獲取客戶資訊
  const { clientName } = useClientInfo()
  const location = useLocation()
  const staffLink = new URLSearchParams(location.search).get('staff_link')
  const membershipParams = new URLSearchParams({ return_to: returnTo })
  if (staffLink) membershipParams.set('staff_link', staffLink)
  const membershipLoginUrl = useSiteLink(`/membership?${membershipParams}`)

  // 🔥 更新頁面標題
  useEffect(() => {
    const previousTitle = document.title
    const loginTitle = `${clientName} - ${t('會員登入')}`
    document.title = loginTitle
    return () => {
      if (document.title === loginTitle) document.title = previousTitle
    }
  }, [clientName, locale])

  useEffect(() => {
    if (returnTo === 'booking') {
      localStorage.setItem('pre_login_url', `${location.pathname}${location.search}`)
    }
  }, [location.pathname, location.search, returnTo, staffLink])

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo和標題 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-primary-500 to-purple-500 mb-4 shadow-lg">
            <Mountain size={40} className="text-white" />
          </div>
          <h1 className="text-balance text-3xl sm:text-4xl font-bold text-gray-800 mb-2">
            {t('{name}預約系統',{name:clientName})}
          </h1>
          <p className="text-gray-600">
            {t('請登入以開始預約您的滑雪課程')}
          </p>
        </div>

        {/* 登入卡片 */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">
              {t('歡迎回來')}
            </h2>
            <p className="text-sm text-gray-600">
              {t('選擇 Google 或 Email 登入')}
            </p>
          </div>

          <GoogleLoginButton />
          <Link to={membershipLoginUrl} className="mt-4 block rounded-full border border-[#2b5f8f] px-5 py-3 text-center text-sm font-semibold text-[#2b5f8f] hover:bg-[#eef4fa]">
            {t('使用 Email 登入或註冊')}
          </Link>

          {/* 說明文字 */}
          <div className="mt-6 text-center">
            <p className="text-xs text-gray-500">
              {t('點擊「使用 Google 登入」即表示您同意我們的')}
              <br />
              {t('服務條款和隱私政策')}
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
              <div className="text-xs font-medium text-gray-700">{t(feature.text)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
