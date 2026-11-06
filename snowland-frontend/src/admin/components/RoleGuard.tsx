import { useEffect, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useContext } from 'react'
import { Lock, Loader2 } from 'lucide-react'
// @ts-ignore
import { SiteBasePathContext } from '@/components/site/SiteLink'
import { fetchAdminMe, type AdminUser } from '../api/auth'
import { canOpenConsolePage, type ConsolePage } from '../consoleNavigation'

export default function RoleGuard({ page }: { page: ConsolePage }) {
  const navigate = useNavigate()
  const location = useLocation()
  const basePath = useContext(SiteBasePathContext)
  const [user, setUser] = useState<AdminUser | null | undefined>(undefined)

  useEffect(() => {
    let active = true
    let revision = 0
    setUser(undefined)
    const refreshAccess = () => {
      const current = ++revision
      void fetchAdminMe().then(result => { if (active && current === revision) setUser(result.user) })
    }
    const refreshWhenVisible = () => { if (document.visibilityState === 'visible') refreshAccess() }
    refreshAccess()
    window.addEventListener('focus', refreshAccess)
    window.addEventListener('snowland:campuses-updated', refreshAccess)
    document.addEventListener('visibilitychange', refreshWhenVisible)
    return () => {
      active = false
      window.removeEventListener('focus', refreshAccess)
      window.removeEventListener('snowland:campuses-updated', refreshAccess)
      document.removeEventListener('visibilitychange', refreshWhenVisible)
    }
  }, [location.pathname])

  if (user === undefined) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} />
      </div>
    )
  }

  if (!user) {
    return (
      <NoAccess
        title="請先登入"
        message="您的登入狀態可能已失效"
        onAction={() => navigate(`${basePath}/console`)}
        actionLabel="重新登入"
      />
    )
  }

  if (!canOpenConsolePage(page, user, basePath)) {
    return (
      <NoAccess
        title="沒有功能權限"
        message="這個帳號沒有此功能權限。如需使用，請聯絡總部管理員。"
        onAction={() => navigate(`${basePath}/console`)}
        actionLabel="回到後台首頁"
      />
    )
  }

  return <Outlet />
}

const PRIMARY = '#8b5cf6'

function NoAccess({ title, message, onAction, actionLabel }: {
  title: string
  message: string
  onAction: () => void
  actionLabel: string
}) {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="max-w-md text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 mb-4">
          <Lock size={28} className="text-red-600 dark:text-red-400" />
        </div>
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">{title}</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">{message}</p>
        <button
          onClick={onAction}
          className="min-h-11 px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90"
          style={{ backgroundColor: PRIMARY }}
        >
          {actionLabel}
        </button>
      </div>
    </div>
  )
}
