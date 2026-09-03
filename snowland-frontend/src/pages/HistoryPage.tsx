import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Home, Calendar, Clock, MapPin, Users, CreditCard, ChevronDown, ChevronUp, Filter, Copy, Repeat2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import LoadingOverlay from '@/components/ui/LoadingOverlay'
import Toast, { ToastType } from '@/components/ui/Toast'
import { useBookingStore } from '@/store/bookingStore'

interface ReservationHistory {
  reservation_group_id: number
  created_at: string
  total_amount: number
  payment_status: string
  reservations: ReservationDetail[]
}

interface ReservationDetail {
  id: number
  resort: string
  course_type: string
  language: string
  status: string
  number_of_people: number
  bookings: BookingDetail[]
  course_fee: number
  coach_fee: number
  equipment_rental_fee: number
  equipment_assistance_time_label?: string
  language_fee: number
  total_fee: number
}

interface BookingDetail {
  course_name: string
  date: string
  start_time: string
  end_time: string
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const { user, loading: authLoading } = useAuth()
  const [loading, setLoading] = useState(true)
  const [history, setHistory] = useState<ReservationHistory[]>([])
  const [profile, setProfile] = useState<{ referral_code: string; points: number; level: string; alumni_verified: boolean } | null>(null)
  const replaceCart = useBookingStore((state) => state.replaceCart)
  const clientCode = window.location.pathname.split('/').filter(Boolean)[0] || 'snowland'
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set())
  const [toast, setToast] = useState<{ message: string; type: ToastType; isOpen: boolean }>({
    message: '',
    type: 'info',
    isOpen: false
  })

  // 🔥 篩選狀態
  const [filterPaymentStatus, setFilterPaymentStatus] = useState<string>('all')
  const [sortBy, setSortBy] = useState<'date_desc' | 'date_asc' | 'amount_desc' | 'amount_asc'>('date_desc')

  // 🔥 如果未登入，重定向到登入頁面
  useEffect(() => {
    if (!authLoading && !user) {
      navigate('../login')
    }
  }, [authLoading, user, navigate])

  const showToast = (message: string, type: ToastType = 'info') => {
    setToast({ message, type, isOpen: true })
  }

  useEffect(() => {
    // 🔥 等待認證完成且確認已登入後才獲取歷史紀錄
    if (authLoading || !user) {
      return
    }

    const fetchHistory = async () => {
      try {
        // 走相對路徑（同 origin）
        const response = await fetch(`/booking/${clientCode}/api/reservation-history/`, {
          credentials: 'include', // 包含 session cookies
        })

        const data = await response.json()

        if (!response.ok) {
          showToast(data.error || '獲取歷史紀錄失敗', 'error')
          setLoading(false)
          return
        }

        // 過濾掉已刪除的預約
        const filteredHistory = ((data.history || []) as ReservationHistory[])
          .map((group) => ({
            ...group,
            reservations: group.reservations.filter((res) => res.status !== 'deleted')
          }))
          .filter((group) => group.reservations.length > 0) // 如果組內沒有有效預約，則過濾掉整個組

        setHistory(filteredHistory)
        const profileResponse = await fetch(`/booking/${clientCode}/api/member-center/`, { credentials: 'include' })
        if (profileResponse.ok) setProfile(await profileResponse.json())
        setLoading(false)
      } catch (error) {
        showToast('無法連接到伺服器', 'error')
        setLoading(false)
      }
    }

    fetchHistory()
  }, [authLoading, user])

  const quickRebook = async (groupId: number) => {
    try {
      const response = await fetch(`/booking/${clientCode}/api/member-center/`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '' }, body: JSON.stringify({ quick_rebook_group_id: groupId }) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || '無法複製訂單')
      replaceCart(data.cart || [])
      navigate('../booking')
    } catch (error: any) { showToast(error.message || '無法複製訂單', 'error') }
  }

  const toggleGroup = (groupId: number) => {
    const newExpanded = new Set(expandedGroups)
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId)
    } else {
      newExpanded.add(groupId)
    }
    setExpandedGroups(newExpanded)
  }

  const getPaymentStatusBadge = (status: string) => {
    const statusMap: Record<string, { label: string; color: string }> = {
      'paid': { label: '已付款', color: 'bg-green-100 text-green-800' },
      'unpaid': { label: '待付款', color: 'bg-yellow-100 text-yellow-800' },
      'pending': { label: '待確認', color: 'bg-blue-100 text-blue-800' },
      'expired': { label: '已過期', color: 'bg-gray-100 text-gray-800' },
      'cancelled': { label: '已取消', color: 'bg-red-100 text-red-800' },
    }

    const statusInfo = statusMap[status] || { label: status, color: 'bg-gray-100 text-gray-800' }

    return (
      <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${statusInfo.color}`}>
        {statusInfo.label}
      </span>
    )
  }

  const getReservationStatusBadge = (status: string) => {
    const statusMap: Record<string, { label: string; color: string }> = {
      'created': { label: '已創建', color: 'bg-gray-100 text-gray-800' },
      'auto_assigned': { label: '已排課', color: 'bg-green-100 text-green-800' },
      'manually_assigned': { label: '人工排課', color: 'bg-blue-100 text-blue-800' },
      'pending_coach_confirmation': { label: '待教練確認', color: 'bg-yellow-100 text-yellow-800' },
      'auto_assignment_failed': { label: '排課失敗', color: 'bg-red-100 text-red-800' },
      'cancelled': { label: '已取消', color: 'bg-red-100 text-red-800' },
      'deleted': { label: '已刪除', color: 'bg-gray-100 text-gray-800' },
    }

    const statusInfo = statusMap[status] || { label: status, color: 'bg-gray-100 text-gray-800' }

    return (
      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusInfo.color}`}>
        {statusInfo.label}
      </span>
    )
  }

  // 🔥 篩選和排序邏輯
  const filteredAndSortedHistory = history
    .filter(group => {
      // 付款狀態篩選
      if (filterPaymentStatus !== 'all' && group.payment_status !== filterPaymentStatus) {
        return false
      }
      return true
    })
    .sort((a, b) => {
      // 排序
      switch (sortBy) {
        case 'date_desc':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        case 'date_asc':
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        case 'amount_desc':
          return b.total_amount - a.total_amount
        case 'amount_asc':
          return a.total_amount - b.total_amount
        default:
          return 0
      }
    })

  // 🔥 顯示載入狀態
  if (authLoading || loading) {
    return <LoadingOverlay isLoading={true} message="載入歷史紀錄中..." />
  }

  // 🔥 如果未登入，不顯示任何內容（會被重定向）
  if (!user) {
    return null
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50">
      {/* 頂部導航 */}
      <nav className="bg-white/80 shadow-sm backdrop-blur-md">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-primary-700">
              預約歷史紀錄
            </h1>
            <button
              onClick={() => navigate('..')}
              className="flex items-center gap-2 rounded-full bg-gray-200 px-4 py-2 text-gray-600 transition-all hover:bg-gray-300"
            >
              <Home size={20} />
              <span>返回首頁</span>
            </button>
          </div>
        </div>
      </nav>

      {/* 主要內容 */}
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        {profile && <section className="mb-6 grid gap-4 rounded-2xl bg-white p-5 shadow-lg sm:grid-cols-[1fr_auto]"><div><p className="text-xs font-semibold uppercase tracking-wider text-gray-400">會員等級</p><h2 className="mt-1 text-xl font-bold text-gray-800">{profile.level} · {profile.points.toLocaleString()} 點</h2><p className="mt-1 text-sm text-gray-500">推薦好友訂課可累積點數；舊生資格{profile.alumni_verified ? '已確認' : '尚待確認'}。</p></div><button onClick={async () => { await navigator.clipboard.writeText(profile.referral_code); showToast('推薦碼已複製', 'success') }} className="flex items-center justify-center gap-2 rounded-xl border border-primary-200 px-5 py-3 font-mono font-bold text-primary-700"><Copy size={16} />{profile.referral_code}</button></section>}
        {/* 篩選器 */}
        {history.length > 0 && (
          <div className="mb-6 rounded-2xl bg-white p-4 shadow-lg">
            <div className="flex flex-wrap items-center gap-4">
              {/* 篩選圖標 */}
              <div className="flex items-center gap-2 text-gray-700">
                <Filter size={20} />
                <span className="font-semibold">篩選</span>
              </div>

              {/* 付款狀態篩選 */}
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-600">付款狀態：</label>
                <select
                  value={filterPaymentStatus}
                  onChange={(e) => setFilterPaymentStatus(e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-200"
                >
                  <option value="all">全部</option>
                  <option value="paid">已付款</option>
                  <option value="unpaid">待付款</option>
                  <option value="pending">待確認</option>
                  <option value="cancelled">已取消</option>
                </select>
              </div>

              {/* 排序 */}
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-600">排序：</label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-200"
                >
                  <option value="date_desc">日期 (新→舊)</option>
                  <option value="date_asc">日期 (舊→新)</option>
                  <option value="amount_desc">金額 (高→低)</option>
                  <option value="amount_asc">金額 (低→高)</option>
                </select>
              </div>

              {/* 結果統計 */}
              <div className="ml-auto text-sm text-gray-600">
                顯示 <span className="font-semibold text-primary-600">{filteredAndSortedHistory.length}</span> / {history.length} 筆
              </div>
            </div>
          </div>
        )}

        {history.length === 0 ? (
          <div className="rounded-3xl bg-white p-12 text-center shadow-xl">
            <div className="text-6xl mb-4">📋</div>
            <h2 className="text-2xl font-bold text-gray-800 mb-2">尚無預約紀錄</h2>
            <p className="text-gray-600 mb-6">您還沒有任何預約紀錄，快來預約您的第一堂滑雪課程吧！</p>
            <button
              onClick={() => navigate('..')}
              className="rounded-full bg-gradient-to-r from-primary-500 to-purple-500 px-8 py-3 text-lg font-bold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl"
            >
              開始預約
            </button>
          </div>
        ) : filteredAndSortedHistory.length === 0 ? (
          <div className="rounded-3xl bg-white p-12 text-center shadow-xl">
            <div className="text-6xl mb-4">🔍</div>
            <h2 className="text-2xl font-bold text-gray-800 mb-2">找不到符合條件的預約</h2>
            <p className="text-gray-600 mb-6">請嘗試調整篩選條件</p>
            <button
              onClick={() => {
                setFilterPaymentStatus('all')
                setSortBy('date_desc')
              }}
              className="rounded-full bg-gradient-to-r from-primary-500 to-purple-500 px-6 py-2 font-bold text-white shadow-lg transition-all hover:scale-105"
            >
              重置篩選
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {filteredAndSortedHistory.map((group) => {
              const isExpanded = expandedGroups.has(group.reservation_group_id)

              return (
                <div
                  key={group.reservation_group_id}
                  className="rounded-3xl bg-white shadow-xl overflow-hidden"
                >
                  {/* 預約組摘要 - 可點擊展開 */}
                  <button
                    onClick={() => toggleGroup(group.reservation_group_id)}
                    className="w-full p-6 text-left transition-all hover:bg-gray-50"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-4 mb-2">
                          <h3 className="text-xl font-bold text-gray-800">
                            預約編號 #{group.reservation_group_id}
                          </h3>
                          {getPaymentStatusBadge(group.payment_status)}
                        </div>
                        <div className="flex items-center gap-6 text-sm text-gray-600">
                          <div className="flex items-center gap-1">
                            <Calendar size={16} />
                            <span>{new Date(group.created_at).toLocaleDateString('zh-TW')}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <CreditCard size={16} />
                            <span>NT$ {group.total_amount}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Users size={16} />
                            <span>{group.reservations.length} 個預約</span>
                          </div>
                        </div>
                      </div>
                      <div className="text-gray-400">
                        {isExpanded ? <ChevronUp size={24} /> : <ChevronDown size={24} />}
                      </div>
                    </div>
                  </button>

                  {/* 預約詳情 - 展開時顯示 */}
                  {isExpanded && (
                    <div className="border-t border-gray-200 bg-gray-50 p-6">
                      <div className="space-y-4">
                        {group.reservations.map((reservation) => (
                          <div
                            key={reservation.id}
                            className="rounded-lg bg-white p-4 shadow"
                          >
                            {/* 預約基本資訊 */}
                            <div className="mb-4 flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-2">
                                  <h4 className="font-semibold text-gray-800">
                                    {reservation.course_type}
                                  </h4>
                                  {getReservationStatusBadge(reservation.status)}
                                </div>
                                <div className="space-y-1 text-sm text-gray-600">
                                  <div className="flex items-center gap-2">
                                    <MapPin size={14} />
                                    <span>{reservation.resort}</span>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <Users size={14} />
                                    <span>{reservation.number_of_people} 人</span>
                                  </div>
                                  {reservation.language && reservation.language !== 'zh' && (
                                    <div className="flex items-center gap-2">
                                      <span>🌐</span>
                                      <span>語言: {reservation.language}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* 課程時段 */}
                            <div className="mb-4">
                              <h5 className="text-sm font-semibold text-gray-700 mb-2">課程時段</h5>
                              <div className="space-y-2">
                                {reservation.bookings.map((booking, idx) => (
                                  <div
                                    key={idx}
                                    className="flex items-center gap-3 rounded bg-gray-50 p-2 text-sm"
                                  >
                                    <Calendar size={14} className="text-primary-500" />
                                    <span className="font-medium">{booking.date}</span>
                                    <Clock size={14} className="text-primary-500" />
                                    <span>{booking.start_time} - {booking.end_time}</span>
                                    <span className="text-gray-600">({booking.course_name})</span>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* 費用明細 */}
                            <div className="border-t border-gray-200 pt-4">
                              <h5 className="text-sm font-semibold text-gray-700 mb-2">費用明細</h5>
                              <div className="space-y-1 text-sm">
                                {reservation.course_fee > 0 && (
                                  <div className="flex justify-between">
                                    <span className="text-gray-600">課程費</span>
                                    <span className="font-medium">NT$ {reservation.course_fee}</span>
                                  </div>
                                )}
                                {reservation.coach_fee > 0 && (
                                  <div className="flex justify-between">
                                    <span className="text-gray-600">教練費</span>
                                    <span className="font-medium">NT$ {reservation.coach_fee}</span>
                                  </div>
                                )}
                                {reservation.equipment_rental_fee > 0 && (
                                  <div className="flex justify-between">
                                    <span className="text-gray-600">器材租借費</span>
                                    <span className="font-medium">NT$ {reservation.equipment_rental_fee}</span>
                                  </div>
                                )}
                                {reservation.equipment_assistance_time_label && (
                                  <div className="flex justify-between">
                                    <span className="text-gray-600">裝備協助時段</span>
                                    <span className="font-medium">{reservation.equipment_assistance_time_label}</span>
                                  </div>
                                )}
                                {reservation.language_fee > 0 && (
                                  <div className="flex justify-between">
                                    <span className="text-gray-600">語言服務費</span>
                                    <span className="font-medium">NT$ {reservation.language_fee}</span>
                                  </div>
                                )}
                                <div className="flex justify-between border-t border-gray-200 pt-2 font-semibold">
                                  <span className="text-gray-800">小計</span>
                                  <span className="text-primary-600">NT$ {reservation.total_fee}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* 總計 */}
                      <div className="mt-6 rounded-lg bg-primary-50 p-4">
                        <div className="flex items-center justify-between">
                          <span className="text-lg font-bold text-gray-800">總金額</span>
                          <span className="text-2xl font-bold text-primary-600">
                            NT$ {group.total_amount}
                          </span>
                        </div>
                      </div>

                      {/* 操作按鈕 */}
                      <div className="mt-4 flex flex-wrap justify-end gap-2">
                        <button onClick={() => quickRebook(group.reservation_group_id)} className="flex items-center gap-2 rounded-full border border-primary-300 bg-white px-5 py-3 font-bold text-primary-700"><Repeat2 size={16} />再次預約</button>
                      {group.payment_status === 'unpaid' && (
                          <button
                            onClick={() => navigate(`../payment?reservation_group=${group.reservation_group_id}`)}
                            className="rounded-full bg-gradient-to-r from-primary-500 to-purple-500 px-6 py-3 font-bold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl"
                          >
                            前往付款
                          </button>
                      )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </main>

      {/* Toast 通知 */}
      <Toast
        message={toast.message}
        type={toast.type}
        isOpen={toast.isOpen}
        onClose={() => setToast({ ...toast, isOpen: false })}
      />
    </div>
  )
}
