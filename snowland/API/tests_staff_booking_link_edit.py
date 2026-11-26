from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting
from Coach.models import Coach
from Control.models import TenantStaffMembership
from Coursekit.models import CourseCategory, CoursePricing, CourseTemplate, CourseType, DiscountCode
from Resorts.models import Campus, EquipmentAssistanceTimeSlot, ResortFee, Resorts
from booking.models import ReservationGroup, StaffBookingLink
from booking.tests_policy_support import checkout_policy_acknowledgement


class StaffLinkFixture:
    def setUp(self):
        self.tenant = Client.objects.create(internal_code='snowland', name='測試學校')
        self.other_tenant = Client.objects.create(internal_code='other', name='另一所學校')
        self.campus = Campus.objects.create(client=self.tenant, code='a', name='甲校區')
        self.other_campus = Campus.objects.create(client=self.tenant, code='b', name='乙校區')
        self.resort = Resorts.objects.create(
            client=self.tenant, name='QAResort', display_name='測試雪場', auto_scheduling_enabled=False,
        )
        self.campus.resorts.add(self.resort)
        category = CourseCategory.objects.create(client=self.tenant, name='滑雪')
        self.kind = CourseType.objects.create(category=category, name='雙板')
        self.template = CourseTemplate.objects.create(course_type=self.kind, name='半天課', duration_hours=4)
        self.template.resorts.add(self.resort)
        self.pricing = CoursePricing.objects.create(
            resort=self.resort, base_price_off_peak=10000, peak_season_surcharge=0,
            additional_person_fee=0, max_capacity=6,
        )
        self.pricing.templates.add(self.template)
        self.author = self.coach('link-author', self.campus)
        self.member = get_user_model().objects.create_user('link-member')
        self.cart = [{
            'id': 'first-group', 'campusId': self.campus.pk, 'resort': self.resort.name,
            'resortName': self.resort.display_name, 'courseCategory': category.name,
            'coach': 'any', 'peopleCount': 1, 'abilityLevel': 'no_exp', 'language': 'zh',
            'equipment': False, 'equipmentOption': 'own_equipment', 'totalPrice': 10000,
            'courses': [{
                'date': str(timezone.localdate() + timedelta(days=30)),
                'courseTypeId': self.kind.pk, 'courseTemplateId': self.template.pk,
                'courseTemplateName': self.template.name, 'durationHours': 4,
                'timeSlotStart': '09:00', 'timeSlotEnd': '13:00', 'price': 10000,
            }],
        }]
        self.link = StaffBookingLink.objects.create(
            client=self.tenant, campus=self.campus, created_by=self.author, title='QA 代客訂課',
            expires_at=timezone.now() + timedelta(days=2), cart_snapshot=self.cart,
        )
        self.admin_url = f'/api/admin/snowland/staff-booking-links/{self.link.pk}/'
        self.public_url = f'/booking/snowland/api/staff-booking-link/{self.link.token}/'
        self.checkout_url = '/booking/snowland/api/create-reservation/'

    def api_for(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api

    def coach(self, username, campus):
        user = get_user_model().objects.create_user(username)
        membership = TenantStaffMembership.objects.create(client=self.tenant, user=user, is_coach=True)
        membership.campuses.add(campus)
        coach = Coach.objects.create(client=self.tenant, user=user, name=username)
        coach.campuses.add(campus)
        return user

    def manager(self, username, campus):
        user = get_user_model().objects.create_user(username)
        membership = TenantStaffMembership.objects.create(
            client=self.tenant, user=user, is_manager=True, role='campus_manager',
            all_campuses=False, admin_permissions=['booking_links'],
        )
        membership.campuses.add(campus)
        return user

    def load_tab(self):
        response = APIClient().get(self.public_url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('no-store', response.headers['Cache-Control'])
        return {
            'cart': response.data['cart_snapshot'],
            'staff_link': response.data['token'],
            'staff_link_version': response.data['snapshot_version'],
            **checkout_policy_acknowledgement(),
            'contact': {
                'name': '測試會員', 'phone': '0900000000', 'messengerType': 'line', 'messengerId': 'qa-link',
            },
        }

    def edit(self, *, cart=None, version=0, user=None, **extra):
        return self.api_for(user or self.author).patch(self.admin_url, {
            'cart_snapshot': self.cart if cart is None else cart,
            'snapshot_version': version, **extra,
        }, format='json')


class StaffBookingLinkEditTests(StaffLinkFixture, TestCase):
    def test_creator_and_campus_manager_update_the_same_link(self):
        StaffBookingLink.objects.filter(pk=self.link.pk).update(
            cart_snapshot=[{**self.cart[0], 'internal_note': '舊版欄位'}],
        )
        existing = self.api_for(self.author).get(self.admin_url)
        self.assertTrue(existing.data['can_edit'])
        self.assertEqual(existing.data['cart_snapshot'], self.cart)
        created_token = str(self.link.token)
        new_cart = [{**self.cart[0], 'courses': [
            {**self.cart[0]['courses'][0], 'date': str(timezone.localdate() + timedelta(days=32))}
        ]}]
        first = self.edit(cart=new_cart)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['snapshot_version'], 1)
        self.assertEqual(first.data['token'], created_token)
        changed = self.load_tab()
        self.assertEqual(changed['cart'][0]['courses'][0]['date'], new_cart[0]['courses'][0]['date'])
        second = self.edit(cart=new_cart, user=self.manager('link-manager', self.campus), version=1)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['snapshot_version'], 1)
        self.assertEqual(second.data['token'], created_token)
        self.assertEqual(StaffBookingLink.objects.count(), 1)
        self.assertEqual(self.edit(version=0).status_code, 409)

    def test_other_coaches_campus_managers_and_tenants_cannot_preview_or_edit(self):
        outside = get_user_model().objects.create_user('other-manager')
        TenantStaffMembership.objects.create(client=self.other_tenant, user=outside, is_manager=True, role='hq_admin')
        for user, expected in (
            (self.coach('other-coach', self.campus), 404),
            (self.coach('other-campus-coach', self.other_campus), 404),
            (self.manager('other-campus-manager', self.other_campus), 404),
            (outside, 403),
        ):
            with self.subTest(user=user.username):
                self.assertEqual(self.edit(user=user).status_code, expected)
                self.assertEqual(self.api_for(user).post(self.admin_url + 'preview/', {
                    'cart_snapshot': self.cart,
                }, format='json').status_code, expected)
        self.assertEqual(self.edit(campus=self.other_campus.pk).status_code, 403)
        self.assertEqual(APIClient().get(self.public_url.replace('/snowland/', '/other/')).status_code, 404)

    def test_unavailable_link_and_setting_disable_edit(self):
        api = self.api_for(self.author)
        for field, value in (
            ('used_at', timezone.now()), ('expires_at', timezone.now()), ('is_active', False),
        ):
            with self.subTest(field=field):
                StaffBookingLink.objects.filter(pk=self.link.pk).update(**{field: value})
                self.assertFalse(api.get(self.admin_url).data['can_edit'])
                self.assertEqual(self.edit().status_code, 400)
                self.assertEqual(api.post(self.admin_url + 'preview/', {'cart_snapshot': self.cart}, format='json').status_code, 400)
                StaffBookingLink.objects.filter(pk=self.link.pk).update(**{field: getattr(self.link, field)})
        self.assertEqual(self.edit(expires_at=timezone.now().isoformat()).status_code, 400)
        module, _ = ModuleInfo.objects.get_or_create(module_sid='booking', defaults={'module_name': '預約'})
        ModuleSetting.objects.create(client=self.tenant, module=module, settings={'staff_booking_link_edit_enabled': False})
        self.assertFalse(api.get(self.admin_url).data['can_edit'])
        self.assertEqual(self.edit().status_code, 403)
        self.assertEqual(APIClient().get(self.public_url).status_code, 200)

    def test_preview_and_save_use_live_fees_and_discounts(self):
        ResortFee.objects.create(resort=self.resort, fee_type='equipment_1to3', price=1200)
        slot = EquipmentAssistanceTimeSlot.objects.create(resort=self.resort, label='裝備協助')
        early_bird = DiscountCode.objects.create(
            client=self.tenant, code='QA-EB', discount_type=DiscountCode.DISCOUNT_TYPE_PERCENT,
            discount_value=10, apply_scope=DiscountCode.APPLY_SCOPE_SKI, is_auto_apply=True,
            end_at=timezone.now() + timedelta(days=1),
        )
        cart = [{**self.cart[0], 'equipment': True, 'equipmentOption': 'extra_time_help',
                 'equipmentAssistanceTimeSlotId': slot.pk, 'totalPrice': 1}]
        api = self.api_for(self.author)
        preview = api.post(self.admin_url + 'preview/', {'cart_snapshot': cart}, format='json')
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data, {
            'previous_subtotal': 10000, 'subtotal': 11200, 'subtotal_difference': 1200,
            'discount_total': 1000, 'total': 10200, 'previous_total': None, 'total_difference': None,
        })
        self.assertEqual(self.load_tab()['staff_link_version'], 0)
        edited = self.edit(cart=cart, expected_quote={'subtotal': 11200, 'total': 10200})
        self.assertEqual(edited.status_code, 200, edited.data)
        self.assertEqual(edited.data['quoted_total'], 10200)

        early_bird.end_at = timezone.now() - timedelta(seconds=1)
        early_bird.save(update_fields=['end_at'])
        self.pricing.base_price_off_peak = 12000
        self.pricing.save(update_fields=['base_price_off_peak'])
        self.assertEqual(self.edit(cart=cart, version=1, expected_quote={
            'subtotal': 11200, 'total': 10200,
        }).status_code, 409)
        current = self.edit(cart=cart, version=1)
        self.assertEqual(current.status_code, 200, current.data)
        self.assertEqual(current.data['price_preview'], {
            'previous_subtotal': 11200, 'subtotal': 13200, 'subtotal_difference': 2000,
            'discount_total': 0, 'total': 13200, 'previous_total': 10200, 'total_difference': 3000,
        })
        shared = APIClient().get(self.public_url)
        self.assertEqual(shared.data['quoted_total'], 13200)
        group = shared.data['cart_snapshot'][0]
        self.assertEqual((group['courses'][0]['price'], group['equipmentRentalFee'], group['totalPrice']),
                         (12000, 1200, 13200))
        checkout = self.api_for(self.member).post(self.checkout_url, self.load_tab(), format='json')
        self.assertEqual(checkout.status_code, 200, checkout.data)
        self.assertEqual(ReservationGroup.objects.get().reservations.get().payment_amount, 13200)

    def test_metadata_and_unchanged_snapshot_keep_customer_tab_current(self):
        saved = self.edit()
        self.assertEqual(saved.status_code, 200, saved.data)
        old_tab = self.load_tab()
        admin = self.api_for(self.author)
        renamed = admin.patch(self.admin_url, {'title': '更新後的標題'}, format='json')
        self.assertEqual(renamed.status_code, 200, renamed.data)
        self.assertEqual(renamed.data['title'], '更新後的標題')
        self.assertEqual(renamed.data['snapshot_version'], old_tab['staff_link_version'])
        same_cart = self.edit(cart=old_tab['cart'], version=0)
        self.assertEqual(same_cart.status_code, 200, same_cart.data)
        self.assertEqual(same_cart.data['snapshot_version'], old_tab['staff_link_version'])

        checkout = self.api_for(self.member).post(self.checkout_url, old_tab, format='json')
        self.assertEqual(checkout.status_code, 200, checkout.data)
        self.assertEqual(ReservationGroup.objects.count(), 1)

    def test_stale_snapshot_requires_reload_and_two_tabs_can_only_use_link_once(self):
        old_tab = self.load_tab()
        new_cart = [{**self.cart[0], 'courses': [
            {**self.cart[0]['courses'][0], 'date': str(timezone.localdate() + timedelta(days=32))},
        ]}]
        missing_version = self.api_for(self.author).patch(self.admin_url, {'cart_snapshot': new_cart}, format='json')
        self.assertEqual(missing_version.status_code, 409)
        saved = self.edit(cart=new_cart, version=old_tab['staff_link_version'])
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data['snapshot_version'], old_tab['staff_link_version'] + 1)
        first_tab, second_tab = self.load_tab(), self.load_tab()
        member = self.api_for(self.member)
        stale = member.post(self.checkout_url, old_tab, format='json')
        self.assertEqual(stale.status_code, 409, stale.data)
        self.assertEqual(stale.data['error'], 'staff_link_updated')
        self.assertEqual(stale.data['msg'], '內容已更新，請重新確認金額')
        self.assertFalse(ReservationGroup.objects.exists())
        self.link.refresh_from_db()
        self.assertIsNone(self.link.used_at)
        first = member.post(self.checkout_url, first_tab, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        duplicate = self.api_for(self.member).post(self.checkout_url, second_tab, format='json')
        self.assertEqual(duplicate.status_code, 400, duplicate.data)
        self.assertEqual(ReservationGroup.objects.count(), 1)
        self.assertEqual(self.edit(version=1).status_code, 400)


class StaffBookingLinkConcurrencyTests(StaffLinkFixture, TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_two_concurrent_submissions_consume_the_link_once(self):
        tabs = [self.load_tab(), self.load_tab()]
        start = Barrier(2)

        def submit(payload):
            try:
                api = self.api_for(self.member)
                start.wait(timeout=10)
                return api.post(self.checkout_url, payload, format='json').status_code
            finally:
                connections['default'].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(submit, tabs)), [200, 400])
        self.assertEqual(ReservationGroup.objects.count(), 1)
