/**
 * 教練待確認課程頁
 * 顯示指派給「當前教練」但還沒接受的課程
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Calendar, Check, X, Loader2, AlertCircle, MapPin, User, BookOpen } from 'lucide-react'
import { fetchCoachPending, coachConfirm } from '../../api/extras'
import { useNotification } from '../../context'

const PRIMARY = '#8b5cf6'

export default function PendingConfirmationsPage() {
  const notify = useNotification()
  const qc = useQueryClient()

  const { data: items = [], isLoading, error } = useQuery({
    queryKey: ['admin', 'coach-pending'],
    queryFn: fetchCoachPending,
  })

  const confirmMutation = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'accept' | 'reject' }) => coachConfirm(id, action),
    onSuccess: (res, vars) => {
      qc.invalidateQueries({ queryKey: ['admin', 'coach-pending'] })
      if (res.code === 200) {
        notify.success(vars.action === 'accept' ? '已接受課程' : res.msg || '已拒絕')
      } else {
        notify.error(res.msg)
      }
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '操作失敗'),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">待確認課程</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">系統指派給您的課程，請確認接受或拒絕</p>
          <p className="mt-1 text-xs text-yellow-600 dark:text-yellow-400">顯示所有需要您確認的課程，請即時接受或拒絕</p>
        </div>
        {items.length > 0 && (
          <div className="px-3 py-1.5 bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 rounded-full text-sm font-medium flex items-center gap-2">
            <AlertCircle size={14} />{items.length} 筆待處理
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20"><Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} /></div>
      ) : error ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
          <p className="text-sm text-red-600">載入失敗</p>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-16 text-center">
          <Check size={48} className="mx-auto mb-3 text-green-500 opacity-60" />
          <p className="text-base font-medium text-gray-700 dark:text-gray-300">目前沒有待確認的課程</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">指派的新課程會出現在這裡</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <BookOpen size={16} style={{ color: PRIMARY }} />
                    <span className="font-semibold text-gray-900 dark:text-white">{item.course_type}</span>
                    <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
                      待確認
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-300">
                    <div className="flex items-center gap-1"><MapPin size={12} className="text-gray-400" />{item.resort}</div>
                    <div className="flex items-center gap-1"><User size={12} className="text-gray-400" />{item.user_name} · {item.number_of_people} 人</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-500 dark:text-gray-400">課程費用</div>
                  <div className="text-lg font-bold" style={{ color: PRIMARY }}>NT$ {(item.total_fee || 0).toLocaleString()}</div>
                </div>
              </div>

              {/* 課程時段 */}
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 mb-4">
                <div className="flex items-center gap-2 mb-2">
                  <Calendar size={14} style={{ color: PRIMARY }} />
                  <span className="text-xs font-medium text-gray-600 dark:text-gray-400">{item.bookings.length} 個時段</span>
                </div>
                <div className="space-y-1">
                  {item.bookings.map((b, i) => (
                    <div key={i} className="text-sm text-gray-700 dark:text-gray-300 flex items-center gap-3">
                      <span className="font-medium">{b.date}</span>
                      <span className="text-gray-500">{b.start_time?.substring(0, 5)} - {b.end_time?.substring(0, 5)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 其他資訊 */}
              <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 mb-4">
                <div>能力等級：{item.ability_level || '—'}</div>
                <div>教學語言：{item.language}</div>
              </div>

              {/* 動作按鈕 */}
              <div className="flex gap-3">
                <button
                  onClick={() => confirmMutation.mutate({ id: item.id, action: 'accept' })}
                  disabled={confirmMutation.isPending}
                  className="flex-1 px-4 py-2 bg-green-500 text-white text-sm font-medium rounded-lg hover:bg-green-600 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {confirmMutation.isPending && confirmMutation.variables?.id === item.id && <Loader2 size={14} className="animate-spin" />}
                  <Check size={16} />接受課程
                </button>
                <button
                  onClick={() => {
                    if (confirm('拒絕後系統會嘗試重新分派教練。確定要拒絕？')) {
                      confirmMutation.mutate({ id: item.id, action: 'reject' })
                    }
                  }}
                  disabled={confirmMutation.isPending}
                  className="flex-1 px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  <X size={16} />拒絕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
