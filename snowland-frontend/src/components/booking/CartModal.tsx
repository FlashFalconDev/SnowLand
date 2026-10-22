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
import { hasUnconfirmedCartPrice, isPhotoCartGroup } from '@/utils/cartService'
import ConfirmModal from '@/components/ui/ConfirmModal'
import { useSiteLocale } from '@/contexts/SiteLocale'

interface CartModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  onEditGroup?: (groupId: string) => void
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
  if (value === null || value === undefined) return '待重新試算'
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

export default function CartModal({ isOpen, onClose, onConfirm, onEditGroup }: CartModalProps) {
  const { t, locale } = useSiteLocale()
  const currency = (value?: number | null) => t(formatCurrency(value))
  const cart = useBookingStore((state) => state.cart)
  const removeFromCart = useBookingStore((state) => state.removeFromCart)
  const removeCourseFromGroup = useBookingStore((state) => state.removeCourseFromGroup)
  const [pending, setPending] = useState<RemovePending>(null)

  const totalAmount = cart.reduce((sum, group) => sum + (group.totalPrice || 0), 0)
  const totalCourses = cart.reduce((sum, group) => sum + group.courses.length, 0)
  const hasPendingPrice = hasUnconfirmedCartPrice(cart)
  const hasSharedClass = cart.some((group) => group.courses.some((course) => course.sharedClassEnabled))

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
            <h2 className="mt-1 text-2xl font-semibold text-[#1f2937] font-display">{t('購物車')}</h2>
            <p className="mt-1 text-sm text-[#64748b]">
              {t('共 {groups} 組預約、{lessons} 堂課', { groups: cart.length, lessons: totalCourses })}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('關閉購物車')}
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
            <p className="mt-5 text-lg font-semibold text-[#1f2937] font-display">{t('購物車是空的')}</p>
            <p className="mt-2 text-sm text-[#64748b]">{t('完成課程設定後，預約會顯示在這裡。')}</p>
            <button
              type="button"
              onClick={onClose}
              className="mt-6 inline-flex items-center justify-center rounded-full bg-[#2b5f8f] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#1f4a6f]"
            >
              {t('開始預約')}
            </button>
          </div>
        ) : (
          <>
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5 md:px-6">
              <div className="rounded-sm border border-[#bfdbfe] bg-[#eff6ff] px-4 py-3 text-xs leading-5 text-[#1e3a8a]">
                <p className="font-semibold">{t(hasSharedClass ? '團體湊班報名' : '購物車讀法')}</p>
                <p className="mt-1">
                  {t(hasSharedClass
                    ? '這筆報名需單獨結帳。滿成班人數並安排教練後，系統才會通知付款。'
                    : !onEditGroup
                      ? '每張卡是一組設定；若需修改，請移除該組後重新選擇課程、日期與時段。'
                      : hasPendingPrice
                      ? '已保留上次的預約設定。請點「修改這組課程」選擇新課程、日期與時段，重新確認價格；不會沿用舊價或直接建立訂單。'
                      : '每張卡是一組設定，同一天多堂課會逐堂列出。可修改這組課程，完成新設定後才替換，原購物車會先保留。')}
                </p>
              </div>
              {cart.map((group, groupIndex) => (
                <article
                  key={group.id}
                  className="rounded-sm border border-[#e5e9f2] bg-white p-5 shadow-[0_10px_24px_rgba(15,23,42,0.04)]"
                >
                  {onEditGroup && <button type="button" onClick={() => onEditGroup(group.id)} className="mb-4 min-h-11 rounded-full border border-[#2b5f8f] px-4 py-2 text-sm font-semibold text-[#2b5f8f]">{t('修改這組課程')}</button>}
                  {group.rebookSource && !isPhotoCartGroup(group) && <p className="mb-4 rounded-sm bg-[#eef4fa] p-3 text-xs leading-6 text-[#1e4e73]">{t('將沿用上次可管理的 {count} 位學員姓名、年齡區間與滑雪程度；其他成人請重新邀請綁定。保險資料與聲明簽名須重新確認。', { count: group.rebookSource.learnerCount })}</p>}
                  {group.rebookLearnersReset && <p role="status" className="mb-4 rounded-sm bg-amber-50 p-3 text-xs leading-6 text-amber-900">{t('人數已變更，本次不自動沿用學員；訂單成立後請重新填寫或邀請綁定。')}</p>}
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#94a3b8]">
                        {t('預約組 {number}', { number: groupIndex + 1 })}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <h3 className="text-lg font-semibold text-[#1f2937] font-display">
                          {group.courseCategory}
                        </h3>
                        <span className="rounded-full bg-[#e9eef3] px-2.5 py-1 text-xs font-semibold text-[#2b5f8f]">
                          {t('{count} 堂', { count: group.courses.length })}
                        </span>
                        {getUniqueDateCount(group.courses) > 1 && (
                          <span className="rounded-full bg-[#f8fafc] px-2.5 py-1 text-xs font-medium text-[#64748b] ring-1 ring-[#dbe3ec]">
                            {t('{count} 天', { count: getUniqueDateCount(group.courses) })}
                          </span>
                        )}
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-[#64748b]">
                        <span className="inline-flex items-center gap-1.5">
                          <MapPin size={14} />
                          {group.resortName || group.resort || t('未指定雪場')}
                        </span>
                        <span>{getCourseDateSummary(group.courses, t)}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveGroup(group.id)}
                      className="inline-flex items-center gap-1.5 rounded-full border border-[#f1c7c7] px-3 py-1.5 text-xs font-semibold text-[#b42318] transition-colors hover:bg-[#fff1f1]"
                    >
                      <Trash2 size={14} />
                      {t('移除整組')}
                    </button>
                  </div>

                  <div className={`mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 ${isPhotoCartGroup(group) ? '' : 'lg:grid-cols-5'}`}>
                    <MetaItem icon={User} label={t(isPhotoCartGroup(group) ? '攝影師' : '教練')} value={isPhotoCartGroup(group) || group.courses[0]?.sharedClassEnabled ? t('由學校安排') : (group.coachName === '不指定' || !group.coachName ? t('不指定') : group.coachName)} />
                    <MetaItem icon={Users} label={t(isPhotoCartGroup(group) ? '預約數量' : '人數')} value={t(isPhotoCartGroup(group) ? '{count} 組' : '{count} 人', { count: group.peopleCount })} />
                    {!isPhotoCartGroup(group) && <>
                    <MetaItem icon={Languages} label={t('語言')} value={t(getLanguageLabel(group.language))} />
                    <MetaItem icon={Package} label={t('裝備')} value={t(getEquipmentLabel(group.equipmentOption, group.equipment))} />
                    <MetaItem label={t('能力')} value={getCartAbilityLabel(group.abilityLevelCounts, group.abilityLevelName || group.abilityLevel, t)} />
                    {group.equipmentAssistanceTimeLabel && (
                      <MetaItem icon={Clock} label={t('裝備協助')} value={group.equipmentAssistanceTimeLabel} />
                    )}</>}
                  </div>

                  <div className="mt-4 border-t border-[#edf1f6] pt-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-[#1f2937]">{t('課程內容')}</p>
                      <p className="text-xs text-[#64748b]">{t('同一日期多堂會分開顯示')}</p>
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
                                {course.date} ({getDayOfWeek(course.date, locale)})
                              </span>
                              <span className="inline-flex items-center gap-1.5">
                                <Clock size={13} />
                                {course.timeSlotStart} - {course.timeSlotEnd}
                              </span>
                            </div>
                          </div>
                          <div className="flex shrink-0 items-center justify-between gap-3 sm:justify-end">
                            <span className="text-sm font-semibold text-[#2b5f8f]">
                              {currency(course.price)}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleRemoveCourse(group.id, courseIndex, course.courseTemplateName || course.courseTypeName)}
                              aria-label={t('移除課程')}
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
                      {group.coachFee ? <FeeLine label={t('教練指定費')} value={group.coachFee} /> : null}
                      {group.languageFee ? <FeeLine label={t('語言加價')} value={group.languageFee} /> : null}
                      {group.equipmentRentalFee ? <FeeLine label={t('裝備協助費')} value={group.equipmentRentalFee} /> : null}
                    </div>
                  ) : null}

                  <div className="mt-4 flex items-center justify-between border-t border-[#edf1f6] pt-4">
                    <span className="text-sm font-semibold text-[#64748b]">{t('小計')}</span>
                    <span className="text-base font-bold text-[#1f2937]">{currency(group.totalPrice)}</span>
                  </div>
                </article>
              ))}
            </div>

            <footer className="border-t border-[#dbe3ec] bg-white px-5 py-4 md:px-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-semibold tracking-[0.12em] text-[#64748b]">{hasSharedClass ? t('成班後應付') : 'Total'}</p>
                  <p className="mt-1 text-2xl font-bold text-[#2b5f8f]">
                    {hasPendingPrice ? t('請先重新試算') : `NT$ ${totalAmount.toLocaleString()}`}
                  </p>
                  <p className="mt-1 text-xs text-[#64748b]">
                    {hasSharedClass
                      ? t('送出只建立報名；收到成班通知後再付款。')
                      : t('送出後會一次建立 {groups} 組預約，共 {lessons} 堂課。', { groups: cart.length, lessons: totalCourses })}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onConfirm}
                  disabled={cart.length === 0 || hasPendingPrice}
                  className="inline-flex items-center justify-center rounded-full bg-[#2b5f8f] px-8 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#1f4a6f] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t('確認預約')}
                </button>
              </div>
            </footer>
          </>
        )}
      </div>

      <div onClick={(e) => e.stopPropagation()}>
        <ConfirmModal
          isOpen={!!pending}
          title={t(pending?.kind === 'group' ? '移除整個預約' : '移除課程')}
          message={
            pending?.kind === 'group'
              ? t('此預約底下的所有課程將被一併移除，確定要繼續嗎？')
              : t('「{course}」將從購物車中移除，其他同日課程會保留。確定要繼續嗎？', { course: pending?.courseName || t('此堂課程') })
          }
          variant="danger"
          confirmText={t('確定移除')}
          cancelText={t('取消')}
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
  const { t } = useSiteLocale()
  return (
    <div className="flex min-h-[44px] items-center gap-2 rounded-sm border border-[#edf1f6] bg-[#f8fafc] px-3 py-2">
      {Icon && <Icon size={15} className="shrink-0 text-[#2b5f8f]" />}
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-[#94a3b8]">{label}</p>
        <p className="break-words text-sm leading-relaxed text-[#1f2937]">{value || t('未指定')}</p>
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

function getCartAbilityLabel(counts: Record<string, number> | undefined, fallback: string, t: (source: string, values?: Record<string, string | number>) => string): string {
  return ['no_exp', 'level1', 'level2', 'level3', 'level4', 'level5', 'level6']
    .map((key, level) => (counts?.[key] || 0) > 0 ? t('等級 {level}：{count} 人', { level, count: counts![key] }) : '')
    .filter(Boolean).join(' / ') || fallback
}

function getCourseDateSummary(courses: Array<{ date: string }>, t: (source: string, values?: Record<string, string>) => string): string {
  const dates = Array.from(new Set(courses.map((course) => course.date).filter(Boolean))).sort()
  if (dates.length === 0) return t('尚未選日期')
  if (dates.length === 1) return dates[0]
  return t('{start} 至 {end}', { start: dates[0], end: dates[dates.length - 1] })
}

function getDayOfWeek(dateString: string, locale: string): string {
  const date = new Date(`${dateString}T00:00:00Z`)
  return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone: 'UTC' }).format(date)
}
