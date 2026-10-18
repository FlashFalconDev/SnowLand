from datetime import timedelta

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_campus_scope as fixtures
from booking.models import Booking, MemberDetail, Reservation, ReservationGroup


class AssistantDocumentTests(TestCase):
    def setUp(self):
        fixtures.CampusScopeApiTests.setUp(self)
        self.profile.role = 'assistant'
        self.profile.admin_permissions = None
        self.profile.save()
        self.manager.refresh_from_db()
        self.api = APIClient()
        self.api.force_authenticate(self.manager)
        group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a)
        reservation = Reservation.objects.create(group=group)
        Booking.objects.create(reservation=reservation, date=timezone.localdate()+timedelta(days=3), start_time='09:00', end_time='12:00')
        self.member = MemberDetail.objects.create(reservation=reservation, insurance_data={'full_name':'QA 學員'}, age_range='adult')
        self.url = '/api/admin/snowland/insurance-records/'

    def test_assistant_can_view_but_not_complete_or_patch_documents(self):
        listed = self.api.get(self.url)
        self.assertEqual(listed.status_code, 200)
        detail = self.api.get(f'{self.url}{self.member.pk}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['insurance_data']['full_name'], 'QA 學員')
        for field in ('insurance', 'waiver'):
            result = self.api.post(f'{self.url}{self.member.pk}/complete/', {'field':field}, format='json')
            self.assertEqual(result.status_code, 403, result.data)
        result = self.api.patch(f'{self.url}{self.member.pk}/', {'age_range':'child'}, format='json')
        self.assertEqual(result.status_code, 403, result.data)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.insurance_completed_at)
        self.assertIsNone(self.member.waiver_completed_at)
        self.assertEqual(self.member.age_range, 'adult')
        self.assertFalse(listed.data['data']['list'][0]['can_mark_complete'])

    def test_headquarters_can_mark_status_without_fabricating_signed_waiver(self):
        api = APIClient()
        api.force_authenticate(self.superuser)
        self.assertTrue(api.get(self.url).data['data']['list'][0]['can_mark_complete'])
        for field in ('insurance', 'waiver'):
            result = api.post(f'{self.url}{self.member.pk}/complete/', {'field':field}, format='json')
            self.assertEqual(result.status_code, 200, result.data)
        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.insurance_completed_at)
        self.assertIsNotNone(self.member.waiver_completed_at)
        self.assertFalse(self.member.waiver_signature)
        self.assertFalse(self.member.waiver_document_snapshot)

    def test_document_mutations_require_csrf_even_for_headquarters(self):
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(self.superuser)
        url = f'{self.url}{self.member.pk}/complete/'
        denied = api.post(url, {'field':'insurance'}, format='json')
        self.assertEqual(denied.status_code, 403, denied.data)
        api.get(self.url)
        allowed = api.post(url, {'field':'insurance'}, format='json', HTTP_X_CSRFTOKEN=api.cookies['csrftoken'].value)
        self.assertEqual(allowed.status_code, 200, allowed.data)

    def test_member_email_is_detail_only_and_never_substitutes_order_payer(self):
        group = self.member.reservation.group
        group.user = self.superuser
        group.save(update_fields=['user'])
        detail_url = f'{self.url}{self.member.pk}/'
        self.assertEqual(self.api.get(detail_url).data['member_email'], '')
        user = User.objects.create_user('qa-form-owner', email='qa-learner@example.test')
        self.member.user = user
        self.member.save(update_fields=['user'])
        self.assertEqual(self.api.get(detail_url).data['member_email'], user.email)
        self.assertNotIn('member_email', self.api.get(self.url).data['data']['list'][0])
