import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { isAxiosError } from 'axios'
import { BookOpen } from 'lucide-react'
import { Link } from 'react-router-dom'
import adminApi from '../api/axios'
import { vehicleGuidePage } from '../consoleNavigation'

type Option = { id: number; name: string }
type Resort = Option & { exempt: boolean; campuses: number[] }
type Vehicle = Option & { campus: number; plate: string; active: boolean; shared_campuses: number[] }
type VehicleConflict = { trip: number; purpose: string; driver: string; starts_at: string; ends_at: string; can_revoke: boolean }
type VehicleOption = { vehicle: number; conflicts: VehicleConflict[]; occupied_outside_scope: boolean }
type Expense = { id?: number; draftKey?: string; kind: string; amount_yen: string | number; note: string; receipt?: string; reimbursable?: boolean }
type Trip = {
  id: number; campus: number; campus_name: string; driver: string; vehicle_name: string; purpose: string; status: string
  starts_at: string; ends_at: string; resort: string; note: string; decision_note: string; owner: boolean; participants: string[]
  revoked: boolean; can_revoke: boolean; vehicle_options?: VehicleOption[]
  departure_km: string | null; return_km: string | null; departure_photo: string | null; return_photo: string | null
  amount_yen: number; amount_twd: number; expenses: Expense[]
  charges: { id: number; coach: string; amount_twd: number; balance: number; manual_due: boolean }[]
}
type Demand = { date: string; reservation__group__campus_id: number; reservation__group__campus__name: string; reservation__resort_id: number; reservation__resort__display_name: string }
type CalendarInterval = { starts_at: string; ends_at: string; resort?: string }
type VehicleCalendar = {
  from: string; to: string
  vehicles: (Option & { plate: string; occupancy: CalendarInterval[] })[]
}
type Desk = {
  campuses: Option[]; settings_campuses: Option[]; coaches: (Option & { campuses: number[] })[]; resorts: Resort[]; vehicles: Vehicle[]
  trips: Trip[]; eligible: boolean; coach_id: number | null; demands: Demand[]
  conflict_mode: 'manual_review' | 'block' | null
  vehicle_calendar: VehicleCalendar | null
  policy: { yen_per_km: string; yen_per_twd: string; payroll_day: number } | null
}
type Submit = (payload: object | FormData) => void
type Mode = 'coach' | 'review' | 'finance'

const purposes: Record<string, string> = { lesson: '課程用車', business: '其他公用', shopping: '生活採買（免費）', private: '私用' }
const statuses: Record<string, string> = {
  pending: '待核准', approved: '已排車', driving: '用車中', returned: '待審核',
  reviewed: '紀錄已審核', settled: '費用已核准', rejected: '未核准',
}
const kinds: Record<string, string> = { fuel: '加油', toll: '過路費', other: '車輛雜支' }
const input = 'min-h-10 w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 dark:border-gray-600 dark:bg-gray-900'
const card = 'space-y-3 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800'
const button = 'min-h-10 rounded-md bg-violet-700 px-3 text-sm font-medium text-white disabled:opacity-50'
const grid = 'grid gap-3 sm:grid-cols-2'

function Field({ title, children }: { title: string; children: ReactNode }) {
  return <label className="block text-sm"><span className="mb-1 block font-medium">{title}</span>{children}</label>
}

