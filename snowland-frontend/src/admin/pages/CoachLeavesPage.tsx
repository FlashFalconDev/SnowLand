/**
 * 教練請假審核（接 API）
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Check, X as XIcon, AlertCircle, Calendar, Loader2 } from 'lucide-react'
import { useNotification } from '../context'
import { fetchCoachLeaves, reviewLeave, type CoachLeave, type LeaveStatus } from '../api/leaves'

const PRIMARY = '#8b5cf6'
const QUERY_KEY = ['admin', 'coach-leaves']

const STATUS_LABEL: Record<LeaveStatus, { label: string; cls: string }> = {
  pending: { label: '待審核', cls: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' },
  approved: { label: '已批准', cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  rejected: { label: '已拒絕', cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  cancelled: { label: '已取消', cls: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300' },
}

export default function CoachLeavesPage() {
  const notify = useNotification()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<LeaveStatus | ''>('')
  const [reviewing, setReviewing] = useState<{ id: number; action: 'approved' | 'rejected' } | null>(null)
  const [reviewNote, setReviewNote] = useState('')

  const { data: leaves = [], isLoading, error } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchCoachLeaves,
  })

  const reviewMutation = useMutation({
    mutationFn: ({ id, status, note }: { id: number; status: 'approved' | 'rejected'; note?: string }) =>
      reviewLeave(id, status, note),
    onSuccess: (_, { status }) => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
      notify.success(status === 'approved' ? '已批准請假' : '已拒絕請假')
      setReviewing(null)
      setReviewNote('')
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '操作失敗'),
  })

  const filtered = leaves.filter((l) => {
    if (search && !l.coach_name.includes(search)) return false
    if (statusFilter && l.status !== statusFilter) return false
    return true
  })

  const pendingCount = leaves.filter((l) => l.status === 'pending').length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">教練請假</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">審核教練請假申請</p>
        </div>
        {pendingCount > 0 && (
          <div className="px-3 py-1.5 bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 rounded-full text-sm font-medium flex items-center gap-2">
            <AlertCircle size={14} />{pendingCount} 筆待審核
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜尋教練姓名..."
              className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30" />
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as LeaveStatus | '')}
            className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30">
            <option value="">全部狀態</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} /></div>
      ) : error ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center"><AlertCircle size={32} className="mx-auto mb-3 text-red-500" /><p className="text-sm text-red-600">載入失敗</p></div>
      ) : (
        <div className="space-y-3">
          {filtered.map((leave) => (
            <div key={leave.id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-700 overflow-hidden flex-shrink-0">
                  {leave.coach_img ? (
                    <img src={leave.coach_img} alt={leave.coach_name} className="w-full h-full object-cover" loading="lazy" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-white font-medium" style={{ backgroundColor: PRIMARY }}>{leave.coach_name.charAt(0)}</div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-gray-900 dark:text-white">{leave.coach_name}</h3>
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${STATUS_LABEL[leave.status].cls}`}>{STATUS_LABEL[leave.status].label}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300 mb-3">
                    <Calendar size={14} /><span>{leave.start_date} ~ {leave.end_date}</span>
                    <span className="text-gray-400">·</span><span>共 {leave.leave_days} 天</span>
                    {leave.affected_count > 0 && <><span className="text-gray-400">·</span><span className="text-orange-600 dark:text-orange-400 font-medium">影響 {leave.affected_count} 筆預約</span></>}
                  </div>
                  <div className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                    <span className="text-xs text-gray-500 dark:text-gray-400">原因：</span>{leave.reason}
                  </div>
                  {leave.processing_result && (
                    <div className="mt-2 text-sm text-gray-700 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg">
                      <span className="text-xs text-gray-500">處理結果：</span>{leave.processing_result}
                      {leave.reviewed_by_name && leave.reviewed_at && (
                        <div className="text-xs text-gray-500 mt-1">— {leave.reviewed_by_name}, {leave.reviewed_at}</div>
                      )}
                    </div>
                  )}
                </div>

                {leave.status === 'pending' && (
                  <div className="flex flex-col gap-2 flex-shrink-0">
                    <button onClick={() => setReviewing({ id: leave.id, action: 'approved' })}
                      className="px-3 py-1.5 bg-green-500 text-white text-sm font-medium rounded-lg hover:bg-green-600 flex items-center gap-1">
                      <Check size={14} />批准
                    </button>
                    <button onClick={() => setReviewing({ id: leave.id, action: 'rejected' })}
                      className="px-3 py-1.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 flex items-center gap-1">
                      <XIcon size={14} />拒絕
                    </button>
                  </div>
                )}
              </div>
              <div className="text-xs text-gray-400 mt-3 text-right">申請於 {leave.created_at}</div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-16 text-sm text-gray-500 dark:text-gray-400">{leaves.length === 0 ? '目前無請假申請' : '沒有符合條件的請假申請'}</div>
          )}
        </div>
      )}

      {reviewing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-fadeIn">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md">
            <div className="rounded-t-2xl px-6 py-4 text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
              <h3 className="text-lg font-semibold">{reviewing.action === 'approved' ? '批准請假' : '拒絕請假'}</h3>
            </div>
            <div className="p-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                處理備註 {reviewing.action === 'rejected' && <span className="text-red-500">*</span>}
              </label>
              <textarea value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} rows={4}
                placeholder={reviewing.action === 'approved' ? '可選填批准備註...' : '請輸入拒絕原因（會顯示給教練）'}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 resize-none" />
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
              <button onClick={() => { setReviewing(null); setReviewNote('') }} disabled={reviewMutation.isPending}
                className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50">取消</button>
              <button
                onClick={() => reviewMutation.mutate({ id: reviewing.id, status: reviewing.action, note: reviewNote })}
                disabled={(reviewing.action === 'rejected' && !reviewNote.trim()) || reviewMutation.isPending}
                className={`px-4 py-2 text-white text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 ${reviewing.action === 'approved' ? 'bg-green-500 hover:bg-green-600' : 'bg-red-500 hover:bg-red-600'}`}>
                {reviewMutation.isPending && <Loader2 size={14} className="animate-spin" />}
                確認{reviewing.action === 'approved' ? '批准' : '拒絕'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
