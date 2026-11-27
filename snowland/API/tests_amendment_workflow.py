from datetime import date
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from API import tests_order_amendment_confirm as fixtures
from Client.models import ModuleInfo, ModuleSetting
from Control.models import TenantStaffMembership
from booking.amendment_workflow import PAYMENT_LINK_MAX_AGE, available_refund
from booking.models import OrderAmendmentEvent, Payment


class AmendmentWorkflowTests(TestCase):
    def setUp(self):
        fixtures.OrderAmendmentConfirmTests.setUp(self)
        self.order_url = self.url.removesuffix('amendment-quote/')
        self.workflow_url = self.order_url + 'amendment-workflow/'
        self.balances_url = self.order_url + 'amendment-balances/'
        self.member_url = f'/booking/snowland/api/member-amendments/{self.group.pk}/'
        self.module = ModuleInfo.objects.create(module_sid='booking', module_name='預約')
        TenantStaffMembership.objects.create(
            client=self.tenant, user=self.superuser, role='hq_admin', is_manager=True,
            admin_permissions=['order_charge_operate', 'order_amendment_refund_request', 'order_amendment_refund_review'],
        )
        gateway = patch('booking.api_views.neweb_pay_request', side_effect=AssertionError('unexpected gateway call'))
        gateway.start()
        self.addCleanup(gateway.stop)

    def feature(self, value):
        settings, _ = ModuleSetting.objects.get_or_create(client=self.tenant, module=self.module)
        settings.settings = {**settings.settings, 'order_refund_charge_enabled': value}
        settings.save(update_fields=['settings'])
        return settings

    def actor(self, role, permissions, *, manager=True, tenant=None):
        user = User.objects.create_user(str(uuid4()))
        TenantStaffMembership.objects.create(
            user=user, client=tenant or self.tenant, is_manager=manager,
            is_coach=role == 'coach', role=role, admin_permissions=permissions, all_campuses=True,
        )
        api = APIClient()
        api.force_authenticate(user)
        return api

    def amend(self, **changes):
        response = self.api.post(self.url_confirm, fixtures.OrderAmendmentConfirmTests.body(self, **changes), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return self.group.amendments.get(pk=response.data['data']['id'])

    def refund(self):
        self.reservation.number_of_people = 2
        self.reservation.course_fee = 12000
        self.reservation.save()
        return self.amend(number_of_people=1, retained_member_ids=[self.member.pk])

    def payload(self, row, action, **values):
        row.refresh_from_db()
        native = row.currency_snapshot
        return {
            'amendment_id': row.pk, 'request_key': str(uuid4()), 'expected_updated_at': row.updated_at.isoformat(),
            'action': action, 'note': 'QA 作業依據', 'currency': native.get('currency', 'TWD'),
            'expected_amount': abs(native.get('balance_amount', row.balance_amount)), **values,
        }

    def post(self, row, action, *, api=None, expected=200, **values):
        response = (api or self.api).post(self.workflow_url, self.payload(row, action, **values), format='json')
        self.assertEqual(response.status_code, expected, response.data)
        return response

    def member_api(self):
        api = APIClient()
        api.force_authenticate(self.manager)
        return api

    def test_feature_defaults_off_and_inactive_or_non_boolean_values_are_off(self):
        row = self.amend()
        self.post(row, 'mark_topup_notified', expected=403)
        for value in ('true', 1, None, False):
            self.feature(value)
            self.post(row, 'mark_topup_notified', expected=403)
        config = self.feature(True)
        config.is_active = False
        config.save(update_fields=['is_active'])
        self.post(row, 'mark_topup_notified', expected=403)
        config.is_active = True
        config.save(update_fields=['is_active'])
        self.module.is_active = False
        self.module.save(update_fields=['is_active'])
        self.post(row, 'mark_topup_notified', expected=403)
        self.assertFalse(OrderAmendmentEvent.objects.exists())

    def test_explicit_tenant_campus_and_role_permissions(self):
        self.feature(True)
        row = self.amend()
        for role, grants in (
            ('hq_admin', None), ('hq_admin', ['orders']), ('assistant', None),
            ('assistant', ['order_payments']), ('coach', ['order_payments', 'order_charge_operate']),
        ):
            self.post(row, 'mark_topup_notified', api=self.actor(role, grants), expected=403)
        operator = self.actor('assistant', ['order_payments', 'order_charge_operate'])
        body = self.payload(row, 'mark_topup_notified')
        self.assertEqual(operator.post(self.workflow_url, body, format='json', HTTP_X_CAMPUS_ID=self.campus_b.pk).status_code, 404)
        foreign = self.actor('hq_admin', ['order_payments', 'order_charge_operate'], tenant=self.other_tenant)
        self.assertEqual(foreign.post(self.workflow_url, body, format='json').status_code, 403)
        self.assertEqual(self.api.post(self.workflow_url.replace('/snowland/', '/other/'), body, format='json').status_code, 403)
        self.post(row, 'mark_topup_notified', api=operator)

    def test_csrf_is_required_for_session_workflow_posts(self):
        self.feature(True)
        row = self.amend()
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(self.superuser)
        body = self.payload(row, 'mark_topup_notified')
        self.assertEqual(api.post(self.workflow_url, body, format='json').status_code, 403)
        self.assertEqual(api.get(self.balances_url).status_code, 200)
        self.assertEqual(api.post(self.workflow_url, body, format='json', HTTP_X_CSRFTOKEN=api.cookies['csrftoken'].value).status_code, 200)

    def test_member_link_and_reporting_legacy_topup_reconcile_when_disabled(self):
        self.feature(True)
        row = self.amend()
        response = self.api.get(self.workflow_url, {'amendment_id': row.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['path'], f'/snowland/membership/orders/{self.group.pk}#amendment-{row.pk}')
        self.post(row, 'record_topup', expected=409, confirmed=True, external_reference='QA-01')
        self.feature(False)
        self.post(row, 'mark_topup_notified', expected=403)
        body = self.payload(row, 'report_topup', reference='12345')
        body.pop('note')
        self.assertEqual(self.member_api().post(self.member_url, body, format='json').status_code, 200)
        body = self.payload(row, 'confirm_topup', confirmed=True)
        self.assertEqual(self.api.post(self.balances_url, body, format='json').status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.status, 'settled')

    def test_guest_link_is_bound_expiring_and_stops_after_void_or_settlement(self):
        self.feature(True)
        self.group.user = None
        self.group.save(update_fields=['user'])
        self.payment.bank_posted_date = date(2026, 11, 4)
        self.payment.save(update_fields=['bank_posted_date'])
        row = self.amend()
        response = self.api.get(self.workflow_url, {'amendment_id': row.pk})
        self.assertEqual(response.status_code, 200)
        parts = urlsplit(response.data['data']['path'])
        access = parse_qs(parts.fragment)['access'][0]
        url = f'/booking/snowland/api/amendment-topup/{self.group.pk}/{row.pk}/'
        guest = APIClient()
        self.assertEqual(guest.get(url).status_code, 404)
        self.assertEqual(guest.get(url.replace('/snowland/', '/other/'), HTTP_X_AMENDMENT_ACCESS=access).status_code, 404)
        wrong_amendment = f'/booking/snowland/api/amendment-topup/{self.group.pk}/{row.pk + 1}/'
        self.assertEqual(guest.get(wrong_amendment, HTTP_X_AMENDMENT_ACCESS=access).status_code, 404)
        with patch('django.core.signing.TimestampSigner.timestamp', return_value='1'):
            expired = self.api.get(self.workflow_url, {'amendment_id': row.pk})
        expired_access = parse_qs(urlsplit(expired.data['data']['path']).fragment)['access'][0]
        self.assertEqual(PAYMENT_LINK_MAX_AGE, 30 * 86400)
        self.assertEqual(guest.get(url, HTTP_X_AMENDMENT_ACCESS=expired_access).status_code, 404)
        self.bank.account_number = 'QA-NEW'
        self.bank.save(update_fields=['account_number'])
        response = guest.get(url, HTTP_X_AMENDMENT_ACCESS=access)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['currency'], response.data['amount']), ('TWD', 2000))
        self.assertEqual(response.data['bank']['account_number'], 'QA-12345')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.post(row, 'mark_topup_notified')
        self.assertEqual(guest.get(url, HTTP_X_AMENDMENT_ACCESS=access).status_code, 200)
        row.status = 'superseded'
        row.save(update_fields=['status'])
        self.assertEqual(guest.get(url, HTTP_X_AMENDMENT_ACCESS=access).status_code, 404)
        row.status = 'topup_due'
        row.save(update_fields=['status'])
        for value in (0, -1, 2001):
            self.post(row, 'record_topup', expected=400, expected_amount=value, confirmed=True, external_reference='QA-17')
        self.post(row, 'record_topup', confirmed=True, external_reference='QA-17')
        self.assertEqual(guest.get(url, HTTP_X_AMENDMENT_ACCESS=access).status_code, 404)
        self.assertEqual(self.api.get(self.workflow_url, {'amendment_id': row.pk}).status_code, 409)
        self.payment.refresh_from_db()
        self.assertEqual((self.payment.status, self.payment.bank_posted_date), ('paid', date(2026, 11, 4)))
        self.assertEqual(Payment.objects.filter(reservation_group=self.group).count(), 1)

    def test_refund_requires_full_amount_review_and_idempotent_external_result(self):
        self.feature(True)
        row = self.refund()
        requester = self.actor('assistant', ['order_payments', 'order_amendment_refund_request'])
        reviewer = self.actor('hq_admin', ['order_payments', 'order_amendment_refund_review'])
        for value in (0, -1, 1000, 2001):
            self.post(row, 'request_refund', api=requester, expected=400, expected_amount=value)
        self.post(row, 'request_refund', api=requester, expected=400, note='')
        self.post(row, 'request_refund', api=requester)
        self.post(row, 'approve_refund', api=requester, expected=403)
        self.post(row, 'record_refund', api=reviewer, confirmed=True, external_reference='QA-R1', expected=409)
        self.post(row, 'reject_refund', api=reviewer, confirmed=True)
        self.post(row, 'request_refund', api=requester)
        self.post(row, 'approve_refund', api=reviewer)
        self.post(row, 'record_refund', api=reviewer, confirmed=True, expected=400)
        body = self.payload(row, 'record_refund', confirmed=True, external_reference='QA-R1')
        first = reviewer.post(self.workflow_url, body, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertTrue(reviewer.post(self.workflow_url, body, format='json').data['duplicate'])
        self.post(row, 'record_refund', api=reviewer, confirmed=True, external_reference='QA-R2', expected=409)
        event = row.events.get(action='record_refund')
        self.assertEqual(event.payload['external_reference'], 'QA-R1')
        self.assertEqual(event.payload['settlement']['amount'], 2000)
        self.assertEqual(event.payload['settlement']['currency'], 'TWD')
        self.assertEqual(row.events.count(), 5)

    def test_refund_uses_actual_cash_and_blocks_cancellation_and_legacy_bypass(self):
        self.feature(True)
        row = self.refund()
        bank = {'bank_name': 'QA', 'account_number': 'QA-1234', 'account_holder': 'QA'}
        account = self.payload(row, 'refund_account', bank=bank)
        account.pop('note')
        self.assertEqual(self.member_api().post(self.member_url, account, format='json').status_code, 200)
        self.payment.DataJSON = {'settlement': {
            'currency': 'TWD', 'amount': 1000, 'base_currency': 'TWD', 'base_amount': 1000,
            'rate': '1', 'locked_at': None, 'confirmed_at': '2026-11-01',
        }}
        self.payment.save(update_fields=['DataJSON'])
        self.post(row, 'request_refund', expected=409)
        self.payment.DataJSON['settlement'].update(amount=11500, base_amount=11500)
        self.payment.save(update_fields=['DataJSON'])
        self.post(row, 'request_refund')
        self.post(row, 'approve_refund')
        body = self.payload(row, 'refund_account', bank=bank)
        body.pop('note')
        self.assertEqual(self.member_api().post(self.member_url, body, format='json').status_code, 409)
        self.feature(False)
        self.post(row, 'record_refund', confirmed=True, external_reference='QA-R2', expected=403)
        self.assertEqual(self.api.post(self.balances_url, self.payload(row, 'confirm_refund', confirmed=True), format='json').status_code, 403)
        cancel = {'reason': 'other', 'refund_bank': bank}
        response = self.api.post(self.order_url + 'cancel/', cancel, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('差額退款處理中', str(response.data))
        self.feature(True)
        self.post(row, 'reject_refund', confirmed=True)
        response = self.api.post(self.order_url + 'cancel/', cancel, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.post(row, 'request_refund', expected=409)

    def test_test_order_rehearses_without_clearing_test_flag_or_appearing_in_default_reconciliation(self):
        self.feature(True)
        self.group.is_test = True
        self.group.save(update_fields=['is_test'])
        self.payment.status = 'unpaid'
        self.payment.save(update_fields=['status'])
        row = self.amend()
        self.assertEqual(row.status, 'topup_due')
        self.assertEqual(self.api.get(self.workflow_url, {'amendment_id': row.pk}).status_code, 409)
        self.assertEqual(self.member_api().get(self.member_url).data['items'], [])
        list_url = '/api/admin/snowland/orders/'
        params = {'workflow': 'payments', 'balance_status': 'topup'}
        self.assertEqual(self.api.get(list_url, params).data['data']['total'], 0)
        self.assertEqual(self.api.get(list_url, {**params, 'include_test': 1}).data['data']['total'], 1)
        self.post(row, 'mark_topup_notified')
        self.post(row, 'record_topup', confirmed=True, external_reference='QA-REHEARSAL')
        refund = self.amend(number_of_people=1, retained_member_ids=[self.member.pk])
        self.post(refund, 'request_refund')
        self.post(refund, 'approve_refund')
        self.post(refund, 'record_refund', confirmed=True, external_reference='QA-REFUND')
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'unpaid')
        self.assertEqual(self.api.get(list_url, {
            'workflow': 'payments', 'balance_status': 'record_refund', 'include_test': 1,
        }).data['data']['total'], 1)
        response = self.api.post(self.order_url + 'test-status/', {'is_test': False, 'reason': 'QA'}, format='json')
        self.assertEqual(response.status_code, 409, response.data)

    def test_foreign_refund_cap_counts_only_settled_original_currency_adjustments(self):
        self.feature(True)
        self.group.currency_snapshot = {
            'currency': 'JPY', 'base_currency': 'TWD', 'rate': '4.50000000', 'locked_at': None,
            'bank_info': {'bank_name': 'QA', 'bank_account_number': 'QA-1234', 'bank_account_holder': 'QA'},
        }
        self.group.save(update_fields=['currency_snapshot'])
        self.payment.DataJSON = {'settlement': {
            **self.group.currency_snapshot, 'amount': 42750, 'base_amount': 9500, 'confirmed_at': '2026-11-01',
        }}
        self.payment.save(update_fields=['DataJSON'])
        topup = self.amend()
        self.assertEqual(available_refund(self.group, self.payment, 'JPY'), 42750)
        self.group.user = None
        self.group.save(update_fields=['user'])
        self.post(topup, 'record_topup', confirmed=True, external_reference='QA-J1')
        self.assertEqual(available_refund(self.group, self.payment, 'JPY'), 51750)
        refund = self.amend(number_of_people=1, retained_member_ids=[self.member.pk])
        self.post(refund, 'request_refund', expected_amount=2000, expected=400)
        self.post(refund, 'request_refund')
        self.post(refund, 'approve_refund')
        self.post(refund, 'record_refund', confirmed=True, external_reference='QA-J2')
        self.assertEqual(available_refund(self.group, self.payment, 'JPY'), 42750)
        self.assertEqual(available_refund(self.group, self.payment, 'TWD'), 0)
