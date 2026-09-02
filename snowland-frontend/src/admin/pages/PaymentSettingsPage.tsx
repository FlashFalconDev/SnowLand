import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, AlertCircle, CreditCard } from 'lucide-react'
import { fetchPaymentSettings, updatePaymentSettings, type PaymentSettings } from '../api/paymentSettings'
import { useNotification } from '../context'

const PRIMARY = '#8b5cf6'
const QUERY_KEY = ['admin', 'payment-settings']

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
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">付款設定</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">學員預約完成後將顯示這組銀行帳號讓對方匯款</p>
      </div>

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
          <div className="flex items-center gap-2 mb-2">
            <CreditCard size={18} style={{ color: PRIMARY }} />
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">銀行收款資訊</h2>
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
        </form>
      )}
    </div>
  )
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
