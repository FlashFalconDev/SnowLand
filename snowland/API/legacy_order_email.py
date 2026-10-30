from Control.tenant_memberships import staff_profile, writable_staff_profile
"""Keep the old form response contract, but never its header-based identity shortcut."""
from django.http import JsonResponse
from booking.models import ReservationGroup
from .admin_permissions import user_has_admin_permission


def order_email_response(request, group_id):
    if not request.user.is_authenticated:
        return JsonResponse({'code': 401, 'msg': '請先登入'}, status=401)
    if not user_has_admin_permission(request.user, 'orders', getattr(request, 'tenant', None)):
        return JsonResponse({'code': 403, 'msg': '需要訂單管理權限'}, status=403)
    try:
        group_id = int(group_id)
        if not 0 < group_id < 2**63:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({'code': 400, 'msg': '請提供正確的訂單編號'}, status=400)
    group = ReservationGroup.objects.select_related('client').filter(pk=group_id).first()
    if not group or not group.client:
        return JsonResponse({'code': 404, 'msg': '找不到訂單'}, status=404)
    from .admin_views import send_order_email
    response = send_order_email(request, client_code=group.client.internal_code, order_id=group.pk)
    body = response.data
    if response.status_code == 200:
        return JsonResponse({**body, 'code': 100, 'success': True, 'message': body.get('msg', 'OK')})
    message = body.get('msg') or body.get('detail') or '請核對輸入資料與目前校區權限'
    return JsonResponse({**body, 'code': response.status_code, 'success': False,
                         'msg': str(message), 'message': str(message)}, status=response.status_code)
