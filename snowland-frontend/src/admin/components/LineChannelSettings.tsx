import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Settings2 } from 'lucide-react'
import adminApi from '../api/axios'
import { lineChannelPath, lineStatusQuery } from '../api/socialChannels'

const fieldClass = 'mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 dark:border-gray-600'
const buttonClass = 'min-h-11 rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-gray-600'

export default function LineChannelSettings({ tenantCode }: { tenantCode: string }) {
  const [secret, setSecret] = useState('')
  const [token, setToken] = useState('')
  const options = lineStatusQuery(tenantCode)
  const queryClient = useQueryClient()
  const query = useQuery(options)
  const mutation = useMutation({
    mutationFn: async (input: { channel_secret: string; access_token: string } | undefined) =>
      input ? adminApi.put(lineChannelPath, input) : adminApi.delete(lineChannelPath),
    onSuccess: () => { setSecret(''); setToken(''); void queryClient.invalidateQueries({ queryKey: options.queryKey }) },
  })
  const data = query.data
  const save = (event: FormEvent) => {
    event.preventDefault()
    mutation.mutate({ channel_secret: secret.trim(), access_token: token.trim() })
  }
  const problem = mutation.error as { response?: { data?: { msg?: string } } } | null

  return <section className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
    <div className="mb-4 flex items-center gap-2">
      <Settings2 size={16} className="shrink-0 text-violet-600 dark:text-violet-300" aria-hidden />
      <h2 className="text-lg font-semibold leading-none text-gray-900 dark:text-white">基本設定</h2>
    </div>
    {query.isLoading && <p role="status" className="mt-3">正在讀取頻道設定…</p>}
    {query.isError && <p role="alert" className="mt-3">無法讀取頻道設定。<button type="button" className={buttonClass} onClick={() => void query.refetch()}>重試</button></p>}
    {data && <div className="mt-3 space-y-3 text-sm">
      <p role="status">{data.verified ? `已驗證 · ${data.display_name}` : data.enabled ? `待驗證 Webhook · ${data.display_name}` : data.legacy ? '使用原有 LINE 頻道設定' : '尚未連線'}</p>
      {data.legacy && <p className="text-gray-600 dark:text-gray-300">此租戶由平台管理員維護原有的 LINE 頻道。如需改由 Console 管理，請先安排移轉，保留既有對話。</p>}
      {!data.legacy && !data.runtime_ready && <p role="status" className="rounded-lg bg-amber-50 p-3 text-amber-900 dark:bg-amber-950 dark:text-amber-200">等系統管理員開通憑證加密後，就能在這裡連接 LINE。</p>}
      {!data.legacy && <ol className="ml-5 list-decimal space-y-1 text-gray-600 dark:text-gray-300">
        <li>在 LINE Developers 開啟官方帳號對應的 Messaging API 頻道。</li>
        <li>把該頻道的 Channel Secret 和 Channel Access Token 填入並儲存。</li>
        <li>在 LINE Developers 貼上儲存後顯示的 Webhook 網址，啟用並驗證。</li>
      </ol>}
      {(data.enabled || data.legacy) && <label className="block">Webhook 網址
        <input className={fieldClass} readOnly value={new URL(data.webhook_path, window.location.origin).href} onFocus={event => event.currentTarget.select()} />
      </label>}
      {data.runtime_ready && !data.legacy && !data.enabled && <form onSubmit={save} className="grid gap-4 md:grid-cols-2">
        <label className="block">頻道存取權杖（Channel Access Token）<input className={fieldClass} type="password" autoComplete="off" required maxLength={4096} value={token} onChange={(event) => setToken(event.target.value)} /></label>
        <label className="block">頻道密鑰（Channel Secret）<input className={fieldClass} type="password" autoComplete="off" required maxLength={32} value={secret} onChange={(event) => setSecret(event.target.value)} /></label>
        <div className="md:col-span-2">
          <button className={`${buttonClass} bg-violet-700 text-white`} disabled={mutation.isPending}>儲存 LINE 頻道</button>
        </div>
      </form>}
      {data.enabled && <div className="flex flex-wrap gap-2">
        <button type="button" className={buttonClass} disabled={mutation.isPending} onClick={() => void query.refetch()}>更新驗證狀態</button>
        <button type="button" className={buttonClass} disabled={mutation.isPending} onClick={() => window.confirm('要停用此 LINE 頻道嗎？既有客服對話會保留。') && mutation.mutate(undefined)}>停用頻道</button>
      </div>}
      {mutation.isPending && <p role="status">正在更新頻道設定…</p>}
      {problem && <p role="alert">{problem.response?.data?.msg || '更新頻道設定失敗'}</p>}
    </div>}
  </section>
}
