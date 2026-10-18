import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, X } from 'lucide-react'
import { fetchAdminMe } from '../api/auth'
import { fetchNotificationTargets, previewManualNotification, sendManualNotification, type ManualNotificationDraft, type ManualNotificationPreview } from '../api/operations'
import { hasAdminPermission } from '../permissions'
import { useNotification } from '../context'

const inputClass = 'mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-violet-400 disabled:opacity-60 dark:border-gray-600 dark:bg-gray-700 dark:text-white'
const errorMessage = (error: any) => {
  const data = error?.response?.data
  const message = ['detail', 'msg', 'subject', 'body', 'target_id', 'non_field_errors']
    .map(key => data?.[key]).map(value => Array.isArray(value) ? value[0] : value)
    .find(value => typeof value === 'string' && value)
  return message
    || (error?.response?.status === 401 || error?.response?.status === 403 ? '權限不足或登入已逾時，請重新登入後再試。' : '發送狀態未確認，請保留此視窗重試；系統會避免重複發送。')
}

export default function ManualNotificationComposer({ onClose, initialTarget }: {
  onClose: () => void
  initialTarget?: { kind: 'order' | 'member'; id: number; label: string }
}) {
  const { data: adminMe } = useQuery({ queryKey: ['admin', 'me'], queryFn: fetchAdminMe })
  const canOrder = hasAdminPermission(adminMe?.user, 'orders')
  const canMember = hasAdminPermission(adminMe?.user, 'customers')
  const qc = useQueryClient(); const notify = useNotification()
  const [kind, setKind] = useState<'order' | 'member'>(initialTarget?.kind || (canOrder ? 'order' : 'member'))
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<{ id: number; label: string } | null>(initialTarget || null)
  const [audience, setAudience] = useState<'owner' | 'participants'>('owner')
  const [subject, setSubject] = useState(''); const [body, setBody] = useState('')
  const [preview, setPreview] = useState<(ManualNotificationPreview & { key: string; draft: ManualNotificationDraft }) | null>(null)
  const [pending, setPending] = useState(false); const [error, setError] = useState('')
  const busy = useRef(false); const dialog = useRef<HTMLDivElement>(null)
  const errorRef = useRef<HTMLParagraphElement>(null)
  const scope = localStorage.getItem('snowland_admin_campus_scope') || 'all'
  const { data: targets = [], isFetching, isError, refetch } = useQuery({
    queryKey: ['admin', 'manual-notification-targets', scope, kind, search],
    queryFn: () => fetchNotificationTargets(kind, search), enabled: !preview && !initialTarget,
  })
  useEffect(() => {
    if (!initialTarget && adminMe && ((kind === 'order' && !canOrder && canMember) || (kind === 'member' && !canMember && canOrder))) {
      setKind(canOrder ? 'order' : 'member'); setSelected(null)
    }
  }, [adminMe, canOrder, canMember, kind, initialTarget])
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialog.current?.focus()
    return () => { document.body.style.overflow = previous; previousFocus?.focus() }
  }, [])
  useEffect(() => { dialog.current?.focus() }, [preview])
  useEffect(() => { if (error) errorRef.current?.scrollIntoView({ block: 'nearest' }) }, [error])
  const valid = !!selected && !!subject.trim() && !!body.trim() && subject.trim().length <= 200 && body.trim().length <= 10000
  const check = async () => {
    if (!valid || busy.current || !selected) return
    busy.current = true; setPending(true); setError('')
    const draft: ManualNotificationDraft = { kind, target_id: selected.id, audience: kind === 'order' ? audience : 'owner', subject: subject.trim(), body: body.trim() }
    try {
      const result = await previewManualNotification(draft)
      setPreview({ ...result, draft, key: crypto.randomUUID() })
    } catch (e) { setError(errorMessage(e)) }
    finally { busy.current = false; setPending(false) }
  }
  const send = async () => {
    if (!preview || busy.current) return
    busy.current = true; setPending(true); setError('')
    try {
      const result = await sendManualNotification({ ...preview.draft, request_key: preview.key, expected_recipient_ids: preview.recipients.map(row => row.id) })
      qc.invalidateQueries({ queryKey: ['admin', 'notification-deliveries'] })
      notify.success(`已發送給 ${result.count} 位會員${result.duplicate ? '（未重複發送）' : ''}`)
      onClose()
    } catch (e: any) { setError(errorMessage(e)); if (e?.response?.status === 409) setPreview(null) }
    finally { busy.current = false; setPending(false) }
  }
  return <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 p-3 sm:p-5">
    <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="manual-notice-title" tabIndex={-1}
      className="flex max-h-[calc(100dvh-24px)] w-full max-w-xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl outline-none dark:bg-gray-800"
      onKeyDown={event => {
        if (event.key === 'Escape' && !pending) { onClose(); return }
        if (event.key !== 'Tab') return
        const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled)'))
        const first = items[0], last = items[items.length - 1]
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last?.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
      }}>
      <header className="flex shrink-0 items-center justify-between gap-3 bg-gradient-to-r from-violet-500 to-violet-600 px-5 py-4 text-white"><h2 id="manual-notice-title" className="font-semibold">{preview ? '確認站內通知' : '新增站內通知'}</h2><button aria-label="關閉站內通知視窗" disabled={pending} onClick={onClose} className="rounded-lg p-2 hover:bg-white/10 disabled:opacity-50"><X size={20} /></button></header>
      <div className="space-y-4 overflow-y-auto p-5 text-sm text-gray-900 dark:text-gray-100">
        <p className="rounded-lg bg-blue-50 p-3 leading-6 text-blue-900 dark:bg-blue-900/30 dark:text-blue-100">只出現在會員「通知中心」，不寄 Email／LINE。發送前請確認收件人及內容。</p>
        {preview ? <>
          <p>對象：<strong className="break-all">{preview.target_label}</strong></p>
          <section className="rounded-lg border border-gray-200 p-3 dark:border-gray-600"><h3 className="font-semibold">共 {preview.count} 位收件人</h3><ul className="mt-2 max-h-32 space-y-1 overflow-auto">{preview.recipients.map(row => <li key={row.id} className="break-all">{row.name}（會員 #{row.id}）</li>)}</ul><p className="mt-2 text-xs text-gray-500 dark:text-gray-400">同一位家長照顧多位孩子只收到一次；不同帳號各有自己的已讀紀錄。</p></section>
          <section className="rounded-lg bg-gray-50 p-4 dark:bg-gray-900"><h3 className="break-words font-semibold">{preview.subject}</h3><p className="mt-3 whitespace-pre-wrap break-words leading-6">{preview.body}</p></section>
        </> : <>
          <label className="block font-medium">發送對象<select aria-label="發送對象" disabled={pending || !!initialTarget} className={inputClass} value={kind} onChange={event => { setKind(event.target.value as 'order' | 'member'); setSelected(null); setQuery(''); setSearch(''); setAudience('owner'); setError('') }}>{canOrder && <option value="order">單筆訂單</option>}{canMember && <option value="member">單一會員</option>}</select></label>
          {!initialTarget && <div><label className="block font-medium">搜尋訂單或會員<input aria-label="搜尋訂單或會員" disabled={pending} className={inputClass} value={query} placeholder={kind === 'order' ? '訂單編號或訂購人' : '姓名或 Email'} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); setSearch(query.trim()); setSelected(null) } }} /></label><button disabled={pending || isFetching} onClick={() => { setSearch(query.trim()); setSelected(null); if (query.trim() === search) refetch() }} className="mt-2 rounded-lg border border-violet-300 px-3 py-2 text-violet-700 dark:text-violet-300">搜尋</button></div>}
          <label className="block font-medium">{kind === 'order' ? '選擇訂單' : '選擇會員'}<select aria-label={kind === 'order' ? '選擇訂單' : '選擇會員'} disabled={pending || !!initialTarget} className={inputClass} value={selected?.id || ''} onChange={event => { setSelected(targets.find(row => row.id === Number(event.target.value)) || null); setError('') }}><option value="">請選擇</option>{selected && !targets.some(row => row.id === selected.id) && <option value={selected.id}>{selected.label}</option>}{targets.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
          {isFetching && <p role="status" className="text-gray-500 dark:text-gray-400">收件對象載入中…</p>}
          {isError && <p role="alert" className="text-red-600 dark:text-red-300">對象載入失敗，請按搜尋重試；也請確認訂單／會員管理權限。</p>}
          {!isFetching && !isError && !targets.length && !initialTarget && <p className="text-gray-500 dark:text-gray-400">沒有符合對象。只列目前校區範圍內有訂課或綁定紀錄的會員。</p>}
          {kind === 'order' && <label className="block font-medium">收件範圍<select aria-label="收件範圍" disabled={pending} className={inputClass} value={audience} onChange={event => setAudience(event.target.value as 'owner' | 'participants')}><option value="owner">只有訂購人</option><option value="participants">訂購人＋已綁定學員／家長</option></select><span className="mt-1 block text-xs font-normal text-gray-500 dark:text-gray-400">付款、退款或個人資料請選只有訂購人；未綁定者不會收到站內通知。</span></label>}
          <label className="block font-medium">通知主旨<input aria-label="手動通知主旨" maxLength={200} disabled={pending} className={inputClass} value={subject} onChange={event => setSubject(event.target.value)} /></label>
          <label className="block font-medium">通知內容<textarea aria-label="手動通知內容" maxLength={10000} rows={5} disabled={pending} className={inputClass} value={body} onChange={event => setBody(event.target.value)} /><span className="mt-1 block text-xs font-normal text-gray-500 dark:text-gray-400">{body.length}／10000 字；以純文字發送，不自動帶入姓名或付款連結。</span></label>
        </>}
        {error && <p ref={errorRef} role="alert" className="rounded-lg bg-red-50 p-3 text-red-700 dark:bg-red-950 dark:text-red-300">{error}</p>}
      </div>
      <footer className="flex shrink-0 justify-end gap-3 border-t border-gray-200 p-4 dark:border-gray-700"><button disabled={pending} onClick={() => { if (preview) { setPreview(null); setError('') } else onClose() }} className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-800 disabled:opacity-50 dark:border-gray-600 dark:text-gray-100">{preview ? '返回修改' : '取消'}</button><button disabled={pending || (!preview && !valid)} onClick={preview ? send : check} className="inline-flex items-center gap-2 rounded-lg bg-violet-500 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-600 disabled:opacity-40">{pending && <Loader2 size={16} className="animate-spin" />}{pending ? preview ? '發送中…' : '預覽中…' : preview ? '確認發送站內通知' : '預覽收件人與內容'}</button></footer>
    </div>
  </div>
}
