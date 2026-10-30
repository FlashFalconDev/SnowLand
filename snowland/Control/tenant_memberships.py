"""Resolve school authority without mutating global login/userprofile state."""
from types import SimpleNamespace
from .models import TenantStaffMembership


def staff_profile(user, tenant=None):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    legacy = getattr(user, 'userprofile', None)
    if tenant is None:
        return legacy
    current = TenantStaffMembership.objects.filter(client=tenant, user=user).first()
    if current is not None:
        return current  # An explicit revoked membership must never fall back.
    if legacy and legacy.is_manager and legacy.manager_client_id == tenant.pk:
        return legacy  # Compatibility during migration / existing imports.
    if legacy and legacy.is_coach:
        from Coach.models import Coach
        coach = Coach.objects.filter(client=tenant, user=user).first()
        if coach:
            return SimpleNamespace(is_manager=False, is_coach=True, role='coach',
                admin_permissions=[], manager_client_id=None, campuses=coach.campuses)
    return None


def writable_staff_profile(user, tenant):
    """Materialize only this school's membership, never reassign another school."""
    current = staff_profile(user, tenant)
    defaults = {
        'is_manager': bool(current and current.is_manager),
        'is_coach': bool(current and current.is_coach),
        'role': current.role if current else '',
        'admin_permissions': current.admin_permissions if current else [],
    }
    existing = TenantStaffMembership.objects.filter(client=tenant,user=user).first()
    return existing or TenantStaffMembership(client=tenant,user=user,**defaults)
