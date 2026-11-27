from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, time, timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import ModuleInfo, ModuleSetting
from Control.models import TenantStaffMembership
from Coursekit.models import CourseSession
from booking.models import BookingClosure, ReservationGroup, StaffBookingLink, StaffLinkCapacityHold

from .tests_staff_booking_link_edit import StaffLinkFixture


class StaffHoldFixture(StaffLinkFixture):
    list_url = '/api/admin/snowland/staff-booking-links/'
    sessions_url = '/booking/snowland/api/course-sessions/'

    def setUp(self):
        super().setUp()
        self.day = date.fromisoformat(self.cart[0]['courses'][0]['date'])
        self.template.max_capacity = 1
        self.template.save(update_fields=['max_capacity'])
        CourseSession.objects.create(template=self.template, start_time=time(9), end_time=time(13))
        self.hq = self.headquarters('hold-hq')

    def headquarters(self, username, *, permissions=None):
        user = get_user_model().objects.create_user(username)
        TenantStaffMembership.objects.create(
            client=self.tenant, user=user, is_manager=True, role='hq_admin', all_campuses=True,
            admin_permissions=['booking_links', 'order_edit', 'scheduling'] if permissions is None else permissions,
        )
        return user

    def create_link(self, *, user=None, cart=None, **fields):
        return self.api_for(user or self.hq).post(self.list_url, {
            'campus': self.campus.pk, 'title': '私人課保留', 'expires_at': self.link.expires_at.isoformat(),
            'cart_snapshot': self.cart if cart is None else cart,
            **fields,
        }, format='json')

    def take_hold(self, **fields):
        response = self.create_link(hold_capacity=True, **fields)
        self.assertEqual(response.status_code, 201, response.data)
        return StaffBookingLink.objects.get(pk=response.data['id'])

    def slots(self, *, day=None, **params):
        response = APIClient().get(self.sessions_url, {
            'template_id': self.template.pk, 'date': (day or self.day).isoformat(),
            'resort': self.resort.name, **params,
        })
        self.assertEqual(response.status_code, 200)
        return response.data[0]

    def cart_for(self, *days):
        cart = deepcopy(self.cart)
        cart[0]['courses'] = [{**self.cart[0]['courses'][0], 'date': day.isoformat()} for day in days]
        return cart

    def use_link(self, link):
        self.public_url = f'/booking/snowland/api/staff-booking-link/{link.token}/'
        return self.load_tab()


