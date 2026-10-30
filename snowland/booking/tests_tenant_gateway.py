import json
from decimal import Decimal
from unittest.mock import patch
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from django.contrib.auth.models import User
from django.test import TestCase
from Client.models import Client
from booking.Newebpay import sha256_hash
from booking.models import ReservationGroup, Reservation, Payment


class TenantGatewayTests(TestCase):
    def setUp(self):
        self.a=Client.objects.create(name='A',internal_code='school-a',payment_env_prefix='SCHOOL_A')
        self.b=Client.objects.create(name='B',internal_code='school-b',payment_env_prefix='SCHOOL_B')
        self.user=User.objects.create_user('owner')
        self.group=ReservationGroup.objects.create(client=self.a,user=self.user)
        self.reservation=Reservation.objects.create(group=self.group,course_fee=1000)
        self.payment=Payment.objects.create(reservation_group=self.group,DataJSON={'original':'keep'})
        self.credentials={'MerchantID':'A-merchant','HashKey':'K'*32,'HashIV':'I'*16}

    def notify(self,school='school-a',amount=1000,order=None,signature=None):
        result={'MerchantOrderNo':str(order or self.group.pk),'Amt':amount,'MerchantID':'A-merchant','TradeNo':'QA-ONLY'}
        plain=json.dumps({'Status':'SUCCESS','Result':result}).encode()
        info=AES.new(b'K'*32,AES.MODE_CBC,iv=b'I'*16).encrypt(pad(plain,32)).hex()
        data={'MerchantID':'A-merchant','TradeInfo':info,'TradeSha':signature or sha256_hash(info,'K'*32,'I'*16)}
        with patch('booking.call_back.gateway_settings',return_value=self.credentials):
            return self.client.post('/call_back/NewebPay/?client_code='+school+'&user_id=999999',data)

    def test_signed_callback_uses_school_order_owner_and_keeps_original_metadata(self):
        result=self.notify()
        self.assertEqual(result.status_code,200,result.content)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status,'paid')
        self.assertEqual(self.payment.user_id,self.user.pk)
        self.assertEqual(self.payment.DataJSON['original'],'keep')
        self.assertEqual(self.payment.DataJSON['gateway_response']['Result']['Amt'],1000)

    def test_another_school_cannot_claim_order_even_with_valid_signature(self):
        self.assertEqual(self.notify(school='school-b').status_code,404)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'unpaid')

    def test_invalid_signature_or_changed_amount_never_marks_paid(self):
        for signature in ['BAD','非合法簽章']:
            self.assertEqual(self.notify(signature=signature).status_code,400)
        self.assertEqual(self.notify(amount=999).status_code,409)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'unpaid')

    def test_repeated_callback_never_restores_refunded_payment(self):
        self.assertEqual(self.notify().status_code,200)
        self.payment.refresh_from_db();snapshot=self.payment.DataJSON.copy()
        self.payment.status='refunded';self.payment.save()
        self.assertEqual(self.notify().status_code,200)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'refunded')
        self.assertEqual(self.payment.DataJSON,snapshot)

    def test_jpy_or_expired_payment_requires_manual_reconciliation(self):
        self.group.currency_snapshot={'currency':'JPY'};self.group.save()
        self.assertEqual(self.notify().status_code,409)
        self.group.currency_snapshot={};self.group.save()
        self.payment.status='expired';self.payment.save()
        self.assertEqual(self.notify().status_code,409)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'expired')
