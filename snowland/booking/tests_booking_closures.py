from copy import deepcopy
from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting
from Control.models import TenantStaffMembership
from Coursekit.models import CourseCategory, CourseSession, CourseTemplate, CourseType
from Resorts.models import Campus, Resorts
from . import tests_capacity_recheck, tests_shared_course_booking
from .closures import active_booking_closures, matching_booking_closure
from .models import Booking, BookingClosure, Payment, Reservation, ReservationGroup, SharedCourseClass


class BookingClosureTests(TestCase):
    def setUp(self):
        tests_capacity_recheck.CapacityRecheckTests.setUp(self)
        self.admin_url = '/api/admin/snowland/booking-closures/'
        self.admin = APIClient()
        self.hq = User.objects.create_user('closure-hq')
        TenantStaffMembership.objects.create(user=self.hq, client=self.client_record, role='hq_admin', is_manager=True)
        self.admin.force_authenticate(self.hq)
        self.other = Client.objects.create(name='Other', internal_code='closure-other')
        self.other_resort = Resorts.objects.create(client=self.client_record, name='elsewhere', display_name='另一雪場')
        self.foreign_resort = Resorts.objects.create(client=self.other, name=self.resort.name, display_name='其他租戶雪場')
        category = CourseCategory.objects.create(client=self.other, name='其他租戶')
        kind = CourseType.objects.create(category=category, name='私人課')
        self.foreign_template = CourseTemplate.objects.create(course_type=kind, name='外租戶模板', duration_hours=4)

    def rule(self, **fields):
        return BookingClosure.objects.create(**{
            'client': self.client_record, 'resort': self.resort, 'date_from': self.day,
            'date_to': self.day, 'reason': '內部原因', **fields,
        })

    def create_rule(self, **fields):
        return self.admin.post(self.admin_url, {
            'resort': self.resort.pk, 'date_from': str(self.day), 'date_to': str(self.day), **fields,
        }, format='json')

    def sessions(self, **params):
        return tests_capacity_recheck.CapacityRecheckTests.sessions(
            self, **{'resort': self.resort.name, **params},
        ).data

    def dates(self, *, template=None, resort=None):
        result = self.api.get(
            f'/booking/snowland/api/course-templates/{(template or self.private_template).pk}/available-dates/',
            {'month': self.day.strftime('%Y-%m'), 'resort': (resort or self.resort).name},
        )
        self.assertEqual(result.status_code, 200, result.data)
        return result.data['available_dates']

    def set_flags(self, **flags):
        return ModuleSetting.objects.create(
            client=self.client_record,
            module=ModuleInfo.objects.create(module_sid='booking', module_name='訂課'), settings=flags,
        )

    def test_match_scope_intersection_dates_and_time_overlap(self):
        trial = {
            'day': self.day, 'resort_id': self.resort.pk, 'template_id': self.private_template.pk,
            'start_time': time(9), 'end_time': time(13),
        }
        last = self.day + timedelta(days=2)
        rule = self.rule(course_template=self.private_template, date_to=last, start_time=time(12), end_time=time(14))
        for changes, match in [
            ({}, True),
            ({'day': last, 'start_time': time(12), 'end_time': time(14)}, True),
            ({'day': self.day - timedelta(days=1)}, False),
            ({'day': last + timedelta(days=1)}, False),
            ({'resort_id': self.other_resort.pk}, False),
            ({'template_id': self.per_person_template.pk}, False),
            ({'start_time': time(10), 'end_time': time(12)}, False),
            ({'start_time': time(14), 'end_time': time(15)}, False),
            ({'start_time': None, 'end_time': None}, False),
        ]:
            with self.subTest(changes=changes):
                self.assertEqual(bool(matching_booking_closure([rule], **{**trial, **changes})), match)

        resort_only = self.rule()
        template_only = self.rule(resort=None, course_template=self.private_template)
        self.assertEqual(matching_booking_closure(
            [resort_only], **{**trial, 'template_id': self.per_person_template.pk},
        ), resort_only)
        self.assertEqual(matching_booking_closure(
            [template_only], **{**trial, 'resort_id': self.other_resort.pk, 'start_time': None, 'end_time': None},
        ), template_only)
        self.assertEqual(active_booking_closures(self.other, self.day, self.day), ())

    def test_display_all_day_and_session_closures_respect_scope_and_hide_internal_reason(self):
        period = self.rule(course_template=self.private_template, start_time=time(12), end_time=time(14))
        result = self.sessions()[0]
        self.assertTrue(result['is_closed'])
        self.assertFalse(result['is_full'])
        self.assertIn('已暫停接單', result['closed_reason_zh'])
        self.assertNotIn(period.reason, str(result))
        self.assertIn(str(self.day), self.dates())
        self.assertFalse(self.sessions(resort=self.other_resort.name)[0]['is_closed'])
        self.rule(course_template=self.private_template)
        self.assertNotIn(str(self.day), self.dates())
        self.assertIn(str(self.day), self.dates(template=self.per_person_template))
        self.assertIn(str(self.day), self.dates(resort=self.other_resort))

    def test_both_checkout_routes_reject_later_mixed_template_and_write_nothing(self):
        self.set_flags(booking_capacity_recheck_enabled=False)
        body = deepcopy(self.payload)
        second = body['cart'][0]['courses'][1]
        second['courseTemplateId'] = self.per_person_template.pk
        day = date.fromisoformat(second['date'])
        self.rule(course_template=self.per_person_template, date_from=day, date_to=day)
        for url in (self.submit_url, self.url):
            response = self.api.post(url, body, format='json')
            self.assertEqual(response.status_code, 409, response.data)
            self.assertEqual(response.data['code'], 'slot_closed')
            conflict, = response.data['conflicts']
            self.assertEqual((conflict['code'], conflict['template_id'], conflict['date']),
                             ('closed', self.per_person_template.pk, str(day)))
            self.assertNotIn('內部原因', str(response.data))
            self.assertEqual(tests_capacity_recheck.CapacityRecheckTests.counts(self), (0,) * 6)

    def test_legacy_checkout_observes_closures_before_creating_order(self):
        self.foreign_resort.name = 'foreign'
        self.foreign_resort.save(update_fields=['name'])
        self.rule()
        response = self.api.post('/booking/api/create_reservation/', {
            'tunnel': 'super_schedule',
            'courses': [{
                'resort': self.resort.name, 'courseType': self.private_template.course_type_id,
                'booking': [{'timeSlot': self.private_template.pk, 'date': str(self.day)}],
            }],
        }, format='json')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['code'], 'slot_closed')
        self.assertFalse(ReservationGroup.objects.exists())

    def test_disabled_rules_can_be_managed_and_deletion_restores_booking(self):
        setting = self.set_flags(booking_closures_enabled=False)
        result = self.create_rule()
        self.assertEqual(result.status_code, 201, result.data)
        rule_id = result.data['data']['id']
        self.assertFalse(self.admin.get(self.admin_url + 'options/').data['data']['enabled'])
        self.assertEqual(self.admin.get(self.admin_url).data['data']['total'], 1)
        self.assertIn(str(self.day), self.dates())
        self.assertFalse(self.sessions()[0]['is_closed'])
        result = self.api.post(self.submit_url, self.payload, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        setting.settings = {'booking_closures_enabled': True}
        setting.save(update_fields=['settings'])
        self.assertTrue(self.sessions()[0]['is_closed'])
        self.assertEqual(self.admin.delete(f'{self.admin_url}{rule_id}/').status_code, 204)
        archived = BookingClosure.all_objects.get(pk=rule_id)
        self.assertEqual((archived.is_deleted, archived.deleted_by_id), (True, self.hq.pk))
        self.assertIsNotNone(archived.deleted_at)
        self.assertFalse(self.sessions()[0]['is_closed'])
        self.assertIn(str(self.day), self.dates())
        self.assertEqual(self.admin.get(self.admin_url).data['data']['total'], 0)
        result = self.api.post(self.submit_url, self.payload, format='json')
        self.assertEqual(result.status_code, 200, result.data)

    def test_existing_orders_can_still_view_payment_pay_and_receive_signed_callback(self):
        groups = []
        for _ in range(2):
            response = self.api.post(self.submit_url, self.payload, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            groups.append(ReservationGroup.objects.get(pk=response.data['reservation_group_ids'][0]))
        self.rule()
        self.assertTrue(self.sessions()[0]['is_closed'])
        bank_order, card_order = groups
        self.assertEqual(tests_capacity_recheck.CapacityRecheckTests.payment_info(self, bank_order).status_code, 200)
        self.assertEqual(tests_capacity_recheck.CapacityRecheckTests.process_payment(self, bank_order, 'bank_transfer').status_code, 200)
        self.assertEqual(bank_order.payments.get().status, 'pending')
        card_order.newebpay_override = True
        card_order.save(update_fields=['newebpay_override'])
        with patch('booking.newebpay_settings.gateway_settings', return_value=self.credentials), patch(
            'booking.api_views.neweb_pay_request', return_value='<form></form>',
        ):
            result = tests_capacity_recheck.CapacityRecheckTests.process_payment(self, card_order, 'newebpay')
        self.assertEqual(result.status_code, 200, result.data)
        card = card_order.payments.get()
        signed = tests_capacity_recheck.CapacityRecheckTests.notify(
            self, card_order, amount=sum(row.payment_amount for row in card_order.reservations.all()),
        )
        self.assertEqual(signed.status_code, 200, signed.content)
        card.refresh_from_db()
        self.assertEqual(card.status, 'paid')
        self.assertNotIn('capacity_conflict', card.DataJSON)

    def test_admin_validation_warning_and_filters(self):
        for fields in (
            {'resort': None}, {'resort': self.foreign_resort.pk}, {'course_template': self.foreign_template.pk},
            {'date_to': str(self.day - timedelta(days=1))}, {'date_to': str(self.day + timedelta(days=366))},
            {'start_time': '10:00'}, {'start_time': '11:00', 'end_time': '10:00'},
        ):
            with self.subTest(fields=fields):
                self.assertEqual(self.create_rule(**fields).status_code, 400)
        self.assertFalse(BookingClosure.objects.exists())
        first = self.create_rule(date_to=str(self.day + timedelta(days=3)))
        self.assertEqual(first.status_code, 201, first.data)
        duplicate = self.create_rule(course_template=self.private_template.pk, start_time='10:00', end_time='12:00')
        self.assertEqual(duplicate.status_code, 201, duplicate.data)
        self.assertIn('涵蓋', duplicate.data['warning'])
        for filters, expected in [
            ({'date': str(self.day)}, 2),
            ({'date_from': str(self.day + timedelta(days=2))}, 1),
            ({'date_to': str(self.day - timedelta(days=1))}, 0),
            ({'resort': self.other_resort.pk}, 0),
            ({'course_template': self.private_template.pk}, 1),
        ]:
            self.assertEqual(self.admin.get(self.admin_url, filters).data['data']['total'], expected)
        options = self.admin.get(self.admin_url + 'options/').data['data']
        self.assertIn(self.session.pk, [row['id'] for template in options['templates'] for row in template['sessions']])

    def test_admin_permissions_and_tenant_isolation(self):
        local = self.rule()
        foreign = self.rule(client=self.other, resort=self.foreign_resort)
        self.assertEqual(self.admin.get(self.admin_url).data['data']['total'], 1)
        self.assertEqual(self.admin.delete(f'{self.admin_url}{foreign.pk}/').status_code, 404)
        self.assertTrue(BookingClosure.objects.filter(pk=foreign.pk).exists())
        self.admin.force_authenticate(self.user)
        self.assertEqual(self.admin.get(self.admin_url).status_code, 403)
        self.assertEqual(self.create_rule().status_code, 403)
        # Scope grants are checked separately within the same tenant.
        self.private_template.resorts.add(self.resort)
        employee = User.objects.create_user('closure-staff')
        staff = TenantStaffMembership.objects.create(
            user=employee, client=self.client_record, role='campus_manager', is_manager=True,
            admin_permissions=['course_types'],
        )
        staff.campuses.add(self.campus)
        self.admin.force_authenticate(employee)
        self.assertEqual(self.create_rule().status_code, 403)
        self.assertEqual(self.create_rule(resort=None, course_template=self.private_template.pk).status_code, 201)
        self.assertEqual(self.admin.delete(f'{self.admin_url}{local.pk}/').status_code, 404)
        staff.admin_permissions = ['resorts']
        staff.save(update_fields=['admin_permissions'])
        self.assertEqual(self.create_rule().status_code, 201)
        self.assertEqual(self.create_rule(course_template=self.private_template.pk).status_code, 403)
        self.assertEqual(self.create_rule(resort=self.other_resort.pk).status_code, 403)
        staff.admin_permissions = ['resorts', 'course_types']
        staff.save(update_fields=['admin_permissions'])
        self.assertEqual(self.create_rule(course_template=self.private_template.pk).status_code, 201)
        second_campus = Campus.objects.create(client=self.client_record, name='其他校區', code='second')
        second_campus.resorts.add(self.other_resort)
        staff.campuses.add(second_campus)
        self.private_template.resorts.add(self.other_resort)
        self.assertEqual(self.create_rule(resort=None, course_template=self.private_template.pk).status_code, 403)
        self.assertEqual(self.create_rule(course_template=self.private_template.pk).status_code, 201)
        second_campus.resorts.add(self.resort)
        self.assertEqual(self.create_rule().status_code, 403)
        self.assertEqual(self.create_rule(resort=None, course_template=self.private_template.pk).status_code, 403)
        self.assertEqual(self.admin.get(self.admin_url).data['data']['total'], 0)
        self.admin.force_authenticate(self.hq)
        self.assertEqual(self.create_rule().status_code, 201)


@override_settings(SHARED_CLASS_FEATURE_ENABLED=True)
class SharedBookingClosureTests(TestCase):
    def setUp(self):
        tests_shared_course_booking.SharedCourseBookingTests.setUp(self)

    def test_group_class_stops_at_display_and_checkout(self):
        self.template.shared_class_fixed_dates = True
        self.template.save(update_fields=['shared_class_fixed_dates'])
        SharedCourseClass.objects.create(
            client=self.tenant, campus=self.campus, resort=self.resort, template=self.template,
            date=self.date, start_time=time(9), end_time=time(13), ability_level='level1',
            minimum_students=3, max_capacity=6, opening_mode='school',
        )
        closure = BookingClosure.objects.create(
            client=self.tenant, resort=self.resort, date_from=self.date, date_to=self.date,
            start_time=time(11), end_time=time(14),
        )
        lookup = {'campus_id': self.campus.pk, 'resort': self.resort.name, 'ability_level': 'level1'}
        sessions = self.api.get('/booking/snowland/api/course-sessions/', {
            'template_id': self.template.pk, 'date': self.date, **lookup,
        })
        self.assertTrue(sessions.data[0]['is_closed'])
        self.assertFalse(sessions.data[0]['is_full'])
        payload = tests_shared_course_booking.SharedCourseBookingTests.payload(self)
        for url in ('create-reservation', 'super-schedule'):
            response = self.api.post(f'/booking/snowland/api/{url}/', payload, format='json')
            self.assertEqual(response.status_code, 409, response.data)
            self.assertEqual(response.data['code'], 'slot_closed')
        self.assertFalse(ReservationGroup.objects.exists())
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(Payment.objects.exists())
        closure.start_time = closure.end_time = None
        closure.save(update_fields=['start_time', 'end_time'])
        dates = self.api.get(f'/booking/snowland/api/course-templates/{self.template.pk}/available-dates/', {
            **lookup, 'month': self.date[:7],
        })
        self.assertNotIn(self.date, dates.data['available_dates'])
        self.assertNotIn(self.date, dates.data['shared_class_dates'])
