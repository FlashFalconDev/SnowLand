import uuid
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from API import tests_order_amendment_confirm as fixtures
from booking.models import OrderAmendment, OrderAmendmentEvent


class AmendmentBalanceTests(TestCase):
    def setUp(self):
        fixtures.OrderAmendmentConfirmTests.setUp(self)
        body=fixtures.OrderAmendmentConfirmTests.body(self)
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,201)
        self.row=OrderAmendment.objects.get()
        self.member_api=APIClient();self.member_api.force_authenticate(self.manager)
        self.member_url=f'/booking/snowland/api/member-amendments/{self.group.pk}/'
        self.staff_url=self.url.replace('amendment-quote/','amendment-balances/')

    def payload(self,action,**values):
        self.row.refresh_from_db()
        return {'amendment_id':self.row.pk,'request_key':str(uuid.uuid4()),'expected_updated_at':self.row.updated_at.isoformat(),'action':action,**values}

    def report(self):
        response=self.member_api.post(self.member_url,self.payload('report_topup',reference='12345'),format='json')
        self.assertEqual(response.status_code,200,getattr(response,'data',None))

    def test_member_read_is_own_order_only_and_no_staff_audit_data(self):
        response=self.member_api.get(self.member_url)
        self.assertEqual(response.status_code,200,getattr(response,'data',None))
        row=response.data['items'][0];self.assertEqual(row['bank_snapshot']['account_number'],'QA-12345')
        self.assertNotIn('events',row)
        self.assertEqual(APIClient().get(self.member_url).status_code,401)
        other=APIClient();other.force_authenticate(self.superuser)
        self.assertEqual(other.get(self.member_url).status_code,404)
        self.assertEqual(self.member_api.get(self.member_url.replace('/snowland/','/other/')).status_code,404)

    def test_reporting_is_idempotent_never_marks_original_payment_or_balance_paid(self):
        body=self.payload('report_topup',reference='12345')
        first=self.member_api.post(self.member_url,body,format='json')
        again=self.member_api.post(self.member_url,body,format='json')
        self.assertEqual(first.status_code,200,getattr(first,'data',None));self.assertEqual(again.status_code,200)
        self.assertTrue(again.data['duplicate']);self.assertEqual(OrderAmendmentEvent.objects.count(),1)
        self.row.refresh_from_db();self.payment.refresh_from_db()
        self.assertEqual(self.row.status,'topup_reported');self.assertEqual(self.row.topup_reference,'12345')
        self.assertEqual(self.payment.status,'paid');self.assertIsNone(self.row.settled_at)
        self.assertEqual(self.member_api.post(self.member_url,{**body,'reference':'99999'},format='json').status_code,409)

    def test_staff_confirmation_needs_ack_and_audit_and_can_retry_same_request(self):
        self.report()
        body=self.payload('confirm_topup',confirmed=False,note='QA核對銀行紀錄')
        self.assertEqual(self.api.post(self.staff_url,body,format='json').status_code,400)
        body=self.payload('confirm_topup',confirmed=True,note='QA核對銀行紀錄')
        self.assertEqual(self.api.post(self.staff_url,body,format='json').status_code,200)
        self.assertEqual(self.api.post(self.staff_url,body,format='json').status_code,200)
        self.row.refresh_from_db();self.assertEqual(self.row.status,'settled')
        self.assertEqual(self.row.settled_by_id,self.superuser.pk);self.assertIsNotNone(self.row.settled_at)
        self.assertEqual(OrderAmendmentEvent.objects.count(),2)
        detail=self.api.get(self.staff_url);self.assertEqual(len(detail.data['data']['items'][0]['events']),2)
        order=self.api.get(self.url.split('amendment-quote/')[0]);self.assertIsNone(order.data['data']['amendment_balance'])
        self.assertEqual(self.group.payments.count(),1)

    def test_stale_version_and_wrong_role_or_scope_do_not_mutate(self):
        self.assertEqual(self.member_api.post(self.member_url,self.payload('confirm_topup',confirmed=True,note='QA不可自行核對'),format='json').status_code,403)
        body=self.payload('report_topup',reference='12345')
        self.row.reason='QA另筆修改';self.row.updated_at=self.row.updated_at.replace(year=2025);self.row.save()
        self.assertEqual(self.member_api.post(self.member_url,body,format='json').status_code,409)
        self.assertEqual(self.api.post(self.staff_url,self.payload('confirm_topup',confirmed=True,note='QA'),format='json',HTTP_X_CAMPUS_ID=str(self.campus_b.pk)).status_code,404)
        self.assertEqual(self.member_api.get(self.staff_url).status_code,403)
        self.assertEqual(OrderAmendmentEvent.objects.count(),0)

    def test_refund_account_then_manual_external_refund_ack_preserves_original_payment(self):
        self.report()
        self.assertEqual(self.api.post(self.staff_url,self.payload('confirm_topup',confirmed=True,note='QA補款已核對'),format='json').status_code,200)
        body=fixtures.OrderAmendmentConfirmTests.body(self,number_of_people=1,equipment=None,retained_member_ids=[self.member.pk])
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,201)
        self.row=OrderAmendment.objects.order_by('-pk').first()
        self.assertEqual((self.row.balance_amount,self.row.status),(-2000,'refund_account_due'))
        invalid=self.payload('refund_account',bank={'bank_name':'QA銀行','account_number':'','account_holder':'QA會員'})
        self.assertEqual(self.member_api.post(self.member_url,invalid,format='json').status_code,400)
        bank={'bank_name':'QA銀行','account_number':'QA-REFUND','account_holder':'QA會員'}
        self.assertEqual(self.member_api.post(self.member_url,self.payload('refund_account',bank=bank),format='json').status_code,200)
        self.row.refresh_from_db();self.assertEqual(self.row.status,'refund_due');self.assertEqual(self.row.refund_bank,bank)
        self.assertEqual(self.api.post(self.staff_url,self.payload('confirm_refund',confirmed=True,note='QA系統外退款核對'),format='json').status_code,200)
        self.row.refresh_from_db();self.payment.refresh_from_db()
        self.assertEqual(self.row.status,'settled');self.assertEqual(self.payment.status,'paid')
        self.assertEqual(self.member_api.post(self.member_url,self.payload('refund_account',bank=bank),format='json').status_code,409)

    def test_csrf_and_invalid_reference_or_unknown_fields_are_rejected(self):
        csrf=APIClient(enforce_csrf_checks=True);csrf.force_login(self.manager)
        self.assertEqual(csrf.post(self.member_url,self.payload('report_topup',reference='12345'),format='json').status_code,403)
        csrf.force_login(self.superuser)
        self.assertEqual(csrf.post(self.staff_url,self.payload('confirm_topup',confirmed=True,note='QA'),format='json').status_code,403)
        for extra in ({'reference':'1234'},{'reference':'abcde'},{'reference':'12345','balance_amount':0}):
            self.assertEqual(self.member_api.post(self.member_url,self.payload('report_topup',**extra),format='json').status_code,400)
        self.assertEqual(OrderAmendmentEvent.objects.count(),0)

    def test_rejected_report_keeps_audit_and_member_can_report_again(self):
        self.report()
        self.assertEqual(self.api.post(self.staff_url,self.payload('reject_topup',note='QA未查得末五碼，請重新核對'),format='json').status_code,200)
        self.row.refresh_from_db();self.assertEqual(self.row.status,'topup_due')
        read=self.member_api.get(self.member_url)
        self.assertIn('未查得',read.data['items'][0]['review_message'])
        self.report();self.assertEqual(OrderAmendmentEvent.objects.count(),3)

    def test_orders_only_assistant_can_reconcile_own_campus_without_insurance_permissions(self):
        self.report()
        self.profile.role='assistant';self.profile.admin_permissions=['orders'];self.profile.save()
        self.manager.refresh_from_db()
        staff=APIClient();staff.force_authenticate(self.manager)
        self.assertEqual(staff.get(self.staff_url).status_code,200)
        self.assertEqual(staff.post(self.staff_url,self.payload('confirm_topup',confirmed=True,note='QA校區訂單核對'),format='json').status_code,200)
        self.row.refresh_from_db();self.assertEqual(self.row.settled_by_id,self.manager.pk)

    def test_original_payment_change_or_cancellation_blocks_new_balance_operations(self):
        from booking.models import CancellationRequest
        for status in ['refunded','unpaid','pending','expired']:
            self.payment.status=status;self.payment.save()
            self.assertEqual(self.member_api.post(self.member_url,self.payload('report_topup',reference='12345'),format='json').status_code,409)
        self.payment.status='paid';self.payment.save()
        CancellationRequest.objects.create(group=self.group,reason='schedule')
        self.assertEqual(self.member_api.post(self.member_url,self.payload('report_topup',reference='12345'),format='json').status_code,409)
        self.assertEqual(OrderAmendmentEvent.objects.count(),0)