function Options({ items }: { items: Option[] }) {
  return <>{items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</>
}

function ids(form: FormData, name: string) {
  return form.getAll(name).map(Number)
}

const japanTime = new Intl.DateTimeFormat('zh-TW', { timeZone: 'Asia/Tokyo', dateStyle: 'short', timeStyle: 'short' })

function tripTime({ starts_at, ends_at }: { starts_at: string; ends_at: string }) {
  return japanTime.format(new Date(starts_at)) + ' ～ ' + japanTime.format(new Date(ends_at)) + '（日本時間）'
}

function CoachVehicleCalendar({ calendar }: { calendar: VehicleCalendar }) {
  return <section className={card} aria-labelledby="vehicle-calendar-title">
    <div>
      <h2 id="vehicle-calendar-title" className="text-lg font-semibold">車輛行事曆</h2>
      <p className="text-sm text-gray-600 dark:text-gray-300">{calendar.from} ～ {calendar.to}（日本時間）</p>
    </div>
    {calendar.vehicles.length === 0 && <p className="text-sm">所屬校區目前沒有車輛。</p>}
    <div className={grid}>
      {calendar.vehicles.map(vehicle => <section key={vehicle.id} className="min-w-0 space-y-2 rounded-md border border-gray-200 p-3 dark:border-gray-600">
        <h3 className="break-words font-medium">{vehicle.name} <span className="text-sm text-gray-600 dark:text-gray-300">{vehicle.plate}</span></h3>
        {vehicle.occupancy.length === 0
          ? <p className="text-sm text-gray-600 dark:text-gray-300">這段期間沒有可顯示的占用。</p>
          : <ul className="divide-y divide-gray-200 text-sm dark:divide-gray-600">
            {vehicle.occupancy.map((interval, index) => <li key={index} className="space-y-1 py-2">
              <p className="break-words font-medium">{interval.resort || '占用時段'}</p>
              <p className="text-gray-700 dark:text-gray-200">{tripTime(interval)}</p>
            </li>)}
          </ul>}
      </section>)}
    </div>
  </section>
}

function RequestForm({ data, staff, submit, busy, seed }: { data: Desk; staff: boolean; submit: Submit; busy: boolean; seed?: Demand }) {
  const [campus, setCampus] = useState(seed?.reservation__group__campus_id || data.campuses[0]?.id)
  const [purpose, setPurpose] = useState(staff ? 'lesson' : 'business')
  const [driver, setDriver] = useState(data.coach_id || 0)
  const resorts = data.resorts.filter(resort => !resort.exempt && campus && resort.campuses.includes(campus))
  const coaches = data.coaches.filter(coach => campus && coach.campuses.includes(campus))
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    submit({ action: 'request', campus, purpose, driver: staff ? Number(form.get('driver')) : undefined,
      resort: purpose === 'lesson' ? Number(form.get('resort')) : undefined, participants: ids(form, 'participants'),
      starts_at: String(form.get('start')) + ':00+09:00', ends_at: String(form.get('end')) + ':00+09:00', note: form.get('note') })
  }
  return <form className={card} onSubmit={save}>
    <h2 className="font-semibold">{staff ? '建立課程用車' : '借車申請'}</h2>
    <div className={grid}>
      <Field title="用車校區"><select className={input} required value={campus || ''} onChange={event => { setCampus(Number(event.target.value)); if (staff) setDriver(0) }}><Options items={data.campuses}/></select></Field>
      {!staff && <Field title="用車用途"><select className={input} value={purpose} onChange={event => setPurpose(event.target.value)}>{Object.entries(purposes).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>}
      {staff && <Field title="駕駛教練"><select className={input} name="driver" value={driver || ''} onChange={event => setDriver(Number(event.target.value))} required><option value="">請選擇</option><Options items={coaches}/></select></Field>}
      {purpose === 'lesson' && <Field title="上課雪場"><select className={input} key={campus} name="resort" required defaultValue={seed?.reservation__group__campus_id === campus ? seed?.reservation__resort_id : ''}><option value="">請選擇</option><Options items={resorts}/></select></Field>}
      <Field title="出發時間（日本時間）"><input className={input} name="start" type="datetime-local" defaultValue={seed ? seed.date + 'T08:00' : ''} required/></Field>
      <Field title="預計歸還（日本時間）"><input className={input} name="end" type="datetime-local" defaultValue={seed ? seed.date + 'T18:00' : ''} required/></Field>
    </div>
    <fieldset className="space-y-2"><legend className="text-sm font-medium">同行的領薪教練</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-2">{coaches.filter(coach => coach.id !== driver).map(coach => <label className="text-sm" key={coach.id}><input name="participants" type="checkbox" value={coach.id}/> {coach.name}</label>)}</div>
    </fieldset>
    {purpose === 'shopping' && <p className="text-sm">每週全校共用一次，至少兩位教練同行，全程免費。</p>}
    <Field title="用車說明"><input className={input} name="note" maxLength={500}/></Field>
    <button className={button} disabled={busy || !campus}>{staff ? '建立課程用車' : '送出借車申請'}</button>
  </form>
}

function TripRecordForm({ trip, submit, busy }: { trip: Trip; submit: Submit; busy: boolean }) {
  const departure = trip.status === 'approved'
  const [expenses, setExpenses] = useState<Expense[]>(trip.expenses)
  const change = (index: number, values: Partial<Expense>) => setExpenses(rows => rows.map((row, i) => i === index ? { ...row, ...values } : row))
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    form.set('action', departure ? 'depart' : 'return')
    form.set('trip', String(trip.id))
    if (!departure) form.set('expenses', JSON.stringify(expenses.map(({ id, kind, amount_yen, note }) => ({ id, kind, amount_yen, note }))))
    submit(form)
  }
  return <form className="space-y-3" onSubmit={save}>
    <div className={grid}>
      <Field title={departure ? '出發里程（公里）' : '歸還里程（公里）'}><input className={input} name="km" type="number" min="0" step="0.1" required defaultValue={departure ? '' : trip.return_km || ''}/></Field>
      <Field title={departure ? '出發里程照片' : '歸還里程照片'}><input className={input} name="photo" type="file" accept="image/jpeg,image/png,image/webp" required={departure || !trip.return_photo}/></Field>
    </div>
    {!departure && <fieldset className="space-y-3">
      <legend className="font-medium">支出與收據</legend>
      {expenses.map((item, index) => <div key={item.id ?? item.draftKey} className="grid items-end gap-2 rounded border p-2 sm:grid-cols-2">
        <Field title="支出類別"><select className={input} value={item.kind} onChange={event => change(index, { kind: event.target.value })}>{Object.entries(kinds).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
        <Field title="金額（日圓）"><input className={input} type="number" min="1" required value={item.amount_yen} onChange={event => change(index, { amount_yen: event.target.value })}/></Field>
        <Field title="收據照片"><input className={input} name={'receipt_' + index} type="file" accept="image/jpeg,image/png,image/webp" required={!item.receipt && (trip.purpose !== 'private' || item.kind === 'fuel')}/></Field>
        <Field title="支出備註"><input className={input} maxLength={200} value={item.note} onChange={event => change(index, { note: event.target.value })}/></Field>
        <button type="button" onClick={() => setExpenses(rows => rows.filter((_, i) => i !== index))}>移除此支出</button>
      </div>)}
      <button type="button" className="underline" disabled={expenses.length >= 20} onClick={() => {
        const draftKey = crypto.randomUUID()
        setExpenses(rows => [...rows, { draftKey, kind: 'fuel', amount_yen: '', note: '' }])
      }}>新增支出</button>
    </fieldset>}
    <button className={button} disabled={busy}>{departure ? '登記出車' : trip.status === 'driving' ? '送出還車紀錄' : '儲存修正'}</button>
  </form>
}

function FinanceSettings({ data, busy, submit }: { data: Desk; busy: boolean; submit: Submit }) {
  const [vehicleId, setVehicleId] = useState('')
  const vehicle = data.vehicles.find(item => item.id === Number(vehicleId))
  return <div className={grid}>
    <form className={card} onSubmit={event => {
      event.preventDefault()
      const form = new FormData(event.currentTarget)
      submit({ action: 'policy', yen_per_km: form.get('yen_per_km'), yen_per_twd: form.get('yen_per_twd'),
        payroll_day: form.get('payroll_day'), exempt_resorts: ids(form, 'exempt_resorts') })
    }}>
      <h2 className="font-semibold">費率與給薪日</h2>
      <Field title="每公里費率（日圓）"><input className={input} name="yen_per_km" type="number" min="0.01" step="0.01" defaultValue={data.policy?.yen_per_km} required/></Field>
      <Field title="1 台幣可換日圓"><input className={input} name="yen_per_twd" type="number" min="0.01" step="0.00000001" defaultValue={data.policy?.yen_per_twd} required/></Field>
      <Field title="次月給薪日"><input className={input} name="payroll_day" type="number" min="1" max="31" defaultValue={data.policy?.payroll_day} required/></Field>
      <fieldset><legend className="text-sm font-medium">不需排車的雪場</legend>{data.resorts.map(resort => <label key={resort.id} className="mr-3 inline-block text-sm"><input type="checkbox" name="exempt_resorts" value={resort.id} defaultChecked={resort.exempt}/> {resort.name}</label>)}</fieldset>
      <button className={button} disabled={busy}>儲存費率</button>
    </form>
    <section className={card}>
      <h2 className="font-semibold">車輛設定</h2>
      <Field title="選擇車輛"><select className={input} value={vehicleId} onChange={event => setVehicleId(event.target.value)}><option value="">新增車輛</option><Options items={data.vehicles.filter(item => data.campuses.some(campus => campus.id === item.campus))}/></select></Field>
      <form key={vehicleId} className="space-y-3" onSubmit={event => {
        event.preventDefault()
        const form = new FormData(event.currentTarget)
        submit({ action: 'vehicle', vehicle: vehicle?.id, campus: form.get('campus'), name: form.get('name'),
          plate: form.get('plate'), active: form.get('active') === 'on', shared_campuses: ids(form, 'shared_campuses') })
      }}>
        <Field title="所屬校區"><select className={input} name="campus" required defaultValue={vehicle?.campus}><Options items={vehicle ? data.campuses.filter(item => item.id === vehicle.campus) : data.campuses}/></select></Field>
        <Field title="車輛名稱"><input className={input} name="name" maxLength={80} defaultValue={vehicle?.name} required/></Field>
        <Field title="車牌"><input className={input} name="plate" maxLength={32} defaultValue={vehicle?.plate} required/></Field>
        <fieldset><legend className="text-sm font-medium">可共用校區</legend>{data.settings_campuses.map(campus => <label key={campus.id} className="mr-3 inline-block text-sm"><input type="checkbox" name="shared_campuses" value={campus.id} defaultChecked={vehicle?.shared_campuses.includes(campus.id)}/> {campus.name}</label>)}</fieldset>
        <label className="block text-sm"><input type="checkbox" name="active" defaultChecked={vehicle?.active ?? true}/> 啟用車輛</label>
        <button className={button} disabled={busy}>儲存車輛</button>
      </form>
    </section>
  </div>
}

function RevokePrivateTrip({ tripId, submit, busy }: { tripId: number; submit: Submit; busy: boolean }) {
  return <details className="space-y-2">
    <summary className="cursor-pointer text-sm font-medium underline">撤銷此私用</summary>
    <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
      event.preventDefault()
      const note = String(new FormData(event.currentTarget).get('note') ?? '').trim()
      if (!busy && note && [...note].length <= 500 && window.confirm(`確定撤銷私用行程 #${tripId}？車輛時段將立即釋放。`)) {
        submit({ action: 'revoke', trip: tripId, note })
      }
    }}>
      <Field title="撤銷原因（必填）"><textarea className={input} name="note" maxLength={500} required onChange={event => {
        event.currentTarget.setCustomValidity(event.currentTarget.value.trim() ? '' : '請填寫撤銷原因')
      }}/></Field>
      <button className={button} disabled={busy}>確認撤銷</button>
    </form>
  </details>
}

