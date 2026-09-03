/**
 * SnowLand 管理後台 Layout
 *
 * 完全複製自 FlashFalcon Console 的 AdminLayout，差異：
 *   - 主色 #8b5cf6 → #2b5f8f
 *   - 移除 console 的 API 邏輯（permissions、navConfig、login）
 *   - NAV 寫死成 SnowLand 業務（教練/雪場/CMS/評論）
 *   - 用 SnowLand 自己的 useAuth + SiteBasePathContext
 */
import { useState, useEffect, useContext } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Settings, ChevronDown, Menu, X, Bell, Users,
  LogOut, Sun, Moon, MessageCircle, FileText,
  BarChart3, Globe, BookOpen, ClipboardCheck, type LucideIcon,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
// @ts-ignore
import { SiteBasePathContext } from '@/components/site/SiteLink'
import { ThemeProvider, useTheme, NotificationProvider } from '../context'
import { GlobalNotification } from '../components/GlobalNotification'
import LoginPage from '@/pages/LoginPage'
import { fetchAdminMe, type AdminMeResult } from '../api/auth'
import { hasAdminPermission } from '../permissions'
import { fetchNotificationDeliveries } from '../api/operations'

// 主色 — 完全採用 console 配色（紫色 #8b5cf6）
const PRIMARY = '#8b5cf6'

// ============== NAV 結構 ==============
interface NavItem {
  id: string
  label: string
  icon: LucideIcon
  path?: string
  permission?: string
  badge?: string | number
  children?: { id: string; label: string; path: string; permission?: string; badge?: string }[]
}

// ============== 通知鈴鐺（從 console 完整移植）==============
interface NotifItem {
  id: number
  type: 'order' | 'member' | 'system' | 'reserve'
  title: string
  message: string
  is_read: boolean
  created_at: string
  link?: string
}

