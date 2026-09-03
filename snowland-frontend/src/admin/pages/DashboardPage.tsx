/**
 * SnowLand 後台儀表板（接 API）
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ShoppingBag, ShoppingCart, DollarSign, TrendingUp, Users, Calendar, CalendarCheck, Loader2, AlertCircle } from 'lucide-react'
import { fetchDashboard, type Period } from '../api/dashboard'

const PRIMARY = '#8b5cf6'

const periodOptions: { value: Period; label: string }[] = [
  { value: 'today', label: '今天' },
  { value: 'yesterday', label: '昨天' },
  { value: 'week', label: '本週' },
  { value: 'month', label: '本月' },
]

const STATUS_CLS: Record<string, string> = {
  paid: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  unpaid: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  expired: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  refunded: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
}
const STATUS_LABEL: Record<string, string> = {
  paid: '已付款', pending: '待確認', unpaid: '未付款', expired: '已過期', refunded: '已退款',
}

function PeriodSelector({ value, onChange }: { value: Period; onChange: (p: Period) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-1 shadow-sm">
      {periodOptions.map((option) => (
        <button key={option.value} onClick={() => onChange(option.value)} className="px-4 py-2 text-sm font-medium rounded-md transition-all"
          style={value === option.value ? { backgroundColor: PRIMARY, color: 'white' } : undefined}>
          <span className={value === option.value ? '' : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'}>{option.label}</span>
        </button>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const [period, setPeriod] = useState<Period>('month')

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'dashboard', period],
    queryFn: () => fetchDashboard(period),
  })

  const stats = data?.stats || { orders: 0, revenue: 0, members: 0, avg_order_value: 0 }
  const topItems = data?.top_items || []
  const recentOrders = data?.recent_orders || []
  const marketingSources = data?.marketing_sources || []
  const campusSummary = data?.campus_summary || []
  const maxQuantity = topItems.length > 0 ? Math.max(...topItems.map((i) => i.quantity)) : 1

  return (
    <div className="space-y-6">
      {/* 統計區塊 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5">
          <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Calendar size={18} style={{ color: PRIMARY }} />統計數據
          </h3>
          <PeriodSelector value={period} onChange={setPeriod} />
        </div>

        {error ? (
          <div className="py-12 text-center"><AlertCircle size={32} className="mx-auto mb-3 text-red-500" /><p className="text-sm text-red-600">載入失敗</p></div>
        ) : (
          <div className="relative">
            {isLoading && (
              <div className="absolute inset-0 bg-white/70 dark:bg-gray-800/70 flex items-center justify-center z-10 rounded-xl">
                <Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} />
              </div>
            )}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-gray-50 dark:bg-gray-700 rounded-xl p-4">
                <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900/50 rounded-lg flex items-center justify-center mb-2">
                  <ShoppingCart size={20} className="text-blue-600 dark:text-blue-400" />
                </div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">{stats.orders}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">訂單數</div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 rounded-xl p-4">
                <div className="w-10 h-10 bg-green-100 dark:bg-green-900/50 rounded-lg flex items-center justify-center mb-2">
                  <DollarSign size={20} className="text-green-600 dark:text-green-400" />
                </div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white whitespace-nowrap">NT$ {stats.revenue.toLocaleString()}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">營收</div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 rounded-xl p-4">
                <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/50 rounded-lg flex items-center justify-center mb-2">
                  <Users size={20} className="text-purple-600 dark:text-purple-400" />
                </div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">{stats.members}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">活躍學員</div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 rounded-xl p-4">
                <div className="w-10 h-10 bg-orange-100 dark:bg-orange-900/50 rounded-lg flex items-center justify-center mb-2">
                  <TrendingUp size={20} className="text-orange-600 dark:text-orange-400" />
                </div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white whitespace-nowrap">NT$ {stats.avg_order_value.toLocaleString()}</div>
                <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">平均客單價</div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <SummaryTable title="各校區營運" empty="此時段沒有校區資料" rows={campusSummary} />
        <SummaryTable title="客戶從哪裡來" empty="此時段沒有來源資料" rows={marketingSources} />
      </div>

      {/* 熱門課程 TOP 5 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2 mb-5">
          <ShoppingBag size={18} style={{ color: PRIMARY }} />熱門課程 TOP 5
        </h3>
        {topItems.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <ShoppingBag size={48} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm font-medium">此時段沒有銷售資料</p>
          </div>
        ) : (
          <div className="space-y-3">
            {topItems.map((item, index) => (
              <div key={item.id} className="flex items-center gap-3">
                <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                  index === 0 ? 'bg-yellow-100 text-yellow-700' : index === 1 ? 'bg-gray-200 text-gray-600' :
                  index === 2 ? 'bg-orange-100 text-orange-700' : 'bg-gray-100 text-gray-500'
                }`}>{index + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 dark:text-white truncate">{item.name}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full h-2">
                      <div className="h-2 rounded-full transition-all" style={{ width: `${(item.quantity / maxQuantity) * 100}%`, backgroundColor: PRIMARY }} />
                    </div>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-sm font-bold whitespace-nowrap" style={{ color: PRIMARY }}>{item.quantity} 堂</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">NT$ {item.revenue.toLocaleString()}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 最近訂單 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
          <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <CalendarCheck size={18} style={{ color: PRIMARY }} />最近訂單
          </h3>
        </div>
        {recentOrders.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <CalendarCheck size={48} className="mx-auto mb-3 opacity-30" /><p className="text-sm font-medium">暫無訂單資料</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="text-left px-5 py-3 font-medium text-gray-600 dark:text-gray-300">訂單編號</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600 dark:text-gray-300">學員</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600 dark:text-gray-300">金額</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600 dark:text-gray-300">狀態</th>
                  <th className="text-left px-5 py-3 font-medium text-gray-600 dark:text-gray-300">時間</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {recentOrders.map((o) => (
                  <tr key={o.sn} className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer">
                    <td className="px-5 py-3 font-mono text-sm font-medium whitespace-nowrap" style={{ color: PRIMARY }}>{o.sn}</td>
                    <td className="px-5 py-3 text-sm text-gray-900 dark:text-white whitespace-nowrap">{o.member}</td>
                    <td className="px-5 py-3 text-sm font-medium text-gray-900 dark:text-white whitespace-nowrap">NT$ {o.amount.toLocaleString()}</td>
                    <td className="px-5 py-3 whitespace-nowrap">
                      <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${STATUS_CLS[o.status] || STATUS_CLS.unpaid}`}>{STATUS_LABEL[o.status] || o.status}</span>
                    </td>
                    <td className="px-5 py-3 text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">{o.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function SummaryTable({ title, empty, rows }: { title: string; empty: string; rows: { name: string; orders: number; revenue: number }[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
      <div className="border-b border-gray-100 px-5 py-4 dark:border-gray-700"><h3 className="font-semibold text-gray-900 dark:text-white">{title}</h3></div>
      {rows.length === 0 ? <p className="px-5 py-10 text-center text-sm text-gray-400">{empty}</p> : (
        <div className="divide-y divide-gray-100 dark:divide-gray-700">
          {rows.map((row) => (
            <div key={row.name} className="grid grid-cols-[1fr_auto_auto] items-center gap-4 px-5 py-3 text-sm">
              <span className="truncate font-medium text-gray-900 dark:text-white">{row.name}</span>
              <span className="text-gray-500 dark:text-gray-400">{row.orders} 筆</span>
              <span className="min-w-24 text-right font-semibold" style={{ color: PRIMARY }}>NT$ {row.revenue.toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
