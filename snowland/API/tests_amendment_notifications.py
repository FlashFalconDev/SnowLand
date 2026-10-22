from unittest.mock import patch

from django.db import transaction
from django.test import TestCase

from API import tests_order_amendment_confirm as fixtures
from booking.amendment_notifications import (
    amendment_delivery_is_current, deliver_amendment_notice,
    dispatch_pending_amendment_notices, prepare_amendment_notice,
)
from booking.models import NotificationDelivery, OrderAmendment


class AmendmentNotificationTests(TestCase):
    def setUp(self):
        fixtures.OrderAmendmentConfirmTests.setUp(self)
        self.manager.email='qa-notice@example.test';self.manager.save(update_fields=['email'])

    def confirm(self):
        body=fixtures.OrderAmendmentConfirmTests.body(self)
        response=self.api.post(self.url_confirm,body,format='json')
        self.assertEqual(response.status_code,201,getattr(response,'data',None))
        return body,response,OrderAmendment.objects.get()

    @patch('booking.scheduler.send_gmail',return_value='ok')
    def test_success_and_replay_have_one_inbox_and_one_mail(self,transport):
        body,response,row=self.confirm()
        self.assertEqual(response.data['data']['notification']['email'],'sent')
        self.assertTrue(response.data['data']['notification']['local_test'])
        self.assertEqual(NotificationDelivery.objects.filter(template__channel='in_app',status='sent').count(),1)
        self.assertEqual(NotificationDelivery.objects.filter(template__channel='email',status='sent').count(),1)
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,200)
        self.assertEqual(NotificationDelivery.objects.count(),2)
        self.assertEqual(transport.call_count,1)
        message=transport.call_args.args[1]
        self.assertIn('2,000',message)
        self.assertNotIn('QA-12345',message)
        self.assertNotIn('insurance_data',message)
        inbox=NotificationDelivery.objects.get(template__channel='in_app')
        self.assertEqual(inbox.payload['in_app_action_path'],f'/membership/orders/{self.group.pk}')

    @patch('booking.scheduler.send_gmail',side_effect=RuntimeError('QA failure'))
    def test_mail_failure_preserves_saved_order_and_independent_inbox_without_auto_retry(self,transport):
        body,response,row=self.confirm()
        self.assertEqual(response.data['data']['notification']['email'],'failed')
        self.assertEqual(NotificationDelivery.objects.get(template__channel='in_app').status,'sent')
        self.reservation.refresh_from_db();self.assertEqual(self.reservation.number_of_people,2)
        self.assertEqual(self.api.post(self.url_confirm,body,format='json').status_code,200)
        self.assertEqual(dispatch_pending_amendment_notices(),(0,0))
        self.assertEqual(transport.call_count,1)

    @patch('booking.scheduler.send_gmail',return_value='ok')
    def test_missing_owner_email_still_creates_inbox(self,transport):
        self.manager.email='';self.manager.save(update_fields=['email'])
        _,response,_=self.confirm()
        self.assertEqual(response.data['data']['notification']['email'],'not_configured')
        self.assertEqual(NotificationDelivery.objects.count(),1)
        transport.assert_not_called()

    def queued(self):
        with patch('booking.amendment_notifications.deliver_amendment_notice'):
            _,response,row=self.confirm()
        self.assertEqual(response.data['data']['notification']['email'],'queued')
        return row,NotificationDelivery.objects.get(template__channel='email')

    @patch('booking.scheduler.send_gmail',return_value='ok')
    def test_worker_delivers_unclaimed_only_once(self,transport):
        row,delivery=self.queued()
        self.assertEqual(dispatch_pending_amendment_notices(),(1,0))
        self.assertEqual(dispatch_pending_amendment_notices(),(0,0))
        self.assertEqual(transport.call_count,1)
        self.assertEqual(NotificationDelivery.objects.count(),2)

    @patch('booking.scheduler.send_gmail',return_value='ok')
    def test_worker_never_retries_claimed_unknown_outcome(self,transport):
        row,delivery=self.queued()
        delivery.payload={**delivery.payload,'email_claimed':True};delivery.save(update_fields=['payload'])
        self.assertEqual(dispatch_pending_amendment_notices(),(0,0))
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail',return_value='ok')
    def test_owner_email_change_cancels_queued_mail(self,transport):
        row,delivery=self.queued()
        self.manager.email='qa-new@example.test';self.manager.save(update_fields=['email'])
        deliver_amendment_notice(row)
        delivery.refresh_from_db();self.assertEqual(delivery.status,'cancelled')
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail',return_value='ok')
    def test_new_balance_state_invalidates_old_instructions(self,transport):
        row,delivery=self.queued()
        from django.utils import timezone
        row.status='topup_reported';row.updated_at=timezone.now();row.save(update_fields=['status','updated_at'])
        inbox=NotificationDelivery.objects.select_related('group__user','template').get(template__channel='in_app')
        self.assertFalse(amendment_delivery_is_current(inbox))
        deliver_amendment_notice(row)
        delivery.refresh_from_db();self.assertEqual(delivery.status,'cancelled')
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail',return_value='ok')
    def test_cancellation_stops_old_topup_instructions(self,transport):
        row,delivery=self.queued()
        from booking.models import CancellationRequest
        CancellationRequest.objects.create(group=self.group,reason='schedule')
        deliver_amendment_notice(row)
        delivery.refresh_from_db();self.assertEqual(delivery.status,'cancelled')
        inbox=NotificationDelivery.objects.select_related('group__user','template').get(template__channel='in_app')
        self.assertFalse(amendment_delivery_is_current(inbox))
        transport.assert_not_called()

    @patch('booking.scheduler.send_gmail',return_value='ok')
    def test_transaction_rollback_removes_prepared_receipts(self,transport):
        _,_,row=self.confirm()
        NotificationDelivery.objects.all().delete()
        from booking.models import NotificationTemplate
        NotificationTemplate.objects.filter(manual_key__isnull=False).delete()
        try:
            with transaction.atomic():
                prepare_amendment_notice(row,self.superuser)
                raise RuntimeError('QA rollback')
        except RuntimeError:
            pass
        self.assertEqual(NotificationDelivery.objects.count(),0)
        self.assertFalse(NotificationTemplate.objects.filter(manual_key__isnull=False).exists())