function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false)
  const [notifications, setNotifications] = useState<NotifItem[]>([])

  const unreadCount = notifications.filter((n) => !n.is_read).length

  useEffect(() => {
    if (isOpen) {
      fetchNotificationDeliveries().then((items) => {
        setNotifications(items.slice(0, 20).map((item) => ({
          id: item.id,
          type: item.status === 'failed' ? 'system' : 'reserve',
          title: item.status === 'failed' ? '通知發送失敗' : item.template_name,
          message: `${item.order_number} · ${item.recipient}${item.error_message ? ` · ${item.error_message}` : ''}`,
          is_read: item.status === 'sent',
          created_at: item.sent_at || item.scheduled_at,
          link: 'notifications',
        })))
      }).catch(() => setNotifications([]))
    }
  }, [isOpen])

  const markAsRead = (id: number) => {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)))
  }

  const markAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  const getTypeColor = (type: NotifItem['type']) => {
    switch (type) {
      case 'order': return 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
      case 'member': return 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400'
      case 'system': return 'bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400'
      case 'reserve': return 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
      default: return 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
    }
  }

  const getTypeName = (type: NotifItem['type']) => {
    switch (type) {
      case 'order': return '訂單'
      case 'member': return '會員'
      case 'system': return '系統'
      case 'reserve': return '預約'
      default: return '通知'
    }
  }

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)
    if (minutes < 1) return '剛剛'
    if (minutes < 60) return `${minutes} 分鐘前`
    if (hours < 24) return `${hours} 小時前`
    if (days < 7) return `${days} 天前`
    return date.toLocaleDateString()
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg relative"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 min-w-[16px] h-4 px-1 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />

          <div className="absolute right-0 top-full mt-2 w-80 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg z-50 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
              <h3 className="font-semibold text-gray-900 dark:text-white">通知</h3>
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="text-xs hover:opacity-80 transition-opacity"
                  style={{ color: PRIMARY }}
                >
                  全部標為已讀
                </button>
              )}
            </div>

            <div className="max-h-80 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="py-8 text-center text-gray-500 dark:text-gray-400">
                  <Bell size={32} className="mx-auto mb-2 opacity-50" />
                  <p>目前沒有通知</p>
                </div>
              ) : (
                notifications.map((notification) => (
                  <div
                    key={notification.id}
                    onClick={() => markAsRead(notification.id)}
                    className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 last:border-0 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                    style={!notification.is_read ? { backgroundColor: `${PRIMARY}0d` } : undefined}
                  >
                    <div className="flex items-start gap-3">
                      <span className={`px-2 py-0.5 text-xs rounded-full flex-shrink-0 ${getTypeColor(notification.type)}`}>
                        {getTypeName(notification.type)}
                      </span>
                      {!notification.is_read && (
                        <span
                          className="w-2 h-2 rounded-full flex-shrink-0 mt-1.5"
                          style={{ backgroundColor: PRIMARY }}
                        />
                      )}
                    </div>
                    <h4 className="font-medium text-gray-900 dark:text-white mt-1.5 text-sm">
                      {notification.title}
                    </h4>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                      {notification.message}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">{formatTime(notification.created_at)}</p>
                  </div>
                ))
              )}
            </div>

            {notifications.length > 0 && (
              <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
                <button
                  className="w-full text-center text-sm hover:opacity-80 transition-opacity"
                  style={{ color: PRIMARY }}
                >
                  查看全部通知
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ============== 側邊欄項目（從 console 完整移植，主色換成 PRIMARY）==============
function SidebarItem({
  item,
  collapsed,
  isExpanded,
  onToggle,
}: {
  item: NavItem
  collapsed: boolean
  isExpanded: boolean
  onToggle: () => void
}) {
  const location = useLocation()
  const [showPopup, setShowPopup] = useState(false)
  const hasChildren = item.children && item.children.length > 0

  const isActive = item.path
    ? location.pathname === item.path
    : item.children?.some((child) => location.pathname === child.path || location.pathname.startsWith(child.path + '/'))

  // 收合 + 有子選單 → hover popup
  if (hasChildren && collapsed) {
    return (
      <div
        className="relative"
        onMouseEnter={() => setShowPopup(true)}
        onMouseLeave={() => setShowPopup(false)}
      >
        <button
          type="button"
          className="w-full flex items-center justify-center p-2.5 rounded-lg transition-all cursor-pointer text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
          style={isActive ? { backgroundColor: `${PRIMARY}1a`, color: PRIMARY } : undefined}
        >
          <item.icon size={20} className={isActive ? '' : 'text-gray-400'} style={isActive ? { color: PRIMARY } : undefined} />
        </button>

        {showPopup && (
          <>
            <div className="absolute left-full top-0 w-2 h-full" />
            <div className="absolute left-full top-0 ml-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-2 min-w-[160px] z-[100]">
              <div className="px-3 py-2 text-sm font-medium text-gray-900 dark:text-white border-b border-gray-100 dark:border-gray-700 flex items-center gap-2">
                <item.icon size={16} style={{ color: PRIMARY }} />
                {item.label}
              </div>
              <div className="py-1">
                {item.children?.map((child) => (
                  <NavLink
                    key={child.id}
                    to={child.path}
                    end
                    className={({ isActive }) =>
                      `block px-3 py-2 text-sm transition-all no-underline ${
                        isActive ? 'text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                      }`
                    }
                    style={({ isActive }) => (isActive ? { backgroundColor: PRIMARY } : undefined)}
                    onClick={() => setShowPopup(false)}
                  >
                    {child.label}
                  </NavLink>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    )
  }

  // 展開 + 有子選單
  if (hasChildren) {
    return (
      <div>
        <button
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onToggle()
          }}
          type="button"
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all cursor-pointer text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
          style={isActive ? { backgroundColor: `${PRIMARY}1a`, color: PRIMARY } : undefined}
        >
          <item.icon size={20} className={isActive ? '' : 'text-gray-400'} style={isActive ? { color: PRIMARY } : undefined} />
          <span className="flex-1 text-sm font-medium">{item.label}</span>
          {item.badge && (
            <span
              className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                typeof item.badge === 'number' ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'
              }`}
            >
              {item.badge}
            </span>
          )}
          <ChevronDown
            size={16}
            className={`transition-transform duration-200 ${isExpanded ? 'rotate-0' : '-rotate-90'}`}
          />
        </button>
        <div
          className={`ml-8 mt-1 space-y-1 overflow-hidden transition-all duration-200 ${
            isExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
          }`}
        >
          {item.children?.map((child) => (
            <NavLink
              key={child.id}
              to={child.path}
              end
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all no-underline ${
                  isActive ? 'text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`
              }
              style={({ isActive }) => (isActive ? { backgroundColor: PRIMARY } : undefined)}
            >
              <span className="flex-1">{child.label}</span>
              {child.badge && (
                <span className="text-xs px-1.5 py-0.5 bg-red-100 text-red-600 rounded-full">{child.badge}</span>
              )}
            </NavLink>
          ))}
        </div>
      </div>
    )
  }

  // 收合 + 無子選單 → tooltip
  if (collapsed) {
    return (
      <div className="relative group">
        <NavLink
          to={item.path!}
          end={item.id === 'dashboard'}
          className={({ isActive }) =>
            `flex items-center justify-center p-2.5 rounded-lg transition-all no-underline ${
              isActive ? 'text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`
          }
          style={({ isActive }) => (isActive ? { backgroundColor: PRIMARY } : undefined)}
        >
          <item.icon size={20} />
        </NavLink>
        <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
          {item.label}
        </div>
      </div>
    )
  }

  // 展開 + 無子選單
  return (
    <NavLink
      to={item.path!}
      end={item.id === 'dashboard'}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all no-underline ${
          isActive ? 'text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
        }`
      }
      style={({ isActive }) => (isActive ? { backgroundColor: PRIMARY } : undefined)}
    >
      <item.icon size={20} />
      <span className="text-sm font-medium">{item.label}</span>
    </NavLink>
  )
}

// ============== 主題切換按鈕 ==============
function ThemeToggleButton() {
  const { isDark, toggleTheme } = useTheme()
  return (
    <button
      onClick={toggleTheme}
      className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
      title={isDark ? '切換淺色模式' : '切換深色模式'}
    >
      {isDark ? <Sun size={20} /> : <Moon size={20} />}
    </button>
  )
}

// ============== 主 Layout ==============
function AdminLayoutContent() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, loading: authLoading, logout } = useAuth()
  const basePath = useContext(SiteBasePathContext) // e.g. "/snowland"

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [expandedMenus, setExpandedMenus] = useState<Record<string, boolean>>({})

  // 檢查當前登入的使用者是否有 manager 權限
  const [adminCheck, setAdminCheck] = useState<AdminMeResult | null>(null)
  const [campusScope, setCampusScope] = useState(() => localStorage.getItem('snowland_admin_campus_scope') || 'all')
  useEffect(() => {
    if (!user) {
      setAdminCheck(null)
      return
    }
    fetchAdminMe().then(setAdminCheck)
  }, [user])

  useEffect(() => {
    const adminUser = adminCheck?.user
    if (!adminUser || adminUser.can_view_all_campuses || !adminUser.campuses?.length) return
    const allowed = new Set(adminUser.campuses.map((campus) => String(campus.id)))
    if (!allowed.has(campusScope)) {
      const onlyCampus = String(adminUser.campuses[0].id)
      localStorage.setItem('snowland_admin_campus_scope', onlyCampus)
      setCampusScope(onlyCampus)
    }
  }, [adminCheck, campusScope])

  const changeCampusScope = (value: string) => {
    localStorage.setItem('snowland_admin_campus_scope', value)
    setCampusScope(value)
    window.location.reload()
  }

  // 一進 console 頁面就把 pre_login_url 設好（不論有沒有登入）
  // 這樣 GoogleLoginButton 登入完一定會跳回後台
  useEffect(() => {
    if (typeof window !== 'undefined' && location.pathname.includes('/console')) {
      localStorage.setItem('pre_login_url', location.pathname)
    }
  }, [location.pathname])

  // 根據使用者角色組 NAV
  const isManager = !!(adminCheck?.user?.is_superuser || adminCheck?.user?.is_manager)
  const isCoach = !!(adminCheck?.user?.is_coach)
  const navPermissionById: Record<string, string> = {
    dashboard: 'analytics',
    orders: 'orders',
    scheduling: 'scheduling',
    customers: 'customers',
    'chat-support': 'chat_support',
    notifications: 'notifications',
    payroll: 'payroll',
    evaluations: 'evaluations',
    insurance: 'insurance_records',
    'booking-links': 'orders',
    resorts: 'resorts',
    campuses: 'campuses',
    'course-types': 'course_types',
    pricing: 'pricing',
    discounts: 'discounts',
    coaches: 'coaches',
    'coach-leaves': 'coaches',
    'payment-settings': 'payment_settings',
    staff: 'staff',
    'cms-homepage': 'cms',
    'cms-courses': 'cms',
    'cms-photography': 'cms',
    'cms-guides': 'cms',
    'cms-news': 'cms',
    'cms-about': 'cms',
    'cms-coaches': 'cms',
    'cms-resorts': 'cms',
    'cms-offers': 'cms',
    'cms-faq': 'cms',
    'cms-articles': 'cms',
    'reviews-google': 'reviews',
    'reviews-manual': 'reviews',
    media: 'reviews',
  }
  const canUseNavItem = (item: { id: string; permission?: string }) => {
    const permission = item.permission || navPermissionById[item.id]
    return !permission || hasAdminPermission(adminCheck?.user, permission)
  }
  const filterNavByPermission = (items: NavItem[]): NavItem[] =>
    items
      .map((item) => {
        if (item.children?.length) {
          const children = item.children.filter(canUseNavItem)
          return children.length ? { ...item, children } : null
        }
        return canUseNavItem(item) ? item : null
      })
      .filter((item): item is NavItem => Boolean(item))

  const managerNav: NavItem[] = [
    { id: 'dashboard', label: '主面板', icon: LayoutDashboard, path: `${basePath}/console` },
    { id: 'customers', label: '會員', icon: Users, path: `${basePath}/console/customers` },
    {
      id: 'operations',
      label: '營運管理',
      icon: BarChart3,
      children: [
        { id: 'orders', label: '訂單管理', path: `${basePath}/console/orders` },
        { id: 'scheduling', label: '排課管理', path: `${basePath}/console/scheduling` },
        { id: 'chat-support', label: 'AI 客服', path: `${basePath}/console/chat-support` },
        { id: 'notifications', label: '自動通知', path: `${basePath}/console/notifications` },
        { id: 'payroll', label: '薪資結算', path: `${basePath}/console/payroll` },
        { id: 'evaluations', label: '學習評量', path: `${basePath}/console/evaluations` },
        { id: 'insurance', label: '保險與聲明書', path: `${basePath}/console/insurance` },
        { id: 'booking-links', label: '代客訂課連結', path: `${basePath}/console/booking-links` },
      ],
    },
    {
      id: 'settings',
      label: '基本設定',
      icon: Settings,
      children: [
        { id: 'campuses', label: '校區與營運規則', path: `${basePath}/console/campuses` },
        { id: 'resorts', label: '雪場管理', path: `${basePath}/console/resorts` },
        { id: 'course-types', label: '課程架構', path: `${basePath}/console/course-types` },
        { id: 'pricing', label: '課程定價', path: `${basePath}/console/pricing` },
        { id: 'discounts', label: '優惠折扣', path: `${basePath}/console/discounts` },
        { id: 'coaches', label: '教練管理', path: `${basePath}/console/coaches` },
        { id: 'coach-leaves', label: '請假審核', path: `${basePath}/console/coaches/leaves` },
        { id: 'payment-settings', label: '付款設定', path: `${basePath}/console/payment-settings` },
        { id: 'staff', label: '員工權限', path: `${basePath}/console/staff` },
      ],
    },
    {
      id: 'cms',
      label: '官網內容',
      icon: FileText,
      children: [
        { id: 'cms-homepage', label: '首頁', path: `${basePath}/console/cms/homepage` },
        { id: 'cms-courses', label: '滑雪課程', path: `${basePath}/console/cms/courses` },
        { id: 'cms-photography', label: '海外攝影', path: `${basePath}/console/cms/photography` },
        { id: 'cms-guides', label: '滑雪攻略', path: `${basePath}/console/cms/guides` },
        { id: 'cms-news', label: '最新消息', path: `${basePath}/console/cms/news` },
        { id: 'cms-about', label: '關於 Snowland', path: `${basePath}/console/cms/about` },
        { id: 'cms-coaches', label: '教練資料', path: `${basePath}/console/cms/coaches` },
      ],
    },
    {
      id: 'reviews',
      label: '評論與媒體',
      icon: MessageCircle,
      children: [
        { id: 'reviews-google', label: 'Google 評論', path: `${basePath}/console/reviews/google` },
        { id: 'reviews-manual', label: '學員心得', path: `${basePath}/console/reviews/manual` },
        { id: 'media', label: '圖庫管理', path: `${basePath}/console/media` },
      ],
    },
  ]

  // 教練視角 NAV（教練自己看自己的）
  const coachNav: NavItem[] = [
    {
      id: 'my-courses',
      label: '我的課程',
      icon: BookOpen,
      children: [
        { id: 'my-pending', label: '待確認課程', path: `${basePath}/console/my/pending` },
        { id: 'my-courses-list', label: '我的所有課程', path: `${basePath}/console/my/courses` },
        { id: 'my-calendar', label: '我的月曆', path: `${basePath}/console/my/calendar` },
      ],
    },
    {
      id: 'my-leaves',
      label: '請假',
      icon: ClipboardCheck,
      children: [
        { id: 'my-apply-leave', label: '申請請假', path: `${basePath}/console/my/leaves/apply` },
        { id: 'my-leaves-list', label: '我的請假紀錄', path: `${basePath}/console/my/leaves` },
      ],
    },
  ]

  // 組合 NAV：manager 看全部 + 教練選單 / coach 只看教練選單
  let navItems: NavItem[] = []
  if (isManager) {
    navItems = filterNavByPermission(managerNav)
    if (isCoach) {
      // manager 同時是 coach → 管理主選單優先，教練視角放後面
      navItems = [...navItems, ...coachNav]
    }
  } else if (isCoach) {
    navItems = [...coachNav]
  }

  // 切換選單展開（單選模式）
  const toggleMenu = (menuId: string) => {
    setExpandedMenus((prev) => {
      if (prev[menuId]) return { ...prev, [menuId]: false }
      const newState: Record<string, boolean> = {}
      navItems.forEach((item) => {
        newState[item.id] = item.id === menuId
      })
      return newState
    })
  }

  // 進入頁面自動展開所在區塊
  useEffect(() => {
    const currentMenu = navItems.find((item) =>
      item.children?.some((child) => location.pathname === child.path || location.pathname.startsWith(child.path + '/'))
    )
    if (currentMenu) {
      setExpandedMenus((prev) => (prev[currentMenu.id] ? prev : { ...prev, [currentMenu.id]: true }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  // ============== 認證檢查 ==============
  // 載入中：spinner
  if (authLoading || (user && adminCheck === null)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="w-12 h-12 border-4 rounded-full animate-spin mx-auto mb-4" style={{ borderColor: `${PRIMARY}33`, borderTopColor: PRIMARY }} />
          <p className="text-sm text-gray-500 dark:text-gray-400">驗證中...</p>
        </div>
      </div>
    )
  }

  // 未登入：顯示預約系統的 Google 登入頁
  // pre_login_url 已在上面 useEffect 設好，登入完會跳回 admin
  if (!user) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <LoginPage />
      </div>
    )
  }

  // 已登入但 /me/ 沒回成功：顯示無權限頁（含詳細錯誤）
  if (adminCheck && !adminCheck.user) {
    return (
      <NoManagerPermission
        user={user}
        onLogout={() => logout(`${basePath}/console`)}
        basePath={basePath}
        errorCode={adminCheck.errorCode}
        errorMsg={adminCheck.errorMsg}
      />
    )
  }

  return (
    <div className="admin-shell min-h-screen bg-gray-50 text-gray-900 dark:bg-gray-900 dark:text-gray-100">
      <GlobalNotification />

      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* 側邊欄 */}
      <aside
        className={`fixed top-0 left-0 h-full bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 z-50 transition-all duration-300 flex flex-col ${
          sidebarCollapsed ? 'w-16 overflow-visible' : 'w-64'
        } ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-gray-100 dark:border-gray-700">
          {!sidebarCollapsed && (
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold text-sm"
                style={{ backgroundColor: PRIMARY }}
              >
                雪
              </div>
              <span className="font-bold text-gray-900 dark:text-white truncate">SnowLand</span>
            </div>
          )}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg hidden md:block flex-shrink-0"
          >
            <Menu size={18} />
          </button>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 md:hidden flex-shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className={`flex-1 p-3 space-y-1 ${sidebarCollapsed ? 'overflow-visible' : 'overflow-y-auto'}`}>
          {navItems.map((item) => (
            <SidebarItem
              key={item.id}
              item={item}
              collapsed={sidebarCollapsed}
              isExpanded={!!expandedMenus[item.id]}
              onToggle={() => toggleMenu(item.id)}
            />
          ))}
        </nav>

        {/* User 區 */}
        {!sidebarCollapsed && (
          <div className="p-3 border-t border-gray-100 dark:border-gray-700">
            <button
              type="button"
              onClick={() => navigate(`${basePath}/console/profile`)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              title="個人設定"
            >
              {user?.picture ? (
                <img
                  src={user.picture}
                  alt={user.name || ''}
                  className="w-8 h-8 rounded-full object-cover flex-shrink-0"
                />
              ) : (
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium flex-shrink-0"
                  style={{ backgroundColor: PRIMARY }}
                >
                  {(user?.name || user?.email || '?').charAt(0).toUpperCase()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {user?.name || '管理員'}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {user?.email}
                </div>
              </div>
            </button>
          </div>
        )}
      </aside>

      {/* 主內容區 */}
      <div className={`transition-all duration-300 ${sidebarCollapsed ? 'md:ml-16' : 'md:ml-64'}`}>
        {/* 頂部欄 */}
        <header className="h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-30 px-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg md:hidden"
            >
              <Menu size={20} />
            </button>
            <div className="min-w-0 flex-1">
              <PageBreadcrumb navItems={navItems} />
            </div>
          </div>

          <div className="flex items-center gap-2">
            {!!adminCheck?.user?.campuses?.length && (
              <label className="hidden sm:flex items-center gap-2 border border-gray-200 dark:border-gray-700 rounded-xl px-3 py-1.5 bg-gray-50 dark:bg-gray-900" title="切換後，所有管理頁只顯示這個校區的資料">
                <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">目前範圍</span>
                <select
                  aria-label="目前管理校區"
                  value={campusScope}
                  onChange={(event) => changeCampusScope(event.target.value)}
                  className="bg-transparent text-sm font-semibold text-gray-800 dark:text-gray-100 outline-none max-w-40"
                >
                  {adminCheck.user.can_view_all_campuses && <option value="all">全部校區</option>}
                  {adminCheck.user.campuses.map((campus) => <option key={campus.id} value={campus.id}>{campus.name}</option>)}
                </select>
              </label>
            )}
            <button
              onClick={() => navigate(basePath || '/')}
              className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              title="查看官網"
            >
              <Globe size={20} />
            </button>
            <NotificationBell />
            <ThemeToggleButton />
            <button
              onClick={() => logout(`${basePath}/console`)}
              className="p-2 text-gray-500 dark:text-gray-400 hover:bg-red-50 dark:hover:bg-red-900/30 hover:text-red-500 rounded-lg"
              title="登出"
            >
              <LogOut size={20} />
            </button>
          </div>
        </header>

        <main className="p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

// ============== 麵包屑 ==============
function PageBreadcrumb({ navItems }: { navItems: NavItem[] }) {
  const location = useLocation()

  // 找出目前所在的父項 + 子項
  let parent: NavItem | null = null
  let child: { id: string; label: string; path: string } | null = null

  for (const item of navItems) {
    if (!item.children) {
      if (item.path === location.pathname) {
        return (
          <h1 className="text-base font-semibold text-gray-900 dark:text-white truncate">
            {item.label}
          </h1>
        )
      }
      continue
    }
    for (const c of item.children) {
      if (location.pathname === c.path || location.pathname.startsWith(c.path + '/')) {
        parent = item
        child = c
        break
      }
    }
    if (parent) break
  }

  if (!parent || !child) {
    return <h1 className="text-base font-semibold text-gray-900 dark:text-white truncate">管理後台</h1>
  }

  return (
    <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
      <span className="text-gray-700 dark:text-gray-300">{parent.label}</span>
      <span aria-hidden>/</span>
      <span className="text-gray-900 dark:text-white font-medium">{child.label}</span>
    </div>
  )
}

// ============== 無 Manager 權限頁 ==============
function NoManagerPermission({
  user,
  onLogout,
  basePath,
  errorCode,
  errorMsg,
}: {
  user: { name?: string; email?: string; picture?: string }
  onLogout: () => Promise<void> | void
  basePath: string
  errorCode: number | null
  errorMsg: string
}) {
  // 401: session 失效（已登入但 cookie 沒被後端認可）→ 直接登出讓他重新走 OAuth
  // 403: 登入了但不是 manager → 顯示「無權限」訊息
  const is401 = errorCode === 401
  const is403 = errorCode === 403

  // 401 自動踢出去重新登入，不顯示嚇人的錯誤頁
  useEffect(() => {
    if (is401) {
      onLogout()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [is401])

  // 是否顯示工程師診斷區塊（只在 localhost 顯示）
  const isDev = typeof window !== 'undefined' && (
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1'
  )

  if (is401) {
    // 等 onLogout 跳轉中
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="w-12 h-12 border-4 rounded-full animate-spin mx-auto mb-4" style={{ borderColor: `${PRIMARY}33`, borderTopColor: PRIMARY }} />
          <p className="text-sm text-gray-500 dark:text-gray-400">重新導向登入中...</p>
        </div>
      </div>
    )
  }

  const title = is403 ? '無管理員權限' : '驗證失敗'
  const desc = is403
    ? '您的帳號目前沒有後台使用權限，請聯繫系統管理員為您開通'
    : '無法驗證您的身份，請稍後再試'

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
      <div className="w-full max-w-md bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 p-8">
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <svg className="w-8 h-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
        </div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-white text-center mb-2">{title}</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 text-center mb-6">{desc}</p>

        {/* 當前登入帳號 */}
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-3">
            {user.picture ? (
              <img src={user.picture} alt="" className="w-10 h-10 rounded-full object-cover" />
            ) : (
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center text-white font-medium"
                style={{ backgroundColor: PRIMARY }}
              >
                {(user.name || user.email || '?').charAt(0).toUpperCase()}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                {user.name || '使用者'}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{user.email}</div>
            </div>
          </div>
        </div>

        {/* 工程師診斷資訊（只在 dev 顯示）*/}
        {isDev && (
          <div className="bg-gray-100 dark:bg-gray-900 rounded-lg p-3 mb-6 text-xs font-mono text-gray-600 dark:text-gray-400">
            <div>HTTP {errorCode || '—'}</div>
            <div>{errorMsg || '(no message)'}</div>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={() => window.location.href = basePath || '/'}
            className="flex-1 px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600"
          >
            回首頁
          </button>
          <button
            onClick={() => onLogout()}
            className="flex-1 px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90"
            style={{ backgroundColor: PRIMARY }}
          >
            切換帳號
          </button>
        </div>
      </div>
    </div>
  )
}

// ============== 主要匯出 ==============
export default function AdminLayout() {
  return (
    <ThemeProvider>
      <NotificationProvider>
        <AdminLayoutContent />
      </NotificationProvider>
    </ThemeProvider>
  )
}