function VehicleAssignment({ trip, vehicles, submit, busy }: { trip: Trip; vehicles: Vehicle[]; submit: Submit; busy: boolean }) {
  const names = new Map(vehicles.map(vehicle => [vehicle.id, vehicle.name]))
  const options = trip.vehicle_options ?? []
  const occupied = options.filter(option => option.conflicts.length || option.occupied_outside_scope)
  const available = options.filter(option => !option.conflicts.length && !option.occupied_outside_scope)
  return <div className="space-y-2">
    <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
      event.preventDefault()
      submit({ action: 'approve', trip: trip.id, vehicle: new FormData(event.currentTarget).get('vehicle') })
    }}>
      <Field title="安排車輛"><select className={input} name="vehicle" required>
        <option value="">請選擇</option>
        {available.map(option => <option key={option.vehicle} value={option.vehicle}>{names.get(option.vehicle)}（可用）</option>)}
        {occupied.map(option => <option key={option.vehicle} value={option.vehicle} disabled>
          {names.get(option.vehicle)}（已占用{option.conflicts.length > 0 && ' · ' + [...new Set(option.conflicts.map(item => purposes[item.purpose]))].join('、')}）
        </option>)}
      </select></Field>
      <button className={button} disabled={busy || !available.length}>核准並排車</button>
    </form>
    {!available.length && <p className="text-sm">此時段沒有可用車輛。</p>}
    {occupied.length > 0 && <ul className="space-y-2" aria-label="車輛占用明細">
      {occupied.map(option => <li className="space-y-2 rounded border border-gray-200 p-2 text-sm dark:border-gray-600" key={option.vehicle}>
        <p className="font-medium">{names.get(option.vehicle)} · 已占用</p>
        {option.conflicts.map(conflict => <div className="space-y-1" key={conflict.trip}>
          <p>#{conflict.trip} · {purposes[conflict.purpose]} · {conflict.driver} · {tripTime(conflict)}</p>
          {conflict.can_revoke && <RevokePrivateTrip tripId={conflict.trip} submit={submit} busy={busy}/>}
        </div>)}
        {option.occupied_outside_scope && <p>此時段有其他校區的行程。</p>}
      </li>)}
    </ul>}
  </div>
}

