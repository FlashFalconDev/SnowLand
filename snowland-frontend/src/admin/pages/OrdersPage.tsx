/**
 * 訂單管理（接 API）
 */
import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { Search, X, Eye, Edit2, Calendar, User, CreditCard, MapPin, Loader2, AlertCircle, Save, Zap, Mail, Link2, ChevronLeft, ChevronRight } from 'lucide-react'
import { fetchOrder, fetchOrdersPaged, fetchCampusManagerOrdersPaged, fetchGuestPaymentLink, updateOrder, completeOrderCourse, saveClassGroupLink, previewOrderRefund, requestOrderCancellation, type Order, type PaymentStatus } from '../api/orders'
import { fetchAdminMe } from '../api/auth'
import { useSearchParams } from 'react-router-dom'
import { fetchOrderEmailMode, sendOrderEmail } from '../api/extras'
import { useNotification } from '../context'
import { formatAbilityLevel } from '@/utils/learningProgress'
import { hasAdminPermission } from '../permissions'
import ManualNotificationComposer from '../components/ManualNotificationComposer'
import ClassGroupQRPanel from '../components/ClassGroupQRPanel'
import CancellationStatusPanel from '../components/CancellationStatusPanel'
import OrderAmendmentDialog from '../components/OrderAmendmentDialog'
import AmendmentBalancesPanel from '../components/AmendmentBalancesPanel'

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
const PAYMENT_METHOD_LABEL: Record<string, string> = {
  newebpay: '藍新支付', TT: '銀行匯款', bank_transfer: '銀行匯款', credit_card: '信用卡', apple_pay: 'Apple Pay', google_pay: 'Google Pay',
}
const LANGUAGE_LABEL: Record<string, string> = { zh: '中文', en: '英文', ja: '日文' }
const REVISION_LABEL: Record<string, string> = { create: '建立訂單', update: '修改訂單', modify: '修改訂單', cancellation: '取消訂單', cancel: '取消申請' }
const CANCELLATION_REASON_LABEL: Record<string, string> = { schedule: '行程變更', health: '健康因素', weather: '天候因素', duplicate: '重複訂單', other: '其他' }
const formatTime = (time?: string | null) => (time || '').slice(0, 5)
const formatCreatedAt = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-TW', {
    timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date)
}
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
  const { data, isLoading } = useQuery({ queryKey: ['admin', 'me'], queryFn: fetchAdminMe })
  if (isLoading) return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-purple-500" /></div>
  return data?.user?.role === 'campus_manager' || data?.user?.role === 'campus_principal'
    ? <CampusManagerOrdersPage isPrincipal={data?.user?.role === 'campus_principal'} />
    : <FullOrdersPage />
}

function CampusManagerOrdersPage({ isPrincipal }: { isPrincipal: boolean }) {
  const [searchParams] = useSearchParams()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState(() => searchParams.get('search') || '')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'campus-orders', isPrincipal, page, search],
    queryFn: () => fetchCampusManagerOrdersPaged({ page, page_size: PAGE_SIZE, search }),
  })
  return <div className="space-y-5">
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{isPrincipal ? '校區訂單資訊' : '近期訂單資訊'}</h1>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{isPrincipal ? '只顯示所屬校區的課程；付款與聯絡資料由總部管理。' : '只顯示所屬校區從今天起 10 天內的課程；付款與聯絡資料由總部管理。'}</p>
    </div>
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <label className="sr-only" htmlFor="campus-order-search">搜尋訂單</label>
      <input id="campus-order-search" value={search} onChange={event => { setSearch(event.target.value); setPage(1) }}
        placeholder="搜尋訂單編號或學員暱稱" className="min-h-11 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white" />
    </div>
    {isLoading && <div className="flex justify-center py-16"><Loader2 className="animate-spin text-purple-500" /></div>}
    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">訂單載入失敗，請確認連線後重新整理。</div>}
    {!isLoading && !error && data?.list.length === 0 && <div role="status" className="rounded-xl border border-gray-200 bg-white p-8 text-center text-gray-500 dark:border-gray-700 dark:bg-gray-800">
      <p>{search.trim() ? '目前可查看範圍內，沒有符合搜尋條件的訂單' : isPrincipal ? '目前沒有校區課程訂單' : '目前沒有 10 天內的課程訂單'}</p>
      {search.trim() && <button type="button" onClick={() => { setSearch(''); setPage(1) }} className="mt-3 min-h-11 rounded-lg border border-purple-300 px-4 py-2 text-sm font-semibold text-purple-700 dark:border-purple-600 dark:text-purple-300">清除搜尋</button>}
    </div>}
    {!isLoading && !error && data?.list.map(order => <section key={order.id} className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-mono text-sm font-semibold text-purple-600 dark:text-purple-400">{order.sn}</div>
          <div className="mt-1 font-medium text-gray-900 dark:text-white">{order.student_alias || '未填暱稱'} · {order.number_of_people} 人</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">{order.campus_name} · {order.course_dates.join('、')}</div>
        </div>
        <button type="button" aria-expanded={expandedId === order.id} onClick={() => setExpandedId(expandedId === order.id ? null : order.id)}
          className="min-h-11 rounded-lg border border-purple-300 px-3 py-1.5 text-sm font-medium text-purple-700 hover:bg-purple-50 dark:border-purple-600 dark:text-purple-300 dark:hover:bg-purple-900/20">
          {expandedId === order.id ? '收起課程' : '查看課程'}
        </button>
      </div>
      {expandedId === order.id && <div className="mt-4 space-y-2 border-t border-gray-100 pt-4 dark:border-gray-700">
        {order.sessions.map((session, index) => <div key={`${session.date}-${index}`} className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700 dark:bg-gray-700 dark:text-gray-200">
          <div className="font-medium">{session.date}　{session.start_time.slice(0, 5)}–{session.end_time.slice(0, 5)} · {session.course_type || '課程'}</div>
          <div className="mt-1 text-xs text-gray-500 dark:text-gray-300">{session.number_of_people} 人 · 程度：{formatAbilityLevel(session.ability_level)} · 年齡：{session.age_ranges.join('、') || '未填'}</div>
        </div>)}
      </div>}
    </section>)}
    {!!data && data.total_pages > 1 && <div className="flex items-center justify-end gap-3 text-sm text-gray-600 dark:text-gray-300">
      <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="min-h-11 rounded-lg border px-3 py-1.5 disabled:opacity-40">上一頁</button>
      <span>{page} / {data.total_pages}</span>
      <button type="button" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)} className="min-h-11 rounded-lg border px-3 py-1.5 disabled:opacity-40">下一頁</button>
    </div>}
  </div>
}

