import csv
import io
from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting
from Coach.models import CoachPayRule, StaffIncentiveRule, StaffIncentiveStatement
from Coach.payroll import calculate_payroll_statement
from Coach.payroll_review import publish_statement
from Coach.staff_incentives import calculate_staff_incentive, confirm_staff_incentive
from Control.models import TenantStaffMembership
from Coursekit.models import DiscountCode
from booking.api_views import is_new_customer_for_discount
from booking.discount_usage import record_checkout_discount_usage
from booking.loyalty import DEFAULT_RULES, start_order_loyalty, sync_order_loyalty
from booking.models import Booking, CancellationRequest, MemberLoyaltyAccount, Payment, Reservation, ReservationGroup

from . import tests_operations as fixtures
from .coach_workload import coach_workload


class TestOrderTests(TestCase):
    orders_url = '/api/admin/snowland/orders/'
    dashboard_url = '/api/admin/snowland/dashboard/'
    lesson_date = date(2026, 1, 12)

    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.hq_user, self.hq = self.actor('n10-hq', role='hq_admin')
        self.detail_url = f'{self.orders_url}{self.group.pk}/'
        self.mark_url = f'{self.detail_url}test-status/'
        self.group.name = 'N10 sample order'
        self.group.marketing_source = 'N10 test source'
        self.group.save(update_fields=['name', 'marketing_source'])
        Booking.objects.filter(reservation=self.reservation).update(date=self.lesson_date)

    def actor(self, username, *, role, permissions=None, tenant=None):
        user = User.objects.create_user(username)
        membership = TenantStaffMembership.objects.create(
            client=tenant or self.client_tenant, user=user, is_manager=True, role=role,
            all_campuses=role == 'hq_admin', admin_permissions=permissions,
        )
        if role != 'hq_admin':
            membership.campuses.add(self.campus)
        api = APIClient()
        api.force_authenticate(user)
        return user, api

    def mark(self, value=True, reason='  N10 reason  '):
        return self.hq.post(self.mark_url, {'is_test': value, 'reason': reason}, format='json')

    def test_permissions_setting_and_cross_tenant_scope(self):
        body = {'is_test': True, 'reason': 'N10 only'}
        for role, permissions in [('hq_admin', ['order_view']), ('campus_manager', None), ('assistant', ['order_edit'])]:
            with self.subTest(role=role):
                _, api = self.actor(f'n10-{role}', role=role, permissions=permissions)
                self.assertEqual(api.post(self.mark_url, body, format='json').status_code, 403)
        other = Client.objects.create(name='Other school', internal_code='n10-other')
        _, other_api = self.actor('n10-other-hq', role='hq_admin', tenant=other)
        self.assertEqual(other_api.post(self.mark_url, body, format='json').status_code, 403)
        self.assertEqual(other_api.post(self.mark_url.replace('snowland', 'n10-other'), body, format='json').status_code, 404)
        other_group = ReservationGroup.objects.create(client=other, is_test=True)
        ids = {row['id'] for row in self.hq.get(self.orders_url, {'include_test': '1'}).data['data']['list']}
        self.assertNotIn(other_group.pk, ids)
        module = ModuleInfo.objects.create(module_sid='booking', module_name='預約')
        ModuleSetting.objects.create(client=self.client_tenant, module=module, settings={'test_order_marking_enabled': False})
        self.assertFalse(self.hq.get(self.detail_url).data['data']['can_mark_test'])
        self.assertEqual(self.mark().status_code, 403)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_test)

    def test_mark_unmark_and_audit_with_idempotent_retries(self):
        self.assertTrue(self.hq.get(self.detail_url).data['data']['can_mark_test'])
        self.assertEqual(self.mark(value='true').status_code, 400)
        self.assertEqual(self.mark(reason=' ').status_code, 400)
        self.assertEqual(self.mark().status_code, 200)
        self.group.refresh_from_db()
        self.assertEqual(self.group.test_marked_by, self.hq_user)
        self.assertIsNotNone(self.group.test_marked_at)
        self.assertEqual(self.mark().status_code, 200)
        self.assertEqual(self.hq.get(self.orders_url).data['data']['total'], 0)
        self.assertEqual(self.hq.get(self.orders_url, {'workflow': 'payments'}).data['data']['total'], 0)
        self.assertTrue(self.hq.get(self.orders_url, {'include_test': '1'}).data['data']['list'][0]['is_test'])
        self.assertEqual(self.mark(False, 'Restore sample').status_code, 200)
        self.group.refresh_from_db()
        self.assertEqual((self.group.is_test, self.group.test_marked_by, self.group.test_marked_at), (False, None, None))
        self.assertEqual(self.hq.get(self.orders_url).data['data']['total'], 1)
        revisions = list(self.group.revisions.order_by('version'))
        self.assertEqual([(row.change_type, row.reason, row.snapshot['is_test']) for row in revisions], [
            ('mark_test', 'N10 reason', True), ('unmark_test', 'Restore sample', False),
        ])
        self.assertTrue(all(row.created_by_id == self.hq_user.pk and row.created_at for row in revisions))
        self.assertEqual(self.hq.get(self.detail_url).data['data']['revisions'][0]['created_by_name'], self.hq_user.username)

    def test_money_history_blocks_mark_and_marked_order_cannot_be_reconciled(self):
        payment = Payment.objects.create(reservation_group=self.group, status='paid')
        Payment.objects.create(reservation_group=self.group, status='unpaid')
        response = self.mark()
        self.assertEqual(response.status_code, 409)
        self.assertIn('請先由主管', response.data['msg'])
        self.assertFalse(self.group.revisions.exists())
        payment.status = 'unpaid'
        payment.save(update_fields=['status'])
        self.assertEqual(self.mark().status_code, 200)
        response = self.hq.patch(self.detail_url, {'action': 'save', 'payment_status': 'paid'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertFalse(self.group.payments.filter(status='paid').exists())
        cancellation = CancellationRequest.objects.create(group=self.group, reason='other', status='requested')
        refunds_url = '/api/admin/snowland/cancellations/'
        self.assertEqual(self.hq.get(f'{refunds_url}{cancellation.pk}/').status_code, 404)

    def test_locked_payroll_and_incentive_snapshots_block_marking(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000)
        statement = self.payroll()
        statement.status = 'review'
        statement.save(update_fields=['status'])
        self.assertEqual(self.mark().status_code, 409)
        statement.status = 'draft'
        statement.save(update_fields=['status'])
        incentive = StaffIncentiveStatement.objects.create(user=self.hq_user, campus=self.campus,
            month=self.lesson_date.replace(day=1), status='confirmed', user_name='HQ', campus_name=self.campus.name)
        incentive.lines.create(group=self.group, entry_key='n10-approved', line_type='earning',
                               order_number=self.group.order_number, event_date=self.lesson_date,
                               base_amount=10000, percent=10, amount=1000)
        self.assertEqual(self.mark().status_code, 409)

    def test_reporting_and_export_include_only_real_orders_by_default(self):
        real_user = User.objects.create_user('n10-real')
        real = ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus, user=real_user, marketing_source='N10 real source')
        reservation = Reservation.objects.create(group=real, resort=self.resort, course_type=self.course_type,
            status='completed', number_of_people=3, course_fee=1700)
        Booking.objects.create(reservation=reservation, course_type='單板', course_name='N10 real lesson',
            date=self.lesson_date, start_time=time(10), end_time=time(11))
        self.assertEqual(self.mark().status_code, 200)
        # Exercise readers with a marked paid row even if a historical import supplied it.
        for group in (real, self.group):
            Payment.objects.create(reservation_group=group, status='paid')
        for basis in ('created', 'completed'):
            params = {'period': 'today'} if basis == 'created' else {
                'period': 'custom', 'date_basis': basis, 'start_date': self.lesson_date.isoformat(), 'end_date': self.lesson_date.isoformat(),
            }
            with self.subTest(basis=basis):
                report = self.hq.get(self.dashboard_url, params).data['data']
                self.assertEqual(report['stats'], {'orders': 1, 'completed_orders': 1, 'revenue': 1700,
                    'avg_order_value': 1700, 'members': 1, 'student_visits': 3, 'teaching_hours': 1})
                self.assertEqual([row['name'] for row in report['marketing_sources']], ['N10 real source'])
                self.assertEqual([row['name'] for row in report['top_items']], ['N10 real lesson'])
                self.assertEqual(report['campus_summary'][0]['orders'], 1)
                self.assertEqual(report['payment_statuses'][0]['orders'], 1)
                self.assertEqual(len(report['recent_orders']), 1)
                text = self.hq.get(self.dashboard_url, {**params, 'export': 'csv', 'include_test': '1'}).content.decode('utf-8-sig')
                self.assertNotIn('N10 test source', text)
        params = {'start': timezone.localdate().isoformat(), 'end': timezone.localdate().isoformat()}
        export_url = f'{self.orders_url}export/'
        response = self.hq.get(export_url, params)
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual([row['訂單編號'] for row in rows], [real.order_number])
        response = self.hq.get(export_url, {**params, 'include_test': '1'})
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual({row['訂單編號']: row['測試訂單'] for row in rows}, {real.order_number: '否', self.group.order_number: '是'})
        self.assertEqual(self.mark(False).status_code, 200)
        self.assertEqual(self.hq.get(self.dashboard_url, {'period': 'today'}).data['data']['stats']['revenue'], 11700)

    def payroll(self):
        return calculate_payroll_statement(coach=self.coach, campus=self.campus,
            period_start=self.lesson_date, period_end=self.lesson_date)

    def test_coach_payroll_workload_and_incentive_exclude_marked_rows(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000,
            referral_percent=10, specified_fee=150, supervisor_allowance=300)
        draft = self.payroll()
        self.assertEqual((draft.course_pay, draft.specified_fees, draft.referral_commission, draft.supervisor_allowance),
                         (4000, 150, 900, 300))
        self.assertEqual(self.mark().status_code, 200)
        with self.assertRaisesMessage(ValueError, '薪資草稿含測試訂單'):
            publish_statement(draft, timezone.localdate())
        self.assertEqual(self.payroll().total_amount, 0)
        workload = coach_workload(tenant=self.client_tenant, campus_ids=None, start=self.lesson_date, end=self.lesson_date,
            resort=None, schedule_statuses=['completed'], can_view_settings=False)
        self.assertEqual(workload['coaches'][0]['completed_seconds'], 0)
        Payment.objects.create(reservation_group=self.group, status='paid')
        StaffIncentiveRule.objects.create(user=self.hq_user, campus=self.campus, completed_order_percent=10)
        def staff_calculation():
            return calculate_staff_incentive(user=self.hq_user, campus=self.campus, month=self.lesson_date.replace(day=1))
        self.assertEqual(staff_calculation().earned_amount, 0)
        self.assertEqual(self.mark(False).status_code, 200)
        incentive = staff_calculation()
        self.assertEqual(incentive.earned_amount, 1000)
        self.assertEqual(self.payroll().total_amount, 5350)
        self.group.is_test = True
        self.group.save(update_fields=['is_test'])
        with self.assertRaisesMessage(ValueError, '獎金草稿含測試訂單'):
            confirm_staff_incentive(incentive, actor=self.hq_user)

    def test_mark_releases_redemption_from_balance_and_unmark_restores_it(self):
        account = MemberLoyaltyAccount.objects.create(client=self.client_tenant, user=self.user, reward_balance=500)
        loyalty = start_order_loyalty(self.group, 1, {**DEFAULT_RULES, 'enabled': True}, spent=200, discount=200)
        account.refresh_from_db()
        self.assertEqual(account.reward_balance, 300)
        self.assertEqual(self.mark().status_code, 200)
        self.group.refresh_from_db()
        sync_order_loyalty(self.group, confirmed_base=10000)
        account.refresh_from_db()
        loyalty.refresh_from_db()
        self.assertEqual((account.points, account.reward_balance, loyalty.paid_base), (0, 500, None))
        self.assertEqual(self.mark(False).status_code, 200)
        account.refresh_from_db()
        self.assertEqual(account.reward_balance, 300)

    def test_discount_usage_and_new_customer_status_follow_marking(self):
        rule = DiscountCode.objects.create(client=self.client_tenant, code='N10', name='N10')
        record_checkout_discount_usage(self.client_tenant, {self.reservation.pk: [rule.pk]})
        rule.refresh_from_db()
        self.assertEqual(rule.used_count, 1)
        self.assertFalse(is_new_customer_for_discount(self.client_tenant, self.user, {}))
        self.assertEqual(self.mark().status_code, 200)
        rule.refresh_from_db()
        self.assertEqual(rule.used_count, 0)
        self.assertTrue(is_new_customer_for_discount(self.client_tenant, self.user, {}))
        self.assertEqual(self.mark(False).status_code, 200)
        rule.refresh_from_db()
        self.assertEqual(rule.used_count, 1)
