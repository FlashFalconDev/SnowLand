import { useId, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { saveOrderMarketingSource } from '../api/orders'
import { useNotification } from '../context'

export default function OrderMarketingSource({ orderId, source, options }: {
  orderId: number
  source: string | null
  options?: string[]
}) {
  const [draft, setDraft] = useState<string | null>(null)
  const selected = draft ?? source ?? ''
  const selectId = useId()
  const queryClient = useQueryClient()
  const notify = useNotification()
  const save = useMutation({
    mutationFn: () => saveOrderMarketingSource(orderId, selected || null),
    onSuccess: async response => {
      notify.success(response.msg)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['admin', 'orders'] }),
        queryClient.invalidateQueries({ queryKey: ['admin', 'dashboard'] }),
      ])
      setDraft(null)
    },
  })
  const feedback = isAxiosError<{ msg?: string; detail?: string }>(save.error) ? save.error.response?.data : undefined

  if (!options) {
    return <div className="mt-2 flex justify-between gap-3">
      <span className="shrink-0 text-gray-500 dark:text-gray-400">補登客人來源</span>
      <span className="min-w-0 break-words text-right">{source || '未補登'}</span>
    </div>
  }

  return <div className="mt-3 border-t border-gray-200 pt-3 dark:border-gray-600">
    <label htmlFor={selectId} className="font-medium">補登客人來源</label>
    <div className="mt-2 flex flex-wrap items-start gap-2">
      <select id={selectId} value={selected} disabled={save.isPending}
        onChange={event => { setDraft(event.target.value); save.reset() }}
        className="min-h-11 w-full min-w-0 rounded-lg border border-gray-300 bg-white px-3 text-sm dark:border-gray-600 dark:bg-gray-800 sm:w-auto sm:flex-1">
        <option value="">沿用原始來源</option>
        {source && !options.includes(source) && <option value={source} disabled>{source}（已停用）</option>}
        {options.map(option => <option key={option} value={option}>{option}</option>)}
      </select>
      <button type="button" disabled={save.isPending || selected === (source || '')} onClick={() => save.mutate()}
        className="min-h-11 rounded-lg bg-violet-600 px-4 text-sm font-medium text-white disabled:opacity-50">
        {save.isPending ? '儲存中…' : '儲存客人來源'}
      </button>
    </div>
    {save.isError && <p role="alert" className="mt-2 break-words text-xs text-red-600 dark:text-red-400">
      {feedback?.msg || feedback?.detail || '客人來源儲存失敗，請重試'}
    </p>}
  </div>
}
