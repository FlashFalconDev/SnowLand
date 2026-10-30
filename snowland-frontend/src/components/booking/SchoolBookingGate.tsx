import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useClientInfo } from '@/hooks/useClient'
import { useSiteLocale } from '@/contexts/SiteLocale'
// @ts-ignore
import SiteHeader from '@/components/site/SiteHeader'
// @ts-ignore
import SiteFooter from '@/components/site/SiteFooter'

export default function SchoolBookingGate({ children }: { children: ReactNode }) {
  const { clientCode, clientInfo, isLoading, error } = useClientInfo()
  const { t } = useSiteLocale()
  if (isLoading) return <main className="flex min-h-screen items-center justify-center bg-[#f7f8fa]" role="status">{t('載入中…')}</main>
  if (!error && clientInfo && clientInfo.booking_enabled !== false) return <>{children}</>
  return <div className="min-h-screen bg-[#f7f8fa] text-[#1f2937]">
    <SiteHeader forceDarkText forceLogoColor forceCompact />
    <main className="mx-auto max-w-2xl px-6 pb-24 pt-36 text-center">
      <h1 className="text-2xl font-semibold">{t(error || !clientInfo ? '目前無法載入學校資料' : '目前暫停受理新預約')}</h1>
      <p className="mt-4 text-sm leading-7 text-[#64748b]">{t(error || !clientInfo ? '請重新載入，或確認學校提供的連結。' : '您仍可登入會員查看既有訂單；新預約請洽學校確認。')}</p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        {error || !clientInfo ? <button type="button" onClick={() => window.location.reload()} className="min-h-11 rounded-full border border-[#2b5f8f] px-5 py-3">{t('重新載入')}</button>
          : <Link to={`/${clientCode}/membership`} className="min-h-11 rounded-full bg-[#2b5f8f] px-5 py-3 text-white">{t('會員專區')}</Link>}
        <Link to={`/${clientCode}/`} className="min-h-11 rounded-full border border-[#2b5f8f] px-5 py-3">{t('返回首頁')}</Link>
      </div>
    </main>
    <SiteFooter />
  </div>
}
