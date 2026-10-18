import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, AlertCircle, CreditCard, Plus, Pencil, Trash2, X } from 'lucide-react'
import { fetchPaymentSettings, updatePaymentSettings, fetchPaymentAccounts, createPaymentAccount, updatePaymentAccount, deletePaymentAccount, type PaymentAccount, type PaymentSettings } from '../api/paymentSettings'
import { fetchCampuses } from '../api/campuses'
import { fetchAllAccessibleResorts } from '../api/resorts'
import { fetchAdminMe } from '../api/auth'
import { useNotification } from '../context'

const PRIMARY = '#8b5cf6'
const QUERY_KEY = ['admin', 'payment-settings']
const EMPTY_ACCOUNT = { name: '', bank_name: '', bank_branch: '', account_number: '', account_holder: '', overseas_details: '', campus_ids: [] as number[], resort_ids: [] as number[], is_default: false, is_active: true, display_order: 0 }

const EMPTY: PaymentSettings = {
  bank_name: '',
  bank_branch: '',
  bank_account_number: '',
  bank_account_holder: '',
  messenger_options: ['LINE', 'WhatsApp', 'WeChat'],
  referral_source_options: [
    '朋友介紹',
    '舊生推薦',
    'Instagram',
    'Facebook',
    'Google 搜尋',
    '小紅書',
    'Dcard / PTT',
    'YouTube',
    '講座 / 限時活動',
    '抽獎活動',
    '其他',
  ],
}

const splitOptions = (value: string) =>
  value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)

export default function PaymentSettingsPage() {
  const notify = useNotification()
  const qc = useQueryClient()
  const [form, setForm] = useState<PaymentSettings>(EMPTY)
  const [messengerText, setMessengerText] = useState(EMPTY.messenger_options.join('\n'))
  const [referralSourceText, setReferralSourceText] = useState(EMPTY.referral_source_options.join('\n'))
  const { data: adminMe } = useQuery({ queryKey: ['admin', 'me'], queryFn: fetchAdminMe })
  const canManageCompany = !!adminMe?.user?.can_view_all_campuses

  const { data, isLoading, error } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchPaymentSettings,
  })

  useEffect(() => {
    if (data) {
      const nextForm = {
        ...EMPTY,
        ...data,
        messenger_options: data.messenger_options?.length ? data.messenger_options : EMPTY.messenger_options,
        referral_source_options: data.referral_source_options?.length
          ? data.referral_source_options
          : EMPTY.referral_source_options,
      }
      setForm(nextForm)
      setMessengerText(nextForm.messenger_options.join('\n'))
      setReferralSourceText(nextForm.referral_source_options.join('\n'))
    }
  }, [data])

  const saveMutation = useMutation({
    mutationFn: (payload: PaymentSettings) => updatePaymentSettings(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEY })
      notify.success('付款設定已更新')
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || '更新失敗'),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    saveMutation.mutate({
      ...form,
      messenger_options: splitOptions(messengerText),
      referral_source_options: splitOptions(referralSourceText),
    })
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">付款設定</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">先設定各校區收款帳戶；找不到適用帳戶時，才使用下方舊版預設帳戶。</p>
      </div>

      <PaymentAccountsSection canManageCompany={canManageCompany} allowedCampusIds={adminMe?.user?.assigned_campus_ids || []} />

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} />
        </div>
      ) : error ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-8 text-center">
          <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
          <p className="text-sm text-red-600 dark:text-red-400">載入失敗</p>
        </div>
      ) : (
        <form
          onSubmit={handleSubmit}
          className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 space-y-5"
        >
          {!canManageCompany && <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/20 dark:text-amber-200">全公司預設收款資訊僅供查看；請在下方建立自己校區的收款帳戶。</p>}
          <fieldset disabled={!canManageCompany} className={`space-y-5 ${!canManageCompany ? 'opacity-60' : ''}`}>
          <div className="flex items-center gap-2 mb-2">
            <CreditCard size={18} style={{ color: PRIMARY }} />
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">舊版預設收款帳戶（備用）</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="銀行名稱" value={form.bank_name} placeholder="例：台灣銀行"
              onChange={(v) => setForm({ ...form, bank_name: v })} />
            <Field label="分行名稱" value={form.bank_branch} placeholder="例：信義分行"
              onChange={(v) => setForm({ ...form, bank_branch: v })} />
            <Field label="銀行帳號" value={form.bank_account_number} placeholder="例：123-456-789012"
              onChange={(v) => setForm({ ...form, bank_account_number: v })} />
            <Field label="戶名" value={form.bank_account_holder} placeholder="例：滑雪預約股份有限公司"
              onChange={(v) => setForm({ ...form, bank_account_holder: v })} />
          </div>

          <div className="pt-5 border-t border-gray-200 dark:border-gray-700 space-y-4">
            <div>
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">訂單表單選項</h2>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                每行一個選項，會顯示在預約最後確認資料的下拉選單。
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <TextAreaField
                label="通訊軟體"
                value={messengerText}
                placeholder={'LINE\nWhatsApp\nWeChat'}
                onChange={setMessengerText}
              />
              <TextAreaField
                label="從哪裡得知 / 活動來源"
                value={referralSourceText}
                placeholder={'朋友介紹\n舊生推薦\nInstagram\n其他'}
                onChange={setReferralSourceText}
              />
            </div>
          </div>

          <div className="pt-3 border-t border-gray-200 dark:border-gray-700 flex justify-end">
            <button
              type="submit"
              disabled={saveMutation.isPending}
              className="px-5 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 flex items-center gap-2 disabled:opacity-50"
              style={{ backgroundColor: PRIMARY }}
            >
              {saveMutation.isPending && <Loader2 size={14} className="animate-spin" />}
              儲存變更
            </button>
          </div>
          </fieldset>
        </form>
      )}
    </div>
  )
}

