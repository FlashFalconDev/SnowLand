"""Keep the old request/response shape, but use the current payment rules."""
from django.http import JsonResponse
from rest_framework import serializers

from .models import ReservationGroup
from .payment_access import can_access_payment


class LegacyPaymentRequest:
    def __init__(self, original, data):
        self.original=original
        self.data=data

    def __getattr__(self, name):
        return getattr(self.original,name)


def process_legacy_payment(request):
    if request.method != 'POST':
        return JsonResponse({'error':'只接受付款回報請求'},status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'error':'請先登入'},status=401)
    try:
        group_id=serializers.IntegerField(min_value=1,max_value=2**63-1).run_validation(request.data.get('reservation_group_pk'))
    except serializers.ValidationError:
        return JsonResponse({'error':'請提供正確的訂單編號'},status=400)
    group=ReservationGroup.objects.select_related('client').filter(pk=group_id).first()
    if not group or not group.client_id or not can_access_payment(group,request.user,request.data.get('access_token','')):
        return JsonResponse({'error':'找不到預約群組'},status=404)
    from .api_views import ProcessPaymentAPI
    method=request.data.get('paymentType')
    payload={
        'reservation_group_id':group_id,
        'payment_type':{'TT':'bank_transfer','newebpay':'newebpay'}.get(method) if isinstance(method,str) else None,
        'sender_account':request.data.get('senderAccount'),
        'access_token':request.data.get('access_token',''),
    }
    # Keep the original session/CSRF context; only legacy field names are adapted.
    # Ownership and state are re-read under the shared handler's client/order locks.
    response=ProcessPaymentAPI().post(LegacyPaymentRequest(request,payload),client_code=group.client.internal_code)
    if response.status_code != 200:
        return JsonResponse(response.data,status=response.status_code)
    return JsonResponse({'message':'Payment confirmed',**({'html':response.data['html']} if 'html' in response.data else {})})
