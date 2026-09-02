import { useState } from 'react'
import {
  Calendar,
  Clock,
  Languages,
  type LucideIcon,
  MapPin,
  Package,
  ShoppingBag,
  Trash2,
  User,
  Users,
  X,
} from 'lucide-react'
import { useBookingStore } from '@/store/bookingStore'
import ConfirmModal from '@/components/ui/ConfirmModal'

interface CartModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
}

type RemovePending =
  | { kind: 'group'; groupId: string }
  | { kind: 'course'; groupId: string; courseIndex: number; courseName: string }
  | null

const languageLabels: Record<string, string> = {
  zh: '中文',
  en: '英文',
  ja: '日文',
  yue: '粵語',
}

const equipmentLabels: Record<string, string> = {
  self_rent: '自行租借',
  own_equipment: '自備裝備',
  class_time_help: '課程時間內協助',
  extra_time_help: '加購協助時間',
}

const formatCurrency = (value?: number | null) => {
  if (value === null || value === undefined) return '價格計算中'
  return `NT$ ${value.toLocaleString()}`
}

const getLanguageLabel = (value?: string | null) => {
  if (!value) return '中文'
  return languageLabels[value] || value
}

const getEquipmentLabel = (option?: string | null, needsEquipment?: boolean) => {
  if (option && equipmentLabels[option]) return equipmentLabels[option]
  return needsEquipment ? '需要協助' : '不需協助'
}

