from django.test import TestCase
from rest_framework.test import APIClient
from API import tests_order_amendment_confirm as fixtures
from booking.models import CancellationRequest,OrderAmendment
from booking.operations import calculate_refund,request_cancellation


class CancellationCashReviewTests(TestCase):
    def setUp(self):
        fixtures.OrderAmendmentConfirmTests.setUp(self)
        body=fixtures.OrderAmendmentConfirmTests.body(self)
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,201)
        self.bank_data={'bank_name':'QA銀行','account_number':'QA-REFUND','account_holder':'QA會員'}
        self.member_api=APIClient();self.member_api.force_authenticate(self.manager)
        self.member_url=f'/booking/snowland/api/member-cancellations/{self.group.pk}/'

    def request_cancel(self):
        result=request_cancellation(self.group,reason='schedule',bank=self.bank_data,user=self.manager,require_paid=True)
        self.process_url=f'/api/admin/snowland/cancellations/{result.pk}/process/'
        return result

    def review(self,**changes):
        return {'status':'approved','actual_received_amount':9500,'refund_amount':7000,
            'cash_review_note':'QA核對原匯款，補款未入帳','confirmed_received':True,**changes}

    def test_all_unsettled_statuses_suppress_automatic_refund(self):
        row=OrderAmendment.objects.get()
        for state,amount in [('topup_due',2000),('topup_reported',2000),('refund_account_due',-2000),('refund_due',-2000)]:
            row.status=state;row.balance_amount=amount;row.save()
            result=self.member_api.get(self.member_url)
            self.assertEqual(result.status_code,200,result.data)
            self.assertTrue(result.data['requires_cash_review']);self.assertIsNone(result.data['refund_amount'])
            self.assertTrue(result.data['requires_bank_account'])

    def test_member_request_keeps_order_and_never_promises_unreceived_refund(self):
        result=self.member_api.post(self.member_url,{'reason':'schedule',**self.bank_data,'refund_amount':999999,'actual_received_amount':999999},format='json')
        self.assertEqual(result.status_code,201,result.data)
        self.assertIsNone(result.data['refund_amount'])
        row=CancellationRequest.objects.get();self.assertTrue(row.requires_cash_review)
        self.assertIsNone(row.actual_received_amount);self.assertEqual(row.refund_amount,0)
        self.assertEqual(row.cash_review_snapshot['outstanding_amendments'][0]['balance_amount'],2000)
        self.reservation.refresh_from_db();self.assertNotEqual(self.reservation.status,'cancelled')
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'paid')

    def test_approval_requires_actual_receipt_note_ack_and_bounded_refund(self):
        row=self.request_cancel()
        invalid=[{'status':'approved'},self.review(confirmed_received=False),self.review(refund_amount=9501),self.review(actual_received_amount=-1),self.review(refund_amount=1.5),self.review(actual_received_amount=True),self.review(cash_review_note='')]
        for body in invalid:
            self.assertEqual(self.api.post(self.process_url,body,format='json').status_code,400,body)
            row.refresh_from_db();self.assertEqual(row.status,'requested');self.assertIsNone(row.actual_received_amount)
        self.assertEqual(self.api.post(self.process_url,self.review(),format='json').status_code,200)
        row.refresh_from_db();self.assertEqual(row.actual_received_amount,9500);self.assertEqual(row.refund_amount,7000)
        self.assertEqual(row.cash_review_snapshot['reviewed_by'],self.superuser.pk)
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.status,'cancelled')
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'paid')

    def test_refunded_closes_old_difference_without_double_refund_or_changing_review(self):
        row=self.request_cancel()
        self.assertEqual(self.api.post(self.process_url,self.review(),format='json').status_code,200)
        row.refresh_from_db();audit=row.cash_review_snapshot
        self.assertEqual(self.api.post(self.process_url,{'status':'refunded'},format='json').status_code,200)
        row.refresh_from_db();self.assertEqual(row.cash_review_snapshot,audit)
        self.assertEqual(OrderAmendment.objects.get().status,'cancelled')
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'refunded')
        self.assertEqual(self.api.post(self.process_url,{'status':'refunded'},format='json').status_code,400)

    def test_rejection_needs_no_cash_review_and_leaves_balance_open(self):
        row=self.request_cancel()
        self.assertEqual(self.api.post(self.process_url,{'status':'rejected'},format='json').status_code,200)
        self.assertEqual(OrderAmendment.objects.get().status,'topup_due')
        self.assertEqual(request_cancellation(self.group,reason='other',bank=self.bank_data).status,'requested')

    def test_cannot_override_amount_before_cash_review_or_skip_legacy_review(self):
        for values in [{'manual_refund_amount':100},{'selected_rule_days_before':0}]:
            with self.assertRaises(ValueError):request_cancellation(self.group,reason='other',bank=self.bank_data,**values)
        row=self.request_cancel();row.status='approved';row.requires_cash_review=False;row.save()
        self.assertEqual(self.api.post(self.process_url,{'status':'refunded'},format='json').status_code,400)
        detail=self.api.get(self.process_url.replace('process/',''))
        self.assertTrue(detail.data['requires_cash_review']);self.assertIsNone(detail.data['refund_amount'])
        self.assertEqual(self.api.post(self.process_url,self.review(),format='json').status_code,200)

    def test_other_campus_and_member_cannot_review(self):
        self.request_cancel()
        self.assertEqual(self.api.post(self.process_url,self.review(),format='json',HTTP_X_CAMPUS_ID=str(self.campus_b.pk)).status_code,404)
        self.assertEqual(self.member_api.post(self.process_url,self.review(),format='json').status_code,403)

    def test_settled_or_no_difference_uses_existing_policy(self):
        row=OrderAmendment.objects.get()
        for state in ['settled','no_difference','included_in_order','superseded','cancelled']:
            row.status=state;row.save()
            result=calculate_refund(self.group)
            self.assertFalse(result['requires_cash_review']);self.assertIsInstance(result['refund_amount'],int)

    def test_zero_received_requires_zero_refund(self):
        row=self.request_cancel()
        self.assertEqual(self.api.post(self.process_url,self.review(actual_received_amount=0,refund_amount=1),format='json').status_code,400)
        self.assertEqual(self.api.post(self.process_url,self.review(actual_received_amount=0,refund_amount=0),format='json').status_code,200)
        row.refresh_from_db();self.assertEqual(row.refund_amount,0);self.assertEqual(row.actual_received_amount,0)

    def test_failed_course_update_rolls_back_cash_review_and_approval(self):
        from unittest.mock import patch
        from django.db.models.query import QuerySet
        from booking.models import Reservation
        row=self.request_cancel();snapshot=row.cash_review_snapshot
        original=QuerySet.update
        def update(query,**values):
            if query.model is Reservation and values.get('status')=='cancelled':raise RuntimeError('QA injected failure')
            return original(query,**values)
        with patch.object(QuerySet,'update',update),self.assertRaises(RuntimeError):
            self.api.post(self.process_url,self.review(),format='json')
        row.refresh_from_db();self.assertEqual(row.status,'requested');self.assertIsNone(row.actual_received_amount)
        self.assertEqual(row.cash_review_snapshot,snapshot);self.assertEqual(row.refund_amount,0)
