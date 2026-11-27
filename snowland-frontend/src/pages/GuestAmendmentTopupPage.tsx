import { useEffect, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { formatPaymentValue, type PaymentCurrency } from '@/utils/settlementPreview'

type Instructions = {
  currency: PaymentCurrency
  amount: number
  bank: { bank_name: string; bank_branch?: string; account_number: string; account_holder: string; overseas_details?: string }
}

const unavailable = '補款連結無效、已到期或差額已停止收款，請聯絡客服。'

export default function GuestAmendmentTopupPage() {
  const { clientCode, groupId, amendmentId } = useParams()
  const { hash } = useLocation()
  const access = new URLSearchParams(hash.slice(1)).get('access')
  const [instructions, setInstructions] = useState<Instructions | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let controller: AbortController | undefined
    async function load() {
      controller?.abort()
      setInstructions(null)
      setError('')
      if (!clientCode || !groupId || !amendmentId || !access) {
        setError(unavailable)
        return
      }
      controller = new AbortController()
      const { signal } = controller
      try {
        const url = `/booking/${encodeURIComponent(clientCode)}/api/amendment-topup/${encodeURIComponent(groupId)}/${encodeURIComponent(amendmentId)}/`
        const response = await fetch(url, {
          signal, cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer',
          headers: { 'X-Amendment-Access': access },
        })
        if (!response.ok) throw new Error(unavailable)
        const result: Instructions = await response.json()
        if (!signal.aborted) setInstructions(result)
      } catch {
        if (!signal.aborted) setError(unavailable)
      }
    }
    function revalidate() {
      if (document.visibilityState === 'visible') void load()
    }
    void load()
    document.addEventListener('visibilitychange', revalidate)
    window.addEventListener('pageshow', revalidate)
    return () => {
      controller?.abort()
      document.removeEventListener('visibilitychange', revalidate)
      window.removeEventListener('pageshow', revalidate)
    }
  }, [clientCode, groupId, amendmentId, access])

  return <main className="mx-auto max-w-lg space-y-5 px-4 py-10 text-slate-900">
    <h1 className="text-2xl font-semibold">訂單修改差額補款</h1>
    {error ? <p role="alert" className="rounded-lg bg-amber-50 p-4">{error}</p>
      : !instructions ? <p role="status">正在確認補款資訊…</p>
        : <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <p>應補款金額 <strong className="text-xl">{formatPaymentValue(instructions.amount, instructions.currency)}</strong></p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
            <dt>銀行</dt><dd className="break-words">{instructions.bank.bank_name}</dd>
            {instructions.bank.bank_branch && <><dt>分行</dt><dd className="break-words">{instructions.bank.bank_branch}</dd></>}
            <dt>帳號</dt><dd className="break-all font-mono">{instructions.bank.account_number}</dd>
            <dt>戶名</dt><dd className="break-words">{instructions.bank.account_holder}</dd>
          </dl>
          {instructions.bank.overseas_details && <p className="whitespace-pre-wrap break-words">{instructions.bank.overseas_details}</p>}
          <p className="text-sm leading-6 text-slate-600">請在銀行完成匯款，再透過原聯絡管道提供匯款資訊，由客服核對實際入帳。</p>
        </section>}
  </main>
}