function PaymentAccountsSection({ canManageCompany, allowedCampusIds }: { canManageCompany: boolean; allowedCampusIds: number[] }) {
  const qc = useQueryClient()
  const notify = useNotification()
  const accountsQuery = useQuery({ queryKey: ['admin', 'payment-accounts'], queryFn: fetchPaymentAccounts })
  const campusesQuery = useQuery({ queryKey: ['admin', 'campuses'], queryFn: fetchCampuses })
  const resortsQuery = useQuery({ queryKey: ['admin', 'resorts', 'all-accessible'], queryFn: fetchAllAccessibleResorts })
  const accounts = accountsQuery.data ?? []
  const campuses = campusesQuery.data ?? []
  const resorts = resortsQuery.data ?? []
  const isLoadingAccounts = accountsQuery.isPending || campusesQuery.isPending || resortsQuery.isPending
  const hasAccountsError = accountsQuery.isError || campusesQuery.isError || resortsQuery.isError
  const [open, setOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleting, setDeleting] = useState<{ id: number; name: string } | null>(null)
  const [form, setForm] = useState(EMPTY_ACCOUNT)
  const closeForm = () => { setOpen(false); setEditingId(null); setForm({ ...EMPTY_ACCOUNT }) }
  const save = useMutation({
    mutationFn: () => editingId === null ? createPaymentAccount(form) : updatePaymentAccount(editingId, form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'payment-accounts'] }); notify.success(editingId === null ? '收款帳戶已建立' : '收款帳戶已更新'); closeForm() },
    onError: (e: any) => notify.error(e?.response?.data?.msg || (editingId === null ? '建立失敗' : '更新失敗')),
  })
  const remove = useMutation({ mutationFn: deletePaymentAccount, onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'payment-accounts'] }); setDeleting(null); notify.success('收款帳戶已刪除') }, onError: (e: any) => notify.error(e?.response?.data?.msg || '刪除失敗') })
  const edit = (account: PaymentAccount) => {
    setEditingId(account.id)
    setForm({
      name: account.name,
      bank_name: account.bank_name,
      bank_branch: account.bank_branch,
      account_number: account.account_number,
      account_holder: account.account_holder,
      overseas_details: account.overseas_details,
      campus_ids: [...account.campus_ids],
      resort_ids: [...account.resort_ids],
      is_default: account.is_default,
      is_active: account.is_active,
      display_order: account.display_order,
    })
    setOpen(true)
  }
  const toggle = (list: number[], id: number) => list.includes(id) ? list.filter(v => v !== id) : [...list, id]
  const scopedResorts = resorts.filter(resort => campuses.some(campus =>
    form.campus_ids.includes(campus.id) && campus.resort_ids.includes(resort.id)))
  const bankDetailsReady = [form.bank_name, form.bank_branch, form.account_number, form.account_holder].every(value => value.trim().length > 0)
  const toggleCampus = (id: number) => {
    const campusIds = toggle(form.campus_ids, id)
    const validResortIds = new Set(campuses.filter(campus => campusIds.includes(campus.id)).flatMap(campus => campus.resort_ids))
    setForm({ ...form, campus_ids: campusIds, resort_ids: form.resort_ids.filter(resortId => validResortIds.has(resortId)) })
  }
  return <>
    <section className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="font-semibold text-gray-900 dark:text-white">多校區收款帳戶</h2><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">優先使用符合校區、雪場的帳戶；總部可不選校區，作為全公司共用帳戶。</p></div>{!isLoadingAccounts && !hasAccountsError && <button onClick={() => { setEditingId(null); setForm({ ...EMPTY_ACCOUNT }); setOpen(true) }} className="flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-white" style={{ backgroundColor: PRIMARY }}><Plus size={15} />新增帳戶</button>}</div>
      {hasAccountsError ? <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300"><p>收款帳戶或適用校區資料載入失敗，請重新載入後再編輯。</p><button type="button" onClick={() => { closeForm(); setDeleting(null); void Promise.all([accountsQuery.refetch(), campusesQuery.refetch(), resortsQuery.refetch()]) }} className="mt-3 rounded-lg border border-red-300 px-3 py-2 font-semibold hover:bg-red-100 dark:border-red-700 dark:hover:bg-red-900/30">重新載入</button></div> : isLoadingAccounts ? <div role="status" className="mt-5 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400"><Loader2 size={16} className="animate-spin" />正在載入收款帳戶…</div> : <div className="mt-5 grid gap-3 md:grid-cols-2">{accounts.map(a => {
        const canManage = canManageCompany || (a.campus_ids.length > 0 && a.campus_ids.every(id => allowedCampusIds.includes(id)))
        const hasOtherCampuses = a.campus_ids.some(id => !campuses.some(c => c.id === id))
        const accountReady = [a.bank_name, a.bank_branch, a.account_number, a.account_holder].every(value => value.trim().length > 0)
        return <div key={a.id} className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0"><b className="text-gray-900 dark:text-white">{a.name}</b>{!a.is_active && <span className="ml-2 rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300">未啟用</span>}{a.is_active && a.is_default && <span className="ml-2 rounded bg-violet-100 px-2 py-0.5 text-xs text-violet-700 dark:bg-violet-900/30 dark:text-violet-300">優先</span>}<p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{a.bank_name} {a.bank_branch}</p><p className="break-all font-mono text-sm text-gray-900 dark:text-white">{a.account_number}</p><p className="text-xs text-gray-500 dark:text-gray-400">戶名：{a.account_holder || '未設定'}</p></div>
            {canManage && <div className="flex shrink-0 gap-1"><button aria-label={`編輯帳戶 ${a.name}`} onClick={() => edit(a)} className="rounded-lg p-2 text-violet-500 hover:bg-violet-50 dark:hover:bg-violet-900/20"><Pencil size={16} /></button><button aria-label={`刪除帳戶 ${a.name}`} onClick={() => setDeleting({ id: a.id, name: a.name })} className="rounded-lg p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"><Trash2 size={16} /></button></div>}
          </div>
          {!a.is_active ? <p className="mt-2 rounded-lg bg-gray-50 px-3 py-2 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">此帳戶尚未啟用，付款頁不會顯示。編輯並補齊資料後即可啟用。</p> : !accountReady && <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800 dark:bg-amber-900/20 dark:text-amber-200">銀行資料未填齊，付款頁不會提供此帳戶的匯款選項。</p>}
          <p className="mt-3 border-t border-gray-100 pt-3 text-xs text-gray-500 dark:border-gray-700 dark:text-gray-400">校區：{campuses.filter(c => a.campus_ids.includes(c.id)).map(c => c.name).join('、') || '全公司共用'}{hasOtherCampuses ? '（另含其他校區，由總部管理）' : ''} · 雪場：{resorts.filter(r => a.resort_ids.includes(r.id)).map(r => r.display_name).join('、') || '全部'}</p>
        </div>
      })}{!accounts.length && <p className="py-8 text-center text-sm text-gray-400 md:col-span-2">尚無分流帳戶，付款頁目前使用下方舊版預設帳戶。</p>}</div>}
    </section>

    {!hasAccountsError && !isLoadingAccounts && open && <div className="fixed inset-0 z-[70] flex items-end justify-center bg-black/50 p-0 animate-fadeIn md:items-center md:p-4" onMouseDown={event => event.target === event.currentTarget && closeForm()}>
      <div className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl bg-white shadow-xl dark:bg-gray-800 md:max-w-2xl md:rounded-2xl">
        <div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}><div><h3 className="text-lg font-semibold">{editingId === null ? '新增收款帳戶' : '編輯收款帳戶'}</h3><p className="mt-0.5 text-xs text-white/80">設定銀行資料與適用範圍</p></div><button onClick={closeForm} aria-label="關閉" className="rounded-lg p-1 text-white/80 hover:bg-white/10 hover:text-white"><X size={20} /></button></div>
        <div className="space-y-5 overflow-y-auto p-6">
          <div className="grid gap-4 sm:grid-cols-2"><Field label="帳戶辨識名稱 *" value={form.name} onChange={v => setForm({ ...form, name: v })} /><Field label="銀行 *" value={form.bank_name} onChange={v => setForm({ ...form, bank_name: v })} /><Field label="分行 *" value={form.bank_branch} onChange={v => setForm({ ...form, bank_branch: v })} /><Field label="帳號 *" value={form.account_number} onChange={v => setForm({ ...form, account_number: v })} /><Field label="戶名 *" value={form.account_holder} onChange={v => setForm({ ...form, account_holder: v })} /><Field label="海外匯款資料" value={form.overseas_details} onChange={v => setForm({ ...form, overseas_details: v })} /></div>
          <p className="text-xs text-gray-500 dark:text-gray-400">* 啟用時須填齊銀行、分行、帳號與戶名；尚未備齊可先存為未啟用草稿。</p>
          <ChoiceGrid title={canManageCompany ? '適用校區（不選代表全公司共用）' : '適用校區（至少選一個）'} items={campuses.filter(c => c.is_active || form.campus_ids.includes(c.id)).map(c => ({ id: c.id, label: c.is_active ? c.name : `${c.name}（已停用）` }))} selected={form.campus_ids} onToggle={toggleCampus} />
          <ChoiceGrid title="適用雪場（不選代表校區下全部雪場）" items={scopedResorts.map(r => ({ id: r.id, label: r.display_name }))} selected={form.resort_ids} onToggle={id => setForm({ ...form, resort_ids: toggle(form.resort_ids, id) })} />
          {!form.campus_ids.length && <p className="text-xs text-gray-500 dark:text-gray-400">{canManageCompany ? '目前設定為全公司共用帳戶；若要指定雪場，請先選擇校區。' : '請先選擇校區，才會顯示該校區的雪場。'}</p>}
          <label className="flex cursor-pointer items-center gap-3 rounded-lg bg-gray-50 p-3 text-sm text-gray-700 dark:bg-gray-700 dark:text-gray-200"><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} className="h-4 w-4" style={{ accentColor: PRIMARY }} /><span><span className="block font-medium">啟用此帳戶</span><span className="block text-xs text-gray-500 dark:text-gray-400">未啟用的帳戶不會顯示在付款頁。</span></span></label>
          <label className="flex cursor-pointer items-center gap-3 rounded-lg bg-gray-50 p-3 text-sm text-gray-700 dark:bg-gray-700 dark:text-gray-200"><input type="checkbox" checked={form.is_default} onChange={e => setForm({ ...form, is_default: e.target.checked })} className="h-4 w-4" style={{ accentColor: PRIMARY }} />設為優先帳戶</label>
        </div>
        <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700"><button onClick={closeForm} className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">取消</button><button disabled={!form.name.trim() || (form.is_active && !bankDetailsReady) || (!canManageCompany && !form.campus_ids.length) || save.isPending} onClick={() => save.mutate()} className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-40" style={{ backgroundColor: PRIMARY }}>{save.isPending && <Loader2 size={14} className="animate-spin" />}{form.is_active ? (editingId === null ? '儲存並啟用' : '儲存修改') : (editingId === null ? '儲存草稿' : '儲存為未啟用')}</button></div>
      </div>
    </div>}

    {!hasAccountsError && !isLoadingAccounts && deleting && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 p-4 animate-fadeIn"><div className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-xl dark:bg-gray-800"><div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, #7c3aed 100%)` }}><h3 className="text-lg font-semibold">刪除收款帳戶</h3><button onClick={() => setDeleting(null)} aria-label="關閉" className="rounded-lg p-1 text-white/80 hover:bg-white/10 hover:text-white"><X size={18} /></button></div><div className="p-6 text-sm text-gray-700 dark:text-gray-300">確定刪除「<b className="text-gray-900 dark:text-white">{deleting.name}</b>」？付款頁將不再顯示這組帳戶。</div><div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700"><button onClick={() => setDeleting(null)} className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">取消</button><button onClick={() => remove.mutate(deleting.id)} disabled={remove.isPending} className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">{remove.isPending && <Loader2 size={14} className="animate-spin" />}確認刪除</button></div></div></div>}
  </>
}

