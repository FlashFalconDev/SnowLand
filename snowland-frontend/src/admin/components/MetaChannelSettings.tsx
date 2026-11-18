import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import adminApi from '../api/axios'
import { metaChannelPath, metaStatusQuery } from '../api/socialChannels'

const button = 'min-h-11 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium disabled:opacity-50 dark:border-gray-600'
const primary = `${button} bg-violet-700 text-white`
const resultMessages: Record<string, string> = {
  bound: '粉絲專頁已綁定。私訊收發尚待開通。',
  declined: '已取消授權。',
  failed: 'Meta 授權未完成。請重新授權並確認粉絲專頁的訊息管理權限。',
}

export default function MetaChannelSettings({ tenantCode }: { tenantCode: string }) {
  const [pageId, setPageId] = useState('')
  const [search, setSearch] = useSearchParams()
  const options = metaStatusQuery(tenantCode)
  const query = useQuery(options)
  const data = query.data
  const pages = data?.available_pages ?? []
  const selected = pageId || (pages.length === 1 ? pages[0].id : '')
  const qc = useQueryClient()
  const mutation = useMutation({
    mutationFn: async (action: 'authorize' | 'bind' | 'disconnect') => {
      if (action === 'disconnect') return adminApi.delete(metaChannelPath)
      if (action === 'bind') return adminApi.put(metaChannelPath, { page_id: selected })
      const response = await adminApi.post(metaChannelPath, {}) as unknown as { data: { authorization_url: string } }
      const target = new URL(response.data.authorization_url)
      if (target.origin !== 'https://www.facebook.com' || !/^\/v\d+\.\d+\/dialog\/oauth$/.test(target.pathname)) throw Error('無效的 Meta 授權網址')
      window.location.assign(target.href)
    },
    onSuccess: async (_, action) => {
      setPageId('')
      if (action !== 'authorize') setSearch(previous => {
        const next = new URLSearchParams(previous)
        if (action === 'bind') next.set('meta', 'bound')
        else next.delete('meta')
        return next
      }, { replace: true })
      await qc.invalidateQueries({ queryKey: options.queryKey })
    },
  })
  const result = search.get('meta') || ''
  const error = mutation.error as { response?: { data?: { msg?: string } } } | null
  return <section className="space-y-3 rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
    <div className="mb-4 flex items-center gap-2">
      <Sparkles size={16} className="shrink-0 text-violet-600 dark:text-violet-300" aria-hidden />
      <h2 className="text-lg font-semibold leading-none text-gray-900 dark:text-white">用 Facebook 一鍵授權</h2>
    </div>
    {resultMessages[result] && (result !== 'bound' || (query.isSuccess && data?.page_id)) &&
      <p role="status" className="text-sm">{resultMessages[result]}</p>}
    {query.isPending && <p role="status" className="text-sm">正在讀取授權狀態…</p>}
    {query.isError && <div role="alert" className="text-sm">無法讀取授權狀態。 <button className={button} onClick={() => void query.refetch()}>重試</button></div>}
    {data && <div className="space-y-3 text-sm">
      <p>{data.page_id ? `已綁定粉絲專頁 · ${data.page_name || data.page_id}` : '尚未綁定粉絲專頁'}</p>
      {data.instagram_name && <p>關聯的 Instagram 帳號 · @{data.instagram_name}</p>}
      {!data.platform_ready && <p role="status" className="rounded-lg bg-amber-50 p-3 text-amber-900 dark:bg-amber-950 dark:text-amber-200">等系統管理員開通 Meta 授權後，由粉絲專頁管理者在這裡連接。</p>}
      <ol className="ml-5 list-decimal space-y-1 text-gray-600 dark:text-gray-300">
        <li>前往 Meta，以有權管理粉絲專頁的帳號授權。</li>
        <li>回到這裡選擇粉絲專頁。已關聯的 Instagram 專業帳號會一起綁定。</li>
      </ol>
      {data.platform_ready && pages.length > 0 && <form className="space-y-2" onSubmit={event => { event.preventDefault(); mutation.mutate('bind') }}>
        <label className="block">選擇要綁定的粉絲專頁
          <select value={selected} onChange={event => setPageId(event.target.value)} required className="mt-1 block min-h-11 w-full max-w-md rounded-lg border border-gray-300 bg-white px-3 dark:border-gray-600 dark:bg-gray-900">
            <option value="">請選擇粉絲專頁</option>
            {pages.map(page => <option key={page.id} value={page.id}>{page.name}{page.instagram_name && ` · @${page.instagram_name}`}</option>)}
          </select>
        </label>
        <button className={primary} disabled={mutation.isPending || !selected}>綁定選取的粉絲專頁</button>
      </form>}
      {data.platform_ready && result === 'choose' && pages.length === 0 && <p role="status">粉絲專頁清單已逾時，請重新授權。</p>}
      <div className="flex flex-wrap gap-2">
        {data.platform_ready && <button className={pages.length ? button : primary} disabled={mutation.isPending} onClick={() => mutation.mutate('authorize')}>{data.page_id || pages.length ? '重新授權' : '前往 Meta 授權'}</button>}
        {data.page_id && <button type="button" className={button} disabled={mutation.isPending} onClick={() => window.confirm('要移除本租戶的 Meta 授權資料嗎？') && mutation.mutate('disconnect')}>解除綁定</button>}
      </div>
      {mutation.isPending && <p role="status">處理中…</p>}
      {error && <p role="alert">{error.response?.data?.msg || '更新 Meta 授權失敗，請確認平台設定及粉絲專頁權限。'}</p>}
    </div>}
  </section>
}
