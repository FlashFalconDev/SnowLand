import { useClientInfo } from '@/hooks/useClient'
import { currentClientCode, campusScopeKey } from '@/utils/tenant'
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
  ChevronDown, Menu, X, Bell, LogOut, Sun, Moon, Globe, type LucideIcon,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
// @ts-ignore
import { SiteBasePathContext } from '@/components/site/SiteLink'
import { ThemeProvider, useTheme, NotificationProvider } from '../context'
import { GlobalNotification } from '../components/GlobalNotification'
import LoginPage from '@/pages/LoginPage'
import { fetchAdminMe, type AdminMeResult } from '../api/auth'
import { hasAdminPermission } from '../permissions'
import { canOpenConsolePage, consoleNavigation } from '../consoleNavigation'
import { fetchNotificationDeliveries } from '../api/operations'

// 主色 — 完全採用 console 配色（紫色 #8b5cf6）
const PRIMARY = '#8b5cf6'

// ============== NAV 結構 ==============
interface CompactMenu {
  id: string
  top: number
  left: number
}

interface NavItem {
  id: string
  label: string
  icon: LucideIcon
  hasSubmenu: boolean
  children: { id: string; label: string; path: string }[]
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
        aria-label="查看通知"
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

function SidebarItem({ item, collapsed, active, expanded, popup, onToggle, onOpen, onDismiss, onNavigate }: {
  item: NavItem
  collapsed: boolean
  active: boolean
  expanded: boolean
  popup?: CompactMenu
  onToggle: () => void
  onOpen: (trigger: HTMLButtonElement) => void
  onDismiss: () => void
  onNavigate: () => void
}) {
  const entryClassName = `flex min-h-11 w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors no-underline
    ${collapsed ? 'justify-center' : ''} ${active
      ? 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200'
      : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}`
  const entryLabel = <>
    <item.icon size={20} className="shrink-0" aria-hidden />
    {!collapsed && <span className="flex-1 text-sm font-medium">{item.label}</span>}
  </>

  if (!item.hasSubmenu) {
    return <NavLink
      to={item.children[0].path}
      end
      aria-label={item.label}
      title={collapsed ? item.label : undefined}
      className={entryClassName}
      onClick={onNavigate}
    >{entryLabel}</NavLink>
  }

  const submenuId = `console-submenu-${item.id}`
  const submenuVisible = collapsed ? !!popup : expanded
  return (
    <div
      onPointerLeave={event => {
        if (collapsed && event.pointerType === 'mouse' && !event.currentTarget.querySelector('ul')?.contains(document.activeElement)) {
          onDismiss()
        }
      }}
      onBlur={event => {
        if (collapsed && !event.currentTarget.contains(event.relatedTarget)) onDismiss()
      }}
      onKeyDown={event => {
        if (collapsed && submenuVisible && event.key === 'Escape') {
          event.stopPropagation()
          event.currentTarget.querySelector('button')?.focus()
          onDismiss()
        }
      }}
    >
      <button
        type="button"
        aria-label={item.label}
        aria-expanded={submenuVisible}
        aria-controls={submenuId}
        title={collapsed ? item.label : undefined}
        className={entryClassName}
        onPointerEnter={event => {
          if (collapsed && event.pointerType === 'mouse') onOpen(event.currentTarget)
        }}
        onClick={event => {
          if (collapsed) onOpen(event.currentTarget)
          else onToggle()
        }}
      >
        {entryLabel}
        {!collapsed && <ChevronDown size={16} aria-hidden className={`shrink-0 transition-transform ${expanded ? '' : '-rotate-90'}`} />}
      </button>
      <div
        id={submenuId}
        hidden={!submenuVisible}
        className={collapsed
          ? 'fixed z-50 w-56 pl-3'
          : 'mb-2 ml-5 mt-1 border-l border-gray-200 pl-2 dark:border-gray-700'}
        style={collapsed ? { top: popup?.top, left: popup?.left } : undefined}
      >
        <div className={collapsed ? 'flex max-h-[calc(100dvh-1rem)] flex-col rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-800' : undefined}>
          {collapsed && <div className="flex min-h-10 shrink-0 items-center gap-2 border-b border-gray-100 px-3 text-sm font-semibold dark:border-gray-700">
            <item.icon size={16} className="text-violet-500" aria-hidden />
            {item.label}
          </div>}
          <ul className={collapsed ? 'min-h-0 overflow-y-auto p-1' : 'space-y-1'}>
            {item.children.map(child => (
              <li key={child.id}>
                <NavLink
                  to={child.path}
                  end
                  onClick={onNavigate}
                  className={({ isActive }) => `flex items-center rounded-lg px-3 py-2 text-sm no-underline ${collapsed ? 'min-h-10' : 'min-h-11'} ${isActive
                    ? 'bg-violet-700 font-semibold text-white'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'}`}
                >{child.label}</NavLink>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
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
  const { clientName, clientInfo } = useClientInfo()
  const navigate = useNavigate()
  const location = useLocation()
  const { user, loading: authLoading, logout, logoutError, loggingOut } = useAuth()
  const basePath = useContext(SiteBasePathContext) // e.g. "/snowland"

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [expandedGroup, setExpandedGroup] = useState<string | null>()
  const [compactMenu, setCompactMenu] = useState<CompactMenu | null>(null)

  // 檢查當前登入的使用者是否有 manager 權限
  const [adminCheck, setAdminCheck] = useState<AdminMeResult | null>(null)
  const [campusScope, setCampusScope] = useState(() => localStorage.getItem(campusScopeKey(currentClientCode())) || 'all')
  useEffect(() => {
    if (!user) {
      setAdminCheck(null)
      return
    }
    let active = true
    let revision = 0
    setAdminCheck(null)
    const refreshAdminScope = () => {
      const current = ++revision
      void fetchAdminMe().then(result => { if (active && current === revision) setAdminCheck(result) })
    }
    const refreshWhenVisible = () => { if (document.visibilityState === 'visible') refreshAdminScope() }
    refreshAdminScope()
    window.addEventListener('snowland:campuses-updated', refreshAdminScope)
    window.addEventListener('focus', refreshAdminScope)
    document.addEventListener('visibilitychange', refreshWhenVisible)
    return () => {
      active = false
      window.removeEventListener('snowland:campuses-updated', refreshAdminScope)
      window.removeEventListener('focus', refreshAdminScope)
      document.removeEventListener('visibilitychange', refreshWhenVisible)
    }
  }, [user, location.pathname])

  useEffect(() => {
    const adminUser = adminCheck?.user
    if (!adminUser) return
    const ownerKey = `${campusScopeKey(currentClientCode())}:owner`
    if (localStorage.getItem(ownerKey) !== String(adminUser.id)) {
      const defaultScope = adminUser.can_view_all_campuses ? 'all' : String(adminUser.campuses?.[0]?.id || 'all')
      localStorage.setItem(ownerKey, String(adminUser.id))
      localStorage.setItem(campusScopeKey(currentClientCode()), defaultScope)
      setCampusScope(defaultScope)
      if (campusScope !== defaultScope) window.location.reload()
      return
    }
    const allowed = new Set((adminUser.campuses || []).map((campus) => String(campus.id)))
    if (!adminUser.can_view_all_campuses && !allowed.size) return
    if ((campusScope !== 'all' && !allowed.has(campusScope)) ||
        (campusScope === 'all' && !adminUser.can_view_all_campuses && allowed.size)) {
      const fallbackScope = adminUser.can_view_all_campuses ? 'all' : String(adminUser.campuses?.[0]?.id)
      localStorage.setItem(campusScopeKey(currentClientCode()), fallbackScope)
      setCampusScope(fallbackScope)
      window.location.reload()
    }
  }, [adminCheck, campusScope])

  const changeCampusScope = (value: string) => {
    localStorage.setItem(campusScopeKey(currentClientCode()), value)
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
  const isPersonalCoachPage = location.pathname.startsWith(`${basePath}/console/my/`)
  const displayUser = adminCheck?.user
    ? { ...user, ...adminCheck.user, picture: user?.picture }
    : user
  const consolePath = `${basePath}/console`
  const navItems: NavItem[] = consoleNavigation.flatMap(group => {
    const children = group.pages
      .filter(page => canOpenConsolePage(page, adminCheck?.user, basePath))
      .map(page => ({ id: page.path, label: page.label, path: page.path ? `${consolePath}/${page.path}` : consolePath }))
    return children.length ? [{
      id: group.id,
      label: group.label,
      icon: group.icon,
      hasSubmenu: (group.id === 'overview' ? children.length > 1 || children[0].id !== '' : group.pages.length > 1) || group.id === 'system',
      children,
    }] : []
  })
  const pathname = location.pathname.replace(/\/$/, '')
  const currentGroup = navItems.find(item => item.children.some(child => child.path === pathname))
  const visibleGroup = expandedGroup === undefined ? currentGroup?.id : expandedGroup
  const firstAvailablePath = navItems[0]?.children[0].path

  const openCompactMenu = (item: NavItem, trigger: HTMLButtonElement) => {
    const { top, right } = trigger.getBoundingClientRect()
    const estimatedHeight = 50 + item.children.length * 40
    setCompactMenu({
      id: item.id,
      top: Math.max(8, Math.min(top, window.innerHeight - estimatedHeight - 8)),
      left: right,
    })
  }

  useEffect(() => {
    if (adminCheck?.user && pathname === consolePath && firstAvailablePath && firstAvailablePath !== consolePath) {
      navigate(firstAvailablePath, { replace: true })
    }
  }, [adminCheck, consolePath, firstAvailablePath, pathname, navigate])

  useEffect(() => {
    setMobileMenuOpen(false)
    setExpandedGroup(undefined)
    setCompactMenu(null)
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
        <LoginPage returnTo="console" />
      </div>
    )
  }

  // 已登入但 /me/ 沒回成功：顯示無權限頁（含詳細錯誤）
  if (adminCheck && !adminCheck.user) {
    return (
      <NoManagerPermission
        user={user}
        onLogout={() => logout(`${basePath}/console`)}
        logoutError={logoutError}
        loggingOut={loggingOut}
        onRetry={() => { setAdminCheck(null); void fetchAdminMe().then(setAdminCheck) }}
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
        className={`fixed top-0 left-0 h-full bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 z-50 transition-all duration-300 flex flex-col md:transform-none ${
          sidebarCollapsed ? 'w-16 overflow-visible' : 'w-64'
        } ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* Logo */}
        <div className="h-16 shrink-0 flex items-center justify-between px-4 border-b border-gray-100 dark:border-gray-700">
          {!sidebarCollapsed && (
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold text-sm"
                style={{ backgroundColor: PRIMARY }}
              >
                {clientInfo?.logo_url ? <img src={clientInfo.logo_url} alt={clientName} className="h-8 w-8 rounded-lg object-contain" /> : clientName.slice(0, 1)}
              </div>
              <span className="font-bold text-gray-900 dark:text-white truncate">{clientName}</span>
            </div>
          )}
          <button
            type="button"
            aria-label={sidebarCollapsed ? '展開側欄' : '收合側欄'}
            onClick={() => { setSidebarCollapsed(!sidebarCollapsed); setCompactMenu(null) }}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg hidden md:block flex-shrink-0"
          >
            <Menu size={18} />
          </button>
          <button
            type="button"
            aria-label="關閉導覽選單"
            onClick={() => setMobileMenuOpen(false)}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 md:hidden flex-shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav aria-label="後台導覽" className="min-h-0 flex-1 space-y-1 overflow-y-auto p-3" onScroll={() => setCompactMenu(null)}>
          {navItems.map((item) => (
            <SidebarItem
              key={item.id}
              item={item}
              collapsed={sidebarCollapsed}
              active={currentGroup?.id === item.id}
              expanded={visibleGroup === item.id}
              popup={compactMenu?.id === item.id ? compactMenu : undefined}
              onToggle={() => setExpandedGroup(visibleGroup === item.id ? null : item.id)}
              onOpen={trigger => openCompactMenu(item, trigger)}
              onDismiss={() => setCompactMenu(current => current?.id === item.id ? null : current)}
              onNavigate={() => { setMobileMenuOpen(false); setCompactMenu(null) }}
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
              {displayUser?.picture ? (
                <img
                  src={displayUser.picture}
                  alt={displayUser.name || ''}
                  className="w-8 h-8 rounded-full object-cover flex-shrink-0"
                />
              ) : (
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium flex-shrink-0"
                  style={{ backgroundColor: PRIMARY }}
                >
                  {(displayUser?.name || displayUser?.email || '?').charAt(0).toUpperCase()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {displayUser?.name || '管理員'}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {displayUser?.email}
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
              onClick={() => { setSidebarCollapsed(false); setCompactMenu(null); setMobileMenuOpen(true) }}
              aria-label="開啟導覽選單"
              className="min-h-11 min-w-11 p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg md:hidden"
            >
              <Menu size={20} />
            </button>
            <div className="min-w-0 flex-1">
              <PageBreadcrumb navItems={navItems} />
            </div>
          </div>

          <div className="flex items-center gap-2">
            {!isPersonalCoachPage && !!adminCheck?.user?.campuses?.length && !!(adminCheck.user.is_manager || adminCheck.user.is_superuser) && (
              <label className="hidden sm:flex items-center gap-2 border border-gray-200 dark:border-gray-700 rounded-xl px-3 py-1.5 bg-gray-50 dark:bg-gray-900" title={adminCheck.user.can_view_all_campuses ? '切換日常資料的校區範圍；總部設定頁仍可管理全部校區' : '目前可查看的校區範圍'}>
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
            {hasAdminPermission(adminCheck?.user, 'notifications') && <NotificationBell />}
            <ThemeToggleButton />
            <button
              onClick={() => logout(`${basePath}/console`)}
              disabled={loggingOut}
              aria-busy={loggingOut}
              className="min-h-11 min-w-11 p-2 text-gray-500 dark:text-gray-400 hover:bg-red-50 dark:hover:bg-red-900/30 hover:text-red-500 rounded-lg disabled:opacity-50"
              title={loggingOut ? '登出中…' : '登出'}
            >
              <LogOut size={20} />
            </button>
          </div>
        </header>

        {!isPersonalCoachPage && !!adminCheck?.user?.campuses?.length && !!(adminCheck.user.is_manager || adminCheck.user.is_superuser) && (
          <div className="border-b border-gray-200 bg-white px-4 py-2 dark:border-gray-700 dark:bg-gray-800 sm:hidden">
            <label className="flex items-center gap-3 text-sm text-gray-600 dark:text-gray-300">
              <span className="shrink-0">目前範圍</span>
              <select
                aria-label="目前管理校區"
                value={campusScope}
                onChange={(event) => changeCampusScope(event.target.value)}
                className="min-w-0 flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 font-semibold text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
              >
                {adminCheck.user.can_view_all_campuses && <option value="all">全部校區</option>}
                {adminCheck.user.campuses.map((campus) => <option key={campus.id} value={campus.id}>{campus.name}</option>)}
              </select>
            </label>
          </div>
        )}

        {isPersonalCoachPage && <div role="note" aria-label="個人教練視角" className="border-b border-violet-100 bg-violet-50 px-4 py-2 text-xs leading-5 text-violet-800 dark:border-violet-900 dark:bg-violet-950/30 dark:text-violet-200">
          <strong>個人教練視角</strong>：僅顯示您本人的課程、評量、請假與薪資，不套用管理校區篩選。
        </div>}
        <main className="p-4 md:p-6">
          {logoutError && <div role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
            <p>{logoutError}</p>
            <button type="button" disabled={loggingOut} onClick={() => logout(`${basePath}/console`)} className="mt-2 min-h-11 rounded-lg border border-current px-4 py-2 disabled:opacity-50">{loggingOut ? '登出中…' : '重試登出'}</button>
          </div>}
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
    for (const c of item.children) {
      if ((location.pathname === c.path || (c.id && location.pathname.startsWith(c.path + '/'))) && (!child || c.path.length > child.path.length)) {
        parent = item
        child = c
      }
    }
  }

  if (!parent || !child) {
    return <h1 className="text-base font-semibold text-gray-900 dark:text-white truncate">管理後台</h1>
  }

  return (
    <div className="flex min-w-0 items-center gap-2 overflow-hidden whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
      <span className="hidden text-gray-700 dark:text-gray-300 sm:inline">{parent.label}</span>
      <span className="hidden sm:inline" aria-hidden>/</span>
      <span className="min-w-0 truncate font-medium text-gray-900 dark:text-white">{child.label}</span>
    </div>
  )
}

// ============== 無 Manager 權限頁 ==============
function NoManagerPermission({
  user,
  onLogout,
  onRetry,
  basePath,
  errorCode,
  errorMsg,
  logoutError,
  loggingOut,
}: {
  user: { name?: string; email?: string; picture?: string }
  onLogout: () => Promise<void> | void
  onRetry: () => void
  basePath: string
  errorCode: number | null
  errorMsg: string
  logoutError?: string
  loggingOut?: boolean
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

  if (is401 && !logoutError) {
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
        {logoutError && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{logoutError}</p>}

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

        <div className="flex flex-wrap gap-3">
          {!is403 && <button
            onClick={onRetry}
            className="min-h-11 flex-1 min-w-[120px] px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90"
            style={{ backgroundColor: PRIMARY }}
          >
            重新驗證
          </button>}
          <button
            onClick={() => window.location.href = basePath || '/'}
            className="min-h-11 flex-1 min-w-[120px] px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600"
          >
            回首頁
          </button>
          <button
            onClick={() => onLogout()}
            disabled={loggingOut}
            aria-busy={loggingOut}
            className="min-h-11 flex-1 min-w-[120px] px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50"
            style={{ backgroundColor: PRIMARY }}
          >
            {loggingOut ? '登出中…' : '切換帳號'}
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
