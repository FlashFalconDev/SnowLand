import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { campusScopeKey, currentClientCode } from '@/utils/tenant'
import adminApi from '../api/axios'

type Result<T> = { data: T }
type MerchantStatus = { configured: boolean; enabled: boolean; environment: 'sandbox' | 'production' | null; runtime_ready: boolean; sandbox_available: boolean; legacy: boolean }
type CardStatus = { enabled: boolean; can_change: boolean; gateway_ready: boolean }
const blank = { merchant_id: '', hash_key: '', hash_iv: '', environment: 'sandbox' }
const input = 'mt-1 block min-h-11 w-full rounded-lg border border-gray-300 px-3 dark:border-gray-600 dark:bg-gray-900'
const button = 'min-h-11 rounded-lg border border-violet-300 px-3 py-2 text-sm font-semibold text-violet-700 disabled:opacity-50 dark:text-violet-300'
const errorMessage = (error: unknown) => {
  const response = (error as { response?: { data?: { msg?: string } } } | null)?.response
  return response?.data?.msg || '操作失敗，請重新整理後再試。'
}

export default function NewebpaySettingsPanel() {
  const key = ['admin', currentClientCode(), 'newebpay-settings']
  const cache = useQueryClient()
  const [form, setForm] = useState(blank)
  const [editing, setEditing] = useState(false)
  const [notice, setNotice] = useState('')
  const query = useQuery({
    queryKey: key, retry: false,
    queryFn: async () => (await adminApi.get('/newebpay-settings/') as unknown as Result<MerchantStatus>).data,
  })
  const save = useMutation({
    gcTime: 0,
    mutationFn: async (body: { enabled: boolean } & Partial<typeof blank>) => {
      try {
        return (await adminApi.put('/newebpay-settings/', body) as unknown as Result<MerchantStatus>).data
      } catch (error) {
        throw new Error(errorMessage(error))
      }
    },
    onSuccess: result => {
      cache.setQueryData(key, result)
      void cache.invalidateQueries({ queryKey: ['admin', currentClientCode(), 'order-card-payment'] })
      setForm(blank); setEditing(false); setNotice('藍新設定已更新。'); save.reset()
    },
  })
  const data = query.data
  return <section aria-label="藍新金流設定" className="space-y-3 rounded-xl border border-gray-200 p-5 dark:border-gray-700">
    <h2 className="font-semibold">藍新金流設定</h2>
    <p className="text-sm">只設定本租戶的商店。金鑰加密保存，不會顯示在後台或回傳給瀏覽器。</p>
    {query.isLoading && <p role="status">讀取藍新設定…</p>}
    {query.isError && <p role="alert">無法讀取藍新設定或沒有權限。</p>}
    {save.isError && <p role="alert">{save.error.message}</p>}
    {notice && <p role="status">{notice}</p>}
    {data && <>
      <p className="text-sm">{data.legacy ? '沿用原有的伺服器商店設定' : !data.configured ? '未設定或金鑰無法解密' : data.environment === 'sandbox' ? '測試商店' : '正式商店'}{!data.legacy && (data.enabled ? ' · 已啟用' : ' · 未啟用')}</p>
      {!data.runtime_ready && <p className="text-sm">平台尚未設定憑證加密，現在不能存入金鑰。</p>}
      {data.environment === 'sandbox' && !data.sandbox_available && <p className="text-sm">這個環境未開放測試商店，不會讓測試交易進入正式訂單。</p>}
      {data.runtime_ready && !editing && <button type="button" className={button} disabled={save.isPending} onClick={() => { save.reset(); setNotice(''); setEditing(true) }}>{data.configured ? '登錄新商店憑證' : '新增商店憑證'}</button>}
      {!editing && !data.legacy && (data.configured || data.enabled) && <button type="button" className={button} disabled={save.isPending || (!data.enabled && data.environment === 'sandbox' && !data.sandbox_available)} onClick={() => { setNotice(''); save.mutate({ enabled: !data.enabled }) }}>
        {data.enabled ? '停用新刷卡' : '啟用藍新刷卡'}
      </button>}
      {editing && <form className="space-y-3" onSubmit={event => { event.preventDefault(); save.mutate({ ...form, enabled: false }) }}>
        <fieldset className="space-y-3" disabled={save.isPending}>
          <label className="block text-sm">商店環境<select className={input} value={form.environment} onChange={event => setForm({ ...form, environment: event.target.value })}><option value="sandbox">測試</option><option value="production">正式</option></select></label>
          <label className="block text-sm">商店代號<input className={input} value={form.merchant_id} required maxLength={15} autoComplete="off" onChange={event => setForm({ ...form, merchant_id: event.target.value })} /></label>
          <label className="block text-sm">HashKey<input className={input} value={form.hash_key} type="password" required minLength={32} maxLength={32} autoComplete="new-password" onChange={event => setForm({ ...form, hash_key: event.target.value })} /></label>
          <label className="block text-sm">HashIV<input className={input} value={form.hash_iv} type="password" required minLength={16} maxLength={16} autoComplete="new-password" onChange={event => setForm({ ...form, hash_iv: event.target.value })} /></label>
          <p className="text-sm">儲存新商店後，先停用新刷卡。已發出的付款連結仍按原商店驗證。</p>
          <button type="button" className={button} onClick={() => { save.reset(); setForm(blank); setEditing(false) }}>取消</button>
          <button type="submit" className={button}>儲存為未啟用</button>
        </fieldset>
      </form>}
    </>}
  </section>
}

export function OrderCardPaymentPanel({ orderId }: { orderId: number }) {
  const cache = useQueryClient()
  const client = currentClientCode()
  const campus = localStorage.getItem(campusScopeKey(client)) || 'all'
  const key = ['admin', client, 'order-card-payment', campus, orderId]
  const route = `/orders/${orderId}/card-payment/`
  const query = useQuery({
    queryKey: key, retry: false,
    queryFn: async () => (await adminApi.get(route) as unknown as Result<CardStatus>).data,
  })
  const save = useMutation({
    mutationFn: async (enabled: boolean) => (await adminApi.put(route, { enabled }) as unknown as Result<CardStatus>).data,
    onSuccess: data => cache.setQueryData(key, data),
  })
  const data = query.data
  return <div className="space-y-2 border-t border-gray-200 pt-3 text-sm dark:border-gray-600">
    {query.isLoading ? <p role="status">確認刷卡設定…</p> : query.isError ? <p role="alert">無法讀取本單的刷卡設定。</p> : data && <>
      <p>本單刷卡：{data.enabled ? '已開放' : '未開放'}</p>
      {!data.gateway_ready && <p>本租戶尚未啟用可用的藍新商店。</p>}
      {data.can_change && <button type="button" className={button} disabled={save.isPending || (!data.enabled && !data.gateway_ready)} onClick={() => save.mutate(!data.enabled)}>{data.enabled ? '關閉本單刷卡' : '開放本單刷卡'}</button>}
    </>}
    {save.isError && <p role="alert">{errorMessage(save.error)}</p>}
  </div>
}
