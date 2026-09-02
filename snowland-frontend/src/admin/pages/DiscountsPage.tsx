/**
 * 優惠折扣管理
 */
import { useState, type FormEvent, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Edit, Loader2, Plus, Trash2, X } from 'lucide-react'
import { useNotification } from '../context'
import {
  createDiscountCode,
  deleteDiscountCode,
  fetchDiscountCodes,
  updateDiscountCode,
  type DiscountCode,
  type DiscountCodeWriteData,
  type DiscountScope,
  type DiscountType,
  type AmountApplyMode,
} from '../api/discounts'

const PRIMARY = '#8b5cf6'
const DISCOUNTS_KEY = ['admin', 'discount-codes']
const inputClass = 'w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-[#8b5cf6] focus:ring-2 focus:ring-[#8b5cf6]/15 dark:border-gray-700 dark:bg-gray-800 dark:text-white'

const emptyForm: DiscountCodeWriteData = {
  code: '',
  name: '',
  description: '',
  discount_type: 'amount',
  amount_apply_mode: 'order',
  discount_value: 500,
  max_discount_amount: null,
  min_order_amount: 0,
  apply_scope: 'all',
  require_multiple_items: false,
  can_combine: false,
  is_auto_apply: false,
  new_customer_only: false,
  usage_limit: null,
  start_at: null,
  end_at: null,
  is_active: true,
}

export default function DiscountsPage() {
  const notify = useNotification()
  const qc = useQueryClient()
  const [editing, setEditing] = useState<DiscountCode | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const { data: discounts = [], isLoading, error } = useQuery({
    queryKey: DISCOUNTS_KEY,
    queryFn: fetchDiscountCodes,
  })

  const refresh = () => qc.invalidateQueries({ queryKey: DISCOUNTS_KEY })

  const createMutation = useMutation({
    mutationFn: createDiscountCode,
    onSuccess: () => {
      notify.success('已新增折扣碼')
      refresh()
      setDrawerOpen(false)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || e.response?.data?.detail || '新增失敗'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: DiscountCodeWriteData }) => updateDiscountCode(id, data),
    onSuccess: () => {
      notify.success('已更新折扣碼')
      refresh()
      setDrawerOpen(false)
      setEditing(null)
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || e.response?.data?.detail || '更新失敗'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteDiscountCode,
    onSuccess: () => {
      notify.success('已刪除折扣碼')
      refresh()
    },
    onError: (e: any) => notify.error(e.response?.data?.msg || e.response?.data?.detail || '刪除失敗'),
  })

  const openCreate = () => {
    setEditing(null)
    setDrawerOpen(true)
  }

  const openEdit = (discount: DiscountCode) => {
    setEditing(discount)
    setDrawerOpen(true)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={32} className="animate-spin" style={{ color: PRIMARY }} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
        <AlertCircle size={18} className="mr-2 inline" />
        無法載入折扣資料
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">優惠折扣</h1>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white"
          style={{ backgroundColor: PRIMARY }}
        >
          <Plus size={16} />新增折扣碼
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
            <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:bg-gray-900/40 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">折扣碼</th>
                <th className="px-4 py-3">折扣</th>
                <th className="px-4 py-3">適用範圍</th>
                <th className="px-4 py-3">有效時間</th>
                <th className="px-4 py-3">使用量</th>
                <th className="px-4 py-3">狀態</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {discounts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-500 dark:text-gray-400">
                    尚未建立任何折扣碼
                  </td>
                </tr>
              ) : discounts.map((discount) => (
                <tr key={discount.id} className="text-gray-700 dark:text-gray-200">
                  <td className="px-4 py-4">
                    <div className="font-semibold text-gray-900 dark:text-white">{discount.code}</div>
                    <div className="mt-1 text-xs text-gray-500">{discount.name || '未命名活動'}</div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="font-medium">
                      {discount.discount_type === 'percent' ? `${discount.discount_value}%` : `NT$ ${discount.discount_value.toLocaleString()}`}
                    </div>
                    {discount.discount_type === 'amount' && (
                      <div className="mt-1 text-xs text-gray-500">{discount.amount_apply_mode_label}</div>
                    )}
                    {discount.min_order_amount > 0 && (
                      <div className="mt-1 text-xs text-gray-500">滿 NT$ {discount.min_order_amount.toLocaleString()}</div>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <div>{discount.apply_scope_label}</div>
                    {discount.is_auto_apply && <div className="mt-1 text-xs text-emerald-600">自動套用</div>}
                    {discount.new_customer_only && <div className="mt-1 text-xs text-blue-600">限新客</div>}
                    {discount.require_multiple_items && <div className="mt-1 text-xs text-purple-600">需搭配多項</div>}
                  </td>
                  <td className="px-4 py-4 text-xs">
                    <div>{formatDateTime(discount.start_at) || '不限開始'}</div>
                    <div className="mt-1">{formatDateTime(discount.end_at) || '不限結束'}</div>
                  </td>
                  <td className="px-4 py-4">
                    {discount.used_count} / {discount.usage_limit ?? '不限'}
                  </td>
                  <td className="px-4 py-4">
                    <StatusBadge discount={discount} />
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => {
                          updateMutation.mutate({
                            id: discount.id,
                            data: { ...toForm(discount), is_active: !discount.is_active },
                          })
                        }}
                        className={`rounded-lg px-3 py-2 text-xs font-semibold transition ${
                          discount.is_active
                            ? 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200'
                            : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-200'
                        }`}
                        title={discount.is_active ? '點擊後此優惠不會套用到前台' : '點擊後此優惠才會套用到前台'}
                      >
                        {discount.is_active ? '點我停用' : '點我啟用'}
                      </button>
                      <button
                        onClick={() => openEdit(discount)}
                        className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:hover:bg-gray-700 dark:hover:text-gray-200"
                        title="編輯"
                      >
                        <Edit size={15} />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`確定刪除折扣碼「${discount.code}」？`)) {
                            deleteMutation.mutate(discount.id)
                          }
                        }}
                        className="rounded-lg p-2 text-gray-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/30"
                        title="刪除"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {drawerOpen && (
        <DiscountDrawer
          discount={editing}
          onClose={() => {
            setDrawerOpen(false)
            setEditing(null)
          }}
          onSubmit={(data) => {
            if (editing) updateMutation.mutate({ id: editing.id, data })
            else createMutation.mutate(data)
          }}
          isSaving={createMutation.isPending || updateMutation.isPending}
        />
      )}
    </div>
  )
}

