import csv
import io
import json
from unittest.mock import patch

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from API.admin_views import BOOKING_FORM_OPTIONS_LOCATION_KEY
from Client.models import Client, ModuleInfo, ModuleSetting, SiteContent
from Control.models import TenantStaffMembership
from Resorts.models import Campus
from booking.models import Payment, ReservationGroup
from . import tests_operations


class OrderMarketingSourceTests(TestCase):
    def setUp(self):
        tests_operations.OperationsTests.setUp(self)
        self.group.marketing_source = '內部導入'
        self.group.marketing_source_detail = '既有訂單匯入'
        self.group.save(update_fields=['marketing_source', 'marketing_source_detail'])
        self.payment = Payment.objects.create(
            reservation_group=self.group, status='paid', DataJSON={'import_source': 'fixture-import'},
        )
        self.other_tenant = Client.objects.create(name='第二租戶', internal_code='other-source')
        self.other_campus = Campus.objects.create(client=self.other_tenant, name='第二租戶校區', code='other')
        self.set_options(self.client_tenant, ['網站廣告', '活動介紹'])
        self.set_options(self.other_tenant, ['第二租戶活動'])
        self.editor, self.editor_user = self.actor('editor', ['order_view', 'order_edit', 'analytics'])
        self.detail_url = self.order_url(self.group)
        self.source_url = self.detail_url + 'marketing-source/'
        self.dashboard_url = '/api/admin/snowland/dashboard/'

    def actor(self, username, permissions, *, tenant=None, campus=None, role='assistant'):
        user = User.objects.create_user(username)
        membership = TenantStaffMembership.objects.create(
            client=tenant or self.client_tenant, user=user, is_manager=True, role=role,
            admin_permissions=permissions, all_campuses=False,
        )
        membership.campuses.add(campus or self.campus)
        api = APIClient()
        api.force_authenticate(user)
        return api, user

    def set_options(self, tenant, options):
        return SiteContent.objects.create(
            client=tenant, content_type='setting', location_key=BOOKING_FORM_OPTIONS_LOCATION_KEY,
            title='訂單表單選項', status='active', metadata={'referral_source_options': options},
        )

    def order_url(self, order, code='snowland'):
        return f'/api/admin/{code}/orders/{order.pk}/'

    def save_source(self, value):
        return self.editor.put(self.source_url, {'marketing_source_override': value}, format='json')

    def audit(self):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(ReservationGroup),
            object_id=str(self.group.pk), action_flag=CHANGE,
        ).order_by('pk')

    def test_paid_order_preserves_import_markers_payment_and_referrer(self):
        detail = self.editor.get(self.detail_url, {'workflow': 'edit'}).data['data']
        self.assertEqual(detail['marketing_source_options'], ['網站廣告', '活動介紹'])
        self.assertIsNone(detail['marketing_source_override'])
        payment_before = Payment.objects.values().get(pk=self.payment.pk)
        response = self.save_source('網站廣告')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['marketing_source_override'], '網站廣告')
        self.group.refresh_from_db()
        self.assertEqual(self.group.marketing_source_override, '網站廣告')
        self.assertEqual(self.group.marketing_source, '內部導入')
        self.assertEqual(self.group.marketing_source_detail, '既有訂單匯入')
        self.assertEqual(self.group.referral_user_id, self.coach_user.pk)
        self.assertEqual(Payment.objects.values().get(pk=self.payment.pk), payment_before)
        self.assertFalse(self.group.revisions.exists())
        detail = self.editor.get(self.detail_url).data['data']
        self.assertEqual(detail['marketing_source'], '內部導入')
        self.assertEqual(detail['marketing_source_override'], '網站廣告')

    def test_audits_each_change_and_clear_without_duplicate_on_retry(self):
        start = timezone.now()
        for value in ('網站廣告', '網站廣告', '活動介紹', None, None):
            self.assertEqual(self.save_source(value).status_code, 200)
        logs = list(self.audit())
        self.assertEqual(len(logs), 3)
        self.assertEqual([json.loads(log.change_message) for log in logs], [
            {'field': 'marketing_source_override', 'old': None, 'new': '網站廣告'},
            {'field': 'marketing_source_override', 'old': '網站廣告', 'new': '活動介紹'},
            {'field': 'marketing_source_override', 'old': '活動介紹', 'new': None},
        ])
        for log in logs:
            self.assertEqual(log.user_id, self.editor_user.pk)
            self.assertLessEqual(start, log.action_time)
            self.assertLessEqual(log.action_time, timezone.now())
        self.group.refresh_from_db()
        self.assertIsNone(self.group.marketing_source_override)

    def test_audit_failure_rolls_back_source(self):
        with patch('API.admin_views.LogEntry.objects.create', side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                self.save_source('網站廣告')
        self.group.refresh_from_db()
        self.assertIsNone(self.group.marketing_source_override)
        self.assertFalse(self.audit().exists())

    def test_requires_edit_permission_and_keeps_existing_read_only_roles(self):
        for role, permissions in (
            ('assistant', ['order_view', 'order_payments']),
            ('campus_manager', ['order_view', 'order_edit']),
            ('campus_principal', ['order_view', 'order_edit']),
        ):
            with self.subTest(role=role):
                viewer, _ = self.actor(f'{role}-viewer', permissions, role=role)
                self.assertEqual(viewer.put(self.source_url, {'marketing_source_override': '網站廣告'}, format='json').status_code, 403)
        reader, _ = self.actor('detail-reader', ['order_view'])
        self.assertNotIn('marketing_source_options', reader.get(self.detail_url).data['data'])
        self.assertFalse(self.audit().exists())

    def test_session_mutations_require_csrf(self):
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(self.editor_user)
        payload = {'marketing_source_override': '網站廣告'}
        self.assertEqual(api.put(self.source_url, payload, format='json').status_code, 403)
        self.assertEqual(api.get(self.detail_url).status_code, 200)
        response = api.put(self.source_url, payload, format='json', HTTP_X_CSRFTOKEN=api.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200, response.data)

    def test_rejects_cross_campus_and_cross_tenant_orders(self):
        other_campus = Campus.objects.create(client=self.client_tenant, name='未授權校區', code='none')
        wrong_campus = ReservationGroup.objects.create(client=self.client_tenant, campus=other_campus)
        wrong_tenant = ReservationGroup.objects.create(client=self.other_tenant, campus=self.other_campus)
        paths = (
            (self.order_url(wrong_campus), 404),
            (self.order_url(wrong_tenant), 404),
            (self.order_url(wrong_tenant, 'other-source'), 403),
        )
        for path, expected in paths:
            response = self.editor.put(path + 'marketing-source/', {'marketing_source_override': '網站廣告'}, format='json')
            self.assertEqual(response.status_code, expected, response.data)
        other_editor, _ = self.actor(
            'other-editor', ['order_view', 'order_edit'], tenant=self.other_tenant, campus=self.other_campus,
        )
        other_url = self.order_url(wrong_tenant, 'other-source')
        detail = other_editor.get(other_url).data['data']
        self.assertEqual(detail['marketing_source_options'], ['第二租戶活動'])
        self.assertEqual(other_editor.put(other_url + 'marketing-source/', {
            'marketing_source_override': '網站廣告',
        }, format='json').status_code, 400)
        wrong_campus.refresh_from_db()
        wrong_tenant.refresh_from_db()
        self.assertIsNone(wrong_campus.marketing_source_override)
        self.assertIsNone(wrong_tenant.marketing_source_override)

    def test_rejects_unknown_options_and_non_source_fields(self):
        for value in ('第二租戶活動', '不存在', ' 網站廣告 ', '', False, 1, [], {}):
            with self.subTest(value=value):
                response = self.save_source(value)
                self.assertEqual(response.status_code, 400, response.data)
        for payload in ({}, {'marketing_source_override': '網站廣告', 'payment_status': 'refunded'}):
            self.assertEqual(self.editor.put(self.source_url, payload, format='json').status_code, 400)
        self.group.refresh_from_db()
        self.assertIsNone(self.group.marketing_source_override)
        self.assertFalse(self.audit().exists())

    def test_rejects_removed_option_but_keeps_old_attribution_readable(self):
        self.assertEqual(self.save_source('網站廣告').status_code, 200)
        config = APIClient()
        config.force_authenticate(User.objects.create_superuser('config-hq'))
        changed = config.put('/api/admin/snowland/payment-settings/?section=booking-form', {
            'referral_source_options': ['活動介紹'],
        }, format='json')
        self.assertEqual(changed.status_code, 200, changed.data)
        detail = self.editor.get(self.detail_url).data['data']
        self.assertEqual(detail['marketing_source_override'], '網站廣告')
        self.assertEqual(detail['marketing_source_options'], ['活動介紹'])
        self.assertEqual(self.save_source('網站廣告').status_code, 400)
        self.assertEqual(self.save_source(None).status_code, 200)

    def test_disabled_tenant_cannot_edit_but_keeps_saved_source(self):
        self.assertEqual(self.save_source('網站廣告').status_code, 200)
        module = ModuleInfo.objects.create(module_sid='booking', module_name='預約')
        ModuleSetting.objects.create(
            client=self.client_tenant, module=module, settings={'order_source_override_enabled': False},
        )
        detail = self.editor.get(self.detail_url).data['data']
        self.assertNotIn('marketing_source_options', detail)
        self.assertEqual(detail['marketing_source_override'], '網站廣告')
        self.assertEqual(self.save_source(None).status_code, 403)
        self.assertEqual(self.editor.get(self.dashboard_url).data['data']['marketing_sources'][0]['name'], '網站廣告')
        self.assertEqual(self.audit().count(), 1)

    def test_dashboard_and_both_exports_use_corrected_original_and_unknown_sources(self):
        self.assertEqual(self.save_source('活動介紹').status_code, 200)
        ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus, marketing_source='活動介紹')
        ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus, marketing_source='朋友介紹')
        ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus)
        expected = {
            '活動介紹': (2, self.reservation.payment_amount),
            '朋友介紹': (1, 0),
            '未填寫': (1, 0),
        }
        response = self.editor.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual({
            item['name']: (item['orders'], item['revenue'])
            for item in response.data['data']['marketing_sources']
        }, expected)
        csv_response = self.editor.get(self.dashboard_url, {'export': 'csv'})
        self.assertEqual(csv_response.status_code, 200)
        csv_rows = list(csv.reader(io.StringIO(csv_response.content.decode('utf-8-sig'))))
        xlsx_response = self.editor.get(self.dashboard_url, {'export': 'xlsx'})
        self.assertEqual(xlsx_response.status_code, 200)
        xlsx = load_workbook(io.BytesIO(xlsx_response.content))
        xlsx_rows = list(xlsx.active.values)
        for name, (count, amount) in expected.items():
            self.assertIn([name, str(count), str(amount)], csv_rows)
            self.assertIn((name, count, amount), xlsx_rows)
        self.assertNotIn('內部導入', csv_response.content.decode('utf-8-sig'))
