import { ReactNode } from 'react'
import { X } from 'lucide-react'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  children: ReactNode
  showCloseButton?: boolean
  className?: string
}

export default function Modal({
  isOpen,
  onClose,
  title,
  children,
  showCloseButton = true,
  className = '',
}: ModalProps) {
  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className={`relative max-h-[90vh] w-full max-w-lg overflow-auto rounded-2xl bg-white p-6 shadow-2xl ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        {showCloseButton && (
          <button
            onClick={onClose}
            className="absolute right-4 top-4 rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            aria-label="關閉"
          >
            <X size={24} />
          </button>
        )}

        {title && (
          <h2 className="mb-6 pr-8 text-2xl font-bold text-gray-800">
            {title}
          </h2>
        )}

        <div className="text-gray-700">{children}</div>
      </div>
    </div>
  )
}
