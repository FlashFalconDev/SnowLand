"""Authenticate gateway callbacks against the order's school, not a caller-selected user."""
import json
import re
from decimal import Decimal, InvalidOperation
from hmac import compare_digest
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from Client.models import Client
from Client.tenant_settings import gateway_settings
from booking.Newebpay import aes256_cbc_decrypt, sha256_hash
from booking.models import Payment, ReservationGroup


@csrf_exempt
@transaction.atomic
def call_back(request, tunnel):
    if tunnel != 'NewebPay':
        return HttpResponse('Unknown gateway',status=404)
    if request.method != 'POST':
        return HttpResponse('Method not allowed',status=405)
    code=request.GET.get('client_code') or getattr(settings,'SNOWLAND_LEGACY_PAYMENT_CLIENT_CODE','snowland')
    school=Client.objects.filter(internal_code=code).first()
    credentials=gateway_settings(school) if school else None
    if not credentials:
        return HttpResponse('Payment gateway unavailable',status=503)
    if request.POST.get('MerchantID') != credentials['MerchantID']:
        return HttpResponse('Invalid merchant',status=400)
    info=request.POST.get('TradeInfo','');signature=request.POST.get('TradeSha','')
    if not re.fullmatch(r'[0-9A-F]{64}',signature) or not compare_digest(sha256_hash(info,credentials['HashKey'],credentials['HashIV']),signature):
        return HttpResponse('Invalid signature',status=400)
    try:
        payload=json.loads(aes256_cbc_decrypt(info,credentials['HashKey'],credentials['HashIV']))
        result=payload.get('Result') or {}
        number=str(result.get('MerchantOrderNo',''))
        amount=Decimal(str(result.get('Amt','')))
        if not number.isascii() or not number.isdecimal() or not amount.is_finite() or amount<=0:
            raise ValueError('Invalid order or amount')
    except (ValueError,TypeError,InvalidOperation,AttributeError):
        return HttpResponse('Invalid payment data',status=400)
    if result.get('MerchantID',credentials['MerchantID']) != credentials['MerchantID']:
        return HttpResponse('Invalid merchant',status=400)
    if payload.get('Status') != 'SUCCESS':
        return HttpResponse('Payment not successful',status=400)
    group=ReservationGroup.objects.select_for_update().filter(pk=number,client=school).first()
    if not group:
        return HttpResponse('Order not found',status=404)
    payment=Payment.objects.select_for_update().filter(reservation_group=group).order_by('-created_at','-pk').first()
    if not payment:
        return HttpResponse('Payment not found',status=404)
    # A genuine replay after payment/refund must not mutate status, ownership or metadata.
    if payment.status in {'paid','refunded'}:
        return HttpResponse('OK')
    if (group.currency_snapshot or {}).get('currency','TWD') != 'TWD':
        return HttpResponse('Currency requires reconciliation',status=409)
    expected=group.reservations.exclude(status__in=['deleted','cancelled']).aggregate(total=Sum('payment_amount'))['total'] or 0
    if amount != Decimal(str(expected)):
        return HttpResponse('Amount requires reconciliation',status=409)
    if payment.status not in {'unpaid','pending'}:
        return HttpResponse('Payment state requires reconciliation',status=409)
    stored=dict(payment.DataJSON) if isinstance(payment.DataJSON,dict) else {}
    stored['gateway_response']=payload
    payment.status='paid';payment.payment_method='newebpay';payment.user_id=group.user_id
    payment.DataJSON=stored
    payment.save(update_fields=['status','payment_method','user','DataJSON','updated_at'])
    return HttpResponse('OK')
