from django.test import TestCase
from django.utils import timezone
from API import tests_jpy_amendments as fixtures
from Resorts.models import OperatingPolicy
from booking.currency import order_settlement
from booking.models import CancellationRequest


class JpyCancellationTests(TestCase):
    def setUp(self):
        fixtures.JpyAmendmentTests.setUp(self)
        OperatingPolicy.objects.update_or_create(client=self.tenant,campus=self.campus_a,
            defaults={'cancellation_rules':[{'days_before':0,'refund_percent':80}],'cancellation_fee_percent':5})
        self.payment.DataJSON={'settlement':{**order_settlement(self.group),'confirmed_at':timezone.now().isoformat(),'confirmed_by_id':self.superuser.pk}}
        self.payment.save(update_fields=['DataJSON'])
        self.member_cancel=f'/booking/snowland/api/member-cancellations/{self.group.pk}/'

    def test_native_preview_and_request_freeze_original_rate_and_policy_amount(self):
        preview=self.member_api.get(self.member_cancel)
        self.assertEqual(preview.status_code,200,preview.data)
        self.assertEqual(preview.data['refund_amount'],7125)
        self.assertEqual(preview.data['settlement']['refund_amount'],32063)
        self.assertEqual(preview.data['settlement']['original_amount'],42750)
        self.config.jpy_per_twd='9';self.config.save()
        request=self.member_api.post(self.member_cancel,{'reason':'schedule','bank_name':'QA日幣銀行',
            'account_number':'QA-NOT-REAL','account_holder':'QA會員','currency':'JPY','expected_refund_amount':32063,
            'refund_amount':999999},format='json')
        self.assertEqual(request.status_code,201,request.data)
        self.assertEqual(request.data['settlement']['rate'],'4.50000000')
        self.assertEqual(request.data['settlement']['refund_amount'],32063)

    def test_approval_and_refund_require_same_native_quote_and_keep_private_audit(self):
        result=self.member_api.post(self.member_cancel,{'reason':'schedule','bank_name':'QA銀行','account_number':'QA-REFUND',
            'account_holder':'QA會員','currency':'JPY','expected_refund_amount':32063},format='json')
        self.assertEqual(result.status_code,201,result.data)
        process=f'/api/admin/snowland/cancellations/{result.data["id"]}/process/'
        missing=self.api.post(process,{'status':'approved'},format='json')
        self.assertEqual(missing.status_code,400,missing.data)
        wrong=self.api.post(process,{'status':'approved','currency':'JPY','expected_refund_amount':32062},format='json')
        self.assertEqual(wrong.status_code,400,wrong.data)
        approved=self.api.post(process,{'status':'approved','currency':'JPY','expected_refund_amount':32063},format='json')
        self.assertEqual(approved.status_code,200,approved.data)
        OperatingPolicy.objects.filter(client=self.tenant,campus=self.campus_a).update(cancellation_rules=[{'days_before':0,'refund_percent':100}],cancellation_fee_percent=0)
        self.config.jpy_per_twd='9';self.config.save()
        after=self.member_api.get(self.member_cancel)
        self.assertEqual(after.status_code,200,after.data)
        self.assertEqual(after.data['settlement']['refund_amount'],32063)
        self.assertEqual(after.data['settlement']['original_amount'],42750)
        public=self.member_api.get('/booking/snowland/api/member-center/').data['orders'][0]['cancellation']['settlement']
        self.assertEqual(public['refund_amount'],32063)
        self.assertNotIn('approval',public)
        native={'status':'refunded','currency':'JPY','expected_refund_amount':32063}
        self.assertEqual(self.api.post(process,native,format='json').status_code,400)
        finished=self.api.post(process,{**native,'confirmed_refund':True},format='json')
        self.assertEqual(finished.status_code,200,finished.data)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'refunded')
        cancellation=CancellationRequest.objects.get()
        self.assertEqual(cancellation.currency_snapshot['refund_receipt']['amount'],32063)
        self.assertEqual(cancellation.currency_snapshot['refund_receipt']['currency'],'JPY')
        self.assertEqual(self.api.post(process,{**native,'confirmed_refund':True},format='json').status_code,400)

    def test_stale_or_missing_native_quote_cannot_create_cancellation(self):
        bank={'reason':'schedule','bank_name':'QA銀行','account_number':'QA-REFUND','account_holder':'QA會員'}
        for extra in ({},{'currency':'TWD','expected_refund_amount':7125},{'currency':'JPY','expected_refund_amount':32062}):
            response=self.member_api.post(self.member_cancel,{**bank,**extra},format='json')
            self.assertEqual(response.status_code,400,response.data)
            self.assertFalse(CancellationRequest.objects.exists())

    def test_missing_native_receipt_is_not_quoted_as_received_or_refunded(self):
        self.payment.DataJSON={};self.payment.save(update_fields=['DataJSON'])
        result=self.member_api.get(self.member_cancel)
        self.assertEqual(result.status_code,200,result.data)
        self.assertTrue(result.data['requires_cash_review'])
        self.assertIsNone(result.data['settlement']['refund_amount'])
        self.assertIsNone(result.data['refund_amount'])

    def test_manual_twd_basis_can_round_to_zero_yen_without_claiming_a_transfer(self):
        from booking.currency import initialize_order_currency
        self.config.jpy_per_twd='0.01';self.config.save()
        self.group.currency_snapshot={};self.group.save(update_fields=['currency_snapshot'])
        initialize_order_currency(self.group,'JPY',expected_rate='0.01')
        self.payment.DataJSON={'settlement':{**order_settlement(self.group),'confirmed_at':timezone.now().isoformat()}}
        self.payment.save(update_fields=['DataJSON'])
        created=self.api.post(self.url.split('amendment-quote/')[0]+'cancel/',{'reason':'other','manual_refund_amount':1,
            'refund_bank':{'bank_name':'QA銀行','account_number':'QA-ONLY','account_holder':'QA會員'},'currency':'JPY','expected_refund_amount':0},format='json')
        self.assertEqual(created.status_code,200,created.data)
        self.assertEqual(created.data['data']['currency_snapshot']['refund_amount'],0)
        self.assertEqual(created.data['data']['refund_amount'],1)
