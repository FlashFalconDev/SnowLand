"""Run with verify-snowland-order-archive-mysql.ps1 on its fresh MySQL container."""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time, timedelta
from io import StringIO
from pathlib import Path
from threading import Event
from time import perf_counter, sleep
from unittest.mock import patch
from uuid import uuid4

import django
import pymysql

DATABASE = 'snowland_order_cleanup_isolated'
TENANT = 'archive-mysql-fixture'
ORDER_COUNT = 120


def prepare_database(port):
    if not 1024 < port <= 65535 or not os.environ.get('MYSQL_PASSWORD'):
        raise SystemExit('Expected the dedicated MySQL container and generated credentials')
    credentials = dict(host='127.0.0.1', port=port, user='archive_test',
                       password=os.environ['MYSQL_PASSWORD'], database=DATABASE)
    for _ in range(60):
        try:
            with pymysql.connect(**credentials) as database, database.cursor() as cursor:
                cursor.execute('SHOW TABLES')
                if cursor.fetchone() is not None:
                    raise SystemExit('Expected a fresh rehearsal database')
            break
        except pymysql.Error:
            sleep(1)
    else:
        raise SystemExit('Isolated MySQL did not become ready')

    os.environ.update(DJANGO_SETTINGS_MODULE='snowland.settings', Mysql_HOST=credentials['host'],
                      Mysql_PORT=str(port), Mysql_NAME=DATABASE)
    # On Linux the settings keys are case sensitive. Windows aliases both case forms.
    os.environ['Mysql_USER'] = credentials['user']
    os.environ['Mysql_PASSWORD'] = credentials['password']
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'snowland'))
    django.setup()
    from django.core.management import call_command
    from django.db import connection

    config = connection.settings_dict
    assert connection.vendor == 'mysql' and config['NAME'] == DATABASE
    assert config['HOST'] == '127.0.0.1' and int(config['PORT']) == port
    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION(), @@transaction_isolation')
        print('MySQL version/isolation:', *cursor.fetchone(), flush=True)
    call_command('migrate', interactive=False, verbosity=0)


