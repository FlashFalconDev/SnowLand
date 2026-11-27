import csv
import io
from datetime import date, datetime, time
from uuid import uuid4

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
from booking.loyalty import DEFAULT_RULES, rebuild_loyalty_account, start_order_loyalty, sync_order_loyalty
from booking.models import (
    Booking, CancellationRequest, MemberLoyaltyAccount, MemberLoyaltyEntry, NewebpayMerchant, OrderLoyalty,
    Payment, Reservation, ReservationGroup,
)
from booking.operations import record_order_revision

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

    def mark(self, value=True, reason='  N10 reason  ', **extra):
        return self.hq.post(self.mark_url, {'is_test': value, 'reason': reason, **extra}, format='json')

    def assert_mark_blocked_by(self, *expected):
        response = self.mark()
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data['detail'], '此訂單已有帳務紀錄，無法標記為測試訂單。')
        self.assertEqual(response.data['msg'], response.data['detail'])
        self.assertIs(response.data['can_override'], True)
        reasons = response.data['reasons']
        self.assertEqual([(reason['code'], reason['label']) for reason in reasons], list(expected))
        for reason in reasons:
            self.assertIsInstance(reason['hint'], str)
            self.assertTrue(reason['hint'].strip())
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_test)
        self.assertFalse(self.group.revisions.filter(change_type='mark_test').exists())

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

    def test_non_headquarters_editor_can_only_check_financial_reasons(self):
        _, api = self.actor('n10-edit', role='assistant', permissions=['order_edit'])
        detail = api.get(self.detail_url, {'workflow': 'edit'}).data['data']
        self.assertTrue(detail['can_check_test_status'])
        self.assertFalse(detail['can_mark_test'])
        body = {'is_test': True, 'reason': ''}
        payment = Payment.objects.create(reservation_group=self.group, status='paid')
        blocked = api.post(self.mark_url, body, format='json')
        self.assertEqual(blocked.status_code, 409, blocked.data)
        self.assertEqual([item['code'] for item in blocked.data['reasons']], ['payment_record'])
        self.assertIs(blocked.data['can_override'], False)
        override = {**body, 'reason': '測試付款', 'acknowledged_reasons': ['payment_record']}
        self.assertEqual(api.post(self.mark_url, override, format='json').status_code, 403)
        payment.status = 'unpaid'
        payment.save(update_fields=['status'])
        self.assertEqual(api.post(self.mark_url, body, format='json').status_code, 403)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_test)
        self.assertFalse(self.group.revisions.exists())

    def test_override_can_be_disabled_independently_for_the_tenant(self):
        module = ModuleInfo.objects.create(module_sid='booking', module_name='預約')
        ModuleSetting.objects.create(client=self.client_tenant, module=module,
                                     settings={'test_order_financial_override_enabled': False})
        other = Client.objects.create(name='Other school', internal_code='n10-switch')
        ModuleSetting.objects.create(client=other, module=module, settings={'test_order_financial_override_enabled': True})
        payment = Payment.objects.create(reservation_group=self.group, status='paid')
        blocked = self.mark()
        self.assertEqual(blocked.status_code, 409, blocked.data)
        self.assertEqual([item['code'] for item in blocked.data['reasons']], ['payment_record'])
        self.assertIs(blocked.data['can_override'], False)
        self.assertEqual(self.mark(acknowledged_reasons=['payment_record']).status_code, 403)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_test)
        self.assertFalse(self.group.revisions.exists())
        payment.status = 'unpaid'
        payment.save(update_fields=['status'])
        self.assertEqual(self.mark().status_code, 200)

    def test_override_requires_nonblank_reason_and_current_blockers(self):
        payment = Payment.objects.create(reservation_group=self.group, status='paid')
        self.assert_mark_blocked_by(('payment_record', '付款紀錄'))
        for reason in ('', ' \t\n　'):
            self.assertEqual(self.mark(reason=reason, acknowledged_reasons=['payment_record']).status_code, 400)
        for reasons in (None, [], 'payment_record', ['payment_record', 'payment_record']):
            self.assertEqual(self.mark(acknowledged_reasons=reasons).status_code, 400)
        payment.bank_posted_date = self.lesson_date
        payment.save(update_fields=['bank_posted_date'])
        changed = self.mark(acknowledged_reasons=['payment_record'])
        self.assertEqual(changed.status_code, 409, changed.data)
        self.assertIs(changed.data['can_override'], True)
        self.assertEqual([item['code'] for item in changed.data['reasons']], ['payment_record', 'bank_posted_date'])
        payment.status = 'unpaid'
        payment.bank_posted_date = None
        payment.save(update_fields=['status', 'bank_posted_date'])
        changed = self.mark(acknowledged_reasons=['payment_record', 'bank_posted_date'])
        self.assertEqual(changed.status_code, 409, changed.data)
        self.assertEqual(changed.data['reasons'], [])
        self.assertIs(changed.data['can_override'], False)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_test)
        self.assertFalse(self.group.revisions.exists())

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
        self.assert_mark_blocked_by(('payment_record', '付款紀錄'))
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

    def test_each_payment_record_condition_blocks_marking_even_when_soft_deleted(self):
        payment = Payment.all_objects.create(reservation_group=self.group, is_deleted=True)
        for fields in (
            {'status': 'paid'},
            {'status': 'refunded'},
            {'DataJSON': {'gateway_response': None}},
            {'DataJSON': {'settlement': {'confirmed_at': None}}},
            {'status': 'pending', 'bank_account': '12345'},
        ):
            with self.subTest(fields=fields):
                values = {'status': 'unpaid', 'bank_account': None, 'DataJSON': {}, **fields}
                Payment.all_objects.filter(pk=payment.pk).update(**values)
                self.assert_mark_blocked_by(('payment_record', '付款紀錄'))

    def test_bank_posted_date_blocks_marking_independently(self):
        Payment.all_objects.create(reservation_group=self.group, status='unpaid',
                                  bank_posted_date=self.lesson_date, is_deleted=True)
        self.assert_mark_blocked_by(('bank_posted_date', '入帳日'))

    def test_each_newebpay_condition_blocks_marking(self):
        self.group.newebpay_form_issued = True
        self.group.save(update_fields=['newebpay_form_issued'])
        self.assert_mark_blocked_by(('newebpay', '藍新表單'))
        self.group.newebpay_form_issued = False
        self.group.newebpay_merchant = NewebpayMerchant.objects.create(client=self.client_tenant, environment='sandbox')
        self.group.save(update_fields=['newebpay_form_issued', 'newebpay_merchant'])
        self.assert_mark_blocked_by(('newebpay', '藍新表單'))

    def test_each_refund_condition_blocks_marking(self):
        cancellation = CancellationRequest.objects.create(
            group=self.group, reason='other', status='refunded', refund_amount=0, actual_received_amount=0,
        )
        self.assert_mark_blocked_by(('refund', '退款'))
        cancellation.status = 'approved'
        cancellation.actual_received_amount = 1
        cancellation.save(update_fields=['status', 'actual_received_amount'])
        self.assert_mark_blocked_by(('refund', '退款'))

    def create_amendment(self, status):
        return self.group.amendments.create(
            revision=record_order_revision(self.group), request_key=uuid4(), reason='QA',
            previous_total=10000, new_total=11000, difference_amount=1000, status=status,
        )

    def test_each_financial_amendment_status_blocks_marking(self):
        amendment = self.create_amendment('topup_due')
        for status in ('topup_reported', 'refund_account_due', 'refund_due', 'settled'):
            with self.subTest(status=status):
                amendment.status = status
                amendment.save(update_fields=['status'])
                self.assert_mark_blocked_by(('amendment', '差額'))

    def test_zero_loyalty_base_blocks_marking_even_when_soft_deleted(self):
        account = MemberLoyaltyAccount.objects.create(client=self.client_tenant, user=self.user)
        OrderLoyalty.all_objects.create(
            group=self.group, account=account, policy_revision=1, rules=DEFAULT_RULES, paid_base=0, is_deleted=True,
        )
        self.assert_mark_blocked_by(('loyalty', '紅利'))

    def test_locked_payroll_and_incentive_snapshots_block_marking_even_when_soft_deleted(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000)
        statement = self.payroll()
        statement.lines.update(is_deleted=True)
        statement.status = 'review'
        statement.save(update_fields=['status'])
        self.assert_mark_blocked_by(('coach_payroll', '教練薪資'))
        statement.status = 'draft'
        statement.save(update_fields=['status'])
        incentive = StaffIncentiveStatement.objects.create(user=self.hq_user, campus=self.campus,
            month=self.lesson_date.replace(day=1), status='confirmed', user_name='HQ', campus_name=self.campus.name)
        incentive.lines.create(group=self.group, entry_key='n10-approved', line_type='earning',
                               order_number=self.group.order_number, event_date=self.lesson_date,
                               base_amount=10000, percent=10, amount=1000, is_deleted=True)
        self.assert_mark_blocked_by(('staff_incentive', '行政獎金'))
        incentive.status = 'draft'
        incentive.save(update_fields=['status'])
        self.assertEqual(self.mark().status_code, 200)

    def test_multiple_reasons_are_unique_and_returned_in_order(self):
        self.create_amendment('topup_reported')
        CancellationRequest.objects.create(group=self.group, reason='other', status='refunded')
        self.group.newebpay_form_issued = True
        self.group.save(update_fields=['newebpay_form_issued'])
        Payment.objects.create(reservation_group=self.group, status='paid', bank_posted_date=self.lesson_date)
        Payment.objects.create(reservation_group=self.group, status='refunded')
        self.assert_mark_blocked_by(
            ('payment_record', '付款紀錄'), ('bank_posted_date', '入帳日'), ('newebpay', '藍新表單'),
            ('refund', '退款'), ('amendment', '差額'),
        )

    def test_nonfinancial_records_still_allow_marking(self):
        # A bank account only counts on the same pending payment.
        Payment.objects.create(reservation_group=self.group, status='unpaid', bank_account='12345')
        Payment.objects.create(reservation_group=self.group, status='pending', bank_account='')
        Payment.objects.create(reservation_group=self.group, status='pending', DataJSON={'settlement': {}})
        self.create_amendment('topup_due')
        CancellationRequest.objects.create(group=self.group, reason='other', status='approved', actual_received_amount=0)
        self.assertEqual(self.mark().status_code, 200)

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

    def test_override_preserves_posted_financial_records_and_audits_all_blockers(self):
        module = ModuleInfo.objects.create(module_sid='booking', module_name='預約')
        ModuleSetting.objects.create(client=self.client_tenant, module=module,
                                     settings={'test_order_financial_override_enabled': True})
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000)
        payroll = self.payroll()
        payroll.status = 'confirmed'
        payroll.save(update_fields=['status'])
        payment = Payment.objects.create(reservation_group=self.group, status='paid',
                                         bank_posted_date=self.lesson_date, DataJSON={'gateway_response': {'ok': True}})
        self.group.newebpay_form_issued = True
        self.group.save(update_fields=['newebpay_form_issued'])
        StaffIncentiveRule.objects.create(user=self.hq_user, campus=self.campus, completed_order_percent=10)
        month = self.lesson_date.replace(day=1)
        incentive = calculate_staff_incentive(user=self.hq_user, campus=self.campus, month=month)
        self.assertEqual(incentive.earned_amount, 1000)
        incentive.status = 'paid'
        incentive.save(update_fields=['status'])
        cancellation = CancellationRequest.objects.create(group=self.group, reason='other', status='refunded',
            actual_received_amount=10000, refund_amount=1000, reviewed_at=timezone.make_aware(
                datetime.combine(self.lesson_date, time(11))))
        amendment = self.create_amendment('settled')
        loyalty = start_order_loyalty(self.group, 1, {**DEFAULT_RULES, 'enabled': True}, spent=0)
        sync_order_loyalty(self.group, confirmed_base=10000, refund=1000, actual_received_amount=10000)
        account = loyalty.account
        account.refresh_from_db()
        self.assertEqual((account.points, account.reward_balance), (9000, 360))

        def later_incentive():
            return calculate_staff_incentive(user=self.hq_user, campus=self.campus, month=date(2026, 2, 1))

        self.assertEqual(later_incentive().refund_deduction, 100)
        expected = (
            ('payment_record', '付款紀錄'), ('bank_posted_date', '入帳日'), ('newebpay', '藍新表單'),
            ('refund', '退款'), ('amendment', '差額'), ('loyalty', '紅利'),
            ('coach_payroll', '教練薪資'), ('staff_incentive', '行政獎金'),
        )
        self.assert_mark_blocked_by(*expected)
        records = [payment, amendment, cancellation, loyalty, account, payroll, incentive,
                   *payroll.lines.all(), *incentive.lines.all(), *MemberLoyaltyEntry.objects.filter(order=loyalty)]
        snapshots = [type(row)._base_manager.values().get(pk=row.pk) for row in records]
        self.assertGreater(self.hq.get(self.dashboard_url, {'period': 'today'}).data['data']['stats']['revenue'], 0)

        override = {'reason': '  已付費演練單  ', 'acknowledged_reasons': [code for code, _ in expected]}
        response = self.mark(**override)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.mark(**override).status_code, 200)
        self.group.refresh_from_db()
        self.assertTrue(self.group.is_test)
        revision = self.group.revisions.get(change_type='mark_test')
        self.assertEqual((revision.group_id, revision.created_by, revision.reason),
                         (self.group.pk, self.hq_user, '已付費演練單'))
        self.assertGreaterEqual(revision.created_at, self.group.test_marked_at)
        self.assertEqual(revision.snapshot['test_actor_name'], self.hq_user.username)
        self.assertEqual(revision.snapshot['test_override_reasons'],
                         [{'code': code, 'label': label} for code, label in expected])
        latest = self.hq.get(self.detail_url).data['data']['revisions'][0]
        self.assertEqual(latest['snapshot']['test_override_reasons'], revision.snapshot['test_override_reasons'])

        self.assertEqual(self.hq.get(self.dashboard_url, {'period': 'today'}).data['data']['stats']['revenue'], 0)
        with self.assertRaisesMessage(ValueError, '不能重新計算'):
            self.payroll()
        with self.assertRaisesMessage(ValueError, '不能重新計算'):
            calculate_staff_incentive(user=self.hq_user, campus=self.campus, month=month)
        self.assertEqual(later_incentive().refund_deduction, 0)
        sync_order_loyalty(self.group, refund=2000, actual_received_amount=10000)
        rebuild_loyalty_account(account)
        self.assertEqual((account.points, account.reward_balance), (9000, 360))
        self.assertEqual(MemberLoyaltyEntry.objects.filter(order=loyalty).count(), 1)
        self.assertEqual([type(row)._base_manager.values().get(pk=row.pk) for row in records], snapshots)

    def test_override_excludes_paid_order_from_draft_payroll_and_new_loyalty_accrual(self):
        CoachPayRule.objects.create(coach=self.coach, discipline='snowboard', hourly_rate=1000)
        Payment.objects.create(reservation_group=self.group, status='paid')
        payroll = self.payroll()
        payroll_lines = list(payroll.lines.values())
        self.assertGreater(payroll.total_amount, 0)
        StaffIncentiveRule.objects.create(user=self.hq_user, campus=self.campus, completed_order_percent=10)
        month = self.lesson_date.replace(day=1)
        incentive = calculate_staff_incentive(user=self.hq_user, campus=self.campus, month=month)
        self.assertEqual(incentive.earned_amount, 1000)
        loyalty = start_order_loyalty(self.group, 1, {**DEFAULT_RULES, 'enabled': True})
        self.assert_mark_blocked_by(('payment_record', '付款紀錄'))
        self.assertEqual(self.mark(acknowledged_reasons=['payment_record']).status_code, 200)
        self.assertEqual(list(payroll.lines.values()), payroll_lines)
        with self.assertRaisesMessage(ValueError, '獎金草稿含測試訂單'):
            confirm_staff_incentive(incentive, actor=self.hq_user)
        self.assertEqual(calculate_staff_incentive(user=self.hq_user, campus=self.campus, month=month).earned_amount, 0)
        self.group.refresh_from_db()
        sync_order_loyalty(self.group, confirmed_base=10000)
        loyalty.refresh_from_db()
        self.assertIsNone(loyalty.paid_base)
        self.assertFalse(MemberLoyaltyEntry.objects.filter(order=loyalty).exists())
        self.assertEqual(self.payroll().total_amount, 0)

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

    def test_new_customer_phone_lookup_keeps_ignoring_soft_deleted_payments(self):
        contact = {'phone': '0900000000'}
        payment = Payment.objects.create(reservation_group=self.group, DataJSON={'contact': contact})
        self.assertFalse(is_new_customer_for_discount(self.client_tenant, None, contact))

        self.assertEqual(self.mark().status_code, 200)
        self.assertTrue(is_new_customer_for_discount(self.client_tenant, None, contact))
        self.assertEqual(self.mark(False).status_code, 200)

        payment.is_deleted = True
        payment.save(update_fields=['is_deleted'])
        self.assertTrue(is_new_customer_for_discount(self.client_tenant, None, contact))