function TripCard({ trip, data, mode, submit, busy }: { trip: Trip; data: Desk; mode: Mode; submit: Submit; busy: boolean }) {
  const approvedPrivate = trip.status === 'approved' && trip.purpose === 'private'
  const send = (action: string, extra: object = {}) => submit({ action, trip: trip.id, ...extra })
  return <article className={card} aria-label={'用車 #' + trip.id + ' ' + purposes[trip.purpose]}>
    <h3 className="font-semibold">#{trip.id} {purposes[trip.purpose]} · {trip.revoked ? '已撤銷' : statuses[trip.status]}</h3>
    <p className="text-sm">{[trip.campus_name, trip.driver, trip.vehicle_name, trip.resort].filter(Boolean).join(' · ')}</p>
    <p className="text-sm">{tripTime(trip)}</p>
    {trip.participants.length > 0 && <p className="text-sm">同行 {trip.participants.join('、')}</p>}
    {trip.note && <p className="break-words text-sm">{trip.note}</p>}
    {trip.revoked ? <div className="space-y-1 rounded border border-amber-300 p-2 text-sm">
      <p className="font-medium">此私用已被主管撤銷</p>
      <p className="break-words">撤銷原因 {trip.decision_note}</p>
    </div> : trip.decision_note && <p className="break-words text-sm">審核說明 {trip.decision_note}</p>}
    {trip.departure_km != null && <div className="flex flex-wrap gap-3 text-sm">
      <span>出發 {trip.departure_km} km</span>{trip.departure_photo && <a className="underline" href={trip.departure_photo} target="_blank" rel="noreferrer">出發照片</a>}
      {trip.return_km != null && <span>歸還 {trip.return_km} km</span>}{trip.return_photo && <a className="underline" href={trip.return_photo} target="_blank" rel="noreferrer">歸還照片</a>}
    </div>}
    {trip.expenses.map(expense => <p key={expense.id} className="text-sm">{kinds[expense.kind]} ¥{expense.amount_yen} · {expense.reimbursable ? '可核銷' : '自付'} {expense.note} {expense.receipt && <a className="underline" href={expense.receipt} target="_blank" rel="noreferrer">查看收據</a>}</p>)}
    {trip.amount_twd > 0 && mode !== 'coach' && <p className="font-medium">私用車資 ¥{trip.amount_yen}／NT${trip.amount_twd}</p>}
    {trip.charges.map(charge => <div key={charge.id} className="text-sm">
      <p>{charge.coach} · 分攤 NT${charge.amount_twd} · 未扣餘額 NT${charge.balance} {charge.manual_due && charge.balance > 0 && '· 待人工收款'}</p>
      {mode === 'finance' && charge.manual_due && charge.balance > 0 && <form className="flex items-end gap-2" onSubmit={event => {
        event.preventDefault()
        send('collect', { charge: charge.id, amount: new FormData(event.currentTarget).get('amount'), expected_balance: charge.balance })
      }}><Field title="實際收款（台幣）"><input className={input} name="amount" type="number" min="1" max={charge.balance} required/></Field><button className={button} disabled={busy}>記錄收款</button></form>}
    </div>)}
    {mode === 'coach' && trip.owner && ['approved', 'driving', 'returned', 'reviewed'].includes(trip.status) &&
      <TripRecordForm key={trip.status + '-' + trip.return_km} trip={trip} submit={submit} busy={busy}/>}
    {mode === 'review' && trip.status === 'pending' && <VehicleAssignment trip={trip} vehicles={data.vehicles} submit={submit} busy={busy}/>}
    {mode === 'review' && trip.can_revoke && <RevokePrivateTrip tripId={trip.id} submit={submit} busy={busy}/>}
    {mode === 'review' && (trip.status === 'pending' || (trip.status === 'approved' && !approvedPrivate)) && <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
      event.preventDefault()
      send('reject', { note: new FormData(event.currentTarget).get('note') })
    }}><Field title="未核准原因"><input className={input} name="note" maxLength={500} required/></Field><button className={button} disabled={busy}>不核准</button></form>}
    {mode === 'review' && trip.status === 'returned' && <button className={button} disabled={busy} onClick={() => send('review')}>通過用車審核</button>}
    {mode === 'finance' && trip.status === 'reviewed' && <button className={button} disabled={busy} onClick={() => send('settle')}>核准用車費用</button>}
  </article>
}