def verify_archive():
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.core.management.base import CommandError
    from django.db import IntegrityError, connection, connections, transaction
    from django.test import RequestFactory
    from rest_framework.test import APIRequestFactory, force_authenticate

    from Client.models import Client
    from Coach.models import Coach, PayrollLine, PayrollStatement, StaffIncentiveLine, StaffIncentiveStatement
    from Coursekit.models import DiscountCode
    from Resorts.models import Campus
    from booking.call_back import call_back
    from booking.management.commands import soft_delete_tenant_orders as command_module
    from booking.models import (
        Booking, MemberDetail, MemberLoyaltyAccount, MemberLoyaltyEntry, OrderDiscountUsage, OrderLoyalty,
        Payment, Reservation, ReservationGroup, TenantOrderArchiveBatch,
    )
    from booking.order_archive import SCOPES
    from booking.views import API as legacy_booking_api

    with transaction.atomic():
        tenant = Client.objects.create(name='Synthetic MySQL archive', internal_code=TENANT)
        other = Client.objects.create(name='Synthetic unaffected tenant', internal_code='archive-mysql-other')
        other_order = ReservationGroup.objects.create(client=other)
        users = get_user_model().objects
        actor = users.create_superuser('archive-mysql-operator')
        buyer = users.create_user('archive-mysql-buyer')
        staff = users.create_user('archive-mysql-staff')
        campus = Campus.objects.create(client=tenant, name='Synthetic campus', code='mysql')
        coach = Coach.objects.create(client=tenant, name='Synthetic coach')
        account = MemberLoyaltyAccount.objects.create(
            client=tenant, user=buyer, previous_points=17, points=20 + ORDER_COUNT * 10,
            reward_balance=-4 + ORDER_COUNT * 2,
        )
        rule = DiscountCode.objects.create(client=tenant, code='MYSQL-FIXTURE', used_count=ORDER_COUNT,
                                          legacy_used_count=0)
        incentive = StaffIncentiveStatement.objects.create(campus=campus, user=staff, month=date(2026, 1, 1))
        for i in range(ORDER_COUNT):
            day = date(2026, 1, 1) + timedelta(days=i)
            group = ReservationGroup.objects.create(client=tenant, campus=campus, user=buyer)
            reservation = Reservation.objects.create(group=group, status='completed', course_fee=900)
            booking = Booking.objects.create(reservation=reservation, date=day, start_time=time(9), end_time=time(11))
            MemberDetail.objects.bulk_create([MemberDetail(reservation=reservation, user=buyer),
                                              MemberDetail(reservation=reservation, is_active=False)])
            Payment.objects.create(reservation_group=group, status='paid')
            callback_payment = Payment.objects.create(reservation_group=group, status='unpaid')
            payroll = PayrollStatement.objects.create(
                campus=campus, coach=coach, period_start=day, period_end=day, status='confirmed',
            )
            PayrollLine.objects.create(statement=payroll, booking=booking, line_type='course', total_amount=900)
            StaffIncentiveLine.objects.create(statement=incentive, group=group, entry_key=f'earn:{i}',
                                              line_type='earning', event_date=day, base_amount=900, percent=10, amount=90)
            loyalty = OrderLoyalty.objects.create(group=group, account=account, policy_revision=1, rules={})
            MemberLoyaltyEntry.objects.create(account=account, order=loyalty, kind='purchase',
                                              points_delta=10, rewards_delta=2)
            OrderDiscountUsage.objects.create(reservation=reservation, rule_id=rule.pk, checkout_key=uuid4())

    def run(*args):
        output = StringIO()
        start = perf_counter()
        try:
            call_command('soft_delete_tenant_orders', '--client-code', TENANT, *args, stdout=output)
        except CommandError as exc:
            return str(exc), perf_counter() - start
        return output.getvalue().strip(), perf_counter() - start

    expected = dict.fromkeys((scope.label for scope in SCOPES), 0)
    for model in (ReservationGroup, Reservation, Booking, PayrollStatement, PayrollLine,
                  StaffIncentiveLine, OrderLoyalty, MemberLoyaltyEntry):
        expected[model._meta.label] = ORDER_COUNT
    expected[Payment._meta.label] = expected[MemberDetail._meta.label] = ORDER_COUNT * 2
    expected[StaffIncentiveStatement._meta.label] = 1
    preview, preview_seconds = run('--dry-run')
    report = preview.splitlines()
    assert {line.split()[0]: int(line.split('pending=')[1].split()[0]) for line in report[:-1]} == expected
    assert all('conflicts=0' in line and 'in_flight=0' in line for line in report[:-1])
    assert not TenantOrderArchiveBatch.objects.filter(client=tenant).exists()
    digest = report[-1].removeprefix('plan_digest=')
    args = ('--apply', '--confirm-client-code', TENANT, '--expected-plan-digest', digest, '--actor-id', str(actor.pk))

    winner_has_locks, contender_started = Event(), Event()
    original_apply, original_tenant = command_module.apply_archive, command_module.Command.tenant

    def hold_first_worker(*args):
        winner_has_locks.set()
        assert contender_started.wait(timeout=15), 'Second worker did not reach the tenant lookup'
        return original_apply(*args)

    def check_contender(queryset, code):
        if winner_has_locks.is_set():
            contender_started.set()
        return original_tenant(queryset, code)

    def worker():
        try:
            return run(*args)
        finally:
            connections.close_all()

    with patch.object(command_module, 'apply_archive', side_effect=hold_first_worker), patch.object(
        command_module.Command, 'tenant', side_effect=check_contender,
    ), ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(worker)
        assert winner_has_locks.wait(timeout=15), 'First worker did not reach the write phase'
        contender = pool.submit(worker)
        applied, apply_seconds = winner.result(timeout=45)
        declined, declined_seconds = contender.result(timeout=45)

    assert applied.startswith('batch='), applied
    assert '計畫已變動' in declined, declined
    batch = TenantOrderArchiveBatch.objects.get(client=tenant)
    assert str(batch.pk) == applied.removeprefix('batch=')
    assert {label: len(ids) for label, ids in batch.targets.items()} == expected
    for scope in SCOPES:
        rows = scope.tenant_rows(tenant)
        assert rows.count() == rows.filter(is_deleted=True, deleted_by=actor).count() == expected[scope.label]
        assert not rows.live().exists(), scope.label
    assert ReservationGroup.objects.filter(pk=other_order.pk).exists()
    account.refresh_from_db()
    rule.refresh_from_db()
    assert (account.points, account.reward_balance, rule.used_count) == (20, -4, 0)

    request = RequestFactory().post(f'/call_back/NewebPay/?client_code={TENANT}', {
        'MerchantID': 'fixture-merchant', 'TradeInfo': 'fixture-body', 'TradeSha': 'A' * 64,
    })
    payload = {'Status': 'SUCCESS', 'Result': {'MerchantOrderNo': str(group.pk), 'Amt': '900'}}
    credentials = dict(MerchantID='fixture-merchant', HashKey='fixture-key', HashIV='fixture-iv')
    with patch('booking.call_back.gateway_settings', return_value=credentials), patch(
        'booking.call_back.sha256_hash', return_value='A' * 64,
    ), patch('booking.call_back.aes256_cbc_decrypt', return_value=json.dumps(payload)):
        callback = call_back(request, 'NewebPay')
    assert callback.status_code == 409 and b'Archived order' in callback.content
    callback_payment.refresh_from_db()
    assert callback_payment.status == 'unpaid' and callback_payment.DataJSON == {}
    account.refresh_from_db()
    assert (account.points, account.reward_balance) == (20, -4)
    assert run('--apply', '--confirm-client-code', TENANT, '--actor-id', str(actor.pk),
               '--expected-plan-digest', run('--dry-run')[0].split('plan_digest=')[1])[0] == 'pending=0'

    restored, restore_seconds = run('--restore', '--batch', str(batch.pk), '--actor-id', str(actor.pk))
    assert restored == f'restored_batch={batch.pk}', restored
    for scope in SCOPES:
        rows = scope.tenant_rows(tenant)
        assert rows.live().filter(deleted_at=None, deleted_by=None).count() == expected[scope.label], scope.label
    account.refresh_from_db()
    rule.refresh_from_db()
    batch.refresh_from_db()
    assert batch.restored_at and batch.restored_by_id == actor.pk
    assert (account.points, account.reward_balance, rule.used_count) == (20 + ORDER_COUNT * 10, -4 + ORDER_COUNT * 2, ORDER_COUNT)
    for model, key in (
        (PayrollStatement, dict(campus=campus, coach=coach, period_start=day, period_end=day)),
        (StaffIncentiveStatement, dict(campus=campus, user=staff, month=incentive.month)),
    ):
        try:
            with transaction.atomic():
                model.objects.create(**key)
        except IntegrityError:
            pass
        else:
            raise AssertionError(f'{model._meta.label} duplicate key was accepted')
    assert ReservationGroup.objects.filter(pk=other_order.pk).exists()
    print(f'PASS {ORDER_COUNT} orders, {sum(expected.values())} archived/restored rows across '
          f'{sum(count > 0 for count in expected.values())}/24 populated scopes')
    print(f'dry-run={preview_seconds:.3f}s apply={apply_seconds:.3f}s contender={declined_seconds:.3f}s '
          f'restore={restore_seconds:.3f}s callback={callback.status_code}')
    print('PASS stale digest rejected, one batch, retry is no-op, callback unchanged, balances and unique keys restored')

    # Reuse the same restored rows to race a normal write against a fresh apply.
    winner_has_locks.clear()
    contender_started.clear()

    def watch_legacy_lock(execute, sql, params, many, context):
        if 'booking_reservationgroup' in sql and 'FOR UPDATE' in sql:
            contender_started.set()
        return execute(sql, params, many, context)

    def legacy_write():
        request = APIRequestFactory().post('/booking/api/member_detail/', {
            'user_id': buyer.pk, 'reservation_pk': reservation.pk, 'members_data': [{'age_range': '19-24y'}],
        }, format='json')
        force_authenticate(request, user=buyer)
        try:
            with connection.execute_wrapper(watch_legacy_lock):
                return legacy_booking_api(request, tunnel='member_detail').status_code
        finally:
            connections.close_all()

    with patch.object(command_module, 'apply_archive', side_effect=hold_first_worker), ThreadPoolExecutor(
        max_workers=2,
    ) as pool:
        winner = pool.submit(worker)
        assert winner_has_locks.wait(timeout=15), 'Archive did not reach the write phase'
        writer = pool.submit(legacy_write)
        applied, _ = winner.result(timeout=45)
        status_code = writer.result(timeout=45)

    assert applied.startswith('batch='), applied
    assert status_code == 404
    reservation.refresh_from_db()
    assert reservation.is_deleted and reservation.course_fee == 900 and reservation.status == 'completed'
    assert MemberDetail.all_objects.filter(reservation=reservation).count() == 2
    second_batch = applied.removeprefix('batch=')
    assert run('--restore', '--batch', second_batch)[0] == f'restored_batch={second_batch}'
    print('PASS concurrent legacy write reaches the locked order, returns 404 and leaves all rows unchanged')


if __name__ == '__main__':
    prepare_database(int(sys.argv[1]))
    verify_archive()
