import { X, Sparkles, ArrowRight } from 'lucide-react'

interface SuperScheduleConfirmModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
}

export default function SuperScheduleConfirmModal({
  isOpen,
  onClose,
  onConfirm,
}: SuperScheduleConfirmModalProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/50 p-4">
      <div className="relative w-full max-w-lg rounded-2xl bg-white shadow-2xl animate-in fade-in zoom-in duration-300">
        {/* Header */}
        <div className="border-b border-gray-200 bg-gradient-to-r from-purple-50 to-blue-50 px-6 py-4 rounded-t-2xl">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-purple-100">
                <Sparkles className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-800">
                  是否使用「進階排課」？
                </h2>
                <p className="text-sm text-gray-600">
                  提高排課成功率
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="rounded-full p-2 text-gray-400 transition-colors hover:bg-white hover:text-gray-600"
            >
              <X size={24} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          <div className="mb-6 space-y-4">
            <div className="rounded-lg bg-purple-50 p-4 border border-purple-200">
              <h3 className="mb-3 flex items-center gap-2 font-semibold text-purple-900">
                <Sparkles size={18} />
                進階排課
              </h3>
              <p className="text-sm text-purple-800 leading-relaxed mb-3">
                進階排課會嘗試把課程拆成單日安排，以提高排課成功率。
              </p>
            </div>

            <div className="rounded-lg bg-amber-50 p-4 border border-amber-200">
              <p className="mb-2 text-sm font-semibold text-amber-900">注意事項：</p>
              <ul className="list-disc space-y-1 pl-5 text-xs leading-relaxed text-amber-900">
                <li>課程期間每日授課教練可能不同。</li>
                <li>所有教練皆依 SnowLand 教學標準進行授課，課程內容與學習進度將完整交接。</li>
                <li>若您希望由同一位教練全程授課，建議改選其他日期或時段，以利安排固定教練。</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 bg-gray-50 px-6 py-4 rounded-b-2xl">
          <div className="flex flex-col gap-3 sm:flex-row-reverse">
            <button
              onClick={onConfirm}
              className="flex-1 rounded-lg bg-gradient-to-r from-purple-500 to-blue-500 px-6 py-3 text-center font-semibold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl"
            >
              <span className="flex items-center justify-center gap-2">
                <Sparkles size={18} />
                確定使用進階排課
                <ArrowRight size={18} />
              </span>
            </button>
            <button
              onClick={onClose}
              className="flex-1 rounded-lg border-2 border-gray-300 bg-white px-6 py-3 text-center font-semibold text-gray-700 transition-all hover:bg-gray-50"
            >
              取消返回
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
