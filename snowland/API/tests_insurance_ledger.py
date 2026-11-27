from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from importlib import import_module
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.apps import apps
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections, models, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.test import APIClient

from Client.models import Client, ModuleInfo, ModuleSetting
from Client.tenant_settings import insurance_ledger_settings
from Control.models import TenantStaffMembership, TenantStaffPosition
from Resorts.models import Campus
from booking.course_documents import capture_course_documents, save_course_documents
from booking.models import (
    InsuranceLedgerEntry, InsurancePrepaidAccount, InsuranceReconciliation, MemberDetail, Reservation, ReservationGroup,
)
from booking.operations import record_order_revision


BASE = '/api/admin/ledger-qa'
LEDGER = BASE + '/insurance-ledger/'
KIND = InsuranceLedgerEntry.Kind


def authenticated(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def processing_url(member):
    return f'{BASE}/insurance-records/{member.pk}/processing/'


def premium_data(amount, *, key=None, expected=None, status='processing', **fields):
    return {
        'status': status, 'premium_amount': amount, 'currency': 'JPY' if amount is not None else '',
        'expected_updated_at': expected, 'idempotency_key': str(key or uuid4()), **fields,
    }


class LedgerFixtures:
    def setup_ledger(self):
        self.tenant = Client.objects.create(name='Ledger QA', internal_code='ledger-qa')
        self.other = Client.objects.create(name='Other QA', internal_code='ledger-outside')
        self.campus = Campus.objects.create(client=self.tenant, name='First QA', code='first')
        self.other_campus = Campus.objects.create(client=self.tenant, name='Second QA', code='second')
        self.module = ModuleInfo.objects.create(module_sid='booking', module_name='Booking QA')
        self.config = ModuleSetting.objects.create(client=self.tenant, module=self.module, settings={
            'insurance_ledger_enabled': True, 'insurance_ledger_currency': 'jpy', 'existing_key': 'preserved',
        })
        self.staff = self.actor('insurance', None)
        self.financier = self.actor('hq_admin', ['insurance_ledger_finance'])
        self.finance = authenticated(self.financier)
        self.insurance = authenticated(self.staff)
        self.member = self.make_member()

    def actor(self, role, permissions, *, all_campuses=True):
        user = User.objects.create_user(f'qa-{role}-{uuid4().hex[:10]}')
        membership = TenantStaffMembership.objects.create(
            client=self.tenant, user=user, role=role, is_manager=role != 'coach', is_coach=role == 'coach',
            all_campuses=all_campuses, admin_permissions=permissions,
        )
        if not all_campuses:
            membership.campuses.add(self.campus)
        return user

    def make_member(self, campus=None, *, is_test=False):
        group = ReservationGroup.objects.create(client=self.tenant, campus=campus or self.campus, is_test=is_test)
        return MemberDetail.objects.create(reservation=Reservation.objects.create(group=group))

    def deposit_data(self, amount='100', *, kind=KIND.OPENING):
        return {'kind': kind, 'amount': amount, 'reference': 'QA 匯款核對', 'idempotency_key': str(uuid4())}

    def deposit(self, amount='100', *, kind=KIND.OPENING):
        response = self.finance.post(LEDGER + 'deposits/', self.deposit_data(amount, kind=kind), format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['data']

    def submit(self, amount, **kwargs):
        return self.insurance.post(processing_url(self.member), premium_data(amount, **kwargs), format='json')

    def change_settings(self, **updates):
        self.config.settings = {**self.config.settings, **updates}
        self.config.save(update_fields=['settings'])

    def assert_balance(self, expected):
        account = InsurancePrepaidAccount.objects.get(client=self.tenant)
        total = Decimal('0')
        entries = list(account.entries.order_by('sequence').select_related('reverses'))
        for number, entry in enumerate(entries, 1):
            credit = entry.kind in (KIND.OPENING, KIND.TOP_UP) or (
                entry.kind == KIND.REVERSAL and entry.reverses.kind == KIND.DEDUCTION
            )
            total += entry.amount if credit else -entry.amount
            self.assertEqual(entry.balance_after, total)
            self.assertEqual(entry.sequence, number)
        self.assertEqual(account.balance, Decimal(expected))
        self.assertEqual(account.balance, total)
        self.assertEqual(account.version, len(entries))


class InsuranceLedgerTests(LedgerFixtures, TestCase):
    def setUp(self):
        self.setup_ledger()

    def test_settings_are_typed_scoped_and_safe_when_missing_or_inactive(self):
        self.assertEqual(tuple(insurance_ledger_settings(self.other)), (False, '', None))
        self.change_settings(insurance_ledger_enabled='true', insurance_ledger_currency=123, insurance_ledger_low_balance=True)
        self.assertEqual(tuple(insurance_ledger_settings(self.tenant)), (False, '', None))
        self.change_settings(insurance_ledger_enabled=True, insurance_ledger_currency='', insurance_ledger_low_balance='100')
        self.assertEqual(tuple(insurance_ledger_settings(self.tenant)), (True, '', None))
        self.assertEqual(self.finance.post(LEDGER + 'deposits/', self.deposit_data(), format='json').status_code, 400)
        self.assertEqual(self.submit('5').status_code, 400)
        self.assertFalse(InsurancePrepaidAccount.objects.exists())
        self.change_settings(insurance_ledger_currency=' jpy ', insurance_ledger_low_balance=7.5)
        self.assertEqual(tuple(insurance_ledger_settings(self.tenant)), (True, 'JPY', Decimal('7.5')))
        self.config.refresh_from_db()
        self.assertEqual(self.config.settings['existing_key'], 'preserved')
        self.config.is_active = False
        self.config.save(update_fields=['is_active'])
        self.assertEqual(tuple(insurance_ledger_settings(self.tenant)), (False, '', None))
        self.config.is_active = True
        self.config.save(update_fields=['is_active'])
        self.module.is_active = False
        self.module.save(update_fields=['is_active'])
        self.assertEqual(tuple(insurance_ledger_settings(self.tenant)), (False, '', None))

    def test_deposit_roles_explicit_grant_campus_tenant_and_csrf(self):
        payload = self.deposit_data()
        forbidden_users = [
            self.staff, self.actor('assistant', None), self.actor('coach', ['insurance_ledger_finance']),
            self.actor('hq_admin', None), self.actor('hq_admin', ['insurance_ledger_finance'], all_campuses=False),
            User.objects.create_superuser('qa-platform', email='qa@example.test'),
        ]
        for user in forbidden_users:
            with self.subTest(user=user.pk):
                api = authenticated(user)
                self.assertEqual(api.get(LEDGER).status_code, 403)
                self.assertEqual(api.post(LEDGER + 'deposits/', payload, format='json').status_code, 403)
        self.assertEqual(self.finance.get(LEDGER, HTTP_X_CAMPUS_ID=str(self.campus.pk)).status_code, 403)
        self.assertEqual(self.finance.get(LEDGER.replace('ledger-qa', 'ledger-outside')).status_code, 403)
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(self.financier)
        self.assertEqual(api.post(LEDGER + 'deposits/', payload, format='json').status_code, 403)
        self.assertEqual(api.get(LEDGER).status_code, 200)
        csrf = api.cookies['csrftoken'].value
        self.assertEqual(api.post(LEDGER + 'deposits/', payload, format='json', HTTP_X_CSRFTOKEN=csrf).status_code, 200)
        self.assert_balance('100')

    def test_opening_and_top_up_validate_evidence_and_replay_with_low_balance_threshold(self):
        self.change_settings(insurance_ledger_low_balance=100)
        self.assertEqual(self.finance.post(LEDGER + 'deposits/', self.deposit_data(kind=KIND.TOP_UP), format='json').status_code, 400)
        payload = self.deposit_data()
        for changes in ({'amount': '0'}, {'reference': ' '}, {'amount': '2.555'}):
            self.assertEqual(self.finance.post(LEDGER + 'deposits/', {**payload, **changes}, format='json').status_code, 400)
        first = self.finance.post(LEDGER + 'deposits/', payload, format='json')
        repeat = self.finance.post(LEDGER + 'deposits/', payload, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data, repeat.data)
        self.assertEqual(self.finance.post(LEDGER + 'deposits/', {**payload, 'amount': '101'}, format='json').status_code, 400)
        self.assertTrue(self.finance.get(LEDGER).data['data']['low_balance'])
        self.deposit('0.01', kind=KIND.TOP_UP)
        self.assertFalse(self.finance.get(LEDGER).data['data']['low_balance'])
        self.assert_balance('100.01')

    def test_positive_deduction_has_version_and_is_replayed_before_stale_version_check(self):
        self.deposit()
        payload = premium_data('25.50')
        result = self.insurance.post(processing_url(self.member), payload, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        retry = self.insurance.post(processing_url(self.member), payload, format='json')
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assertEqual(self.insurance.post(processing_url(self.member), {**payload, 'premium_amount': '30'}, format='json').status_code, 400)
        self.member.refresh_from_db()
        entry = InsuranceLedgerEntry.objects.get(kind=KIND.DEDUCTION)
        self.assertEqual(entry.member_id, self.member.pk)
        self.assertEqual(entry.actor_id, self.staff.pk)
        self.assertEqual(entry.order_id, self.member.reservation.group_id)
        self.assertEqual(entry.idempotency_key, self.member.insurance_premium_ledger_key)
        self.assertEqual(self.member.insurance_premium_amount, Decimal('25.50'))
        self.assertIsNotNone(self.member.insurance_processing_updated_at)
        self.assert_balance('74.50')

    def test_neither_equal_amount_status_only_nor_blank_or_zero_deducts(self):
        self.deposit()
        first = self.submit('25')
        for amount in ('25.00', '0', '', None):
            first = self.submit(amount, expected=first.data['data']['insurance_processing_updated_at'], status='checking')
            self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(InsuranceLedgerEntry.objects.filter(kind=KIND.DEDUCTION).count(), 1)
        self.assertEqual(InsuranceLedgerEntry.objects.filter(kind=KIND.REVERSAL).count(), 0)
        self.assert_balance('75')

    def test_ineligible_rejects_new_deductions_and_preserves_existing_charge(self):
        self.change_settings(insurance_eligibility_enabled=True)
        self.deposit()
        first = self.submit('25')
        self.assertEqual(first.status_code, 200, first.data)
        deduction = InsuranceLedgerEntry.objects.get(kind=KIND.DEDUCTION)
        version = first.data['data']['insurance_processing_updated_at']

        invalid_mark = self.submit('30', status='ineligible', expected=version, correction_note='QA')
        self.assertEqual(invalid_mark.status_code, 400, invalid_mark.data)
        self.assertIn('不符投保資格時無法新增投保金額', invalid_mark.data['msg'])
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_processing_status, 'processing')

        marked = self.submit(None, status='ineligible', expected=version)
        self.assertEqual(marked.status_code, 200, marked.data)
        detail = self.insurance.get(processing_url(self.member).removesuffix('processing/')).data
        self.assertTrue(detail['premium_policy']['has_unreversed_deduction'])
        self.assertFalse(detail['premium_policy']['legacy_premium'])
        version = detail['insurance_processing_updated_at']
        self.member.refresh_from_db()
        updated_at = self.member.insurance_processing_updated_at

        for next_status in ('ineligible', 'checking'):
            with self.subTest(next_status=next_status):
                rejected = self.submit('30', status=next_status, expected=version, correction_note='QA')
                self.assertEqual(rejected.status_code, 400, rejected.data)
                self.assertIn('不符投保資格時無法新增投保金額', rejected.data['msg'])
                self.member.refresh_from_db()
                self.assertEqual(self.member.insurance_processing_status, 'ineligible')
                self.assertEqual(self.member.insurance_processing_updated_at, updated_at)
                self.assertEqual(self.member.insurance_premium_amount, Decimal('25'))
                self.assertEqual(self.member.insurance_premium_currency, 'JPY')
                self.assertEqual(self.member.insurance_premium_ledger_key, deduction.idempotency_key)
                self.assertEqual(InsuranceLedgerEntry.objects.filter(kind=KIND.DEDUCTION).count(), 1)
                self.assertFalse(InsuranceLedgerEntry.objects.filter(kind=KIND.REVERSAL).exists())
                self.assert_balance('75')

        restored = self.submit('25', status='checking', expected=version)
        self.assertEqual(restored.status_code, 200, restored.data)
        self.assert_balance('75')
        corrected = self.submit('30', expected=restored.data['data']['insurance_processing_updated_at'], correction_note='QA')
        self.assertEqual(corrected.status_code, 200, corrected.data)
        self.assertEqual(InsuranceLedgerEntry.objects.get(kind=KIND.REVERSAL).reverses_id, deduction.pk)
        self.assert_balance('70')

    def test_preexisting_preserved_premium_is_not_back_charged(self):
        self.change_settings(insurance_ledger_enabled=False)
        old = self.submit('25')
        self.assertEqual(old.status_code, 200, old.data)
        self.change_settings(insurance_ledger_enabled=True)
        self.deposit()
        new = self.submit('25', expected=old.data['data']['insurance_processing_updated_at'], status='checking')
        self.assertEqual(new.status_code, 200, new.data)
        detail = self.insurance.get(processing_url(self.member).removesuffix('processing/')).data
        self.assertTrue(detail['premium_policy']['legacy_premium'])
        self.assertFalse(InsuranceLedgerEntry.objects.filter(kind=KIND.DEDUCTION).exists())
        self.assert_balance('100')
        changed = self.submit('30', expected=new.data['data']['insurance_processing_updated_at'])
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(InsuranceLedgerEntry.objects.get(kind=KIND.DEDUCTION).amount, Decimal('30'))
        self.assertFalse(InsuranceLedgerEntry.objects.filter(kind=KIND.REVERSAL).exists())
        self.assert_balance('70')

    def test_member_detail_admin_post_cannot_change_premium_fields(self):
        self.deposit()
        result = self.submit('25')
        self.assertEqual(result.status_code, 200, result.data)
        self.member.refresh_from_db()
        ledger_key = self.member.insurance_premium_ledger_key
        admin_user = User.objects.create_superuser(username='ledger-qa-admin')
        self.client.force_login(admin_user)
        url = reverse('admin:booking_memberdetail_change', args=[self.member.pk])
        new_age = next(value for value, _ in MemberDetail.AGE_CHOICES if value != self.member.age_range)
        response = self.client.post(url, {
            'reservation': self.member.reservation_id,
            'filled_by': self.member.filled_by,
            'age_range': new_age,
            'insurance_premium_amount': '99',
            'insurance_premium_currency': 'TWD',
            'insurance_processing_status': 'ineligible',
            'insurance_premium_ledger_key': str(uuid4()),
            '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertEqual(self.member.age_range, new_age)
        self.assertEqual(self.member.insurance_premium_amount, Decimal('25'))
        self.assertEqual(self.member.insurance_premium_currency, 'JPY')
        self.assertEqual(self.member.insurance_processing_status, 'processing')
        self.assertEqual(self.member.insurance_premium_ledger_key, ledger_key)
        self.assert_balance('75')

    def test_deduction_requires_both_permissions_and_uses_member_scope(self):
        self.deposit()
        for actor, expected in [
            (self.actor('assistant', None), 403),
            (self.actor('insurance', ['insurance_ledger_deduct']), 403),
            (self.actor('coach', ['insurance_records', 'insurance_ledger_deduct']), 403),
            (self.actor('insurance', None, all_campuses=False), 404),
        ]:
            member = self.make_member(self.other_campus)
            api = authenticated(actor)
            self.assertEqual(api.post(processing_url(member), premium_data('40'), format='json').status_code, expected)
        self.assertEqual(self.insurance.post(processing_url(self.member).replace('ledger-qa', 'ledger-outside'),
                                             premium_data('20'), format='json').status_code, 403)
        self.assertEqual(self.submit('20', currency='TWD').status_code, 400)
        self.assert_balance('100')

    def test_insufficient_funds_rolls_back_status_and_premium_including_correction(self):
        self.deposit('50')
        too_high = self.submit('51')
        self.assertEqual(too_high.status_code, 400, too_high.data)
        self.assertIn('餘額不足', str(too_high.data['msg']))
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_processing_status, 'pending')
        self.assertIsNone(self.member.insurance_premium_amount)
        self.assert_balance('50')
        first = self.submit('45')
        self.assertEqual(first.status_code, 200, first.data)
        correction = self.submit('51', expected=first.data['data']['insurance_processing_updated_at'],
                                 correction_note='保險對帳差額', status='checking')
        self.assertEqual(correction.status_code, 400, correction.data)
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_processing_status, 'processing')
        self.assertEqual(self.member.insurance_premium_amount, Decimal('45'))
        self.assertFalse(InsuranceLedgerEntry.objects.filter(kind=KIND.REVERSAL).exists())
        self.assert_balance('5')

    def test_correction_is_one_reversal_and_one_replacement(self):
        self.deposit()
        first = self.submit('30')
        expected = first.data['data']['insurance_processing_updated_at']
        self.assertEqual(self.submit('40', expected=expected).status_code, 400)
        payload = premium_data('40', expected=expected, correction_note='原保費輸入誤差')
        second = self.insurance.post(processing_url(self.member), payload, format='json')
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(self.insurance.post(processing_url(self.member), payload, format='json').status_code, 200)
        entries = list(InsuranceLedgerEntry.objects.order_by('sequence'))
        self.assertEqual([row.kind for row in entries], [KIND.OPENING, KIND.DEDUCTION, KIND.REVERSAL, KIND.DEDUCTION])
        self.assertEqual(entries[2].reverses_id, entries[1].pk)
        self.assertEqual(entries[2].amount, Decimal('30'))
        self.assertEqual(entries[3].amount, Decimal('40'))
        self.assertEqual(entries[2].created_at, entries[3].created_at)
        self.assert_balance('60')

    def test_failure_after_ledger_write_rolls_back_entry_balance_and_processing(self):
        self.deposit()
        with patch.object(MemberDetail, 'save', side_effect=RuntimeError('QA failure after posting')):
            with self.assertRaisesMessage(RuntimeError, 'QA failure after posting'):
                self.submit('41')
        self.member.refresh_from_db()
        self.assertIsNone(self.member.insurance_premium_amount)
        self.assertEqual(self.member.insurance_processing_status, 'pending')
        self.assertFalse(InsuranceLedgerEntry.objects.filter(kind=KIND.DEDUCTION).exists())
        self.assert_balance('100')

    def test_explicit_finance_reversal_is_once_and_can_be_replayed(self):
        self.deposit()
        self.assertEqual(self.submit('35').status_code, 200)
        entry = InsuranceLedgerEntry.objects.get(kind=KIND.DEDUCTION)
        url = LEDGER + f'entries/{entry.pk}/reverse/'
        data = {'reference': 'QA 收到退款', 'note': '財務核對退款', 'idempotency_key': str(uuid4())}
        self.assertEqual(self.insurance.post(url, data, format='json').status_code, 403)
        first = self.finance.post(url, data, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data, self.finance.post(url, data, format='json').data)
        self.assertEqual(self.finance.post(url, {**data, 'idempotency_key': str(uuid4())}, format='json').status_code, 400)
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_premium_amount, Decimal('35'))
        self.assertTrue(self.insurance.get(processing_url(self.member).removesuffix('processing/')).data['premium_policy']['deduction_reversed'])
        self.assert_balance('100')

    def test_reschedule_clears_premium_and_new_premium_keeps_original_charge(self):
        self.deposit()
        insured = self.submit('23', status='insured', confirm_insured=True)
        self.assertEqual(insured.status_code, 200, insured.data)
        self.member.refresh_from_db()
        changes = capture_course_documents([self.member], [{'date': '2026-11-28'}], [{'date': '2026-11-29'}])
        self.change_settings(insurance_ledger_enabled=False)
        with self.assertRaises(ApiValidationError):
            with transaction.atomic():
                revision = record_order_revision(self.member.reservation.group, user=self.staff, reason='QA')
                save_course_documents(changes, revision, self.staff)
        self.member.refresh_from_db()
        self.assertEqual(self.member.insurance_premium_amount, Decimal('23'))
        self.change_settings(insurance_ledger_enabled=True)
        with transaction.atomic():
            revision = record_order_revision(self.member.reservation.group, user=self.staff, reason='QA')
            save_course_documents(changes, revision, self.staff)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.insurance_premium_amount)
        self.assertIsNone(self.member.insurance_premium_ledger_key)
        detail = self.insurance.get(processing_url(self.member).removesuffix('processing/')).data
        self.assertTrue(detail['premium_policy']['retained_deduction'])
        self.assertEqual(self.submit('25', expected=detail['insurance_processing_updated_at']).status_code, 200)
        self.assertEqual(InsuranceLedgerEntry.objects.filter(kind=KIND.DEDUCTION).count(), 2)
        self.assertFalse(InsuranceLedgerEntry.objects.filter(kind=KIND.REVERSAL).exists())
        self.assert_balance('52')

    def test_disabling_account_allows_reads_and_status_updates_but_blocks_positive_premium_changes(self):
        self.deposit()
        first = self.submit('25')
        entry = InsuranceLedgerEntry.objects.get(kind=KIND.DEDUCTION)
        self.change_settings(insurance_ledger_enabled=False)
        desk = self.finance.get(LEDGER).data['data']
        self.assertFalse(desk['writable'])
        self.assertEqual(len(desk['entries']), 2)
        self.assertEqual(self.finance.post(LEDGER + 'deposits/', self.deposit_data(kind=KIND.TOP_UP), format='json').status_code, 403)
        self.assertEqual(self.finance.post(LEDGER + f'entries/{entry.pk}/reverse/', {
            'reference': 'QA', 'note': 'QA', 'idempotency_key': str(uuid4()),
        }, format='json').status_code, 403)
        self.assertEqual(self.finance.post(LEDGER + 'reconciliation/', {
            'month': '2025-01', 'cutoff_sequence': 0, 'statement_balance': '0.00',
        }, format='json').status_code, 403)
        expected = first.data['data']['insurance_processing_updated_at']
        self.assertEqual(self.submit('30', expected=expected).status_code, 400)
        self.assertEqual(self.submit(None, expected=expected).status_code, 400)
        self.assertEqual(self.submit('25', expected=expected, status='checking').status_code, 200)
        another = self.make_member()
        self.assertEqual(self.insurance.post(processing_url(another), premium_data('10'), format='json').status_code, 400)
        self.assert_balance('75')

    def test_test_orders_cannot_be_charged_and_orders_with_entries_cannot_be_marked_test(self):
        self.deposit()
        test_member = self.make_member(is_test=True)
        self.assertEqual(self.insurance.post(processing_url(test_member), premium_data('10'), format='json').status_code, 404)
        self.assertEqual(self.submit('25').status_code, 200)
        mark_url = f'{BASE}/orders/{self.member.reservation.group_id}/test-status/'
        hq = self.actor('hq_admin', None)
        api = authenticated(hq)
        body = {'is_test': True, 'reason': 'QA 確認測試標記'}
        for payload in (body, {**body, 'acknowledged_reasons': ['payment_record']}):
            response = api.post(mark_url, payload, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('預付保費', str(response.data['msg']))
        self.assertFalse(ReservationGroup.objects.get(pk=self.member.reservation.group_id).is_test)
        self.assert_balance('75')

    def test_purging_learner_keeps_append_only_order_and_learner_evidence(self):
        self.deposit()
        self.assertEqual(self.submit('37').status_code, 200)
        member_id = self.member.pk
        order_id = self.member.reservation.group_id
        models.Model.delete(self.member)
        entry = InsuranceLedgerEntry.objects.get(kind=KIND.DEDUCTION)
        self.assertIsNone(entry.member_id)
        self.assertEqual(entry.member_record_id, member_id)
        self.assertEqual(entry.order_id, order_id)
        self.assert_balance('63')

    def test_monthly_reconciliation_uses_local_boundaries_and_freezes_confirmation(self):
        zone = ZoneInfo('Asia/Taipei')
        with patch('django.utils.timezone.now', return_value=datetime(2025, 3, 1, 0, 5, tzinfo=zone)):
            self.deposit('100')
            self.deposit('10', kind=KIND.TOP_UP)
            self.assertEqual(self.submit('25').status_code, 200)
            entry = InsuranceLedgerEntry.objects.get(kind=KIND.DEDUCTION)
            self.assertEqual(self.finance.post(LEDGER + f'entries/{entry.pk}/reverse/', {
                'reference': 'QA', 'note': '退款', 'idempotency_key': str(uuid4()),
            }, format='json').status_code, 200)
        with patch('django.utils.timezone.now', return_value=datetime(2025, 4, 1, 0, 1, tzinfo=zone)):
            self.deposit('20', kind=KIND.TOP_UP)
        self.assertEqual(len(self.finance.get(LEDGER, {'month': '2025-03'}).data['data']['entries']), 4)
        url = LEDGER + 'reconciliation/'
        preview = self.finance.get(url, {'month': '2025-03'}).data['data']
        self.assertEqual([preview[k] for k in ('opening', 'top_ups', 'deductions', 'reversals', 'closing')],
                         ['100.00', '10.00', '25.00', '25.00', '110.00'])
        payload = {'month': '2025-03', 'cutoff_sequence': preview['cutoff_sequence'], 'statement_balance': '110', 'note': '核對相符'}
        self.assertEqual(self.finance.post(url, {**payload, 'statement_balance': '111'}, format='json').status_code, 400)
        saved = self.finance.post(url, payload, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data['data']['note'], '核對相符')
        self.assertIsNotNone(saved.data['data']['confirmed_at'])
        self.assertEqual(self.finance.post(url, {**payload, 'note': '不能覆寫'}, format='json').data, saved.data)
        self.assertEqual(InsuranceReconciliation.objects.count(), 1)
        snapshot = InsuranceReconciliation.objects.get()
        with self.assertRaises(ValidationError):
            InsuranceReconciliation.objects.filter(pk=snapshot.pk).update(note='改寫')
        with self.assertRaises(ValidationError):
            snapshot.delete()
        self.assertEqual(self.finance.get(url, {'month': '2025-03'}).data['data'], saved.data['data'])
        self.assert_balance('130')

    def test_monthly_activity_can_exceed_the_account_balance_limit(self):
        month = '2025-03'
        with patch('django.utils.timezone.now', return_value=datetime(2025, 3, 2, tzinfo=ZoneInfo('Asia/Taipei'))):
            self.deposit('10')
            for _ in range(2):
                row = self.deposit('60000000000000', kind=KIND.TOP_UP)
                response = self.finance.post(LEDGER + f"entries/{row['id']}/reverse/", {
                    'reference': 'QA', 'note': '重複匯款沖回', 'idempotency_key': str(uuid4()),
                }, format='json')
                self.assertEqual(response.status_code, 200, response.data)
        self.assert_balance('10')
        url = LEDGER + 'reconciliation/'
        preview = self.finance.get(url, {'month': month}).data['data']
        self.assertEqual(preview['top_ups'], '120000000000000.00')
        self.assertEqual(preview['reversals'], '-120000000000000.00')
        confirm = self.finance.post(url, {
            'month': month, 'cutoff_sequence': preview['cutoff_sequence'], 'statement_balance': '10.00',
        }, format='json')
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.assertEqual(confirm.data['data']['top_ups'], preview['top_ups'])

    def test_ledger_entries_reject_instance_and_queryset_mutations(self):
        self.deposit()
        row = InsuranceLedgerEntry.objects.get()
        row.note = '不得改寫'
        for mutation in (
            row.save, row.delete, lambda: InsuranceLedgerEntry.objects.filter(pk=row.pk).update(note='不得改寫'),
            lambda: InsuranceLedgerEntry.objects.filter(pk=row.pk).delete(),
        ):
            with self.assertRaises(ValidationError):
                mutation()
        self.assert_balance('100')

    def test_seed_is_reversible_idempotent_and_preserves_custom_positions(self):
        migration = import_module('Control.migrations.0013_insurance_ledger_deduct_permission')
        school = Client.objects.create(name='QA', internal_code='snowland')
        base = ['insurance_records']
        position = TenantStaffPosition.objects.create(
            client=school, name='保險人員（預設）', role='insurance', all_campuses=True, permissions=base,
        )
        custom = TenantStaffPosition.objects.create(
            client=school, name='自訂職位', role='insurance', all_campuses=True, permissions=base,
        )
        membership = TenantStaffMembership.objects.create(
            client=school, user=self.staff, role='insurance', is_manager=True, all_campuses=True, admin_permissions=base,
        )
        membership.positions.add(position)
        schema = SimpleNamespace(connection=connection)
        migration.grant(apps, schema)
        migration.grant(apps, schema)
        position.refresh_from_db()
        membership.refresh_from_db()
        custom.refresh_from_db()
        self.assertEqual(position.permissions, [*base, 'insurance_ledger_deduct'])
        self.assertEqual(membership.admin_permissions, position.permissions)
        self.assertEqual(custom.permissions, base)
        migration.revoke(apps, schema)
        migration.revoke(apps, schema)
        position.refresh_from_db()
        membership.refresh_from_db()
        self.assertEqual(position.permissions, base)
        self.assertEqual(membership.admin_permissions, base)


class ConcurrentInsuranceLedgerTests(LedgerFixtures, TransactionTestCase):
    def setUp(self):
        self.setup_ledger()
        self.deposit('60')

    def in_parallel(self, jobs):
        start = Barrier(len(jobs), timeout=10)
        user_id = self.staff.pk

        def submit(job):
            close_old_connections()
            try:
                user = User.objects.get(pk=user_id)
                start.wait()
                return authenticated(user).post(*job, format='json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            return list(pool.map(submit, jobs))

    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_deductions_cannot_overspend(self):
        other = self.make_member()
        results = self.in_parallel([
            (processing_url(self.member), premium_data('40')),
            (processing_url(other), premium_data('40')),
        ])
        self.assertEqual(sorted(results), [200, 400])
        self.assertEqual(InsuranceLedgerEntry.objects.filter(kind=KIND.DEDUCTION).count(), 1)
        self.assertEqual(MemberDetail.objects.filter(insurance_premium_amount=40).count(), 1)
        self.assert_balance('20')

    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_replay_of_one_uuid_posts_once(self):
        job = (processing_url(self.member), premium_data('40'))
        self.assertEqual(self.in_parallel([job, job]), [200, 200])
        self.assertEqual(InsuranceLedgerEntry.objects.filter(kind=KIND.DEDUCTION).count(), 1)
        self.assert_balance('20')
