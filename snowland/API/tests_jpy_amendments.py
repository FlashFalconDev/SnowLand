"""JPY differences retain the original quote and require explicit native-currency review."""
from django.test import TestCase
from rest_framework.test import APIClient
from API import tests_order_amendment_confirm as fixtures
from Resorts.models import PaymentAccount,PaymentCurrencySettings
from booking.currency import initialize_order_currency
from booking.models import OrderAmendment,OrderAmendmentEvent,NotificationDelivery
import uuid


class JpyAmendmentTests(TestCase):
    def setUp(self):
        fixtures.OrderAmendmentConfirmTests.setUp(self)
        self.config=PaymentCurrencySettings.objects.create(client=self.tenant,jpy_enabled=True,jpy_per_twd='4.5')
        self.jpy_bank=PaymentAccount.objects.create(client=self.tenant,name='QA日幣補款',currency='JPY',bank_name='QA銀行',bank_branch='QA分行',account_number='QA-JPY-ORIGINAL',account_holder='QA戶名')
        initialize_order_currency(self.group,'JPY',expected_rate='4.5')
        self.member_api=APIClient();self.member_api.force_authenticate(self.manager)
        self.member_url=f'/booking/snowland/api/member-amendments/{self.group.pk}/'
        self.staff_url=self.url.replace('amendment-quote/','amendment-balances/')

    def test_quote_and_confirm_keep_native_difference_and_original_bank_when_rate_changes(self):
        self.config.jpy_per_twd='9';self.config.save()
        self.jpy_bank.account_number='QA-CHANGED';self.jpy_bank.save()
        body=fixtures.OrderAmendmentConfirmTests.body(self)
        quote=self.api.post(self.url,{'changes':body['changes']},format='json')
        self.assertEqual(quote.status_code,200,quote.data)
        settlement=quote.data['data']['settlement']
        self.assertEqual((settlement['currency'],settlement['previous_total'],settlement['new_total'],settlement['difference_amount']),('JPY',42750,51750,9000))
        confirmed=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(confirmed.status_code,201,confirmed.data)
        self.assertEqual(confirmed.data['data']['settlement']['balance_amount'],9000)
        row=self.member_api.get(self.member_url).data['items'][0]
        self.assertEqual(row['bank_snapshot']['account_number'],'QA-JPY-ORIGINAL')
        self.assertEqual(row['bank_snapshot']['currency'],'JPY')
        self.assertEqual(row['settlement']['rate'],'4.50000000')
        self.assertEqual(row['balance_amount'],2000,'Original accounting fields remain TWD')
        badge=self.api.get(self.url.split('amendment-quote/')[0]).data['data']['amendment_balance']
        self.assertEqual(badge['settlement'],{'currency':'JPY','amount':9000})
        notice=NotificationDelivery.objects.get(template__channel='in_app').payload['in_app_body']
        self.assertIn('待收退差額：JPY ¥ 9,000',notice)
        self.assertIn('台幣計價基準',notice)
        self.assertNotIn('QA-JPY-ORIGINAL',notice)

    def test_native_topup_requires_matching_currency_and_amount_and_keeps_retry_receipt(self):
        body=fixtures.OrderAmendmentConfirmTests.body(self)
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,201)
        row=OrderAmendment.objects.get()
        def payload(action,**extra):
            row.refresh_from_db()
            return {'amendment_id':row.pk,'expected_updated_at':row.updated_at.isoformat(),'request_key':str(uuid.uuid4()),'action':action,**extra}
        missing=self.member_api.post(self.member_url,payload('report_topup',reference='12345'),format='json')
        self.assertEqual(missing.status_code,409,missing.data)
        wrong=self.member_api.post(self.member_url,payload('report_topup',reference='12345',currency='TWD',expected_amount=2000),format='json')
        self.assertEqual(wrong.status_code,409,wrong.data)
        report=payload('report_topup',reference='12345',currency='JPY',expected_amount=9000)
        self.assertEqual(self.member_api.post(self.member_url,report,format='json').status_code,200)
        self.assertEqual(self.member_api.post(self.member_url,report,format='json').status_code,200)
        unsafe=payload('confirm_topup',confirmed=True,note='QA未核幣別')
        self.assertEqual(self.api.post(self.staff_url,unsafe,format='json').status_code,409)
        confirmed=payload('confirm_topup',confirmed=True,note='QA日幣已查核',currency='JPY',expected_amount=9000)
        self.assertEqual(self.api.post(self.staff_url,confirmed,format='json').status_code,200)
        self.assertEqual(self.api.post(self.staff_url,confirmed,format='json').status_code,200)
        row.refresh_from_db();self.assertEqual(row.status,'settled')
        self.assertEqual(OrderAmendmentEvent.objects.count(),2)
        event=OrderAmendmentEvent.objects.get(action='confirm_topup')
        self.assertEqual(event.payload['settlement']['currency'],'JPY')
        self.assertEqual(event.payload['settlement']['amount'],9000)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'paid')

    def test_uncollected_topup_is_netted_in_native_currency_without_a_second_collection(self):
        first=self.api.post(self.url_confirm,fixtures.OrderAmendmentConfirmTests.body(self),format='json')
        self.assertEqual(first.status_code,201,first.data)
        body=fixtures.OrderAmendmentConfirmTests.body(self,number_of_people=1,equipment=None,retained_member_ids=[self.member.pk])
        response=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['data']['settlement']['difference_amount'],-9000)
        self.assertEqual(response.data['data']['settlement']['balance_amount'],0)
        self.assertEqual(response.data['data']['status'],'no_difference')
        self.assertEqual(OrderAmendment.objects.filter(status='superseded').count(),1)

    def test_rounding_order_totals_can_leave_no_native_cash_due_for_a_one_twd_change(self):
        self.config.jpy_per_twd='0.5';self.config.save()
        self.reservation.course_fee=9501;self.reservation.discount_amount=0;self.reservation.save()
        self.pricing.base_price_off_peak=9501;self.pricing.additional_person_fee=1;self.pricing.save()
        self.group.currency_snapshot={};self.group.save(update_fields=['currency_snapshot'])
        initialize_order_currency(self.group,'JPY',expected_rate='0.5')
        response=self.api.post(self.url_confirm,fixtures.OrderAmendmentConfirmTests.body(self),format='json')
        self.assertEqual(response.status_code,201,response.data)
        row=response.data['data']
        self.assertEqual(row['difference_amount'],1)
        self.assertEqual((row['settlement']['previous_total'],row['settlement']['new_total'],row['settlement']['balance_amount']),(4751,4751,0))
        self.assertEqual(row['status'],'no_difference')

    def test_settled_native_topup_then_refund_has_its_own_currency_receipt(self):
        self.assertEqual(self.api.post(self.url_confirm,fixtures.OrderAmendmentConfirmTests.body(self),format='json').status_code,201)
        row=OrderAmendment.objects.get()
        def payload(action,**extra):
            row.refresh_from_db()
            return {'amendment_id':row.pk,'expected_updated_at':row.updated_at.isoformat(),'request_key':str(uuid.uuid4()),
                'action':action,'currency':'JPY','expected_amount':9000,**extra}
        self.assertEqual(self.member_api.post(self.member_url,payload('report_topup',reference='12345'),format='json').status_code,200)
        self.assertEqual(self.api.post(self.staff_url,payload('confirm_topup',confirmed=True,note='QA日幣補款留底'),format='json').status_code,200)
        self.config.jpy_per_twd='9';self.config.save()
        response=self.api.post(self.url_confirm,fixtures.OrderAmendmentConfirmTests.body(self,number_of_people=1,equipment=None,retained_member_ids=[self.member.pk]),format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['data']['settlement']['balance_amount'],-9000)
        row=OrderAmendment.objects.order_by('-pk').first()
        bank={'bank_name':'QA可收日幣銀行','account_number':'QA-NOT-REAL','account_holder':'QA會員','overseas_details':'QA分行與SWIFT，非真實資料'}
        invalid=self.member_api.post(self.member_url,payload('refund_account',bank=bank,expected_amount=2000),format='json')
        self.assertEqual(invalid.status_code,409,invalid.data)
        self.assertEqual(self.member_api.post(self.member_url,payload('refund_account',bank=bank),format='json').status_code,200)
        self.assertEqual(self.member_api.get(self.member_url).data['items'][0]['refund_bank'],bank)
        unchecked=self.api.post(self.staff_url,payload('confirm_refund',confirmed=False,note='QA未確認實退'),format='json')
        self.assertEqual(unchecked.status_code,400,unchecked.data)
        confirmed=payload('confirm_refund',confirmed=True,note='QA系統外日幣退款確認')
        self.assertEqual(self.api.post(self.staff_url,confirmed,format='json').status_code,200)
        self.assertEqual(self.api.post(self.staff_url,confirmed,format='json').status_code,200)
        event=OrderAmendmentEvent.objects.get(amendment=row,action='confirm_refund')
        self.assertEqual(event.payload['settlement']['amount'],9000)
        self.assertEqual(event.payload['settlement']['currency'],'JPY')
        row.refresh_from_db();self.assertEqual(row.status,'settled')
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'paid')