export default function CartModal({ isOpen, onClose, onConfirm }: CartModalProps) {
  const cart = useBookingStore((state) => state.cart)
  const removeFromCart = useBookingStore((state) => state.removeFromCart)
  const removeCourseFromGroup = useBookingStore((state) => state.removeCourseFromGroup)
  const [pending, setPending] = useState<RemovePending>(null)

  const totalAmount = cart.reduce((sum, group) => sum + (group.totalPrice || 0), 0)
  const totalCourses = cart.reduce((sum, group) => sum + group.courses.length, 0)
  const hasPendingPrice = cart.some((group) => group.totalPrice === null)

  if (!isOpen) return null

  const handleRemoveGroup = (groupId: string) => {
    setPending({ kind: 'group', groupId })
  }

  const handleRemoveCourse = (groupId: string, courseIndex: number, courseName: string) => {
    setPending({ kind: 'course', groupId, courseIndex, courseName })
  }

  const confirmRemove = () => {
    if (!pending) return
    if (pending.kind === 'group') removeFromCart(pending.groupId)
    if (pending.kind === 'course') removeCourseFromGroup(pending.groupId, pending.courseIndex)
    setPending(null)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 px-4 py-6 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-sm border border-[#dbe3ec] bg-[#f7f8fa] shadow-[0_24px_70px_rgba(15,23,42,0.22)]"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between border-b border-[#dbe3ec] bg-white px-5 py-4 md:px-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#94a3b8]">Cart</p>
            <h2 className="mt-1 text-2xl font-semibold text-[#1f2937] font-display">購物車</h2>
            <p className="mt-1 text-sm text-[#64748b]">
              共 {cart.length} 組預約、{totalCourses} 堂課
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="關閉購物車"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[#dbe3ec] bg-white text-[#64748b] transition-colors hover:border-[#2b5f8f] hover:text-[#2b5f8f]"
          >
            <X size={18} />
          </button>
        </header>

        {cart.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center px-6 py-14 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full border border-dashed border-[#cbd5e1] bg-white text-[#94a3b8]">
              <ShoppingBag size={28} />
            </div>
            <p className="mt-5 text-lg font-semibold text-[#1f2937] font-display">購物車是空的</p>
            <p className="mt-2 text-sm text-[#64748b]">完成課程設定後，預約會顯示在這裡。</p>
            <button
              type="button"
              onClick={onClose}
              className="mt-6 inline-flex items-center justify-center rounded-full bg-[#2b5f8f] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#1f4a6f]"
            >
              開始預約
            </button>
          </div>
        ) : (
          <>
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5 md:px-6">
              <div className="rounded-sm border border-[#bfdbfe] bg-[#eff6ff] px-4 py-3 text-xs leading-5 text-[#1e3a8a]">
                <p className="font-semibold">購物車讀法</p>
                <p className="mt-1">
                  每張卡是一組設定。像同一批學生、同一位教練、同一個裝備協助方式會放在同一組；同一天多堂課也會逐堂列出。
                  要改整組日期或設定，請移除整組後重新選；只刪單堂課可點課程列右側的垃圾桶。
                </p>
              </div>
              {cart.map((group, groupIndex) => (
                <article
                  key={group.id}
                  className="rounded-sm border border-[#e5e9f2] bg-white p-5 shadow-[0_10px_24px_rgba(15,23,42,0.04)]"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#94a3b8]">
                        預約組 {groupIndex + 1}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <h3 className="text-lg font-semibold text-[#1f2937] font-display">
                          {group.courseCategory}
                        </h3>
                        <span className="rounded-full bg-[#e9eef3] px-2.5 py-1 text-xs font-semibold text-[#2b5f8f]">
                          {group.courses.length} 堂
                        </span>
                        {getUniqueDateCount(group.courses) > 1 && (
                          <span className="rounded-full bg-[#f8fafc] px-2.5 py-1 text-xs font-medium text-[#64748b] ring-1 ring-[#dbe3ec]">
                            {getUniqueDateCount(group.courses)} 天
                          </span>
                        )}
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-[#64748b]">
                        <span className="inline-flex items-center gap-1.5">
                          <MapPin size={14} />
                          {group.resortName || group.resort || '未指定雪場'}
                        </span>
                        <span>{getCourseDateSummary(group.courses)}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveGroup(group.id)}
                      className="inline-flex items-center gap-1.5 rounded-full border border-[#f1c7c7] px-3 py-1.5 text-xs font-semibold text-[#b42318] transition-colors hover:bg-[#fff1f1]"
                    >
                      <Trash2 size={14} />
                      移除整組
                    </button>
                  </div>

                  <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5">
                    <MetaItem icon={User} label="教練" value={group.coachName || '不指定'} />
                    <MetaItem icon={Users} label="人數" value={`${group.peopleCount} 人`} />
                    <MetaItem icon={Languages} label="語言" value={getLanguageLabel(group.language)} />
                    <MetaItem icon={Package} label="裝備" value={getEquipmentLabel(group.equipmentOption, group.equipment)} />
                    <MetaItem label="能力" value={group.abilityLevelName || group.abilityLevel} />
                    {group.equipmentAssistanceTimeLabel && (
                      <MetaItem icon={Clock} label="裝備協助" value={group.equipmentAssistanceTimeLabel} />
                    )}
                  </div>

                  <div className="mt-4 border-t border-[#edf1f6] pt-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-[#1f2937]">課程內容</p>
                      <p className="text-xs text-[#64748b]">同一日期多堂會分開顯示</p>
                    </div>
                    <div className="space-y-2">
                      {group.courses.map((course, courseIndex) => (
                        <div
                          key={`${course.date}-${course.timeSlotId}-${courseIndex}`}
                          className="grid gap-3 rounded-sm border border-[#e5e9f2] bg-[#f8fafc] px-4 py-3 sm:grid-cols-[2.2rem_1fr_auto] sm:items-center"
                        >
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-xs font-semibold text-[#2b5f8f] ring-1 ring-[#dbe3ec]">
                            {courseIndex + 1}
                          </div>
                          <div className="min-w-0 space-y-1">
                            <p className="truncate text-sm font-semibold text-[#1f2937]">
                              {course.courseTemplateName || course.courseTypeName}
                            </p>
                            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#64748b]">
                              <span className="inline-flex items-center gap-1.5">
                                <Calendar size={13} />
                                {course.date} ({getDayOfWeek(course.date)})
                              </span>
                              <span className="inline-flex items-center gap-1.5">
                                <Clock size={13} />
                                {course.timeSlotStart} - {course.timeSlotEnd}
                              </span>
                            </div>
                          </div>
                          <div className="flex shrink-0 items-center justify-between gap-3 sm:justify-end">
                            <span className="text-sm font-semibold text-[#2b5f8f]">
                              {formatCurrency(course.price)}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleRemoveCourse(group.id, courseIndex, course.courseTemplateName || course.courseTypeName)}
                              aria-label="移除課程"
                              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-transparent text-[#94a3b8] transition-colors hover:border-[#f1c7c7] hover:bg-[#fff1f1] hover:text-[#b42318]"
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {(group.coachFee || group.languageFee || group.equipmentRentalFee) ? (
                    <div className="mt-4 space-y-1 border-t border-[#edf1f6] pt-3 text-xs text-[#64748b]">
                      {group.coachFee ? <FeeLine label="教練指定費" value={group.coachFee} /> : null}
                      {group.languageFee ? <FeeLine label="語言加價" value={group.languageFee} /> : null}
                      {group.equipmentRentalFee ? <FeeLine label="裝備協助費" value={group.equipmentRentalFee} /> : null}
                    </div>
                  ) : null}

                  <div className="mt-4 flex items-center justify-between border-t border-[#edf1f6] pt-4">
                    <span className="text-sm font-semibold text-[#64748b]">小計</span>
                    <span className="text-base font-bold text-[#1f2937]">{formatCurrency(group.totalPrice)}</span>
                  </div>
                </article>
              ))}
            </div>

            <footer className="border-t border-[#dbe3ec] bg-white px-5 py-4 md:px-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#94a3b8]">Total</p>
                  <p className="mt-1 text-2xl font-bold text-[#2b5f8f]">
                    {hasPendingPrice ? '價格計算中' : `NT$ ${totalAmount.toLocaleString()}`}
                  </p>
                  <p className="mt-1 text-xs text-[#64748b]">
                    送出後會一次建立 {cart.length} 組預約，共 {totalCourses} 堂課。
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onConfirm}
                  disabled={cart.length === 0}
                  className="inline-flex items-center justify-center rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#1f4a6f] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  確認預約
                </button>
              </div>
            </footer>
          </>
        )}
      </div>

      <div onClick={(e) => e.stopPropagation()}>
        <ConfirmModal
          isOpen={!!pending}
          title={pending?.kind === 'group' ? '移除整個預約' : '移除課程'}
          message={
            pending?.kind === 'group'
              ? '此預約底下的所有課程將被一併移除，確定要繼續嗎？'
              : `「${pending?.courseName || '此堂課程'}」將從購物車中移除，其他同日課程會保留。確定要繼續嗎？`
          }
          variant="danger"
          confirmText="確定移除"
          onConfirm={confirmRemove}
          onCancel={() => setPending(null)}
        />
      </div>
    </div>
  )
}

function MetaItem({
  icon: Icon,
  label,
  value,
}: {
  icon?: LucideIcon
  label: string
  value?: string | number | null
}) {
  return (
    <div className="flex min-h-[44px] items-center gap-2 rounded-sm border border-[#edf1f6] bg-[#f8fafc] px-3 py-2">
      {Icon && <Icon size={15} className="shrink-0 text-[#2b5f8f]" />}
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-[#94a3b8]">{label}</p>
        <p className="truncate text-sm text-[#1f2937]">{value || '未指定'}</p>
      </div>
    </div>
  )
}

function FeeLine({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between">
      <span>{label}</span>
      <span>{formatCurrency(value)}</span>
    </div>
  )
}

function getUniqueDateCount(courses: Array<{ date: string }>): number {
  return new Set(courses.map((course) => course.date).filter(Boolean)).size
}

function getCourseDateSummary(courses: Array<{ date: string }>): string {
  const dates = Array.from(new Set(courses.map((course) => course.date).filter(Boolean))).sort()
  if (dates.length === 0) return '尚未選日期'
  if (dates.length === 1) return dates[0]
  return `${dates[0]} 至 ${dates[dates.length - 1]}`
}

function getDayOfWeek(dateString: string): string {
  const days = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  const date = new Date(dateString)
  return days[date.getDay()]
}
