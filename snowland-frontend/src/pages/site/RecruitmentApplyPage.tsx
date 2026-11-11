import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import SiteFooter from '@/components/site/SiteFooter'
import SiteHeader from '@/components/site/SiteHeader'
import RecruitmentFields from '@/components/site/RecruitmentFields'
import { recruitmentError, type RecruitmentSettings } from '@/components/site/recruitmentForm'
import { schoolBookingApiPath } from '@/utils/tenant'
import { useSiteLink } from '@/hooks/useSiteBasePath'

const formPath = () => schoolBookingApiPath('/recruitment/')

export default function RecruitmentApplyPage() {
  const joinUrl = useSiteLink('/join-us')
  const [config, setConfig] = useState<RecruitmentSettings | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [reload, setReload] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [fields, setFields] = useState<Record<string, string>>({})
  const [outdated, setOutdated] = useState(false)
  const [reference, setReference] = useState('')
  const attempt = useRef('')
  const inFlight = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    fetch(formPath(), {signal: controller.signal, cache: 'no-store'})
      .then(response => {
        if (!response.ok) throw new Error()
        return response.json()
      })
      .then(result => setConfig(result))
      .catch(() => { if (!controller.signal.aborted) setLoadFailed(true) })
    return () => controller.abort()
  }, [reload])

  function changeAnswer(event: FormEvent<HTMLFormElement>) {
    attempt.current = ''
    const id = (event.target as HTMLInputElement).name?.replace(/^(answer|file)_/, '')
    if (!id || !fields[id]) return
    const remaining = {...fields}
    delete remaining[id]
    setFields(remaining)
    if (!Object.keys(remaining).length) setError('')
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!config?.enabled || inFlight.current || outdated) return
    const values = new FormData(event.currentTarget)
    const body = new FormData()
    const answers: Record<string, unknown> = {}
    for (const field of config.fields) {
      if (field.type === 'file') {
        const key = `file_${field.id}`
        const file = values.get(key)
        if (file instanceof File && file.name) body.set(key, file)
      } else {
        const key = `answer_${field.id}`
        answers[field.id] = field.type === 'multiple' ? values.getAll(key) : values.get(key)
      }
    }
    attempt.current ||= crypto.randomUUID()
    body.set('submission_id', attempt.current)
    body.set('revision', config.revision)
    body.set('answers', JSON.stringify(answers))
    inFlight.current = true
    setBusy(true)
    setError('')
    setFields({})
    try {
      const response = await fetch(formPath(), {method: 'POST', body})
      const data = await response.json()
      if (!response.ok) {
        setFields(data.fields || {})
        setOutdated(data.reload === true)
        setError(data.fields ? '請檢查標記的欄位。' : recruitmentError({response: {data, status: response.status}}, '目前無法送出，請稍後再試。'))
      } else if (typeof data.reference === 'string') {
        setReference(data.reference)
      } else {
        throw new Error()
      }
    } catch {
      setError('目前無法確認是否送出，資料已保留，可以重試。')
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }

  function reloadForm() {
    setConfig(null)
    setLoadFailed(false)
    setOutdated(false)
    setError('')
    setFields({})
    attempt.current = ''
    setReload(value => value + 1)
  }

  return <div className="flex min-h-screen flex-col bg-[#f7f8fa] text-slate-900">
    <SiteHeader forceDarkText forceLogoColor />
    <main className="mx-auto w-full max-w-2xl flex-1 px-5 pb-20 pt-28">
      <Link to={joinUrl} className="text-sm font-medium text-[#2b5f8f] underline underline-offset-4">返回成為教練</Link>
      <h1 className="mb-6 mt-3 text-3xl font-semibold">教練招募申請</h1>
      <div className="rounded-md border border-slate-200 bg-white p-5 sm:p-8">
        {loadFailed ? <div role="alert" className="space-y-2 text-sm">
          <p>招募表單暫時無法載入。</p><button type="button" className="underline" onClick={reloadForm}>重新載入</button>
        </div> : !config ? <p role="status">表單載入中…</p>
        : !config.enabled ? <p>目前未開放站內應徵，請返回招募頁查看最新資訊。</p>
        : reference ? <div role="status" className="space-y-2">
          <h2 className="font-semibold">已收到您的應徵資料</h2>
          <p className="break-all text-sm text-slate-600">送件編號 {reference}</p>
        </div> : <form className="space-y-6" onSubmit={submit} onChange={changeAnswer} aria-busy={busy}>
          <fieldset disabled={busy || outdated}>
            <RecruitmentFields fields={config.fields} errors={fields} />
          </fieldset>
          {error && <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          {outdated ? <button type="button" className="text-sm underline" onClick={reloadForm}>重新載入表單</button>
          : <button type="submit" disabled={busy} className="min-h-11 rounded-full bg-[#2b5f8f] px-6 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {busy ? '送出中…' : '送出應徵資料'}
          </button>}
        </form>}
      </div>
    </main>
    <SiteFooter />
  </div>
}
