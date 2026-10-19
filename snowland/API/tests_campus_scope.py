from booking.tests_policy_support import checkout_policy_acknowledgement
from datetime import datetime, time, timedelta, timezone as datetime_timezone
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client
from Control.models import UserProfile
from Resorts.models import (
    Campus, EquipmentAssistanceTimeSlot, EquipmentPricingTier, EquipmentRentalItem,
    OperatingPolicy, PaymentAccount, ResortFee, Resorts,
)
from Coach.models import Coach, CoachPayRule, PayrollStatement
from Coursekit.models import CourseCategory, CoursePricing, CourseSession, CourseTemplate, CourseType, SeasonSetting
from Courses.models import Course
from booking.models import Booking, CancellationRequest, CourseEvaluation, MemberDetail, NotificationDelivery, NotificationTemplate, Payment, Reservation, ReservationGroup, SharedCourseClass, StaffBookingLink
from booking.api_views import CreateReservationAPI
from booking.operations import payment_expiration_for, resolve_payment_account


BANK_FIELDS = {
    'bank_name': '測試銀行',
    'bank_branch': '測試分行',
    'account_number': 'QA-ACCOUNT',
    'account_holder': '測試戶名',
}


class CampusScopeApiTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.other_tenant = Client.objects.create(name='Other', internal_code='other')
        self.resort_a = Resorts.objects.create(client=self.tenant, name='a', display_name='A 雪場')
        self.resort_b = Resorts.objects.create(client=self.tenant, name='b', display_name='B 雪場')
        self.other_resort = Resorts.objects.create(client=self.other_tenant, name='other', display_name='外部雪場')
        self.campus_a = Campus.objects.create(client=self.tenant, name='A 校區', code='a')
        self.campus_b = Campus.objects.create(client=self.tenant, name='B 校區', code='b')
        self.campus_a.resorts.add(self.resort_a)
        self.campus_b.resorts.add(self.resort_b)
        OperatingPolicy.objects.create(client=self.tenant)
        self.superuser = User.objects.create_superuser('root', 'root@example.com', 'test-password')
        self.manager = User.objects.create_user('manager', 'manager@example.com', 'test-password')
        self.profile = UserProfile.objects.get(user=self.manager)
        self.profile.is_manager = True
        self.profile.manager_client = self.tenant
        self.profile.role = 'campus_manager'
        self.profile.admin_permissions = ['orders', 'resorts', 'campuses']
        self.profile.save()
        self.profile.campuses.add(self.campus_a)
        self.manager.refresh_from_db()

    def authenticated(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_staff_booking_link_cannot_be_moved_to_another_campus_by_manager(self):
        link = StaffBookingLink.objects.create(
            client=self.tenant, campus=self.campus_a, created_by=self.manager,
            expires_at=timezone.now() + timedelta(days=1),
        )
        url = f'/api/admin/snowland/staff-booking-links/{link.id}/'
        manager = self.authenticated(self.manager)

        moved = manager.patch(url, {'campus': self.campus_b.id}, format='json')
        self.assertEqual(moved.status_code, 403, moved.data)
        link.refresh_from_db()
        self.assertEqual(link.campus_id, self.campus_a.id)
        self.assertEqual(manager.patch(url, {'title': '本道東連結'}, format='json').status_code, 200)

        headquarters = self.authenticated(self.superuser)
        selected = headquarters.patch(url, {'campus': self.campus_b.id}, format='json',
                                      HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(selected.status_code, 403, selected.data)
        link.refresh_from_db()
        self.assertEqual(link.campus_id, self.campus_a.id)
        moved_by_headquarters = headquarters.patch(url, {'campus': self.campus_b.id}, format='json')
        self.assertEqual(moved_by_headquarters.status_code, 200, moved_by_headquarters.data)
        link.refresh_from_db()
        self.assertEqual(link.campus_id, self.campus_b.id)
        self.assertEqual(manager.get(url).status_code, 404)

    def test_staff_booking_link_shares_selected_course_with_guest(self):
        template = CourseTemplate.objects.create(
            course_type=CourseType.objects.create(
                category=CourseCategory.objects.create(client=self.tenant, name='滑雪'),
                name='私人課',
            ),
            name='全天課程', duration_hours=6,
        )
        template.resorts.add(self.resort_a)
        selected_course = [{
            'campusId': self.campus_a.id,
            'resort': self.resort_a.name,
            'peopleCount': 2,
            'courses': [{
                'courseTemplateId': template.id,
                'date': (timezone.localdate() + timedelta(days=30)).isoformat(),
            }],
        }]
        created = self.authenticated(self.superuser).post(
            '/api/admin/snowland/staff-booking-links/', {
                'campus': self.campus_a.id,
                'title': '客戶已選課程',
                'expires_at': (timezone.now() + timedelta(days=1)).isoformat(),
                'cart_snapshot': selected_course,
            }, format='json',
        )
        self.assertEqual(created.status_code, 201, created.data)
        guest = APIClient().get(
            f"/booking/snowland/api/staff-booking-link/{created.data['token']}/"
        )
        self.assertEqual(guest.status_code, 200, guest.data)
        self.assertEqual(guest.data['cart_snapshot'], selected_course)

    def test_staff_booking_link_cannot_be_created_without_selected_course(self):
        created = self.authenticated(self.superuser).post(
            '/api/admin/snowland/staff-booking-links/', {
                'campus': self.campus_a.id,
                'title': '空白代客連結',
                'expires_at': (timezone.now() + timedelta(days=1)).isoformat(),
                'cart_snapshot': [],
            }, format='json',
        )
        self.assertEqual(created.status_code, 400, created.data)
        self.assertFalse(StaffBookingLink.objects.filter(title='空白代客連結').exists())

    def test_staff_booking_link_does_not_publish_internal_snapshot_fields(self):
        template=CourseTemplate.objects.create(course_type=CourseType.objects.create(
            category=CourseCategory.objects.create(client=self.tenant,name='隱私選課測試'),name='單板'),
            name='有效測試課程',duration_hours=3)
        template.resorts.add(self.resort_a)
        link = StaffBookingLink.objects.create(
            client=self.tenant, campus=self.campus_a, created_by=self.superuser,
            expires_at=timezone.now() + timedelta(days=1),
            cart_snapshot=[{
                'resort': self.resort_a.name,
                'peopleCount': 2,
                'internal_note': '不應公開的內部備註',
                'courses': [{
                    'courseTemplateId': template.pk,
                    'date': (timezone.localdate() + timedelta(days=30)).isoformat(),
                    'internal_note': '不應公開的課程備註',
                }],
            }],
        )
        guest = APIClient().get(f'/booking/snowland/api/staff-booking-link/{link.token}/')
        self.assertEqual(guest.status_code, 200, guest.data)
        self.assertEqual(guest.data['cart_snapshot'], [{
            'resort': self.resort_a.name,
            'peopleCount': 2,
            'courses': [{
                'courseTemplateId': template.pk,
                'date': (timezone.localdate() + timedelta(days=30)).isoformat(),
            }],
        }])

    def test_staff_booking_link_rejects_course_from_another_campus(self):
        course_type = CourseType.objects.create(
            category=CourseCategory.objects.create(client=self.tenant, name='滑雪'),
            name='私人課',
        )
        template = CourseTemplate.objects.create(
            course_type=course_type, name='B 校區課程', duration_hours=6,
        )
        template.resorts.add(self.resort_b)
        created = self.authenticated(self.superuser).post(
            '/api/admin/snowland/staff-booking-links/', {
                'campus': self.campus_a.id,
                'title': '不應跨校區選課',
                'expires_at': (timezone.now() + timedelta(days=1)).isoformat(),
                'cart_snapshot': [{
                    'resort': self.resort_b.name,
                    'peopleCount': 2,
                    'courses': [{
                        'courseTemplateId': template.id,
                        'date': (timezone.localdate() + timedelta(days=30)).isoformat(),
                    }],
                }],
            }, format='json',
        )
        self.assertEqual(created.status_code, 400, created.data)
        self.assertFalse(StaffBookingLink.objects.filter(title='不應跨校區選課').exists())

    def test_staff_booking_link_rejects_snapshot_fields_hidden_from_guest(self):
        template = CourseTemplate.objects.create(
            course_type=CourseType.objects.create(
                category=CourseCategory.objects.create(client=self.tenant, name='滑雪'),
                name='私人課',
            ),
            name='全天課程', duration_hours=6,
        )
        template.resorts.add(self.resort_a)
        created = self.authenticated(self.superuser).post(
            '/api/admin/snowland/staff-booking-links/', {
                'campus': self.campus_a.id,
                'title': '不應產生客人無法送出的連結',
                'expires_at': (timezone.now() + timedelta(days=1)).isoformat(),
                'cart_snapshot': [{
                    'resort': self.resort_a.name,
                    'peopleCount': 2,
                    'internal_note': '只供內部閱讀',
                    'courses': [{
                        'courseTemplateId': template.id,
                        'date': (timezone.localdate() + timedelta(days=30)).isoformat(),
                    }],
                }],
            }, format='json',
        )
        self.assertEqual(created.status_code, 400, created.data)
        self.assertFalse(StaffBookingLink.objects.filter(title='不應產生客人無法送出的連結').exists())

    def test_inactive_campus_cannot_create_or_resolve_staff_booking_link(self):
        template = CourseTemplate.objects.create(
            course_type=CourseType.objects.create(
                category=CourseCategory.objects.create(client=self.tenant, name='滑雪'),
                name='私人課',
            ),
            name='全天課程', duration_hours=6,
        )
        template.resorts.add(self.resort_b)
        self.campus_b.is_active = False
        self.campus_b.save(update_fields=['is_active'])
        headquarters = self.authenticated(self.superuser)
        url = '/api/admin/snowland/staff-booking-links/'

        payload = {
            'campus': self.campus_b.id, 'title': '停用校區連結',
            'expires_at': (timezone.now() + timedelta(days=1)).isoformat(),
            'cart_snapshot': [{
                'campusId': self.campus_b.id,
                'resort': self.resort_b.name,
                'peopleCount': 2,
                'courses': [{
                    'courseTemplateId': template.id,
                    'date': (timezone.localdate() + timedelta(days=30)).isoformat(),
                }],
            }],
        }
        created = headquarters.post(url, payload, format='json')
        self.assertEqual(created.status_code, 400, created.data)
        self.assertIn('校區已停用', str(created.data))
        manager_denied = self.authenticated(self.manager).post(url, payload, format='json')
        self.assertEqual(manager_denied.status_code, 403, manager_denied.data)
        self.assertNotIn('校區已停用', str(manager_denied.data))
        self.assertFalse(StaffBookingLink.objects.filter(campus=self.campus_b).exists())

        old_link = StaffBookingLink.objects.create(
            client=self.tenant, campus=self.campus_b, created_by=self.superuser,
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(APIClient().get(
            f'/booking/snowland/api/staff-booking-link/{old_link.token}/'
        ).status_code, 404)
        attempted_booking = headquarters.post('/booking/snowland/api/create-reservation/', {
            'staff_link': str(old_link.token), 'cart': [],
        }, format='json')
        self.assertEqual(attempted_booking.status_code, 400)
        self.assertIn('失效', attempted_booking.data['msg'])
        listed = headquarters.get(url)
        row = next(row for row in listed.data['data']['list'] if row['id'] == old_link.id)
        self.assertFalse(row['is_available'])
        selected = headquarters.get(url, HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertNotIn(old_link.id, [row['id'] for row in selected.data['data']['list']])

    def test_campus_manager_cannot_create_or_move_evaluation_to_other_campus(self):
        self.profile.admin_permissions = ['evaluations']
        self.profile.save(update_fields=['admin_permissions'])
        bookings = []
        members = []
        for campus, resort in ((self.campus_a, self.resort_a), (self.campus_b, self.resort_b)):
            group = ReservationGroup.objects.create(client=self.tenant, campus=campus, name='評量測試')
            reservation = Reservation.objects.create(group=group, resort=resort)
            bookings.append(Booking.objects.create(
                reservation=reservation, date=timezone.localdate(),
                start_time=time(9), end_time=time(11),
            ))
            members.append(MemberDetail.objects.create(reservation=reservation))

        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/evaluations/'
        own = client.post(url, {'booking': bookings[0].id, 'member': members[0].id}, format='json')
        self.assertEqual(own.status_code, 201, own.data)
        outside = client.post(url, {'booking': bookings[1].id, 'member': members[1].id}, format='json')
        self.assertEqual(outside.status_code, 400, outside.data)
        self.assertFalse(CourseEvaluation.objects.filter(booking=bookings[1]).exists())

        moved = client.patch(f'{url}{own.data["id"]}/', {
            'booking': bookings[1].id, 'member': members[1].id,
        }, format='json')
        self.assertEqual(moved.status_code, 400, moved.data)
        evaluation = CourseEvaluation.objects.get(pk=own.data['id'])
        self.assertEqual(evaluation.booking_id, bookings[0].id)

        own_update = client.patch(f'{url}{evaluation.id}/', {'coach_notes': '已完成'}, format='json')
        self.assertEqual(own_update.status_code, 200, own_update.data)
        headquarters = self.authenticated(self.superuser)
        other_campus = headquarters.post(url, {
            'booking': bookings[1].id, 'member': members[1].id,
        }, format='json')
        self.assertEqual(other_campus.status_code, 201, other_campus.data)
        self.assertEqual(client.get(f'{url}{other_campus.data["id"]}/').status_code, 404)
        second_booking = Booking.objects.create(
            reservation=bookings[1].reservation,
            date=timezone.localdate() + timedelta(days=1),
            start_time=time(9), end_time=time(11),
        )
        selected = headquarters.post(url, {
            'booking': second_booking.id, 'member': members[1].id,
        }, format='json', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(selected.status_code, 400, selected.data)

    def test_campus_principal_can_update_only_own_campus_evaluation(self):
        principal = User.objects.create_user('evaluation-principal')
        profile = principal.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'campus_principal'
        profile.admin_permissions = ['evaluations']
        profile.save(update_fields=['is_manager', 'manager_client', 'role', 'admin_permissions'])
        profile.campuses.add(self.campus_a)
        evaluations = []
        for campus, resort in ((self.campus_a, self.resort_a), (self.campus_b, self.resort_b)):
            group = ReservationGroup.objects.create(client=self.tenant, campus=campus)
            reservation = Reservation.objects.create(group=group, resort=resort, status='completed')
            booking = Booking.objects.create(
                reservation=reservation, date=timezone.localdate() - timedelta(days=1),
                start_time=time(9), end_time=time(11),
            )
            member = MemberDetail.objects.create(reservation=reservation)
            evaluations.append(CourseEvaluation.objects.create(booking=booking, member=member))

        api = self.authenticated(principal)
        url = '/api/admin/snowland/evaluations/'
        listed = api.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row['id'] for row in listed.data['data']['list']], [evaluations[0].id])
        own = api.patch(f'{url}{evaluations[0].id}/', {'coach_notes': '本校評量已填寫'}, format='json')
        self.assertEqual(own.status_code, 200, own.data)
        self.assertEqual(api.patch(f'{url}{evaluations[1].id}/', {
            'coach_notes': '越權修改',
        }, format='json').status_code, 404)
        evaluations[1].refresh_from_db()
        self.assertEqual(evaluations[1].coach_notes, '')

    def test_headquarters_keeps_inactive_campus_operational_history(self):
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_b)
        reservation = Reservation.objects.create(group=group, resort=self.resort_b)
        booking = Booking.objects.create(
            reservation=reservation, date=timezone.localdate() - timedelta(days=1),
            start_time=time(9), end_time=time(11),
        )
        member = MemberDetail.objects.create(reservation=reservation)
        evaluation = CourseEvaluation.objects.create(booking=booking, member=member)
        cancellation = CancellationRequest.objects.create(group=group, reason='schedule')
        template = NotificationTemplate.objects.create(
            client=self.tenant, campus=self.campus_b, name='歷史通知',
            event='pre_course', channel='email', body='上課提醒',
        )
        delivery = NotificationDelivery.objects.create(
            template=template, group=group, recipient='history@example.test',
            scheduled_at=timezone.now(),
        )
        self.campus_b.is_active = False
        self.campus_b.save(update_fields=['is_active'])
        self.profile.admin_permissions = ['evaluations', 'insurance_records', 'orders', 'notifications']
        self.profile.save(update_fields=['admin_permissions'])
        paths_and_ids = (
            ('evaluations', evaluation.id),
            ('insurance-records', member.id),
            ('cancellations', cancellation.id),
            ('notification-deliveries', delivery.id),
        )
        headquarters = self.authenticated(self.superuser)
        manager = self.authenticated(self.manager)
        for path, object_id in paths_and_ids:
            with self.subTest(path=path):
                url = f'/api/admin/snowland/{path}/'
                all_rows = headquarters.get(url, HTTP_X_CAMPUS_ID='all')
                self.assertEqual(all_rows.status_code, 200, all_rows.data)
                self.assertIn(object_id, [row['id'] for row in all_rows.data['data']['list']])
                self.assertEqual(headquarters.get(f'{url}{object_id}/').status_code, 200)
                selected = headquarters.get(url, HTTP_X_CAMPUS_ID=str(self.campus_a.id))
                self.assertNotIn(object_id, [row['id'] for row in selected.data['data']['list']])
                self.assertEqual(headquarters.get(
                    f'{url}{object_id}/', HTTP_X_CAMPUS_ID=str(self.campus_a.id),
                ).status_code, 404)
                manager_rows = manager.get(url)
                self.assertEqual(manager_rows.status_code, 200, manager_rows.data)
                self.assertNotIn(object_id, [row['id'] for row in manager_rows.data['data']['list']])
                self.assertEqual(manager.get(f'{url}{object_id}/').status_code, 404)

        updated = headquarters.patch(
            f'/api/admin/snowland/evaluations/{evaluation.id}/',
            {'coach_notes': '歷史評量仍可補寫'}, format='json',
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        completed_insurance = headquarters.post(
            f'/api/admin/snowland/insurance-records/{member.id}/complete/',
            {'field': 'insurance'}, format='json',
        )
        self.assertEqual(completed_insurance.status_code, 200, completed_insurance.data)
        processed_cancellation = headquarters.post(
            f'/api/admin/snowland/cancellations/{cancellation.id}/process/',
            {'status': 'approved'}, format='json',
        )
        self.assertEqual(processed_cancellation.status_code, 200, processed_cancellation.data)

    def test_headquarters_keeps_inactive_campus_coach_payroll_and_notification_settings(self):
        coach = Coach.objects.create(client=self.tenant, name='停用校區教練')
        coach.campuses.add(self.campus_b)
        rule = CoachPayRule.objects.create(coach=coach, discipline='ski', hourly_rate=1000)
        statement = PayrollStatement.objects.create(
            coach=coach, campus=self.campus_b,
            period_start=timezone.localdate() - timedelta(days=30),
            period_end=timezone.localdate(),
        )
        template = NotificationTemplate.objects.create(
            client=self.tenant, campus=self.campus_b, name='停用校區通知',
            event='pre_course', channel='email', body='上課提醒',
        )
        self.campus_b.is_active = False
        self.campus_b.save(update_fields=['is_active'])
        self.profile.admin_permissions = ['coaches', 'payroll', 'notifications']
        self.profile.save(update_fields=['admin_permissions'])
        headquarters = self.authenticated(self.superuser)
        manager = self.authenticated(self.manager)
        for path, object_id in (
            ('coaches', coach.id),
            ('coach-pay-rules', rule.id),
            ('payroll-statements', statement.id),
            ('notification-templates', template.id),
        ):
            with self.subTest(path=path):
                url = f'/api/admin/snowland/{path}/'
                all_rows = headquarters.get(url, HTTP_X_CAMPUS_ID='all')
                self.assertEqual(all_rows.status_code, 200, all_rows.data)
                self.assertIn(object_id, [row['id'] for row in all_rows.data['data']['list']])
                self.assertEqual(headquarters.get(f'{url}{object_id}/').status_code, 200)
                for restricted in (
                    headquarters.get(url, HTTP_X_CAMPUS_ID=str(self.campus_a.id)),
                    manager.get(url),
                ):
                    self.assertEqual(restricted.status_code, 200, restricted.data)
                    self.assertNotIn(object_id, [row['id'] for row in restricted.data['data']['list']])
                self.assertEqual(headquarters.get(
                    f'{url}{object_id}/', HTTP_X_CAMPUS_ID=str(self.campus_a.id),
                ).status_code, 404)
                self.assertEqual(manager.get(f'{url}{object_id}/').status_code, 404)

        all_coaches = headquarters.get('/api/admin/snowland/coach-pay-rules/coaches/')
        self.assertIn(coach.id, [row['id'] for row in all_coaches.data['data']['list']])
        updated_coach = headquarters.patch(
            f'/api/admin/snowland/coaches/{coach.id}/', {'name': '歷史教練'}, format='json',
        )
        self.assertEqual(updated_coach.status_code, 200, updated_coach.data)
        disabled_template = headquarters.patch(
            f'/api/admin/snowland/notification-templates/{template.id}/',
            {'is_active': False}, format='json',
        )
        self.assertEqual(disabled_template.status_code, 200, disabled_template.data)

    def test_campus_manager_insurance_completion_stays_in_assigned_campus(self):
        self.profile.admin_permissions = ['insurance_records']
        self.profile.save(update_fields=['admin_permissions'])
        own_group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a)
        other_group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_b)
        own = MemberDetail.objects.create(insurance_data={'full_name': 'QA 校區A'}, reservation=Reservation.objects.create(
            group=own_group, resort=self.resort_a,
        ))
        other = MemberDetail.objects.create(reservation=Reservation.objects.create(
            group=other_group, resort=self.resort_b,
        ))
        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/insurance-records/'

        listed = client.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row['id'] for row in listed.data['data']['list']], [own.id])
        self.assertNotIn('insurance_data', listed.data['data']['list'][0])
        own_detail = client.get(f'{url}{own.id}/')
        self.assertEqual(own_detail.status_code, 200, own_detail.data)
        self.assertEqual(own_detail.data['insurance_data']['full_name'], 'QA 校區A')
        headquarters = self.authenticated(self.superuser)
        selected_detail = headquarters.get(f'{url}{other.id}/', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(selected_detail.status_code, 404)
        self.assertEqual(headquarters.get(f'{url}{other.id}/').status_code, 200)
        member_client = self.authenticated(User.objects.create_user('insurance-member'))
        self.assertEqual(member_client.get(f'{url}{own.id}/').status_code, 403)
        self.assertEqual(client.get(f'{url}{other.id}/').status_code, 404)
        self.assertEqual(client.post(f'{url}{other.id}/complete/', {
            'field': 'insurance',
        }, format='json').status_code, 404)
        self.assertEqual(client.post(f'{url}{own.id}/complete/', {
            'field': 'insurance',
        }, format='json').status_code, 200)
        own.refresh_from_db(); other.refresh_from_db()
        self.assertIsNotNone(own.insurance_completed_at)
        self.assertIsNone(other.insurance_completed_at)

    def test_campus_manager_cannot_change_other_or_shared_coach_pay_rules(self):
        self.profile.admin_permissions = ['payroll']
        self.profile.save(update_fields=['admin_permissions'])
        own = Coach.objects.create(client=self.tenant, name='A 教練')
        own.campuses.add(self.campus_a)
        other = Coach.objects.create(client=self.tenant, name='B 教練')
        other.campuses.add(self.campus_b)
        shared = Coach.objects.create(client=self.tenant, name='共用教練')
        shared.campuses.add(self.campus_a, self.campus_b)
        url = '/api/admin/snowland/coach-pay-rules/'
        manager = self.authenticated(self.manager)
        headquarters = self.authenticated(self.superuser)

        scoped_coaches = manager.get(f'{url}coaches/')
        self.assertEqual(scoped_coaches.status_code, 200, scoped_coaches.data)
        self.assertEqual({row['id']: row['can_manage'] for row in scoped_coaches.data['data']['list']}, {
            own.id: True, shared.id: False,
        })
        self.assertEqual({row['id']: row['campus_ids'] for row in scoped_coaches.data['data']['list']}, {
            own.id: [self.campus_a.id], shared.id: [self.campus_a.id, self.campus_b.id],
        })
        self.assertEqual(manager.get('/api/admin/snowland/coaches/').status_code, 403)
        self.assertEqual({row['id'] for row in headquarters.get(f'{url}coaches/').data['data']['list']}, {
            own.id, other.id, shared.id,
        })

        own_rule = manager.post(url, {
            'coach': own.id, 'discipline': 'ski', 'hourly_rate': 1000,
        }, format='json')
        self.assertEqual(own_rule.status_code, 201, own_rule.data)
        for coach in (other, shared):
            blocked = manager.post(url, {
                'coach': coach.id, 'discipline': 'ski', 'hourly_rate': 2000,
            }, format='json')
            self.assertEqual(blocked.status_code, 403, blocked.data)
            self.assertFalse(CoachPayRule.objects.filter(coach=coach).exists())

        shared_rule = headquarters.post(url, {
            'coach': shared.id, 'discipline': 'ski', 'hourly_rate': 2000,
        }, format='json')
        self.assertEqual(shared_rule.status_code, 201, shared_rule.data)
        visible_rules = manager.get(url)
        self.assertEqual(visible_rules.status_code, 200, visible_rules.data)
        self.assertEqual({row['coach'] for row in visible_rules.data['data']['list']}, {own.id, shared.id})
        self.assertEqual(manager.patch(f'{url}{shared_rule.data["id"]}/', {
            'hourly_rate': 3000,
        }, format='json').status_code, 403)
        self.assertEqual(manager.delete(f'{url}{shared_rule.data["id"]}/').status_code, 403)
        self.assertEqual(manager.patch(f'{url}{own_rule.data["id"]}/', {
            'coach': other.id,
        }, format='json').status_code, 403)
        self.assertEqual(manager.patch(f'{url}{own_rule.data["id"]}/', {
            'hourly_rate': 1200,
        }, format='json').status_code, 200)
        self.assertEqual(CoachPayRule.objects.get(pk=own_rule.data['id']).hourly_rate, 1200)
        self.assertEqual(CoachPayRule.objects.get(pk=shared_rule.data['id']).hourly_rate, 2000)

    def test_payroll_requires_coach_assigned_to_selected_campus(self):
        self.profile.admin_permissions = ['payroll']
        self.profile.save(update_fields=['admin_permissions'])
        own = Coach.objects.create(client=self.tenant, name='A 教練')
        own.campuses.add(self.campus_a)
        other = Coach.objects.create(client=self.tenant, name='B 教練')
        other.campuses.add(self.campus_b)
        shared = Coach.objects.create(client=self.tenant, name='共用教練')
        shared.campuses.add(self.campus_a, self.campus_b)
        url = '/api/admin/snowland/payroll-statements/calculate/'
        payload = {
            'campus': self.campus_a.id,
            'period_start': str(timezone.localdate()),
            'period_end': str(timezone.localdate()),
        }
        manager = self.authenticated(self.manager)

        wrong_coach = manager.post(url, {**payload, 'coach': other.id}, format='json')
        self.assertEqual(wrong_coach.status_code, 400, wrong_coach.data)
        self.assertFalse(PayrollStatement.objects.filter(coach=other, campus=self.campus_a).exists())
        wrong_campus = manager.post(url, {**payload, 'coach': other.id, 'campus': self.campus_b.id}, format='json')
        self.assertEqual(wrong_campus.status_code, 403, wrong_campus.data)
        for coach in (own, shared):
            valid = manager.post(url, {**payload, 'coach': coach.id}, format='json')
            self.assertEqual(valid.status_code, 200, valid.data)
            self.assertTrue(PayrollStatement.objects.filter(coach=coach, campus=self.campus_a).exists())

        headquarters = self.authenticated(self.superuser)
        self.assertEqual(headquarters.post(url, {**payload, 'coach': other.id}, format='json').status_code, 400)
        self.profile.campuses.clear()
        self.assertEqual(manager.get('/api/admin/snowland/coach-pay-rules/').status_code, 403)
        self.assertEqual(manager.get('/api/admin/snowland/payroll-statements/').status_code, 403)

    def test_only_headquarters_can_reissue_payable_guest_order_link(self):
        guest = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='舊訪客訂單')
        Reservation.objects.create(group=guest, resort=self.resort_a, status='completed', course_fee=123)
        Payment.objects.create(reservation_group=guest, status='unpaid')
        path = f'/api/admin/snowland/orders/{guest.id}/payment-link/'

        self.assertEqual(self.authenticated(self.manager).get(path).status_code, 403)
        response = self.authenticated(self.superuser).get(path)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['valid_days'], 30)
        link = urlsplit(response.data['data']['path'])
        self.assertEqual(link.path, '/snowland/payment')
        params = parse_qs(link.query)
        self.assertEqual(params['reservation_group'], [str(guest.id)])
        payment_info = APIClient().get('/booking/snowland/api/payment-info/', {
            'reservation_group': guest.id, 'access_token': params['access_token'][0],
        })
        self.assertEqual(payment_info.status_code, 200, payment_info.data)

        guest.user = self.manager
        guest.save(update_fields=['user'])
        self.assertEqual(self.authenticated(self.superuser).get(path).status_code, 400)
        guest.user = None
        guest.save(update_fields=['user'])
        payment = guest.payments.get()
        payment.status = 'paid'
        payment.save(update_fields=['status'])
        self.assertEqual(self.authenticated(self.superuser).get(path).status_code, 400)
        other = ReservationGroup.objects.create(client=self.other_tenant, name='外部訂單')
        self.assertEqual(self.authenticated(self.superuser).get(
            f'/api/admin/snowland/orders/{other.id}/payment-link/',
        ).status_code, 404)

    def test_other_tenants_headquarters_cannot_read_snowland_campuses(self):
        outside_campus = Campus.objects.create(client=self.other_tenant, name='外部校區', code='outside')
        outsider = User.objects.create_user('outside-hq', 'outside-hq@example.test', 'test-password')
        profile = outsider.userprofile
        profile.is_manager = True
        profile.manager_client = self.other_tenant
        profile.role = 'hq_admin'
        profile.admin_permissions = ['campuses']
        profile.save(update_fields=['is_manager', 'manager_client', 'role', 'admin_permissions'])
        profile.campuses.add(outside_campus)

        response = self.authenticated(outsider).get('/api/admin/snowland/campuses/')

        self.assertEqual(response.status_code, 403)

    def test_unassigned_headquarters_cannot_read_snowland_campuses(self):
        manager = User.objects.create_user('unassigned-hq', 'unassigned@example.test', 'test-password')
        profile = manager.userprofile
        profile.is_manager = True
        profile.role = 'hq_admin'
        profile.admin_permissions = ['campuses']
        profile.save(update_fields=['is_manager', 'role', 'admin_permissions'])

        response = self.authenticated(manager).get('/api/admin/snowland/campuses/')

        self.assertEqual(response.status_code, 403)

    def test_headquarters_permission_is_bound_to_one_client_and_revoked(self):
        staff = User.objects.create_user('new-hq', 'new-hq@example.test', 'test-password')
        url = f'/api/admin/snowland/customers/{staff.id}/permission/'
        admin = self.authenticated(self.superuser)

        granted = admin.post(url, {
            'is_manager': True, 'role': 'hq_admin', 'campus_ids': [],
            'permissions': ['campuses'],
        }, format='json')
        self.assertEqual(granted.status_code, 200)
        staff.userprofile.refresh_from_db()
        self.assertEqual(staff.userprofile.manager_client_id, self.tenant.id)
        staff_api = self.authenticated(staff)
        self.assertEqual(staff_api.get('/api/admin/snowland/campuses/').status_code, 200)
        self.assertEqual(staff_api.get('/api/admin/other/campuses/').status_code, 403)

        revoked = admin.post(url, {
            'is_manager': False, 'role': '', 'campus_ids': [], 'permissions': [],
        }, format='json')
        self.assertEqual(revoked.status_code, 200)
        staff.userprofile.refresh_from_db()
        self.assertIsNone(staff.userprofile.manager_client_id)
        self.assertEqual(staff_api.get('/api/admin/snowland/campuses/').status_code, 403)

    def test_staff_list_does_not_expose_another_tenants_staff(self):
        outside_campus = Campus.objects.create(client=self.other_tenant, name='外部校區', code='outside')
        outsider = User.objects.create_user('outside-manager', 'outside@example.test', 'test-password')
        outsider.userprofile.is_manager = True
        outsider.userprofile.manager_client = self.other_tenant
        outsider.userprofile.role = 'campus_manager'
        outsider.userprofile.save(update_fields=['is_manager', 'manager_client', 'role'])
        outsider.userprofile.campuses.add(outside_campus)
        invitee = User.objects.create_user('new-staff', 'invitee@example.test', 'test-password')
        admin = self.authenticated(self.superuser)
        url = '/api/admin/snowland/staff/'

        default = admin.get(url)
        partial = admin.get(url, {'q': 'outside'})
        exact_outside = admin.get(url, {'q': outsider.email})
        exact_invitee = admin.get(url, {'q': invitee.email})

        self.assertEqual(default.status_code, 200)
        self.assertIn(self.manager.id, [item['id'] for item in default.data['data']['list']])
        for response in (default, partial, exact_outside):
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(outsider.id, [item['id'] for item in response.data['data']['list']])
        self.assertEqual(exact_invitee.status_code, 200)
        self.assertIn(invitee.id, [item['id'] for item in exact_invitee.data['data']['list']])

    def test_staff_list_excludes_other_tenants_manager_who_is_a_customer(self):
        outsider = User.objects.create_user('other-hq-customer', 'other-hq@example.test', 'test-password')
        profile = outsider.userprofile
        profile.is_manager = True
        profile.manager_client = self.other_tenant
        profile.role = 'hq_admin'
        profile.save(update_fields=['is_manager', 'manager_client', 'role'])
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, user=outsider)
        admin = self.authenticated(self.superuser)
        url = '/api/admin/snowland/staff/'

        for response in (admin.get(url), admin.get(url, {'q': outsider.email})):
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(outsider.id, [item['id'] for item in response.data['data']['list']])

    def test_staff_list_ignores_stale_campus_link_from_another_tenant(self):
        outsider = User.objects.create_user('other-hq-stale', 'other-stale@example.test', 'test-password')
        profile = outsider.userprofile
        profile.is_manager = True
        profile.manager_client = self.other_tenant
        profile.role = 'hq_admin'
        profile.save(update_fields=['is_manager', 'manager_client', 'role'])
        profile.campuses.add(self.campus_a)
        admin = self.authenticated(self.superuser)
        url = '/api/admin/snowland/staff/'

        for response in (admin.get(url), admin.get(url, {'q': outsider.email})):
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(outsider.id, [item['id'] for item in response.data['data']['list']])

    def test_staff_list_still_includes_tenants_coach(self):
        coach_user = User.objects.create_user('local-coach', 'coach@example.test', 'test-password')
        coach_user.userprofile.is_coach = True
        coach_user.userprofile.save(update_fields=['is_coach'])
        Coach.objects.create(client=self.tenant, user=coach_user, name='本校教練')

        response = self.authenticated(self.superuser).get('/api/admin/snowland/staff/')

        self.assertEqual(response.status_code, 200)
        self.assertIn(coach_user.id, [item['id'] for item in response.data['data']['list']])

    def test_staff_permission_update_preserves_other_tenants_assignment(self):
        outside_campus = Campus.objects.create(client=self.other_tenant, name='外部校區', code='outside')
        outsider = User.objects.create_user('outside-manager', 'outside@example.test', 'test-password')
        profile = outsider.userprofile
        profile.is_manager = True
        profile.manager_client = self.other_tenant
        profile.role = 'campus_manager'
        profile.admin_permissions = ['orders']
        profile.save(update_fields=['is_manager', 'manager_client', 'role', 'admin_permissions'])
        profile.campuses.add(outside_campus)

        response = self.authenticated(self.superuser).post(
            f'/api/admin/snowland/customers/{outsider.id}/permission/',
            {'is_manager': True, 'role': 'campus_manager', 'campus_ids': [self.campus_a.id],
             'permissions': ['orders']},
            format='json',
        )

        self.assertEqual(response.status_code, 409)
        profile.refresh_from_db()
        self.assertEqual(profile.role, 'campus_manager')
        self.assertEqual(profile.admin_permissions, ['orders'])
        self.assertEqual(list(profile.campuses.values_list('id', flat=True)), [outside_campus.id])

    def test_staff_permission_update_preserves_other_tenants_headquarters(self):
        outsider = User.objects.create_user('outside-hq', 'outside-hq@example.test', 'test-password')
        profile = outsider.userprofile
        profile.is_manager = True
        profile.manager_client = self.other_tenant
        profile.role = 'hq_admin'
        profile.admin_permissions = ['campuses']
        profile.save(update_fields=['is_manager', 'manager_client', 'role', 'admin_permissions'])

        response = self.authenticated(self.superuser).post(
            f'/api/admin/snowland/customers/{outsider.id}/permission/',
            {'is_manager': True, 'role': 'hq_admin', 'campus_ids': [], 'permissions': ['campuses']},
            format='json',
        )

        self.assertEqual(response.status_code, 409)
        profile.refresh_from_db()
        self.assertEqual(profile.manager_client_id, self.other_tenant.id)

    def test_coach_manager_can_read_form_choices_but_not_edit_resorts(self):
        self.profile.admin_permissions = ['coaches']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)

        resorts = client.get('/api/admin/snowland/resorts/')
        self.assertEqual(resorts.status_code, 200)
        self.assertEqual([item['id'] for item in resorts.data['data']['list']], [self.resort_a.id])
        self.assertFalse(resorts.data['data']['list'][0]['can_manage'])
        self.assertEqual(client.get('/api/admin/snowland/course-categories/').status_code, 200)
        self.assertEqual(client.get('/api/admin/snowland/course-types/').status_code, 200)
        self.assertEqual(client.post('/api/admin/snowland/resorts/', {'name': '不應新增'}, format='json').status_code, 403)

    def test_resort_template_options_are_readable_without_course_management_and_campus_scoped(self):
        category = CourseCategory.objects.create(client=self.tenant, name='滑雪')
        course_type = CourseType.objects.create(category=category, name='私人課')
        template_a = CourseTemplate.objects.create(
            course_type=course_type, name='A 課程', duration_hours=2,
        )
        template_a.resorts.add(self.resort_a)
        template_b = CourseTemplate.objects.create(
            course_type=course_type, name='B 課程', duration_hours=4,
        )
        template_b.resorts.add(self.resort_b)
        self.profile.admin_permissions = ['resorts']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)

        response = client.get('/api/admin/snowland/resorts/course-template-options/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['list'], [{
            'id': template_a.id,
            'name': 'A 課程',
            'course_type_name': '私人課',
            'duration_hours': 2,
            'resorts': [self.resort_a.id],
        }])
        self.assertEqual(client.get('/api/admin/snowland/course-templates/').status_code, 403)
        self.assertEqual(client.post('/api/admin/snowland/resorts/course-template-options/', {}, format='json').status_code, 405)

        self.profile.admin_permissions = ['orders']
        self.profile.save(update_fields=['admin_permissions'])
        no_resort_access = self.authenticated(User.objects.get(pk=self.manager.pk))
        self.assertEqual(no_resort_access.get('/api/admin/snowland/resorts/course-template-options/').status_code, 403)

    def test_coach_creation_assigns_campus_and_rejects_other_campus(self):
        self.profile.admin_permissions = ['coaches']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/coaches/'

        created = client.post(url, {'name': '道東新教練'}, format='json')
        self.assertEqual(created.status_code, 201)
        coach = Coach.objects.get(name='道東新教練')
        self.assertEqual(list(coach.campuses.values_list('id', flat=True)), [self.campus_a.id])
        self.assertEqual(created.data['data']['campus_ids'], [self.campus_a.id])
        self.assertTrue(created.data['data']['can_manage'])

        denied = client.post(url, {'name': '越權教練', 'campus_ids_input': [self.campus_b.id]}, format='json')
        self.assertEqual(denied.status_code, 400)
        self.assertFalse(Coach.objects.filter(name='越權教練').exists())

        headquarters = self.authenticated(self.superuser)
        missing = headquarters.post(url, {'name': '未選校區'}, format='json')
        self.assertEqual(missing.status_code, 400)
        shared = headquarters.post(url, {
            'name': '共用教練', 'campus_ids_input': [self.campus_a.id, self.campus_b.id],
        }, format='json')
        self.assertEqual(shared.status_code, 201)
        self.assertCountEqual(shared.data['data']['campus_ids'], [self.campus_a.id, self.campus_b.id])

    def test_headquarters_can_preserve_existing_inactive_coach_campus(self):
        coach = Coach.objects.create(client=self.tenant, name='歷史教練')
        coach.campuses.add(self.campus_b)
        self.campus_b.is_active = False
        self.campus_b.save(update_fields=['is_active'])
        headquarters = self.authenticated(self.superuser)
        url = f'/api/admin/snowland/coaches/{coach.id}/'

        detail = headquarters.get(url)
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['campus_assignments'], [{
            'id': self.campus_b.id, 'name': 'B 校區', 'is_active': False,
        }])
        saved = headquarters.put(url, {
            'name': '歷史教練已更新', 'campus_ids_input': [self.campus_b.id],
        }, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(list(coach.campuses.values_list('id', flat=True)), [self.campus_b.id])

        another = Coach.objects.create(client=self.tenant, name='新教練')
        another.campuses.add(self.campus_a)
        denied = headquarters.patch(f'/api/admin/snowland/coaches/{another.id}/', {
            'campus_ids_input': [self.campus_a.id, self.campus_b.id],
        }, format='json')
        self.assertEqual(denied.status_code, 400, denied.data)
        self.assertEqual(list(another.campuses.values_list('id', flat=True)), [self.campus_a.id])

    def test_shared_coach_is_read_only_for_one_campus(self):
        self.profile.admin_permissions = ['coaches']
        self.profile.save(update_fields=['admin_permissions'])
        coach = Coach.objects.create(client=self.tenant, name='共用教練')
        coach.campuses.set([self.campus_a, self.campus_b])
        client = self.authenticated(self.manager)
        url = f'/api/admin/snowland/coaches/{coach.id}/'

        detail = client.get(url)
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.data['can_manage'])
        self.assertEqual(client.patch(url, {'name': '越權修改'}, format='json').status_code, 403)
        self.assertEqual(client.delete(url).status_code, 403)
        coach.refresh_from_db()
        self.assertEqual(coach.name, '共用教練')

    def test_coach_with_order_cannot_be_deleted(self):
        self.profile.admin_permissions = ['coaches']
        self.profile.save(update_fields=['admin_permissions'])
        coach = Coach.objects.create(client=self.tenant, name='已有課程教練')
        coach.campuses.add(self.campus_a)
        category = CourseCategory.objects.create(client=self.tenant, name='單板')
        course_type = CourseType.objects.create(category=category, name='一般課程')
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='測試訂單')
        Reservation.objects.create(group=group, resort=self.resort_a, course_type=course_type, preferred_coach=coach)

        response = self.authenticated(self.manager).delete(f'/api/admin/snowland/coaches/{coach.id}/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Coach.objects.filter(pk=coach.id).exists())

    def test_headquarters_can_list_all_and_filter_one_campus(self):
        client = self.authenticated(self.superuser)
        response = client.get('/api/admin/snowland/campuses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 2)

        response = client.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID='all')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item['id'] for item in response.data['data']['list']}, {self.resort_a.id, self.resort_b.id})

        response = client.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data['data']['list']], [self.resort_a.id])

    def test_new_campus_uses_company_policy_until_it_gets_its_own(self):
        headquarters = self.authenticated(self.superuser)
        company_policy = OperatingPolicy.objects.get(client=self.tenant, campus__isnull=True)
        updated = headquarters.patch(
            f'/api/admin/snowland/operating-policies/{company_policy.id}/',
            {'unpaid_hold_days': 7}, format='json',
        )
        self.assertEqual(updated.status_code, 200)

        created = headquarters.post('/api/admin/snowland/campuses/', {
            'name': '新校區', 'code': 'new-campus', 'resort_ids': [self.resort_a.id],
        }, format='json')
        self.assertEqual(created.status_code, 201)
        campus_id = created.data['id']
        group = ReservationGroup.objects.create(client=self.tenant, campus_id=campus_id)
        self.assertAlmostEqual(
            (payment_expiration_for(group) - timezone.now()).total_seconds(), 7 * 86400, delta=5,
        )

        updated = headquarters.patch(
            f'/api/admin/snowland/operating-policies/{company_policy.id}/',
            {'unpaid_hold_days': 9}, format='json',
        )
        self.assertEqual(updated.status_code, 200)
        self.assertAlmostEqual(
            (payment_expiration_for(group) - timezone.now()).total_seconds(), 9 * 86400, delta=5,
        )

    def test_new_campus_override_starts_from_company_values_then_becomes_independent(self):
        headquarters = self.authenticated(self.superuser)
        company_policy = OperatingPolicy.objects.get(client=self.tenant, campus__isnull=True)
        headquarters.patch(
            f'/api/admin/snowland/operating-policies/{company_policy.id}/',
            {'unpaid_hold_days': 7}, format='json',
        )
        created = headquarters.post('/api/admin/snowland/campuses/', {
            'name': '新校區', 'code': 'new-campus',
        }, format='json')
        self.assertEqual(created.status_code, 201)
        campus_id = created.data['id']
        group = ReservationGroup.objects.create(client=self.tenant, campus_id=campus_id)

        override = headquarters.post('/api/admin/snowland/operating-policies/', {
            'campus': campus_id,
        }, format='json')
        self.assertEqual(override.status_code, 201)
        self.assertAlmostEqual(
            (payment_expiration_for(group) - timezone.now()).total_seconds(), 7 * 86400, delta=5,
        )

        headquarters.patch(
            f'/api/admin/snowland/operating-policies/{company_policy.id}/',
            {'unpaid_hold_days': 9}, format='json',
        )
        self.assertAlmostEqual(
            (payment_expiration_for(group) - timezone.now()).total_seconds(), 7 * 86400, delta=5,
        )

    def test_duplicate_campus_code_returns_validation_error_without_creating_campus(self):
        client = self.authenticated(self.superuser)
        before = Campus.objects.filter(client=self.tenant).count()
        response = client.post('/api/admin/snowland/campuses/', {
            'name': '重複代碼校區', 'code': self.campus_a.code,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('code', response.data)
        self.assertEqual(Campus.objects.filter(client=self.tenant).count(), before)

        update = client.patch(f'/api/admin/snowland/campuses/{self.campus_b.id}/', {
            'code': self.campus_a.code,
        }, format='json')
        self.assertEqual(update.status_code, 400)
        self.assertIn('code', update.data)
        self.campus_b.refresh_from_db()
        self.assertEqual(self.campus_b.code, 'b')

        unchanged = client.patch(f'/api/admin/snowland/campuses/{self.campus_a.id}/', {
            'code': self.campus_a.code,
        }, format='json')
        self.assertEqual(unchanged.status_code, 200)

    def test_headquarters_can_create_campus_without_technical_code(self):
        client = self.authenticated(self.superuser)
        response = client.post('/api/admin/snowland/campuses/', {
            'name': '不用填代碼的校區', 'resort_ids': [self.resort_a.id],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        campus = Campus.objects.get(pk=response.data['id'])
        self.assertTrue(campus.code.startswith('campus-'))
        self.assertEqual(campus.name, '不用填代碼的校區')
        self.assertEqual(list(campus.resorts.values_list('id', flat=True)), [self.resort_a.id])

        second = client.post('/api/admin/snowland/campuses/', {
            'name': '第二個校區', 'code': '',
        }, format='json')
        self.assertEqual(second.status_code, 201, second.data)
        self.assertNotEqual(second.data['code'], campus.code)
        rejected = client.patch(f'/api/admin/snowland/campuses/{campus.id}/', {
            'code': '',
        }, format='json')
        self.assertEqual(rejected.status_code, 400, rejected.data)
        campus.refresh_from_db()
        self.assertNotEqual(campus.code, '')

        manager = self.authenticated(self.manager)
        denied = manager.post('/api/admin/snowland/campuses/', {
            'name': '越權新增校區',
        }, format='json')
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(Campus.objects.filter(client=self.tenant, name='越權新增校區').exists())

    def test_headquarters_can_assign_new_unassigned_resort_to_campus(self):
        headquarters = self.authenticated(self.superuser)
        created = headquarters.post('/api/admin/snowland/resorts/', {
            'name': 'unassigned', 'display_name': '待分配雪場',
        }, format='json')
        self.assertEqual(created.status_code, 201)
        resort = Resorts.objects.get(client=self.tenant, name='unassigned')
        self.assertFalse(resort.campuses.exists())

        all_resorts = headquarters.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID='all')
        self.assertEqual(all_resorts.status_code, 200)
        self.assertIn(resort.id, [item['id'] for item in all_resorts.data['data']['list']])
        scoped = headquarters.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertNotIn(resort.id, [item['id'] for item in scoped.data['data']['list']])
        manager = self.authenticated(self.manager)
        limited = manager.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID='all')
        self.assertNotIn(resort.id, [item['id'] for item in limited.data['data']['list']])

        assigned = headquarters.patch(f'/api/admin/snowland/campuses/{self.campus_a.id}/', {
            'resort_ids': [self.resort_a.id, resort.id],
        }, format='json')
        self.assertEqual(assigned.status_code, 200)
        self.assertTrue(self.campus_a.resorts.filter(id=resort.id).exists())
        visible = manager.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID='all')
        self.assertIn(resort.id, [item['id'] for item in visible.data['data']['list']])

    def test_resort_list_shows_campus_status_without_exposing_other_campuses_to_manager(self):
        self.campus_b.resorts.add(self.resort_a)
        self.campus_b.is_active = False
        self.campus_b.save(update_fields=['is_active'])
        unassigned = Resorts.objects.create(client=self.tenant, name='unassigned', display_name='未分配雪場')
        url = '/api/admin/snowland/resorts/'

        headquarters = self.authenticated(self.superuser).get(url, HTTP_X_CAMPUS_ID='all')
        self.assertEqual(headquarters.status_code, 200)
        hq_rows = {item['id']: item for item in headquarters.data['data']['list']}
        self.assertEqual(hq_rows[self.resort_a.id]['campus_assignments'], [
            {'id': self.campus_a.id, 'name': 'A 校區', 'is_active': True},
            {'id': self.campus_b.id, 'name': 'B 校區', 'is_active': False},
        ])
        self.assertEqual(hq_rows[unassigned.id]['campus_assignments'], [])

        manager = self.authenticated(self.manager).get(url, HTTP_X_CAMPUS_ID='all')
        self.assertEqual(manager.status_code, 200)
        manager_rows = {item['id']: item for item in manager.data['data']['list']}
        self.assertEqual(manager_rows[self.resort_a.id]['campus_assignments'], [
            {'id': self.campus_a.id, 'name': 'A 校區', 'is_active': True},
        ])
        self.assertNotIn(unassigned.id, manager_rows)

    def test_campus_manager_is_limited_to_assigned_campus(self):
        client = self.authenticated(self.manager)
        response = client.get('/api/admin/snowland/campuses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data['data']['list']], [self.campus_a.id])

        resorts = client.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID='all')
        self.assertEqual([item['id'] for item in resorts.data['data']['list']], [self.resort_a.id])

        create = client.post('/api/admin/snowland/campuses/', {'name': '未授權', 'code': 'denied'}, format='json')
        self.assertEqual(create.status_code, 403)

        forbidden = client.get('/api/admin/snowland/resorts/', HTTP_X_CAMPUS_ID=str(self.campus_b.id))
        self.assertEqual(forbidden.status_code, 403)

    def test_removing_resort_from_campus_keeps_historical_order_visible(self):
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='舊訂單')
        Payment.objects.create(reservation_group=group, status='paid')
        coach = Coach.objects.create(client=self.tenant, name='舊課程教練')
        coach.campuses.add(self.campus_a)
        reservation = Reservation.objects.create(
            group=group, resort=self.resort_a, number_of_people=1,
            preferred_coach=coach, status='manually_assigned',
        )
        Booking.objects.create(
            reservation=reservation, date=timezone.localdate() + timedelta(days=1),
            start_time=time(9), end_time=time(11), course_type='單板', course_name='舊課程',
            is_scheduled=True,
        )
        headquarters = self.authenticated(self.superuser)
        response = headquarters.patch(f'/api/admin/snowland/campuses/{self.campus_a.id}/', {
            'resort_ids': [],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.campus_a.resorts.exists())

        self.profile.admin_permissions = ['orders', 'resorts', 'campuses', 'scheduling']
        self.profile.save(update_fields=['admin_permissions'])
        manager = self.authenticated(self.manager)
        resorts = manager.get('/api/admin/snowland/resorts/')
        self.assertEqual(resorts.status_code, 200)
        self.assertEqual(resorts.data['data']['list'], [])
        orders = manager.get('/api/admin/snowland/orders/')
        self.assertEqual(orders.status_code, 200)
        self.assertEqual([item['id'] for item in orders.data['data']['list']], [group.id])
        schedule = manager.get('/api/admin/snowland/bookings/', {
            'start': timezone.localdate().isoformat(),
            'end': (timezone.localdate() + timedelta(days=2)).isoformat(),
        })
        self.assertEqual(schedule.status_code, 200)
        self.assertEqual(schedule.data['data']['total'], 1)
        self.assertEqual(reservation.resort_id, self.resort_a.id)

    def test_resort_with_historical_order_cannot_be_deleted(self):
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='歷史訂單')
        reservation = Reservation.objects.create(group=group, resort=self.resort_a, number_of_people=1)
        headquarters = self.authenticated(self.superuser)

        response = headquarters.delete(f'/api/admin/snowland/resorts/{self.resort_a.id}/')

        self.assertEqual(response.status_code, 400)
        self.assertIn('已有訂單或課程紀錄', str(response.data))
        self.assertTrue(Resorts.objects.filter(pk=self.resort_a.id).exists())
        reservation.refresh_from_db()
        self.assertEqual(reservation.resort_id, self.resort_a.id)

    def test_resort_without_history_can_be_deleted(self):
        response = self.authenticated(self.superuser).delete(
            f'/api/admin/snowland/resorts/{self.resort_a.id}/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Resorts.objects.filter(pk=self.resort_a.id).exists())

    def test_invalid_resort_fee_returns_400_without_changing_existing_fee(self):
        fee = ResortFee.objects.create(resort=self.resort_a, fee_type='coach_general', price=1000)
        client = self.authenticated(self.superuser)
        url = f'/api/admin/snowland/resorts/{self.resort_a.id}/'
        for invalid_fee in (
            {'fee_type': 'coach_general', 'price': -1},
            {'fee_type': 'coach_general'},
            {'fee_type': 'unknown', 'price': 500},
            [
                {'fee_type': 'coach_general', 'price': 1000},
                {'fee_type': 'coach_general', 'price': 2000},
            ],
        ):
            with self.subTest(invalid_fee=invalid_fee):
                response = client.patch(url, {
                    'display_name': '不應儲存',
                    'fees_input': invalid_fee if isinstance(invalid_fee, list) else [invalid_fee],
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.resort_a.refresh_from_db()
                fee.refresh_from_db()
                self.assertEqual(self.resort_a.display_name, 'A 雪場')
                self.assertEqual(fee.price, 1000)

    def test_valid_resort_fee_update_preserves_other_fields(self):
        fee = ResortFee.objects.create(resort=self.resort_a, fee_type='coach_general', price=1000)
        response = self.authenticated(self.superuser).patch(
            f'/api/admin/snowland/resorts/{self.resort_a.id}/', {
                'fees_input': [{'fee_type': 'coach_general', 'price': 1200, 'is_active': True}],
            }, format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        fee.refresh_from_db()
        self.resort_a.refresh_from_db()
        self.assertEqual(fee.price, 1200)
        self.assertEqual(self.resort_a.display_name, 'A 雪場')

    def test_zero_coach_fee_is_distinct_from_missing_fee(self):
        self.assertEqual(ResortFee.get_coach_fee(self.resort_a, 'general'), 1000)
        url = f'/api/admin/snowland/resorts/{self.resort_a.id}/'
        client = self.authenticated(self.superuser)

        response = client.patch(url, {
            'fees_input': [{'fee_type': 'coach_general', 'price': 0}],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(ResortFee.get_coach_fee(self.resort_a, 'general'), 0)
        self.assertEqual(ResortFee.objects.get(resort=self.resort_a, fee_type='coach_general').price, 0)

        response = client.patch(url, {'fees_input': []}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(ResortFee.get_coach_fee(self.resort_a, 'general'), 1000)

    def test_invalid_equipment_tier_preserves_existing_resort_settings(self):
        tier = EquipmentPricingTier.objects.create(
            resort=self.resort_a, min_people=1, max_people=3, price=1000,
        )
        url = f'/api/admin/snowland/resorts/{self.resort_a.id}/'
        for invalid in (
            {'min_people': 1, 'max_people': 3},
            {'min_people': 'bad', 'max_people': 3, 'price': 2000},
            {'min_people': 1, 'max_people': 3, 'price': -1, 'is_active': False},
        ):
            with self.subTest(invalid=invalid):
                response = self.authenticated(self.superuser).patch(url, {
                    'display_name': '不應儲存', 'equipment_tiers_input': [invalid],
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.resort_a.refresh_from_db()
                tier.refresh_from_db()
                self.assertEqual(self.resort_a.display_name, 'A 雪場')
                self.assertEqual(tier.price, 1000)
                self.assertEqual(EquipmentPricingTier.objects.filter(resort=self.resort_a).count(), 1)

    def test_invalid_equipment_rental_item_preserves_existing_resort_settings(self):
        item = EquipmentRentalItem.objects.create(
            resort=self.resort_a, code='ski', name='雪板', daily_price=500,
        )
        url = f'/api/admin/snowland/resorts/{self.resort_a.id}/'
        for invalid in (
            {'code': 'ski', 'daily_price': 500},
            {'code': 'ski', 'name': '雪板'},
            {'code': 'ski', 'name': '雪板', 'daily_price': 'bad'},
            {'code': 'ski', 'name': '雪板', 'daily_price': -1, 'is_active': False},
        ):
            with self.subTest(invalid=invalid):
                response = self.authenticated(self.superuser).patch(url, {
                    'display_name': '不應儲存', 'equipment_rental_items_input': [invalid],
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.resort_a.refresh_from_db()
                item.refresh_from_db()
                self.assertEqual(self.resort_a.display_name, 'A 雪場')
                self.assertEqual(item.daily_price, 500)
                self.assertEqual(EquipmentRentalItem.objects.filter(resort=self.resort_a).count(), 1)

    def test_explicit_free_equipment_rental_item_price_is_allowed(self):
        response = self.authenticated(self.superuser).patch(
            f'/api/admin/snowland/resorts/{self.resort_a.id}/',
            {'equipment_rental_items_input': [
                {'code': 'free_ski', 'name': '免費裝備', 'daily_price': 0},
            ]},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        item = EquipmentRentalItem.objects.get(resort=self.resort_a, code='free_ski')
        self.assertEqual(item.daily_price, 0)
        self.assertEqual(item.additional_day_price, 0)

    def test_invalid_equipment_time_slot_preserves_existing_resort_settings(self):
        slot = EquipmentAssistanceTimeSlot.objects.create(resort=self.resort_a, label='09:00 - 10:00')
        url = f'/api/admin/snowland/resorts/{self.resort_a.id}/'
        for invalid in (
            {'course_template_ids': [1]},
            {'label': '09:00 - 10:00', 'start_time': 'not-a-time'},
        ):
            with self.subTest(invalid=invalid):
                response = self.authenticated(self.superuser).patch(url, {
                    'display_name': '不應儲存', 'equipment_time_slots_input': [invalid],
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.resort_a.refresh_from_db()
                self.assertEqual(self.resort_a.display_name, 'A 雪場')
                self.assertTrue(EquipmentAssistanceTimeSlot.objects.filter(pk=slot.id).exists())

    def test_valid_equipment_settings_can_be_saved_and_explicitly_cleared(self):
        url = f'/api/admin/snowland/resorts/{self.resort_a.id}/'
        client = self.authenticated(self.superuser)
        response = client.patch(url, {
            'equipment_tiers_input': [
                {'min_people': 1, 'max_people': 3, 'price': 1000},
            ],
            'equipment_rental_items_input': [
                {'code': 'ski', 'name': '雪板', 'daily_price': 500},
            ],
            'equipment_time_slots_input': [
                {'label': '09:00 - 10:00', 'start_time': '09:00', 'end_time': '10:00'},
            ],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(EquipmentPricingTier.objects.get(resort=self.resort_a).price, 1000)
        self.assertEqual(EquipmentRentalItem.objects.get(resort=self.resort_a).daily_price, 500)
        self.assertEqual(EquipmentAssistanceTimeSlot.objects.get(resort=self.resort_a).label, '09:00 - 10:00')

        response = client.patch(url, {
            'equipment_tiers_input': [],
            'equipment_rental_items_input': [],
            'equipment_time_slots_input': [],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(EquipmentPricingTier.objects.filter(resort=self.resort_a).exists())
        self.assertFalse(EquipmentRentalItem.objects.filter(resort=self.resort_a).exists())
        self.assertFalse(EquipmentAssistanceTimeSlot.objects.filter(resort=self.resort_a).exists())

    def test_time_slot_rejects_other_resort_course_without_dropping_existing_binding(self):
        category = CourseCategory.objects.create(client=self.tenant, name='滑雪')
        course_type = CourseType.objects.create(category=category, name='私人課')
        own_template = CourseTemplate.objects.create(course_type=course_type, name='A 課程', duration_hours=2)
        own_template.resorts.add(self.resort_a)
        other_template = CourseTemplate.objects.create(course_type=course_type, name='B 課程', duration_hours=2)
        other_template.resorts.add(self.resort_b)
        slot = EquipmentAssistanceTimeSlot.objects.create(resort=self.resort_a, label='09:00 - 10:00')
        slot.course_templates.add(own_template)

        response = self.authenticated(self.superuser).patch(
            f'/api/admin/snowland/resorts/{self.resort_a.id}/', {
                'display_name': '不應儲存',
                'equipment_time_slots_input': [
                    {'label': slot.label, 'course_template_ids': [other_template.id]},
                ],
            }, format='json',
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.resort_a.refresh_from_db()
        self.assertEqual(self.resort_a.display_name, 'A 雪場')
        self.assertEqual(list(slot.course_templates.values_list('id', flat=True)), [own_template.id])

    def test_duplicate_inactive_equipment_rows_return_400_without_changing_resort(self):
        url = f'/api/admin/snowland/resorts/{self.resort_a.id}/'
        duplicates = (
            ('equipment_tiers_input', [
                {'min_people': 1, 'max_people': 3, 'price': 1000, 'is_active': False},
                {'min_people': 1, 'max_people': 3, 'price': 2000, 'is_active': False},
            ]),
            ('equipment_rental_items_input', [
                {'code': 'ski', 'name': '雪板', 'is_active': False},
                {'code': 'ski', 'name': '雪板二', 'is_active': False},
            ]),
            ('equipment_time_slots_input', [
                {'label': '09:00 - 10:00', 'is_active': False},
                {'label': '09:00 - 10:00', 'is_active': False},
            ]),
        )
        for field, rows in duplicates:
            with self.subTest(field=field):
                response = self.authenticated(self.superuser).patch(url, {
                    'display_name': '不應儲存', field: rows,
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.resort_a.refresh_from_db()
                self.assertEqual(self.resort_a.display_name, 'A 雪場')

    def test_resort_with_course_slot_cannot_be_deleted(self):
        course = Course.objects.create(resort=self.resort_a, date_range='12/01–12/31', main_time='09:00–11:00')

        response = self.authenticated(self.superuser).delete(
            f'/api/admin/snowland/resorts/{self.resort_a.id}/'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('已有訂單或課程紀錄', str(response.data))
        self.assertTrue(Resorts.objects.filter(pk=self.resort_a.id).exists())
        self.assertTrue(Course.objects.filter(pk=course.id).exists())

    def test_stale_cart_cannot_reassign_an_unassigned_resort(self):
        self.campus_a.resorts.remove(self.resort_a)
        before_campuses = Campus.objects.filter(client=self.tenant).count()
        item = {
            'resort': self.resort_a.name,
            'resortName': self.resort_a.display_name,
            'courseCategory': '測試課程',
        }
        with self.assertRaisesMessage(ValueError, '雪場目前未分配到可用校區'):
            CreateReservationAPI()._create_reservation_group(
                user=None, item=item, tenant_client=self.tenant,
                contact_info={'referral_source': '官網'},
            )
        with patch('booking.api_views.calculate_cart_discount_summary', return_value={}):
            response = self.authenticated(self.manager).post('/booking/snowland/api/create-reservation/', {
                **checkout_policy_acknowledgement(),
                'contact': {
                    'name': '舊購物車測試', 'phone': '0900000000',
                    'messengerType': 'line', 'messengerId': 'qa-test',
                    'referralSource': '官網',
                },
                'cart': [item],
            }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('雪場目前未分配到可用校區', response.data['msg'])
        self.assertEqual(Campus.objects.filter(client=self.tenant).count(), before_campuses)
        self.assertFalse(self.resort_a.campuses.exists())
        self.assertFalse(ReservationGroup.objects.filter(client=self.tenant).exists())

    def test_disabling_only_campus_immediately_revokes_manager_resort_access(self):
        client = self.authenticated(self.manager)
        self.assertEqual(client.get('/api/admin/snowland/resorts/').status_code, 200)
        self.campus_a.is_active = False
        self.campus_a.save(update_fields=['is_active'])
        self.assertEqual(client.get('/api/admin/snowland/resorts/').status_code, 403)
        self.assertEqual(client.get('/api/admin/snowland/resorts/course-template-options/').status_code, 403)
        self.assertEqual(client.patch(
            f'/api/admin/snowland/resorts/{self.resort_a.id}/',
            {'display_name': '不應修改'}, format='json',
        ).status_code, 403)
        self.resort_a.refresh_from_db()
        self.assertEqual(self.resort_a.display_name, 'A 雪場')

        self.campus_a.is_active = True
        self.campus_a.save(update_fields=['is_active'])
        self.assertEqual(client.get('/api/admin/snowland/resorts/').status_code, 200)

    def test_headquarters_can_find_historical_order_after_campus_is_disabled(self):
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='停用前的訂單')
        Reservation.objects.create(group=group, resort=self.resort_a, number_of_people=1)
        Payment.objects.create(reservation_group=group, status='paid')
        self.campus_a.is_active = False
        self.campus_a.save(update_fields=['is_active'])

        headquarters = self.authenticated(self.superuser)
        orders = headquarters.get('/api/admin/snowland/orders/')
        self.assertEqual(orders.status_code, 200, orders.data)
        self.assertIn(group.id, [item['id'] for item in orders.data['data']['list']])
        detail = headquarters.get(f'/api/admin/snowland/orders/{group.id}/')
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['data']['id'], group.id)
        selected_other = headquarters.get('/api/admin/snowland/orders/', HTTP_X_CAMPUS_ID=str(self.campus_b.id))
        self.assertEqual(selected_other.status_code, 200, selected_other.data)
        self.assertNotIn(group.id, [item['id'] for item in selected_other.data['data']['list']])
        self.assertEqual(headquarters.get(
            '/api/admin/snowland/orders/', HTTP_X_CAMPUS_ID=str(self.campus_a.id),
        ).status_code, 403)

        public_resorts = APIClient().get('/booking/snowland/api/resorts/')
        self.assertEqual(public_resorts.status_code, 200, public_resorts.data)
        self.assertNotIn(self.resort_a.name, [item['name'] for item in public_resorts.data])

        manager = self.authenticated(self.manager)
        self.assertEqual(manager.get(f'/api/admin/snowland/orders/{group.id}/').status_code, 403)

    def test_campus_manager_new_resort_is_attached_to_selected_campus(self):
        client = self.authenticated(self.manager)
        response = client.post('/api/admin/snowland/resorts/', {
            'name': 'new-a-resort', 'display_name': 'A 新雪場',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        resort = Resorts.objects.get(name='new-a-resort')
        self.assertEqual(list(resort.campuses.values_list('id', flat=True)), [self.campus_a.id])
        visible = client.get('/api/admin/snowland/resorts/')
        self.assertIn(resort.id, [item['id'] for item in visible.data['data']['list']])
        self.assertTrue(next(item for item in visible.data['data']['list'] if item['id'] == resort.id)['can_manage'])

    def test_shared_resort_cannot_be_changed_by_one_campus(self):
        self.campus_b.resorts.add(self.resort_a)
        client = self.authenticated(self.manager)
        update = client.patch(f'/api/admin/snowland/resorts/{self.resort_a.id}/', {
            'display_name': '不應跨校區變更',
        }, format='json')
        self.assertEqual(update.status_code, 403)
        visible = client.get('/api/admin/snowland/resorts/')
        self.assertFalse(next(item for item in visible.data['data']['list'] if item['id'] == self.resort_a.id)['can_manage'])
        delete = client.delete(f'/api/admin/snowland/resorts/{self.resort_a.id}/')
        self.assertEqual(delete.status_code, 403)
        self.resort_a.refresh_from_db()
        self.assertEqual(self.resort_a.display_name, 'A 雪場')
        self.assertCountEqual(
            self.resort_a.campuses.values_list('id', flat=True),
            [self.campus_a.id, self.campus_b.id],
        )

    def test_manager_with_multiple_campuses_must_choose_one_before_creating_resort(self):
        self.profile.campuses.add(self.campus_b)
        client = self.authenticated(self.manager)
        payload = {'name': 'new-resort', 'display_name': '新雪場'}
        ambiguous = client.post('/api/admin/snowland/resorts/', payload, format='json')
        self.assertEqual(ambiguous.status_code, 400)
        self.assertFalse(Resorts.objects.filter(name='new-resort').exists())

        selected = client.post('/api/admin/snowland/resorts/', payload, format='json',
                               HTTP_X_CAMPUS_ID=str(self.campus_b.id))
        self.assertEqual(selected.status_code, 201)
        self.assertEqual(list(Resorts.objects.get(name='new-resort').campuses.values_list('id', flat=True)),
                         [self.campus_b.id])

    def test_headquarters_can_update_shared_resort(self):
        self.campus_b.resorts.add(self.resort_a)
        client = self.authenticated(self.superuser)
        response = client.patch(f'/api/admin/snowland/resorts/{self.resort_a.id}/', {
            'display_name': '共用雪場更新',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['data']['can_manage'])
        self.resort_a.refresh_from_db()
        self.assertEqual(self.resort_a.display_name, '共用雪場更新')

    def test_explicit_general_manager_permissions_limit_campus_scope(self):
        general = User.objects.create_user('general-manager', 'general@example.test', 'test-password')
        profile = general.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = ''
        profile.admin_permissions = ['orders']
        profile.save()
        profile.campuses.add(self.campus_a)
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='A 訂單')
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_b, name='B 訂單')

        client = self.authenticated(general)
        scope = client.get('/api/admin/snowland/me/')
        self.assertEqual(scope.status_code, 200)
        self.assertFalse(scope.data['data']['can_view_all_campuses'])
        self.assertEqual([item['id'] for item in scope.data['data']['campuses']], [self.campus_a.id])
        orders = client.get('/api/admin/snowland/orders/')
        self.assertEqual(orders.status_code, 200)
        self.assertEqual([item['name'] for item in orders.data['data']['list']], ['A 訂單'])
        self.assertEqual(client.get('/api/admin/snowland/orders/', HTTP_X_CAMPUS_ID=str(self.campus_b.id)).status_code, 403)

    def test_new_general_manager_cannot_save_without_campus(self):
        general = User.objects.create_user('new-general', 'new-general@example.test', 'test-password')
        response = self.authenticated(self.superuser).post(
            f'/api/admin/snowland/customers/{general.id}/permission/',
            {'is_manager': True, 'role': '', 'permissions': ['orders'], 'campus_ids': []},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(general.userprofile.is_manager)

    def test_non_superuser_headquarters_can_grant_and_revoke_scoped_staff_without_protected_flag(self):
        hq = User.objects.create_user('ordinary-hq-staff', 'hq-staff@example.test', 'test-password')
        profile = hq.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'hq_admin'
        profile.admin_permissions = ['staff']
        profile.save()
        target = User.objects.create_user('new-scoped-staff', 'scoped-staff@example.test', 'test-password')
        url = f'/api/admin/snowland/customers/{target.pk}/permission/'
        payload = {'is_manager': True, 'is_coach': False, 'role': 'campus_manager',
            'permissions': ['orders'], 'campus_ids': [self.campus_a.pk]}
        client = self.authenticated(hq)
        campuses = client.get('/api/admin/snowland/campuses/')
        self.assertEqual(campuses.status_code, 200, campuses.data)
        self.assertEqual(client.patch(f'/api/admin/snowland/campuses/{self.campus_a.pk}/',
            {'name': '不應被員工管理權限修改'}, format='json').status_code, 403)
        result = client.post(url, payload, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        target.refresh_from_db()
        self.assertFalse(target.is_superuser)
        scope = self.authenticated(target).get('/api/admin/snowland/me/')
        self.assertEqual(scope.status_code, 200, scope.data)
        self.assertEqual([row['id'] for row in scope.data['data']['campuses']], [self.campus_a.pk])
        self.assertEqual(client.post(url, {**payload, 'is_superuser': True}, format='json').status_code, 403)
        target.refresh_from_db()
        self.assertFalse(target.is_superuser)
        revoked = client.post(url, {'is_manager': False, 'is_coach': False, 'role': '',
            'permissions': [], 'campus_ids': []}, format='json')
        self.assertEqual(revoked.status_code, 200, revoked.data)
        self.assertEqual(self.authenticated(target).get('/api/admin/snowland/me/').status_code, 403)

    def test_existing_campus_manager_without_campus_cannot_view_customers_or_orders(self):
        self.profile.admin_permissions = ['customers', 'orders']
        self.profile.save(update_fields=['admin_permissions'])
        self.profile.campuses.clear()
        client = self.authenticated(self.manager)

        self.assertEqual(client.get('/api/admin/snowland/customers/').status_code, 403)
        self.assertEqual(client.get('/api/admin/snowland/orders/').status_code, 403)

    def test_inactive_campus_cannot_be_assigned_to_new_manager(self):
        self.campus_b.is_active = False
        self.campus_b.save(update_fields=['is_active'])
        general = User.objects.create_user('inactive-general', 'inactive@example.test', 'test-password')
        response = self.authenticated(self.superuser).post(
            f'/api/admin/snowland/customers/{general.id}/permission/',
            {'is_manager': True, 'role': 'campus_manager', 'permissions': ['orders'],
             'campus_ids': [self.campus_b.id]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(general.userprofile.is_manager)

    def test_company_role_can_use_all_campuses_but_only_allowed_modules(self):
        marketing = User.objects.create_user('marketing-manager', 'marketing@example.test', 'test-password')
        response = self.authenticated(self.superuser).post(
            f'/api/admin/snowland/customers/{marketing.id}/permission/',
            {'is_manager': True, 'role': 'marketing', 'permissions': ['analytics'], 'campus_ids': []},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        marketing.refresh_from_db()
        client = self.authenticated(marketing)
        scope = client.get('/api/admin/snowland/me/')
        self.assertTrue(scope.data['data']['can_view_all_campuses'])
        self.assertCountEqual(
            [item['id'] for item in scope.data['data']['campuses']],
            [self.campus_a.id, self.campus_b.id],
        )
        self.assertEqual(client.get('/api/admin/snowland/orders/').status_code, 403)
        self.assertEqual(client.get('/api/admin/snowland/dashboard/').status_code, 200)

    def test_invalid_permission_update_does_not_grant_superuser(self):
        general = User.objects.create_user('invalid-general', 'invalid@example.test', 'test-password')
        response = self.authenticated(self.superuser).post(
            f'/api/admin/snowland/customers/{general.id}/permission/',
            {'is_superuser': True, 'is_manager': True, 'role': 'invalid-role',
             'permissions': ['orders'], 'campus_ids': []},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        general.refresh_from_db()
        self.assertFalse(general.is_superuser)

    def test_malformed_campus_ids_return_400_without_changing_permissions(self):
        general = User.objects.create_user('malformed-campus', 'malformed@example.test', 'test-password')
        url = f'/api/admin/snowland/customers/{general.id}/permission/'
        for campus_ids in ([{'id': self.campus_a.id}], ['not-a-campus'], ['²'], [True]):
            with self.subTest(campus_ids=campus_ids):
                response = self.authenticated(self.superuser).post(
                    url,
                    {'is_superuser': True, 'is_manager': True, 'role': 'campus_manager',
                     'permissions': ['orders'], 'campus_ids': campus_ids},
                    format='json',
                )
                self.assertEqual(response.status_code, 400)
                general.refresh_from_db()
                general.userprofile.refresh_from_db()
                self.assertFalse(general.is_superuser)
                self.assertFalse(general.userprofile.is_manager)

    def test_legacy_general_manager_keeps_company_scope(self):
        legacy = User.objects.create_user('legacy-manager', 'legacy@example.test', 'test-password')
        profile = legacy.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = ''
        profile.admin_permissions = None
        profile.save()
        response = self.authenticated(legacy).get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['data']['can_view_all_campuses'])
        self.assertCountEqual(
            [item['id'] for item in response.data['data']['campuses']],
            [self.campus_a.id, self.campus_b.id],
        )

    def test_schedule_limits_manager_to_ten_days_and_own_campus(self):
        today = timezone.localdate()
        for campus, resort, offset in (
            (self.campus_a, self.resort_a, 1),
            (self.campus_a, self.resort_a, 11),
            (self.campus_b, self.resort_b, 1),
        ):
            coach = Coach.objects.create(client=self.tenant, name=f'{campus.code}-{offset}')
            coach.campuses.add(campus)
            slot = EquipmentAssistanceTimeSlot.objects.create(
                resort=resort, label=f'協助-{campus.code}-{offset}',
                start_time=time(8), end_time=time(8, 30),
            )
            group = ReservationGroup.objects.create(client=self.tenant, campus=campus, name=f'{campus.code}-{offset}')
            Payment.objects.create(reservation_group=group, status='paid')
            reservation = Reservation.objects.create(
                group=group, resort=resort, preferred_coach=coach,
                status='manually_assigned', equipment='purchaseAssistanceTime',
                equipment_assistance_time_slot=slot,
            )
            Booking.objects.create(
                reservation=reservation, date=today + timedelta(days=offset),
                start_time=time(9), end_time=time(11),
                course_type='單板', course_name='測試課程', is_scheduled=True,
            )

        self.profile.admin_permissions = ['scheduling']
        self.profile.save(update_fields=['admin_permissions'])
        url = '/api/admin/snowland/bookings/'
        manager = self.authenticated(self.manager)
        response = manager.get(url, {'start': today.isoformat(), 'end': (today + timedelta(days=30)).isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 2)
        self.assertEqual({item['date'] for item in response.data['data']['list']},
                         {(today + timedelta(days=1)).isoformat()})
        self.assertEqual(len(response.data['data']['daily_summary']), 11)
        self.assertEqual(response.data['data']['daily_summary'][0]['total_coaches'], 2)

        beyond = manager.get(url, {'start': (today + timedelta(days=11)).isoformat(),
                                   'end': (today + timedelta(days=20)).isoformat()})
        self.assertEqual(beyond.status_code, 200)
        self.assertEqual(beyond.data['data']['list'], [])

        principal = User.objects.create_user('principal')
        principal_profile = principal.userprofile
        principal_profile.is_manager = True
        principal_profile.manager_client = self.tenant
        principal_profile.role = 'campus_principal'
        principal_profile.admin_permissions = ['scheduling']
        principal_profile.save()
        principal_profile.campuses.add(self.campus_a)
        principal_response = self.authenticated(principal).get(
            url, {'start': today.isoformat(), 'end': (today + timedelta(days=30)).isoformat()})
        self.assertEqual(principal_response.status_code, 200)
        self.assertEqual(principal_response.data['data']['total'], 4)

    def test_headquarters_schedule_keeps_inactive_campus_history_scoped(self):
        day = timezone.localdate() + timedelta(days=1)
        bookings = {}
        assistance_ids = {}
        for campus, resort in ((self.campus_a, self.resort_a), (self.campus_b, self.resort_b)):
            coach = Coach.objects.create(client=self.tenant, name=f'{campus.code} 教練')
            coach.campuses.add(campus)
            slot = EquipmentAssistanceTimeSlot.objects.create(
                resort=resort, label=f'{campus.code} 裝備協助',
                start_time=time(8), end_time=time(8, 30),
            )
            group = ReservationGroup.objects.create(client=self.tenant, campus=campus)
            Payment.objects.create(reservation_group=group, status='paid')
            reservation = Reservation.objects.create(
                group=group, resort=resort, preferred_coach=coach,
                status='manually_assigned', equipment='purchaseAssistanceTime',
                equipment_assistance_time_slot=slot,
            )
            booking = Booking.objects.create(
                reservation=reservation, date=day, start_time=time(9), end_time=time(11),
                course_type='單板', course_name='歷史課程', is_scheduled=True,
            )
            bookings[campus.id] = booking.id
            assistance_ids[campus.id] = -(booking.id * 100000 + slot.id)

        self.campus_b.is_active = False
        self.campus_b.save(update_fields=['is_active'])
        self.profile.admin_permissions = ['scheduling']
        self.profile.save(update_fields=['admin_permissions'])
        url = '/api/admin/snowland/bookings/'
        params = {'start': day.isoformat(), 'end': day.isoformat()}
        headquarters = self.authenticated(self.superuser)
        all_rows = headquarters.get(url, params, HTTP_X_CAMPUS_ID='all')
        self.assertEqual(all_rows.status_code, 200, all_rows.data)
        self.assertEqual(
            {row['id'] for row in all_rows.data['data']['list']},
            set(bookings.values()) | set(assistance_ids.values()),
        )
        inactive_rows = [
            row for row in all_rows.data['data']['list']
            if row['id'] in (bookings[self.campus_b.id], assistance_ids[self.campus_b.id])
        ]
        self.assertEqual(len(inactive_rows), 2)
        self.assertTrue(all(row['campus_name'] == self.campus_b.name for row in inactive_rows))
        self.assertTrue(all(row['campus_is_active'] is False for row in inactive_rows))
        self.assertEqual(all_rows.data['data']['daily_summary'][0]['total_coaches'], 1)

        for response in (
            headquarters.get(url, params, HTTP_X_CAMPUS_ID=str(self.campus_a.id)),
            self.authenticated(self.manager).get(url, params),
        ):
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(
                {row['id'] for row in response.data['data']['list']},
                {bookings[self.campus_a.id], assistance_ids[self.campus_a.id]},
            )

    def test_notification_templates_cannot_cross_campus_or_change_company_default(self):
        self.profile.admin_permissions = ['notifications']
        self.profile.save(update_fields=['admin_permissions'])
        url = '/api/admin/snowland/notification-templates/'
        own = NotificationTemplate.objects.create(client=self.tenant, campus=self.campus_a, name='A 提醒', event='pre_course', channel='email', body='A')
        other = NotificationTemplate.objects.create(client=self.tenant, campus=self.campus_b, name='B 提醒', event='pre_course', channel='email', body='B')
        global_template = NotificationTemplate.objects.create(client=self.tenant, name='總部提醒', event='pre_course', channel='email', body='全部')
        client = self.authenticated(self.manager)

        listed = client.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual({row['id'] for row in listed.data['data']['list']}, {own.id, global_template.id})
        payload = {'name': '新增提醒', 'event': 'pre_course', 'channel': 'email', 'body': '內容'}
        self.assertEqual(client.post(url, {**payload, 'campus': self.campus_a.id}, format='json').status_code, 201)
        self.assertEqual(client.post(url, {**payload, 'campus': self.campus_b.id}, format='json').status_code, 403)
        self.assertEqual(client.post(url, {**payload, 'campus': None}, format='json').status_code, 403)
        self.assertEqual(client.patch(f'{url}{own.id}/', {'campus': self.campus_b.id}, format='json').status_code, 403)
        self.assertEqual(client.patch(f'{url}{global_template.id}/', {'name': '越權'}, format='json').status_code, 404)
        self.assertEqual(client.delete(f'{url}{global_template.id}/').status_code, 404)
        self.assertEqual(client.get(f'{url}{other.id}/').status_code, 404)

        headquarters = self.authenticated(self.superuser)
        scoped = headquarters.get(url, HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual({row['campus'] for row in scoped.data['data']['list']}, {self.campus_a.id, None})
        self.assertNotIn(other.id, {row['id'] for row in scoped.data['data']['list']})
        self.assertEqual(headquarters.post(url, {**payload, 'campus': self.campus_b.id}, format='json', HTTP_X_CAMPUS_ID=str(self.campus_a.id)).status_code, 403)

    def test_cannot_attach_other_tenant_resort(self):
        client = self.authenticated(self.superuser)
        response = client.post('/api/admin/snowland/campuses/', {
            'name': '錯誤校區', 'code': 'invalid', 'resort_ids': [self.other_resort.id],
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_campus_manager_cannot_create_payment_account_for_other_campus(self):
        self.profile.admin_permissions = ['payment_settings']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/payment-accounts/'

        for data in (
            {'name': '其他校區帳戶', 'campus_ids': [self.campus_b.id]},
            {'name': '其他雪場帳戶', 'campus_ids': [self.campus_a.id], 'resort_ids': [self.resort_b.id]},
            {'name': '全公司帳戶'},
        ):
            response = client.post(url, {**BANK_FIELDS, **data}, format='json')
            self.assertEqual(response.status_code, 400)

        self.assertFalse(PaymentAccount.objects.filter(client=self.tenant).exists())

    def test_campus_manager_can_create_payment_account_for_own_campus(self):
        self.profile.admin_permissions = ['payment_settings']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        response = client.post('/api/admin/snowland/payment-accounts/', {
            **BANK_FIELDS,
            'name': 'A 校區帳戶',
            'campus_ids': [self.campus_a.id],
            'resort_ids': [self.resort_a.id],
        }, format='json')
        self.assertEqual(response.status_code, 201)
        account = PaymentAccount.objects.get(client=self.tenant)
        self.assertEqual(list(account.campuses.values_list('id', flat=True)), [self.campus_a.id])
        self.assertEqual(list(account.resorts.values_list('id', flat=True)), [self.resort_a.id])

    def test_payment_account_requires_bank_details_before_activation(self):
        client = self.authenticated(self.superuser)
        url = '/api/admin/snowland/payment-accounts/'

        incomplete = client.post(url, {'name': '未完成帳戶', 'bank_name': '測試銀行'}, format='json')
        self.assertEqual(incomplete.status_code, 400)
        self.assertIn('bank_branch', str(incomplete.data))
        self.assertFalse(PaymentAccount.objects.filter(client=self.tenant).exists())

        draft = client.post(url, {'name': '未完成帳戶', 'bank_name': '測試銀行', 'is_active': False}, format='json')
        self.assertEqual(draft.status_code, 201)
        account = PaymentAccount.objects.get(client=self.tenant)
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a)
        self.assertIsNone(resolve_payment_account(group))
        activation_url = f'{url}{account.id}/'

        incomplete_activation = client.patch(activation_url, {'is_active': True}, format='json')
        self.assertEqual(incomplete_activation.status_code, 400)
        account.refresh_from_db()
        self.assertFalse(account.is_active)

        activation = client.patch(activation_url, {**BANK_FIELDS, 'is_active': True}, format='json')
        self.assertEqual(activation.status_code, 200)
        account.refresh_from_db()
        self.assertTrue(account.is_active)
        self.assertEqual(resolve_payment_account(group), account)

        deactivation = client.patch(activation_url, {'is_active': False}, format='json')
        self.assertEqual(deactivation.status_code, 200)
        self.assertIsNone(resolve_payment_account(group))

    def test_campus_manager_can_update_own_payment_account(self):
        self.profile.admin_permissions = ['payment_settings']
        self.profile.save(update_fields=['admin_permissions'])
        account = PaymentAccount.objects.create(client=self.tenant, name='原帳戶', **BANK_FIELDS)
        account.campuses.add(self.campus_a)
        client = self.authenticated(self.manager)

        response = client.patch(f'/api/admin/snowland/payment-accounts/{account.id}/', {
            'name': '更新後帳戶', 'account_number': '222',
            'campus_ids': [self.campus_a.id], 'resort_ids': [self.resort_a.id],
        }, format='json')

        self.assertEqual(response.status_code, 200)
        account.refresh_from_db()
        self.assertEqual((account.name, account.account_number), ('更新後帳戶', '222'))
        self.assertEqual(list(account.campuses.values_list('id', flat=True)), [self.campus_a.id])
        self.assertEqual(list(account.resorts.values_list('id', flat=True)), [self.resort_a.id])

    def test_headquarters_can_update_company_payment_account_without_campus(self):
        account = PaymentAccount.objects.create(client=self.tenant, name='全公司帳戶', **BANK_FIELDS)
        client = self.authenticated(self.superuser)

        response = client.patch(f'/api/admin/snowland/payment-accounts/{account.id}/', {
            'account_number': '222', 'campus_ids': [], 'resort_ids': [],
        }, format='json')

        self.assertEqual(response.status_code, 200)
        account.refresh_from_db()
        self.assertEqual(account.account_number, '222')
        self.assertFalse(account.campuses.exists())
        self.assertFalse(account.resorts.exists())

    def test_payment_account_resort_must_belong_to_selected_campus(self):
        client = self.authenticated(self.superuser)
        response = client.post('/api/admin/snowland/payment-accounts/', {
            **BANK_FIELDS,
            'name': '錯配帳戶',
            'campus_ids': [self.campus_a.id],
            'resort_ids': [self.resort_b.id],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PaymentAccount.objects.filter(client=self.tenant).exists())

        valid = client.post('/api/admin/snowland/payment-accounts/', {
            **BANK_FIELDS,
            'name': '跨校區共用帳戶',
            'campus_ids': [self.campus_a.id, self.campus_b.id],
            'resort_ids': [self.resort_b.id],
        }, format='json')
        self.assertEqual(valid.status_code, 201)

    def test_campus_manager_pricing_is_limited_to_own_unshared_resort(self):
        category = CourseCategory.objects.create(client=self.tenant, name='滑雪')
        course_type = CourseType.objects.create(category=category, name='私人課')
        template_a = CourseTemplate.objects.create(course_type=course_type, name='A 課程', duration_hours=2)
        template_b = CourseTemplate.objects.create(course_type=course_type, name='B 課程', duration_hours=2)
        template_a.resorts.add(self.resort_a)
        template_b.resorts.add(self.resort_b)
        pricing_a = CoursePricing.objects.create(
            resort=self.resort_a, base_price_off_peak=1000, peak_season_surcharge=0,
            additional_person_fee=0, max_capacity=6,
        )
        pricing_b = CoursePricing.objects.create(
            resort=self.resort_b, base_price_off_peak=2000, peak_season_surcharge=0,
            additional_person_fee=0, max_capacity=6,
        )
        pricing_a.templates.add(template_a)
        pricing_b.templates.add(template_b)
        self.profile.admin_permissions = ['pricing']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/course-pricing/'

        listed = client.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item['id'] for item in listed.data['data']['list']], [pricing_a.id])
        self.assertEqual(client.patch(f'{url}{pricing_a.id}/', {'base_price_off_peak': 1100}, format='json').status_code, 200)
        pricing_a.refresh_from_db()
        self.assertEqual(pricing_a.base_price_off_peak, 1100)
        own_create = client.post(url, {
            'templates': [template_a.id], 'resort': self.resort_a.id,
            'base_price_off_peak': 1500, 'peak_season_surcharge': 0,
            'additional_person_fee': 0, 'max_capacity': 6,
        }, format='json')
        self.assertEqual(own_create.status_code, 201, own_create.data)
        self.assertEqual(client.get(f'{url}{pricing_b.id}/').status_code, 404)
        self.assertEqual(client.patch(f'{url}{pricing_b.id}/', {'base_price_off_peak': 5}, format='json').status_code, 404)
        self.assertEqual(client.delete(f'{url}{pricing_b.id}/').status_code, 404)
        self.assertEqual(client.post(url, {
            'templates': [template_b.id], 'resort': self.resort_b.id,
            'base_price_off_peak': 3000, 'peak_season_surcharge': 0,
            'additional_person_fee': 0, 'max_capacity': 6,
        }, format='json').status_code, 400)
        pricing_b.refresh_from_db()
        self.assertEqual(pricing_b.base_price_off_peak, 2000)

        self.campus_b.resorts.add(self.resort_a)
        self.assertEqual(client.get(url).data['data']['list'], [])
        self.assertEqual(client.patch(f'{url}{pricing_a.id}/', {'base_price_off_peak': 5}, format='json').status_code, 404)
        self.assertEqual(self.authenticated(self.superuser).get(url).data['data']['total'], 3)

    def test_campus_manager_course_templates_stay_in_own_exclusive_resorts(self):
        category = CourseCategory.objects.create(client=self.tenant, name='滑雪')
        course_type = CourseType.objects.create(category=category, name='私人課')
        own = CourseTemplate.objects.create(course_type=course_type, name='A 課程', duration_hours=2)
        other = CourseTemplate.objects.create(course_type=course_type, name='B 課程', duration_hours=2)
        own.resorts.add(self.resort_a)
        other.resorts.add(self.resort_b)
        self.profile.admin_permissions = ['course_types']
        self.profile.save(update_fields=['admin_permissions'])
        manager = self.authenticated(self.manager)
        url = '/api/admin/snowland/course-templates/'
        options_url = f'{url}editor-options/'
        editor_options = manager.get(options_url)
        self.assertEqual(editor_options.status_code, 200, editor_options.data)
        self.assertEqual([item['id'] for item in editor_options.data['data']['resorts']], [self.resort_a.id])
        self.assertTrue(editor_options.data['data']['resorts'][0]['can_select'])

        listed = manager.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item['id'] for item in listed.data['data']['list']], [own.id])
        self.assertTrue(listed.data['data']['list'][0]['can_manage'])
        self.assertEqual(manager.get(f'{url}{other.id}/').status_code, 404)
        self.assertEqual(manager.patch(f'{url}{other.id}/', {'name': '偷改'}, format='json').status_code, 404)
        self.assertEqual(manager.delete(f'{url}{other.id}/').status_code, 404)
        self.assertEqual(manager.post(url, {
            'course_type': course_type.id, 'name': 'B 新課程', 'duration_hours': 2,
            'resorts': [self.resort_b.id],
        }, format='json').status_code, 400)
        created = manager.post(url, {
            'course_type': course_type.id, 'name': 'A 新課程', 'duration_hours': 2,
            'resorts': [self.resort_a.id],
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        disposable = CourseTemplate.objects.create(
            course_type=course_type, name='A 待刪模板', duration_hours=2,
        )
        disposable.resorts.add(self.resort_a)
        disposable_session = CourseSession.objects.create(
            template=disposable, start_time=time(8), end_time=time(10),
        )
        self.assertEqual(manager.delete(f'{url}{disposable.id}/').status_code, 204)
        self.assertFalse(CourseTemplate.objects.filter(pk=disposable.id).exists())
        self.assertFalse(CourseSession.objects.filter(pk=disposable_session.id).exists())
        self.assertEqual(manager.patch(f'{url}{own.id}/', {
            'resorts': [self.resort_b.id],
        }, format='json').status_code, 400)
        other_coach = Coach.objects.create(client=self.tenant, name='B 教練')
        other_coach.campuses.add(self.campus_b)
        own_coach = Coach.objects.create(client=self.tenant, name='A 教練')
        own_coach.campuses.add(self.campus_a)
        self.assertEqual([item['id'] for item in manager.get(options_url).data['data']['coaches']], [own_coach.id])
        self.assertEqual(manager.patch(f'{url}{own.id}/', {
            'allowed_coaches': [other_coach.id],
        }, format='json').status_code, 400)
        self.assertEqual(manager.patch(f'{url}{own.id}/', {'name': 'A 更新'}, format='json').status_code, 200)
        own_session = CourseSession.objects.create(template=own, start_time=time(9), end_time=time(11))
        other_session = CourseSession.objects.create(template=other, start_time=time(13), end_time=time(15))
        session_url = '/api/admin/snowland/course-sessions/'
        self.assertEqual([item['id'] for item in manager.get(session_url).data['data']['list']], [own_session.id])
        self.assertEqual(manager.patch(f'{session_url}{other_session.id}/', {
            'start_time': '14:00',
        }, format='json').status_code, 404)
        self.assertEqual(manager.post(session_url, {
            'template': other.id, 'start_time': '09:00', 'end_time': '11:00',
        }, format='json').status_code, 403)
        self.assertEqual(manager.patch(f'{session_url}{own_session.id}/', {
            'template': other.id,
        }, format='json').status_code, 403)
        self.assertEqual(manager.patch(f'{session_url}{own_session.id}/', {
            'start_time': '10:00',
        }, format='json').status_code, 200)
        own.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(own.name, 'A 更新')
        self.assertEqual(other.name, 'B 課程')

        headquarters = self.authenticated(self.superuser)
        selected = headquarters.patch(f'{url}{other.id}/', {'name': '不應跨範圍'},
                                      format='json', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(selected.status_code, 404)
        selected_session = headquarters.patch(f'{session_url}{other_session.id}/', {
            'start_time': '14:00',
        }, format='json', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(selected_session.status_code, 404)
        self.assertEqual(headquarters.patch(f'{url}{other.id}/', {
            'name': '總部更新',
        }, format='json').status_code, 200)

        self.campus_b.resorts.add(self.resort_a)
        shared_options = manager.get(options_url).data['data']
        self.assertFalse(shared_options['resorts'][0]['can_select'])
        shared_list = manager.get(url).data['data']['list']
        self.assertEqual([item['id'] for item in shared_list], [own.id, created.data['id']])
        self.assertTrue(all(not item['can_manage'] for item in shared_list))
        self.assertEqual(manager.patch(f'{url}{own.id}/', {'name': '共享雪場偷改'}, format='json').status_code, 403)
        self.assertEqual(manager.patch(f'{session_url}{own_session.id}/', {
            'start_time': '11:00',
        }, format='json').status_code, 403)
        shared_hq = headquarters.get(url, HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertIn(own.id, [item['id'] for item in shared_hq.data['data']['list']])
        self.assertFalse(next(item for item in shared_hq.data['data']['list'] if item['id'] == own.id)['can_manage'])
        selected_options = headquarters.get(options_url, HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(selected_options.status_code, 200, selected_options.data)
        self.assertFalse(next(item for item in selected_options.data['data']['resorts']
                              if item['id'] == self.resort_a.id)['can_select'])
        self.assertTrue(next(item for item in headquarters.get(options_url).data['data']['resorts']
                             if item['id'] == self.resort_a.id)['can_select'])
        self.assertEqual(self.authenticated(self.superuser).get(url).data['data']['total'], 3)

    def test_course_session_rejects_invalid_time_range_without_changing_existing_session(self):
        category = CourseCategory.objects.create(client=self.tenant, name='滑雪')
        course_type = CourseType.objects.create(category=category, name='私人課')
        template = CourseTemplate.objects.create(course_type=course_type, name='全天課', duration_hours=2)
        template.resorts.add(self.resort_a)
        client = self.authenticated(self.superuser)
        url = '/api/admin/snowland/course-sessions/'

        for start_time, end_time in (('12:00', '12:00'), ('13:00', '12:00')):
            response = client.post(url, {
                'template': template.id, 'start_time': start_time, 'end_time': end_time,
            }, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(CourseSession.objects.filter(template=template).exists())

        created = client.post(url, {
            'template': template.id, 'start_time': '09:00', 'end_time': '11:00',
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        session_id = created.data['id']
        invalid_update = client.patch(f'{url}{session_id}/', {'start_time': '12:00'}, format='json')
        self.assertEqual(invalid_update.status_code, 400, invalid_update.data)
        session = CourseSession.objects.get(pk=session_id)
        self.assertEqual((session.start_time, session.end_time), (time(9), time(11)))

    def test_inactive_legacy_campus_does_not_turn_resort_into_shared_management(self):
        legacy = Campus.objects.create(
            client=self.tenant, code='legacy', name='已停用舊校區', is_active=False,
        )
        legacy.resorts.add(self.resort_a)
        category = CourseCategory.objects.create(client=self.tenant, name='滑雪')
        course_type = CourseType.objects.create(category=category, name='私人課')
        template = CourseTemplate.objects.create(course_type=course_type, name='A 課程', duration_hours=2)
        template.resorts.add(self.resort_a)
        pricing = CoursePricing.objects.create(
            resort=self.resort_a, base_price_off_peak=2000,
            peak_season_surcharge=0, additional_person_fee=0, max_capacity=6,
        )
        pricing.templates.add(template)
        self.profile.admin_permissions = ['resorts', 'course_types', 'pricing']
        self.profile.save(update_fields=['admin_permissions'])
        manager = self.authenticated(self.manager)

        resorts = manager.get('/api/admin/snowland/resorts/')
        self.assertEqual(resorts.status_code, 200, resorts.data)
        self.assertTrue(next(item for item in resorts.data['data']['list']
                             if item['id'] == self.resort_a.id)['can_manage'])
        options = manager.get('/api/admin/snowland/course-templates/editor-options/')
        self.assertEqual(options.status_code, 200, options.data)
        self.assertTrue(next(item for item in options.data['data']['resorts']
                             if item['id'] == self.resort_a.id)['can_select'])
        templates = manager.get('/api/admin/snowland/course-templates/')
        self.assertEqual(templates.status_code, 200, templates.data)
        self.assertTrue(next(item for item in templates.data['data']['list']
                             if item['id'] == template.id)['can_manage'])
        self.assertEqual(manager.patch(
            f'/api/admin/snowland/course-templates/{template.id}/',
            {'name': 'A 更新'}, format='json',
        ).status_code, 200)
        prices = manager.get('/api/admin/snowland/course-pricing/')
        self.assertIn(pricing.id, [item['id'] for item in prices.data['data']['list']])
        self.assertEqual(manager.patch(
            f'/api/admin/snowland/course-pricing/{pricing.id}/',
            {'base_price_off_peak': 2200}, format='json',
        ).status_code, 200)
        self.assertCountEqual(self.resort_a.campuses.values_list('id', flat=True),
                              [self.campus_a.id, legacy.id])

    def test_course_structure_used_by_an_order_cannot_be_deleted(self):
        category = CourseCategory.objects.create(client=self.tenant, name='已售課程')
        course_type = CourseType.objects.create(category=category, name='已售類型')
        template = CourseTemplate.objects.create(
            course_type=course_type, name='已售模板', duration_hours=3,
        )
        template.resorts.add(self.resort_a)
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a)
        reservation = Reservation.objects.create(
            group=group, resort=self.resort_a, course_type=course_type,
            course_template=template, course_fee=3000,
        )
        headquarters = self.authenticated(self.superuser)

        for resource, instance in (
            ('course-templates', template),
            ('course-types', course_type),
            ('course-categories', category),
        ):
            response = headquarters.delete(f'/api/admin/snowland/{resource}/{instance.id}/')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('不能刪除', response.data['msg'])
            self.assertTrue(type(instance).objects.filter(pk=instance.pk).exists())
            reservation.refresh_from_db()
            self.assertEqual(reservation.course_template_id, template.id)
            self.assertEqual(reservation.course_type_id, course_type.id)

    def test_course_structure_used_by_a_shared_class_cannot_be_deleted(self):
        category = CourseCategory.objects.create(client=self.tenant, name='合班課程')
        course_type = CourseType.objects.create(category=category, name='合班類型')
        template = CourseTemplate.objects.create(
            course_type=course_type, name='合班模板', duration_hours=3,
        )
        template.resorts.add(self.resort_a)
        shared_class = SharedCourseClass.objects.create(
            client=self.tenant, campus=self.campus_a, resort=self.resort_a,
            template=template, date=timezone.localdate() + timedelta(days=1),
            start_time=time(9), end_time=time(12), ability_level='level1',
        )
        headquarters = self.authenticated(self.superuser)

        for resource, instance in (
            ('course-templates', template),
            ('course-types', course_type),
            ('course-categories', category),
        ):
            response = headquarters.delete(f'/api/admin/snowland/{resource}/{instance.id}/')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('不能刪除', response.data['msg'])
            self.assertTrue(type(instance).objects.filter(pk=instance.pk).exists())
            self.assertEqual(SharedCourseClass.objects.get(pk=shared_class.id).template_id, template.id)

    def test_unused_course_structure_can_still_be_deleted(self):
        category = CourseCategory.objects.create(client=self.tenant, name='未使用課程')
        course_type = CourseType.objects.create(category=category, name='未使用類型')
        template = CourseTemplate.objects.create(
            course_type=course_type, name='未使用模板', duration_hours=3,
        )
        template.resorts.add(self.resort_a)
        headquarters = self.authenticated(self.superuser)

        self.assertEqual(headquarters.delete(
            f'/api/admin/snowland/course-types/{course_type.id}/',
        ).status_code, 204)
        self.assertFalse(CourseTemplate.objects.filter(pk=template.id).exists())
        self.assertEqual(headquarters.delete(
            f'/api/admin/snowland/course-categories/{category.id}/',
        ).status_code, 204)

    def test_course_structure_shares_names_but_hides_other_campus_templates(self):
        category = CourseCategory.objects.create(client=self.tenant, name='共用大類')
        course_type = CourseType.objects.create(category=category, name='共用類型')
        category.available_resorts.add(self.resort_a, self.resort_b)
        course_type.available_resorts.add(self.resort_a, self.resort_b)
        own = CourseTemplate.objects.create(course_type=course_type, name='A 專用模板', duration_hours=2)
        other = CourseTemplate.objects.create(course_type=course_type, name='B 專用模板', duration_hours=2)
        own.resorts.add(self.resort_a)
        other.resorts.add(self.resort_b)
        self.profile.admin_permissions = ['course_types']
        self.profile.save(update_fields=['admin_permissions'])
        manager = self.authenticated(self.manager)
        categories_url = '/api/admin/snowland/course-categories/'
        types_url = '/api/admin/snowland/course-types/'

        listed = manager.get(categories_url)
        self.assertEqual(listed.status_code, 200)
        row = listed.data['data']['list'][0]
        self.assertEqual(row['name'], '共用大類')
        self.assertEqual(row['available_resorts'], [self.resort_a.id])
        self.assertEqual(row['types'][0]['available_resorts'], [self.resort_a.id])
        self.assertEqual([item['id'] for item in row['types'][0]['templates']], [own.id])
        self.assertNotIn('B 專用模板', str(listed.data))
        type_detail = manager.get(f'{types_url}{course_type.id}/')
        self.assertEqual(type_detail.status_code, 200)
        self.assertEqual([item['id'] for item in type_detail.data['templates']], [own.id])

        self.assertEqual(manager.post(categories_url, {'name': '越權大類'}, format='json').status_code, 403)
        self.assertEqual(manager.patch(f'{categories_url}{category.id}/', {
            'name': '越權修改',
        }, format='json').status_code, 403)
        self.assertEqual(manager.delete(f'{categories_url}{category.id}/').status_code, 403)
        self.assertEqual(manager.post(types_url, {
            'category': category.id, 'name': '越權類型',
        }, format='json').status_code, 403)
        self.assertEqual(manager.patch(f'{types_url}{course_type.id}/', {
            'name': '越權修改',
        }, format='json').status_code, 403)
        self.assertEqual(manager.delete(f'{types_url}{course_type.id}/').status_code, 403)
        category.refresh_from_db()
        course_type.refresh_from_db()
        self.assertEqual((category.name, course_type.name), ('共用大類', '共用類型'))

        headquarters = self.authenticated(self.superuser)
        selected = headquarters.get(categories_url, HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual([item['id'] for item in selected.data['data']['list'][0]['types'][0]['templates']], [own.id])
        all_campuses = headquarters.get(categories_url)
        self.assertEqual([item['id'] for item in all_campuses.data['data']['list'][0]['types'][0]['templates']],
                         [own.id, other.id])

    def test_headquarters_course_structure_cannot_attach_another_company(self):
        category = CourseCategory.objects.create(client=self.tenant, name='本公司課程')
        other_category = CourseCategory.objects.create(client=self.other_tenant, name='其他公司課程')
        course_type = CourseType.objects.create(category=category, name='本公司類型')
        headquarters = self.authenticated(self.superuser)
        categories_url = '/api/admin/snowland/course-categories/'
        types_url = '/api/admin/snowland/course-types/'

        self.assertEqual(headquarters.post(categories_url, {
            'name': '跨公司雪場', 'available_resorts': [self.other_resort.id],
        }, format='json').status_code, 400)
        self.assertEqual(headquarters.patch(f'{categories_url}{category.id}/', {
            'available_resorts': [self.other_resort.id],
        }, format='json').status_code, 400)
        self.assertEqual(headquarters.post(types_url, {
            'category': other_category.id, 'name': '跨公司類型',
        }, format='json').status_code, 400)
        self.assertEqual(headquarters.post(types_url, {
            'category': category.id, 'name': '跨公司雪場類型',
            'available_resorts': [self.other_resort.id],
        }, format='json').status_code, 400)
        self.assertEqual(headquarters.patch(f'{types_url}{course_type.id}/', {
            'category': other_category.id,
        }, format='json').status_code, 400)
        self.assertEqual(headquarters.patch(f'{types_url}{course_type.id}/', {
            'available_resorts': [self.other_resort.id],
        }, format='json').status_code, 400)
        self.assertFalse(CourseCategory.objects.filter(client=self.tenant).exclude(pk=category.pk).exists())
        self.assertEqual(course_type.category_id, category.id)

    def test_headquarters_cannot_attach_another_tenants_pricing_relations(self):
        category = CourseCategory.objects.create(client=self.tenant, name='本公司課程')
        other_category = CourseCategory.objects.create(client=self.other_tenant, name='其他公司課程')
        template = CourseTemplate.objects.create(
            course_type=CourseType.objects.create(category=category, name='私人課'),
            name='本公司模板', duration_hours=2,
        )
        other_template = CourseTemplate.objects.create(
            course_type=CourseType.objects.create(category=other_category, name='私人課'),
            name='其他公司模板', duration_hours=2,
        )
        client = self.authenticated(self.superuser)
        url = '/api/admin/snowland/course-pricing/'
        payload = {
            'templates': [template.id], 'resort': self.resort_a.id,
            'base_price_off_peak': 1000, 'peak_season_surcharge': 0,
            'additional_person_fee': 0, 'max_capacity': 6,
        }

        self.assertEqual(client.post(url, {**payload, 'resort': self.other_resort.id}, format='json').status_code, 400)
        self.assertEqual(client.post(url, {**payload, 'templates': [other_template.id]}, format='json').status_code, 400)
        self.assertFalse(CoursePricing.objects.exists())

    def test_pricing_requires_template_to_be_available_at_selected_resort(self):
        category = CourseCategory.objects.create(client=self.tenant, name='課程')
        course_type = CourseType.objects.create(category=category, name='一般課程')
        template = CourseTemplate.objects.create(course_type=course_type, name='全天', duration_hours=6)
        template.resorts.add(self.resort_a)
        client = self.authenticated(self.superuser)
        url = '/api/admin/snowland/course-pricing/'
        payload = {
            'templates': [template.id], 'resort': self.resort_b.id,
            'base_price_off_peak': 1200, 'peak_season_surcharge': 0,
            'additional_person_fee': 0, 'max_capacity': 6,
        }

        rejected = client.post(url, payload, format='json')
        self.assertEqual(rejected.status_code, 400, rejected.data)
        self.assertEqual(client.post(url, {**payload, 'templates': []}, format='json').status_code, 400)
        self.assertFalse(CoursePricing.objects.exists())
        created = client.post(url, {**payload, 'resort': self.resort_a.id}, format='json')
        self.assertEqual(created.status_code, 201, created.data)

        legacy = CoursePricing.objects.create(
            resort=self.resort_b, base_price_off_peak=1000,
            peak_season_surcharge=0, additional_person_fee=0, max_capacity=6,
        )
        legacy.templates.add(template)
        self.assertEqual(client.patch(f'{url}{legacy.id}/', {
            'base_price_off_peak': 1100,
        }, format='json').status_code, 200)
        self.assertEqual(client.patch(f'{url}{created.data["data"]["id"]}/', {
            'resort': self.resort_b.id,
        }, format='json').status_code, 400)

    def test_pricing_only_manager_catalog_contains_own_exclusive_resort_templates(self):
        category_a = CourseCategory.objects.create(client=self.tenant, name='A 課程大類')
        category_b = CourseCategory.objects.create(client=self.tenant, name='B 課程大類')
        type_a = CourseType.objects.create(category=category_a, name='A 類型')
        type_b = CourseType.objects.create(category=category_b, name='B 類型')
        template_a = CourseTemplate.objects.create(course_type=type_a, name='A 模板', duration_hours=2)
        template_b = CourseTemplate.objects.create(course_type=type_b, name='B 模板', duration_hours=4)
        template_a.resorts.add(self.resort_a)
        template_b.resorts.add(self.resort_b)
        self.profile.admin_permissions = ['pricing']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/course-pricing/catalog/'

        self.assertEqual(client.get('/api/admin/snowland/course-categories/').status_code, 403)
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['resort_ids'], [self.resort_a.id])
        self.assertEqual(response.data['data']['resorts'], [{'id': self.resort_a.id, 'display_name': 'A 雪場'}])
        self.assertEqual([item['name'] for item in response.data['data']['list']], ['A 課程大類'])
        own_template = response.data['data']['list'][0]['types'][0]['templates'][0]
        self.assertEqual((own_template['id'], own_template['resorts']), (template_a.id, [self.resort_a.id]))
        self.assertNotIn('B 模板', str(response.data))
        self.assertEqual(client.post(url, {}, format='json').status_code, 405)

        hq_response = self.authenticated(self.superuser).get(url)
        self.assertEqual(hq_response.status_code, 200)
        self.assertCountEqual(hq_response.data['data']['resort_ids'], [self.resort_a.id, self.resort_b.id])
        self.assertCountEqual([item['name'] for item in hq_response.data['data']['list']], ['A 課程大類', 'B 課程大類'])

        self.campus_b.resorts.add(self.resort_a)
        shared_response = client.get(url)
        self.assertEqual(shared_response.data['data'], {'list': [], 'total': 0, 'resort_ids': [], 'resorts': []})

    def test_campus_manager_cannot_change_global_season_ranges(self):
        season = SeasonSetting.objects.create(
            name='測試雪季', season_type='peak', start_date='2026-12-01', end_date='2026-12-31',
        )
        self.profile.admin_permissions = ['pricing']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/seasons/'

        self.assertEqual(client.post(url, {
            'name': '越權雪季', 'season_type': 'peak',
            'start_date': '2027-01-01', 'end_date': '2027-01-31',
        }, format='json').status_code, 403)
        self.assertEqual(client.patch(f'{url}{season.id}/', {'name': '越權修改'}, format='json').status_code, 403)
        self.assertEqual(client.delete(f'{url}{season.id}/').status_code, 403)
        season.refresh_from_db()
        self.assertEqual(season.name, '測試雪季')
        self.assertEqual(self.authenticated(self.superuser).patch(
            f'{url}{season.id}/', {'name': '總部修改'}, format='json',
        ).status_code, 200)

    def test_campus_manager_cannot_modify_shared_payment_account(self):
        self.profile.admin_permissions = ['payment_settings']
        self.profile.save(update_fields=['admin_permissions'])
        account = PaymentAccount.objects.create(client=self.tenant, name='共用帳戶', **BANK_FIELDS)
        account.campuses.add(self.campus_a, self.campus_b)
        client = self.authenticated(self.manager)
        response = client.patch(f'/api/admin/snowland/payment-accounts/{account.id}/', {
            'name': '擅自修改',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        account.refresh_from_db()
        self.assertEqual(account.name, '共用帳戶')

        deleted = client.delete(f'/api/admin/snowland/payment-accounts/{account.id}/')
        self.assertEqual(deleted.status_code, 403)
        self.assertTrue(PaymentAccount.objects.filter(pk=account.id).exists())

    def test_campus_manager_cannot_modify_company_operating_policy(self):
        client = self.authenticated(self.manager)
        policy = OperatingPolicy.objects.get(client=self.tenant, campus__isnull=True)
        response = client.patch(f'/api/admin/snowland/operating-policies/{policy.id}/', {
            'unpaid_hold_days': 9,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        policy.refresh_from_db()
        self.assertEqual(policy.unpaid_hold_days, 3)

        deleted = client.delete(f'/api/admin/snowland/operating-policies/{policy.id}/')
        self.assertEqual(deleted.status_code, 403)
        self.assertTrue(OperatingPolicy.objects.filter(pk=policy.id).exists())

    def test_campus_manager_can_modify_own_operating_policy(self):
        policy = OperatingPolicy.objects.create(client=self.tenant, campus=self.campus_a)
        client = self.authenticated(self.manager)
        response = client.patch(f'/api/admin/snowland/operating-policies/{policy.id}/', {
            'unpaid_hold_days': 5,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        policy.refresh_from_db()
        self.assertEqual(policy.unpaid_hold_days, 5)

    def test_campus_manager_can_restore_company_policy_for_own_campus(self):
        company_policy = OperatingPolicy.objects.get(client=self.tenant, campus__isnull=True)
        company_policy.unpaid_hold_days = 7
        company_policy.save(update_fields=['unpaid_hold_days'])
        policy = OperatingPolicy.objects.create(client=self.tenant, campus=self.campus_a, unpaid_hold_days=5)
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a)
        self.assertAlmostEqual(
            (payment_expiration_for(group) - timezone.now()).total_seconds(), 5 * 86400, delta=5,
        )

        client = self.authenticated(self.manager)
        response = client.delete(f'/api/admin/snowland/operating-policies/{policy.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(OperatingPolicy.objects.filter(pk=policy.id).exists())
        self.assertAlmostEqual(
            (payment_expiration_for(group) - timezone.now()).total_seconds(), 7 * 86400, delta=5,
        )

    def test_company_policy_cannot_be_deleted(self):
        policy = OperatingPolicy.objects.get(client=self.tenant, campus__isnull=True)
        response = self.authenticated(self.superuser).delete(
            f'/api/admin/snowland/operating-policies/{policy.id}/',
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(OperatingPolicy.objects.filter(pk=policy.id).exists())

    def test_campus_manager_cannot_reset_another_campus_policy(self):
        policy = OperatingPolicy.objects.create(client=self.tenant, campus=self.campus_b)
        response = self.authenticated(self.manager).delete(
            f'/api/admin/snowland/operating-policies/{policy.id}/',
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(OperatingPolicy.objects.filter(pk=policy.id).exists())

    def test_campus_manager_cannot_change_company_payment_settings(self):
        self.profile.admin_permissions = ['payment_settings']
        self.profile.save(update_fields=['admin_permissions'])
        client = self.authenticated(self.manager)
        url = '/api/admin/snowland/payment-settings/'
        self.assertEqual(client.get(url).status_code, 200)
        response = client.put(url, {'bank_name': '擅自修改'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.tenant.refresh_from_db()
        self.assertNotEqual(self.tenant.bank_name, '擅自修改')

        headquarters = self.authenticated(self.superuser)
        response = headquarters.put(url, {'bank_name': '總部銀行'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.bank_name, '總部銀行')

    def test_campus_with_orders_cannot_be_deleted(self):
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='訂單')
        client = self.authenticated(self.superuser)
        response = client.delete(f'/api/admin/snowland/campuses/{self.campus_a.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Campus.objects.filter(pk=self.campus_a.id).exists())

    def test_campus_with_staff_or_coach_cannot_be_deleted(self):
        client = self.authenticated(self.superuser)
        response = client.delete(f'/api/admin/snowland/campuses/{self.campus_a.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.profile.campuses.filter(pk=self.campus_a.id).exists())

        coach = Coach.objects.create(client=self.tenant, name='B 校區教練')
        coach.campuses.add(self.campus_b)
        response = client.delete(f'/api/admin/snowland/campuses/{self.campus_b.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(coach.campuses.filter(pk=self.campus_b.id).exists())

    def test_campus_with_payment_account_or_notification_cannot_be_deleted(self):
        client = self.authenticated(self.superuser)
        account = PaymentAccount.objects.create(client=self.tenant, name='B 校區收款')
        account.campuses.add(self.campus_b)
        response = client.delete(f'/api/admin/snowland/campuses/{self.campus_b.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(account.campuses.filter(pk=self.campus_b.id).exists())

        campus = Campus.objects.create(client=self.tenant, name='通知專用', code='notice')
        NotificationTemplate.objects.create(
            client=self.tenant, campus=campus, name='課前提醒', event='pre_course', channel='email', body='通知'
        )
        response = client.delete(f'/api/admin/snowland/campuses/{campus.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(NotificationTemplate.objects.filter(campus=campus).exists())

    def test_unused_campus_can_be_deleted(self):
        client = self.authenticated(self.superuser)
        created = client.post('/api/admin/snowland/campuses/', {'name': '空校區', 'code': 'empty'}, format='json')
        self.assertEqual(created.status_code, 201)
        campus = Campus.objects.get(client=self.tenant, code='empty')
        override = client.post('/api/admin/snowland/operating-policies/', {'campus': campus.id}, format='json')
        self.assertEqual(override.status_code, 201)
        self.assertTrue(OperatingPolicy.objects.filter(campus=campus).exists())
        response = client.delete(f'/api/admin/snowland/campuses/{campus.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Campus.objects.filter(pk=campus.id).exists())
        self.assertFalse(OperatingPolicy.objects.filter(campus_id=campus.id).exists())

    def test_admin_me_returns_scope_context(self):
        client = self.authenticated(self.manager)
        response = client.get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['role'], 'campus_manager')
        self.assertFalse(response.data['data']['can_view_all_campuses'])
        self.assertEqual(response.data['data']['assigned_campus_ids'], [self.campus_a.id])

    def test_coach_only_admin_me_lists_only_coach_campuses(self):
        coach_user = User.objects.create_user('campus-coach', 'coach@example.test', 'test-password')
        coach_profile = coach_user.userprofile
        coach_profile.is_coach = True
        coach_profile.save(update_fields=['is_coach'])
        coach = Coach.objects.create(client=self.tenant, user=coach_user, name='A 教練')
        coach.campuses.add(self.campus_a)

        response = self.authenticated(coach_user).get('/api/admin/snowland/me/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['data']['can_view_all_campuses'])
        self.assertEqual(response.data['data']['assigned_campus_ids'], [self.campus_a.id])
        self.assertEqual([item['id'] for item in response.data['data']['campuses']], [self.campus_a.id])

    def test_order_list_respects_selected_campus(self):
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='A order')
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_b, name='B order')
        client = self.authenticated(self.superuser)
        response = client.get('/api/admin/snowland/orders/', HTTP_X_CAMPUS_ID=str(self.campus_b.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 1)
        self.assertEqual(response.data['data']['list'][0]['name'], 'B order')

    def test_campus_manager_cannot_complete_other_campus_order(self):
        other_order = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_b, name='B order')
        response = self.authenticated(self.manager).post(
            f'/api/admin/snowland/orders/{other_order.pk}/complete-course/',
            {'reservation_id': 1}, format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_campus_manager_order_info_is_ten_day_read_only_summary(self):
        today = timezone.localdate()
        member = User.objects.create_user('student', 'private@example.com', 'test-password')
        created = []
        for campus, resort, offset in (
            (self.campus_a, self.resort_a, 1),
            (self.campus_a, self.resort_a, 11),
            (self.campus_b, self.resort_b, 1),
        ):
            group = ReservationGroup.objects.create(client=self.tenant, campus=campus, user=member, name=f'訂單-{offset}')
            reservation = Reservation.objects.create(group=group, resort=resort, number_of_people=1)
            Booking.objects.create(
                reservation=reservation, date=today + timedelta(days=offset),
                start_time=time(9), end_time=time(11), course_type='單板', course_name='上午班',
            )
            created.append(group)
        later_reservation = Reservation.objects.create(
            group=created[0], resort=self.resort_a, number_of_people=7,
        )
        Booking.objects.create(
            reservation=later_reservation, date=today + timedelta(days=12),
            start_time=time(9), end_time=time(11), course_type='雙板', course_name='未來課程',
        )

        client = self.authenticated(self.manager)
        response = client.get('/api/admin/snowland/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['total'], 1)
        item = response.data['data']['list'][0]
        self.assertEqual(item['id'], created[0].id)
        self.assertEqual(item['number_of_people'], 1)
        self.assertEqual(item['course_dates'], [(today + timedelta(days=1)).isoformat()])
        self.assertEqual(len(item['sessions']), 1)
        self.assertNotIn('private@example.com', str(item))
        for forbidden in ('user_email', 'total_fee', 'payment_status', 'bank_account', 'revisions'):
            self.assertNotIn(forbidden, item)

        self.assertEqual(client.get('/api/admin/snowland/orders/', {'search': 'private@example.com'}).data['data']['total'], 0)
        self.assertEqual(client.get('/api/admin/snowland/orders/', {'search': item['sn']}).data['data']['total'], 1)
        ReservationGroup.objects.filter(pk=created[0].pk).update(order_number='DEMO-MANAGER-001')
        self.assertEqual(client.get('/api/admin/snowland/orders/', {'search': 'DEMO-MANAGER-001'}).data['data']['total'], 1)
        self.assertEqual(client.get('/api/admin/snowland/orders/', {'payment_status': 'paid'}).data['data']['total'], 1)

        from booking.operations import record_order_revision
        record_order_revision(created[0])
        detail = client.get(f'/api/admin/snowland/orders/{created[0].id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn('user_email', detail.data['data'])
        self.assertNotIn('revisions', detail.data['data'])
        self.assertEqual(client.get(f'/api/admin/snowland/orders/{created[1].id}/').status_code, 404)
        self.assertEqual(client.get(f'/api/admin/snowland/orders/{created[2].id}/').status_code, 404)
        self.assertEqual(client.patch(f'/api/admin/snowland/orders/{created[0].id}/', {'payment_status': 'paid'}, format='json').status_code, 403)
        self.assertEqual(client.get(f'/api/admin/snowland/orders/{created[0].id}/refund-preview/').status_code, 403)
        self.assertEqual(client.post(f'/api/admin/snowland/orders/{created[0].id}/class-group-link/', {
            'line_group_url': 'https://line.me/ti/g/not-allowed',
        }, format='json').status_code, 403)
        created[0].refresh_from_db()
        self.assertEqual(created[0].line_group_url, '')

    def test_campus_principal_sees_all_own_campus_dates_but_only_partial_order_info(self):
        today = timezone.localdate()
        principal = User.objects.create_user('principal', 'principal@example.com', 'test-password')
        profile = principal.userprofile
        profile.is_manager = True
        profile.manager_client = self.tenant
        profile.role = 'campus_principal'
        profile.admin_permissions = ['orders']
        profile.save()
        profile.campuses.add(self.campus_a)
        customer = User.objects.create_user('private-customer', 'private@example.com', 'test-password')
        customer.first_name = '小雪'
        customer.save(update_fields=['first_name'])
        groups = []
        for campus, resort, offset in (
            (self.campus_a, self.resort_a, 1),
            (self.campus_a, self.resort_a, 11),
            (self.campus_b, self.resort_b, 1),
        ):
            group = ReservationGroup.objects.create(client=self.tenant, campus=campus, user=customer)
            reservation = Reservation.objects.create(group=group, resort=resort, number_of_people=2)
            MemberDetail.objects.create(reservation=reservation, age_range='7-12y')
            Booking.objects.create(
                reservation=reservation, date=today + timedelta(days=offset),
                start_time=time(9), end_time=time(11), course_type='單板', course_name='上午班',
            )
            groups.append(group)

        client = self.authenticated(principal)
        response = client.get('/api/admin/snowland/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item['id'] for item in response.data['data']['list']}, {groups[0].id, groups[1].id})
        item = next(item for item in response.data['data']['list'] if item['id'] == groups[1].id)
        self.assertEqual(item['student_alias'], '小雪')
        self.assertEqual(item['course_dates'], [(today + timedelta(days=11)).isoformat()])
        self.assertEqual(item['number_of_people'], 2)
        self.assertEqual(item['sessions'][0]['age_ranges'], ['兒童7-12y'])
        for forbidden in ('user_email', 'total_fee', 'payment_status', 'bank_account', 'revisions'):
            self.assertNotIn(forbidden, item)
        self.assertEqual(client.get('/api/admin/snowland/orders/', {'search': 'private@example.com'}).data['data']['total'], 0)
        ReservationGroup.objects.filter(pk=groups[0].pk).update(order_number='DEMO-PRINCIPAL-001')
        ReservationGroup.objects.filter(pk=groups[2].pk).update(order_number='DEMO-OTHER-CAMPUS-001')
        self.assertEqual(client.get('/api/admin/snowland/orders/', {'search': 'DEMO-PRINCIPAL-001'}).data['data']['total'], 1)
        self.assertEqual(client.get('/api/admin/snowland/orders/', {'search': 'DEMO-OTHER-CAMPUS-001'}).data['data']['total'], 0)
        self.assertEqual(client.get(f'/api/admin/snowland/orders/{groups[2].id}/').status_code, 404)
        self.assertEqual(client.patch(f'/api/admin/snowland/orders/{groups[0].id}/', {'payment_status': 'paid'}, format='json').status_code, 403)
        self.assertEqual(client.get(f'/api/admin/snowland/orders/{groups[0].id}/refund-preview/').status_code, 403)

    def test_dashboard_respects_campus_scope_and_shows_breakdowns(self):
        ReservationGroup.objects.create(
            client=self.tenant, campus=self.campus_a, name='A order', marketing_source='Google'
        )
        ReservationGroup.objects.create(
            client=self.tenant, campus=self.campus_b, name='B order', marketing_source='朋友介紹'
        )
        client = self.authenticated(self.superuser)
        response = client.get('/api/admin/snowland/dashboard/', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['stats']['orders'], 1)
        self.assertEqual(response.data['data']['campus_summary'][0]['name'], 'A 校區')
        self.assertEqual(response.data['data']['marketing_sources'][0]['name'], 'Google')

    def test_headquarters_dashboard_includes_inactive_campus_history(self):
        active = ReservationGroup.objects.create(
            client=self.tenant, campus=self.campus_a, name='A order'
        )
        inactive = ReservationGroup.objects.create(
            client=self.tenant, campus=self.campus_b, name='B old order'
        )
        self.campus_b.is_active = False
        self.campus_b.save(update_fields=['is_active'])
        url = '/api/admin/snowland/dashboard/'

        headquarters = self.authenticated(self.superuser)
        all_result = headquarters.get(url, HTTP_X_CAMPUS_ID='all')
        self.assertEqual(all_result.status_code, 200, all_result.data)
        self.assertEqual(all_result.data['data']['stats']['orders'], 2)
        self.assertEqual({row['name'] for row in all_result.data['data']['campus_summary']}, {
            self.campus_a.name, self.campus_b.name,
        })
        self.assertEqual({row['name']: row['is_active'] for row in all_result.data['data']['campus_summary']}, {
            self.campus_a.name: True, self.campus_b.name: False,
        })
        self.assertEqual({row['sn'] for row in all_result.data['data']['recent_orders']}, {
            f'SL{active.created_at.year}-{active.id:04d}',
            f'SL{inactive.created_at.year}-{inactive.id:04d}',
        })

        selected = headquarters.get(url, HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(selected.data['data']['stats']['orders'], 1)
        self.assertEqual(selected.data['data']['campus_summary'][0]['name'], self.campus_a.name)

        self.profile.admin_permissions = ['analytics']
        self.profile.save(update_fields=['admin_permissions'])
        manager = self.authenticated(self.manager)
        own = manager.get(url)
        self.assertEqual(own.status_code, 200, own.data)
        self.assertEqual(own.data['data']['stats']['orders'], 1)

    def test_headquarters_customer_list_includes_inactive_campus_member(self):
        member = User.objects.create_user('historical-member', 'history@example.test', 'test-password')
        ReservationGroup.objects.create(client=self.tenant, campus=self.campus_b, user=member)
        self.campus_b.is_active = False
        self.campus_b.save(update_fields=['is_active'])
        url = '/api/admin/snowland/customers/'

        headquarters = self.authenticated(self.superuser)
        all_result = headquarters.get(url, HTTP_X_CAMPUS_ID='all')
        self.assertEqual(all_result.status_code, 200, all_result.data)
        self.assertIn(member.id, [row['id'] for row in all_result.data['data']['list']])
        selected = headquarters.get(url, HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertNotIn(member.id, [row['id'] for row in selected.data['data']['list']])

        self.profile.admin_permissions = ['customers']
        self.profile.save(update_fields=['admin_permissions'])
        manager = self.authenticated(self.manager)
        own = manager.get(url)
        self.assertEqual(own.status_code, 200, own.data)
        self.assertNotIn(member.id, [row['id'] for row in own.data['data']['list']])

    def test_legacy_other_marketing_source_is_readable_and_grouped(self):
        legacy = ReservationGroup.objects.create(
            client=self.tenant, campus=self.campus_a, name='舊訂單', marketing_source='other'
        )
        ReservationGroup.objects.create(
            client=self.tenant, campus=self.campus_a, name='新訂單', marketing_source='其他'
        )

        client = self.authenticated(self.superuser)
        dashboard = client.get('/api/admin/snowland/dashboard/', HTTP_X_CAMPUS_ID=str(self.campus_a.id))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data['data']['marketing_sources'], [
            {'name': '其他', 'orders': 2, 'revenue': 0},
        ])

        detail = client.get(f'/api/admin/snowland/orders/{legacy.id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['data']['marketing_source'], '其他')
        legacy.refresh_from_db()
        self.assertEqual(legacy.marketing_source, 'other')

    def test_dashboard_member_count_excludes_guest_orders_and_deduplicates_members(self):
        member = User.objects.create_user('member', 'member@example.test', 'test-password')
        guest = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, name='Guest')
        first = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, user=member)
        second = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, user=member)
        Reservation.objects.create(group=guest, resort=self.resort_a, course_fee=1000)
        Reservation.objects.create(group=first, resort=self.resort_a, course_fee=2000)
        Reservation.objects.create(group=second, resort=self.resort_a, course_fee=3000)

        response = self.authenticated(self.superuser).get('/api/admin/snowland/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['stats']['orders'], 3)
        self.assertEqual(response.data['data']['stats']['members'], 1)
        # These orders are unpaid and not completed: membership still counts,
        # but they must not inflate completed-order revenue or its average.
        self.assertEqual(response.data['data']['stats']['revenue'], 0)
        self.assertEqual(response.data['data']['stats']['avg_order_value'], 0)

    def test_dashboard_today_and_yesterday_use_taipei_day_boundary(self):
        previous_day = ReservationGroup.objects.create(
            client=self.tenant, campus=self.campus_a, name='Previous day'
        )
        current_day = ReservationGroup.objects.create(
            client=self.tenant, campus=self.campus_a, name='Current day'
        )
        ReservationGroup.objects.filter(pk=previous_day.pk).update(
            created_at=datetime(2026, 10, 15, 15, 50, tzinfo=datetime_timezone.utc)
        )
        ReservationGroup.objects.filter(pk=current_day.pk).update(
            created_at=datetime(2026, 10, 15, 16, 10, tzinfo=datetime_timezone.utc)
        )
        utc_now = datetime(2026, 10, 15, 16, 30, tzinfo=datetime_timezone.utc)
        client = self.authenticated(self.superuser)

        with patch('API.admin_views.timezone.now', return_value=utc_now):
            today = client.get('/api/admin/snowland/dashboard/', {'period': 'today'})
            yesterday = client.get('/api/admin/snowland/dashboard/', {'period': 'yesterday'})

        self.assertEqual(today.status_code, 200)
        self.assertEqual(yesterday.status_code, 200)
        self.assertEqual(today.data['data']['stats']['orders'], 1)
        self.assertEqual(yesterday.data['data']['stats']['orders'], 1)

    def test_dashboard_week_and_month_use_taipei_boundaries(self):
        for label, created_at in (
            ('Sunday night', datetime(2026, 10, 4, 15, 50, tzinfo=datetime_timezone.utc)),
            ('Monday morning', datetime(2026, 10, 4, 16, 10, tzinfo=datetime_timezone.utc)),
        ):
            group = ReservationGroup.objects.create(
                client=self.tenant, campus=self.campus_a, name=label
            )
            ReservationGroup.objects.filter(pk=group.pk).update(created_at=created_at)

        client = self.authenticated(self.superuser)
        with patch('API.admin_views.timezone.now', return_value=datetime(
            2026, 10, 4, 16, 30, tzinfo=datetime_timezone.utc
        )):
            week = client.get('/api/admin/snowland/dashboard/', {'period': 'week'})
        for label, created_at in (
            ('October night', datetime(2026, 10, 31, 15, 50, tzinfo=datetime_timezone.utc)),
            ('November morning', datetime(2026, 10, 31, 16, 10, tzinfo=datetime_timezone.utc)),
        ):
            group = ReservationGroup.objects.create(
                client=self.tenant, campus=self.campus_a, name=label
            )
            ReservationGroup.objects.filter(pk=group.pk).update(created_at=created_at)
        with patch('API.admin_views.timezone.now', return_value=datetime(
            2026, 10, 31, 16, 30, tzinfo=datetime_timezone.utc
        )):
            month = client.get('/api/admin/snowland/dashboard/', {'period': 'month'})

        self.assertEqual(week.status_code, 200)
        self.assertEqual(month.status_code, 200)
        self.assertEqual(week.data['data']['stats']['orders'], 1)
        self.assertEqual(month.data['data']['stats']['orders'], 1)

    def test_principal_dashboard_recent_orders_hide_contact_and_per_order_payment(self):
        self.profile.role = 'campus_principal'
        self.profile.admin_permissions = ['analytics']
        self.profile.save(update_fields=['role', 'admin_permissions'])
        customer = User.objects.create_user('private@example.test', 'private@example.test', 'test-password')
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, user=customer)
        Reservation.objects.create(group=group, resort=self.resort_a, course_fee=12345)

        response = self.authenticated(User.objects.get(pk=self.manager.pk)).get('/api/admin/snowland/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['data']['restricted_order_details'])
        item = response.data['data']['recent_orders'][0]
        self.assertEqual(item['member'], '學員')
        self.assertNotIn('private@example.test', str(response.data['data']['recent_orders']))
        self.assertNotIn('amount', item)
        self.assertNotIn('status', item)

        self.profile.role = 'campus_manager'
        self.profile.save(update_fields=['role'])
        manager_response = self.authenticated(User.objects.get(pk=self.manager.pk)).get('/api/admin/snowland/dashboard/')
        self.assertEqual(manager_response.status_code, 200)
        self.assertTrue(manager_response.data['data']['restricted_order_details'])
        self.assertNotIn('private@example.test', str(manager_response.data['data']['recent_orders']))
        self.assertNotIn('amount', manager_response.data['data']['recent_orders'][0])

        headquarters = self.authenticated(self.superuser).get('/api/admin/snowland/dashboard/')
        self.assertFalse(headquarters.data['data']['restricted_order_details'])
        self.assertEqual(headquarters.data['data']['recent_orders'][0]['amount'], 12345)
