import uuid
from types import SimpleNamespace
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.views import APIView
from PIL import Image
from .media_files import validate_course_upload, private_file_response
from .models import ReservationGroup, MemberDetail, NotificationDelivery


def group_qr_url(group):
    if not group.line_group_qr:
        return ''
    return reverse('booking:api_class_group_qr_client', kwargs={
        'client_code': group.client.internal_code, 'group_id': group.pk,
    }) + '?v=' + group.line_group_qr.name.rsplit('/', 1)[-1]


def paid_group_qr_url(group):
    payment = group.payments.order_by('-created_at', '-pk').first()
    if not payment or payment.status != 'paid' or not group.reservations.exclude(status__in=['cancelled', 'deleted']).exists():
        return ''
    return group_qr_url(group)


def replace_group_qr(group, upload=None):
    extension = None
    if upload:
        if upload.size > 5 * 1024 * 1024:
            raise ValueError('群組 QR 碼圖片不可超過 5 MB')
        media_type, extension = validate_course_upload(upload)
        if media_type != 'photo':
            raise ValueError('請上傳 PNG、JPEG 或 WebP 的 QR 碼圖片，不接受影片')
        image = Image.open(upload)
        if max(image.size) > 4096:
            upload.seek(0)
            raise ValueError('QR 碼圖片長寬不可超過 4096 像素')
        upload.seek(0)
    new_name = None
    storage = group.line_group_qr.storage
    try:
        with transaction.atomic():
            locked = ReservationGroup.objects.select_for_update().get(pk=group.pk)
            old_name = locked.line_group_qr.name
            if upload:
                locked.line_group_qr.save(f'{group.client_id}/{group.pk}/{uuid.uuid4().hex}{extension}', upload, save=False)
                new_name = locked.line_group_qr.name
            else:
                locked.line_group_qr = ''
            locked.save(update_fields=['line_group_qr'])
            if not locked.line_group_qr and not locked.line_group_url:
                NotificationDelivery.objects.filter(group=locked, template__event='line_group', status='scheduled').update(status='cancelled')
            if old_name:
                transaction.on_commit(lambda: storage.delete(old_name), robust=True)
            return locked
    except Exception:
        if new_name:
            storage.delete(new_name)
        raise


class ClassGroupQRAPI(APIView):
    permission_key = 'orders'

    def get(self, request, client_code, group_id):
        if not request.user.is_authenticated:
            return Response({'error': '請先登入'}, status=401)
        group = get_object_or_404(ReservationGroup.objects.select_related('client'),
                                 pk=group_id, client__internal_code=client_code, client__is_active=True)
        allowed = False
        profile = getattr(request.user, 'userprofile', None)
        if request.user.is_superuser or (profile and profile.is_manager):
            from API.admin_views import IsTenantManager
            from API.admin_permissions import user_has_admin_permission
            if (not profile or profile.role not in {'campus_principal', 'campus_manager'}) and user_has_admin_permission(request.user, 'orders'):
                if IsTenantManager().has_permission(request, self):
                    allowed = (request.can_view_all_campuses and request.selected_campus_id is None) or group.campus_id in request.campus_ids
        if not allowed and paid_group_qr_url(group):
            allowed = group.user_id == request.user.pk or MemberDetail.objects.filter(
                Q(user=request.user) | Q(guardian=request.user), reservation__group=group,
            ).exclude(reservation__status__in=['cancelled', 'deleted']).exists()
        if not allowed or not group.line_group_qr:
            return Response({'error': '找不到上課群組 QR 碼'}, status=404)
        try:
            return private_file_response(SimpleNamespace(file=group.line_group_qr))
        except OSError:
            return Response({'error': '找不到上課群組 QR 碼'}, status=404)
