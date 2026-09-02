import Modal from '@/components/ui/Modal'
import { AlertCircle } from 'lucide-react'

interface Under6SuggestModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  onBack: () => void
}

export default function Under6SuggestModal({
  isOpen,
  onClose,
  onConfirm,
  onBack,
}: Under6SuggestModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="建議選擇 1 對 1 課程">
      <div className="space-y-6">
        <div className="flex flex-col items-center gap-4 rounded-xl bg-yellow-50 p-6 text-center">
          <AlertCircle size={48} className="text-yellow-600" />
          <p className="text-lg font-semibold text-yellow-800">
            為了確保6歲以下學員的安全和學習效果
          </p>
          <p className="text-sm text-yellow-700">
            我們建議您選擇 <strong>1 對 1</strong> 的教學方式
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <button
            onClick={onBack}
            className="rounded-lg border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 transition-all hover:border-gray-400 hover:bg-gray-50"
          >
            返回
          </button>
          <button
            onClick={onConfirm}
            className="rounded-lg bg-primary-500 px-6 py-3 font-semibold text-white transition-all hover:bg-primary-600 hover:shadow-lg"
          >
            確認選擇 1 對 1
          </button>
        </div>
      </div>
    </Modal>
  )
}