function getDiscountStatus(discount: DiscountCode) {
  const now = new Date()
  const start = discount.start_at ? new Date(discount.start_at) : null
  const end = discount.end_at ? new Date(discount.end_at) : null
  const usageFull = discount.usage_limit !== null && discount.used_count >= discount.usage_limit

  if (!discount.is_active) {
    return {
      state: 'disabled',
      label: '目前停用',
      reason: '日期可能符合，但此優惠目前關閉中，不會出現在前台金額明細。',
      className: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-200',
    }
  }

  if (start && now < start) {
    return {
      state: 'scheduled',
      label: '尚未開始',
      reason: `會在 ${formatDateTime(discount.start_at)} 後開始套用。`,
      className: 'bg-blue-100 text-blue-700',
    }
  }

  if (end && now > end) {
    return {
      state: 'expired',
      label: '已過期',
      reason: `已在 ${formatDateTime(discount.end_at)} 結束。`,
      className: 'bg-red-100 text-red-700',
    }
  }

  if (usageFull) {
    return {
      state: 'full',
      label: '已達上限',
      reason: '使用次數已滿，請提高使用上限或複製新活動。',
      className: 'bg-amber-100 text-amber-700',
    }
  }

  return {
    state: 'active',
    label: '目前啟用',
    reason: discount.is_auto_apply ? '系統會自動檢查條件並套用。' : '客人需輸入折扣碼才會套用。',
    className: 'bg-green-100 text-green-700',
  }
}

