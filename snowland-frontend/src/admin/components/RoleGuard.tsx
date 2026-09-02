/**
 * 路由守衛：根據使用者角色擋下沒權限的頁面
 *
 * 用法：
 *   <Route element={<RoleGuard requireManager />}>
 *     <Route path="orders" element={<OrdersPage />} />
 *   </Route>
 *
 *   <Route element={<RoleGuard requireCoach />}>
 *     <Route path="my/pending" element={<PendingConfirmationsPage />} />
 *   </Route>
 */
import { useEffect, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useContext } from 'react'
import { Lock, Loader2 } from 'lucide-react'
// @ts-ignore
import { SiteBasePathContext } from '@/components/site/SiteLink'
import { fetchAdminMe, type AdminUser } from '../api/auth'
import { hasAdminPermission } from '../permissions'

interface Props {
  requireManager?: boolean
  requireCoach?: boolean
  permission?: string
}

const PRIMARY = '#8b5cf6'

const PATH_PERMISSION_MAP: Array<[string, string]> = [
  ['/console/orders', 'orders'],
  ['/console/scheduling', 'scheduling'],
  ['/console/customers', 'customers'],
  ['/console/chat-support', 'chat_support'],
  ['/console/coaches', 'coaches'],
  ['/console/resorts', 'resorts'],
  ['/console/course-types', 'course_types'],
  ['/console/pricing', 'pricing'],
  ['/console/discounts', 'discounts'],
  ['/console/staff', 'staff'],
  ['/console/payment-settings', 'payment_settings'],
  ['/console/cms', 'cms'],
  ['/console/reviews', 'reviews'],
  ['/console/media', 'reviews'],
]

function inferPermissionFromPath(pathname: string): string {
  const match = PATH_PERMISSION_MAP.find(([path]) => pathname.includes(path))
  return match?.[1] || 'analytics'
}

export default function RoleGuard({ requireManager, requireCoach, permission }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const basePath = useContext(SiteBasePathContext)
  const [user, setUser] = useState<AdminUser | null | undefined>(undefined)

  useEffect(() => {
    fetchAdminMe().then((res) => setUser(res.user))
  }, [])

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

  // 檢查角色
  const isSuperuser = !!user.is_superuser
  const isManager = !!user.is_manager
  const isCoach = !!user.is_coach

  if (requireManager && !isSuperuser && !isManager) {
    return (
      <NoAccess
        title="無權限存取"
        message="此頁面僅限管理員使用"
        onAction={() => navigate(`${basePath}/console/my/pending`)}
        actionLabel="返回我的課程"
      />
    )
  }

  const requiredPermission = permission || (requireManager ? inferPermissionFromPath(location.pathname) : '')
  if (requiredPermission && !hasAdminPermission(user, requiredPermission)) {
    return (
      <NoAccess
        title="沒有功能權限"
        message="這個帳號尚未開啟此後台模組，請由 Superuser 到員工權限調整。"
        onAction={() => navigate(`${basePath}/console`)}
        actionLabel="回到後台首頁"
      />
    )
  }

  if (requireCoach && !isSuperuser && !isCoach) {
    return (
      <NoAccess
        title="無權限存取"
        message="此頁面僅限教練使用"
        onAction={() => navigate(`${basePath}/console`)}
        actionLabel="返回儀表板"
      />
    )
  }

  return <Outlet />
}

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
          className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90"
          style={{ backgroundColor: PRIMARY }}
        >
          {actionLabel}
        </button>
      </div>
    </div>
  )
}
