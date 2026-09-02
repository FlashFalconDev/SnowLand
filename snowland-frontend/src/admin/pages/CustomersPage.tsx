/**
 * 會員管理（接 API）
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Eye, Mail, Phone, X, Loader2, AlertCircle, Shield, Save } from 'lucide-react'
import { fetchCustomers, type Customer } from '../api/customers'
import { updateCustomerPermission } from '../api/extras'
import { useNotification } from '../context'

const PRIMARY = '#8b5cf6'

export default function CustomersPage() {
  const { data: customers = [], isLoading, error } = useQuery({
    queryKey: ['admin', 'customers'],
    queryFn: fetchCustomers,
  })

  const [search, setSearch] = useState('')
  const [viewingId, setViewingId] = useState<number | null>(null)

  const filtered = customers.filter((c) =>
    !search || c.name.includes(search) || c.email.includes(search) || c.phone.includes(search)
  )

  const viewing = viewingId ? customers.find((c) => c.id === viewingId) : null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">會員管理</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">管理所有會員資料、預約紀錄與滑雪程度</p>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜尋姓名 / Email / 電話..."
            className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} /></div>
        ) : error ? (
          <div className="p-8 text-center"><AlertCircle size={32} className="mx-auto mb-3 text-red-500" /><p className="text-sm text-red-600">載入失敗</p></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">會員</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden md:table-cell">聯絡資訊</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden lg:table-cell">年齡層</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">總預約</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden md:table-cell">總消費</th>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden xl:table-cell">最近上課</th>
                  <th className="px-5 py-3 text-right font-medium text-gray-600 dark:text-gray-300">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {filtered.map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full flex items-center justify-center text-white font-medium flex-shrink-0" style={{ backgroundColor: PRIMARY }}>
                          {(c.name || c.email).charAt(0).toUpperCase()}
                        </div>
                        <div className="font-medium text-gray-900 dark:text-white whitespace-nowrap">{c.name}</div>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-gray-600 dark:text-gray-300 hidden md:table-cell">
                      <div className="text-xs">{c.email}</div>
                      {c.phone && <div className="text-xs font-mono">{c.phone}</div>}
                    </td>
                    <td className="px-5 py-3 text-gray-600 dark:text-gray-300 hidden lg:table-cell whitespace-nowrap">{c.age_range || '—'}</td>
                    <td className="px-5 py-3 text-gray-900 dark:text-white whitespace-nowrap"><span className="font-medium">{c.total_reservations}</span> 次</td>
                    <td className="px-5 py-3 font-medium text-gray-900 dark:text-white hidden md:table-cell whitespace-nowrap">NT$ {c.total_spent.toLocaleString()}</td>
                    <td className="px-5 py-3 text-gray-600 dark:text-gray-300 hidden xl:table-cell whitespace-nowrap">{c.last_visit || '—'}</td>
                    <td className="px-5 py-3 text-right">
                      <button onClick={() => setViewingId(c.id)} className="p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"><Eye size={16} /></button>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={7} className="px-5 py-16 text-center text-sm text-gray-500 dark:text-gray-400">{customers.length === 0 ? '尚未有會員資料' : '沒有符合條件的會員'}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-600 dark:text-gray-400">共 <span className="font-medium">{filtered.length}</span> 位會員</div>
        </div>
      </div>

      {viewing && <CustomerDetailDrawer customer={viewing} onClose={() => setViewingId(null)} />}
    </div>
  )
}

function CustomerDetailDrawer({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const notify = useNotification()
  const qc = useQueryClient()
  const [isManager, setIsManager] = useState(!!customer.is_manager)
  const [isCoach, setIsCoach] = useState(!!customer.is_coach)
  const dirty = isManager !== !!customer.is_manager || isCoach !== !!customer.is_coach

  const permMutation = useMutation({
    mutationFn: () => updateCustomerPermission(customer.id, { is_manager: isManager, is_coach: isCoach }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['admin', 'customers'] })
      if (res.code === 200) {
        notify.success('權限已更新')
      } else {
        notify.error(res.msg)
      }
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '更新失敗'),
  })

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 animate-fadeIn" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-white dark:bg-gray-800 shadow-2xl flex flex-col animate-slideIn">
        <div className="px-6 py-4 flex items-center justify-between text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
          <h2 className="text-lg font-semibold">{customer.name}</h2>
          <button onClick={onClose} className="text-white/80 hover:text-white"><X size={20} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400">總預約次數</div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{customer.total_reservations}</div>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400">總消費金額</div>
              <div className="text-2xl font-bold mt-1" style={{ color: PRIMARY }}>NT$ {customer.total_spent.toLocaleString()}</div>
            </div>
          </div>

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">聯絡資料</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"><Mail size={16} className="text-gray-400" /><span className="text-gray-900 dark:text-white">{customer.email}</span></div>
              {customer.phone && <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"><Phone size={16} className="text-gray-400" /><span className="text-gray-900 dark:text-white font-mono">{customer.phone}</span></div>}
              {customer.age_range && <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"><span className="text-xs text-gray-500 w-20">年齡層</span><span className="text-gray-900 dark:text-white">{customer.age_range}</span></div>}
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">滑雪程度</h3>
            {customer.snowboard_skills.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs text-gray-500 dark:text-gray-400 mb-2">單板技能</h4>
                <div className="flex flex-wrap gap-1">
                  {customer.snowboard_skills.map((s) => <span key={s} className="px-2.5 py-1 bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 rounded-full text-xs font-medium">{s}</span>)}
                </div>
              </div>
            )}
            {customer.ski_skills.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs text-gray-500 dark:text-gray-400 mb-2">雙板技能</h4>
                <div className="flex flex-wrap gap-1">
                  {customer.ski_skills.map((s) => <span key={s} className="px-2.5 py-1 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded-full text-xs font-medium">{s}</span>)}
                </div>
              </div>
            )}
            {customer.snowboard_skills.length === 0 && customer.ski_skills.length === 0 && (
              <p className="text-sm text-gray-500 dark:text-gray-400">尚未填寫滑雪程度</p>
            )}
          </section>

          {customer.last_visit && (
            <div className="text-xs text-gray-500 text-center pt-4 border-t border-gray-200 dark:border-gray-700">最近上課：{customer.last_visit}</div>
          )}

          {/* 後台權限 */}
          <section>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <Shield size={14} style={{ color: PRIMARY }} />後台權限
            </h3>
            <div className="space-y-2">
              <label className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  checked={isManager}
                  onChange={(e) => setIsManager(e.target.checked)}
                  className="w-4 h-4 rounded"
                  style={{ accentColor: PRIMARY }}
                />
                <div>
                  <div className="text-sm font-medium text-gray-900 dark:text-white">管理員</div>
                  <div className="text-xs text-gray-500">可進入後台管理所有資料</div>
                </div>
              </label>
              <label className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  checked={isCoach}
                  onChange={(e) => setIsCoach(e.target.checked)}
                  className="w-4 h-4 rounded"
                  style={{ accentColor: PRIMARY }}
                />
                <div>
                  <div className="text-sm font-medium text-gray-900 dark:text-white">教練</div>
                  <div className="text-xs text-gray-500">可看自己的課程與請假申請</div>
                </div>
              </label>
            </div>
            {dirty && (
              <button
                onClick={() => permMutation.mutate()}
                disabled={permMutation.isPending}
                className="mt-3 w-full px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2"
                style={{ backgroundColor: PRIMARY }}
              >
                {permMutation.isPending && <Loader2 size={14} className="animate-spin" />}
                <Save size={14} />儲存權限變更
              </button>
            )}
          </section>
        </div>
      </div>
    </>
  )
}
