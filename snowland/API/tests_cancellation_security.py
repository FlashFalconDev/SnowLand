from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from API.admin_views import CancellationAdminViewSet
from Client.models import Client
from Resorts.models import Campus
from booking.models import Booking, CancellationRequest, Payment, Reservation, ReservationGroup
from booking.operations import calculate_refund, request_cancellation


class CancellationSecurityTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.payment = Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        self.cancellation = CancellationRequest.objects.create(group=self.group, reason='health', reason_note='QA private health note',
            status='approved', original_amount=10000, refund_amount=5000,
            refund_bank_name='QA Bank', refund_account_number='QA-PRIVATE-ACCOUNT', refund_account_holder='QA Person')
        self.hq = User.objects.create_superuser('cancel-hq', 'cancel-hq@example.test', 'QA-only')
        self.api = APIClient()
        self.api.force_authenticate(self.hq)
        self.url = f'/api/admin/snowland/cancellations/{self.cancellation.pk}/'

    def campus_actor(self, role):
        user = User.objects.create_user('cancel-' + role)
        profile = user.userprofile
        profile.is_manager = True
        profile.manager_client = self.client_tenant
        profile.role = role
        profile.admin_permissions = ['orders']
        profile.save()
        profile.campuses.add(self.campus)
        user.refresh_from_db()
        return user

    def test_browser_refund_requires_csrf_and_rejection_does_not_mutate(self):
        from django.test import Client as BrowserClient
        import json
        browser = BrowserClient(enforce_csrf_checks=True)
        browser.force_login(self.hq)
        response = browser.post(self.url + 'process/', json.dumps({'status': 'refunded'}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.cancellation.refresh_from_db()
        self.assertEqual(self.cancellation.status, 'approved')
        self.assertEqual(browser.get(self.url).status_code, 200)
        response = browser.post(self.url + 'process/', json.dumps({'status': 'refunded'}), content_type='application/json', HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200, response.content)

    def test_campus_summary_roles_cannot_read_bank_health_or_refund_amount_or_process(self):
        self.booking_1.date = timezone.localdate() + timedelta(days=1)
        self.booking_1.save(update_fields=['date'])
        for role in ['campus_manager', 'campus_principal']:
            self.api.force_authenticate(self.campus_actor(role))
            response = self.api.get(self.url)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(set(response.data), {'id', 'group', 'order_number', 'status'})
            listed = self.api.get('/api/admin/snowland/cancellations/')
            self.assertEqual(set(listed.data['data']['list'][0]), {'id', 'group', 'order_number', 'status'})
            self.assertEqual(self.api.post(self.url + 'process/', {'status': 'refunded'}, format='json').status_code, 403)
        self.cancellation.refresh_from_db()
        self.assertEqual(self.cancellation.status, 'approved')

    def test_campus_manager_cannot_read_cancellation_outside_ten_day_window(self):
        self.api.force_authenticate(self.campus_actor('campus_manager'))
        self.assertEqual(self.api.get(self.url).status_code, 404)
        self.assertEqual(self.api.get('/api/admin/snowland/cancellations/').data['data']['list'], [])

    def test_stale_object_does_not_overwrite_a_completed_refund_or_its_timestamp(self):
        original = CancellationAdminViewSet.get_object
        completed_at = timezone.now() - timedelta(days=1)

        def stale(view):
            item = original(view)
            CancellationRequest.objects.filter(pk=item.pk).update(status='refunded', reviewed_at=completed_at)
            return item

        with patch.object(CancellationAdminViewSet, 'get_object', stale):
            response = self.api.post(self.url + 'process/', {'status': 'refunded'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.cancellation.refresh_from_db()
        self.assertEqual(self.cancellation.reviewed_at, completed_at)

    def test_campus_move_between_initial_permission_check_and_write_is_rechecked(self):
        other = Campus.objects.create(client=self.client_tenant, name='Other campus', code='other')
        original = CancellationAdminViewSet.get_object

        def stale(view):
            item = original(view)
            ReservationGroup.objects.filter(pk=self.group.pk).update(campus=other)
            return item

        with patch.object(CancellationAdminViewSet, 'get_object', stale):
            response = self.api.post(self.url + 'process/', {'status': 'refunded'}, format='json', HTTP_X_CAMPUS_ID=str(self.campus.pk))
        self.assertEqual(response.status_code, 404, response.data)
        self.cancellation.refresh_from_db()
        self.assertEqual(self.cancellation.status, 'approved')

    def test_other_company_and_selected_campus_cannot_read_or_process(self):
        other = Client.objects.create(name='Other cancel', internal_code='cancel-other')
        wrong = Campus.objects.create(client=self.client_tenant, name='Wrong', code='wrong')
        self.assertEqual(self.api.get(f'/api/admin/cancel-other/cancellations/{self.cancellation.pk}/').status_code, 404)
        self.assertEqual(self.api.post(self.url + 'process/', {'status':'refunded'}, format='json', HTTP_X_CAMPUS_ID=str(wrong.pk)).status_code, 404)

    def test_repeated_or_invalid_status_does_not_change_completed_timestamp(self):
        self.assertEqual(self.api.post(self.url + 'process/', {'status': 'refunded'}, format='json').status_code, 200)
        self.cancellation.refresh_from_db()
        old = self.cancellation.reviewed_at
        for value in ['refunded', 'approved', 'rejected', 'invalid', True, None]:
            result = self.api.post(self.url + 'process/', {'status': value}, format='json')
            self.assertEqual(result.status_code, 400, result.data)
        self.cancellation.refresh_from_db()
        self.assertEqual(self.cancellation.reviewed_at, old)

    def test_payment_write_failure_rolls_back_cancellation_and_reservation_changes(self):
        original = QuerySet.update

        def fail(queryset, **values):
            if queryset.model is Payment and values.get('status') == 'refunded':
                raise RuntimeError('QA payment update failed')
            return original(queryset, **values)

        with patch.object(QuerySet, 'update', fail):
            with self.assertRaises(RuntimeError):
                self.api.post(self.url + 'process/', {'status': 'refunded'}, format='json')
        self.cancellation.refresh_from_db()
        self.reservation.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.cancellation.status, 'approved')
        self.assertIsNone(self.cancellation.reviewed_at)
        self.assertEqual(self.reservation.status, 'completed')
        self.assertEqual(self.payment.status, 'paid')


class CancellationRequestSecurityTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.payment = Payment.objects.create(reservation_group=self.group, user=self.user,
            status='paid', payment_method='credit_card')
        self.hq = User.objects.create_superuser('request-hq', 'request-hq@example.test', 'QA-only')
        self.admin_url = f'/api/admin/snowland/orders/{self.group.pk}/cancel/'
        self.member_url = f'/booking/snowland/api/member-cancellations/{self.group.pk}/'
        self.api = APIClient()

    def test_both_browser_request_endpoints_require_csrf(self):
        from django.test import Client as BrowserClient
        import json
        for user, url, expected in [(self.hq, self.admin_url, 200), (self.user, self.member_url, 201)]:
            browser = BrowserClient(enforce_csrf_checks=True)
            browser.force_login(user)
            response = browser.post(url, json.dumps({'reason': 'schedule'}), content_type='application/json')
            self.assertEqual(response.status_code, 403, response.content)
            self.assertFalse(self.group.cancellation_requests.exists())
            preview_url = url if user == self.user else f'/api/admin/snowland/orders/{self.group.pk}/'
            self.assertEqual(browser.get(preview_url).status_code, 200)
            response = browser.post(url, json.dumps({'reason': 'schedule'}), content_type='application/json',
                HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)
            self.assertEqual(response.status_code, expected, response.content)
            self.group.cancellation_requests.all().delete()

    def test_admin_invalid_bank_payload_returns_400_without_partial_revision(self):
        self.api.force_authenticate(self.hq)
        self.payment.payment_method = 'bank_transfer'
        self.payment.save(update_fields=['payment_method'])
        for bank in [True, ['bank'], 'bank', {'bank_name': ['invalid'], 'account_number': '123', 'account_holder': 'QA'}]:
            response = self.api.post(self.admin_url, {'reason': 'schedule', 'refund_bank': bank}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(self.group.cancellation_requests.exists())
        self.assertFalse(self.group.revisions.exists())

    def test_refund_rule_rejects_boolean_or_fraction_instead_of_truncating(self):
        self.api.force_authenticate(self.hq)
        for value in [True, False, 14.5]:
            response = self.api.post(self.admin_url, {'reason': 'schedule', 'selected_rule_days_before': value}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(self.group.cancellation_requests.exists())

    def test_stale_group_owner_is_not_allowed_to_create_request(self):
        from booking.api_views import MemberCancellationAPI
        original = MemberCancellationAPI._group

        def stale(view, request, client_code, group_id):
            result = original(view, request, client_code, group_id)
            ReservationGroup.objects.filter(pk=self.group.pk).update(user=self.coach_user)
            return result

        self.api.force_authenticate(self.user)
        with patch.object(MemberCancellationAPI, '_group', stale):
            response = self.api.post(self.member_url, {'reason': 'schedule'}, format='json')
        self.assertEqual(response.status_code, 404, response.data)
        self.assertFalse(self.group.cancellation_requests.exists())

    def test_stale_payment_is_rechecked_before_member_request(self):
        from booking.api_views import MemberCancellationAPI
        original = MemberCancellationAPI._group

        def stale(view, request, client_code, group_id):
            result = original(view, request, client_code, group_id)
            Payment.objects.filter(pk=self.payment.pk).update(status='refunded')
            return result

        self.api.force_authenticate(self.user)
        with patch.object(MemberCancellationAPI, '_group', stale):
            response = self.api.post(self.member_url, {'reason': 'schedule'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(self.group.cancellation_requests.exists())

    def test_already_refunded_order_cannot_open_another_refund(self):
        CancellationRequest.objects.create(group=self.group, reason='schedule', status='refunded',
            original_amount=10000, refund_amount=5000)
        with self.assertRaises(ValueError):
            request_cancellation(self.group, reason='schedule')
        self.assertEqual(self.group.cancellation_requests.count(), 1)

    def test_revision_failure_rolls_back_request(self):
        with patch('booking.operations.record_order_revision', side_effect=RuntimeError('QA revision failure')):
            with self.assertRaises(RuntimeError):
                request_cancellation(self.group, reason='schedule')
        self.assertFalse(self.group.cancellation_requests.exists())

    def test_member_invalid_bank_and_reason_note_are_not_coerced_or_truncated(self):
        self.api.force_authenticate(self.user)
        for values in [{'bank_name': ['not text']}, {'account_number': '1' * 101}, {'reason_note': {'private': 'note'}}, {'reason_note': 'x' * 1001}]:
            response = self.api.post(self.member_url, {'reason': 'schedule', **values}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(self.group.cancellation_requests.exists())

    def test_admin_selected_campus_is_rechecked_after_initial_object_read(self):
        from API.admin_views import OrderAdminViewSet
        other = Campus.objects.create(client=self.client_tenant, name='Moved', code='moved')
        original = OrderAdminViewSet.get_object

        def stale(view):
            result = original(view)
            ReservationGroup.objects.filter(pk=self.group.pk).update(campus=other)
            return result

        self.api.force_authenticate(self.hq)
        with patch.object(OrderAdminViewSet, 'get_object', stale):
            response = self.api.post(self.admin_url, {'reason': 'schedule'}, format='json', HTTP_X_CAMPUS_ID=str(self.campus.pk))
        self.assertEqual(response.status_code, 404, response.data)
        self.assertFalse(self.group.cancellation_requests.exists())

    def test_admin_invalid_reason_structure_returns_validation_error(self):
        self.api.force_authenticate(self.hq)
        for reason in [[], {}, ['health'], True, 0, None]:
            with self.subTest(reason=reason):
                response = self.api.post(self.admin_url, {'reason': reason}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(self.group.cancellation_requests.exists())

    def test_refund_date_ignores_deleted_or_cancelled_courses(self):
        for status in ['deleted', 'cancelled']:
            with self.subTest(status=status):
                old = Reservation.objects.create(group=self.group, resort=self.resort, course_type=self.course_type,
                    status=status, course_fee=9000)
                Booking.objects.create(reservation=old, date=timezone.localdate(),
                    start_time=self.booking_1.start_time, end_time=self.booking_1.end_time)
                preview = calculate_refund(self.group)
                self.assertEqual(preview['days_before'], 35)
                self.assertEqual(preview['original_amount'], 10000)
                self.assertEqual(preview['refund_amount'], 9500)
                old.delete()

    def test_member_cannot_submit_after_order_moved_to_another_company(self):
        from booking.api_views import MemberCancellationAPI
        original = MemberCancellationAPI._group
        other = Client.objects.create(name='Moved company', internal_code='moved-company')

        def stale(view, request, client_code, group_id):
            result = original(view, request, client_code, group_id)
            ReservationGroup.objects.filter(pk=self.group.pk).update(client=other)
            return result

        self.api.force_authenticate(self.user)
        with patch.object(MemberCancellationAPI, '_group', stale):
            response = self.api.post(self.member_url, {'reason': 'schedule'}, format='json')
        self.assertEqual(response.status_code, 404, response.data)
        self.assertFalse(self.group.cancellation_requests.exists())
