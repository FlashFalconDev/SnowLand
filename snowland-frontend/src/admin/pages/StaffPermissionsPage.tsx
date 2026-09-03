/**
 * 員工權限管理
 * 集中管理誰是 manager / coach
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Shield, UserCog, Loader2, AlertCircle, Save, Crown, Star, AlertTriangle, UserPlus, Users } from 'lucide-react'
import { fetchStaff, updateCustomerPermission, type StaffMember } from '../api/extras'
import { useNotification } from '../context'
import { ADMIN_PERMISSION_DEFINITIONS, groupPermissions } from '../permissions'
import { fetchCampuses } from '../api/campuses'

const PRIMARY = '#8b5cf6'

export default function StaffPermissionsPage() {
  const [search, setSearch] = useState('')
  const [searchMode, setSearchMode] = useState(false)
  const [editingStaff, setEditingStaff] = useState<StaffMember | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)

  const { data: staff = [], isLoading, error } = useQuery({
    queryKey: ['admin', 'staff', searchMode ? search : ''],
    queryFn: () => fetchStaff(searchMode ? search : undefined),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">員工權限</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">設定使用者為最大管理員、後台人員或教練</p>
        </div>
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90"
          style={{ backgroundColor: PRIMARY }}
        >
          <UserPlus size={16} />
          新增授權
        </button>
      </div>

      {/* 搜尋列 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜尋使用者（姓名 / Email / 帳號）..."
              className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
            />
          </div>
          <button
            onClick={() => setSearchMode(true)}
            disabled={!search.trim()}
            className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: PRIMARY }}
          >
            搜尋使用者
          </button>
          {searchMode && (
            <button
              onClick={() => { setSearchMode(false); setSearch('') }}
              className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50"
            >
              清除
            </button>
          )}
        </div>
        <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          {searchMode
            ? `搜尋結果：${staff.length} 位（含尚無權限的使用者）`
            : `現有員工：${staff.length} 位（顯示已被授權的使用者）`}
        </div>
      </div>

      {/* 列表 */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} /></div>
      ) : error ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
          <p className="text-sm text-red-600">載入失敗</p>
        </div>
      ) : staff.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-16 text-center">
          <UserCog size={48} className="mx-auto mb-3 text-gray-300" />
          <p className="text-sm text-gray-500">{searchMode ? '沒有符合的使用者' : '目前沒有員工'}</p>
          {!searchMode && (
            <p className="text-xs text-gray-400 mt-2">使用上方搜尋找出使用者，給他們開通後台人員 / 教練權限</p>
          )}
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">使用者</th>
                <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden md:table-cell">Email</th>
                <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">角色</th>
                <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300 hidden lg:table-cell">最近登入</th>
                <th className="px-5 py-3 text-right font-medium text-gray-600 dark:text-gray-300">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {staff.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-medium flex-shrink-0"
                        style={{ backgroundColor: PRIMARY }}
                      >
                        {(s.name || s.username || '?').charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div className="font-medium text-gray-900 dark:text-white">{s.name}</div>
                        <div className="text-xs text-gray-500">@{s.username}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-gray-600 dark:text-gray-300 hidden md:table-cell font-mono text-xs">{s.email}</td>
                  <td className="px-5 py-3">
                    <div className="flex flex-wrap gap-1">
                      <RoleBadges staff={s} />
                    </div>
                    {s.is_coach && !s.has_coach_record && (
                      <div className="text-xs text-orange-600 mt-1 flex items-center gap-1">
                        <AlertTriangle size={10} />未綁定 Coach 紀錄
                      </div>
                    )}
                  </td>
                  <td className="px-5 py-3 text-gray-500 dark:text-gray-400 text-xs hidden lg:table-cell">
                    {s.last_login || '從未登入'}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => setEditingStaff(s)}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
                      style={{ color: PRIMARY }}
                    >
                      編輯權限
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pickerOpen && (
        <MemberPickerModal
          onClose={() => setPickerOpen(false)}
          onSelect={(member) => {
            setPickerOpen(false)
            setEditingStaff(member)
          }}
        />
      )}
      {editingStaff && <EditPermissionModal staff={editingStaff} onClose={() => setEditingStaff(null)} />}
    </div>
  )
}

function RoleBadges({ staff }: { staff: StaffMember }) {
  const hasRole = staff.is_superuser || staff.is_manager || staff.is_coach

  return (
    <>
      {staff.is_member && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
          <Users size={10} />會員{staff.reservation_count ? ` ${staff.reservation_count} 筆預約` : ''}
        </span>
      )}
      {staff.is_superuser && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400">
          <Crown size={10} />最大管理員
        </span>
      )}
      {!staff.is_superuser && staff.is_manager && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
          <Shield size={10} />後台人員
        </span>
      )}
      {staff.is_coach && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
          <Star size={10} />教練{!staff.has_coach_record && ' ⚠️'}
        </span>
      )}
      {!hasRole && (
        <span className="text-xs text-gray-400">尚未授權</span>
      )}
    </>
  )
}

