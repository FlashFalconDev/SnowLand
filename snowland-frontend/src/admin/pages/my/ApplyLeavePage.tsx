/**
 * 教練申請請假
 */
import { useState, FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Calendar, Send, Loader2, AlertCircle } from 'lucide-react'
import { applyLeave } from '../../api/extras'
import { useNotification } from '../../context'

const PRIMARY = '#8b5cf6'

export default function ApplyLeavePage() {
  const navigate = useNavigate()
  const notify = useNotification()
  const qc = useQueryClient()

  const today = new Date().toISOString().split('T')[0]
  const [startDate, setStartDate] = useState(today)
  const [endDate, setEndDate] = useState(today)
  const [reason, setReason] = useState('')

  const mutation = useMutation({
    mutationFn: () => applyLeave({ start_date: startDate, end_date: endDate, reason }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['admin', 'my-leaves'] })
      if (res.code === 200) {
        notify.success(`請假申請已送出${res.data?.affected_count ? `（影響 ${res.data.affected_count} 筆預約）` : ''}`)
        // 跳到我的請假紀錄
        navigate('../leaves')
      } else {
        notify.error(res.msg)
      }
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '申請失敗'),
  })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!reason.trim()) {
      notify.warning('請填寫請假原因')
      return
    }
    if (startDate > endDate) {
      notify.warning('結束日期不能早於開始日期')
      return
    }
    mutation.mutate()
  }

  const days = Math.max(1, Math.round((new Date(endDate).getTime() - new Date(startDate).getTime()) / 86400000) + 1)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">申請請假</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">提交請假申請給管理員審核</p>
      </div>

      <div className="max-w-2xl">
        <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                開始日期 <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <Calendar size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  min={today}
                  required
                  className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                結束日期 <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <Calendar size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  min={startDate}
                  required
                  className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                />
              </div>
            </div>
          </div>

          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 text-sm">
            <span className="text-gray-500">請假天數：</span>
            <span className="font-semibold text-gray-900 dark:text-white">{days} 天</span>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              請假原因 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              rows={4}
              placeholder="請說明請假原因..."
              className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 resize-none"
            />
          </div>

          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-900/50 rounded-lg p-3 text-xs text-yellow-800 dark:text-yellow-300 flex gap-2">
            <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
            <div>
              <strong>注意：</strong>若這段期間已有指派給您的課程，將會在系統中標記為「受影響」，
              管理員審核通過後會通知學員調整時間或更換教練。
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => navigate('../leaves')}
              disabled={mutation.isPending}
              className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              style={{ backgroundColor: PRIMARY }}
            >
              {mutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              送出申請
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
