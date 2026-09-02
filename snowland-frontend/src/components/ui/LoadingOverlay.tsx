import { Loader2 } from 'lucide-react'

interface LoadingOverlayProps {
  isLoading: boolean
  message?: string
  detail?: string
  steps?: string[]
  activeStep?: number
}

export default function LoadingOverlay({
  isLoading,
  message = '處理中...',
  detail,
  steps = [],
  activeStep = 0,
}: LoadingOverlayProps) {
  if (!isLoading) return null

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-[min(92vw,460px)] rounded-2xl bg-white p-7 shadow-2xl animate-in fade-in zoom-in duration-300">
        <div className="flex flex-col items-center gap-4 text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary-500" />
          <div>
            <p className="text-lg font-semibold text-gray-800">{message}</p>
            {detail && (
              <p className="mt-2 text-sm leading-6 text-gray-500">{detail}</p>
            )}
          </div>

          {steps.length > 0 && (
            <div className="mt-1 w-full space-y-2 rounded-xl bg-gray-50 p-4 text-left">
              {steps.map((step, index) => {
                const done = index < activeStep
                const current = index === activeStep
                return (
                  <div key={step} className="flex items-center gap-3 text-sm">
                    <span
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
                        done
                          ? 'bg-emerald-500 text-white'
                          : current
                          ? 'bg-primary-500 text-white'
                          : 'bg-gray-200 text-gray-500'
                      }`}
                    >
                      {done ? '✓' : index + 1}
                    </span>
                    <span className={current ? 'font-semibold text-gray-800' : done ? 'text-gray-600' : 'text-gray-400'}>
                      {step}
                    </span>
                  </div>
                )
              })}
            </div>
          )}

          <p className="text-xs leading-5 text-amber-700">
            多組預約排課可能需要一些時間，請不要關閉頁面或重複送出。
          </p>
        </div>
      </div>
    </div>
  )
}
