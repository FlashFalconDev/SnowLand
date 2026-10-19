import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { fetchCheckoutPolicies, type CheckoutPolicies, type CheckoutPolicyAcceptance } from '../../api/booking'

type DocumentKey = 'terms' | 'privacy'
export default function CheckoutPolicyConsent({ onChange }: { onChange: (proof: CheckoutPolicyAcceptance | null) => void }) {
  const tenantCode = typeof window === 'undefined' ? '' : window.location.pathname.split('/').filter(Boolean)[0]
  const [policies, setPolicies] = useState<CheckoutPolicies | null>(null)
  const [error, setError] = useState(false)
  const [reload, setReload] = useState(0)
  const [accepted, setAccepted] = useState({ terms: false, privacy: false })
  const [opened, setOpened] = useState<DocumentKey | null>(null)
  const [atBottom, setAtBottom] = useState(false)
  const callback = useRef(onChange)
  callback.current = onChange
  const dialog = useRef<HTMLDialogElement>(null)
  const body = useRef<HTMLDivElement>(null)
  const opener = useRef<HTMLElement | null>(null)
  useEffect(() => {
    let current = true
    dialog.current?.close(); setOpened(null); setAtBottom(false)
    setPolicies(null); setError(false); setAccepted({ terms: false, privacy: false }); callback.current(null)
    fetchCheckoutPolicies().then(value => {
      if (!value?.documents?.terms?.body || !value?.documents?.privacy?.body) throw new Error('Missing policy')
      if (current) setPolicies(value)
    }).catch(() => { if (current) setError(true) })
    return () => { current = false }
  }, [reload, tenantCode])
  useLayoutEffect(() => {
    if (!opened) return
    setAtBottom(false)
    dialog.current?.showModal()
    const container = body.current
    if (container) { container.scrollTop = 0; setAtBottom(container.scrollHeight <= container.clientHeight + 2) }
  }, [opened])
  const close = () => { dialog.current?.close(); setOpened(null); opener.current?.focus() }
  const update = (key: DocumentKey, checked: boolean) => {
    const next = { ...accepted, [key]: checked }
    setAccepted(next)
    callback.current(policies && next.terms && next.privacy ? {
      ...next, terms_version: policies.documents.terms.version, privacy_version: policies.documents.privacy.version,
    } : null)
  }
  return <section aria-label="訂課條款確認" className="space-y-3 text-sm text-[#475569]">
    <p className="text-xs">請分別開啟兩份文件，閱讀到底並按「確認已閱讀」。</p>
    {error ? <p role="alert">條款載入失敗，尚無法送出訂單。<button type="button" className="min-h-11 px-3 underline" onClick={() => setReload(value => value + 1)}>重新載入條款</button></p> : !policies ? <p role="status">正在載入訂課條款…</p> : <>
      {(['terms', 'privacy'] as const).map(key => <div key={key} className="rounded-sm border border-[#d6dee8] bg-white px-3 py-2">
        <div className="flex items-center gap-2">
          <input type="checkbox" aria-label={`同意${policies.documents[key].title}`} checked={accepted[key]} disabled={!accepted[key]} onChange={() => update(key, false)} className="h-5 w-5" />
          <button type="button" className="min-h-11 text-left text-[#2b5f8f] underline" onClick={event => { opener.current = event.currentTarget; setAtBottom(false); setOpened(key) }}>{accepted[key] ? '已閱讀：' : '閱讀：'}{policies.documents[key].title}</button>
        </div>
        <p className="text-xs leading-6">{key === 'terms' ? '我了解課程服務內容、注意事項、取消、改期與退費規則，並須於指定期限內完成課前安全聲明。' : '我同意為完成預約、行程安排、保險及相關服務，在必要範圍內處理本人與同行者個人資料。'}</p>
      </div>)}
      <button type="button" className="min-h-11 text-xs underline" onClick={() => setReload(value => value + 1)}>重新載入最新條款（會清除本次勾選）</button>
    </>}
    <dialog ref={dialog} aria-labelledby="checkout-policy-title" onCancel={event => { event.preventDefault(); close() }} className="fixed inset-0 m-auto w-[calc(100%-2rem)] max-w-2xl rounded-2xl border-0 bg-white p-0 text-[#1f2937] shadow-2xl backdrop:bg-black/50">
      {opened && policies && <div className="flex max-h-[85dvh] flex-col">
        <header className="flex items-center justify-between gap-3 border-b bg-[#e9eef3] px-5 py-3"><h2 id="checkout-policy-title" className="font-semibold">{policies.documents[opened].title}</h2><button type="button" aria-label="關閉條款" onClick={close} className="min-h-11 min-w-11">✕</button></header>
        <div ref={body} tabIndex={0} aria-label="條款正文" onScroll={event => { const element = event.currentTarget; if (element.scrollHeight - element.scrollTop - element.clientHeight <= 4) setAtBottom(true) }} className="overflow-y-auto whitespace-pre-wrap break-words px-5 py-4 text-sm leading-7">{policies.documents[opened].body}</div>
        <footer className="flex shrink-0 flex-wrap items-center justify-end gap-3 border-t bg-gray-50 px-5 py-3"><p role="status" className="mr-auto text-xs">{atBottom ? '已到文件底部，可確認閱讀。' : '請閱讀並捲動至文件最下方。'}</p><button type="button" onClick={close} className="min-h-11 rounded-full border px-4">稍後閱讀</button><button type="button" disabled={!atBottom} onClick={() => { update(opened, true); close() }} className="min-h-11 rounded-full bg-[#2b5f8f] px-5 text-white disabled:opacity-40">確認已閱讀</button></footer>
      </div>}
    </dialog>
  </section>
}
