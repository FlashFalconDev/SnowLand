/**
 * 教練申請請假
 */
import { useEffect, useState, FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Calendar, Send, Loader2, AlertCircle } from 'lucide-react'
import { applyLeave, fetchCoachLeaveRules } from '../../api/extras'
import { useNotification } from '../../context'

const PRIMARY = '#8b5cf6'

export default function ApplyLeavePage() {
  const navigate = useNavigate()
  const notify = useNotification()
  const qc = useQueryClient()

  const rules = useQuery({ queryKey: ['admin', 'coach-leave-rules'], queryFn: fetchCoachLeaveRules })
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [reason, setReason] = useState('')
  useEffect(() => {
    if (rules.data) {
      setStartDate(current => current || rules.data.minimum_start_date)
      setEndDate(current => current || rules.data.minimum_start_date)
    }
  }, [rules.data])

  const mutation = useMutation({
    mutationFn: () => applyLeave({ start_date: startDate, end_date: endDate, reason }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['admin', 'my-leaves'] })
      if (res.code === 200) {
        notify.success(`請假申請已送出${res.data?.affected_count ? `（影響 ${res.data.affected_count} 筆預約）` : ''}`)
        // 跳到我的請假紀錄
        navigate('..', { relative: 'path' })
      } else {
        notify.error(res.msg)
      }
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '申請失敗'),
  })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!rules.data || rules.isError || mutation.isPending) return
    if (!reason.trim()) {
      notify.warning('請填寫請假原因')
      return
    }
    if (startDate > endDate) {
      notify.warning('結束日期不能早於開始日期')
      return
    }
    if (startDate < rules.data.minimum_start_date) {
      notify.warning(`最早可申請 ${rules.data.minimum_start_date}；緊急狀況請聯絡主管`)
      return
    }
    if (days > rules.data.leave_max_consecutive_days) {
      notify.warning(`一般申請最多連續 ${rules.data.leave_max_consecutive_days} 天；較長假期請聯絡主管`)
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
          {rules.isPending && <p role="status" className="text-sm text-gray-500 dark:text-gray-400">正在讀取請假規則…</p>}
          {rules.isError && <div role="alert" className="text-sm text-red-600 dark:text-red-300">請假規則載入失敗，請重試。<button type="button" className="min-h-11 underline" onClick={() => rules.refetch()}>重新載入請假規則</button></div>}
          {rules.data && !rules.isError && <p className="rounded-lg bg-gray-50 p-3 text-sm leading-6 text-gray-600 dark:bg-gray-700 dark:text-gray-200">依學校日期 {rules.data.today}：最早可申請 {rules.data.minimum_start_date}。至少提前 {rules.data.leave_advance_days} 天、最多連續 {rules.data.leave_max_consecutive_days} 天、每日最多 {rules.data.leave_daily_coach_limit} 位教練請假。緊急狀況請聯絡主管。</p>}
          <fieldset disabled={mutation.isPending || rules.isPending || rules.isError} className="space-y-5 disabled:opacity-60">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="coach-leave-start" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                開始日期 <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <Calendar size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="date"
                  id="coach-leave-start"
                  value={startDate}
                  onChange={(e) => { setStartDate(e.target.value); if (e.target.value > endDate) setEndDate(e.target.value) }}
                  min={rules.data?.minimum_start_date}
                  required
                  className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                />
              </div>
            </div>
            <div>
              <label htmlFor="coach-leave-end" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                結束日期 <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <Calendar size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="date"
                  id="coach-leave-end"
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
            <label htmlFor="coach-leave-reason" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              請假原因 <span className="text-red-500">*</span>
            </label>
            <textarea
              id="coach-leave-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              rows={4}
              maxLength={1000}
              placeholder="請說明請假原因..."
              className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 resize-none"
            />
          </div>

          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-900/50 rounded-lg p-3 text-xs text-yellow-800 dark:text-yellow-300 flex gap-2">
            <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
            <div>
              <strong>注意：</strong>若這段期間已有指派給您的課程，將會在系統中標記為「受影響」，
              管理員需另外安排調整時間或更換教練，並確認已通知受影響學員；核准請假不會自動改動既有訂單。
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => navigate('..', { relative: 'path' })}
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
          </fieldset>
        </form>
      </div>
    </div>
  )
}
