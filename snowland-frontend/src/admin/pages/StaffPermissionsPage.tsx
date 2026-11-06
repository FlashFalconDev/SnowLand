/**
 * 員工權限管理
 * 集中管理誰是 manager / coach
 */
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Shield, UserCog, Loader2, AlertCircle, Crown, Star, AlertTriangle, UserPlus, Users } from 'lucide-react'
import {
  fetchStaff, updateCustomerPermission, type StaffMember, fetchStaffPositions,
  saveStaffPosition, deleteStaffPosition, type StaffPosition, type StaffPositionInput,
} from '../api/extras'
import { useNotification } from '../context'
import { hasAdminPermission } from '../permissions'
import { consoleNavigation } from '../consoleNavigation'
import { fetchCampuses } from '../api/campuses'
import { fetchAdminMe } from '../api/auth'
import { useAdminDialog } from '../hooks/useAdminDialog'

const PRIMARY = '#8b5cf6'
const STAFF_ROLE_OPTIONS = [
  ['hq_admin', '總部管理員'],
  ['campus_principal', '校區校長'],
  ['campus_manager', '校區主管'],
  ['assistant', '行政小幫手'],
  ['insurance', '保險人員'],
  ['marketing', '行銷人員'],
  ['web_editor', '網頁人員'],
  ['photographer', '攝影人員'],
  ['', '一般後台人員'],
] as const

