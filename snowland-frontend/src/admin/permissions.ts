import type { AdminUser } from './api/auth'

export interface AdminPermissionDefinition {
  key: string
  label: string
  group: string
  description: string
}

export const ADMIN_PERMISSION_DEFINITIONS: AdminPermissionDefinition[] = [
  { key: 'analytics', label: '營運分析', group: '營運管理', description: '查看儀表板、營收與訂單統計' },
  { key: 'orders', label: '訂單管理', group: '營運管理', description: '查看與處理訂單、寄送訂單信件' },
  { key: 'scheduling', label: '排課管理', group: '營運管理', description: '查看排課月曆與課程安排' },
  { key: 'customers', label: '會員管理', group: '營運管理', description: '查看會員資料與預約紀錄' },
  { key: 'chat_support', label: 'AI 客服', group: '營運管理', description: '查看 LINE 對話、接手案件並人工回覆' },
  { key: 'insurance_records', label: '保險資料', group: '營運管理', description: '查看保險與聲明書完成狀態' },
  { key: 'evaluations', label: '評量與課程紀錄', group: '營運管理', description: '填寫評量、學習進度與課程媒體' },
  { key: 'payroll', label: '薪資結算', group: '營運管理', description: '管理教練時薪、指定費、介紹費與月結' },
  { key: 'notifications', label: '自動通知', group: '營運管理', description: '設定郵件與 LINE 通知' },
  { key: 'campuses', label: '校區與營運規則', group: '基本設定', description: '管理校區、雪場與營運規則' },
  { key: 'resorts', label: '雪場管理', group: '基本設定', description: '管理雪場、接送與租借設定' },
  { key: 'course_types', label: '課程架構', group: '基本設定', description: '管理課程大類、類型、模板與時段' },
  { key: 'pricing', label: '課程定價', group: '基本設定', description: '管理旺淡季與課程價格' },
  { key: 'discounts', label: '優惠折扣', group: '基本設定', description: '管理折扣碼、早鳥與促銷規則' },
  { key: 'coaches', label: '教練管理', group: '基本設定', description: '管理教練資料、證照與請假審核' },
  { key: 'staff', label: '員工權限', group: '基本設定', description: '設定管理員、教練與模組權限' },
  { key: 'payment_settings', label: '付款設定', group: '基本設定', description: '管理匯款帳戶與付款資訊' },
  { key: 'cms', label: '官網內容', group: '官網內容', description: '管理首頁、教練、雪場、FAQ 與文章內容' },
  { key: 'reviews', label: '評論與媒體', group: '評論與媒體', description: '管理 Google 評論、手動評論與媒體素材' },
]

export const ADMIN_PERMISSION_KEYS = ADMIN_PERMISSION_DEFINITIONS.map((item) => item.key)

export function hasAdminPermission(user: AdminUser | null | undefined, permission?: string): boolean {
  if (!permission) return !!user?.is_manager || !!user?.is_superuser
  if (user?.is_superuser) return true
  if (!user?.is_manager) return false
  return (user.permissions || []).includes(permission)
}

export function groupPermissions(definitions = ADMIN_PERMISSION_DEFINITIONS) {
  return definitions.reduce<Record<string, AdminPermissionDefinition[]>>((groups, permission) => {
    groups[permission.group] = groups[permission.group] || []
    groups[permission.group].push(permission)
    return groups
  }, {})
}