function MemberPickerModal({
  onClose,
  onSelect,
}: {
  onClose: () => void
  onSelect: (staff: StaffMember) => void
}) {
  const [query, setQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const enabled = submittedQuery.trim().length > 0
  const { data: members = [], isLoading, error } = useQuery({
    queryKey: ['admin', 'staff-picker', submittedQuery],
    queryFn: () => fetchStaff(submittedQuery),
    enabled,
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-fadeIn">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-2xl max-h-[86vh] overflow-hidden flex flex-col">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">選擇會員新增授權</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">搜尋會員姓名、Email 或帳號，選取後即可設定後台 / 教練權限。</p>
          </div>
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
          >
            關閉
          </button>
        </div>

        <div className="p-6 space-y-4 overflow-y-auto">
          <form
            className="flex flex-col sm:flex-row gap-3"
            onSubmit={(e) => {
              e.preventDefault()
              setSubmittedQuery(query.trim())
            }}
          >
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="輸入會員姓名 / Email / 帳號"
                className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                autoFocus
              />
            </div>
            <button
              type="submit"
              disabled={!query.trim()}
              className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ backgroundColor: PRIMARY }}
            >
              搜尋會員
            </button>
          </form>

          {!enabled ? (
            <div className="rounded-xl border border-dashed border-gray-200 dark:border-gray-700 p-10 text-center text-sm text-gray-500 dark:text-gray-400">
              先搜尋會員，再選擇要新增授權的帳號。
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center py-12"><Loader2 size={28} className="animate-spin" style={{ color: PRIMARY }} /></div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 dark:border-red-900/50 p-8 text-center">
              <AlertCircle size={28} className="mx-auto mb-2 text-red-500" />
              <p className="text-sm text-red-600">搜尋失敗</p>
            </div>
          ) : members.length === 0 ? (
            <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-10 text-center text-sm text-gray-500 dark:text-gray-400">
              找不到符合條件的會員
            </div>
          ) : (
            <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {members.map((member) => (
                  <button
                    key={member.id}
                    type="button"
                    onClick={() => onSelect(member)}
                    className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  >
                    <div
                      className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-medium flex-shrink-0"
                      style={{ backgroundColor: PRIMARY }}
                    >
                      {(member.name || member.username || '?').charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-gray-900 dark:text-white truncate">{member.name}</div>
                      <div className="text-xs text-gray-500 truncate">{member.email || `@${member.username}`}</div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        <RoleBadges staff={member} />
                      </div>
                    </div>
                    <span className="text-xs font-medium whitespace-nowrap" style={{ color: PRIMARY }}>
                      設定權限
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function EditPermissionModal({ staff, onClose }: { staff: StaffMember; onClose: () => void }) {
  const notify = useNotification()
  const qc = useQueryClient()
  const [isSuperuser, setIsSuperuser] = useState(staff.is_superuser)
  const [isManager, setIsManager] = useState(staff.is_superuser ? false : staff.is_manager)
  const [isCoach, setIsCoach] = useState(staff.is_coach)
  const [permissions, setPermissions] = useState<string[]>(staff.permissions || [])
  const [role, setRole] = useState(staff.role || '')
  const [campusIds, setCampusIds] = useState<number[]>(staff.campus_ids || [])
  const { data: campuses = [] } = useQuery({ queryKey: ['admin', 'campuses'], queryFn: fetchCampuses })
  const permissionGroups = groupPermissions()
  const togglePermission = (key: string) => {
    setPermissions((prev) => prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key])
  }
  const selectAllPermissions = () => setPermissions(ADMIN_PERMISSION_DEFINITIONS.map((item) => item.key))
  const clearPermissions = () => setPermissions([])

  const mutation = useMutation({
    mutationFn: () => updateCustomerPermission(staff.id, {
      is_superuser: isSuperuser,
      is_manager: isSuperuser ? false : isManager,
      is_coach: isCoach,
      permissions: !isSuperuser && isManager ? permissions : [],
      role: isSuperuser ? 'hq_admin' : role,
      campus_ids: isSuperuser ? [] : campusIds,
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['admin', 'staff'] })
      qc.invalidateQueries({ queryKey: ['admin', 'customers'] })
      if (res.code === 200) {
        notify.success('權限已更新')
        onClose()
      } else {
        notify.error(res.msg)
      }
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '更新失敗'),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-fadeIn">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="rounded-t-2xl px-6 py-4 text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
          <h3 className="text-lg font-semibold">編輯權限</h3>
          <p className="text-xs text-white/80 mt-0.5">{staff.name}（@{staff.username}）</p>
        </div>

        <div className="p-6 space-y-3 overflow-y-auto">
          {staff.is_superuser && (
            <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-900/50 rounded-lg p-3 text-xs text-orange-800 dark:text-orange-300 flex gap-2">
              <Crown size={14} className="flex-shrink-0 mt-0.5" />
              <div>此使用者是 <strong>Superuser</strong>，自動擁有所有權限（不受下方設定限制）</div>
            </div>
          )}

          <label className="flex items-start gap-3 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600">
            <input
              type="checkbox"
              checked={isSuperuser}
              onChange={(e) => {
                setIsSuperuser(e.target.checked)
                if (e.target.checked) setIsManager(false)
              }}
              className="mt-1 w-4 h-4 rounded"
              style={{ accentColor: PRIMARY }}
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Crown size={14} className="text-orange-600 dark:text-orange-400" />
                <span className="text-sm font-medium text-gray-900 dark:text-white">最大管理員</span>
              </div>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">擁有全部後台權限，不受下方功能勾選限制。</p>
            </div>
          </label>

          <label className="flex items-start gap-3 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600">
            <input
              type="checkbox"
              checked={isManager}
              onChange={(e) => {
                setIsManager(e.target.checked)
                if (e.target.checked) setIsSuperuser(false)
              }}
              className="mt-1 w-4 h-4 rounded"
              style={{ accentColor: PRIMARY }}
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Shield size={14} className="text-purple-600 dark:text-purple-400" />
                <span className="text-sm font-medium text-gray-900 dark:text-white">後台人員</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">可進入後台所有頁面、管理訂單、教練、雪場、課程設定等</p>
            </div>
          </label>

          {!isSuperuser && isManager && (
            <div className="space-y-4">
              <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
                <label className="mb-2 block text-sm font-semibold text-gray-900 dark:text-white">工作角色</label>
                <select value={role} onChange={e => setRole(e.target.value)} className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white">
                  <option value="">一般後台人員</option><option value="hq_admin">總部管理員</option><option value="marketing">行銷</option><option value="web_editor">網站編輯</option><option value="insurance">保險人員</option><option value="assistant">助理</option><option value="campus_principal">校區校長</option><option value="campus_manager">校區主管</option><option value="photographer">攝影人員</option>
                </select>
                <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">總部管理員可看全部校區；其他角色請勾選負責校區。</p>
                {role !== 'hq_admin' && <div className="mt-3 flex flex-wrap gap-2">{campuses.map(c => <label key={c.id} className={`cursor-pointer rounded-lg border px-3 py-2 text-sm transition-colors ${campusIds.includes(c.id) ? 'border-violet-400 bg-violet-50 text-violet-700 dark:border-violet-500 dark:bg-violet-900/30 dark:text-violet-300' : 'border-gray-200 bg-white text-gray-700 hover:border-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200'}`}><input type="checkbox" className="sr-only" checked={campusIds.includes(c.id)} onChange={() => setCampusIds(prev => prev.includes(c.id) ? prev.filter(id => id !== c.id) : [...prev, c.id])} />{c.name}</label>)}</div>}
              </div>
            <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 dark:bg-gray-700 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="text-sm font-semibold text-gray-900 dark:text-white">後台模組權限</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">勾選這個後台人員可以看到與操作的功能。</div>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={selectAllPermissions}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    全選
                  </button>
                  <button
                    type="button"
                    onClick={clearPermissions}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    清空
                  </button>
                </div>
              </div>
              <div className="p-4 space-y-4">
                {Object.entries(permissionGroups).map(([group, items]) => (
                  <div key={group}>
                    <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2">{group}</div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {items.map((item) => (
                        <label
                          key={item.key}
                          className="flex items-start gap-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3 cursor-pointer hover:border-purple-300 dark:hover:border-purple-600"
                        >
                          <input
                            type="checkbox"
                            checked={permissions.includes(item.key)}
                            onChange={() => togglePermission(item.key)}
                            className="mt-1 w-4 h-4 rounded"
                            style={{ accentColor: PRIMARY }}
                          />
                          <span className="min-w-0">
                            <span className="block text-sm font-medium text-gray-900 dark:text-white">{item.label}</span>
                            <span className="block text-xs text-gray-500 dark:text-gray-400 mt-0.5">{item.description}</span>
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            </div>
          )}

          <label className="flex items-start gap-3 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600">
            <input
              type="checkbox"
              checked={isCoach}
              onChange={(e) => setIsCoach(e.target.checked)}
              className="mt-1 w-4 h-4 rounded"
              style={{ accentColor: PRIMARY }}
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Star size={14} className="text-blue-600 dark:text-blue-400" />
                <span className="text-sm font-medium text-gray-900 dark:text-white">教練</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">可看自己被指派的課程、申請請假</p>
              {isCoach && !staff.has_coach_record && (
                <div className="mt-2 text-xs text-orange-600 dark:text-orange-400 flex items-center gap-1">
                  <AlertTriangle size={11} />
                  尚未綁定 Coach 紀錄。需要先到「教練管理」建立 Coach 並關聯此 user，否則登入後看不到任何資料。
                </div>
              )}
            </div>
          </label>
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
          <button onClick={onClose} disabled={mutation.isPending} className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50">取消</button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
            style={{ backgroundColor: PRIMARY }}
          >
            {mutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            儲存
          </button>
        </div>
      </div>
    </div>
  )
}