function StatusBadge({ discount }: { discount: DiscountCode }) {
  const status = getDiscountStatus(discount)
  return (
    <span
      title={status.reason}
      className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${status.className}`}
    >
      {status.label}
    </span>
  )
}

function DiscountDrawer({
  discount,
  onClose,
  onSubmit,
  isSaving,
}: {
  discount: DiscountCode | null
  onClose: () => void
  onSubmit: (data: DiscountCodeWriteData) => void
  isSaving: boolean
}) {
  const [form, setForm] = useState<DiscountCodeWriteData>(() => discount ? toForm(discount) : { ...emptyForm })

  const update = <K extends keyof DiscountCodeWriteData>(key: K, value: DiscountCodeWriteData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const applyPreset = (preset: 'manual' | 'auto' | 'bundle') => {
    setForm((prev) => {
      if (preset === 'bundle') {
        return {
          ...prev,
          apply_scope: 'bundle',
          require_multiple_items: true,
          is_auto_apply: true,
          discount_type: 'amount',
          amount_apply_mode: 'order',
        }
      }
      if (preset === 'auto') {
        return {
          ...prev,
          apply_scope: 'all',
          require_multiple_items: false,
          is_auto_apply: true,
        }
      }
      return {
        ...prev,
        apply_scope: 'all',
        require_multiple_items: false,
        is_auto_apply: false,
      }
    })
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit({
      ...form,
      code: form.code.trim().toUpperCase(),
      name: form.name?.trim() || '',
      description: form.description?.trim() || '',
      max_discount_amount: normalizeOptionalNumber(form.max_discount_amount),
      min_order_amount: Number(form.min_order_amount || 0),
      usage_limit: normalizeOptionalNumber(form.usage_limit),
      start_at: form.start_at || null,
      end_at: form.end_at || null,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30">
      <div className="h-full w-full max-w-xl overflow-y-auto bg-white shadow-xl dark:bg-gray-900">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4 dark:border-gray-700 dark:bg-gray-900">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {discount ? `編輯折扣碼：${discount.code}` : '新增折扣碼'}
            </h2>
            <p className="mt-1 text-xs text-gray-500">設定會先保存到後台，套用到付款流程需另接驗證。</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-5 p-6">
          <div className="rounded-xl border border-violet-100 bg-violet-50 p-4 dark:border-violet-900/50 dark:bg-violet-950/20">
            <p className="text-sm font-semibold text-gray-900 dark:text-white">先選活動用法</p>
            <div className="mt-3 grid gap-2 md:grid-cols-3">
              <PresetButton
                title="手動折扣碼"
                description="客人輸入代碼才折扣"
                onClick={() => applyPreset('manual')}
              />
              <PresetButton
                title="自動優惠"
                description="符合條件自動套用"
                onClick={() => applyPreset('auto')}
              />
              <PresetButton
                title="搭配課程折扣"
                description="滑雪加購攝影才套用"
                onClick={() => applyPreset('bundle')}
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Field label="折扣碼">
              <input value={form.code} onChange={(e) => update('code', e.target.value)} required className={inputClass} placeholder="例如 SNOW500" />
            </Field>
            <Field label="活動名稱">
              <input value={form.name || ''} onChange={(e) => update('name', e.target.value)} className={inputClass} placeholder="例如 舊生推薦" />
            </Field>
          </div>

          <div className="grid gap-4 md:grid-cols-4">
            <Field label="折扣類型">
              <select value={form.discount_type} onChange={(e) => update('discount_type', e.target.value as DiscountType)} className={inputClass}>
                <option value="amount">固定金額</option>
                <option value="percent">百分比</option>
              </select>
            </Field>
            <Field label="固定金額折扣單位">
              <select
                value={form.amount_apply_mode || 'order'}
                onChange={(e) => update('amount_apply_mode', e.target.value as AmountApplyMode)}
                disabled={form.discount_type !== 'amount'}
                className={inputClass}
              >
                <option value="order">整筆一次</option>
                <option value="item">每個項目</option>
                <option value="course">每堂課</option>
                <option value="hour">每小時</option>
              </select>
            </Field>
            <Field label={form.discount_type === 'percent' ? '折扣百分比' : '折扣金額'}>
              <input type="number" min={1} value={form.discount_value} onChange={(e) => update('discount_value', Number(e.target.value))} required className={inputClass} />
            </Field>
            <Field label="最高折抵">
              <input
                type="number"
                min={1}
                value={form.max_discount_amount ?? ''}
                onChange={(e) => update('max_discount_amount', e.target.value ? Number(e.target.value) : null)}
                className={inputClass}
                placeholder="不限"
              />
            </Field>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Field label="適用範圍">
              <select value={form.apply_scope} onChange={(e) => update('apply_scope', e.target.value as DiscountScope)} className={inputClass}>
                <option value="all">全部訂單</option>
                <option value="ski">滑雪課程</option>
                <option value="photo">攝影服務</option>
                <option value="bundle">課程搭配/組合</option>
              </select>
            </Field>
            <Field label="最低金額">
              <input type="number" min={0} value={form.min_order_amount || 0} onChange={(e) => update('min_order_amount', Number(e.target.value))} className={inputClass} />
            </Field>
            <Field label="使用上限">
              <input
                type="number"
                min={1}
                value={form.usage_limit ?? ''}
                onChange={(e) => update('usage_limit', e.target.value ? Number(e.target.value) : null)}
                className={inputClass}
                placeholder="不限"
              />
            </Field>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Field label="開始時間">
              <input type="datetime-local" value={toDateTimeInput(form.start_at)} onChange={(e) => update('start_at', e.target.value || null)} className={inputClass} />
            </Field>
            <Field label="結束時間">
              <input type="datetime-local" value={toDateTimeInput(form.end_at)} onChange={(e) => update('end_at', e.target.value || null)} className={inputClass} />
            </Field>
          </div>

          <Field label="備註">
            <textarea value={form.description || ''} onChange={(e) => update('description', e.target.value)} className={`${inputClass} min-h-[96px]`} placeholder="內部備註或使用條件" />
          </Field>

          <div className="grid gap-3 md:grid-cols-5">
            <Toggle label="啟用折扣碼" checked={form.is_active} onChange={(value) => update('is_active', value)} />
            <Toggle label="自動套用" checked={!!form.is_auto_apply} onChange={(value) => update('is_auto_apply', value)} />
            <Toggle label="限新客" checked={!!form.new_customer_only} onChange={(value) => update('new_customer_only', value)} />
            <Toggle label="需搭配多項" checked={!!form.require_multiple_items} onChange={(value) => update('require_multiple_items', value)} />
            <Toggle label="可與其他優惠並用" checked={!!form.can_combine} onChange={(value) => update('can_combine', value)} />
          </div>

          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs leading-5 text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300">
            <p className="font-semibold text-gray-800 dark:text-gray-100">設定提醒</p>
            <p className="mt-1">
              自動套用只是「不用輸入折扣碼」，仍然要打開「啟用折扣碼」，且目前日期必須落在開始/結束時間內。
              搭配課程折扣請選「課程搭配/組合」，目前規則是同一張訂單同時有滑雪課程與攝影服務時，折扣套到攝影項目。
            </p>
          </div>

          <div className="flex justify-end gap-3 border-t border-gray-200 pt-5 dark:border-gray-700">
            <button type="button" onClick={onClose} className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800">
              取消
            </button>
            <button type="submit" disabled={isSaving} className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-60" style={{ backgroundColor: PRIMARY }}>
              {isSaving && <Loader2 size={14} className="animate-spin" />}
              儲存
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">{label}</span>
      {children}
    </label>
  )
}

function PresetButton({
  title,
  description,
  onClick,
}: {
  title: string
  description: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-white bg-white px-3 py-3 text-left text-sm shadow-sm transition hover:border-[#8b5cf6] hover:text-[#6d28d9] dark:border-gray-700 dark:bg-gray-800 dark:hover:border-[#8b5cf6]"
    >
      <span className="block font-semibold text-gray-900 dark:text-white">{title}</span>
      <span className="mt-1 block text-xs leading-5 text-gray-500 dark:text-gray-400">{description}</span>
    </button>
  )
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between rounded-lg border border-gray-200 p-3 text-sm font-medium text-gray-700 dark:border-gray-700 dark:text-gray-200">
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 rounded border-gray-300" />
    </label>
  )
}

function toForm(discount: DiscountCode): DiscountCodeWriteData {
  return {
    code: discount.code,
    name: discount.name,
    description: discount.description,
    discount_type: discount.discount_type,
    amount_apply_mode: discount.amount_apply_mode || 'order',
    discount_value: discount.discount_value,
    max_discount_amount: discount.max_discount_amount,
    min_order_amount: discount.min_order_amount,
    apply_scope: discount.apply_scope,
    require_multiple_items: discount.require_multiple_items,
    can_combine: discount.can_combine,
    is_auto_apply: discount.is_auto_apply,
    new_customer_only: discount.new_customer_only,
    usage_limit: discount.usage_limit,
    start_at: discount.start_at,
    end_at: discount.end_at,
    is_active: discount.is_active,
  }
}

function normalizeOptionalNumber(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null
  const numeric = Number(value)
  return numeric > 0 ? numeric : null
}

function toDateTimeInput(value?: string | null) {
  if (!value) return ''
  return value.slice(0, 16)
}

function formatDateTime(value?: string | null) {
  if (!value) return ''
  return value.replace('T', ' ').slice(0, 16)
}