export default function VehiclePage({ mode }: { mode: Mode }) {
  const isCoach = mode === 'coach'
  const path = isCoach ? '/coach/vehicles/' : '/vehicles/'
  const [data, setData] = useState<Desk | null>(null)
  const [error, setError] = useState<{ text: string; source: 'load' | 'submit' } | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [revision, setRevision] = useState(0)
  const [range, setRange] = useState({ from: '', to: '' })
  const [seed, setSeed] = useState<Demand>()
  const calendar = isCoach ? data?.vehicle_calendar : null
  useEffect(() => {
    let activeController: AbortController | undefined
    const params = Object.fromEntries(Object.entries(range).filter(([, value]) => value))
    function load() {
      activeController?.abort()
      const controller = new AbortController()
      activeController = controller
      adminApi.get(path, { params, signal: controller.signal }).then((result: unknown) => {
        if (!controller.signal.aborted) setData((result as { data: Desk }).data)
      }).catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError({ text: errorText(cause), source: 'load' })
        if (isCoach) {
          setData(current => current?.vehicle_calendar ? { ...current, vehicle_calendar: null } : current)
        }
      })
    }

    load()
    if (!isCoach) return () => activeController?.abort()

    function refresh() {
      setError(current => current?.source === 'load' ? null : current)
      load()
    }
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('focus', refresh)
    return () => {
      activeController?.abort()
      document.removeEventListener('visibilitychange', onVisibilityChange)
      window.removeEventListener('focus', refresh)
    }
  }, [isCoach, path, range, revision])

  async function submit(payload: object | FormData) {
    setError(null)
    setMessage('')
    setBusy(true)
    try {
      await adminApi.post(path, payload, payload instanceof FormData ? { headers: { 'Content-Type': 'multipart/form-data' } } : undefined)
      setMessage('已儲存')
      setSeed(undefined)
      setRevision(value => value + 1)
    } catch (cause) {
      setError({ text: errorText(cause), source: 'submit' })
    } finally {
      setBusy(false)
    }
  }

  return <div className="space-y-4">
    <header className="flex flex-wrap items-center justify-between gap-2">
      <h1 className="text-2xl font-bold">{mode === 'coach' ? '我的用車' : mode === 'review' ? '車輛排班與用車審核' : '車輛費率與費用核准'}</h1>
      <Link
        to={`../../${vehicleGuidePage.path}#${mode}`}
        relative="path"
        className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-violet-200 bg-white px-3 text-sm font-medium text-violet-800 hover:bg-violet-50 dark:border-violet-800 dark:bg-gray-800 dark:text-violet-200 dark:hover:bg-violet-950"
      >
        <BookOpen aria-hidden="true" size={16} /> 使用說明
      </Link>
    </header>
    {error && <p role="alert" className="rounded border border-red-300 p-3 text-red-700 dark:text-red-300">{error.text}</p>}
    {isCoach && !data && error?.source === 'load' && <button type="button" className={button} onClick={() => {
      setError(null)
      setRevision(value => value + 1)
    }}>重新載入</button>}
    {message && <p role="status" className="text-green-700 dark:text-green-300">{message}</p>}
    {!data && !error && <p role="status">載入用車資料中…</p>}
    {data && <>
      {isCoach && !data.eligible && <p>{data.campuses?.length
        ? '請確認此教練有已啟用、且時薪大於 0 的計薪規則'
        : '此教練沒有啟用中的所屬校區'}</p>}
      {isCoach && data.eligible && <RequestForm key={'request-' + revision} data={data} staff={false} submit={submit} busy={busy}/>}
      {mode === 'finance' && <FinanceSettings key={revision} data={data} submit={submit} busy={busy}/>}
      {mode === 'review' && <>
        {data.conflict_mode && <p className="text-sm">目前衝突模式 <code>{data.conflict_mode}</code></p>}
        <section className={card}><h2 className="font-semibold">課程用車需求</h2>
          {data.demands.length === 0 && <p className="text-sm">選取期間沒有需排車的課程。</p>}
          {data.demands.map(demand => <div className="flex flex-wrap items-center justify-between gap-2 text-sm" key={[demand.date, demand.reservation__group__campus_id, demand.reservation__resort_id].join('-')}>
            <span>{demand.date} · {demand.reservation__group__campus__name} · {demand.reservation__resort__display_name}</span>
            <button type="button" className="underline" onClick={() => setSeed(demand)}>帶入排車</button>
          </div>)}
        </section>
        <RequestForm key={[revision, seed?.date, seed?.reservation__resort_id, seed?.reservation__group__campus_id].join('-')} data={data} seed={seed} staff submit={submit} busy={busy}/>
      </>}
      <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
        event.preventDefault()
        const values = new FormData(event.currentTarget)
        setError(null)
        setRange({ from: String(values.get('from')), to: String(values.get('to')) })
      }}>
        <Field title="查詢起日"><input className={input} name="from" type="date"/></Field>
        <Field title="查詢迄日"><input className={input} name="to" type="date"/></Field>
        <button className={button}>{calendar ? '查詢行事曆與用車紀錄' : '查詢用車紀錄'}</button>
      </form>
      {calendar && <CoachVehicleCalendar calendar={calendar}/>}
      <section className="space-y-3" aria-label="用車紀錄">
        <h2 className="text-lg font-semibold">用車紀錄</h2>
        {data.trips.length === 0 && <p className="text-sm">目前沒有用車紀錄。</p>}
        {[...data.trips].sort((a, b) => mode === 'review' ? Number(b.status === 'pending' && b.purpose === 'lesson') - Number(a.status === 'pending' && a.purpose === 'lesson') : 0)
          .map(trip => <TripCard key={trip.id + '-' + revision} trip={trip} data={data} mode={mode} submit={submit} busy={busy}/>)}
      </section>
    </>}
  </div>
}

function errorText(error: unknown) {
  if (!isAxiosError(error) || !error.response?.data) return '用車操作失敗，請重試。'
  return Object.values(error.response.data).flat().filter(value => typeof value === 'string').join('、') || '用車操作失敗，請重試。'
}
