from booking.tests_policy_support import checkout_policy_acknowledgement
from datetime import timedelta
from copy import deepcopy

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Coursekit.models import CoursePricing
from booking.models import ReservationGroup
from booking import tests_participants as fixtures


class PhotographyCheckoutTests(TestCase):
    def setUp(self):
        fixtures.MemberEnrollmentTests.setUp(self)
        category = self.template.course_type.category
        category.service_type = 'photo'
        category.name = '自訂影像方案'
        category.save()
        self.template.billing_mode = 'private'
        self.template.save()
        pricing = CoursePricing.objects.get(templates=self.template)
        pricing.base_price_off_peak = 15123
        pricing.save()

    def test_member_photo_checkout_admin_payment_and_rebook_keep_type_price_and_owner(self):
        date = (timezone.localdate() + timedelta(days=20)).isoformat()
        payload = {
            **checkout_policy_acknowledgement(),
            'contact': {'name': 'QA影像客人', 'email': self.owner.email, 'phone': '0900000000',
                        'messengerType': 'LINE', 'messengerId': 'qa-only', 'referralSource': 'Instagram'},
            'cart': [{'serviceType': 'photo', 'courseCategory': '自訂影像方案',
                      'coach': 'any', 'peopleCount': 1, 'abilityLevel': 'no_exp',
                      'equipment': False, 'equipmentOption': None, 'language': 'zh',
                      'resort': self.resort.name, 'campusId': self.campus.pk, 'totalPrice': 15123,
                      'courses': [{'date': date, 'courseTypeId': self.template.course_type_id,
                                   'courseTemplateId': self.template.pk, 'courseTemplateName': self.template.name,
                                   'timeSlotStart': '09:00', 'timeSlotEnd': '13:00', 'price': 15123}]}],
        }
        stale = deepcopy(payload)
        stale['cart'][0]['totalPrice'] = stale['cart'][0]['courses'][0]['price'] = 1
        rejected = self.api.post('/booking/snowland/api/create-reservation/', stale, format='json')
        self.assertEqual(rejected.status_code, 400)
        self.assertFalse(ReservationGroup.objects.exists())
        response = self.api.post('/booking/snowland/api/create-reservation/', payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        group = ReservationGroup.objects.get(pk=response.data['reservation_group_ids'][0])
        reservation = group.reservations.get()
        self.assertEqual(group.user, self.owner)
        self.assertEqual(reservation.course_fee, 15123)
        self.assertEqual(reservation.coach_fee, 0)
        self.assertFalse(reservation.equipment)
        self.assertEqual(group.payments.get().status, 'unpaid')
        self.assertEqual(str(reservation.bookings.get().date), date)

        hq = APIClient()
        hq.force_authenticate(User.objects.create_superuser('photo-checkout-hq', password='qa-only'))
        saved = hq.patch(f'/api/admin/snowland/orders/{group.pk}/',
                         {'action': 'save', 'payment_status': 'paid'}, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        center = self.api.get('/booking/snowland/api/member-center/')
        order = center.data['orders'][0]
        self.assertEqual(order['payment_status'], 'paid')
        self.assertEqual(order['total_amount'], 15123)
        self.assertEqual(order['reservations'][0]['service_type'], 'photo')
        copied = self.api.post('/booking/snowland/api/member-center/',
                               {'quick_rebook_group_id': group.pk}, format='json')
        self.assertEqual(copied.status_code, 200)
        self.assertEqual(copied.data['cart'][0]['serviceType'], 'photo')
        self.assertIsNone(copied.data['cart'][0]['totalPrice'])
        self.api.force_authenticate(User.objects.create_user('photo-stranger'))
        self.assertEqual(self.api.get('/booking/snowland/api/member-center/').data['orders'], [])
        self.assertEqual(self.api.post('/booking/snowland/api/member-center/',
                                     {'quick_rebook_group_id': group.pk}, format='json').status_code, 404)
