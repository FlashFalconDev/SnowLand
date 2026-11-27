from copy import deepcopy
from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting
from Control.models import TenantStaffMembership
from Coursekit.models import CourseCategory, CourseSession, CourseTemplate, CourseType
from . import tests_advanced_booking_scope, tests_tenant_gateway
from .capacity import PAID_CAPACITY_REVISION_REASON, Slot, group_capacity_conflicts, occupied_count
from .models import Booking, MemberDetail, OrderRevision, Payment, Reservation, ReservationGroup, StaffBookingLink


class CapacityRecheckTests(TestCase):
    def setUp(self):
        tests_advanced_booking_scope.AdvancedBookingScopeTests.setUp(self)
        self.submit_url = '/booking/snowland/api/create-reservation/'
        self.lesson = self.payload['cart'][0]['courses'][0]
        self.day = date.fromisoformat(self.lesson['date'])
        self.slot = Slot(self.private_template, self.day, time(9), time(13))
        self.session = CourseSession.objects.create(
            template=self.private_template, start_time=self.slot.start_time, end_time=self.slot.end_time,
        )
        self.user = User.objects.get(username='pricing-member')
        self.credentials = {'MerchantID': 'A-merchant', 'HashKey': 'K' * 32, 'HashIV': 'I' * 16}

    def set_limit(self, capacity):
        self.private_template.max_capacity = capacity
        self.private_template.save(update_fields=['max_capacity'])

    def opt_out(self):
        ModuleSetting.objects.create(
            client=self.client_record,
            module=ModuleInfo.objects.create(module_sid='booking', module_name='預約'),
            settings={'booking_capacity_recheck_enabled': False},
        )

    def create_booking(self, *, template=None, group=None, status='created', **booking_fields):
        template = template or self.private_template
        group = group or ReservationGroup.objects.create(client=self.client_record, campus=self.campus, user=self.user)
        reservation = Reservation.objects.create(
            group=group, resort=self.resort, course_template=template,
            course_type=template.course_type, course_fee=1000, number_of_people=4, status=status,
        )
        return self.add_lesson(reservation, **booking_fields)

    def add_lesson(self, reservation, **fields):
        return Booking.objects.create(reservation=reservation, **{
            'date': self.day, 'start_time': self.slot.start_time, 'end_time': self.slot.end_time, **fields,
        })

    def sessions(self, **params):
        return self.api.get('/booking/snowland/api/course-sessions/', {
            'template_id': self.private_template.pk, 'date': self.day.isoformat(), **params,
        })

    def counts(self):
        return tuple(model.objects.count() for model in (ReservationGroup, Reservation, Booking, Payment, MemberDetail, OrderRevision))

    def payment_info(self, group):
        return self.api.get('/booking/snowland/api/payment-info/', {'reservation_group': group.pk})

    def process_payment(self, group, method):
        return self.api.post('/booking/snowland/api/process-payment/', {
            'reservation_group_id': group.pk, 'payment_type': method, 'sender_account': '12345',
        }, format='json')

    def notify(self, group, **kwargs):
        return tests_tenant_gateway.TenantGatewayTests.notify(
            self, school='snowland', order=group.pk, **kwargs,
        )

    def test_display_matches_original_count_and_response(self):
        self.set_limit(0)  # Preserve the legacy fallback to six.
        live = self.create_booking(course_template=self.per_person_template)
        for _ in range(4):
            self.add_lesson(live.reservation)
        self.create_booking(status='cancelled')
        self.create_booking(status='deleted')
        self.create_booking(is_deleted=True)
        archived = self.create_booking()
        ReservationGroup.objects.filter(pk=archived.reservation.group_id).update(is_deleted=True)
        deleted = self.create_booking()
        Reservation.objects.filter(pk=deleted.reservation_id).update(is_deleted=True)
        self.create_booking(template=self.per_person_template)
        self.create_booking(date=self.day + timedelta(days=1))
        self.create_booking(start_time=time(9, 1))
        self.create_booking(end_time=time(12, 59))
        foreign = Client.objects.create(name='Other', internal_code='other')
        kind = CourseType.objects.create(category=CourseCategory.objects.create(client=foreign, name='Other'), name='Other')
        foreign_template = CourseTemplate.objects.create(course_type=kind, name='Other', duration_hours=4)
        foreign_group = ReservationGroup.objects.create(client=foreign)
        self.create_booking(group=foreign_group, template=foreign_template)
        self.opt_out()
        for expected_count in (5, 6):
            with self.subTest(expected_count=expected_count):
                old_count = Reservation.objects.live().filter(
                    course_template=self.private_template, bookings__is_deleted=False, bookings__date=self.day,
                    bookings__start_time=self.slot.start_time, bookings__end_time=self.slot.end_time,
                ).exclude(status__in=['cancelled', 'deleted']).count()
                self.assertEqual(old_count, expected_count)
                self.assertEqual(occupied_count(self.slot), old_count)
                self.assertEqual(self.sessions().data, [{
                    'id': self.session.pk, 'template_id': self.private_template.pk,
                    'start_time': '09:00', 'end_time': '13:00', 'is_active': True,
                    'is_full': old_count >= 6, 'shared_class': None,
                }])
                self.add_lesson(live.reservation)
        self.assertFalse(self.sessions(date='').data[0]['is_full'])

    def test_available_slot_then_full_slot_for_both_checkout_routes(self):
        self.set_limit(1)
        response = self.api.post(self.submit_url, self.payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        before = self.counts()
        for url in (self.submit_url, self.url):
            with self.subTest(url=url):
                response = self.api.post(url, self.payload, format='json')
                self.assertEqual(response.status_code, 409, response.data)
                self.assertEqual(response.data['code'], 'slot_full')
                self.assertIn(f'{self.day} 09:00–13:00', response.data['message'])
                self.assertEqual(response.data['conflicts'][0]['occupied'], 1)
                self.assertEqual(self.counts(), before)

    def test_opt_out_allows_checkout_and_payment_while_display_stays_full(self):
        self.set_limit(1)
        self.create_booking()
        self.opt_out()
        self.assertTrue(self.sessions().data[0]['is_full'])
        response = self.api.post(self.submit_url, self.payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        group = ReservationGroup.objects.get(pk=response.data['reservation_group_ids'][0])
        self.assertEqual(self.payment_info(group).status_code, 200)
        self.assertEqual(self.process_payment(group, 'bank_transfer').status_code, 200)

    def test_mixed_templates_reject_the_whole_cart(self):
        self.per_person_template.max_capacity = 1
        self.per_person_template.save(update_fields=['max_capacity'])
        body = deepcopy(self.payload)
        body['cart'][0]['courses'][1].update(courseTemplateId=self.per_person_template.pk)
        self.create_booking(template=self.per_person_template, date=self.day + timedelta(days=1))
        before = self.counts()
        for url in (self.submit_url, self.url):
            response = self.api.post(url, body, format='json')
            self.assertEqual(response.status_code, 409, response.data)
            self.assertEqual([slot['template_id'] for slot in response.data['conflicts']], [self.per_person_template.pk])
            self.assertEqual(self.counts(), before)

    def test_batch_that_would_exceed_capacity_is_rejected_before_creating_any_row(self):
        self.set_limit(1)
        body = deepcopy(self.payload)
        body['cart'][0]['courses'][1] = deepcopy(self.lesson)
        for url in (self.submit_url, self.url):
            response = self.api.post(url, body, format='json')
            self.assertEqual(response.status_code, 409, response.data)
            self.assertEqual(response.data['conflicts'][0]['occupied'], 0)
            self.assertEqual(self.counts(), (0, 0, 0, 0, 0, 0))

    def test_staff_selected_full_slot_does_not_consume_link(self):
        self.set_limit(1)
        self.create_booking()
        link = StaffBookingLink.objects.create(
            client=self.client_record, campus=self.campus, created_by=self.user, title='代客測試',
            expires_at=timezone.now() + timedelta(days=1),
        )
        before = self.counts()
        response = self.api.post(self.submit_url, {**self.payload, 'staff_link': str(link.token)}, format='json')
        self.assertEqual(response.status_code, 409, response.data)
        link.refresh_from_db()
        self.assertIsNone(link.used_at)
        self.assertEqual(self.counts(), before)

    def test_legacy_checkout_rechecks_before_creating_any_rows(self):
        self.set_limit(1)
        self.create_booking()
        before = self.counts()
        response = self.api.post('/booking/api/create_reservation/', {
            'tunnel': 'super_schedule',
            'courses': [{
                'resort': self.resort.name, 'courseType': self.private_template.course_type_id,
                'booking': [{'timeSlot': self.private_template.pk, 'date': self.day.isoformat()}],
            }],
        }, format='json')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['code'], 'slot_full')
        self.assertEqual(self.counts(), before)

    def test_payment_excludes_own_reservations_and_preserves_the_limit_boundary(self):
        self.set_limit(2)
        reservation = self.create_booking().reservation
        group = reservation.group
        self.add_lesson(reservation)
        self.assertTrue(self.sessions().data[0]['is_full'])
        self.assertEqual(occupied_count(self.slot, exclude_group_id=group.pk), 0)
        self.assertEqual(group_capacity_conflicts(group), [])
        payment = Payment.objects.create(reservation_group=group)
        self.assertEqual(self.payment_info(group).status_code, 200)
        response = self.process_payment(group, 'bank_transfer')
        self.assertEqual(response.status_code, 200, response.data)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'pending')

    def test_full_slot_holds_payment_info_card_form_and_transfer(self):
        self.set_limit(1)
        group = self.create_booking().reservation.group
        payment = Payment.objects.create(reservation_group=group)
        self.create_booking()
        with patch('booking.api_views.neweb_pay_request') as form:
            for response in (
                self.payment_info(group), self.process_payment(group, 'newebpay'),
                self.process_payment(group, 'bank_transfer'),
            ):
                self.assertEqual(response.status_code, 409, response.data)
                self.assertEqual(response.data['code'], 'slot_full_at_payment')
                self.assertFalse(response.data['requires_payment'])
                self.assertIn('客服', response.data['message'])
            form.assert_not_called()
        payment.refresh_from_db()
        group.refresh_from_db()
        self.assertEqual(payment.status, 'unpaid')
        self.assertFalse(group.newebpay_form_issued)

    def test_paid_order_does_not_recheck(self):
        self.set_limit(1)
        group = self.create_booking().reservation.group
        Payment.objects.create(reservation_group=group, status='paid')
        self.create_booking()
        with patch('booking.api_views.group_capacity_conflicts') as capacity:
            self.assertEqual(self.payment_info(group).data['payment_status'], 'paid')
            self.assertEqual(self.process_payment(group, 'bank_transfer').status_code, 400)
            capacity.assert_not_called()

    def test_full_signed_callback_keeps_payment_and_marks_conflict_only_once(self):
        self.set_limit(1)
        group = self.create_booking(status='manually_assigned', is_scheduled=True).reservation.group
        payment = Payment.objects.create(reservation_group=group, DataJSON={'original': 'keep'})
        self.create_booking()
        self.assertEqual(self.notify(group, signature='BAD').status_code, 400)
        self.assertEqual(self.notify(group, amount=999).status_code, 409)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'unpaid')
        self.assertEqual(self.notify(group).status_code, 200)
        payment.refresh_from_db()
        marker = payment.DataJSON['capacity_conflict']
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(payment.DataJSON['original'], 'keep')
        self.assertIn('detected_at', marker)
        self.assertEqual(marker['conflicts'][0]['date'], self.day.isoformat())
        self.assertEqual(marker['conflicts'][0]['occupied'], 1)
        self.assertEqual(self.notify(group).status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.DataJSON['capacity_conflict'], marker)
        self.assertEqual(list(group.revisions.values_list('reason', flat=True)), [PAID_CAPACITY_REVISION_REASON])
        self.assertEqual(group.reservations.get().status, 'manually_assigned')
        self.assertTrue(group.reservations.get().bookings.get().is_scheduled)

    def test_signed_callback_with_capacity_has_no_marker(self):
        self.set_limit(1)
        group = self.create_booking().reservation.group
        payment = Payment.objects.create(reservation_group=group)
        self.assertEqual(self.notify(group).status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'paid')
        self.assertNotIn('capacity_conflict', payment.DataJSON)
        self.assertFalse(group.revisions.exists())

    def test_paid_capacity_check_can_be_disabled(self):
        self.set_limit(1)
        group = self.create_booking().reservation.group
        self.create_booking()
        self.opt_out()
        payment = Payment.objects.create(reservation_group=group)
        self.assertEqual(self.notify(group).status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'paid')
        self.assertNotIn('capacity_conflict', payment.DataJSON)
        self.assertFalse(group.revisions.exists())

    def test_bank_reconciliation_marks_capacity_conflict_visible_in_admin(self):
        self.set_limit(1)
        group = self.create_booking().reservation.group
        Payment.objects.create(reservation_group=group, status='pending')
        self.create_booking()
        admin = APIClient()
        user = User.objects.create_user('capacity-finance')
        TenantStaffMembership.objects.create(
            client=self.client_record, user=user, is_manager=True, role='hq_admin', all_campuses=True,
        )
        admin.force_authenticate(user)
        orders = '/api/admin/snowland/orders/'
        detail = f'{orders}{group.pk}/'
        for _ in range(2):
            response = admin.patch(detail, {'action': 'save', 'payment_status': 'paid'}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
        data = admin.get(detail).data['data']
        self.assertEqual(data['payment_status'], 'paid')
        self.assertEqual(data['capacity_conflict']['conflicts'][0]['code'], 'full')
        self.assertEqual(group.revisions.filter(reason=PAID_CAPACITY_REVISION_REASON).count(), 1)
        row = next(order for order in admin.get(orders).data['data']['list'] if order['id'] == group.pk)
        self.assertEqual(row['capacity_conflict'], data['capacity_conflict'])
