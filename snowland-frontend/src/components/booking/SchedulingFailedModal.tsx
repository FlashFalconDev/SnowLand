import { X, AlertCircle, Calendar, Sparkles } from 'lucide-react'
import { useSiteLocale } from '../../contexts/SiteLocale'

interface SchedulingFailedModalProps {
  isOpen: boolean
  onClose: () => void
  onTrySuperSchedule?: () => void
  onWaitForStaff?: () => void   // 等待課服處理（新）
  onChangeDate?: () => void     // 改其他日期（回 Step 2）（新）
  onSelectSuggestion?: (date: string, period: string) => void
  isSuggestionBookable?: (date: string) => boolean
  message: string
  conflictDetails?: {
    identifier?: string
    reason?: string
    suggestions?: {
      [date: string]: {
        [period: string]: {
          available_sessions: number
        }
      }
    }
  }
}

export default function SchedulingFailedModal({
  isOpen,
  onClose,
  onTrySuperSchedule,
  onWaitForStaff,
  onChangeDate,
  onSelectSuggestion,
  isSuggestionBookable,
  message,
  conflictDetails,
}: SchedulingFailedModalProps) {
  const { t } = useSiteLocale()
  if (!isOpen) return null

  const suggestions = Object.entries(conflictDetails?.suggestions || {})
    .filter(([date]) => !isSuggestionBookable || isSuggestionBookable(date))
  const hasSuggestions = suggestions.length > 0 && Boolean(onSelectSuggestion)

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 p-4">
      <div role="dialog" aria-modal="true" aria-label={t('排課失敗')} className="relative flex max-h-[calc(100dvh-2rem)] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl animate-in fade-in zoom-in duration-300">
        {/* Header */}
        <div className="shrink-0 border-b border-gray-200 bg-gradient-to-r from-red-50 to-orange-50 px-6 py-4 rounded-t-2xl">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <AlertCircle className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-800">
                  {t('排課失敗')}
                </h2>
                <p className="text-sm text-gray-600">
                  {t('無法為您安排教練')}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t('關閉並保留訂單，等待課服處理')}
              title={t('保留訂單，等待課服處理')}
              className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-full p-2 text-gray-400 transition-colors hover:bg-white hover:text-gray-600"
            >
              <X size={24} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {/* 失敗信息 */}
          <div className="mb-6 rounded-lg bg-red-50 p-4 border border-red-100">
            <p className="text-sm text-red-800 leading-relaxed">
              {t(message)}
            </p>
          </div>

          {/* 失敗課程 */}
          {conflictDetails?.identifier && (
            <div className="mb-6">
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-700">
                <Calendar size={16} />
                {t('失敗課程')}
              </h3>
              <div className="rounded-lg bg-gray-50 p-3 border border-gray-200">
                <p className="text-sm text-gray-800">
                  {conflictDetails.identifier}
                </p>
              </div>
            </div>
          )}

          {/* 具體原因 */}
          {conflictDetails?.reason && (
            <div className="mb-6">
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-700">
                <AlertCircle size={16} />
                {t('原因')}
              </h3>
              <div className="rounded-lg bg-yellow-50 p-3 border border-yellow-200">
                <p className="text-sm text-yellow-900">
                  {t(conflictDetails.reason)}
                </p>
              </div>
            </div>
          )}

          {/* 建議時段 */}
          {hasSuggestions ? (
            <div className="mb-6">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700">
                <Calendar size={16} />
                {t('建議調整到以下時段')}
              </h3>
              <div className="space-y-3">
                {suggestions.map(([date, periods]) => (
                  <div key={date} className="rounded-lg border border-gray-200 bg-white p-4">
                    <div className="mb-2 font-semibold text-gray-800">
                      {date}
                    </div>
                    <div className="grid gap-2 sm:grid-cols-3">
                      {Object.entries(periods).map(([period]) => (
                        <button
                          key={period}
                          type="button"
                          onClick={() => onSelectSuggestion?.(date, period)}
                          className="min-h-11 rounded-lg bg-green-50 px-3 py-2 text-center border border-green-200 transition-colors hover:border-green-500 hover:bg-green-100 focus:outline-none focus:ring-2 focus:ring-green-400"
                        >
                          <span className="text-sm font-medium text-green-800">
                            {period}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="mb-6 rounded-lg bg-orange-50 p-4 border border-orange-200">
              <p className="text-sm text-orange-800">
                {t('目前沒有可用時段建議。請嘗試選擇其他日期，或聯繫客服進行人工安排。')}
              </p>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-gray-200 bg-gray-50 px-6 py-4 rounded-b-2xl">
          <div className="grid gap-2 sm:grid-cols-3">
            {onWaitForStaff && (
              <button
                onClick={onWaitForStaff}
                className="rounded-lg bg-[#2b5f8f] px-4 py-3 text-center font-semibold text-white hover:opacity-90 transition-opacity"
              >
                {t('等待課服處理')}
              </button>
            )}
            {onChangeDate && (
              <button
                onClick={onChangeDate}
                className="rounded-lg border-2 border-[#2b5f8f] bg-white px-4 py-3 text-center font-semibold text-[#2b5f8f] hover:bg-[#2b5f8f]/5 transition-colors"
              >
                {t('改選其他日期')}
              </button>
            )}
            {onTrySuperSchedule && <button
              onClick={onTrySuperSchedule}
              className="rounded-lg bg-gradient-to-r from-purple-500 to-blue-500 px-4 py-3 text-center font-semibold text-white shadow hover:opacity-90 transition-opacity"
            >
              <span className="flex items-center justify-center gap-2">
                <Sparkles size={16} />
                {t('進階排課')}
              </span>
            </button>}
          </div>
          <p className="mt-3 text-center text-xs text-gray-500">
            {t(onChangeDate ? '訂單已建立但需要進一步處理 — 課服會主動聯繫您，或您可改選其他日期/嘗試進階排課' : '訂單已保留，課服會聯絡您協助處理。')}
          </p>
        </div>
      </div>
    </div>
  )
}
