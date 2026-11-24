import json
from datetime import date, time, timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach, PayrollLine, PayrollStatement, StaffIncentiveLine, StaffIncentiveStatement
from Coach.payroll import calculate_payroll_statement
from Coach.staff_incentives import calculate_staff_incentive
from Coach.vehicle_models import VehicleCharge, VehicleDeduction, VehicleExpense, VehicleTrip
from Coach.vehicle_payroll import charge_balance
from Control.models import TenantStaffMembership
from Coursekit.models import CourseCategory, CourseTemplate, CourseType, DiscountCode
from Resorts.models import Campus, Resorts

from .amendment_balances import group_balances
from .api_views import get_booked_slots, member_notification_queryset, notification_unread_count
from .call_back import call_back
from .discount_usage import rebuild_discount_usage, record_checkout_discount_usage
from .models import (
    Booking, CancellationRequest, CourseAlbumAsset, CourseEvaluation, CourseMedia, MemberCourseDocumentRevision,
    MemberDetail, MemberLoyaltyAccount, MemberLoyaltyEntry, MemberWaiverSignature, NotificationDelivery,
    NotificationTemplate, OrderAmendment, OrderAmendmentEvent, OrderDiscountUsage, OrderLoyalty, OrderRevision, ParticipantInvitation,
    Payment, Reservation, ReservationGroup, SharedCourseClass, TenantOrderArchiveBatch,
)
from .operations import calculate_refund
from .order_archive import SCOPES, build_archive_plan
from .tasks import expire_unpaid_payment


class OrderArchiveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Client.objects.create(name='Archive fixture', internal_code='archive-fixture')
        cls.other = Client.objects.create(name='Another school', internal_code='another-school')
        cls.actor = User.objects.create_superuser('archive-platform')
        cls.staff = User.objects.create_user('archive-hq', is_staff=True)
        cls.owner = User.objects.create_user('archive-owner')
        TenantStaffMembership.objects.create(user=cls.staff, client=cls.tenant, is_manager=True,
            role='hq_admin', all_campuses=True, admin_permissions=['orders'])
        cls.staff.user_permissions.add(Permission.objects.get(codename='view_reservationgroup'))
        cls.campus = Campus.objects.create(client=cls.tenant, name='Archive campus', code='archive')
        cls.resort = Resorts.objects.create(client=cls.tenant, name='archive-resort')
        cls.coach = Coach.objects.create(client=cls.tenant, name='Archive coach')
        category = CourseCategory.objects.create(client=cls.tenant, name='Archive course')
        course_type = CourseType.objects.create(category=category, name='Private lesson')
        template = CourseTemplate.objects.create(course_type=course_type, name='Private lesson', duration_hours=2)
        cls.day = date(2026, 1, 15)
        slot = dict(client=cls.tenant, campus=cls.campus, resort=cls.resort, template=template,
                    start_time=time(9), end_time=time(11), ability_level='1', minimum_students=2)
        cls.customer_class = SharedCourseClass.objects.create(date=cls.day, opening_mode='customer', **slot)
        cls.school_class = SharedCourseClass.objects.create(date=cls.day + timedelta(days=1), opening_mode='school', **slot)
        cls.group = ReservationGroup.objects.create(client=cls.tenant, campus=cls.campus, user=cls.owner)
        cls.other_group = ReservationGroup.objects.create(client=cls.other)
        cls.unknown_group = ReservationGroup.objects.create()
        cls.reservation = Reservation.objects.create(
            group=cls.group, resort=cls.resort, preferred_coach=cls.coach, shared_course_class=cls.customer_class,
            status='completed', number_of_people=3, course_fee=900,
        )
        cls.booking = Booking.objects.create(reservation=cls.reservation, date=cls.day, start_time=time(9), end_time=time(11))
        cls.member = MemberDetail.objects.create(reservation=cls.reservation, user=cls.owner)
        cls.exited = MemberDetail.all_objects.create(reservation=cls.reservation, is_active=False)
        cls.payment = Payment.objects.create(reservation_group=cls.group, status='paid')
        cls.evaluation = CourseEvaluation.objects.create(booking=cls.booking, member=cls.member, coach=cls.coach)
        cls.signature = MemberWaiverSignature.objects.create(member=cls.member, signed_at=timezone.now(), strokes=[])
        cls.media = CourseMedia.objects.create(evaluation=cls.evaluation, media_type='photo', file='course-records/fixture.png')
        cls.album = CourseAlbumAsset.objects.create(booking=cls.booking, media_type='photo', file='course-albums/fixture.png')
        cls.album.tagged_members.add(cls.member)
        cls.invitation = ParticipantInvitation.objects.create(member=cls.member, expires_at=timezone.now() + timedelta(days=1))
        revision = OrderRevision.objects.create(group=cls.group, version=1)
        cls.document = MemberCourseDocumentRevision.objects.create(member=cls.member, revision=revision)
        cls.amendment = OrderAmendment.objects.create(group=cls.group, revision=revision, request_key=uuid4(), previous_total=900,
            new_total=900, difference_amount=0, balance_amount=0)
        OrderAmendmentEvent.objects.create(amendment=cls.amendment, request_key=uuid4())
        CancellationRequest.objects.create(group=cls.group, reason='other', status='refunded')
        cls.notification_template = NotificationTemplate.objects.create(client=cls.tenant, name='Archive notice', channel='in_app')
        notification = dict(template=cls.notification_template, recipient=str(cls.owner.pk), scheduled_at=timezone.now())
        cls.delivery = NotificationDelivery.objects.create(group=cls.group, **notification)
        cls.manual = NotificationDelivery.objects.create(**notification)
        cls.unknown_delivery = NotificationDelivery.objects.create(group=cls.unknown_group, **notification)
        cls.account = MemberLoyaltyAccount.objects.create(client=cls.tenant, user=cls.owner, points=260,
            previous_points=50, reward_balance=35)
        loyalty = OrderLoyalty.objects.create(group=cls.group, account=cls.account, policy_revision=1, rules={})
        MemberLoyaltyEntry.objects.create(account=cls.account, order=loyalty, kind='purchase', points_delta=210, rewards_delta=30)
        cls.payroll = PayrollStatement.objects.create(campus=cls.campus, coach=cls.coach,
            period_start=cls.day, period_end=cls.day, status='confirmed')
        PayrollLine.objects.create(statement=cls.payroll, booking=cls.booking, line_type='course', total_amount=900)
        cls.incentive = StaffIncentiveStatement.objects.create(campus=cls.campus, user=cls.staff, month=cls.day.replace(day=1))
        StaffIncentiveLine.objects.create(statement=cls.incentive, group=cls.group, entry_key='earn:fixture',
            line_type='earning', event_date=cls.day, base_amount=900, percent=10, amount=90)
        now = timezone.now()
        cls.trip = VehicleTrip.objects.create(campus=cls.campus, driver=cls.coach, purpose='lesson',
            starts_at=now, ends_at=now + timedelta(hours=1))
        cls.trip.participants.add(cls.coach)
        cls.expense = VehicleExpense.objects.create(trip=cls.trip, kind='toll', amount_yen=100, receipt='vehicle-receipts/test.png')
        cls.charge = VehicleCharge.objects.create(trip=cls.trip, coach=cls.coach, amount_twd=100, first_month=cls.day, last_month=cls.day)
        cls.deduction = VehicleDeduction.objects.create(charge=cls.charge, statement=cls.payroll, amount_twd=10)

    def command(self, *args, code='archive-fixture'):
        output = StringIO()
        call_command('soft_delete_tenant_orders', '--client-code', code, *args, stdout=output)
        return output.getvalue()

    def apply(self, digest=None):
        digest = digest or self.command('--dry-run').split('plan_digest=')[1].strip()
        return self.command('--apply', '--confirm-client-code', self.tenant.internal_code,
                            '--expected-plan-digest', digest, '--actor-id', str(self.actor.pk))

    def assert_live(self, row, visible):
        self.assertEqual(type(row).all_objects.live().filter(pk=row.pk).exists(), visible, type(row)._meta.label)

    def test_preview_apply_restore_all_tables_and_preserve_history(self):
        self.assertEqual(len(SCOPES), 24)
        preview = self.command('--dry-run')
        self.assertIn('booking.MemberDetail tenant_total=2 already_deleted=0 pending=2', preview)
        self.assertIn('without_group=1 unknown_group_owner=1', preview)
        self.assertFalse(TenantOrderArchiveBatch.objects.exists())
        self.assert_live(self.group, True)
        cache_key = f'course_data_optimized_v2_{self.tenant.internal_code}'
        cache.set(cache_key, 'old')
        with self.captureOnCommitCallbacks(execute=True), patch('booking.signals.delete_private_course_file') as delete_file:
            output = self.apply()
        delete_file.assert_not_called()
        self.assertIsNone(cache.get(cache_key))
        batch = TenantOrderArchiveBatch.objects.get(pk=output.split('batch=')[1].strip())
        for scope in SCOPES:
            ids = batch.targets[scope.label]
            self.assertTrue(ids, scope.label)
            self.assertEqual(scope.rows().filter(pk__in=ids, is_deleted=True, deleted_by=self.actor).count(), len(ids))
            self.assertFalse(scope.rows().live().filter(pk__in=ids).exists())
        for row in (self.school_class, self.other_group, self.unknown_group, self.manual, self.unknown_delivery):
            self.assert_live(row, True)
        self.assertEqual(CourseMedia.objects.get(pk=self.media.pk).evaluation_id, self.evaluation.pk)
        self.assertTrue(self.album.tagged_members.filter(pk=self.member.pk).exists())
        self.assertTrue(MemberWaiverSignature.objects.filter(pk=self.signature.pk).exists())
        self.assert_live(self.album.booking, False)
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.receipt.name, 'vehicle-receipts/test.png')
        self.account.refresh_from_db()
        self.assertEqual((self.account.points, self.account.reward_balance), (50, 5))
        self.assertEqual(self.apply().strip(), 'pending=0')
        self.assertIn('restored_batch=', self.command('--restore', '--batch', str(batch.pk)))
        for scope in SCOPES:
            ids = batch.targets[scope.label]
            self.assertEqual(scope.rows().live().filter(pk__in=ids, deleted_at=None, deleted_by=None).count(), len(ids))
        self.exited.refresh_from_db()
        self.assertFalse(self.exited.is_active)
        self.account.refresh_from_db()
        self.assertEqual((self.account.points, self.account.reward_balance), (260, 35))

    def test_validation_drift_and_unsafe_scope_leave_flags_unchanged(self):
        for invalid in ('*', 'archive', 'Archive-Fixture', 'archive-fixture '):
            with self.subTest(code=invalid), self.assertRaises(CommandError):
                self.command('--dry-run', code=invalid)
        digest = build_archive_plan(self.tenant).digest
        new = ReservationGroup.objects.create(client=self.tenant)
        with self.assertRaisesMessage(CommandError, '計畫已變動'):
            self.apply(digest)
        self.assert_live(new, True)
        self.delivery.status = 'sending'
        self.delivery.save(update_fields=['status'])
        with self.assertRaisesMessage(CommandError, '尚未結案'):
            self.apply()
        self.assert_live(self.group, True)
        self.delivery.status = 'scheduled'
        self.delivery.save(update_fields=['status'])
        other_reservation = Reservation.objects.create(group=self.other_group, shared_course_class=self.customer_class)
        plan = build_archive_plan(self.tenant)
        self.assertNotIn(self.customer_class.pk, plan.targets['booking.SharedCourseClass'])
        with self.assertRaisesMessage(CommandError, '歸戶矛盾'):
            self.apply()
        self.assert_live(other_reservation, True)

    def test_reconciliation_failure_rolls_back_all_flags_and_batch(self):
        with patch('booking.order_archive.rebuild_discount_usage', side_effect=IntegrityError):
            with self.assertRaisesMessage(CommandError, '所有變更已回滾'):
                self.apply()
        self.assertFalse(TenantOrderArchiveBatch.objects.exists())
        self.assert_live(self.group, True)
        self.assert_live(self.incentive, True)
        self.account.refresh_from_db()
        self.assertEqual((self.account.points, self.account.reward_balance), (260, 35))

    def test_payroll_and_incentive_keys_stay_occupied_and_restore_checks_overlap(self):
        self.apply()
        batch = TenantOrderArchiveBatch.objects.get()
        period = dict(coach=self.coach, campus=self.campus, period_start=self.day, period_end=self.day)
        with self.assertRaisesMessage(ValueError, '封存薪資單'):
            calculate_payroll_statement(**period)
        with self.assertRaisesMessage(ValueError, '封存員工獎金'):
            calculate_staff_incentive(user=self.staff, campus=self.campus, month=self.incentive.month)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PayrollStatement.all_objects.create(**period)
        with self.assertRaises(IntegrityError), transaction.atomic():
            StaffIncentiveStatement.all_objects.create(user=self.staff, campus=self.campus, month=self.incentive.month)
        PayrollStatement.all_objects.create(**{**period, 'period_end': self.day + timedelta(days=1)})
        with self.assertRaisesMessage(CommandError, '日期與有效期間重疊'):
            self.command('--restore', '--batch', str(batch.pk))
        self.assert_live(self.group, False)

    def test_console_and_member_history_hide_archive_while_platform_can_read(self):
        self.apply()
        api = APIClient()
        url = f'/api/admin/archive-fixture/orders/{self.group.pk}/'
        api.force_authenticate(self.staff)
        self.assertEqual(api.get(url).status_code, 404)
        api.force_authenticate(self.actor)
        self.assertEqual(api.get(url).status_code, 404)
        api.force_authenticate(self.owner)
        history = api.get('/booking/archive-fixture/api/reservation-history/')
        self.assertEqual(history.status_code, 200, history.data)
        self.assertNotContains(history, self.group.order_number)

        listing = reverse('admin:booking_reservationgroup_changelist')
        detail = reverse('admin:booking_reservationgroup_change', args=[self.group.pk])
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get(listing), '僅已刪除')
        self.assertEqual(self.client.get(detail).status_code, 302)
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(listing, {'archive': 'deleted'}), detail)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.post(detail, {'name': 'changed'}).status_code, 403)
        delete_url = reverse('admin:booking_reservationgroup_delete', args=[self.group.pk])
        self.assertEqual(self.client.post(delete_url, {'post': 'yes'}).status_code, 403)
        with self.assertRaises(ProtectedError):
            ReservationGroup.all_objects.get(pk=self.group.pk).delete()

    def test_active_relation_rollups_exclude_flagged_children_and_ancestors(self):
        self.assertEqual(self.customer_class.registered_students, 3)
        self.assertEqual(charge_balance(self.charge), 90)
        self.deduction.is_deleted = True
        self.deduction.save(update_fields=['is_deleted'])
        self.assertEqual(charge_balance(self.charge), 100)
        Payment.objects.create(reservation_group=self.group, status='refunded', is_deleted=True)
        api = APIClient()
        api.force_authenticate(self.actor)
        url = '/api/admin/archive-fixture/orders/'
        self.assertEqual(api.get(url, {'payment_status': 'refunded'}).data['data']['total'], 0)
        self.assertEqual(api.get(url, {'payment_status': 'paid'}).data['data']['total'], 1)
        self.group.is_deleted = True
        self.group.save(update_fields=['is_deleted'])
        self.assertEqual(self.customer_class.registered_students, 0)
        self.assert_live(self.booking, False)
        self.assert_live(self.invitation, False)
        self.assert_live(self.delivery, False)
        self.assert_live(self.manual, True)

    def test_refund_and_schedule_use_active_courses_and_sessions(self):
        date_of_lesson = timezone.localdate() + timedelta(days=21)
        self.booking.date = date_of_lesson
        self.booking.save(update_fields=['date'])
        self.reservation.status = 'manually_assigned'
        self.reservation.save(update_fields=['status'])
        Booking.objects.create(reservation=self.reservation, date=date_of_lesson - timedelta(days=10),
                               start_time=time(8), end_time=time(9), is_deleted=True)
        Reservation.objects.create(group=self.group, course_fee=1200, is_deleted=True)
        refund = calculate_refund(self.group)
        self.assertEqual(refund['original_amount'], 900)
        self.assertEqual(refund['days_before'], 21)
        self.assertEqual(get_booked_slots(self.coach), [{'date': date_of_lesson, 'start_time': '09:00', 'end_time': '11:00'}])

    def test_balance_events_and_member_unread_count_follow_archive_visibility(self):
        revision = OrderRevision.objects.create(group=self.group, version=2)
        OrderAmendment.objects.create(group=self.group, revision=revision, request_key=uuid4(),
            previous_total=900, new_total=1200, difference_amount=300, balance_amount=300, is_deleted=True)
        OrderAmendmentEvent.objects.create(amendment=self.amendment, request_key=uuid4(), is_deleted=True)
        balances = group_balances(self.group, staff=True)
        self.assertEqual(len(balances), 1)
        self.assertEqual(len(balances[0]['events']), 1)
        NotificationTemplate.objects.filter(pk=self.notification_template.pk).update(event='manual', manual_key=uuid4())
        NotificationDelivery.objects.update(status='sent', sent_at=timezone.now())
        unread = member_notification_queryset(self.tenant, self.owner)
        self.assertEqual(notification_unread_count(unread), 2)
        ReservationGroup.all_objects.filter(pk=self.group.pk).update(is_deleted=True)
        self.assertEqual(notification_unread_count(unread), 1)

    def test_discount_uses_distinct_checkouts_and_rebuilds_on_apply_and_restore(self):
        rule = DiscountCode.objects.create(client=self.tenant, code='ARCHIVE', used_count=2)
        later = Reservation.objects.create(group=self.group)
        Reservation.objects.create(group=self.group, discount_amount=10, discount_code='ARCHIVE')
        with transaction.atomic():
            rebuild_discount_usage(self.tenant)
            record_checkout_discount_usage(self.tenant, {self.reservation.pk: {rule.pk}, later.pk: {rule.pk}})
        rule.refresh_from_db()
        self.assertEqual(rule.used_count, 3)
        self.apply()
        rule.refresh_from_db()
        self.assertEqual(rule.used_count, 0)
        self.command('--restore', '--batch', str(TenantOrderArchiveBatch.objects.get().pk))
        rule.refresh_from_db()
        self.assertEqual(rule.used_count, 3)

    def test_discount_history_retains_rule_identity_after_rule_removal(self):
        rule = DiscountCode.objects.create(client=self.tenant, code='RETIRED')
        rule_id = rule.pk
        record_checkout_discount_usage(self.tenant, {self.reservation.pk: {rule_id}})
        rule.delete()
        self.assertTrue(OrderDiscountUsage.objects.filter(reservation=self.reservation, rule_id=rule_id).exists())

    def test_private_media_and_album_file_authorize_historical_orders(self):
        self.apply()
        self.client.force_login(self.owner)
        for name, kwargs, handler in (
            ('api_course_media_file_client', {'media_id': self.media.pk}, 'booking.api_views.private_file_response'),
            ('api_course_album_file_client', {'asset_id': self.album.pk}, 'booking.learning_views.private_file_response'),
        ):
            route = reverse(f'booking:{name}', kwargs={'client_code': self.tenant.internal_code, **kwargs})
            with self.subTest(name=name), patch(handler, return_value=HttpResponse('fixture')) as response:
                self.assertContains(self.client.get(route), 'fixture')
                response.assert_called_once()

    def test_late_callback_and_expiry_never_mutate_archived_order(self):
        self.payment.status = 'unpaid'
        self.payment.expires_at = timezone.now() - timedelta(days=1)
        self.payment.save(update_fields=['status', 'expires_at'])
        self.apply()
        request = RequestFactory().post('/callback/?client_code=archive-fixture', {
            'MerchantID': 'fixture-merchant', 'TradeInfo': 'fixture-body', 'TradeSha': 'A' * 64,
        })
        payload = {'Status': 'SUCCESS', 'Result': {'MerchantOrderNo': str(self.group.pk), 'Amt': '900'}}
        with patch('booking.call_back.gateway_settings', return_value={
            'MerchantID': 'fixture-merchant', 'HashKey': 'fixture-key', 'HashIV': 'fixture-iv',
        }), patch('booking.call_back.sha256_hash', return_value='A' * 64), patch(
            'booking.call_back.aes256_cbc_decrypt', return_value=json.dumps(payload),
        ):
            self.assertEqual(call_back(request, 'NewebPay').status_code, 409)
        self.assertEqual(expire_unpaid_payment(self.payment.pk), (0, 0))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'unpaid')
        self.assertEqual(self.payment.DataJSON, {})