export default function StaffPermissionsPage() {
  const [searchParams] = useSearchParams()
  const initialSearch = searchParams.get('q')?.trim() || ''
  const [search, setSearch] = useState(initialSearch)
  const [searchMode, setSearchMode] = useState(!!initialSearch)
  const [editingStaff, setEditingStaff] = useState<StaffMember | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [positionsOpen, setPositionsOpen] = useState(false)

  const { data: staff = [], isLoading, error } = useQuery({
    queryKey: ['admin', 'staff', searchMode ? search : ''],
    queryFn: () => fetchStaff(searchMode ? search : undefined),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3 sm:items-center">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">員工權限</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">設定員工的工作職務、可見分頁和校區</p>
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-2">
        <button type="button" onClick={() => setPositionsOpen(true)} className="min-h-10 rounded-lg border border-violet-300 px-3 text-sm font-medium text-violet-700 dark:border-violet-700 dark:text-violet-300">職位設定</button>
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="inline-flex flex-shrink-0 items-center justify-center gap-2 whitespace-nowrap px-3 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 sm:px-4"
          style={{ backgroundColor: PRIMARY }}
        >
          <UserPlus size={16} />
          新增授權
        </button>
        </div>
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
              placeholder="搜尋現有員工；新員工請輸入完整 Email"
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
            <p className="text-xs text-gray-400 mt-2">新員工請輸入完整 Email 搜尋，再設定後台或教練權限。</p>
          )}
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="divide-y divide-gray-100 dark:divide-gray-700 lg:hidden">
            {staff.map((s) => (
              <div key={s.id} className="p-4">
                <div className="flex min-w-0 items-start gap-3">
                  <div
                    className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-medium flex-shrink-0"
                    style={{ backgroundColor: PRIMARY }}
                  >
                    {(s.name || s.username || '?').charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-gray-900 dark:text-white">{s.name}</div>
                    <div className="text-xs text-gray-500 break-all">@{s.username}</div>
                    <div className="mt-2 flex flex-wrap gap-1"><RoleBadges staff={s} /></div>
                    {s.is_coach && !s.has_coach_record && (
                      <div className="mt-1 flex items-center gap-1 text-xs text-orange-600">
                        <AlertTriangle size={10} />未綁定 Coach 紀錄
                      </div>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setEditingStaff(s)}
                  className="mt-3 min-h-10 w-full rounded-lg border border-violet-300 px-3 py-2 text-sm font-medium text-violet-700 hover:bg-violet-50 dark:border-violet-700 dark:text-violet-300 dark:hover:bg-violet-900/20"
                >
                  指派職位
                </button>
              </div>
            ))}
          </div>
          <table className="hidden w-full text-sm lg:table">
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
                      指派職位
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
      {positionsOpen && <StaffPositionManager onClose={() => setPositionsOpen(false)} />}
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
      {(staff.position_names?.length ? staff.position_names : !staff.is_superuser && staff.is_manager
        ? [STAFF_ROLE_OPTIONS.find(([value]) => value === staff.role)?.[1] || '後台人員'] : []).map(name => (
        <span key={name} className="inline-flex max-w-full items-center gap-1 break-all rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
          <Shield size={10} className="shrink-0" />{name}
        </span>
      ))}
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
    queryFn: () => fetchStaff(submittedQuery, true),
    enabled,
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-fadeIn">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-2xl max-h-[86vh] overflow-hidden flex flex-col">
        <div className="px-4 py-4 border-b border-gray-200 dark:border-gray-700 flex items-start justify-between gap-2 sm:px-6">
          <div className="min-w-0">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">選擇會員新增授權</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">本校員工可用姓名搜尋；新增人員請輸入完整 Email。授權只適用於本校。</p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 whitespace-nowrap px-2 py-1.5 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-700 rounded-lg sm:px-3"
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
                placeholder="姓名或完整 Email"
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
  const { data: adminMe } = useQuery({ queryKey: ['admin', 'me'], queryFn: fetchAdminMe })
  const positions = useQuery({ queryKey: ['admin', 'staff-positions'], queryFn: fetchStaffPositions })
  const [selected, setSelected] = useState(staff.position_ids ?? [])
  const [platformMode, setPlatformMode] = useState(false)
  const [platformAdmin, setPlatformAdmin] = useState(staff.is_superuser)
  const [error, setError] = useState('')
  const canManagePlatform = adminMe?.user?.is_superuser === true
  const mutation = useMutation({
    mutationFn: () => updateCustomerPermission(staff.id, platformMode ? { is_superuser: platformAdmin } : { position_ids: selected }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin', 'staff'] })
      void qc.invalidateQueries({ queryKey: ['admin', 'customers'] })
      void qc.invalidateQueries({ queryKey: ['admin', 'me'] })
      window.dispatchEvent(new Event('snowland:campuses-updated'))
      notify.success(platformMode ? '最大管理員已更新' : '員工職位已更新')
      onClose()
    },
    onError: err => setError(positionError(err)),
  })
  const title = platformMode ? '最大管理員設定' : '指派職位'

  return <PositionDialog title={title} subtitle={staff.name} onClose={onClose} busy={mutation.isPending}>
    <div className="min-h-0 space-y-4 overflow-y-auto p-5">
      {platformMode ? <>
        <label className="flex items-center gap-3 rounded-lg border border-orange-300 p-4 text-sm">
          <input type="checkbox" checked={platformAdmin} onChange={event => setPlatformAdmin(event.target.checked)} />
          <Crown size={16} />最大管理員
        </label>
        <p className="text-sm text-gray-500 dark:text-gray-400">最大管理員可管理所有租戶，並可在 FlashFalcon 發布前端。</p>
      </> : <>
        <p className="text-sm text-gray-500 dark:text-gray-400">可勾選多個職位。員工的側欄分頁與校區由職位設定決定。</p>
        {staff.is_manager && !staff.position_ids?.some(id => id !== 0) && <p className="text-sm text-amber-700 dark:text-amber-400">此員工仍使用舊授權。儲存後會改用這次所選的職位。</p>}
        {positions.isPending && <p role="status" className="text-sm">正在載入職位…</p>}
        {positions.isError && <p role="alert" className="text-sm text-red-600">職位載入失敗。<button type="button" onClick={() => void positions.refetch()} className="underline">重新載入</button></p>}
        {positions.data?.map(position => <label key={position.id} className="flex min-h-11 items-center gap-3 rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-600">
          <input type="checkbox" checked={selected.includes(position.id)} onChange={event => {
            setError('')
            setSelected(ids => event.target.checked ? [...ids, position.id] : ids.filter(id => id !== position.id))
          }} />
          <span>{position.name}</span>
          {position.built_in && !staff.has_coach_record && selected.includes(position.id) && <span className="text-xs text-amber-700 dark:text-amber-400">需先在教練名冊綁定帳號</span>}
        </label>)}
        {canManagePlatform && <button type="button" onClick={() => { setError(''); setPlatformMode(true) }} className="text-sm font-medium text-violet-700 underline dark:text-violet-300">最大管理員設定</button>}
      </>}
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    </div>
    <DialogActions onCancel={platformMode ? () => { setError(''); setPlatformMode(false) } : onClose}
      onSave={() => mutation.mutate()} disabled={mutation.isPending || !adminMe?.user || (!platformMode && (!positions.data || (staff.is_superuser && !canManagePlatform)))} />
  </PositionDialog>
}

const EMPTY_POSITION: StaffPositionInput = { name: '', role: '', permissions: [], all_campuses: false, campus_ids: [] }

function StaffPositionManager({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const notify = useNotification()
  const positions = useQuery({ queryKey: ['admin', 'staff-positions'], queryFn: fetchStaffPositions })
  const campuses = useQuery({ queryKey: ['admin', 'campuses'], queryFn: fetchCampuses })
  const { data: adminMe } = useQuery({ queryKey: ['admin', 'me'], queryFn: fetchAdminMe })
  const [editing, setEditing] = useState<number | null | undefined>(undefined)
  const [draft, setDraft] = useState<StaffPositionInput>(EMPTY_POSITION)
  const [error, setError] = useState('')
  const [deleting, setDeleting] = useState<StaffPosition | null>(null)
  const definitions = adminMe?.user?.permission_definitions ?? []
  const candidate = {
    id: 0, username: '', name: '', email: '', is_manager: true,
    role: draft.role, can_view_all_campuses: draft.all_campuses,
    permissions: definitions.map(definition => definition.key),
  }
  const choices = new Set(candidate.permissions.filter(key => hasAdminPermission(candidate, key) && (
    !['site_tracking', 'checkout_policies'].includes(key) || (draft.role === 'hq_admin' && draft.all_campuses)
  )))
  const groups = consoleNavigation.map(group => ({
    label: group.label, pages: group.pages.filter(page => choices.has(page.access)),
  })).filter(group => group.pages.length)
  const activeCampuses = (campuses.data ?? []).filter(campus => campus.is_active)
  const scopedIds = draft.campus_ids.filter(id => activeCampuses.some(campus => campus.id === id))
  const mutation = useMutation({
    mutationFn: () => deleting ? deleteStaffPosition(deleting.id) : saveStaffPosition(editing ?? null, {
      ...draft, permissions: draft.permissions.filter(key => choices.has(key)), campus_ids: draft.all_campuses ? [] : scopedIds,
    }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin', 'staff-positions'] })
      void qc.invalidateQueries({ queryKey: ['admin', 'staff'] })
      void qc.invalidateQueries({ queryKey: ['admin', 'me'] })
      window.dispatchEvent(new Event('snowland:campuses-updated'))
      notify.success(deleting ? '職位已移除' : '職位已儲存')
      setEditing(undefined)
      setDeleting(null)
      setError('')
    },
    onError: err => setError(positionError(err)),
  })
  function edit(position?: StaffPosition) {
    setError('')
    setEditing(position?.id ?? null)
    setDraft(position?.settings ?? EMPTY_POSITION)
  }
  const title = deleting ? '移除職位' : editing === undefined ? '職位設定' : editing === null ? '新增職位' : '編輯職位'
  return <PositionDialog title={title} onClose={onClose} busy={mutation.isPending}>
    <div className="min-h-0 space-y-4 overflow-y-auto p-5">
      {deleting ? <p className="text-sm">移除「{deleting.name}」？仍有員工使用時，需先改派職位。</p> : editing === undefined ? <>
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm text-gray-500 dark:text-gray-400">先設定各職位可用的側欄分頁和校區，再指派給員工。</p>
          <button type="button" onClick={() => edit()} className="shrink-0 rounded-lg bg-violet-600 px-3 py-2 text-sm text-white">新增職位</button>
        </div>
        {positions.isPending && <p role="status">正在載入職位…</p>}
        {positions.isError && <p role="alert">職位載入失敗。<button type="button" onClick={() => void positions.refetch()} className="underline">重新載入</button></p>}
        <ul className="space-y-2">
          {positions.data?.map(position => <li key={position.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-700">
            <div>
              <span className="font-medium">{position.name}</span>
              {position.built_in && <p className="text-xs text-gray-500 dark:text-gray-400">教練的課程、月曆、評量、請假與薪資。</p>}
            </div>
            {!position.built_in && <div className="flex gap-3">
              <button type="button" onClick={() => edit(position)} aria-label={`編輯 ${position.name}`} className="min-h-10 px-2 text-violet-700 dark:text-violet-300">編輯</button>
              <button type="button" onClick={() => { setError(''); setDeleting(position) }} aria-label={`移除 ${position.name}`} className="min-h-10 px-2 text-red-600 dark:text-red-400">移除</button>
            </div>}
          </li>)}
        </ul>
      </> : <>
        <label className="block space-y-1 text-sm">職位名稱<input maxLength={100} value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })} className={positionInputClass} /></label>
        <label className="block space-y-1 text-sm">職務類型
          <select value={draft.role} onChange={event => setDraft({ ...draft, role: event.target.value })} className={positionInputClass}>
            {STAFF_ROLE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            {draft.role === 'coach' && <option value="coach">教練兼任後台</option>}
          </select>
        </label>
        <fieldset className="space-y-2 text-sm">
          <legend className="font-semibold">可查看校區</legend>
          <label className="block"><input type="checkbox" checked={draft.all_campuses} onChange={event => setDraft({ ...draft, all_campuses: event.target.checked })} /> 全部校區</label>
          {!draft.all_campuses && activeCampuses.map(campus => <label key={campus.id} className="inline-flex min-h-9 items-center gap-2 pr-4">
            <input type="checkbox" checked={scopedIds.includes(campus.id)} onChange={event => setDraft({ ...draft, campus_ids: event.target.checked ? [...scopedIds, campus.id] : scopedIds.filter(id => id !== campus.id) })} />{campus.name}
          </label>)}
          {campuses.isError && <p role="alert" className="text-red-600">校區載入失敗。</p>}
        </fieldset>
        <div className="space-y-3">
          <p className="text-sm font-semibold">可使用的側欄分頁</p>
          {groups.map(group => <fieldset key={group.label} className="grid gap-1 rounded-lg border border-gray-200 px-3 pb-2 sm:grid-cols-2 dark:border-gray-700">
            <legend className="px-1 text-xs text-gray-500 dark:text-gray-400">{group.label}</legend>
            {group.pages.map(page => <label key={page.path} className="flex min-h-9 items-center gap-2 text-sm">
              <input type="checkbox" checked={draft.permissions.includes(page.access)} onChange={event => setDraft({ ...draft, permissions: event.target.checked ? [...draft.permissions, page.access] : draft.permissions.filter(key => key !== page.access) })} />
              {page.label}
            </label>)}
          </fieldset>)}
        </div>
      </>}
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    </div>
    {editing !== undefined || deleting
      ? <DialogActions label={deleting ? '移除' : '儲存'} onCancel={() => { setDeleting(null); setEditing(undefined); setError('') }}
          onSave={() => mutation.mutate()} disabled={mutation.isPending || (!deleting && (!definitions.length || !draft.name.trim() || (!draft.all_campuses && !scopedIds.length)))} />
      : <DialogActions label="關閉" onSave={onClose} />}
  </PositionDialog>
}

const positionInputClass = 'block min-h-11 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-600 dark:bg-gray-700'

function PositionDialog({ title, subtitle, onClose, busy, children }: { title: string; subtitle?: string; onClose: () => void; busy?: boolean; children: React.ReactNode }) {
  const panel = useAdminDialog(true, !!busy, onClose)
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
    <div ref={panel as React.Ref<HTMLDivElement>} tabIndex={-1} role="dialog" aria-modal="true" aria-busy={busy} aria-label={title} className="flex max-h-[90dvh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white text-gray-900 shadow-xl dark:bg-gray-800 dark:text-white">
      <div className="shrink-0 bg-violet-600 px-5 py-4 text-white">
        <h3 className="text-lg font-semibold">{title}</h3>
        {subtitle && <p className="break-all text-sm">{subtitle}</p>}
      </div>
      {children}
    </div>
  </div>
}

function DialogActions({ label = '儲存', onCancel, onSave, disabled }: { label?: string; onCancel?: () => void; onSave: () => void; disabled?: boolean }) {
  return <div className="flex shrink-0 justify-end gap-3 border-t border-gray-200 px-5 py-3 dark:border-gray-700">
    {onCancel && <button type="button" onClick={onCancel} className="min-h-11 rounded-lg border border-gray-300 px-4 text-sm dark:border-gray-600">取消</button>}
    <button type="button" onClick={onSave} disabled={disabled} className="min-h-11 rounded-lg bg-violet-600 px-4 text-sm font-medium text-white disabled:opacity-50">{label}</button>
  </div>
}

function positionError(error: unknown) {
  const response = (error as { response?: { data?: { msg?: string; detail?: string } } })?.response?.data
  return response?.msg || response?.detail || '無法儲存，請重新確認設定後再試。'
}
