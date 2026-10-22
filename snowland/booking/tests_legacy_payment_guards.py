from unittest.mock import patch

from django.http import HttpResponse
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from booking import tests_payment_expiry_race as fixtures


class LegacyPaymentGuardTests(TestCase):
    def setUp(self):
        fixtures.PaymentExpiryRaceTests.setUp(self)
        self.payment.expires_at = timezone.now()+timezone.timedelta(days=1)
        self.payment.save(update_fields=['expires_at'])
        self.client.force_login(self.group.user)

    def legacy_report(self, **changes):
        return self.client.post('/booking/api/process_payment/', {
            'reservation_group_pk':self.group.pk,'paymentType':'TT','senderAccount':'12345',**changes,
        }, content_type='application/json')

    def test_refunded_payment_is_never_reopened_by_either_endpoint(self):
        for report in [self.legacy_report, lambda: fixtures.PaymentExpiryRaceTests.report(self)]:
            self.payment.status='refunded'; self.payment.save(update_fields=['status'])
            result=report()
            self.assertEqual(result.status_code,400)
            self.payment.refresh_from_db()
            self.assertEqual(self.payment.status,'refunded')

    def test_cancelled_or_unconfirmed_lessons_cannot_report_through_legacy_endpoint(self):
        for value in ['cancelled','deleted','pending_coach_confirmation','auto_assignment_failed']:
            self.reservation.status=value; self.reservation.save(update_fields=['status'])
            self.assertEqual(self.legacy_report().status_code,400,value)
            self.payment.refresh_from_db()
            self.assertEqual(self.payment.status,'unpaid')

    def test_past_deadline_cannot_be_reopened_before_expiry_job(self):
        self.payment.expires_at=timezone.now()-timezone.timedelta(seconds=1)
        self.payment.save(update_fields=['expires_at'])
        self.assertEqual(self.legacy_report().status_code,400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status,'unpaid')

    def test_invalid_transfer_reference_returns_error_without_changing_payment(self):
        for value in ['', '12', 'abcde', ['12345'], 12345]:
            for result in [self.legacy_report(senderAccount=value), self.api.post('/booking/snowland/api/process-payment/',{
                    'reservation_group_id':self.group.pk,'payment_type':'bank_transfer','sender_account':value},format='json')]:
                self.assertEqual(result.status_code,400)
                self.payment.refresh_from_db()
                self.assertEqual(self.payment.status,'unpaid')

    def test_valid_legacy_transfer_keeps_response_shape_and_does_not_change_price(self):
        price=self.reservation.payment_amount
        result=self.legacy_report()
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json(),{'message':'Payment confirmed'})
        self.payment.refresh_from_db(); self.reservation.refresh_from_db()
        self.assertEqual(self.payment.status,'pending')
        self.assertEqual(self.payment.bank_account,'12345')
        self.assertEqual(self.reservation.payment_amount,price)

    def test_missing_bank_setup_is_not_a_success_and_invalid_orders_are_not_500(self):
        tenant=self.group.client
        tenant.bank_name='';tenant.save(update_fields=['bank_name'])
        self.assertEqual(self.legacy_report().status_code,400)
        for value in [None,'not-an-id',-1,10**40,{},[]]:
            self.assertEqual(self.legacy_report(reservation_group_pk=value).status_code,400)
        self.assertEqual(self.client.get('/booking/api/process_payment/').status_code,405)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'unpaid')

    def test_legacy_endpoint_keeps_csrf_protection(self):
        from rest_framework.test import APIClient
        client=APIClient(enforce_csrf_checks=True); client.force_login(self.group.user)
        result=client.post('/booking/api/process_payment/',{'reservation_group_pk':self.group.pk,'paymentType':'TT','senderAccount':'12345'},format='json')
        self.assertEqual(result.status_code,403)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'unpaid')

    def test_both_endpoints_accept_real_csrf_from_payment_info(self):
        from rest_framework.test import APIClient
        for url,body in [('/booking/api/process_payment/',{'reservation_group_pk':self.group.pk,'paymentType':'TT','senderAccount':'12345'}),
                         ('/booking/snowland/api/process-payment/',{'reservation_group_id':self.group.pk,'payment_type':'bank_transfer','sender_account':'12345'})]:
            self.payment.status='unpaid';self.payment.save(update_fields=['status'])
            client=APIClient(enforce_csrf_checks=True);client.force_login(self.group.user)
            self.assertEqual(client.post(url,body,format='json').status_code,403)
            self.assertEqual(client.get('/booking/snowland/api/payment-info/',{'reservation_group':self.group.pk}).status_code,200)
            token=client.cookies['csrftoken'].value
            self.assertEqual(client.post(url,body,format='json',HTTP_X_CSRFTOKEN=token).status_code,200)
            self.payment.refresh_from_db();self.assertEqual(self.payment.status,'pending')

    @override_settings(NEWEBPAY_MERCHANT_ID='QA',NEWEBPAY_HASH_KEY='QA',NEWEBPAY_HASH_IV='QA')
    @patch('booking.api_views.neweb_pay_request',return_value='<form>QA-only</form>')
    def test_legacy_card_requires_overseas_order_and_keeps_html_contract(self, provider):
        self.assertEqual(self.legacy_report(paymentType='newebpay').status_code,400)
        provider.assert_not_called()
        self.group.source_country='JP';self.group.save(update_fields=['source_country'])
        result=self.legacy_report(paymentType='newebpay',price=1)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json(),{'message':'Payment confirmed','html':'<form>QA-only</form>'})
        self.assertEqual(provider.call_args.args[0]['body']['price'],'1000')
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'unpaid')

    def test_legacy_booking_get_does_not_run_global_expiry(self):
        keys=['time_slot_config','template_slots_config','all_courses_data','course_categories','course_types','course_templates','course_sessions']
        request=RequestFactory().get('/booking/snowland/')
        request.user=self.group.user; request.tenant=self.group.client; request.client_code='snowland'
        self.payment.expires_at=timezone.now()-timezone.timedelta(seconds=1)
        self.payment.save(update_fields=['expires_at'])
        with patch('booking.tasks.auto_cancel_unpaid_reservations') as expire, patch('booking.views.render',return_value=HttpResponse('QA')), patch('booking.views.build_course_data_optimized',return_value={key:{} for key in keys}):
            from booking.views import home
            result=home(request,client_code='snowland')
        self.assertEqual(result.status_code,200,result.content[:400])
        expire.assert_not_called()
        self.payment.refresh_from_db();self.reservation.refresh_from_db()
        self.assertEqual(self.payment.status,'unpaid')
        self.assertEqual(self.reservation.status,'auto_assigned')

    def test_payment_info_uses_latest_attempt_instead_of_crashing_on_multiple_rows(self):
        from booking.models import Payment
        latest=Payment.objects.create(reservation_group=self.group,user=self.group.user,status='paid')
        result=self.api.get('/booking/snowland/api/payment-info/',{'reservation_group':self.group.pk})
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.data['payment_status'],'paid')

    def test_new_unpaid_attempt_does_not_reopen_existing_collection(self):
        from booking.models import Payment
        self.payment.status='paid';self.payment.save(update_fields=['status'])
        newest=Payment.objects.create(reservation_group=self.group,user=self.group.user,status='unpaid')
        info=self.api.get('/booking/snowland/api/payment-info/',{'reservation_group':self.group.pk})
        self.assertEqual(info.status_code,400)
        self.assertFalse(info.data['requires_payment'])
        center=self.api.get('/booking/snowland/api/member-center/').data
        order=next(row for row in center['orders'] if row['id']==self.group.pk)
        self.assertEqual(order['payment_hold_status'],'payment_records_review')
        self.assertEqual(self.legacy_report().status_code,400)
        self.assertEqual(fixtures.PaymentExpiryRaceTests.report(self).status_code,400)
        newest.refresh_from_db();self.payment.refresh_from_db()
        self.assertEqual((newest.status,self.payment.status),('unpaid','paid'))
