import type { AdminUser } from './api/auth'

export interface AdminPermissionDefinition {
  key: string
  label: string
  group: string
  description: string
}

export function canUseFrontendSupport(basePath: string, user?: AdminUser | null): boolean {
  return basePath === '/flashfalcon' && !!user?.is_superuser
}

export function hasAdminPermission(user: AdminUser | null | undefined, permission?: string): boolean {
  if (!permission) return !!user?.is_manager || !!user?.is_superuser
  if (user?.is_superuser) return true
  if (!user?.is_manager) return false
  if (['member_loyalty', 'social_sync', 'staff', 'order_export'].includes(permission) &&
    (user.role !== 'hq_admin' || !user.can_view_all_campuses)) return false
  if (['order_edit', 'order_payments', 'order_refunds'].includes(permission) &&
    ['campus_manager', 'campus_principal'].includes(user.role || '')) return false
  if (permission === 'recruitment' && !user.can_view_all_campuses) return false
  if (permission === 'contact_inbox' && (user.can_view_all_campuses === false || ['campus_manager', 'campus_principal', 'coach', 'photographer'].includes(user.role || ''))) return false
  return (user.permissions || []).includes(permission)
}

export function groupPermissions(definitions: AdminPermissionDefinition[]) {
  return definitions.reduce<Record<string, AdminPermissionDefinition[]>>((groups, permission) => {
    groups[permission.group] = groups[permission.group] || []
    groups[permission.group].push(permission)
    return groups
  }, {})
}
