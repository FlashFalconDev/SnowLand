import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { campusScopeKey, currentClientCode } from '@/utils/tenant'
import {
  confirmInsuranceReconciliation, depositInsuranceFunds, fetchInsuranceLedger,
  fetchInsuranceReconciliation, reverseInsuranceEntry, type LedgerEntry, type Reconciliation,
} from '../api/insuranceLedger'
import { useInsuranceRequestKey } from './useInsuranceRequestKey'

const section = 'space-y-4 rounded-xl border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-700 dark:bg-gray-800'
const input = 'min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 dark:border-gray-600 dark:bg-gray-700'
const button = 'min-h-11 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40'
const secondary = 'min-h-11 rounded-lg border border-gray-300 px-3 text-sm disabled:opacity-40 dark:border-gray-600'
const kinds: Record<LedgerEntry['kind'], string> = { opening: '期初', top_up: '儲值', deduction: '扣款', reversal: '沖正' }
const taipeiTime = { timeZone: 'Asia/Taipei' }
const currentMonth = () => new Intl.DateTimeFormat('sv-SE', { ...taipeiTime, year: 'numeric', month: '2-digit' }).format(new Date())

function errorMessage(error: unknown, fallback: string) {
  const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data
  const message = data?.msg || data?.detail || Object.values(data || {})[0]
  return message ? String(message) : fallback
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block space-y-1 text-sm"><span className="font-medium">{label}</span>{children}</label>
}

export default function InsuranceLedgerPanel() {
  const tenant = currentClientCode()
  const allCampuses = (window.localStorage.getItem(campusScopeKey(tenant)) || 'all') === 'all'
  const [month, setMonth] = useState(currentMonth)
  const [page, setPage] = useState(1)
  const [reverseId, setReverseId] = useState<number | null>(null)
  const qc = useQueryClient()
  const ledger = useQuery({
    queryKey: ['admin', 'insurance-ledger', tenant, month, page],
    queryFn: () => fetchInsuranceLedger(month, page),
    enabled: allCampuses,
  })
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['admin', 'insurance-ledger', tenant] })
    void qc.invalidateQueries({ queryKey: ['admin', 'insurance-reconciliation', tenant] })
    void qc.invalidateQueries({ queryKey: ['admin', 'insurance-detail'] })
  }
  if (!allCampuses) return <p className={section}>請在上方校區選單切換至「全部校區」以查看帳本。</p>
  if (ledger.isPending) return <p role="status" className={section}>載入保費帳本中…</p>
  if (ledger.isError) return <div className={section} role="alert">
    <p>{errorMessage(ledger.error, '保費帳本載入失敗。')}</p>
    <button type="button" className={secondary} onClick={() => ledger.refetch()}>重新載入</button>
  </div>
  const data = ledger.data
  return <div className="space-y-5 text-gray-900 dark:text-gray-100">
    <section className={section}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <h2 className="font-semibold">目前餘額</h2>
        <p className="text-2xl font-semibold tabular-nums">{data.balance === null ? '尚未開帳' : `${data.currency} ${data.balance}`}</p>
      </div>
      {data.low_balance && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">預付保費已達低餘額門檻，請核對並安排儲值。</p>}
      {!data.writable && <p className="text-sm text-gray-600 dark:text-gray-300">{data.enabled ? '租戶設定幣別缺漏或與帳戶不符。' : '帳本已停用，目前僅供查閱。'}</p>}
    </section>
    {data.writable && <DepositForm key={String(data.balance === null)} opening={data.balance === null} currency={data.currency} onSaved={refresh} />}
    <section className={section}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="font-semibold">帳本明細</h2>
        <Field label="帳務月份"><input className={input} type="month" min="1900-01" max="9998-12" value={month}
          onChange={event => { if (event.target.value && event.target.validity.valid) { setMonth(event.target.value); setPage(1); setReverseId(null) } }} /></Field>
      </div>
      {!data.entries.length && <p className="text-sm text-gray-600 dark:text-gray-300">本月沒有分錄。</p>}
      <ul className="divide-y divide-gray-200 dark:divide-gray-700">
        {data.entries.map(entry => <li className="space-y-2 py-3 text-sm" key={entry.id}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-semibold">#{entry.sequence} {kinds[entry.kind]}{entry.reversed ? '（已沖正）' : ''}</p>
            <p className="tabular-nums">{Number(entry.amount) > 0 ? '+' : ''}{entry.amount} · 帳後 {entry.balance_after}</p>
          </div>
          <p className="text-gray-600 dark:text-gray-300">{new Date(entry.created_at).toLocaleString('zh-TW', taipeiTime)} · {entry.actor}</p>
          {entry.order_id !== null && <p>訂單 ID {entry.order_id} · 學員紀錄 ID {entry.member_id}</p>}
          {entry.reverses_id !== null && <p>原分錄 ID {entry.reverses_id}</p>}
          {(entry.reference || entry.note) && <p className="break-words">{[entry.reference, entry.note].filter(Boolean).join(' · ')}</p>}
          {data.writable && !entry.reversed && entry.kind !== 'reversal' && (
            reverseId === entry.id
              ? <ReversalForm entry={entry} onCancel={() => setReverseId(null)} onSaved={() => { setReverseId(null); refresh() }} />
              : <button type="button" className={secondary} onClick={() => setReverseId(entry.id)}>沖正 #{entry.sequence}</button>
          )}
        </li>)}
      </ul>
      {data.pages > 1 && <nav className="flex flex-wrap items-center gap-3" aria-label="帳本分頁">
        <button type="button" className={secondary} disabled={data.page <= 1} onClick={() => setPage(data.page - 1)}>上一頁</button>
        <span>第 {data.page}／{data.pages} 頁</span>
        <button type="button" className={secondary} disabled={data.page >= data.pages} onClick={() => setPage(data.page + 1)}>下一頁</button>
      </nav>}
    </section>
    {data.balance !== null && <ReconciliationPanel key={month} tenant={tenant} month={month} currency={data.currency} canConfirm={data.can_confirm_month} onSaved={refresh} />}
  </div>
}

