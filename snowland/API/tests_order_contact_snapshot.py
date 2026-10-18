from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_operations
from API.admin_serializers import OrderAdminSerializer


class OrderContactSnapshotTests(TestCase):
    setUp = tests_operations.OperationsTests.setUp

    def snapshot(self):
        return {
            'name': '本單聯絡人', 'email': 'contact@example.test', 'phone': '0900000000',
            'messenger_type': 'LINE', 'messenger_id': 'qa-contact',
            'source_ip': '192.0.2.1', 'policy_accepted_at': 'private-audit-value',
        }

    def test_hq_receives_whitelisted_contact_without_replacing_member_identity(self):
        self.group.booking_contact = self.snapshot()
        self.group.save(update_fields=['booking_contact'])
        api = APIClient()
        api.force_authenticate(User.objects.create_superuser('contact-hq', 'hq@example.test', 'test-password'))
        for path in ['/api/admin/snowland/orders/', f'/api/admin/snowland/orders/{self.group.pk}/']:
            response = api.get(path)
            self.assertEqual(response.status_code, 200)
            data = response.data['data']
            row = data['list'][0] if 'list' in data else data
            self.assertEqual(row.get('booking_contact'), {
                key: self.snapshot()[key] for key in ('name', 'email', 'phone', 'messenger_type', 'messenger_id')
            })
            self.assertEqual(row['user_name'], 'student')
            self.assertNotIn('private-audit-value', str(row))
            self.assertNotIn('192.0.2.1', str(row))
        self.assertTrue(OrderAdminSerializer().fields['booking_contact'].read_only)

    def test_legacy_contact_has_safe_name_email_fallback(self):
        row = OrderAdminSerializer(self.group).data
        self.assertEqual(row.get('booking_contact'), {
            'name': self.group.name, 'email': self.user.email, 'phone': '',
            'messenger_type': '', 'messenger_id': '',
        })

    def test_campus_viewer_does_not_receive_contact_snapshot(self):
        self.reservation.bookings.update(date=timezone.localdate() + timedelta(days=1))
        self.group.booking_contact = self.snapshot()
        self.group.save(update_fields=['booking_contact'])
        user = User.objects.create_user('contact-manager')
        profile = user.userprofile
        profile.is_manager = True
        profile.manager_client = self.client_tenant
        profile.admin_permissions = ['orders']
        profile.save()
        profile.campuses.add(self.campus)
        api = APIClient()
        api.force_authenticate(user)
        for role in ('campus_manager', 'campus_principal'):
            profile.role = role
            profile.save(update_fields=['role'])
            for path in ['/api/admin/snowland/orders/', f'/api/admin/snowland/orders/{self.group.pk}/']:
                response = api.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('booking_contact', str(response.data))
                self.assertNotIn('contact@example.test', str(response.data))
                self.assertNotIn('0900000000', str(response.data))
