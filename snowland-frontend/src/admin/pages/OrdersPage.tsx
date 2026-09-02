/**
 * 訂單管理（接 API）
 */
import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { Search, X, Eye, Edit2, Calendar, User, CreditCard, MapPin, Loader2, AlertCircle, Save, Zap, Mail, ChevronLeft, ChevronRight } from 'lucide-react'
import { fetchOrder, fetchOrdersPaged, updateOrder, type Order, type PaymentStatus } from '../api/orders'
import { sendOrderEmail } from '../api/extras'
import { useNotification } from '../context'

const PRIMARY = '#8b5cf6'

const STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  created: { label: '已建立', cls: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300' },
  cancelled: { label: '已取消', cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  auto_assigned: { label: '已自動排定', cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  manually_assigned: { label: '人工排定', cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  pending_coach_confirmation: { label: '等待教練確認', cls: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' },
  auto_assignment_failed: { label: '排定失敗', cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  manual_assignment_needed: { label: '需人工排定', cls: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' },
  completed: { label: '已完成', cls: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
  form_filled: { label: '已填表單', cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  deleted: { label: '已刪除', cls: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400' },
}

const PAYMENT_LABEL: Record<string, { label: string; cls: string }> = {
  unpaid: { label: '未付款', cls: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300' },
  pending: { label: '待確認', cls: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' },
  paid: { label: '已付款', cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  expired: { label: '已過期', cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  refunded: { label: '已退款', cls: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400' },
}

const getStatusPill = (s: string) => STATUS_LABEL[s] || { label: s, cls: 'bg-gray-100 text-gray-700' }
const getPaymentPill = (s: string) => PAYMENT_LABEL[s] || { label: s, cls: 'bg-gray-100 text-gray-700' }
const PAGE_SIZE = 10

function getOrderLoadError(error: unknown): { title: string; message: string } {
  const err = error as any
  const status = err?.response?.status
  const apiMessage = err?.response?.data?.msg || err?.response?.data?.detail || err?.message

  if (status === 401) {
    return {
      title: '尚未登入後台',
      message: '目前瀏覽器沒有有效的登入狀態，請重新登入後台再查看訂單。',
    }
  }

  if (status === 403) {
    return {
      title: '沒有訂單權限或登入已失效',
      message: apiMessage || '此帳號目前無法讀取訂單資料，請確認員工權限有開啟「訂單管理」。',
    }
  }

  if (status === 404) {
    return {
      title: '訂單 API 路徑不存在',
      message: '請確認目前前端網址與後端 API 代理設定是否一致。',
    }
  }

  if (status) {
    return {
      title: `載入失敗（HTTP ${status}）`,
      message: apiMessage || '後端回傳錯誤，請查看伺服器紀錄。',
    }
  }

  return {
    title: '載入失敗',
    message: apiMessage || '無法連線到訂單 API，請確認後端服務是否正在執行。',
  }
}

function getVisiblePageItems(currentPage: number, totalPages: number): Array<number | 'ellipsis'> {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1)

  const pages = new Set<number>([1, totalPages, currentPage])
  if (currentPage > 1) pages.add(currentPage - 1)
  if (currentPage < totalPages) pages.add(currentPage + 1)
  if (currentPage <= 3) {
    pages.add(2)
    pages.add(3)
    pages.add(4)
  }
  if (currentPage >= totalPages - 2) {
    pages.add(totalPages - 1)
    pages.add(totalPages - 2)
    pages.add(totalPages - 3)
  }

  const sorted = [...pages]
    .filter((pageNumber) => pageNumber >= 1 && pageNumber <= totalPages)
    .sort((a, b) => a - b)

  const items: Array<number | 'ellipsis'> = []
  sorted.forEach((pageNumber, index) => {
    const previous = sorted[index - 1]
    if (previous && pageNumber - previous > 1) items.push('ellipsis')
    items.push(pageNumber)
  })
  return items
}

export default function OrdersPage() {
  const [searchInput, setSearchInput] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [paymentFilter, setPaymentFilter] = useState('')
  const [page, setPage] = useState(1)
  const [viewingId, setViewingId] = useState<number | null>(null)

  // 搜尋 debounce 300ms,避免每打一個字就打一次 API
  const [search, setSearch] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput.trim()), 300)
    return () => clearTimeout(t)
  }, [searchInput])

  // 搜尋 / 過濾條件變動 → 強制回到第一頁(避免在第 5 頁但條件過濾後只剩 2 頁的空畫面)
  useEffect(() => { setPage(1) }, [search, statusFilter, paymentFilter])

  const { data: pageData, isLoading, error, isFetching } = useQuery({
    queryKey: ['admin', 'orders', { page, page_size: PAGE_SIZE, search, status: statusFilter, payment_status: paymentFilter }],
    queryFn: () => fetchOrdersPaged({
      page,
      page_size: PAGE_SIZE,
      search: search || undefined,
      status: statusFilter || undefined,
      payment_status: paymentFilter || undefined,
    }),
    placeholderData: keepPreviousData,  // 翻頁時保留舊資料避免畫面閃白
  })

  const orders = pageData?.items || []
  const total = pageData?.total || 0
  const totalPages = pageData?.total_pages || 0
  const currentPage = pageData?.page || page
  const currentPageSize = pageData?.page_size || PAGE_SIZE
  const pageItems = getVisiblePageItems(currentPage, totalPages)
  const firstItemNumber = total ? ((currentPage - 1) * currentPageSize) + 1 : 0
  const lastItemNumber = total ? Math.min(currentPage * currentPageSize, total) : 0
  const orderLoadError = error ? getOrderLoadError(error) : null

  useEffect(() => {
    if (pageData?.page && pageData.page !== page) setPage(pageData.page)
  }, [page, pageData?.page])

  const { data: viewing, isLoading: isViewingLoading, error: viewingError } = useQuery({
    queryKey: ['admin', 'orders', 'detail', viewingId],
    queryFn: () => fetchOrder(viewingId as number),
    enabled: viewingId !== null,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">訂單管理</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">查看與管理所有預約訂單</p>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder="搜尋訂單編號 / 學員姓名 / Email..."
              className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30">
            <option value="">全部訂單狀態</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
          <select value={paymentFilter} onChange={(e) => setPaymentFilter(e.target.value)}
            className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30">
            <option value="">全部付款狀態</option>
            {Object.entries(PAYMENT_LABEL).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} /></div>
        ) : orderLoadError ? (
          <div className="p-8 text-center">
            <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
            <p className="text-sm font-semibold text-red-600">{orderLoadError.title}</p>
            <p className="mx-auto mt-2 max-w-md text-sm text-gray-500 dark:text-gray-400">{orderLoadError.message}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-4 rounded-lg px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              style={{ backgroundColor: PRIMARY }}
            >
              重新載入
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">訂單編號</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden md:table-cell">下單時間</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">學員</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden lg:table-cell">課程</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">金額</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">訂單狀態</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden md:table-cell">付款</th>
                  <th className="px-5 py-3 text-right font-medium text-gray-600 dark:text-gray-300">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {orders.map((order) => {
                  const firstR = order.reservations[0]
                  const statusPill = firstR ? getStatusPill(firstR.status) : { label: '無', cls: '' }
                  const paymentPill = getPaymentPill(order.payment_status)
                  return (
                    <tr key={order.id} className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                      <td className="px-5 py-3 font-mono whitespace-nowrap" style={{ color: PRIMARY }}>{order.sn}</td>
                      <td className="px-5 py-3 text-gray-600 dark:text-gray-300 hidden md:table-cell whitespace-nowrap">
                        {order.created_at ? (
                          <>
                            <div>{order.created_at.slice(0, 10)}</div>
                            <div className="text-xs text-gray-500">{order.created_at.slice(11, 16)}</div>
                          </>
                        ) : '—'}
                      </td>
                      <td className="px-5 py-3 text-gray-900 dark:text-white whitespace-nowrap">
                        <div className="font-medium">{order.user_name}</div>
                        {firstR && <div className="text-xs text-gray-500">{firstR.number_of_people} 人</div>}
                      </td>
                      <td className="px-5 py-3 text-gray-600 dark:text-gray-300 hidden lg:table-cell whitespace-nowrap">
                        {firstR ? (
                          <>
                            <div>{firstR.resort}</div>
                            <div className="text-xs text-gray-500">{firstR.course_type}</div>
                          </>
                        ) : '—'}
                      </td>
                      <td className="px-5 py-3 font-medium text-gray-900 dark:text-white whitespace-nowrap">NT$ {(order.total_fee || 0).toLocaleString()}</td>
                      <td className="px-5 py-3 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-1 text-xs font-medium rounded-full ${statusPill.cls}`}>{statusPill.label}</span>
                      </td>
                      <td className="px-5 py-3 hidden md:table-cell whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-1 text-xs font-medium rounded-full ${paymentPill.cls}`}>{paymentPill.label}</span>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button onClick={() => setViewingId(order.id)} className="p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"><Eye size={16} /></button>
                      </td>
                    </tr>
                  )
                })}
                {orders.length === 0 && (
                  <tr><td colSpan={8} className="px-5 py-16 text-center text-sm text-gray-500 dark:text-gray-400">{total === 0 && !search && !statusFilter && !paymentFilter ? '尚未有訂單' : '沒有符合條件的訂單'}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {total > 0 ? (
              <>
                顯示 <span className="font-medium">{firstItemNumber}</span> - <span className="font-medium">{lastItemNumber}</span> 筆，
                共 <span className="font-medium">{total}</span> 筆訂單
                {totalPages > 1 && (
                  <span className="ml-2 text-gray-400">
                    · 第 {currentPage} / {totalPages} 頁
                  </span>
                )}
              </>
            ) : (
              <>共 <span className="font-medium">0</span> 筆訂單</>
            )}
            {isFetching && <Loader2 size={12} className="inline-block ml-2 animate-spin text-gray-400" />}
          </div>
          {totalPages > 1 && (
            <div className="flex flex-wrap items-center justify-end gap-1">
              <button
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={currentPage <= 1}
                className="p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg disabled:opacity-40 disabled:cursor-not-allowed"
                title="上一頁"
              >
                <ChevronLeft size={16} />
              </button>
              {pageItems.map((item, index) => (
                item === 'ellipsis' ? (
                  <span key={`ellipsis-${index}`} className="px-2 text-sm text-gray-400">...</span>
                ) : (
                  <button
                    key={item}
                    onClick={() => setPage(item)}
                    disabled={item === currentPage}
                    className={`min-w-8 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors ${
                      item === currentPage
                        ? 'text-white disabled:opacity-100'
                        : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                    }`}
                    style={item === currentPage ? { backgroundColor: PRIMARY } : undefined}
                  >
                    {item}
                  </button>
                )
              ))}
              <button
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                disabled={currentPage >= totalPages}
                className="p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg disabled:opacity-40 disabled:cursor-not-allowed"
                title="下一頁"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
      </div>

      {viewingId !== null && isViewingLoading && (
        <OrderDetailStatusDrawer title="載入訂單明細中" onClose={() => setViewingId(null)} />
      )}
      {viewingId !== null && viewingError && (
        <OrderDetailStatusDrawer
          title="明細載入失敗"
          message={(viewingError as any)?.response?.data?.msg || (viewingError as any)?.response?.data?.detail || (viewingError as any)?.message || '請稍後再試'}
          onClose={() => setViewingId(null)}
        />
      )}
      {viewing && <OrderDetailDrawer order={viewing} onClose={() => setViewingId(null)} />}
    </div>
  )
}

function OrderDetailStatusDrawer({ title, message = '請稍候...', onClose }: { title: string; message?: string; onClose: () => void }) {
  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 animate-fadeIn" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col bg-white shadow-2xl animate-slideIn dark:bg-gray-800">
        <div className="px-6 py-4 text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
          <h2 className="text-lg font-semibold">{title}</h2>
        </div>
        <div className="flex flex-1 items-center justify-center p-8 text-center">
          <div>
            <Loader2 size={32} className="mx-auto mb-3 animate-spin" style={{ color: PRIMARY }} />
            <p className="text-sm text-gray-500 dark:text-gray-400">{message}</p>
          </div>
        </div>
      </div>
    </>
  )
}

export function OrderDetailDrawer({ order, onClose, readOnly = false }: { order: Order; onClose: () => void; readOnly?: boolean }) {
  const notify = useNotification()
  const qc = useQueryClient()

  // 編輯狀態（reservation id → 教練 id 或 null）
  const [coachAssignments, setCoachAssignments] = useState<Record<number, number | null>>(() => {
    const init: Record<number, number | null> = {}
    order.reservations.forEach((r) => {
      init[r.id] = r.preferred_coach_id ?? null
    })
    return init
  })
  const [bookingEdits, setBookingEdits] = useState<Record<number, { date: string; start_time: string; end_time: string }>>(() => {
    const init: Record<number, { date: string; start_time: string; end_time: string }> = {}
    order.reservations.forEach((r) => {
      r.bookings.forEach((b) => {
        init[b.id] = {
          date: b.date,
          start_time: (b.start_time || '').slice(0, 5),
          end_time: (b.end_time || '').slice(0, 5),
        }
      })
    })
    return init
  })
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus>(order.payment_status)
  const [editing, setEditing] = useState(false)

  const [emailOpen, setEmailOpen] = useState(false)
  const [emailForm, setEmailForm] = useState({
    recipient_email: order.user_email || '',
    subject: `[${order.sn}] 課程通知`,
    message: '',
  })

  const emailMutation = useMutation({
    mutationFn: () => sendOrderEmail(order.id, emailForm),
    onSuccess: (res) => {
      if (res.code === 200) {
        notify.success('Email 已寄出')
        setEmailOpen(false)
      } else {
        notify.error(res.msg)
      }
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '寄送失敗'),
  })

  const saveMutation = useMutation({
    mutationFn: (action: 'save' | 'schedule') => {
      const studentSpecifiedIds = new Set(
        order.reservations
          .filter((r) => r.is_preferred_coach)
          .map((r) => r.id),
      )
      const updates = Object.entries(coachAssignments)
        .filter(([rid]) => !studentSpecifiedIds.has(Number(rid)))
        .map(([rid, cid]) => ({
          reservation_id: Number(rid),
          coach_id: cid,
        }))
      const bookingUpdates = Object.entries(bookingEdits).map(([bookingId, value]) => ({
        booking_id: Number(bookingId),
        date: value.date,
        start_time: value.start_time,
        end_time: value.end_time,
      }))
      return updateOrder(order.id, {
        action,
        payment_status: paymentStatus !== order.payment_status ? paymentStatus : undefined,
        reservation_updates: updates,
        booking_updates: bookingUpdates,
      })
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['admin', 'orders'] })
      qc.invalidateQueries({ queryKey: ['admin', 'bookings'] })
      if (res.code === 200) {
        notify.success(res.msg)
        setEditing(false)
      } else {
        notify.error(res.msg)
      }
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '更新失敗'),
  })
  const firstR = order.reservations[0]
  const statusPill = firstR ? getStatusPill(firstR.status) : { label: '無', cls: '' }
  const paymentPill = getPaymentPill(paymentStatus)

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 animate-fadeIn" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white dark:bg-gray-800 shadow-2xl flex flex-col animate-slideIn">
        <div className="px-6 py-4 flex items-center justify-between text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold font-mono">{order.sn}</h2>
            {!editing && !readOnly && (
              <>
                <button
                  onClick={() => setEditing(true)}
                  className="px-2.5 py-1 bg-white/20 hover:bg-white/30 backdrop-blur rounded-md text-xs font-medium flex items-center gap-1"
                >
                  <Edit2 size={12} />編輯
                </button>
                <button
                  onClick={() => setEmailOpen(true)}
                  className="px-2.5 py-1 bg-white/20 hover:bg-white/30 backdrop-blur rounded-md text-xs font-medium flex items-center gap-1"
                >
                  <Mail size={12} />寄信
                </button>
              </>
            )}
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white"><X size={20} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex flex-wrap gap-2">
            <span className={`inline-flex items-center px-3 py-1 text-xs font-medium rounded-full ${statusPill.cls}`}>{statusPill.label}</span>
            <span className={`inline-flex items-center px-3 py-1 text-xs font-medium rounded-full ${paymentPill.cls}`}>{paymentPill.label}</span>
          </div>

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2"><User size={14} style={{ color: PRIMARY }} />學員資料</h3>
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">姓名</span><span className="text-gray-900 dark:text-white">{order.user_name}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Email</span><span className="font-mono text-gray-900 dark:text-white">{order.user_email || '—'}</span></div>
            </div>
          </section>

          {order.reservations.map((r, idx) => {
            const availableCoaches = r.available_coaches || []
            const selectedCoachId = coachAssignments[r.id] ?? null
            const selectedCoachMissing = !!selectedCoachId && !availableCoaches.some((coach) => coach.id === selectedCoachId)
            const reservationStatusPill = getStatusPill(r.status)
            const isSchedulingFailed = r.status === 'auto_assignment_failed' || r.status === 'manual_assignment_needed'
            const isStudentSpecifiedCoach = Boolean(r.is_preferred_coach && r.preferred_coach_id)
            return (
            <section key={r.id}>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2"><MapPin size={14} style={{ color: PRIMARY }} />課程 {order.reservations.length > 1 ? `#${idx + 1}` : ''}</h3>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${reservationStatusPill.cls}`}>
                  {reservationStatusPill.label}
                </span>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">雪場</span><span className="text-gray-900 dark:text-white">{r.resort}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">課程類型</span><span className="text-gray-900 dark:text-white">{r.course_type}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">能力等級</span><span className="text-gray-900 dark:text-white">{r.ability_level}</span></div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-500">教練</span>
                  {editing && isStudentSpecifiedCoach ? (
                    <div className="text-right">
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <span className="text-gray-900 dark:text-white">{r.preferred_coach || '指定教練'}</span>
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:bg-amber-900/40 dark:text-amber-200">
                          客人指定
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">不可由後台更換</p>
                    </div>
                  ) : editing ? (
                    <select
                      value={coachAssignments[r.id] ?? ''}
                      onChange={(e) => setCoachAssignments((p) => ({
                        ...p,
                        [r.id]: e.target.value ? Number(e.target.value) : null,
                      }))}
                      className="px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                    >
                      <option value="">{availableCoaches.length === 0 ? '目前沒有可排教練' : '不指定（系統自動排）'}</option>
                      {selectedCoachMissing && (
                        <option value={selectedCoachId} disabled>
                          {r.preferred_coach || '目前指派教練'}（目前不在可排清單）
                        </option>
                      )}
                      {availableCoaches.map((coach) => (
                        <option key={coach.id} value={coach.id}>
                          {coach.name}{coach.requires_confirmation ? '（需確認）' : ''}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      <span className="text-gray-900 dark:text-white">{r.preferred_coach || '不指定'}</span>
                      {isStudentSpecifiedCoach && (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:bg-amber-900/40 dark:text-amber-200">
                          客人指定
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex justify-between"><span className="text-gray-500">語言</span><span className="text-gray-900 dark:text-white">{r.language}</span></div>
                {r.equipment_assistance_time_label && (
                  <div className="flex justify-between"><span className="text-gray-500">裝備協助時段</span><span className="text-gray-900 dark:text-white">{r.equipment_assistance_time_label}</span></div>
                )}
                <div className="flex justify-between"><span className="text-gray-500">人數</span><span className="text-gray-900 dark:text-white">{r.number_of_people} 人</span></div>
              </div>

              {isSchedulingFailed && (
                <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-700 dark:border-red-900/60 dark:bg-red-900/20 dark:text-red-300">
                  此小單尚未排課成功。未付款的排課失敗訂單會在建立後 30 分鐘自動取消；也可以請客人改選其他日期後重新下單。
                </div>
              )}

              {r.bookings.length > 0 && (
                <div className="mt-3">
                  <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 flex items-center gap-1"><Calendar size={12} />課程時段</h4>
                  <div className="space-y-2">
                    {r.bookings.map((b) => {
                      const edit = bookingEdits[b.id] || {
                        date: b.date,
                        start_time: (b.start_time || '').slice(0, 5),
                        end_time: (b.end_time || '').slice(0, 5),
                      }
                      return (
                        <div key={b.id} className="flex flex-col gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg text-sm md:flex-row md:items-center">
                          <Calendar size={16} className="text-gray-400" />
                          {editing ? (
                            <div className="grid flex-1 grid-cols-1 gap-2 md:grid-cols-[1.2fr_1fr_1fr]">
                              <label className="space-y-1">
                                <span className="block text-[11px] font-medium text-gray-500 dark:text-gray-400">日期</span>
                                <input
                                  type="date"
                                  value={edit.date}
                                  onChange={(e) => setBookingEdits((prev) => ({
                                    ...prev,
                                    [b.id]: { ...edit, date: e.target.value },
                                  }))}
                                  className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                                />
                              </label>
                              <label className="space-y-1">
                                <span className="block text-[11px] font-medium text-gray-500 dark:text-gray-400">開始</span>
                                <input
                                  type="time"
                                  value={edit.start_time}
                                  onChange={(e) => setBookingEdits((prev) => ({
                                    ...prev,
                                    [b.id]: { ...edit, start_time: e.target.value },
                                  }))}
                                  className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                                />
                              </label>
                              <label className="space-y-1">
                                <span className="block text-[11px] font-medium text-gray-500 dark:text-gray-400">結束</span>
                                <input
                                  type="time"
                                  value={edit.end_time}
                                  onChange={(e) => setBookingEdits((prev) => ({
                                    ...prev,
                                    [b.id]: { ...edit, end_time: e.target.value },
                                  }))}
                                  className="w-full rounded border border-gray-200 bg-white px-2 py-1 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                                />
                              </label>
                            </div>
                          ) : (
                            <>
                              <span className="font-medium text-gray-900 dark:text-white">{b.date}</span>
                              <span className="text-gray-500">{b.start_time} - {b.end_time}</span>
                            </>
                          )}
                          <span className="text-xs text-gray-500 md:ml-auto">{b.course_name}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </section>
          )})}

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2"><CreditCard size={14} style={{ color: PRIMARY }} />付款資訊</h3>
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-2 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-gray-500">付款狀態</span>
                {editing ? (
                  <select
                    value={paymentStatus}
                    onChange={(e) => setPaymentStatus(e.target.value as PaymentStatus)}
                    className="px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                  >
                    {Object.entries(PAYMENT_LABEL).map(([k, v]) => (
                      <option key={k} value={k}>{v.label}</option>
                    ))}
                  </select>
                ) : (
                  <span className={`px-2.5 py-0.5 text-xs font-medium rounded-full ${paymentPill.cls}`}>{paymentPill.label}</span>
                )}
              </div>
              <div className="flex justify-between"><span className="text-gray-500">付款方式</span><span className="text-gray-900 dark:text-white">{order.payment_method}</span></div>
              <div className="flex justify-between">
                <span className="text-gray-500">匯款後五碼</span>
                <span className="font-mono text-gray-900 dark:text-white">{order.bank_account || '未填寫'}</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-gray-200 dark:border-gray-600">
                <span className="font-medium text-gray-900 dark:text-white">總金額</span>
                <span className="text-lg font-bold" style={{ color: PRIMARY }}>NT$ {(order.total_fee || 0).toLocaleString()}</span>
              </div>
            </div>
          </section>

          <div className="text-xs text-gray-500 text-center">建立於 {order.created_at}</div>
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          {editing && !readOnly ? (
            <>
              <button
                onClick={() => setEditing(false)}
                disabled={saveMutation.isPending}
                className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={() => saveMutation.mutate('save')}
                disabled={saveMutation.isPending}
                className="px-4 py-2 bg-white dark:bg-gray-700 border border-[#8b5cf6] text-sm font-medium rounded-lg hover:bg-[#8b5cf6]/5 disabled:opacity-50 flex items-center gap-2"
                style={{ color: PRIMARY }}
              >
                {saveMutation.isPending && <Loader2 size={14} className="animate-spin" />}
                <Save size={14} />只儲存
              </button>
              <button
                onClick={() => saveMutation.mutate('schedule')}
                disabled={saveMutation.isPending}
                className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                style={{ backgroundColor: PRIMARY }}
              >
                {saveMutation.isPending && <Loader2 size={14} className="animate-spin" />}
                <Zap size={14} />儲存並 AI 排課
              </button>
            </>
          ) : (
            <button onClick={onClose} className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600">關閉</button>
          )}
        </div>
      </div>

      {/* Email Modal */}
      {emailOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 animate-fadeIn">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md">
            <div className="rounded-t-2xl px-6 py-4 text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
              <h3 className="text-lg font-semibold">寄信給訂單聯絡人</h3>
              <p className="text-xs text-white/80 mt-0.5">{order.sn}</p>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">收件人</label>
                <input
                  type="email"
                  value={emailForm.recipient_email}
                  onChange={(e) => setEmailForm({ ...emailForm, recipient_email: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">主旨</label>
                <input
                  type="text"
                  value={emailForm.subject}
                  onChange={(e) => setEmailForm({ ...emailForm, subject: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">內容</label>
                <textarea
                  value={emailForm.message}
                  onChange={(e) => setEmailForm({ ...emailForm, message: e.target.value })}
                  rows={6}
                  placeholder="輸入信件內容..."
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 resize-none"
                />
                <p className="mt-1 text-xs text-gray-500">系統會自動加上品牌簽名</p>
              </div>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
              <button onClick={() => setEmailOpen(false)} disabled={emailMutation.isPending} className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50">取消</button>
              <button
                onClick={() => emailMutation.mutate()}
                disabled={emailMutation.isPending || !emailForm.message.trim() || !emailForm.recipient_email}
                className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                style={{ backgroundColor: PRIMARY }}
              >
                {emailMutation.isPending && <Loader2 size={14} className="animate-spin" />}
                <Mail size={14} />寄出
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