function FullOrdersPage() {
  const [searchParams] = useSearchParams()
  const querySearch = searchParams.get('search') || ''
  const [searchInput, setSearchInput] = useState(querySearch)
  const [statusFilter, setStatusFilter] = useState('')
  const [paymentFilter, setPaymentFilter] = useState('')
  const [page, setPage] = useState(1)
  const [viewingId, setViewingId] = useState<number | null>(null)

  // 搜尋 debounce 300ms,避免每打一個字就打一次 API
  const [search, setSearch] = useState(querySearch)
  useEffect(() => { setSearchInput(querySearch) }, [querySearch])
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
        <p className="text-gray-500 dark:text-gray-400 mt-1">
          {(localStorage.getItem('snowland_admin_campus_scope') || 'all') === 'all'
            ? '查看與管理全部校區的預約訂單'
            : '僅顯示目前選取校區的預約訂單'}
        </p>
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
          <>
          <div className="space-y-3 p-3 md:hidden">
            {orders.map((order) => {
              const statusPill = order.reservations[0] ? getStatusPill(order.reservations[0].status) : { label: '無', cls: '' }
              const paymentPill = getPaymentPill(order.payment_status)
              return <div key={order.id} className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-xs text-gray-500 dark:text-gray-400">訂單編號</div>
                    <div className="break-all font-mono text-sm" style={{ color: PRIMARY }}>{order.sn}</div>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-1 text-xs font-medium ${statusPill.cls}`}>{statusPill.label}</span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                  <div className="min-w-0"><div className="text-xs text-gray-500 dark:text-gray-400">學員</div><div className="truncate font-medium text-gray-900 dark:text-white">{order.user_name}</div></div>
                  <div><div className="text-xs text-gray-500 dark:text-gray-400">金額</div><div className="font-medium text-gray-900 dark:text-white">NT$ {(order.total_fee || 0).toLocaleString()}</div></div>
                </div>
                <div className="mt-3 flex items-center justify-between gap-2 border-t border-gray-200 pt-3 dark:border-gray-700">
                  <span className={`rounded-full px-2 py-1 text-xs font-medium ${paymentPill.cls}`}>{paymentPill.label}</span>
                  {order.amendment_balance && <span className="rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">{order.amendment_balance.amount>0?'待補款':'待退款'} NT$ {Math.abs(order.amendment_balance.amount).toLocaleString()}</span>}
                  <button type="button" onClick={() => setViewingId(order.id)} className="min-h-11 rounded-lg px-4 text-sm font-medium text-white" style={{ backgroundColor: PRIMARY }}>查看訂單</button>
                </div>
              </div>
            })}
            {orders.length === 0 && <div className="py-12 text-center text-sm text-gray-500 dark:text-gray-400">{total === 0 && !search && !statusFilter && !paymentFilter ? '尚未有訂單' : '沒有符合條件的訂單'}</div>}
          </div>
          <div className="hidden overflow-x-auto md:block">
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
                        {order.amendment_balance && <div className="mt-1 text-xs text-amber-800 dark:text-amber-200">{order.amendment_balance.amount>0?'待補款':'待退款'} NT$ {Math.abs(order.amendment_balance.amount).toLocaleString()}</div>}
                      </td>
                      <td className="px-5 py-2 text-right">
                        <button type="button" aria-label={`查看訂單 ${order.sn}`} onClick={() => setViewingId(order.id)} className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700"><Eye size={16} /></button>
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
          </>
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
  const [composingNotice, setComposingNotice] = useState(false)
  const [amending, setAmending] = useState(false)
  const { data: noticeAdmin } = useQuery({ queryKey: ['admin', 'me'], queryFn: fetchAdminMe })
  const canNotify = !readOnly && hasAdminPermission(noticeAdmin?.user, 'notifications') && hasAdminPermission(noticeAdmin?.user, 'orders')
    && !['campus_manager', 'campus_principal'].includes(noticeAdmin?.user?.role || '')

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
  const [groupLinkDraft, setGroupLinkDraft] = useState(order.line_group_url || '')
  const [groupLinkError, setGroupLinkError] = useState('')
  useEffect(() => { setGroupLinkDraft(order.line_group_url || ''); setGroupLinkError('') }, [order.id, order.line_group_url])
  const groupLinkMutation = useMutation({
    mutationFn: () => saveClassGroupLink(order.id, groupLinkDraft.trim()),
    onMutate: () => setGroupLinkError(''),
    onSuccess: (response) => { qc.invalidateQueries({ queryKey: ['admin', 'orders'] }); notify.success(response.msg) },
    onError: (error: any) => setGroupLinkError(error?.response?.data?.msg || '群組連結儲存失敗，請重試'),
  })
  const [confirmCompletionId, setConfirmCompletionId] = useState<number | null>(null)

  const resetOrderEdits = () => {
    const assignments: Record<number, number | null> = {}
    const bookings: Record<number, { date: string; start_time: string; end_time: string }> = {}
    order.reservations.forEach((reservation) => {
      assignments[reservation.id] = reservation.preferred_coach_id ?? null
      reservation.bookings.forEach((booking) => {
        bookings[booking.id] = {
          date: booking.date,
          start_time: formatTime(booking.start_time),
          end_time: formatTime(booking.end_time),
        }
      })
    })
    setCoachAssignments(assignments)
    setBookingEdits(bookings)
    setPaymentStatus(order.payment_status)
  }

  const [emailOpen, setEmailOpen] = useState(false)
  const [paymentLink, setPaymentLink] = useState('')
  useEffect(() => setPaymentLink(''), [order.id])
  const [cancelOpen, setCancelOpen] = useState(false)
  const [cancelForm, setCancelForm] = useState({ reason: 'schedule', reason_note: '', bank_name: '', account_number: '', account_holder: '' })
  const [refundChoice, setRefundChoice] = useState('auto')
  const [manualRefund, setManualRefund] = useState('')
  const { data: refundPreview } = useQuery({ queryKey: ['admin', 'orders', order.id, 'refund-preview'], queryFn: () => previewOrderRefund(order.id), enabled: cancelOpen })
  const selectedRule = refundPreview?.available_rules.find(rule => refundChoice === `rule:${rule.days_before}`)
  const manualRefundValid = manualRefund !== '' && Number.isInteger(Number(manualRefund)) && Number(manualRefund) >= 0 && Number(manualRefund) <= (refundPreview?.original_amount ?? -1)
  const displayedRefund = refundChoice === 'manual' ? (manualRefundValid ? Number(manualRefund) : null) : selectedRule && refundPreview
    ? Math.max(0, Math.round(refundPreview.original_amount * (selectedRule.refund_percent - Number(refundPreview.handling_fee_percent)) / 100))
    : (refundPreview?.refund_amount ?? null)
  const [emailForm, setEmailForm] = useState({
    recipient_email: order.user_email || '',
    subject: `[${order.sn}] 課程通知`,
    message: '',
  })
  const [emailRequestKey, setEmailRequestKey] = useState(() => crypto.randomUUID())
  const [emailError, setEmailError] = useState('')
  const { data: emailMode } = useQuery({ queryKey: ['admin', 'order-email-mode', order.id], queryFn: () => fetchOrderEmailMode(order.id), enabled: emailOpen })
  const [emailUnconfirmed, setEmailUnconfirmed] = useState(false)
  const emailErrorRef = useRef<HTMLParagraphElement>(null)
  const emailDialogRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!emailOpen) return
    const previous = document.activeElement as HTMLElement | null
    emailDialogRef.current?.querySelector<HTMLInputElement>('input')?.focus()
    return () => { previous?.focus() }
  }, [emailOpen])
  useEffect(() => { if (emailError) emailErrorRef.current?.scrollIntoView({ block: 'nearest' }) }, [emailError])
  const emailAddressValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailForm.recipient_email.trim())
  const emailValid = emailAddressValid && !!emailForm.subject.trim() && !!emailForm.message.trim()
  const openOrderEmail = () => { setEmailRequestKey(crypto.randomUUID()); setEmailError(''); setEmailUnconfirmed(false); setEmailOpen(true) }

  const emailMutation = useMutation({
    mutationFn: () => sendOrderEmail(order.id, { ...emailForm, request_key: emailRequestKey }),
    onMutate: () => setEmailError(''),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['admin', 'notification-deliveries'] })
      if (res.code === 200) {
        notify.success(res.msg)
        setEmailOpen(false)
      } else if (res.code === 202) {
        setEmailError(res.msg); setEmailUnconfirmed(true)
      } else {
        setEmailError(res.msg)
      }
    },
    onError: (e: any) => {
      const data = e.response?.data
      const text = ['msg', 'detail', 'recipient_email', 'subject', 'message', 'request_key']
        .map(key => data?.[key]).map(value => Array.isArray(value) ? value[0] : value).find(value => typeof value === 'string' && value)
      setEmailError(text || '寄送結果未確認，請查詢發送紀錄，避免重複寄送。')
      if (!e.response || e.response.status >= 500) setEmailUnconfirmed(true)
      qc.invalidateQueries({ queryKey: ['admin', 'notification-deliveries'] })
    },
  })
  const paymentLinkMutation = useMutation({
    mutationFn: () => fetchGuestPaymentLink(order.id),
    onSuccess: ({ path, valid_days }) => {
      const link = new URL(path, window.location.origin).toString()
      setPaymentLink(link)
      notify.success(`付款連結已產生（${valid_days} 天有效），請按下方按鈕複製`)
    },
    onError: (error: any) => { setPaymentLink(''); notify.error(error?.response?.data?.msg || '無法產生付款連結') },
  })
  const copyPaymentLink = async () => {
    try {
      await navigator.clipboard.writeText(paymentLink)
      notify.success('付款連結已複製，請只傳給此訂單的客人')
    } catch {
      notify.error('無法自動複製；請點連結欄位後按 Ctrl+C')
    }
  }
  const cancelMutation = useMutation({ mutationFn: () => requestOrderCancellation(order.id, { reason: cancelForm.reason, reason_note: cancelForm.reason_note, refund_bank: { bank_name: cancelForm.bank_name, account_number: cancelForm.account_number, account_holder: cancelForm.account_holder }, ...(!refundPreview?.requires_cash_review && refundChoice === 'manual' ? { manual_refund_amount: Number(manualRefund) } : !refundPreview?.requires_cash_review && refundChoice.startsWith('rule:') ? { selected_rule_days_before: Number(refundChoice.slice(5)) } : {}) }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'orders'] }); setCancelOpen(false); notify.success('取消申請已建立，請到訂單內確認退款金額') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '建立取消申請失敗') })
  const completeCourse = useMutation({
    mutationFn: (reservationId: number) => completeOrderCourse(order.id, reservationId),
    onSuccess: (response) => {
      setConfirmCompletionId(null)
      qc.invalidateQueries({ queryKey: ['admin', 'orders'] })
      qc.invalidateQueries({ queryKey: ['admin', 'bookings'] })
      qc.invalidateQueries({ queryKey: ['admin', 'evaluations'] })
      qc.invalidateQueries({ queryKey: ['admin', 'payroll'] })
      notify.success(response.msg)
    },
    onError: (error: any) => notify.error(error?.response?.data?.msg || error?.response?.data?.detail || '完課確認失敗'),
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
  const sharedPaymentHeld = order.reservations.some((r) => r.shared_course_class_id && r.shared_class_status === 'collecting')
  const statusPill = firstR ? getStatusPill(firstR.status) : { label: '無', cls: '' }
  const paymentPill = getPaymentPill(paymentStatus)
  const courseBookings = order.reservations.flatMap((r) => r.bookings)
  const invalidBooking = courseBookings.find((booking) => {
    const edit = bookingEdits[booking.id]
    return !edit?.date || !edit.start_time || !edit.end_time || edit.end_time <= edit.start_time
  })
  const hasBookingChanges = courseBookings.some((booking) => {
    const edit = bookingEdits[booking.id]
    return edit && (
      edit.date !== booking.date ||
      edit.start_time !== formatTime(booking.start_time) ||
      edit.end_time !== formatTime(booking.end_time)
    )
  })
  const hasCoachChanges = order.reservations.some((reservation) =>
    !reservation.is_preferred_coach &&
    coachAssignments[reservation.id] !== (reservation.preferred_coach_id ?? null),
  )
  const hasOrderChanges = hasBookingChanges || hasCoachChanges || paymentStatus !== order.payment_status

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 animate-fadeIn" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white dark:bg-gray-800 shadow-2xl flex flex-col animate-slideIn">
        <div className="relative px-4 py-4 text-white sm:px-6" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
          <div className="flex flex-wrap items-center gap-2 pr-10">
            <h2 className="mr-1 font-mono text-base font-semibold sm:text-lg">{order.sn}</h2>
            {!editing && canNotify && <button onClick={() => setComposingNotice(true)} className="min-h-10 rounded-md bg-white/20 px-3 py-2 text-xs font-medium hover:bg-white/30">發送站內通知</button>}
            {!editing && !readOnly && (
              <>
                <button
                  onClick={() => { resetOrderEdits(); setEditing(true) }}
                  className="flex min-h-10 items-center gap-1 rounded-md bg-white/20 px-3 py-2 text-xs font-medium hover:bg-white/30"
                >
                  <Edit2 size={12} />付款／排課
                </button>
                <button onClick={() => setAmending(true)} className="min-h-10 rounded-md bg-white/20 px-3 py-2 text-xs font-medium hover:bg-white/30">修改課程／人數與差額</button>
                <button
                  onClick={openOrderEmail}
                  className="flex min-h-10 items-center gap-1 rounded-md bg-white/20 px-3 py-2 text-xs font-medium hover:bg-white/30"
                >
                  <Mail size={12} />寄信
                </button>
                {(!order.cancellation || order.cancellation.status === 'rejected') && <button onClick={() => setCancelOpen(true)} className="min-h-11 rounded-md bg-red-500/80 px-3 py-2 text-xs font-medium hover:bg-red-500">{order.cancellation ? '重新申請取消／退款' : '取消／退款'}</button>}
              </>
            )}
          </div>
          <button onClick={onClose} aria-label="關閉訂單明細" className="absolute right-2 top-2 flex h-10 w-10 items-center justify-center rounded-lg text-white/80 hover:bg-white/20 hover:text-white"><X size={20} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex flex-wrap gap-2">
            <span className={`inline-flex items-center px-3 py-1 text-xs font-medium rounded-full ${statusPill.cls}`}>{statusPill.label}</span>
            <span className={`inline-flex items-center px-3 py-1 text-xs font-medium rounded-full ${paymentPill.cls}`}>{paymentPill.label}</span>
          </div>
          {order.amendment_balance && <section className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100"><h3 className="font-semibold">訂單修改差額尚未結清</h3><p className="mt-2">{order.amendment_balance.amount>0?'待補款':'待退款'} NT$ {Math.abs(order.amendment_balance.amount).toLocaleString('zh-TW')}</p><p className="mt-1 text-xs leading-6">{['requested','approved'].includes(order.cancellation?.status||'')?'取消流程已暫停這筆差額，請至下方「取消與退款處理」核對實收款。':'上方付款狀態是原訂單付款，不代表這筆差額已收退。請在下方「差額回報與核對」處理；未核對前不視為結清。'}</p></section>}
          {!readOnly&&<AmendmentBalancesPanel orderId={order.id} cancellationStatus={order.cancellation?.status}/>}

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2"><User size={14} style={{ color: PRIMARY }} />訂單聯絡資料</h3>
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-2 text-sm">
              <div className="flex justify-between gap-4"><span className="shrink-0 text-gray-500 dark:text-gray-300">聯絡人姓名</span><span className="min-w-0 break-all text-right text-gray-900 dark:text-white">{order.booking_contact?.name || order.name || order.user_name}</span></div>
              <div className="flex justify-between gap-4"><span className="shrink-0 text-gray-500 dark:text-gray-300">Email</span><span className="min-w-0 break-all text-right font-mono text-gray-900 dark:text-white">{order.booking_contact?.email || order.user_email || '—'}</span></div>
              <div className="flex justify-between gap-4"><span className="shrink-0 text-gray-500 dark:text-gray-300">聯絡電話</span><span className="min-w-0 break-all text-right text-gray-900 dark:text-white">{order.booking_contact?.phone || '—'}</span></div>
              <div className="flex justify-between gap-4"><span className="shrink-0 text-gray-500 dark:text-gray-300">通訊軟體</span><span className="min-w-0 break-all text-right text-gray-900 dark:text-white">{order.booking_contact?.messenger_id ? `${order.booking_contact.messenger_type} ${order.booking_contact.messenger_id}` : '—'}</span></div>
              <div className="flex justify-between gap-4"><span className="shrink-0 text-gray-500 dark:text-gray-300">訂購會員</span><span className="min-w-0 break-all text-right text-gray-900 dark:text-white">{order.user_name || '訪客'}</span></div>
            </div>
          </section>

          {!readOnly && <section className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">上課群組連結</h3>
            <p className="mt-2 text-xs leading-5 text-gray-500 dark:text-gray-400">先由行政建立群組，再貼上完整 HTTPS 邀請連結。已付款會員可在這張訂單加入；通知依「自動通知」的群組邀請範本與天數排程，儲存不會立即寄信或重寄已發送通知。</p>
            <label className="mt-3 block text-xs font-medium text-gray-700 dark:text-gray-300">群組邀請網址
              <input aria-label="群組邀請網址" value={groupLinkDraft} onChange={event => { setGroupLinkDraft(event.target.value); setGroupLinkError('') }} disabled={groupLinkMutation.isPending} placeholder="https://line.me/ti/g/..." className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white" />
            </label>
            {groupLinkError && <p role="alert" className="mt-2 text-xs text-red-600 dark:text-red-400">{groupLinkError}</p>}
            <div className="mt-3 flex flex-wrap gap-2"><button type="button" disabled={groupLinkMutation.isPending || groupLinkDraft.trim() === (order.line_group_url || '')} onClick={() => groupLinkMutation.mutate()} className="min-h-11 rounded-lg bg-violet-600 px-4 text-sm font-medium text-white disabled:opacity-50">{groupLinkMutation.isPending ? '儲存中…' : groupLinkDraft.trim() ? '儲存群組連結' : '移除群組連結'}</button><button type="button" disabled={groupLinkMutation.isPending} onClick={() => { setGroupLinkDraft(order.line_group_url || ''); setGroupLinkError('') }} className="min-h-11 rounded-lg border border-gray-300 px-4 text-sm text-gray-700 dark:border-gray-600 dark:text-gray-200">取消變更</button></div>
            <ClassGroupQRPanel orderId={order.id} url={order.line_group_qr_url || ''} />
          </section>}

          <section>
            <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">訂單歸屬與歷程</h3>
            <div className="rounded-lg bg-gray-50 p-4 text-sm dark:bg-gray-700"><div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">校區</span><b>{order.campus_name || '未設定'}</b></div><div className="mt-2 flex justify-between"><span className="text-gray-500 dark:text-gray-400">行銷來源</span><span>{order.marketing_source || '未填寫'}{order.marketing_source_detail ? ` · ${order.marketing_source_detail}` : ''}</span></div></div>
            <div className="mt-3 space-y-2">{order.revisions?.map(revision => <details key={revision.id} className="rounded-lg border border-gray-100 text-xs dark:border-gray-700">
              <summary className="min-h-11 cursor-pointer px-3 py-3 text-gray-900 dark:text-gray-100">
                <span className="ml-1 break-words">第 {revision.version} 版 · {REVISION_LABEL[revision.change_type] || revision.change_type}{revision.reason ? ` · ${revision.change_type === 'cancel' ? (CANCELLATION_REASON_LABEL[revision.reason] || revision.reason) : revision.reason}` : ''}</span>
                <b className={`ml-2 inline-block ${revision.difference_amount > 0 ? 'text-red-600 dark:text-red-400' : revision.difference_amount < 0 ? 'text-emerald-600 dark:text-emerald-400' : ''}`}>{revision.difference_amount ? `${revision.difference_amount > 0 ? '+' : ''}NT$ ${revision.difference_amount.toLocaleString()}` : '無差額'}</b>
                <span className="mt-1 block text-gray-500 dark:text-gray-400">點選查看當時課程內容</span>
              </summary>
              <div className="space-y-3 border-t border-gray-100 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800">
                <p className="text-gray-500 dark:text-gray-400">這是當時保存的資料，不代表目前訂單，也不會還原或修改訂單。</p>
                {revision.snapshot?.reservations?.length ? revision.snapshot.reservations.map(item => <div key={item.id} className="space-y-1 break-words rounded border border-gray-200 bg-white p-3 text-gray-800 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100">
                  <p className="font-semibold">{item.resort_name || (item.resort_id ? `雪場（舊資料編號 ${item.resort_id}）` : '未設定雪場')} · {item.course_template_name || item.course_type_name || '舊版未保存課程名稱'}</p>
                  <p>教練：{item.coach_name || (item.coach_id ? `舊資料編號 ${item.coach_id}` : '未安排')} · {item.people ?? 0} 人</p>
                  <p>當時應付：NT$ {(item.payable ?? 0).toLocaleString()}</p>
                  {item.bookings?.map(booking => <p key={booking.id}>{booking.date} · {booking.start_time}–{booking.end_time}</p>)}
                </div>) : <p className="text-gray-500 dark:text-gray-400">這筆舊紀錄沒有保存課程明細。</p>}
              </div>
            </details>)}</div>
            {order.cancellation && <CancellationStatusPanel cancellation={order.cancellation} readOnly={readOnly} />}
          </section>

          {order.reservations.map((r, idx) => {
            const availableCoaches = r.available_coaches || []
            const selectedCoachId = coachAssignments[r.id] ?? null
            const selectedCoachMissing = !!selectedCoachId && !availableCoaches.some((coach) => coach.id === selectedCoachId)
            const reservationStatusPill = getStatusPill(r.status)
            const isSchedulingFailed = r.status === 'auto_assignment_failed' || r.status === 'manual_assignment_needed'
            const isStudentSpecifiedCoach = Boolean(r.is_preferred_coach && r.preferred_coach_id)
            const canEditCourse = editing && r.status !== 'completed' && !r.shared_course_class_id
            const canComplete = !readOnly && !editing && order.payment_status === 'paid' &&
              ['auto_assigned', 'manually_assigned', 'form_filled'].includes(r.status) &&
              Boolean(r.preferred_coach_id) && r.bookings.length > 0 &&
              r.bookings.every(b => new Date(`${b.date}T${formatTime(b.end_time)}:00`).getTime() <= Date.now())
            return (
            <section key={r.id}>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2"><MapPin size={14} style={{ color: PRIMARY }} />課程 {order.reservations.length > 1 ? `#${idx + 1}` : ''}</h3>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${reservationStatusPill.cls}`}>
                  {reservationStatusPill.label}
                </span>
              </div>
              {r.shared_course_class_id && <p className="mb-3 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm leading-6 text-violet-900 dark:border-violet-700 dark:bg-violet-900/20 dark:text-violet-100">
                跨訂單團體班（{r.shared_class_status === 'ready' ? '已成班' : r.shared_class_status === 'collecting' ? '湊班中' : '已取消'}）：時段與教練需整班調整，不能只修改這張訂單。{r.shared_class_status === 'collecting' ? '成班後才能確認付款。' : '付款狀態可依這張訂單單獨編輯。'}
              </p>}
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">雪場</span><span className="text-gray-900 dark:text-white">{r.resort}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">課程類型</span><span className="text-gray-900 dark:text-white">{r.course_type}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">能力等級</span><span className="text-gray-900 dark:text-white">{formatAbilityLevel(r.ability_level)}</span></div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-500">教練</span>
                  {canEditCourse && isStudentSpecifiedCoach ? (
                    <div className="text-right">
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <span className="text-gray-900 dark:text-white">{r.preferred_coach || '指定教練'}</span>
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:bg-amber-900/40 dark:text-amber-200">
                          客人指定
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">不可由後台更換</p>
                    </div>
                  ) : canEditCourse ? (
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
                <div className="flex justify-between"><span className="text-gray-500">語言</span><span className="text-gray-900 dark:text-white">{LANGUAGE_LABEL[r.language] || r.language || '未填寫'}</span></div>
                {r.equipment_assistance_time_label && (
                  <div className="flex justify-between"><span className="text-gray-500">裝備協助時段</span><span className="text-gray-900 dark:text-white">{r.equipment_assistance_time_label}</span></div>
                )}
                <div className="flex justify-between"><span className="text-gray-500">人數</span><span className="text-gray-900 dark:text-white">{r.number_of_people} 人</span></div>
              </div>

              {isSchedulingFailed && (
                <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-700 dark:border-red-900/60 dark:bg-red-900/20 dark:text-red-300">
                  這筆課程尚未排課成功。未付款的排課失敗訂單會在建立後 30 分鐘自動取消；也可以請客人改選其他日期後重新下單。
                </div>
              )}

              {canComplete && <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm text-violet-900 dark:border-violet-700 dark:bg-violet-900/20 dark:text-violet-100">
                <p>課程都已結束。確認實際授課完成後，才會納入教練時數與薪資，並建立學員評量。</p>
                {confirmCompletionId === r.id ? <div className="mt-3 flex flex-wrap gap-2">
                  <button onClick={() => setConfirmCompletionId(null)} disabled={completeCourse.isPending} className="rounded-lg border border-violet-300 px-3 py-2 text-sm disabled:opacity-40">返回</button>
                  <button onClick={() => completeCourse.mutate(r.id)} disabled={completeCourse.isPending} className="rounded-lg bg-violet-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40">{completeCourse.isPending ? '處理中…' : '確認已授課完成'}</button>
                </div> : <button onClick={() => setConfirmCompletionId(r.id)} className="mt-3 rounded-lg bg-violet-600 px-3 py-2 text-sm font-semibold text-white">標記課程完成</button>}
              </div>}
              {r.status === 'completed' && <p className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-200">已確認完課；時段與教練已鎖定，評量可在「學習評量」查看，教練時數可在「薪資結算」計算。</p>}

              {r.bookings.length > 0 && (
                <div className="mt-3">
                  <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 flex items-center gap-1"><Calendar size={12} />課程時段</h4>
                  <div className="space-y-2">
                    {r.bookings.map((b) => {
                      return (
                        <div key={b.id} className="flex flex-col gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg text-sm md:flex-row md:items-center">
                          <Calendar size={16} className="text-gray-400" />
                          <span className="font-medium text-gray-900 dark:text-white">{b.date}</span>
                          <span className="text-gray-500 dark:text-gray-300">{formatTime(b.start_time)} - {formatTime(b.end_time)}</span>
                          {canEditCourse && <span className="text-xs text-purple-700 dark:text-purple-300">改日期或時段請先取消本次編輯，再使用「修改課程／人數與差額」。</span>}
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
                {editing && !sharedPaymentHeld ? (
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
              <div className="flex justify-between"><span className="text-gray-500">付款方式</span><span className="text-gray-900 dark:text-white">{PAYMENT_METHOD_LABEL[order.payment_method] || order.payment_method || '未設定'}</span></div>
              {order.payment_method === 'TT' && (
                <div className="flex justify-between">
                  <span className="text-gray-500">匯款後五碼</span>
                  <span className="font-mono text-gray-900 dark:text-white">{order.bank_account || '未填寫'}</span>
                </div>
              )}

              <div className="flex justify-between pt-2 border-t border-gray-200 dark:border-gray-600">
                <span className="font-medium text-gray-900 dark:text-white">總金額</span>
                <span className="text-lg font-bold" style={{ color: PRIMARY }}>NT$ {(order.total_fee || 0).toLocaleString()}</span>
              </div>
              {!readOnly && !editing && !sharedPaymentHeld && order.user === null && ['unpaid', 'pending'].includes(paymentStatus) && (
                <div className="border-t border-gray-200 pt-3 dark:border-gray-600">
                  <button type="button" onClick={() => paymentLinkMutation.mutate()} disabled={paymentLinkMutation.isPending} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-violet-300 bg-white px-3 py-2 font-medium text-violet-700 hover:bg-violet-50 disabled:opacity-50 dark:border-violet-600 dark:bg-gray-800 dark:text-violet-300 dark:hover:bg-gray-700">
                    {paymentLinkMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Link2 size={15} />}
                    產生訪客付款連結
                  </button>
                  {paymentLink && <div className="mt-3">
                    <label className="block text-xs font-medium text-gray-700 dark:text-gray-200">新付款連結（點一下可全選）
                      <input aria-label="新付款連結" type="text" readOnly value={paymentLink} onFocus={event => event.currentTarget.select()} className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 font-mono text-xs text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-white" />
                    </label>
                    <button type="button" onClick={copyPaymentLink} className="mt-2 min-h-10 rounded-lg bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-700">複製連結</button>
                  </div>}
                  <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">舊連結失效時，可在這裡重新產生；只傳給此訂單的客人，不要公開張貼。</p>
                </div>
              )}
            </div>
          </section>

          <div className="text-xs text-gray-500 text-center">建立於 {formatCreatedAt(order.created_at)}</div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          {editing && !readOnly ? (
            <>
              <p role={invalidBooking ? 'alert' : undefined} className={`w-full text-sm ${invalidBooking ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400'}`}>
                {invalidBooking ? '課程結束時間須晚於開始時間，請檢查日期與時段。' : !hasOrderChanges ? '尚未修改任何資料。' : '請確認課程、教練與付款狀態後再儲存。'}
              </p>
              <button
                onClick={() => { resetOrderEdits(); setEditing(false) }}
                disabled={saveMutation.isPending}
                className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={() => saveMutation.mutate('save')}
                disabled={saveMutation.isPending || !hasOrderChanges || Boolean(invalidBooking)}
                className="px-4 py-2 bg-white dark:bg-gray-700 border border-[#8b5cf6] text-sm font-medium rounded-lg hover:bg-[#8b5cf6]/5 disabled:opacity-50 flex items-center gap-2"
                style={{ color: PRIMARY }}
              >
                {saveMutation.isPending && <Loader2 size={14} className="animate-spin" />}
                <Save size={14} />只儲存
              </button>
              <button
                onClick={() => saveMutation.mutate('schedule')}
                disabled={saveMutation.isPending || !hasOrderChanges || Boolean(invalidBooking)}
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

      {amending && <OrderAmendmentDialog orderId={order.id} onClose={() => setAmending(false)} />}
      {/* Email Modal */}
      {cancelOpen && <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4 animate-fadeIn"><div className="flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-2xl bg-white shadow-xl dark:bg-gray-800"><div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}><div><h3 className="text-lg font-semibold">取消訂單與退款試算</h3><p className="mt-0.5 text-xs text-white/80">{order.sn}</p></div><button onClick={() => setCancelOpen(false)} aria-label="關閉" className="rounded-lg p-1 text-white/80 hover:bg-white/10 hover:text-white"><X size={18} /></button></div><div className="space-y-4 overflow-y-auto p-6">{refundPreview && <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 text-sm text-violet-800 dark:border-violet-800 dark:bg-violet-900/20 dark:text-violet-300"><b className="text-lg">{refundPreview.requires_cash_review?'退款金額待核對實收款':`預計退款 ${displayedRefund === null ? '請輸入有效金額' : `NT$ ${displayedRefund.toLocaleString()}`}`}</b><p className="mt-1">{refundPreview.requires_cash_review ? '訂單有未結清差額。先建立取消申請，再核對原款、已收補款與已退款；不會自動算入尚未收款的補款。' : refundChoice === 'manual' ? '特殊金額，請在補充說明記錄原因' : `距課程 ${refundPreview.days_before} 天 · 退 ${selectedRule?.refund_percent ?? refundPreview.refund_percent}% · 再扣原價的 ${refundPreview.handling_fee_percent}% 手續費`}</p></div>}<div><label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">退款方案</label><select aria-label="退款方案" disabled={refundPreview?.requires_cash_review} className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white" value={refundChoice} onChange={e => setRefundChoice(e.target.value)}><option value="auto">{refundPreview?.requires_cash_review?'待核對實收款（建立後人工確認）':'依上課日期自動計算'}</option>{refundPreview?.available_rules.map(rule => <option key={rule.days_before} value={`rule:${rule.days_before}`}>課前至少 {rule.days_before} 天：退 {rule.refund_percent}%</option>)}<option value="manual">特殊情況：手動輸入金額</option></select>{!refundPreview?.requires_cash_review && refundChoice === 'manual' && <label className="mt-2 block text-sm text-gray-700 dark:text-gray-300">退款金額（不可超過 NT$ {refundPreview?.original_amount.toLocaleString() ?? '—'}）<input aria-label="手動退款金額" type="number" min="0" max={refundPreview?.original_amount} step="1" className="mt-1 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-600 dark:bg-gray-700 dark:text-white" value={manualRefund} onChange={e => setManualRefund(e.target.value)} /></label>}</div><div><label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">取消原因</label><select className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" value={cancelForm.reason} onChange={e => setCancelForm({ ...cancelForm, reason: e.target.value })}><option value="schedule">行程變更</option><option value="health">健康因素</option><option value="weather">天候因素</option><option value="duplicate">重複訂單</option><option value="other">其他</option></select></div><div><label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">補充說明</label><textarea className="w-full resize-none rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 outline-none focus:ring-2 focus:ring-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" rows={3} placeholder="請說明取消原因" value={cancelForm.reason_note} onChange={e => setCancelForm({ ...cancelForm, reason_note: e.target.value })} /></div>{(refundPreview?.requires_cash_review || !['newebpay', 'credit_card', 'apple_pay', 'google_pay'].includes(order.payment_method)) && <div className="space-y-3 rounded-lg border border-gray-200 p-4 dark:border-gray-700"><p className="text-sm font-semibold text-gray-900 dark:text-white">退款帳戶</p><input className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="退款銀行" value={cancelForm.bank_name} onChange={e => setCancelForm({ ...cancelForm, bank_name: e.target.value })} /><input className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="退款帳號" value={cancelForm.account_number} onChange={e => setCancelForm({ ...cancelForm, account_number: e.target.value })} /><input className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="退款戶名" value={cancelForm.account_holder} onChange={e => setCancelForm({ ...cancelForm, account_holder: e.target.value })} /></div>}</div><div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700"><button onClick={() => setCancelOpen(false)} className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">返回</button><button onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending || !refundPreview || ((refundPreview.requires_cash_review || !['newebpay','credit_card','apple_pay','google_pay'].includes(order.payment_method)) && ![cancelForm.bank_name,cancelForm.account_number,cancelForm.account_holder].every(value=>value.trim())) || (!refundPreview?.requires_cash_review && refundChoice === 'manual' && !manualRefundValid)} className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">{cancelMutation.isPending && <Loader2 size={14} className="animate-spin" />}確認建立取消申請</button></div></div></div>}
      {composingNotice && <ManualNotificationComposer initialTarget={{ kind: 'order', id: order.id, label: order.sn }} onClose={() => setComposingNotice(false)} />}
      {emailOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 animate-fadeIn">
          <div ref={emailDialogRef} role="dialog" aria-modal="true" aria-label="寄信給訂單聯絡人" className="flex max-h-[calc(100dvh-32px)] w-full max-w-md flex-col overflow-hidden rounded-2xl bg-white shadow-xl dark:bg-gray-800" onKeyDown={event => {
            if (event.key === 'Escape' && !emailMutation.isPending) { setEmailOpen(false); return }
            if (event.key !== 'Tab') return
            const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled)'))
            if (!items.length) { event.preventDefault(); return }
            const first = items[0], last = items[items.length - 1]
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
          }}>
            <div className="rounded-t-2xl px-6 py-4 text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
              <h3 className="text-lg font-semibold">寄信給訂單聯絡人</h3>
              <p className="text-xs text-white/80 mt-0.5">{order.sn}</p>
            </div>
            <div className="overflow-y-auto p-6 space-y-4">
              {emailMode?.local_test && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm font-medium text-amber-900 dark:bg-amber-900/30 dark:text-amber-100">本機郵件測試模式：只寫入本機郵件輸出，不會對外寄送。站內通知仍會同步到這筆測試訂單的會員。</p>}
              <p className="rounded-lg bg-blue-50 p-3 text-sm text-blue-900 dark:bg-blue-900/30 dark:text-blue-100">成功寄出後，只同步到能明確對應此收件信箱的訂購人或已綁定會員；不會只憑相同 Email 認領陌生帳號。共用信箱無法確認時，請改用「發送站內通知」指定會員。</p>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">收件人</label>
                <input
                  type="email"
                  aria-label="寄信收件人"
                  maxLength={200}
                  disabled={emailMutation.isPending || emailUnconfirmed}
                  value={emailForm.recipient_email}
                  onChange={(e) => { setEmailForm({ ...emailForm, recipient_email: e.target.value }); setEmailError('') }}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                />
                {!!emailForm.recipient_email && !emailAddressValid && <p className="mt-1 text-xs text-red-600 dark:text-red-300">請填寫正確的 Email 地址。</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">主旨</label>
                <input
                  type="text"
                  aria-label="寄信主旨"
                  maxLength={200}
                  disabled={emailMutation.isPending || emailUnconfirmed}
                  value={emailForm.subject}
                  onChange={(e) => { setEmailForm({ ...emailForm, subject: e.target.value }); setEmailError('') }}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">內容</label>
                <textarea
                  aria-label="寄信內容"
                  maxLength={10000}
                  disabled={emailMutation.isPending || emailUnconfirmed}
                  value={emailForm.message}
                  onChange={(e) => { setEmailForm({ ...emailForm, message: e.target.value }); setEmailError('') }}
                  rows={6}
                  placeholder="輸入信件內容..."
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 resize-none"
                />
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">系統會自動加上品牌簽名；只寄送一次，結果未確認時請先查詢，不要反覆重寄。</p>
              </div>
              {emailError && <p ref={emailErrorRef} role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">{emailError}</p>}
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
              <button onClick={() => setEmailOpen(false)} disabled={emailMutation.isPending} className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50">取消</button>
              <button
                onClick={() => emailMutation.mutate()}
                disabled={emailMutation.isPending || !emailValid}
                className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
                style={{ backgroundColor: PRIMARY }}
              >
                {emailMutation.isPending && <Loader2 size={14} className="animate-spin" />}
                <Mail size={14} />{emailMutation.isPending ? '處理中…' : emailUnconfirmed ? '查詢寄送結果' : '寄出'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
