from django.test import TestCase
from django.utils import timezone
from API import tests_jpy_amendments as fixtures
from API import tests_order_amendment_confirm as amendment_fixtures
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

    def manual_request(self,clear_receipt=True):
        if clear_receipt:
            self.payment.DataJSON={};self.payment.save(update_fields=['DataJSON'])
        result=self.member_api.post(self.member_cancel,{'reason':'schedule','bank_name':'QA銀行','account_number':'QA-REFUND',
            'account_holder':'QA會員','currency':'JPY','expected_refund_amount':None},format='json')
        self.assertEqual(result.status_code,201,result.data)
        return f'/api/admin/snowland/cancellations/{result.data["id"]}/process/'

    def manual_body(self,**changes):
        return {'status':'approved','currency':'JPY','expected_refund_amount':21000,
            'actual_received_currency_amount':42750,'refund_currency_amount':21000,
            'actual_received_amount':9500,'refund_amount':4667,
            'cash_review_note':'QA核對原實收紀錄，依原實收比例沖回台幣帳務','confirmed_received':True,**changes}

    def test_manual_native_refund_and_twd_bookkeeping_are_independently_reviewed_and_frozen(self):
        process=self.manual_request()
        approved=self.api.post(process,self.manual_body(),format='json')
        self.assertEqual(approved.status_code,200,approved.data)
        detail=self.api.get(process.replace('process/',''))
        self.assertEqual(detail.data['actual_received_amount'],9500)
        self.assertEqual(detail.data['refund_amount'],4667,'Use original receipt ratio with HALF_UP rounding, not current FX')
        native=detail.data['currency_snapshot']
        self.assertEqual(native['actual_received_amount'],42750)
        self.assertEqual(native['refund_amount'],21000)
        self.assertEqual(native['cash_review']['accounting_mode'],'original_receipt_ratio')
        self.assertEqual(native['cash_review']['refund_base_amount'],4667)
        self.config.jpy_per_twd='9';self.config.save()
        member=self.member_api.get('/booking/snowland/api/member-center/').data['orders'][0]['cancellation']['settlement']
        self.assertEqual(member['refund_amount'],21000)
        self.assertNotIn('cash_review',member)
        body={'status':'refunded','currency':'JPY','expected_refund_amount':21000,'confirmed_refund':True}
        changed=self.api.post(process,{**body,'refund_amount':999},format='json')
        self.assertEqual(changed.status_code,400,changed.data)
        finished=self.api.post(process,body,format='json')
        self.assertEqual(finished.status_code,200,finished.data)
        self.assertEqual(finished.data['data']['refund_amount'],4667)
        self.assertEqual(finished.data['data']['currency_snapshot']['refund_receipt']['amount'],21000)

    def test_manual_review_requires_both_currency_amounts_and_rejects_over_refund_without_partial_write(self):
        process=self.manual_request()
        invalid=[self.manual_body(refund_amount=4001),self.manual_body(actual_received_currency_amount=0,refund_currency_amount=0,expected_refund_amount=0,refund_amount=0),self.manual_body(actual_received_currency_amount=True),self.manual_body(refund_currency_amount=42751,expected_refund_amount=42751),
            self.manual_body(refund_currency_amount=-1),self.manual_body(refund_currency_amount=1.5),self.manual_body(actual_received_currency_amount=9007199254740992),
            self.manual_body(expected_refund_amount=20999),self.manual_body(currency='TWD'),self.manual_body(confirmed_received=False),self.manual_body(cash_review_note='')]
        missing=self.manual_body();missing.pop('actual_received_currency_amount');invalid.append(missing)
        for body in invalid:
            result=self.api.post(process,body,format='json')
            self.assertEqual(result.status_code,400,result.data)
            detail=self.api.get(process.replace('process/','')).data
            self.assertEqual(detail['status'],'requested');self.assertIsNone(detail['actual_received_amount'])
            self.assertIsNone(detail['currency_snapshot']['refund_amount'])

    def test_unreceived_native_topup_is_cancelled_only_after_reviewed_refund_without_double_count(self):
        body=amendment_fixtures.OrderAmendmentConfirmTests.body(self)
        created=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(created.status_code,201,created.data)
        process=self.manual_request(clear_receipt=False)
        requested=self.api.get(process.replace('process/','')).data
        self.assertIsNone(requested['currency_snapshot']['refund_amount'])
        self.assertEqual(requested['cash_review_snapshot']['outstanding_amendments'][0]['currency_snapshot']['balance_amount'],9000)
        self.assertEqual(self.api.post(process,self.manual_body(),format='json').status_code,200)
        result=self.api.post(process,{'status':'refunded','currency':'JPY','expected_refund_amount':21000,'confirmed_refund':True},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.data['data']['actual_received_amount'],9500)
        self.assertEqual(result.data['data']['currency_snapshot']['actual_received_amount'],42750)
        self.assertEqual(result.data['data']['refund_amount'],4667)
        self.assertEqual(self.api.get(self.staff_url).data['data']['items'][0]['status'],'cancelled')

    def test_full_native_refund_reverses_exact_original_base_receipt(self):
        process=self.manual_request()
        result=self.api.post(process,self.manual_body(refund_currency_amount=42750,expected_refund_amount=42750,refund_amount=9500),format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.data['data']['refund_amount'],9500)

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
        self.assertEqual(created.data['data']['refund_amount'],0,'No native refund means no TWD cash-accounting reversal')