function DepositForm({ opening, currency, onSaved }: { opening: boolean; currency: string; onSaved: () => void }) {
  const [amount, setAmount] = useState('')
  const [reference, setReference] = useState('')
  const [note, setNote] = useState('')
  const [posted, setPosted] = useState(false)
  const key = useInsuranceRequestKey()
  const save = useMutation({
    mutationFn: () => {
      const data = { kind: opening ? 'opening' as const : 'top_up' as const, amount, reference: reference.trim(), note: note.trim() }
      return depositInsuranceFunds({ ...data, idempotency_key: key.forPayload(data) })
    },
    onSuccess: () => { setAmount(''); setReference(''); setNote(''); setPosted(true); key.reset(); onSaved() },
  })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!save.isPending && Number(amount) > 0 && reference.trim()) { setPosted(false); save.mutate() }
  }
  return <form onSubmit={submit} className={section}>
    <h2 className="font-semibold">{opening ? '登錄期初' : '儲值'}</h2>
    <fieldset disabled={save.isPending} className="grid gap-3 sm:grid-cols-2">
      <Field label={`金額（${currency}）`}><input className={input} type="number" required min="0.01" max="99999999999999.99" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} /></Field>
      <Field label="憑證參考"><input className={input} required maxLength={200} value={reference} onChange={e => setReference(e.target.value)} /></Field>
      <Field label="備註"><textarea className={input} rows={2} maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></Field>
    </fieldset>
    {save.isError && <p role="alert" className="text-red-600 dark:text-red-300">{errorMessage(save.error, '入帳失敗，請核對後重試。')}</p>}
    {posted && <p role="status">儲值已入帳。</p>}
    <button className={button} type="submit" disabled={save.isPending}>{opening ? '確認期初入帳' : '確認儲值'}</button>
  </form>
}

