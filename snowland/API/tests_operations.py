from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Coach.models import Coach, CoachPayRule, PayrollStatement
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from Resorts.models import Campus, EquipmentAssistanceTimeSlot, OperatingPolicy, PaymentAccount, Resorts
from booking.models import (
    Booking, CancellationRequest, CourseEvaluation, CourseMedia, MemberDetail, NotificationDelivery, NotificationTemplate, Payment,
    Reservation, ReservationGroup, StaffBookingLink,
)
from booking.operations import calculate_refund, request_cancellation, resolve_payment_account, schedule_group_notifications
from booking.legal_documents import get_current_waiver
from Coach.payroll import add_payroll_adjustment, calculate_payroll_statement
from booking.tasks import auto_cancel_unpaid_reservations
from API.admin_serializers import CoachAdminSerializer, OperatingPolicyAdminSerializer


class OperationsTests(TestCase):
    def setUp(self):
        self.client_tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.resort = Resorts.objects.create(client=self.client_tenant, name='tomamu-test', display_name='Tomamu')
        self.campus = Campus.objects.create(client=self.client_tenant, name='北海道校區', code='hokkaido')
        self.campus.resorts.add(self.resort)
        self.policy = OperatingPolicy.objects.create(
            client=self.client_tenant,
            cancellation_fee_percent=5,
            cancellation_rules=[
                {'days_before': 30, 'refund_percent': 100},
                {'days_before': 14, 'refund_percent': 80},
                {'days_before': 7, 'refund_percent': 50},
                {'days_before': 0, 'refund_percent': 0},
            ],
        )
        self.user = User.objects.create_user('student', email='student@example.com')
        self.coach_user = User.objects.create_user('coach', email='coach@example.com')
        self.coach = Coach.objects.create(client=self.client_tenant, user=self.coach_user, name='教練 A')
        self.coach.campuses.add(self.campus)
        self.category = CourseCategory.objects.create(client=self.client_tenant, name='單板')
        self.course_type = CourseType.objects.create(category=self.category, name='初階')
        self.group = ReservationGroup.objects.create(
            client=self.client_tenant, campus=self.campus, user=self.user,
            referral_user=self.coach_user, name='測試訂單', marketing_source='朋友介紹', source_country='TW',
        )
        self.reservation = Reservation.objects.create(
            group=self.group, resort=self.resort, course_type=self.course_type,
            preferred_coach=self.coach, status='completed', number_of_people=2,
            course_fee=10000, coach_fee=1000, discount_amount=1000,
        )
        self.booking_1 = Booking.objects.create(
            reservation=self.reservation, course_type='單板', course_name='初階',
            date=timezone.localdate() + timedelta(days=35), start_time=time(9), end_time=time(11), is_scheduled=True,
        )
        self.booking_2 = Booking.objects.create(
            reservation=self.reservation, course_type='單板', course_name='初階',
            date=timezone.localdate() + timedelta(days=36), start_time=time(9), end_time=time(11), is_scheduled=True,
        )

    def test_refund_uses_tier_then_subtracts_five_percent_handling_fee(self):
        values = calculate_refund(self.group)
        self.assertEqual(values['refund_percent'], 100)
        self.assertEqual(values['original_amount'], 10000)
        self.assertEqual(values['refund_amount'], 9500)

    def test_refund_rule_editor_rejects_duplicate_days_and_invalid_fee(self):
        serializer = OperatingPolicyAdminSerializer(self.policy, data={
            'cancellation_rules': [
                {'days_before': 30, 'refund_percent': 80},
                {'days_before': 30, 'refund_percent': 50},
            ],
            'cancellation_fee_percent': 101,
        }, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('cancellation_rules', serializer.errors)
        self.assertIn('cancellation_fee_percent', serializer.errors)

    def test_member_cancel_requires_owned_paid_order_and_bank_details(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='bank_transfer')
        url = f'/booking/{self.client_tenant.internal_code}/api/member-cancellations/{self.group.pk}/'
        stranger = APIClient()
        stranger.force_authenticate(user=User.objects.create_user('stranger'))
        self.assertEqual(stranger.get(url).status_code, 404)
        member = APIClient()
        member.force_authenticate(user=self.user)
        preview = member.get(url)
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.data['requires_bank_account'])
        self.assertEqual(member.post(url, {'reason': 'schedule'}, format='json').status_code, 400)
        submitted = member.post(url, {
            'reason': 'schedule', 'bank_name': 'Test Bank',
            'account_number': '123456', 'account_holder': 'Student',
        }, format='json')
        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(submitted.data['status'], 'requested')
        self.assertEqual(member.post(url, {'reason': 'schedule'}, format='json').status_code, 400)

    def test_bank_transfer_cancellation_requires_refund_bank(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='TT')
        with self.assertRaisesMessage(ValueError, '匯款訂單必須填寫'):
            request_cancellation(self.group, reason='schedule')

    def test_card_cancellation_does_not_require_refund_bank(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='credit_card')
        cancellation = request_cancellation(self.group, reason='schedule')
        self.assertEqual(cancellation.refund_amount, 9500)
        self.assertEqual(self.group.revisions.count(), 1)

    def test_staff_can_choose_configured_refund_rule(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='credit_card')
        cancellation = request_cancellation(self.group, reason='schedule', selected_rule_days_before=14)
        self.assertEqual(cancellation.calculation_mode, 'rule')
        self.assertEqual(cancellation.refund_percent, 80)
        self.assertEqual(cancellation.refund_amount, 7500)
        self.assertEqual(cancellation.selected_rule_days_before, 14)

    def test_staff_can_enter_special_refund_but_not_overpay(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid', payment_method='credit_card')
        with self.assertRaisesMessage(ValueError, '不可超過訂單金額'):
            request_cancellation(self.group, reason='weather', manual_refund_amount=10001)
        with self.assertRaisesMessage(ValueError, '不在目前營運規則中'):
            request_cancellation(self.group, reason='weather', selected_rule_days_before=99)
        cancellation = request_cancellation(self.group, reason='weather', manual_refund_amount=9800)
        self.assertEqual(cancellation.calculation_mode, 'manual')
        self.assertEqual(cancellation.refund_amount, 9800)
        self.assertEqual(cancellation.handling_fee_percent, 0)

    def test_payment_account_prefers_matching_resort_and_campus(self):
        fallback = PaymentAccount.objects.create(client=self.client_tenant, name='全域', is_default=True)
        matched = PaymentAccount.objects.create(client=self.client_tenant, name='北海道專用')
        matched.campuses.add(self.campus)
        matched.resorts.add(self.resort)
        self.assertEqual(resolve_payment_account(self.group), matched)
        matched.is_active = False
        matched.save()
        self.assertEqual(resolve_payment_account(self.group), fallback)

    def test_unpaid_order_stays_active_until_configured_expiration(self):
        payment = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            created_at=timezone.now() - timedelta(days=2),
            expires_at=timezone.now() + timedelta(days=1),
        )
        Payment.objects.filter(pk=payment.pk).update(created_at=timezone.now() - timedelta(days=2))
        auto_cancel_unpaid_reservations()
        payment.refresh_from_db()
        self.reservation.refresh_from_db()
        self.assertEqual(payment.status, 'unpaid')
        self.assertEqual(self.reservation.status, 'completed')

    def test_coach_schedule_visibility_default_and_full_setting(self):
        today = timezone.localdate()
        for offset in (-1, 10, 11):
            Booking.objects.create(
                reservation=self.reservation, course_type='單板', course_name='初階',
                date=today + timedelta(days=offset), start_time=time(9),
                end_time=time(11), is_scheduled=True,
            )
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        def visible_dates(path):
            response = api.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['data']['visibility_mode'],
                             'full' if self.coach.schedule_visibility == 'full' else 'recent_10_days')
            items = response.data['data']['list']
            if path.endswith('my-courses/'):
                return {booking['date'] for item in items for booking in item['bookings']}
            return {item['date'] for item in items}

        courses_url = '/api/admin/snowland/coach/my-courses/'
        calendar_url = '/api/admin/snowland/coach/my-calendar/'
        restricted = {(today + timedelta(days=offset)).isoformat() for offset in (-1, 10)}
        for path in (courses_url, calendar_url):
            self.assertEqual(visible_dates(path), restricted)
        future_only = api.get(courses_url, {'date_from': (today + timedelta(days=11)).isoformat()})
        self.assertEqual(future_only.status_code, 200)
        self.assertEqual(future_only.data['data']['list'], [])

        self.coach.schedule_visibility = 'full'
        self.coach.save(update_fields=['schedule_visibility'])
        all_dates = {(today + timedelta(days=offset)).isoformat() for offset in (-1, 10, 11, 35, 36)}
        for path in (courses_url, calendar_url):
            self.assertEqual(visible_dates(path), all_dates)

    def test_coach_can_confirm_future_booking_not_yet_visible_in_schedule(self):
        self.reservation.status = 'pending_coach_confirmation'
        self.reservation.save(update_fields=['status'])
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        pending = api.get('/api/admin/snowland/coach/pending/')
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.data['data']['visibility_mode'], 'all_pending')
        self.assertEqual(pending.data['data']['total'], 1)
        self.assertEqual(
            {booking['date'] for booking in pending.data['data']['list'][0]['bookings']},
            {(timezone.localdate() + timedelta(days=offset)).isoformat() for offset in (35, 36)},
        )

        for path in ('/api/admin/snowland/coach/my-courses/', '/api/admin/snowland/coach/my-calendar/'):
            response = api.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['data']['list'], [])

    def test_coach_order_views_expose_only_student_alias_and_lesson_details(self):
        self.user.first_name = '小雪'
        self.user.last_name = '私密姓氏'
        self.user.save(update_fields=['first_name', 'last_name'])
        self.reservation.status = 'pending_coach_confirmation'
        self.reservation.save(update_fields=['status'])
        self.booking_1.date = timezone.localdate() + timedelta(days=1)
        self.booking_1.save(update_fields=['date'])
        MemberDetail.objects.create(reservation=self.reservation, age_range='7-12y')
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        for path in ('coach/pending/', 'coach/my-courses/'):
            response = api.get(f'/api/admin/snowland/{path}')
            self.assertEqual(response.status_code, 200)
            item = response.data['data']['list'][0]
            self.assertEqual(item['user_name'], '小雪')
            if path == 'coach/my-courses/':
                self.assertEqual(item['course_category'], '單板')
            self.assertEqual(item['age_ranges'], ['兒童7-12y'])
            self.assertEqual(item['language_label'], '中文')
            self.assertNotIn('total_fee', item)
            self.assertNotIn('student@example.com', str(item))
            self.assertNotIn('私密姓氏', str(item))

        calendar = api.get('/api/admin/snowland/coach/my-calendar/')
        self.assertEqual(calendar.status_code, 200)
        self.assertEqual(calendar.data['data']['list'][0]['user_name'], '小雪')

    def test_coach_cannot_reject_a_completed_course(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        self.coach.schedule_visibility = 'full'
        self.coach.save(update_fields=['schedule_visibility'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        response = api.post(
            f'/api/admin/snowland/coach/confirm/{self.reservation.id}/',
            {'action': 'reject'}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        courses = api.get('/api/admin/snowland/coach/my-courses/')
        self.assertEqual(courses.status_code, 200)
        item = courses.data['data']['list'][0]
        self.assertEqual(item['status'], 'completed')
        self.assertTrue(all(booking['is_scheduled'] for booking in item['bookings']))

    def test_coach_can_accept_pending_course_but_cannot_reject_it_after_accepting(self):
        self.reservation.status = 'pending_coach_confirmation'
        self.reservation.save(update_fields=['status'])
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        self.coach.schedule_visibility = 'full'
        self.coach.save(update_fields=['schedule_visibility'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)
        url = f'/api/admin/snowland/coach/confirm/{self.reservation.id}/'

        self.assertEqual(api.post(url, {'action': 'accept'}, format='json').status_code, 200)
        self.assertEqual(api.post(url, {'action': 'reject'}, format='json').status_code, 400)
        courses = api.get('/api/admin/snowland/coach/my-courses/')
        self.assertEqual(courses.status_code, 200)
        self.assertEqual(courses.data['data']['list'][0]['status'], 'manually_assigned')

    def test_coach_cannot_view_or_confirm_another_tenants_order(self):
        other_tenant = Client.objects.create(name='Other', internal_code='other')
        other_resort = Resorts.objects.create(client=other_tenant, name='other', display_name='Other Resort')
        assistance_slot = EquipmentAssistanceTimeSlot.objects.create(
            resort=other_resort, label='裝備協助', start_time=time(8), end_time=time(8, 30),
        )
        other_group = ReservationGroup.objects.create(client=other_tenant, user=self.user)
        other_reservation = Reservation.objects.create(
            group=other_group, preferred_coach=self.coach,
            resort=other_resort, equipment='purchaseAssistanceTime',
            equipment_assistance_time_slot=assistance_slot,
            status='pending_coach_confirmation', number_of_people=1,
        )
        Booking.objects.create(
            reservation=other_reservation, date=timezone.localdate() + timedelta(days=1),
            start_time=time(9), end_time=time(11), is_scheduled=True,
        )
        Payment.objects.create(reservation_group=other_group, user=self.user, status='paid')
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        for path in ('coach/pending/', 'coach/my-courses/', 'coach/my-calendar/'):
            response = api.get(f'/api/admin/snowland/{path}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['data']['list'], [])
        response = api.post(
            f'/api/admin/snowland/coach/confirm/{other_reservation.id}/',
            {'action': 'accept'}, format='json',
        )
        self.assertEqual(response.status_code, 404)

    def test_coach_leave_counts_only_snowland_courses(self):
        leave_date = timezone.localdate() + timedelta(days=7)
        self.reservation.status = 'manually_assigned'
        self.reservation.save(update_fields=['status'])
        self.booking_1.date = leave_date
        self.booking_1.save(update_fields=['date'])
        other_tenant = Client.objects.create(name='Other', internal_code='other')
        other_group = ReservationGroup.objects.create(client=other_tenant, user=self.user)
        other_reservation = Reservation.objects.create(
            group=other_group, preferred_coach=self.coach, status='manually_assigned',
        )
        Booking.objects.create(
            reservation=other_reservation, date=leave_date,
            start_time=time(9), end_time=time(11), is_scheduled=True,
        )
        profile = self.coach_user.userprofile
        profile.is_coach = True
        profile.save(update_fields=['is_coach'])
        api = APIClient()
        api.force_authenticate(user=self.coach_user)

        response = api.post('/api/admin/snowland/coach/apply-leave/', {
            'start_date': leave_date.isoformat(),
            'end_date': leave_date.isoformat(),
            'reason': '請假測試',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['affected_count'], 1)
        leaves = api.get('/api/admin/snowland/coach/my-leaves/')
        self.assertEqual(leaves.status_code, 200)
        self.assertEqual(leaves.data['data']['list'][0]['affected_count'], 1)

    def test_coach_schedule_visibility_serializer_rejects_invalid_value(self):
        self.assertEqual(self.coach.schedule_visibility, 'ten_days')
        serializer = CoachAdminSerializer(self.coach, data={'schedule_visibility': 'anything'}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('schedule_visibility', serializer.errors)

    def test_unpaid_order_expires_after_configured_deadline(self):
        payment = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        auto_cancel_unpaid_reservations()
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'expired')

    def test_scheduled_job_releases_expired_unpaid_reservation(self):
        self.reservation.status = 'auto_assigned'
        self.reservation.save(update_fields=['status'])
        payment = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        call_command('process_snowland_jobs', '--dry-run')
        payment.refresh_from_db()
        self.reservation.refresh_from_db()
        self.assertEqual(payment.status, 'unpaid')
        self.assertEqual(self.reservation.status, 'auto_assigned')
        call_command('process_snowland_jobs')
        payment.refresh_from_db()
        self.reservation.refresh_from_db()
        self.assertEqual(payment.status, 'expired')
        self.assertEqual(self.reservation.status, 'cancelled')

    def test_expired_payment_attempt_does_not_cancel_paid_order(self):
        self.reservation.status = 'auto_assigned'
        self.reservation.save(update_fields=['status'])
        protected_payment = Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        expired_attempt = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        call_command('process_snowland_jobs')
        self.reservation.refresh_from_db()
        expired_attempt.refresh_from_db()
        self.assertEqual(self.reservation.status, 'auto_assigned')
        self.assertEqual(expired_attempt.status, 'expired')
        protected_payment.status = 'pending'
        protected_payment.save(update_fields=['status'])
        second_attempt = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        call_command('process_snowland_jobs')
        self.reservation.refresh_from_db()
        second_attempt.refresh_from_db()
        self.assertEqual(self.reservation.status, 'auto_assigned')
        self.assertEqual(second_attempt.status, 'expired')

    def test_notifications_are_scheduled_for_matching_campus(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, DataJSON={'contact': {'email': 'student@example.com'}}
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='付款通知', event='payment_confirmed',
            channel='email', subject='付款完成', body='收到款項',
        )
        other = Campus.objects.create(client=self.client_tenant, name='其他校區', code='other')
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=other, name='不應發送', event='payment_confirmed',
            channel='email', subject='錯誤', body='錯誤',
        )
        deliveries = schedule_group_notifications(self.group, 'payment_confirmed')
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].recipient, 'student@example.com')

    def test_notification_template_only_matches_selected_course_template(self):
        matching = CourseTemplate.objects.create(course_type=self.course_type, name='符合課程', duration_hours=6)
        other = CourseTemplate.objects.create(course_type=self.course_type, name='其他課程', duration_hours=3)
        self.reservation.course_template = matching
        self.reservation.save(update_fields=['course_template'])
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        template = NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='指定課程提醒', event='pre_course',
            channel='email', subject='提醒', body='內容', days_before=3,
        )
        template.course_templates.add(other)
        self.assertEqual(schedule_group_notifications(self.group, 'pre_course'), [])
        template.course_templates.add(matching)
        self.assertEqual(len(schedule_group_notifications(self.group, 'pre_course')), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_disabled_template_cancels_queued_delivery_without_sending(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        template = NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='停用提醒', event='pre_course',
            channel='email', subject='提醒', body='內容', days_before=0,
        )
        delivery = NotificationDelivery.objects.create(
            template=template, group=self.group, recipient='student@example.com',
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        template.is_active = False
        template.save(update_fields=['is_active'])
        call_command('process_snowland_jobs')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'cancelled')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_course_restriction_change_cancels_queued_delivery(self):
        matching = CourseTemplate.objects.create(course_type=self.course_type, name='原課程', duration_hours=6)
        other = CourseTemplate.objects.create(course_type=self.course_type, name='其他課程', duration_hours=3)
        self.reservation.course_template = matching
        self.reservation.save(update_fields=['course_template'])
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        template = NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='改課程提醒', event='pre_course',
            channel='email', subject='提醒', body='內容', days_before=0,
        )
        template.course_templates.add(matching)
        delivery = NotificationDelivery.objects.create(
            template=template, group=self.group, recipient='student@example.com',
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        template.course_templates.set([other])
        call_command('process_snowland_jobs')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'cancelled')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reactivated_template_creates_one_new_delivery(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        template = NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='重新啟用提醒', event='pre_course',
            channel='email', subject='提醒', body='內容', days_before=0,
        )
        original = NotificationDelivery.objects.create(
            template=template, group=self.group, recipient='student@example.com',
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        template.is_active = False
        template.save(update_fields=['is_active'])
        call_command('process_snowland_jobs')
        original.refresh_from_db()
        self.assertEqual(original.status, 'cancelled')
        template.is_active = True
        template.save(update_fields=['is_active'])
        call_command('process_snowland_jobs')
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(template=template, group=self.group).count(), 2)
        self.assertEqual(NotificationDelivery.objects.filter(template=template, group=self.group, status='sent').count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_rescheduled_course_moves_unsent_reminder_without_duplicate(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='改期提醒', event='pre_course',
            channel='email', subject='提醒', body='內容', days_before=3,
        )
        schedule_group_notifications(self.group, 'pre_course')
        delivery = NotificationDelivery.objects.get(group=self.group)
        original_time = delivery.scheduled_at
        self.booking_1.date += timedelta(days=2)
        self.booking_1.save(update_fields=['date'])
        self.booking_2.date += timedelta(days=2)
        self.booking_2.save(update_fields=['date'])
        schedule_group_notifications(self.group, 'pre_course')
        delivery.refresh_from_db()
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)
        self.assertEqual(delivery.scheduled_at, original_time + timedelta(days=2))

    def test_pre_course_reminder_waits_for_paid_order(self):
        self.reservation.status = 'auto_assigned'
        self.reservation.save(update_fields=['status'])
        payment = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            DataJSON={'contact': {'email': 'student@example.com'}},
            expires_at=timezone.now() + timedelta(days=1),
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='課前提醒', event='pre_course',
            channel='email', subject='上課提醒', body='請準備裝備', days_before=3,
        )
        call_command('process_snowland_jobs')
        self.assertFalse(NotificationDelivery.objects.filter(group=self.group).exists())
        payment.status = 'paid'
        payment.save(update_fields=['status'])
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_existing_pre_course_reminder_is_not_sent_before_payment(self):
        payment = Payment.objects.create(
            reservation_group=self.group, user=self.user, status='unpaid',
            DataJSON={'contact': {'email': 'student@example.com'}},
            expires_at=timezone.now() + timedelta(days=1),
        )
        template = NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='課前提醒', event='pre_course',
            channel='email', subject='上課提醒', body='請準備裝備', days_before=3,
        )
        delivery = NotificationDelivery.objects.create(
            template=template, group=self.group, recipient='student@example.com',
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        call_command('process_snowland_jobs')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'scheduled')
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)
        payment.status = 'paid'
        payment.save(update_fields=['status'])
        call_command('process_snowland_jobs')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'scheduled')
        self.assertGreater(delivery.scheduled_at, timezone.now())
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_immediate_reminder_is_not_duplicated_on_repeated_job_runs(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='立即提醒', event='pre_course',
            channel='email', subject='上課提醒', body='請準備裝備', days_before=0,
        )
        call_command('process_snowland_jobs')
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_completed_documents_do_not_trigger_missing_documents_reminder(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        MemberDetail.objects.create(
            reservation=self.reservation, user=self.user,
            insurance_data={'full_name': '測試學員', 'birth_date': '1990-01-01', 'id_number': 'TEST123', 'phone': '0900000000'},
            insurance_completed_at=timezone.now(), waiver_signature='測試學員',
            waiver_document_version=get_current_waiver(self.client_tenant)['version'],
            waiver_completed_at=timezone.now(),
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='文件提醒', event='missing_documents',
            channel='email', subject='補資料', body='請完成課前資料', days_before=3,
        )
        call_command('process_snowland_jobs')
        self.assertFalse(NotificationDelivery.objects.filter(group=self.group).exists())

    def test_missing_documents_reminder_is_scheduled_when_no_members_bound(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='文件提醒', event='missing_documents',
            channel='email', subject='補資料', body='請完成課前資料', days_before=3,
        )
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)

    def test_line_group_invitation_waits_for_link(self):
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='群組邀請', event='line_group',
            channel='email', subject='上課群組', body='{line_group_url}', days_before=3,
        )
        call_command('process_snowland_jobs')
        self.assertFalse(NotificationDelivery.objects.filter(group=self.group).exists())
        self.group.line_group_url = 'https://example.com/snowland-group'
        self.group.save(update_fields=['line_group_url'])
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)

    def test_incomplete_course_does_not_trigger_evaluation_reminder(self):
        self.reservation.status = 'auto_assigned'
        self.reservation.save(update_fields=['status'])
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='評量提醒', event='evaluation_due',
            channel='email', subject='填評量', body='請完成評量', days_before=0,
        )
        call_command('process_snowland_jobs')
        self.assertFalse(NotificationDelivery.objects.filter(group=self.group).exists())

    def test_completed_course_with_unfinished_evaluation_gets_reminder(self):
        MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        Payment.objects.create(
            reservation_group=self.group, user=self.user, status='paid',
            DataJSON={'contact': {'email': 'student@example.com'}},
        )
        NotificationTemplate.objects.create(
            client=self.client_tenant, campus=self.campus, name='評量提醒', event='evaluation_due',
            channel='email', subject='填評量', body='請完成評量', days_before=3,
        )
        call_command('process_snowland_jobs')
        self.assertEqual(NotificationDelivery.objects.filter(group=self.group).count(), 1)

    def test_payroll_does_not_duplicate_per_reservation_fees_across_days(self):
        CoachPayRule.objects.create(
            coach=self.coach, discipline='snowboard', hourly_rate=1000,
            specified_fee=500, referral_percent=10, supervisor_allowance=300,
        )
        statement = calculate_payroll_statement(
            coach=self.coach, campus=self.campus,
            period_start=self.booking_1.date, period_end=self.booking_2.date,
        )
        self.assertEqual(statement.course_pay, 4000)
        self.assertEqual(statement.specified_fees, 500)
        self.assertEqual(statement.referral_commission, 900)
        self.assertEqual(statement.supervisor_allowance, 300)
        self.assertEqual(statement.total_amount, 5700)

    def test_payroll_refuses_to_hide_completed_hours_without_pay_rule(self):
        with self.assertRaisesMessage(ValueError, '尚未設定薪資規則'):
            calculate_payroll_statement(
                coach=self.coach, campus=self.campus,
                period_start=self.booking_1.date, period_end=self.booking_2.date,
            )
        self.assertFalse(PayrollStatement.objects.filter(coach=self.coach, campus=self.campus).exists())

    def test_manual_payroll_items_survive_recalculation_and_are_itemized(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, referral_percent=0)
        args = dict(coach=self.coach, campus=self.campus, period_start=self.booking_1.date, period_end=self.booking_2.date)
        statement = calculate_payroll_statement(**args)
        add_payroll_adjustment(statement=statement, description='本月日文協助費', amount=1200)
        statement = calculate_payroll_statement(**args)
        self.assertEqual(statement.adjustment, 1200)
        self.assertEqual(statement.total_amount, 5200)
        self.assertEqual(statement.lines.filter(line_type='adjustment', description='本月日文協助費').count(), 1)

    def test_payroll_rejects_overlapping_period_but_allows_same_period_recalculation(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, referral_percent=0)
        start, end = self.booking_1.date, self.booking_2.date
        first = calculate_payroll_statement(coach=self.coach, campus=self.campus, period_start=start, period_end=end)
        recalculated = calculate_payroll_statement(coach=self.coach, campus=self.campus, period_start=start, period_end=end)
        self.assertEqual(recalculated.pk, first.pk)
        with self.assertRaisesMessage(ValueError, '結算期間不能重疊'):
            calculate_payroll_statement(coach=self.coach, campus=self.campus, period_start=end, period_end=end)
        self.assertEqual(PayrollStatement.objects.filter(coach=self.coach, campus=self.campus).count(), 1)

    def test_completed_course_cannot_change_time_or_coach_or_partially_update_payment(self):
        admin = User.objects.create_superuser('completion-lock-admin', 'completion-lock@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        payment = Payment.objects.create(reservation_group=self.group, user=self.user, status='pending')
        url = f'/api/admin/snowland/orders/{self.group.pk}/'
        new_date = self.booking_1.date + timedelta(days=1)
        changed_time = api.put(url, {
            'action': 'save', 'payment_status': 'paid',
            'booking_updates': [{'booking_id': self.booking_1.pk, 'date': str(new_date)}],
        }, format='json')
        self.assertEqual(changed_time.status_code, 400)
        self.assertIn('已完課', changed_time.data['msg'])
        payment.refresh_from_db(); self.booking_1.refresh_from_db()
        self.assertEqual(payment.status, 'pending')
        self.assertNotEqual(self.booking_1.date, new_date)

        another = Coach.objects.create(client=self.client_tenant, name='教練 B')
        another.campuses.add(self.campus)
        changed_coach = api.put(url, {
            'action': 'save', 'reservation_updates': [{'reservation_id': self.reservation.pk, 'coach_id': another.pk}],
        }, format='json')
        self.assertEqual(changed_coach.status_code, 400)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.preferred_coach_id, self.coach.pk)

    def test_paid_scheduled_course_completion_creates_evaluations_and_payroll_hours(self):
        admin = User.objects.create_superuser('lifecycle-admin', 'lifecycle@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        group = ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus, user=self.user, name='閉環測試')
        reservation = Reservation.objects.create(
            group=group, resort=self.resort, course_type=self.course_type,
            preferred_coach=self.coach, status='manually_assigned', course_fee=10000,
        )
        yesterday = timezone.localdate() - timedelta(days=1)
        past = Booking.objects.create(reservation=reservation, course_type='單板', course_name='初階', date=yesterday, start_time=time(9), end_time=time(11), is_scheduled=True)
        future = Booking.objects.create(reservation=reservation, course_type='單板', course_name='初階', date=timezone.localdate() + timedelta(days=1), start_time=time(9), end_time=time(11), is_scheduled=True)
        member = MemberDetail.objects.create(reservation=reservation, user=self.user)
        payment = Payment.objects.create(reservation_group=group, user=self.user, status='pending', payment_method='bank_transfer')
        url = f'/api/admin/snowland/orders/{group.id}/complete-course/'
        payload = {'reservation_id': reservation.id}

        self.assertEqual(api.post(url, payload, format='json').status_code, 400)
        payment.status = 'paid'; payment.save(update_fields=['status'])
        self.assertEqual(api.post(url, payload, format='json').status_code, 400)
        self.assertEqual(CourseEvaluation.objects.filter(member=member, booking__reservation=reservation).count(), 0)

        future.date = yesterday; future.save(update_fields=['date'])
        schedule = api.get('/api/admin/snowland/bookings/', {'start': str(yesterday), 'end': str(yesterday)})
        self.assertEqual(schedule.status_code, 200)
        self.assertTrue(any(item['id'] == past.id for item in schedule.data['data']['list']))
        completed = api.post(url, payload, format='json')
        self.assertEqual(completed.status_code, 200, completed.data)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'completed')
        self.assertEqual(CourseEvaluation.objects.filter(member=member, booking__reservation=reservation).count(), 2)
        self.assertEqual(api.post(url, payload, format='json').status_code, 200)
        self.assertEqual(CourseEvaluation.objects.filter(member=member, booking__reservation=reservation).count(), 2)

        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000, referral_percent=0)
        payroll = api.post('/api/admin/snowland/payroll-statements/calculate/', {
            'coach': self.coach.id, 'campus': self.campus.id,
            'period_start': str(yesterday), 'period_end': str(yesterday),
        }, format='json')
        self.assertEqual(payroll.status_code, 200, payroll.data)
        self.assertEqual(payroll.data['data']['course_pay'], 4000)
        self.assertEqual(PayrollStatement.objects.get(coach=self.coach, campus=self.campus).lines.filter(line_type='course').count(), 2)

    def test_cross_tenant_pay_rule_is_rejected(self):
        other_tenant = Client.objects.create(name='Other', internal_code='other')
        other_coach = Coach.objects.create(client=other_tenant, name='外部教練')
        admin = User.objects.create_superuser('root', 'root@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        response = api.post('/api/admin/snowland/coach-pay-rules/', {
            'coach': other_coach.id, 'discipline': 'ski', 'hourly_rate': 1000,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_general_pay_rule_can_be_saved_without_course_type(self):
        admin = User.objects.create_superuser('payroll-admin', 'payroll@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        response = api.post('/api/admin/snowland/coach-pay-rules/', {
            'coach': self.coach.id, 'discipline': 'snowboard', 'hourly_rate': 1000,
            'specified_fee': 0, 'referral_percent': '0',
            'assistance_hour_factor': '0', 'supervisor_allowance': 0,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(CoachPayRule.objects.filter(coach=self.coach, course_type__isnull=True).exists())
        duplicate = api.post('/api/admin/snowland/coach-pay-rules/', {
            'coach': self.coach.id, 'discipline': 'snowboard', 'hourly_rate': 1200,
        }, format='json')
        self.assertEqual(duplicate.status_code, 400)
        updated = api.patch(f'/api/admin/snowland/coach-pay-rules/{response.data["id"]}/', {
            'hourly_rate': 1200,
        }, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(CoachPayRule.objects.get(pk=response.data['id']).hourly_rate, 1200)

    def test_member_center_quick_rebook_only_returns_own_tenant_order(self):
        api = APIClient(); api.force_authenticate(self.user)
        response = api.post('/booking/snowland/api/member-center/', {
            'quick_rebook_group_id': self.group.id,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['cart']), 1)
        self.assertEqual(response.data['cart'][0]['campusId'], self.campus.id)

        stranger = User.objects.create_user('stranger')
        api.force_authenticate(stranger)
        response = api.post('/booking/snowland/api/member-center/', {
            'quick_rebook_group_id': self.group.id,
        }, format='json')
        self.assertEqual(response.status_code, 404)

    def test_member_center_returns_real_orders_forms_and_learning_records(self):
        member = MemberDetail.objects.create(
            reservation=self.reservation,
            user=self.user,
            age_range='25-35y',
            snowboard_skills=['雪場S turn'],
        )
        evaluation = CourseEvaluation.objects.create(
            booking=self.booking_1,
            member=member,
            coach=self.coach,
            learning_progress={'before': '等級 1', 'after': '等級 2'},
            coach_notes='轉彎控制已有明顯進步。',
            completed_at=timezone.now(),
        )
        CourseMedia.objects.create(
            evaluation=evaluation,
            media_type='photo',
            url='https://example.com/lesson.jpg',
            is_public=True,
        )
        CourseMedia.objects.create(
            evaluation=evaluation,
            media_type='photo',
            url='https://example.com/private.jpg',
            is_public=False,
        )
        api = APIClient(); api.force_authenticate(self.user)

        response = api.get('/booking/snowland/api/member-center/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['member']['email'], 'student@example.com')
        self.assertEqual(response.data['orders'][0]['id'], self.group.id)
        self.assertEqual(response.data['orders'][0]['reservations'][0]['resort'], 'Tomamu')
        self.assertEqual(response.data['pre_course_forms'][0]['age_range'], '25-35y')
        self.assertEqual(response.data['learning_records'][0]['coach_notes'], '轉彎控制已有明顯進步。')
        self.assertEqual(response.data['learning_records'][0]['media'][0]['url'], 'https://example.com/lesson.jpg')
        self.assertEqual(len(response.data['learning_records'][0]['media']), 1)

    def test_member_can_complete_pre_course_form_and_waiver(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        api = APIClient(); api.force_authenticate(self.user)
        response = api.post('/booking/snowland/api/member-center/', {
            'action': 'update_pre_course_form',
            'member_id': member.id,
            'age_range': '25-35y',
            'snowboard_skills': ['雪場S turn'],
            'ski_skills': [],
            'insurance_data': {
                'full_name': '測試學員', 'birth_date': '1990-01-01',
                'id_number': 'TEST123', 'phone': '0900000000',
            },
            'waiver_agreed': True,
            'waiver_signature': '測試學員',
            'waiver_document_version': 'V0-2026-10-08',
            'media_consent': 'decline',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        member.refresh_from_db()
        self.assertIsNotNone(member.insurance_completed_at)
        self.assertIsNotNone(member.waiver_completed_at)
        self.assertEqual(member.waiver_signature, '測試學員')
        self.assertEqual(member.waiver_document_version, 'V0-2026-10-08')
        self.assertEqual(member.media_consent, 'decline')
        self.assertIn('SnowLand 滑雪運動安全聲明書', member.waiver_document_snapshot)

    def test_member_old_insurance_completion_without_details_is_not_complete(self):
        member = MemberDetail.objects.create(
            reservation=self.reservation,
            user=self.user,
            age_range='25-35y',
            insurance_completed_at=timezone.now(),
            insurance_data={},
        )
        api = APIClient(); api.force_authenticate(self.user)

        response = api.get('/booking/snowland/api/member-center/')

        self.assertEqual(response.status_code, 200)
        form = next(item for item in response.data['pre_course_forms'] if item['id'] == member.id)
        self.assertFalse(form['insurance_completed'])

    def test_member_must_sign_current_waiver_version(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        api = APIClient(); api.force_authenticate(self.user)
        response = api.post('/booking/snowland/api/member-center/', {
            'action': 'update_pre_course_form',
            'member_id': member.id,
            'age_range': '25-35y',
            'insurance_data': {},
            'waiver_agreed': True,
            'waiver_signature': '測試學員',
            'waiver_document_version': 'OLD',
            'media_consent': 'decline',
        }, format='json')
        self.assertEqual(response.status_code, 409)

    def test_member_can_submit_course_satisfaction(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        evaluation = CourseEvaluation.objects.create(booking=self.booking_1, member=member, coach=self.coach)
        api = APIClient(); api.force_authenticate(self.user)
        response = api.post('/booking/snowland/api/member-center/', {
            'action': 'submit_satisfaction',
            'evaluation_id': evaluation.id,
            'rating': 5,
            'feedback': '課程很清楚。',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.self_assessment['satisfaction_rating'], 5)
        self.assertEqual(evaluation.self_assessment['satisfaction_feedback'], '課程很清楚。')

    def test_member_email_registration_and_login_use_real_django_session(self):
        api = APIClient()
        registered = api.post('/booking/snowland/api/member-auth/', {
            'action': 'register',
            'email': 'new-member@example.com',
            'password': 'secure-pass-123',
        }, format='json')
        self.assertEqual(registered.status_code, 201)
        self.assertTrue(User.objects.get(email='new-member@example.com').check_password('secure-pass-123'))
        self.assertEqual(api.get('/booking/snowland/api/member-center/').status_code, 200)

        api.post('/control/api/logout/', {}, format='json')
        rejected = api.post('/booking/snowland/api/member-auth/', {
            'action': 'login', 'email': 'new-member@example.com', 'password': 'wrong-password',
        }, format='json')
        self.assertEqual(rejected.status_code, 400)
        logged_in = api.post('/booking/snowland/api/member-auth/', {
            'action': 'login', 'email': 'new-member@example.com', 'password': 'secure-pass-123',
        }, format='json')
        self.assertEqual(logged_in.status_code, 200)

    def test_staff_booking_link_resolves_only_before_use_and_expiry(self):
        link = StaffBookingLink.objects.create(
            client=self.client_tenant, campus=self.campus, created_by=self.coach_user,
            title='北海道櫃台', expires_at=timezone.now() + timedelta(days=1),
        )
        response = APIClient().get(f'/booking/snowland/api/staff-booking-link/{link.token}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['campus']['id'], self.campus.id)
        link.used_at = timezone.now(); link.save(update_fields=['used_at'])
        self.assertEqual(APIClient().get(f'/booking/snowland/api/staff-booking-link/{link.token}/').status_code, 404)

    def test_insurance_staff_can_complete_only_assigned_campus_record(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        staff = User.objects.create_user('insurance-staff')
        profile = staff.userprofile
        profile.is_manager = True
        profile.role = 'insurance'
        profile.admin_permissions = ['insurance_records']
        profile.save()
        profile.campuses.add(self.campus)
        api = APIClient(); api.force_authenticate(staff)
        response = api.post(f'/api/admin/snowland/insurance-records/{member.id}/complete/', {
            'field': 'insurance',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        member.refresh_from_db()
        self.assertIsNotNone(member.insurance_completed_at)

    def test_insurance_list_has_one_row_per_member_for_multi_day_course(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        admin = User.objects.create_superuser('insurance-admin', 'insurance-admin@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)

        response = api.get('/api/admin/snowland/insurance-records/?status=missing')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 1)
        self.assertEqual(response.data['data']['list'][0]['id'], member.id)
        self.assertEqual(
            response.data['data']['list'][0]['sn'],
            f'{self.group.created_at:%Y%m%d}-{self.group.id:04d}',
        )

    def test_cancellation_state_cannot_skip_approval(self):
        cancellation = CancellationRequest.objects.create(
            group=self.group, reason='schedule', original_amount=10000, refund_amount=9500,
        )
        admin = User.objects.create_superuser('cancel-admin', 'cancel@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        response = api.post(f'/api/admin/snowland/cancellations/{cancellation.id}/process/', {
            'status': 'refunded',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_background_job_prepares_evaluations_for_completed_course(self):
        member = MemberDetail.objects.create(reservation=self.reservation, user=self.user)
        call_command('process_snowland_jobs')
        self.assertTrue(CourseEvaluation.objects.filter(booking=self.booking_1, member=member).exists())
        self.assertTrue(CourseEvaluation.objects.filter(booking=self.booking_2, member=member).exists())

    def test_order_console_prefers_customer_display_name_over_login_name(self):
        self.user.first_name = '小林'
        self.user.save(update_fields=['first_name'])
        admin = User.objects.create_superuser('display-admin', 'display@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)
        response = api.get('/api/admin/snowland/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['list'][0]['user_name'], '小林')
        search_response = api.get('/api/admin/snowland/orders/?search=小林')
        self.assertEqual(search_response.data['data']['total'], 1)

    def test_schedule_console_prefers_customer_display_name_over_login_name(self):
        self.user.first_name = '小林'
        self.user.save(update_fields=['first_name'])
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        admin = User.objects.create_superuser('schedule-display-admin', 'schedule-display@example.com', 'pw')
        api = APIClient(); api.force_authenticate(admin)

        response = api.get('/api/admin/snowland/bookings/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['list'][0]['user_name'], '小林')
        self.assertEqual(response.data['data']['list'][0]['order_number'], self.group.order_number)
        order_response = api.get('/api/admin/snowland/orders/')
        self.assertEqual(response.data['data']['list'][0]['sn'], order_response.data['data']['list'][0]['sn'])
