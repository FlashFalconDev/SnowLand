import Modal from '@/components/ui/Modal'

interface Under6QuestionModalProps {
  isOpen: boolean
  onClose: () => void
  onCanSelfSki: () => void
  onCannotSelfSki: () => void
  onBack: () => void
}

export default function Under6QuestionModal({
  isOpen,
  onClose,
  onCanSelfSki,
  onCannotSelfSki,
  onBack,
}: Under6QuestionModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="6歲以下學員是否可以自主滑行？">
      <button
        onClick={onBack}
        className="mb-4 rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200"
      >
        ← 返回
      </button>

      <div className="grid gap-4 sm:grid-cols-2">
        <button
          onClick={onCanSelfSki}
          className="rounded-xl bg-gradient-to-br from-green-500 to-emerald-500 p-6 text-center font-bold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl"
        >
          可以
        </button>

        <button
          onClick={onCannotSelfSki}
          className="rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 p-6 text-center font-bold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl"
        >
          不行
        </button>
      </div>
    </Modal>
  )
}
