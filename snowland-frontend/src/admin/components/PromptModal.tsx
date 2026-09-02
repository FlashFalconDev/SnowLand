/**
 * 輸入對話框（取代瀏覽器原生 prompt）
 * 用法：見 usePromptModal hook 下面
 */
import { useState, useEffect, useRef } from 'react'
import { X, Loader2 } from 'lucide-react'

const PRIMARY = '#8b5cf6'

export interface PromptField {
  name: string
  label: string
  type?: 'text' | 'number' | 'time' | 'date' | 'textarea' | 'select'
  defaultValue?: string
  placeholder?: string
  required?: boolean
  helper?: string
  options?: Array<{ value: string; label: string }>
}

export interface PromptModalProps {
  open: boolean
  title: string
  description?: string
  fields: PromptField[]
  submitLabel?: string
  onCancel: () => void
  onSubmit: (values: Record<string, string>) => void | Promise<void>
}

export default function PromptModal({
  open, title, description, fields,
  submitLabel = '確定', onCancel, onSubmit,
}: PromptModalProps) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const firstInputRef = useRef<{ focus: () => void } | null>(null)

  // 初始化
  useEffect(() => {
    if (open) {
      const init: Record<string, string> = {}
      fields.forEach((f) => { init[f.name] = f.defaultValue || '' })
      setValues(init)
      setLoading(false)
      // 自動 focus 第一個輸入
      setTimeout(() => firstInputRef.current?.focus(), 50)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  if (!open) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // 必填驗證
    for (const f of fields) {
      if (f.required && !(values[f.name] || '').trim()) {
        alert(`請填寫「${f.label}」`)
        return
      }
    }
    setLoading(true)
    try {
      await onSubmit(values)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/50 animate-fadeIn">
      <form
        onSubmit={handleSubmit}
        className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md"
      >
        <div className="rounded-t-2xl px-6 py-4 text-white flex items-center justify-between"
          style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}>
          <h3 className="text-lg font-semibold">{title}</h3>
          <button type="button" onClick={onCancel} className="text-white/80 hover:text-white">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {description && (
            <p className="text-sm text-gray-600 dark:text-gray-400">{description}</p>
          )}

          {fields.map((f, idx) => (
            <div key={f.name}>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {f.label} {f.required && <span className="text-red-500">*</span>}
              </label>
              {f.type === 'textarea' ? (
                <textarea
                  value={values[f.name] || ''}
                  onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                  placeholder={f.placeholder}
                  rows={4}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30 resize-none"
                />
              ) : f.type === 'select' ? (
                <select
                  ref={idx === 0 ? (element) => { firstInputRef.current = element } : undefined}
                  value={values[f.name] || ''}
                  onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                >
                  {(f.options || []).map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  ref={idx === 0 ? (element) => { firstInputRef.current = element } : undefined}
                  type={f.type || 'text'}
                  value={values[f.name] || ''}
                  onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                  placeholder={f.placeholder}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
                />
              )}
              {f.helper && (
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{f.helper}</p>
              )}
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
          <button type="button" onClick={onCancel} disabled={loading}
            className="px-4 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50">
            取消
          </button>
          <button type="submit" disabled={loading}
            className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
            style={{ backgroundColor: PRIMARY }}>
            {loading && <Loader2 size={14} className="animate-spin" />}
            {submitLabel}
          </button>
        </div>
      </form>
    </div>
  )
}
