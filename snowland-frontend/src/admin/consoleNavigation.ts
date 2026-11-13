import { LayoutDashboard, ShoppingCart, MessageCircle, Users, ClipboardCheck, BookOpen, Wallet, Megaphone, Globe, Settings, Shield } from 'lucide-react'
import type { AdminUser } from './api/auth'
import { canPrepareStaffBooking, canUseFrontendSupport, hasAdminPermission } from './permissions'

export const consoleNavigation = [
  { id: 'overview', label: '營運總覽', icon: LayoutDashboard, pages: [
    { path: '', label: '營運看板與報表', access: 'analytics' },
    { path: 'coach-workload', label: '教練排課統計', access: '@superuser' },
    { path: 'vehicles/review', label: '車輛排班與用車審核', access: 'vehicle_review' },
    { path: 'vehicles/finance', label: '車輛費率與費用核准', access: 'vehicle_finance' },
  ] },
  { id: 'members', label: '會員與課前資料', icon: Users, pages: [
    { path: 'customers', label: '會員名單', access: 'member_directory' },
    { path: 'insurance', label: '保險與聲明書紀錄', access: 'insurance_records' },
    { path: 'customers/loyalty', label: '會員制度與舊生審核', access: 'member_loyalty' },
    { path: 'cms/membership', label: '課前聲明書與表單', access: 'course_documents' },
  ] },
  { id: 'teaching', label: '教學與教練', icon: ClipboardCheck, pages: [
    { path: 'scheduling', label: '排課月曆與團體班', access: 'scheduling' },
    { path: 'coaches', label: '教練名冊與排課設定', access: 'coach_directory' },
    { path: 'coaches/leaves', label: '請假審核', access: 'coach_leaves' },
    { path: 'evaluations', label: '學習評量與課程附件', access: 'evaluations' },
    { path: 'my/pending', label: '我的待確認課程', access: '@coach' },
    { path: 'my/courses', label: '我的課程', access: '@coach' },
    { path: 'my/calendar', label: '我的月曆', access: '@coach' },
    { path: 'my/vehicles', label: '我的用車', access: '@coach' },
    { path: 'my/evaluations', label: '我的學員評量', access: '@coach' },
    { path: 'my/leaves', label: '我的請假紀錄', access: '@coach' },
    { path: 'my/leaves/apply', label: '申請請假', access: '@coach' },
  ] },
  { id: 'orders', label: '訂單', icon: ShoppingCart, pages: [
    { path: 'orders', label: '訂單列表', access: 'order_view' },
    { path: 'booking-links', label: '代客訂課連結', access: 'booking_links' },
    { path: 'orders/edit', label: '修改與排課', access: 'order_edit' },
    { path: 'orders/payments', label: '對帳與差額', access: 'order_payments' },
    { path: 'orders/refunds', label: '取消與退款', access: 'order_refunds' },
    { path: 'orders/export', label: '匯出訂單', access: 'order_export' },
  ] },
  { id: 'support', label: '客服與通知', icon: MessageCircle, pages: [
    { path: 'contact-inbox', label: '官網聯絡收件', access: 'contact_inbox' },
    { path: 'chat-support', label: 'LINE／AI 客服', access: 'chat_support' },
    { path: 'notifications', label: '通知範本與發送紀錄', access: 'notifications' },
  ] },
  { id: 'finance', label: '財務', icon: Wallet, pages: [
    { path: 'payment-settings', label: '收款帳戶與幣別', access: 'payment_accounts' },
    { path: 'payroll/rules', label: '教練計薪規則', access: 'payroll_rules' },
    { path: 'payroll', label: '薪資單與月結', access: 'payroll_statements' },
    { path: 'payroll/incentives', label: '行政獎金', access: 'staff_incentives' },
    { path: 'payroll/documents', label: '薪資文件設定', access: 'payroll_documents' },
    { path: 'my/payroll', label: '我的薪資', access: '@coach' },
  ] },
  { id: 'catalog', label: '課程與雪場', icon: BookOpen, pages: [
    { path: 'course-types', label: '課程架構', access: 'course_types' },
    { path: 'pricing', label: '課程定價', access: 'pricing' },
    { path: 'resorts', label: '雪場營運資料', access: 'resorts' },
  ] },
  { id: 'marketing', label: '行銷與優惠', icon: Megaphone, pages: [
    { path: 'discounts', label: '折扣碼與促銷規則', access: 'discounts' },
    { path: 'cms/offers', label: '官網優惠活動與社群', access: 'site_campaigns' },
    { path: 'social-sync', label: '官方社群授權', access: 'social_sync' },
  ] },
  { id: 'site', label: '官網內容', icon: Globe, pages: [
    { path: 'cms/homepage', label: '首頁與頁尾', access: 'site_home' },
    { path: 'cms/courses', label: '滑雪課程與雪場介紹', access: 'site_courses' },
    { path: 'cms/photography', label: '海外攝影', access: 'site_photography' },
    { path: 'cms/guides', label: '滑雪攻略與 FAQ', access: 'site_guides' },
    { path: 'cms/news', label: '最新消息', access: 'site_news' },
    { path: 'cms/about', label: '品牌介紹與聯絡頁', access: 'site_about' },
    { path: 'cms/recruitment', label: '教練招募', access: 'recruitment' },
    { path: 'cms/coaches', label: '官網教練資料', access: 'site_coaches' },
    { path: 'reviews/manual', label: '網站評論', access: 'site_reviews' },
    { path: 'media', label: '圖庫', access: 'site_media' },
    { path: 'cms/tracking', label: '網站追蹤設定', access: 'site_tracking' },
    { path: 'cms/structure', label: '官網頁面與區塊', access: 'site_structure' },
  ] },
  { id: 'settings', label: '設定', icon: Settings, pages: [
    { path: 'campuses', label: '校區與營運規則', access: 'campuses' },
    { path: 'staff', label: '員工與權限', access: 'staff' },
    { path: 'cms/policies', label: '訂課條款與隱私政策', access: 'checkout_policies' },
    { path: 'booking-form-settings', label: '訂單表單選項', access: 'booking_form_options' },
  ] },
  { id: 'system', label: '系統管理', icon: Shield, pages: [
    { path: 'system/support', label: '前端版本發布與還原', access: '@platform' },
  ] },
] as const

export type ConsolePage = (typeof consoleNavigation)[number]['pages'][number]
export type ConsolePath = ConsolePage['path']

export function canOpenConsolePage(page: ConsolePage, user: AdminUser | null | undefined, basePath: string) {
  if (page.access === 'booking_links') return canPrepareStaffBooking(user)
  if (page.access === '@coach') return user?.is_coach === true
  if (page.access === '@superuser') return user?.is_superuser === true
  if (page.access === '@platform') return canUseFrontendSupport(basePath, user)
  return hasAdminPermission(user, page.access)
}
