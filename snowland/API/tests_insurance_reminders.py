import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_campus_scope as fixtures
from booking.models import MemberDetail, NotificationDelivery, Reservation, ReservationGroup


class InsuranceReminderTests(TestCase):
    def setUp(self):
        fixtures.CampusScopeApiTests.setUp(self)
        self.owner = User.objects.create_user('insurance-owner', email='owner@example.test')
        self.group = ReservationGroup.objects.create(client=self.tenant, campus=self.campus_a, user=self.owner)
        self.member = MemberDetail.objects.create(reservation=Reservation.objects.create(group=self.group))
        self.api = APIClient(); self.api.force_authenticate(self.superuser)
        self.url = f'/api/admin/snowland/insurance-records/{self.member.pk}/reminder/'
        self.payload = {'field':'insurance','recipient_email':self.owner.email,'request_key':str(uuid.uuid4())}

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_preview_has_no_side_effect_and_send_is_idempotent(self, send):
        preview = self.api.get(self.url, {'field':'insurance'})
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['data']['recipient_email'], self.owner.email)
        send.assert_not_called(); self.assertEqual(NotificationDelivery.objects.count(), 0)
        first = self.api.post(self.url, self.payload, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        repeat = self.api.post(self.url, self.payload, format='json')
        self.assertEqual(repeat.status_code, 200, repeat.data)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(NotificationDelivery.objects.filter(template__channel='email',recipient=self.owner.email).count(), 1)
        self.assertEqual(NotificationDelivery.objects.filter(payload__has_key='in_app_mirror_of').count(), 1)
        self.member.refresh_from_db(); self.assertIsNone(self.member.insurance_completed_at)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_assistant_can_remind_but_cannot_mark_complete(self, send):
        self.profile.role='assistant'; self.profile.admin_permissions=None; self.profile.save()
        self.api.force_authenticate(User.objects.get(pk=self.manager.pk))
        self.assertEqual(self.api.post(self.url, self.payload, format='json').status_code, 200)
        self.assertEqual(self.api.post(self.url.replace('reminder/','complete/'), {'field':'insurance'}, format='json').status_code, 403)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_completed_cancelled_changed_recipient_and_extra_fields_do_not_send(self, send):
        for data in ({**self.payload,'recipient_email':'stranger@example.test'}, {**self.payload,'message':'injected'},
                     {**self.payload,'field':'other'}, {k:v for k,v in self.payload.items() if k!='request_key'}):
            self.assertIn(self.api.post(self.url,data,format='json').status_code,[400,409])
        self.member.insurance_completed_at=timezone.now(); self.member.save()
        self.assertEqual(self.api.post(self.url,self.payload,format='json').status_code,409)
        self.member.insurance_completed_at=None; self.member.save()
        self.member.reservation.status='cancelled'; self.member.reservation.save()
        self.assertEqual(self.api.post(self.url,self.payload,format='json').status_code,409)
        send.assert_not_called()

    def test_scoped_record_and_csrf_are_enforced(self):
        self.assertEqual(self.api.get(self.url, {'field':'insurance'},HTTP_X_CAMPUS_ID=str(self.campus_b.pk)).status_code,404)
        api=APIClient(enforce_csrf_checks=True); api.force_login(self.superuser)
        self.assertEqual(api.post(self.url,self.payload,format='json').status_code,403)

    def test_guardian_is_preferred_to_order_owner_without_unrelated_email_claiming(self):
        parent=User.objects.create_user('insurance-parent', email='parent@example.test')
        self.member.guardian=parent; self.member.save()
        response=self.api.get(self.url, {'field':'waiver'})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['data']['recipient_email'],parent.email)
        self.assertNotIn('id_number',response.data['data'])

    def test_missing_address_returns_readable_error(self):
        self.group.user=None; self.group.save()
        response=self.api.get(self.url, {'field':'insurance'})
        self.assertEqual(response.status_code,400,response.data)

    @patch('booking.scheduler.send_gmail', return_value='ok')
    def test_insurance_only_role_does_not_need_or_gain_order_management(self, send):
        self.profile.role='insurance'; self.profile.admin_permissions=None; self.profile.save()
        self.api.force_authenticate(User.objects.get(pk=self.manager.pk))
        self.assertEqual(self.api.get(self.url,{'field':'insurance'}).status_code,200)
        self.assertEqual(self.api.post(self.url,self.payload,format='json').status_code,200)
        self.assertEqual(self.api.get('/api/admin/snowland/orders/').status_code,403)

    @patch('booking.scheduler.send_gmail', side_effect=RuntimeError('private server secret'))
    def test_transport_failure_is_recorded_not_retried_or_reported_as_success(self, send):
        first=self.api.post(self.url,self.payload,format='json')
        self.assertEqual(first.status_code,502,first.data)
        self.assertNotIn('private server secret',str(first.data))
        self.assertEqual(self.api.post(self.url,self.payload,format='json').status_code,502)
        self.assertEqual(send.call_count,1)
