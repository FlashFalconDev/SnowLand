import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import adminApi from '../api/axios'
import { instagramPostsPath, instagramStatusQuery } from '../api/socialChannels'

const button = 'min-h-11 rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold disabled:opacity-50 dark:border-gray-600'
const callbackMessages: Record<string, string> = {
  connected: '官方帳號授權已完成，可按「立即同步」檢查貼文。',
  declined: '已取消官方授權，既有貼文保留。',
  invalid_state: '授權已逾時或驗證不符，請重新授權。',
  failed: '授權未完成，請查看下方原因後重新嘗試。',
}
const formatDate = (value: string | null) => value ? new Date(value).toLocaleString('zh-TW') : '尚無紀錄'

export default function InstagramPostSettings({ tenantCode }: { tenantCode: string }) {
  const [search] = useSearchParams()
  const result = search.get('ig') || ''
  const options = instagramStatusQuery(tenantCode)
  const query = useQuery(options)
  const current = query.data
  const qc = useQueryClient()
  const [usernameDraft, setUsername] = useState<string | null>(null)
  const username = usernameDraft ?? current?.expected_username ?? ''
  const action = useMutation({
    mutationFn: async (kind: 'connect' | 'sync' | 'disconnect') => {
      const response = await adminApi.post(`${instagramPostsPath}${kind}/`, kind === 'connect' ? { expected_username: username.trim() } : {}, {
        timeout: kind === 'sync' ? 45000 : 15000,
      }) as unknown as { msg?: string; data?: { authorization_url?: string } }
      if (kind === 'connect') {
        const target = new URL(response.data?.authorization_url || '')
        if (target.origin !== 'https://www.instagram.com' || target.pathname !== '/oauth/authorize') throw Error('授權網址不正確')
        window.location.assign(target.href)
      }
      return response
    },
    onSuccess: async () => {
      setUsername(null)
      await qc.invalidateQueries({ queryKey: options.queryKey })
      await qc.invalidateQueries({ queryKey: ['admin', 'site-content'] })
    },
  })
  const error = action.error as { response?: { data?: { msg?: string; detail?: string } } } | null
  return <section className="space-y-3 rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
    <h2 className="text-lg font-semibold">同步設定</h2>
    {callbackMessages[result] && <p role="status">{callbackMessages[result]}</p>}
    {query.isPending && <p role="status">正在讀取同步狀態…</p>}
    {query.isError && <div role="alert">無法讀取同步狀態。 <button className={button} onClick={() => void query.refetch()}>重試</button></div>}
    {current && <>
      <p className="text-sm">{current.enabled && current.connected ? '已授權，允許同步' : '尚未授權或已停用'}{current.username && ` · @${current.username}`}</p>
      {current.missing_configuration.length > 0 ? <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">等系統管理員開通 Instagram 貼文同步後，由官方帳號管理者授權。</p> :
        <form className="space-y-3" onSubmit={event => { event.preventDefault(); action.mutate('connect') }}>
          <label className="block text-sm">官方 IG 帳號（不含 @）<input required maxLength={30} pattern="[A-Za-z0-9_.]+" disabled={current.connected || action.isPending} value={username} onChange={event => setUsername(event.target.value)} className="mt-1 block min-h-11 w-full max-w-md rounded-lg border border-gray-300 bg-transparent px-3 dark:border-gray-600" /></label>
          <div className="flex flex-wrap gap-2">
            <button className={`${button} bg-violet-700 text-white`} disabled={action.isPending || !username.trim()}>{current.connected ? '重新授權' : '前往 Instagram 授權'}</button>
            {current.enabled && current.connected && <button type="button" className={button} disabled={action.isPending} onClick={() => action.mutate('sync')}>立即同步</button>}
          </div>
        </form>}
      {current.connected && <button type="button" className={button} disabled={action.isPending} onClick={() => action.mutate('disconnect')}>停用並移除授權</button>}
      <dl className="grid gap-2 text-sm sm:grid-cols-2"><div><dt className="text-gray-600 dark:text-gray-300">最後同步</dt><dd>{formatDate(current.last_synced_at)}</dd></div><div><dt className="text-gray-600 dark:text-gray-300">授權有效期限</dt><dd>{formatDate(current.token_expires_at)}</dd></div></dl>
      {current.last_error && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{current.last_error}</p>}
    </>}
    {action.isPending && <p role="status">處理中…</p>}
    {action.data?.msg && <p role="status">{action.data.msg}</p>}
    {error && <p role="alert">{error.response?.data?.msg || error.response?.data?.detail || '操作未完成，請稍後再試。'}</p>}
  </section>
}
