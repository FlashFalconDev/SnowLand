from django.db import transaction
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from Client.models import Client
from Control.models import TenantStaffPosition, UserProfile
from Resorts.models import Campus

from .admin_permissions import ADMIN_PERMISSION_KEYS, ROLE_DEFAULT_PERMISSIONS, normalize_admin_permissions, user_has_admin_permission
from .admin_views import IsTenantManager, _require_headquarters


COACH_POSITION_ID = 0
RESTRICTED_ROLES = {'hq_admin', 'campus_principal', 'campus_manager', 'assistant', 'photographer', 'coach'}
HEADQUARTERS_ONLY = {'member_loyalty', 'social_sync', 'staff', 'order_export', 'site_tracking', 'checkout_policies'}
CAMPUS_ORDER_RESTRICTIONS = {'order_edit', 'order_payments', 'order_refunds'}


def usable_permissions(permissions, role, all_campuses):
    blocked = set()
    if role not in {'hq_admin', 'campus_principal', 'campus_manager'}:
        blocked.add('vehicle_review')
    if role not in {'hq_admin', 'assistant'}:
        blocked.add('vehicle_finance')
    if role != 'hq_admin' or not all_campuses:
        blocked.update(HEADQUARTERS_ONLY)
    if role in {'campus_manager', 'campus_principal'}:
        blocked.update(CAMPUS_ORDER_RESTRICTIONS)
    if not all_campuses or role in {'campus_manager', 'campus_principal', 'coach', 'photographer'}:
        blocked.add('contact_inbox')
    if not all_campuses:
        blocked.add('recruitment')
    return [key for key in normalize_admin_permissions(permissions) if key not in blocked]


def position_permissions(position):
    permissions = position.permissions
    if permissions is None:
        permissions = ADMIN_PERMISSION_KEYS if position.role in ('', 'hq_admin') else ROLE_DEFAULT_PERMISSIONS.get(position.role, [])
    return usable_permissions(permissions, position.role, position.all_campuses)


def position_access(positions, is_coach):
    roles = {position.role for position in positions} & RESTRICTED_ROLES
    if len(roles) > 1:
        raise ValidationError({'msg': '所選職位的管理規則不同，請只選一種管理職務，再搭配其他職位。'})

    # The existing request scope is shared by all pages. Intersect limited scopes to avoid widening another position.
    scopes = [set(position.campuses.filter(client_id=position.client_id).values_list('id', flat=True)) for position in positions if not position.all_campuses]
    campuses = set.intersection(*scopes) if scopes else set()
    if len(scopes) > 1 and not campuses:
        raise ValidationError({'msg': '所選職位沒有共同校區，請選擇校區相容的職位。'})
    role = next(iter(roles), positions[0].role if positions else ('coach' if is_coach else ''))
    if len(positions) == 1:
        permissions = positions[0].permissions
    else:
        permissions = usable_permissions(
            [key for position in positions for key in position_permissions(position)], role, not scopes,
        )
    return {
        'is_manager': bool(positions), 'is_coach': is_coach, 'role': role,
        'admin_permissions': permissions, 'all_campuses': not scopes if positions else None,
    }, campuses


def apply_position_access(profile, positions, is_coach):
    # Existing views continue to read the school membership's effective grants and campus scope.
    values, campuses = position_access(positions, is_coach)
    for field, value in values.items():
        setattr(profile, field, value)
    profile.save()
    profile.campuses.set(campuses)


def assign_staff_positions(request, profile, raw_ids):
    if not isinstance(raw_ids, list) or any(type(value) is not int or value < 0 for value in raw_ids):
        raise ValidationError({'msg': '職位必須是有效的清單。'})
    ids = set(raw_ids) - {COACH_POSITION_ID}
    positions = list(TenantStaffPosition.objects.filter(client=request.tenant, pk__in=ids).order_by('id'))
    if len(positions) != len(ids):
        raise ValidationError({'msg': '所選職位不存在或不屬於這個租戶。'})
    apply_position_access(profile, positions, COACH_POSITION_ID in raw_ids)
    profile.positions.set(positions)