class StaffLinkCapacityHoldTests(StaffHoldFixture, TestCase):
    def test_hq_creates_hold_and_both_availability_and_checkout_count_it(self):
        self.assertFalse(self.slots()['is_full'])
        held = self.take_hold()
        self.assertTrue(self.slots()['is_full'])
        self.assertFalse(self.slots(staff_link=str(held.token))['is_full'])
        self.assertTrue(self.slots(staff_link=str(self.link.token))['is_full'])
        self.assertFalse(ReservationGroup.objects.exists())
        listing = self.api_for(self.hq).get(self.list_url).data['data']
        self.assertTrue(listing['can_create_hold'])
        self.assertTrue(listing['can_release_hold'])
        holds = next(row['capacity_holds'] for row in listing['list'] if row['id'] == held.pk)
        self.assertEqual([(hold['date'], hold['start_time'], hold['end_time']) for hold in holds],
                         [(self.day.isoformat(), '09:00', '13:00')])
        self.assertEqual(held.capacity_holds.get().expires_at, held.expires_at)
        response = self.api_for(self.member).post(self.checkout_url, self.load_tab(), format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'slot_full')
        self.assertFalse(ReservationGroup.objects.exists())

    def test_full_conflict_reports_all_slots_and_creates_no_rows_on_retry(self):
        next_day = self.day + timedelta(days=1)
        self.take_hold(cart=self.cart_for(self.day, next_day))
        link_count = StaffBookingLink.objects.count()
        for _ in range(2):
            response = self.create_link(hold_capacity=True, cart=self.cart_for(self.day, next_day))
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data['code'], 'slot_full')
            self.assertEqual([slot['date'] for slot in response.data['conflicts']],
                             [self.day.isoformat(), next_day.isoformat()])
        self.assertEqual(StaffBookingLink.objects.count(), link_count)
        self.assertEqual(StaffLinkCapacityHold.objects.count(), 2)
        self.assertFalse(ReservationGroup.objects.exists())

    def test_capacity_counts_groups_not_people_or_duplicate_lessons(self):
        cart = self.cart_for(self.day, self.day)
        cart[0]['peopleCount'] = 4
        held = self.take_hold(cart=cart)
        self.assertEqual(held.capacity_holds.count(), 1)
        response = self.create_link(hold_capacity=True, cart=[cart[0], {**cart[0], 'id': 'another'}])
        self.assertEqual(response.data['conflicts'][0]['occupied'], 1)

    def test_legacy_link_can_acquire_hold_and_edit_moves_existing_hold_atomically(self):
        admin = self.api_for(self.hq)
        self.assertFalse(self.link.capacity_holds.exists())
        initial = self.edit(user=self.hq, hold_capacity=True)
        self.assertEqual(initial.status_code, 200, initial.data)
        version = initial.data['snapshot_version']
        old_hold = self.link.capacity_holds.get()
        next_day = self.day + timedelta(days=1)
        other_link = self.take_hold(cart=self.cart_for(next_day))
        edited = self.edit(user=self.hq, cart=self.cart_for(next_day), hold_capacity=True, version=version)
        self.assertEqual(edited.status_code, 409)
        self.assertEqual(edited.data['code'], 'slot_full')
        old_hold.refresh_from_db()
        self.assertIsNone(old_hold.released_at)
        self.assertEqual(self.link.capacity_holds.count(), 1)
        self.link.refresh_from_db()
        self.assertEqual(self.link.cart_snapshot[0]['courses'][0]['date'], self.day.isoformat())

        admin.post(f'{self.list_url}{other_link.pk}/release-hold/')
        moved = self.edit(user=self.hq, cart=self.cart_for(next_day), hold_capacity=True, version=version)
        self.assertEqual(moved.status_code, 200, moved.data)
        self.assertEqual(moved.data['snapshot_version'], version + 1)
        old_hold.refresh_from_db()
        self.assertIsNotNone(old_hold.released_at)
        self.assertFalse(self.slots()['is_full'])
        self.assertTrue(self.slots(day=next_day)['is_full'])
        self.assertEqual(self.edit(user=self.hq, hold_capacity=True, version=version).status_code, 409)

    def test_failure_after_releasing_old_rows_restores_hold_and_snapshot(self):
        saved = self.edit(user=self.hq, hold_capacity=True)
        self.assertEqual(saved.status_code, 200)
        version = saved.data['snapshot_version']
        original = self.link.capacity_holds.get()
        with patch('API.admin_views.create_holds', side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                self.edit(user=self.hq, cart=self.cart_for(self.day + timedelta(days=1)), hold_capacity=True, version=version)
        original.refresh_from_db()
        self.link.refresh_from_db()
        self.assertIsNone(original.released_at)
        self.assertEqual(self.link.snapshot_version, version)
        self.assertTrue(self.slots()['is_full'])

    def test_customer_converts_hold_without_blocking_own_slot(self):
        link = self.take_hold()
        response = self.api_for(self.member).post(self.checkout_url, self.use_link(link), format='json')
        self.assertEqual(response.status_code, 200, response.data)
        hold = link.capacity_holds.get()
        link.refresh_from_db()
        self.assertEqual(hold.released_at, hold.converted_at)
        self.assertIsNotNone(hold.converted_at)
        self.assertIsNotNone(link.used_at)
        self.assertEqual(ReservationGroup.objects.count(), 1)
        self.assertTrue(self.slots()['is_full'])
        response = self.create_link(hold_capacity=True)
        self.assertEqual(response.data['conflicts'][0]['occupied'], 1)

    def test_checkout_late_failure_rolls_back_conversion(self):
        link = self.take_hold()
        payload = self.use_link(link)
        with patch('booking.operations.resolve_payment_account', side_effect=ValueError('測試付款設定失敗')):
            response = self.api_for(self.member).post(self.checkout_url, payload, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        link.refresh_from_db()
        self.assertIsNone(link.used_at)
        self.assertIsNone(link.capacity_holds.get().released_at)
        self.assertFalse(ReservationGroup.objects.exists())
        self.assertTrue(self.slots()['is_full'])

    def test_expired_deactivated_used_and_deleted_links_release_capacity(self):
        admin = self.api_for(self.hq)
        expired = self.take_hold()
        expired.capacity_holds.update(expires_at=timezone.now())
        self.assertFalse(self.slots()['is_full'])
        expired.capacity_holds.update(expires_at=expired.expires_at)
        StaffBookingLink.objects.filter(pk=expired.pk).update(expires_at=timezone.now())
        self.assertFalse(self.slots()['is_full'])

        inactive = self.take_hold()
        response = admin.patch(f'{self.list_url}{inactive.pk}/', {'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNotNone(inactive.capacity_holds.get().released_at)
        self.assertFalse(self.slots()['is_full'])

        used = self.take_hold()
        StaffBookingLink.objects.filter(pk=used.pk).update(used_at=timezone.now())
        self.assertFalse(self.slots()['is_full'])
        deleted = self.take_hold()
        self.assertEqual(admin.delete(f'{self.list_url}{deleted.pk}/').status_code, 204)
        self.assertFalse(deleted.capacity_holds.exists())
        self.assertFalse(self.slots()['is_full'])

    def test_scoped_users_and_hq_without_scheduling_cannot_request_or_release_holds(self):
        link = self.take_hold()
        for user in (self.author, self.manager('local-manager', self.campus),
                     self.headquarters('restricted-hq', permissions=['booking_links', 'order_edit'])):
            with self.subTest(role=user.username):
                plain = self.create_link(user=user)
                self.assertEqual(plain.status_code, 201, plain.data)
                self.assertEqual(plain.data['capacity_holds'], [])
                self.assertEqual(self.create_link(user=user, hold_capacity=True).status_code, 403)
                self.assertEqual(self.edit(user=user, hold_capacity=True).status_code, 403)
                self.assertFalse(self.api_for(user).get(self.list_url).data['data']['can_create_hold'])
                self.assertEqual(self.api_for(user).post(f'{self.list_url}{link.pk}/release-hold/').status_code, 403)
        self.assertTrue(self.slots()['is_full'])

    def test_hq_release_is_audited_and_safe_to_retry(self):
        link = self.take_hold()
        url = f'{self.list_url}{link.pk}/release-hold/'
        admin = self.api_for(self.hq)
        self.assertEqual(admin.post(url).data['capacity_holds'], [])
        self.assertEqual(admin.post(url).status_code, 200)
        self.assertFalse(self.slots()['is_full'])
        self.assertIsNone(link.capacity_holds.get().converted_at)
        audit = LogEntry.objects.get(object_id=str(link.pk))
        self.assertEqual(audit.user, self.hq)
        self.assertIn('釋放代客訂課名額保留', audit.change_message)
        link.refresh_from_db()
        self.assertTrue(link.is_open)

    def test_opt_out_leaves_capacity_available(self):
        response = self.create_link(hold_capacity=False)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['capacity_holds'], [])
        self.assertFalse(self.slots()['is_full'])

    def test_retired_campus_resort_assignment_stops_counting_hold(self):
        link = self.take_hold()
        self.campus.resorts.remove(self.resort)
        self.assertFalse(self.slots()['is_full'])
        link.refresh_from_db()
        self.assertFalse(link.is_available)

    def test_tenant_setting_off_keeps_existing_hold_and_suppresses_new_ones(self):
        held = self.take_hold()
        module, _ = ModuleInfo.objects.get_or_create(module_sid='booking', defaults={'module_name': '預約'})
        ModuleSetting.objects.create(client=self.tenant, module=module, settings={'staff_booking_link_hold_enabled': False})
        listing = self.api_for(self.hq).get(self.list_url).data['data']
        self.assertFalse(listing['can_create_hold'])
        self.assertTrue(listing['can_release_hold'])
        self.assertFalse(self.take_hold(cart=self.cart_for(self.day + timedelta(days=1))).capacity_holds.exists())
        self.assertEqual(self.edit(user=self.hq, hold_capacity=True).data['capacity_holds'], [])
        self.assertEqual(held.capacity_holds.count(), 1)
        self.assertTrue(self.slots()['is_full'])

    def test_cross_tenant_link_and_hold_cannot_change_availability_or_be_released(self):
        held = self.take_hold()
        root = get_user_model().objects.create_superuser('hold-root')
        response = self.api_for(root).post(f'/api/admin/other/staff-booking-links/{held.pk}/release-hold/')
        self.assertEqual(response.status_code, 404)
        self.assertTrue(self.slots()['is_full'])
        held.capacity_holds.update(client=self.other_tenant)
        self.assertFalse(self.slots()['is_full'])
        response = APIClient().get(self.sessions_url.replace('/snowland/', '/other/'), {
            'template_id': self.template.pk, 'date': self.day.isoformat(), 'staff_link': str(held.token),
        })
        self.assertEqual(response.data, [])

    def test_closure_blocks_hold_and_checkout_without_consuming_existing_hold(self):
        link = self.take_hold()
        payload = self.use_link(link)
        BookingClosure.objects.create(
            client=self.tenant, resort=self.resort, date_from=self.day, date_to=self.day,
        )
        self.assertTrue(self.slots()['is_closed'])
        self.assertTrue(self.slots()['is_full'])
        response = self.create_link(hold_capacity=True)
        self.assertEqual((response.status_code, response.data['code']), (409, 'slot_closed'))
        response = self.api_for(self.member).post(self.checkout_url, payload, format='json')
        self.assertEqual((response.status_code, response.data['code']), (409, 'slot_closed'))
        self.assertIsNone(link.capacity_holds.get().released_at)

    def test_shared_classes_do_not_take_holds(self):
        self.template.shared_class_enabled = True
        self.template.save(update_fields=['shared_class_enabled'])
        response = self.create_link(hold_capacity=True)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['capacity_holds'], [])
        self.assertFalse(StaffLinkCapacityHold.objects.exists())


class StaffLinkCapacityHoldConcurrencyTests(StaffHoldFixture, TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_two_headquarters_users_compete_for_last_group(self):
        second = self.headquarters('second-hold-hq')
        start = Barrier(2)

        def create(user):
            try:
                start.wait(timeout=10)
                return self.create_link(user=user, hold_capacity=True).status_code
            finally:
                connections['default'].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(create, [self.hq, second])), [201, 409])
        self.assertEqual(StaffLinkCapacityHold.objects.count(), 1)
        self.assertEqual(StaffBookingLink.objects.exclude(pk=self.link.pk).count(), 1)
