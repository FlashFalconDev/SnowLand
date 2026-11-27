import csv
import io
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting
from Control.models import TenantStaffMembership
from booking.currency import order_settlement
from booking.models import Payment, ReservationGroup
from . import tests_operations


class OrderBankPostedDateTests(TestCase):
    def setUp(self):
        tests_operations.OperationsTests.setUp(self)
        self.booking_module = ModuleInfo.objects.create(module_sid='booking', module_name='預約')
        self.payment = Payment.objects.create(reservation_group=self.group, status='pending')
        self.admin = self.actor('finance-hq', role='hq_admin')
        self.orders_url = '/api/admin/snowland/orders/'
        self.detail_url = f'{self.orders_url}{self.group.pk}/'
        self.posted_date = date(2026, 1, 2)

    def actor(self, username, *, role, permissions=None, tenant=None):
        user = User.objects.create_user(username)
        membership = TenantStaffMembership.objects.create(
            client=tenant or self.client_tenant, user=user, is_manager=True, role=role,
            admin_permissions=permissions, all_campuses=role == 'hq_admin',
        )
        if role != 'hq_admin':
            membership.campuses.add(self.campus)
        api = APIClient()
        api.force_authenticate(user)
        return api

    def set_config(self, config):
        ModuleSetting.objects.update_or_create(
            client=self.client_tenant, module=self.booking_module, defaults={'settings': config},
        )

    def set_mode(self, mode):
        self.set_config({'manual_payment_posting_date_mode': mode})

    def save_paid(self, **fields):
        return self.admin.patch(self.detail_url, {'action': 'save', 'payment_status': 'paid', **fields}, format='json')

    def assert_payment(self, status, posted_date=None):
        self.payment.refresh_from_db()
        self.assertEqual((self.payment.status, self.payment.bank_posted_date), (status, posted_date))

    def assert_detail(self, mode, posted_date=None, workflow=None):
        response = self.admin.get(self.detail_url, {'workflow': workflow} if workflow else {})
        self.assertEqual(response.status_code, 200, response.data)
        detail = response.data['data']
        self.assertEqual(detail['manual_payment_posting_date_mode'], mode)
        self.assertEqual(detail['bank_posted_date'], posted_date.isoformat() if posted_date else None)

    def test_optional_can_mark_paid_with_a_blank_or_valid_date(self):
        self.set_mode('optional')
        for value, expected in ((None, None), (self.posted_date.isoformat(), self.posted_date)):
            with self.subTest(value=value):
                self.payment.status = 'pending'
                self.payment.save(update_fields=['status'])
                response = self.save_paid(bank_posted_date=value)
                self.assertEqual(response.status_code, 200, response.data)
                self.assert_payment('paid', expected)
                self.assert_detail('optional', expected)
                self.assert_detail('optional', expected, workflow='payments')
                rows = self.admin.get(self.orders_url, {'workflow': 'payments'}).data['data']['list']
                self.assertEqual(rows[0]['bank_posted_date'], value)

    def test_required_rejects_missing_date_without_saving_payment_or_revision(self):
        self.set_mode('required')
        response = self.save_paid()
        self.assertEqual(response.status_code, 400)
        self.assertIn('請填寫入帳日期', response.data['msg'])
        self.assert_payment('pending')
        self.assertFalse(self.group.revisions.exists())

    def test_disabled_allows_confirmation_and_rejects_date_changes(self):
        self.set_mode('disabled')
        self.assertEqual(self.save_paid().status_code, 200)
        self.assert_payment('paid')
        self.payment.bank_posted_date = self.posted_date
        self.payment.save(update_fields=['bank_posted_date'])
        for value in (None, '2026-02-03'):
            response = self.save_paid(bank_posted_date=value)
            self.assertEqual(response.status_code, 400)
            self.assertIn('停用入帳日期輸入', response.data['msg'])
        self.assertEqual(self.save_paid().status_code, 200)
        self.assert_payment('paid', self.posted_date)
        self.assert_detail('disabled', self.posted_date, workflow='payments')

    def test_rejects_future_and_invalid_dates_using_taipei_today(self):
        now = datetime(2026, 1, 1, 16, 5, tzinfo=datetime_timezone.utc)
        self.payment.bank_posted_date = self.posted_date - timedelta(days=1)
        self.payment.save(update_fields=['bank_posted_date'])
        with timezone.override('UTC'), patch('django.utils.timezone.now', return_value=now):
            for value, message in [('2026-01-03', '不可晚於今天'), ('2026-02-30', '有效的入帳日期'),
                                   ('20260102', '有效的入帳日期'), ('2026-01-02T00:00:00', '有效的入帳日期'),
                                   (20260102, '有效的入帳日期')]:
                with self.subTest(value=value):
                    response = self.save_paid(bank_posted_date=value)
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(message, response.data['msg'])
                    self.assert_payment('pending', date(2026, 1, 1))
            self.assertEqual(self.save_paid(bank_posted_date='2026-01-02').status_code, 200)
        self.assert_payment('paid', self.posted_date)

    def test_no_setting_empty_or_unknown_mode_defaults_to_optional(self):
        self.assert_detail('optional')
        self.assertEqual(self.save_paid().status_code, 200)
        self.assertFalse(ModuleSetting.objects.filter(client=self.client_tenant).exists())
        for config in ({}, {'manual_payment_posting_date_mode': None}, {'manual_payment_posting_date_mode': ''},
                       {'manual_payment_posting_date_mode': 'unknown'}):
            with self.subTest(config=config):
                self.set_config(config)
                self.assert_detail('optional')
                self.assertEqual(self.save_paid().status_code, 200)
                self.assert_payment('paid')

    def test_mode_is_scoped_to_request_tenant(self):
        self.set_mode('required')
        other = Client.objects.create(internal_code='other-pay', name='第二租戶')
        other_group = ReservationGroup.objects.create(client=other)
        other_admin = self.actor('other-finance', role='hq_admin', tenant=other)
        other_url = f'/api/admin/other-pay/orders/{other_group.pk}/'
        self.assertEqual(other_admin.get(other_url).data['data']['manual_payment_posting_date_mode'], 'optional')
        self.assertEqual(other_admin.patch(other_url, {'payment_status': 'paid'}, format='json').status_code, 200)
        self.assertIsNone(other_group.payments.get().bank_posted_date)
        self.assertEqual(self.save_paid().status_code, 400)
        self.assert_payment('pending')

    def test_existing_paid_order_can_add_date_in_optional_and_required_modes(self):
        self.payment.status = 'paid'
        self.payment.save(update_fields=['status'])
        for mode in ('optional', 'required'):
            with self.subTest(mode=mode):
                self.set_mode(mode)
                self.payment.bank_posted_date = None
                self.payment.save(update_fields=['bank_posted_date'])
                if mode == 'required':
                    self.assertEqual(self.save_paid().status_code, 400)
                    self.assert_payment('paid')
                response = self.save_paid(bank_posted_date=self.posted_date.isoformat())
                self.assertEqual(response.status_code, 200, response.data)
                self.assert_payment('paid', self.posted_date)
                self.assertEqual(self.save_paid().status_code, 200)
                self.assert_payment('paid', self.posted_date)
        self.set_mode('optional')
        self.assertEqual(self.save_paid(bank_posted_date=None).status_code, 200)
        self.assert_payment('paid')

    def test_foreign_receipt_and_bank_date_use_same_paid_save(self):
        self.set_mode('required')
        self.group.currency_snapshot = {'currency': 'JPY', 'base_currency': 'TWD', 'rate': '4.5', 'locked_at': None}
        self.group.save(update_fields=['currency_snapshot'])
        receipt = {'payment_currency': 'JPY', 'payment_received_amount': order_settlement(self.group)['amount']}
        self.assertEqual(self.save_paid(**receipt).status_code, 400)
        self.assert_payment('pending')
        self.assertEqual(self.payment.DataJSON, {})
        self.assertEqual(self.save_paid(bank_posted_date=self.posted_date.isoformat()).status_code, 400)
        self.assert_payment('pending')
        self.assertEqual(self.save_paid(bank_posted_date=self.posted_date.isoformat(), **receipt).status_code, 200)
        self.assert_payment('paid', self.posted_date)
        confirmation = self.payment.DataJSON['settlement']['confirmed_at']
        self.assertEqual(self.save_paid(bank_posted_date='2026-01-01').status_code, 200)
        self.assert_payment('paid', date(2026, 1, 1))
        self.assertEqual(self.payment.DataJSON['settlement']['confirmed_at'], confirmation)
        self.assertEqual(len(self.payment.DataJSON['settlement_confirmations']), 1)

    def test_export_includes_date_and_legacy_blank_under_existing_permissions(self):
        self.payment.status = 'paid'
        self.payment.DataJSON = {'settlement': {'confirmed_at': '2026-01-01T00:00:00+00:00'}}
        self.payment.save(update_fields=['status', 'DataJSON'])
        self.assert_detail('optional')
        export_url = self.orders_url + 'export/'
        today = timezone.localdate().isoformat()
        params = {'start': today, 'end': today}

        def export_rows():
            response = self.admin.get(export_url, params)
            self.assertEqual(response.status_code, 200)
            rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
            self.assertEqual(len(rows), 2)
            return rows

        self.assertEqual([row['入帳日期'] for row in export_rows()], ['', ''])
        self.assert_payment('paid')
        self.assertEqual(self.save_paid(bank_posted_date=self.posted_date.isoformat()).status_code, 200)
        self.assertEqual([row['入帳日期'] for row in export_rows()], [self.posted_date.isoformat()] * 2)
        assistant = self.actor('finance-assistant', role='assistant', permissions=['order_payments'])
        self.assertEqual(assistant.get(export_url, params).status_code, 403)

    def test_date_requires_payment_permission_and_explicit_paid_status(self):
        editor = self.actor('course-editor', role='assistant', permissions=['order_edit'])
        payload = {'bank_posted_date': self.posted_date.isoformat()}
        self.assertEqual(editor.patch(self.detail_url, payload, format='json').status_code, 403)
        response = self.admin.patch(self.detail_url, {**payload, 'payment_status': 'pending'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('請將付款狀態設為已付款', response.data['msg'])
        self.assert_payment('pending')