function ChoiceGrid({ title, items, selected, onToggle }: { title: string; items: { id: number; label: string }[]; selected: number[]; onToggle: (id: number) => void }) {
  return <div><p className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-300">{title}</p><div className="flex flex-wrap gap-2">{items.map(item => <label key={item.id} className={`cursor-pointer rounded-lg border px-3 py-2 text-sm transition-colors ${selected.includes(item.id) ? 'border-violet-400 bg-violet-50 text-violet-700 dark:border-violet-500 dark:bg-violet-900/30 dark:text-violet-300' : 'border-gray-200 bg-white text-gray-700 hover:border-violet-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200'}`}><input className="sr-only" type="checkbox" checked={selected.includes(item.id)} onChange={() => onToggle(item.id)} />{item.label}</label>)}</div></div>
}

function TextAreaField({ label, value, placeholder, onChange }: {
  label: string
  value: string
  placeholder?: string
  onChange: (v: string) => void
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
      <textarea
        value={value}
        placeholder={placeholder}
        rows={7}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
      />
    </div>
  )
}

function Field({ label, value, placeholder, onChange }: {
  label: string
  value: string
  placeholder?: string
  onChange: (v: string) => void
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm dark:text-white focus:outline-none focus:ring-2 focus:ring-[#8b5cf6]/30"
      />
    </div>
  )
}