function ReversalForm({ entry, onSaved, onCancel }: { entry: LedgerEntry; onSaved: () => void; onCancel: () => void }) {
  const [reference, setReference] = useState('')
  const [note, setNote] = useState('')
  const key = useInsuranceRequestKey()
  const save = useMutation({
    mutationFn: () => {
      const data = { reference: reference.trim(), note: note.trim() }
      return reverseInsuranceEntry(entry.id, { ...data, idempotency_key: key.forPayload(data) })
    },
    onSuccess: onSaved,
  })
  return <form className="space-y-3 rounded-lg bg-gray-50 p-3 dark:bg-gray-900" onSubmit={event => {
    event.preventDefault()
    if (!save.isPending && reference.trim() && note.trim()) save.mutate()
  }}>
    <p>請核對原分錄和財務憑證，再確認沖正。</p>
    <fieldset disabled={save.isPending} className="grid gap-3 sm:grid-cols-2">
      <Field label="沖正憑證"><input className={input} required maxLength={200} value={reference} onChange={e => setReference(e.target.value)} /></Field>
      <Field label="沖正原因"><input className={input} required maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></Field>
    </fieldset>
    {save.isError && <p role="alert" className="text-red-600 dark:text-red-300">{errorMessage(save.error, '沖正失敗，請核對後重試。')}</p>}
    <div className="flex gap-2">
      <button className={button} disabled={save.isPending} type="submit">確認沖正</button>
      <button className={secondary} disabled={save.isPending} type="button" onClick={onCancel}>取消</button>
    </div>
  </form>
}

function downloadReconciliation(data: Reconciliation, currency: string) {
  const header = '月份,幣別,期初,儲值,扣款,沖正淨額,期末,截止序號,確認時間'
  const values = [data.month, currency, data.opening, data.top_ups, data.deductions, data.reversals,
    data.closing, data.cutoff_sequence, data.confirmed_at].join(',')
  const url = URL.createObjectURL(new Blob([`\uFEFF${header}\r\n${values}\r\n`], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `insurance-reconciliation-${data.month}.csv`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function ReconciliationPanel({ tenant, month, currency, canConfirm, onSaved }: {
  tenant: string; month: string; currency: string; canConfirm: boolean; onSaved: () => void
}) {
  const [view, setView] = useState(false)
  const [statement, setStatement] = useState('')
  const [note, setNote] = useState('')
  const preview = useQuery({
    queryKey: ['admin', 'insurance-reconciliation', tenant, month],
    queryFn: () => fetchInsuranceReconciliation(month),
    enabled: view,
  })
  const save = useMutation({
    mutationFn: (cutoff_sequence: number) => confirmInsuranceReconciliation({ month, cutoff_sequence, statement_balance: statement, note: note.trim() }),
    onSuccess: onSaved,
  })
  const data = preview.data
  return <section className={section}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="font-semibold">{month} 月對帳</h2>
      <button type="button" className={secondary} disabled={preview.isFetching} onClick={() => { if (view) void preview.refetch(); else setView(true) }}>
        {view ? '重新核對' : '查看月對帳快照'}
      </button>
    </div>
    {preview.isFetching && <p role="status">載入對帳資料中…</p>}
    {preview.isError && <p role="alert">{errorMessage(preview.error, '月對帳載入失敗。')}</p>}
    {data && <>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
        {([['期初', data.opening], ['儲值', data.top_ups], ['扣款', data.deductions], ['沖正淨額', data.reversals], ['期末', data.closing]]).map(([label, value]) =>
          <div key={label}><dt>{label}</dt><dd className="font-semibold tabular-nums">{currency} {value}</dd></div>)}
      </dl>
      {data.confirmed_at && <div className="flex flex-wrap items-center gap-3">
        <p role="status">已由 {data.confirmed_by} 於 {new Date(data.confirmed_at).toLocaleString('zh-TW', taipeiTime)} 確認。{data.note}</p>
        <button type="button" className={secondary} onClick={() => downloadReconciliation(data, currency)}>下載對帳快照</button>
      </div>}
      {canConfirm && !data.confirmed_at && !save.isSuccess && <form className="space-y-3" onSubmit={event => {
        event.preventDefault()
        if (!save.isPending && statement !== '') save.mutate(data.cutoff_sequence)
      }}>
        <fieldset disabled={save.isPending} className="grid gap-3 sm:grid-cols-2">
          <Field label="對帳單期末餘額"><input className={input} type="number" required min="0" step="0.01" value={statement} onChange={e => setStatement(e.target.value)} /></Field>
          <Field label="對帳備註"><input className={input} maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></Field>
        </fieldset>
        {save.isError && <p role="alert" className="text-red-600 dark:text-red-300">{errorMessage(save.error, '確認失敗，請重新核對。')}</p>}
        <button className={button} type="submit" disabled={save.isPending}>確認月對帳</button>
      </form>}
    </>}
  </section>
}
