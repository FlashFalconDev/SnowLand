import type { AdminUser } from './api/auth'

const GENERAL_STAFF_LABEL = '一般後台人員'

export const STAFF_ROLE_OPTIONS = [
  ['hq_admin', '總部管理員'],
  ['campus_principal', '校區校長'],
  ['campus_manager', '校區主管'],
  ['assistant', '行政小幫手'],
  ['insurance', '保險人員'],
  ['marketing', '行銷人員'],
  ['web_editor', '網頁人員'],
  ['photographer', '攝影人員'],
  ['', GENERAL_STAFF_LABEL],
] as const

type StaffRole = Pick<AdminUser, 'role' | 'is_superuser' | 'is_manager' | 'is_coach'>

export function getSidebarRoleLabel(user: StaffRole | null | undefined): string {
  const labels = new Set<string>()
  if (user?.is_superuser === true) {
    labels.add('最大管理員')
  } else if (user?.is_manager === true) {
    const roleLabel = STAFF_ROLE_OPTIONS.find(([role]) => role === user.role)?.[1]
    labels.add(roleLabel ?? GENERAL_STAFF_LABEL)
  }
  if (user?.is_coach === true) {
    labels.add('教練')
  }
  return [...labels].join('・') || '尚未授權'
}
