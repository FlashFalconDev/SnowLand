"""Legacy self-service payment mail; never trusts a caller-supplied destination link."""
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .models import ReservationGroup
from .payment_access import payment_url_for_group


class PaymentEmailInput(serializers.Serializer):
    gmail = serializers.EmailField(max_length=200)
    payment_url = serializers.CharField(max_length=2048, required=False, default='', allow_blank=True)
    group_id = serializers.IntegerField(min_value=1, max_value=2**63-1, required=False)
    request_key = serializers.UUIDField(required=False)

    def validate(self, data):
        try:
            values = parse_qs(urlsplit(data['payment_url']).query).get('reservation_group', [])
            link_id = int(values[0]) if len(values) == 1 else None
            if values and (len(values) != 1 or not 0 < link_id < 2**63):
                raise ValueError
            if 'group_id' in data and link_id is not None and data['group_id'] != link_id:
                raise ValueError
            data['group_id'] = data.get('group_id') or link_id
            if not data['group_id']:
                raise ValueError
        except (TypeError, ValueError):
            raise serializers.ValidationError('請提供正確的訂單編號')
        return data


class PaymentEmailAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return send_payment_email(request)


def send_payment_email(request):
    if request.method != 'POST':
        return JsonResponse({'message': '只接受寄信請求'}, status=405)
    # The old universal API decorator accepts a legacy identity header. It is not authentication here.
    if not request.user.is_authenticated:
        return JsonResponse({'message': '請先登入'}, status=401)
    SessionAuthentication().enforce_csrf(request)
    form = PaymentEmailInput(data=request.data)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    group = ReservationGroup.objects.select_related('client', 'campus', 'user').filter(
        pk=data['group_id'], user=request.user, client__is_active=True,
    ).first()
    if group is None:
        return JsonResponse({'message': '找不到您的訂單'}, status=404)
    payment = group.payments.order_by('-created_at', '-pk').first()
    from .api_views import get_group_payment_hold
    hold, _ = get_group_payment_hold(group)
    payable = sum(reservation.payment_amount for reservation in group.reservations.exclude(status__in=['cancelled', 'deleted']))
    if hold or not payment or payment.status != 'unpaid' or payable <= 0:
        return JsonResponse({'message': hold or '這張訂單目前不需付款，請到會員訂單查看最新狀態'}, status=409)
    from API.order_email_notifications import sync_accounts, prepare_email, deliver_order_email
    if sync_accounts(group, data['gmail']) != [request.user.pk]:
        return JsonResponse({'message': '只能寄到您的會員信箱或這張訂單的聯絡信箱'}, status=403)
    public_url = settings.SNOWLAND_PUBLIC_PAYMENT_URL
    try:
        URLValidator(schemes=['http', 'https'])(public_url)
        parts = urlsplit(public_url)
        parts.port  # Reject malformed port numbers before creating any mail receipt.
        local_http = parts.scheme == 'http' and parts.hostname in {'localhost', '127.0.0.1', '::1'}
        if (not parts.netloc or not parts.hostname or (parts.scheme != 'https' and not local_http)
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path.rstrip('/') != f'/{group.client.internal_code}/payment'):
            raise ValueError
    except (ValueError, TypeError, ValidationError):
        return JsonResponse({'message': '付款頁網址尚未完成設定，請聯絡客服'}, status=503)
    mail_data = {'recipient_email': data['gmail'], 'subject': '滑雪課程預約付款連結',
        'message': '您的課程訂單尚待付款，請登入查看訂單與最新付款狀態：\n'
                   + payment_url_for_group(public_url, group)}
    if data.get('request_key'):
        mail_data['request_key'] = data['request_key']
    delivery_id = prepare_email(SimpleNamespace(tenant=group.client, user=request.user), group, mail_data)
    code, result = deliver_order_email(delivery_id)
    # Old clients treat every 2xx as "sent". An unconfirmed send must not look successful there.
    response_code = 409 if code == 202 else code
    return JsonResponse({**result, 'code': response_code, 'message': result['msg'],
                         'result': 'ok' if code == 200 else 'pending' if code == 202 else 'error'}, status=response_code)