def position_payload(position):
    return {
        'id': position.pk, 'name': position.name, 'built_in': False,
        'settings': {
            'name': position.name, 'role': position.role, 'permissions': position_permissions(position),
            'all_campuses': position.all_campuses, 'campus_ids': list(position.campuses.values_list('id', flat=True)),
        },
    }


@api_view(['GET', 'POST'])
@permission_classes([IsTenantManager])
@transaction.atomic
def staff_positions(request, client_code):
    require_position_management(request)
    positions = TenantStaffPosition.objects.filter(client=request.tenant)
    if request.method == 'GET':
        get_token(request._request)
        coach = {'id': COACH_POSITION_ID, 'name': '教練', 'role': 'coach', 'built_in': True}
        return Response({'code': 200, 'data': [coach, *(position_payload(p) for p in positions.order_by('name', 'id'))]})
    SessionAuthentication().enforce_csrf(request)
    Client.objects.select_for_update().get(pk=request.tenant.pk)
    position = save_position(request, TenantStaffPosition(client=request.tenant))
    return Response({'code': 201, 'data': position_payload(position)}, status=201)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsTenantManager])
@transaction.atomic
def staff_position_detail(request, client_code, position_id):
    require_position_management(request)
    SessionAuthentication().enforce_csrf(request)
    Client.objects.select_for_update().get(pk=request.tenant.pk)
    position = get_object_or_404(TenantStaffPosition, client=request.tenant, pk=position_id)
    members = position.memberships.filter(client=request.tenant).order_by('pk')
    if request.method == 'DELETE':
        if members.exists():
            raise ValidationError({'msg': '仍有員工使用此職位，請先改派員工。'})
        position.delete()
        return Response(status=204)
    position = save_position(request, position)
    for profile in members:
        try:
            apply_position_access(profile, list(profile.positions.order_by('id')), profile.is_coach)
        except ValidationError as error:
            raise ValidationError({'msg': f'此變更會與已指派員工的其他職位衝突。{error.detail["msg"]}'}) from error
    return Response({'code': 200, 'data': position_payload(position)})


def require_position_management(request):
    if not user_has_admin_permission(request.user, 'staff', request.tenant):
        raise PermissionDenied('沒有員工與權限管理權限。')
    _require_headquarters(request)


def save_position(request, position):
    data = request.data
    name = data.get('name')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100 or name.strip() in {'教練', '最大管理員', '平台最高管理員'}:
        raise ValidationError({'msg': '請輸入 1 至 100 個字的職位名稱，並避開保留名稱。'})
    role = data.get('role')
    allowed_roles = {key for key, _ in UserProfile.ROLE_CHOICES} - {'coach'}
    if position.role == 'coach':
        allowed_roles.add('coach')
    if not isinstance(role, str) or role not in ({''} | allowed_roles):
        raise ValidationError({'msg': '工作職務類型不正確。'})
    if TenantStaffPosition.objects.filter(client=request.tenant, name=name.strip()).exclude(pk=position.pk).exists():
        raise ValidationError({'msg': '已有同名職位。'})
    all_campuses = data.get('all_campuses')
    ids = data.get('campus_ids')
    if type(all_campuses) is not bool or not isinstance(ids, list) or any(type(value) is not int for value in ids):
        raise ValidationError({'msg': '請選擇職位可查看的校區。'})
    if all_campuses == bool(ids):
        raise ValidationError({'msg': '請選擇全部校區或至少一個指定校區。'})
    campuses = list(Campus.objects.filter(client=request.tenant, id__in=ids, is_active=True))
    if len(campuses) != len(set(ids)):
        raise ValidationError({'msg': '所選校區未啟用或不屬於這個租戶。'})
    raw_permissions = data.get('permissions')
    if not isinstance(raw_permissions, list):
        raise ValidationError({'msg': '請選擇職位可使用的分頁。'})
    position.name = name.strip()
    position.role = role
    position.all_campuses = all_campuses
    position.permissions = usable_permissions(raw_permissions, role, all_campuses)
    position.save()
    position.campuses.set(campuses)
    return position
