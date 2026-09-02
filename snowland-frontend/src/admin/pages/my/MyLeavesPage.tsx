/**
 * 教練我的請假紀錄
 */
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Calendar, Plus, Loader2, AlertCircle, ClipboardCheck } from 'lucide-react'
import { fetchMyLeaves, type MyLeave } from '../../api/extras'

const PRIMARY = '#8b5cf6'

const STATUS_LABEL: Record<MyLeave['status'], { label: string; cls: string }> = {
  pending: { label: '審核中', cls: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' },
  approved: { label: '已批准', cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  rejected: { label: '已拒絕', cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  cancelled: { label: '已取消', cls: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300' },
}

export default function MyLeavesPage() {
  const navigate = useNavigate()
  const { data: leaves = [], isLoading, error } = useQuery({
    queryKey: ['admin', 'my-leaves'],
    queryFn: fetchMyLeaves,
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">我的請假紀錄</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">您所有提交的請假申請</p>
        </div>
        <button
          onClick={() => navigate('apply')}
          className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 flex items-center gap-2"
          style={{ backgroundColor: PRIMARY }}
        >
          <Plus size={16} />申請請假
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} /></div>
      ) : error ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
          <p className="text-sm text-red-600">載入失敗</p>
        </div>
      ) : leaves.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-16 text-center">
          <ClipboardCheck size={48} className="mx-auto mb-3 text-gray-300" />
          <p className="text-sm text-gray-500">還沒有任何請假申請</p>
          <button
            onClick={() => navigate('apply')}
            className="mt-4 px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 inline-flex items-center gap-2"
            style={{ backgroundColor: PRIMARY }}
          >
            <Plus size={14} />立即申請
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {leaves.map((leave) => {
            const s = STATUS_LABEL[leave.status]
            return (
              <div key={leave.id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <Calendar size={16} style={{ color: PRIMARY }} />
                    <div>
                      <div className="font-semibold text-gray-900 dark:text-white">
                        {leave.start_date} ~ {leave.end_date}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">共 {leave.leave_days} 天 · 申請於 {leave.created_at}</div>
                    </div>
                  </div>
                  <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${s.cls}`}>{s.label}</span>
                </div>

                <div className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                  <span className="text-xs text-gray-500">原因：</span>{leave.reason}
                </div>

                {leave.affected_count > 0 && (
                  <div className="mt-2 text-xs text-orange-600 dark:text-orange-400 flex items-center gap-1">
                    <AlertCircle size={12} />影響 {leave.affected_count} 筆預約
                  </div>
                )}

                {leave.processing_result && (
                  <div className="mt-3 text-sm text-gray-700 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg">
                    <div className="text-xs text-gray-500 mb-1">管理員回覆：</div>
                    {leave.processing_result}
                    {leave.reviewed_at && (
                      <div className="text-xs text-gray-500 mt-1">— {leave.reviewed_at}</div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
