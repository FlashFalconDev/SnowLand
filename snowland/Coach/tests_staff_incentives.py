from datetime import date, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from API import tests_operations as fixtures
from Coach.models import StaffIncentiveRule, StaffIncentiveStatement
from Coach.staff_incentives import calculate_staff_incentive, confirm_staff_incentive, mark_staff_incentive_paid, adjust_staff_incentive
from booking.models import Booking, CancellationRequest, Payment, Reservation, ReservationGroup


class StaffIncentiveCalculationTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.employee = User.objects.create_user('qa-bonus-staff')
        self.rule = StaffIncentiveRule.objects.create(user=self.employee, campus=self.campus, completed_order_percent='2.50')
        Booking.objects.filter(pk__in=[self.booking_1.pk, self.booking_2.pk]).update(date=date(2026, 1, 10))
        Payment.objects.create(reservation_group=self.group, user=self.user, status='paid')
        self.reservation.refresh_from_db()
        self.month = date(2026, 1, 1)

    def calculate(self, month=None):
        return calculate_staff_incentive(user=self.employee, campus=self.campus, month=month or self.month)

    def pay(self, statement):
        statement = confirm_staff_incentive(statement, actor=self.employee)
        return mark_staff_incentive_paid(statement, actor=self.employee)

    def refund(self, amount=4000, day=date(2026, 2, 10), status='refunded'):
        return CancellationRequest.objects.create(group=self.group, reason='other', status=status,
            original_amount=self.reservation.payment_amount, refund_amount=amount,
            reviewed_at=timezone.make_aware(__import__('datetime').datetime.combine(day, time(12))))

    def test_monthly_revenue_and_percentage_are_snapshotted_and_recalculation_is_idempotent(self):
        statement = self.calculate()
        self.assertEqual(statement.revenue, 10000)
        self.assertEqual(statement.earned_amount, 250)
        self.assertEqual(statement.total_amount, 250)
        self.assertEqual(statement.lines.count(), 1)
        self.assertEqual(self.calculate().pk, statement.pk)
        self.assertEqual(statement.lines.count(), 1)

    def test_only_fully_completed_paid_orders_in_completion_month_count(self):
        self.booking_2.date = date(2026, 2, 1)
        self.booking_2.save(update_fields=['date'])
        self.assertEqual(self.calculate().revenue, 0)
        self.assertEqual(self.calculate(date(2026, 2, 1)).revenue, 10000)
        Reservation.objects.create(group=self.group, resort=self.resort, course_type=self.course_type, status='created', course_fee=2000)
        self.assertEqual(self.calculate(date(2026, 2, 1)).revenue, 0)

    def test_unpaid_latest_payment_and_foreign_campus_are_not_revenue(self):
        Payment.objects.create(reservation_group=self.group, user=self.user, status='pending')
        self.assertEqual(self.calculate().revenue, 0)
        self.assertFalse(self.calculate().lines.exists())

    def test_old_paid_statement_keeps_original_percentage_and_names(self):
        statement = self.pay(self.calculate())
        self.rule.completed_order_percent = 10
        self.rule.save()
        self.employee.first_name = 'Changed'
        self.employee.save()
        self.campus.name = 'Changed campus'
        self.campus.save()
        with self.assertRaisesMessage(ValueError, '不能重新計算'):
            self.calculate()
        statement.refresh_from_db()
        self.assertEqual(statement.percent, Decimal('2.50'))
        self.assertEqual(statement.total_amount, 250)
        self.assertEqual(statement.user_name, 'qa-bonus-staff')
        self.assertEqual(statement.campus_name, '北海道校區')

    def test_refunded_paid_bonus_is_deducted_next_month_at_original_percent_only_once(self):
        source = self.pay(self.calculate())
        self.rule.completed_order_percent = 10
        self.rule.save()
        cancellation = self.refund()
        self.assertEqual(self.calculate(date(2026, 2, 1)).refund_deduction, 0)
        march = self.calculate(date(2026, 3, 1))
        self.assertEqual(march.refund_deduction, 100)
        self.assertEqual(march.total_amount, -100)
        line = march.lines.get()
        self.assertEqual(line.percent, Decimal('2.50'))
        self.assertEqual(line.cancellation_id, cancellation.pk)
        self.assertEqual(line.source_line.statement_id, source.pk)
        self.assertEqual(self.calculate(date(2026, 3, 1)).refund_deduction, 100)
        self.pay(march)
        self.assertEqual(self.calculate(date(2026, 4, 1)).refund_deduction, 0)

    def test_unpaid_bonus_and_unfinished_refund_are_not_clawed_back(self):
        statement = confirm_staff_incentive(self.calculate(), actor=self.employee)
        cancellation = self.refund(status='approved')
        self.assertEqual(self.calculate(date(2026, 3, 1)).refund_deduction, 0)
        mark_staff_incentive_paid(statement, actor=self.employee)
        self.assertEqual(self.calculate(date(2026, 3, 1)).refund_deduction, 0)
        cancellation.status = 'refunded'
        cancellation.save(update_fields=['status'])
        self.assertEqual(self.calculate(date(2026, 3, 1)).refund_deduction, 100)

    def test_refund_deductions_never_exceed_original_paid_bonus(self):
        self.pay(self.calculate())
        self.refund(amount=9000)
        self.refund(amount=9000)
        statement = self.calculate(date(2026, 3, 1))
        self.assertEqual(statement.refund_deduction, 250)
        self.assertEqual(statement.total_amount, -250)

    def test_small_split_refunds_recover_the_same_bonus_as_one_full_refund(self):
        self.rule.completed_order_percent = 25
        self.rule.save()
        self.reservation.course_fee = 2
        self.reservation.coach_fee = 0
        self.reservation.discount_amount = 0
        self.reservation.save()
        self.assertEqual(self.pay(self.calculate()).earned_amount, 1)
        self.refund(amount=1)
        self.refund(amount=1)
        statement = self.calculate(date(2026, 3, 1))
        self.assertEqual(statement.refund_deduction, 1)
        self.assertEqual(sum(statement.lines.values_list('base_amount', flat=True)), 2)
        self.assertEqual(self.calculate(date(2026, 3, 1)).refund_deduction, 1)

    def test_zero_rounded_refund_retains_its_base_for_later_month(self):
        self.rule.completed_order_percent = 25
        self.rule.save()
        self.reservation.course_fee = 2
        self.reservation.coach_fee = 0
        self.reservation.discount_amount = 0
        self.reservation.save()
        self.pay(self.calculate())
        self.refund(amount=1)
        march = self.calculate(date(2026, 3, 1))
        self.assertEqual(march.refund_deduction, 0)
        self.assertEqual(list(march.lines.values_list('base_amount', 'amount')), [(1, 0)])
        self.pay(march)
        self.refund(amount=1, day=date(2026, 3, 10))
        april = self.calculate(date(2026, 4, 1))
        self.assertEqual(april.refund_deduction, 1)
        self.pay(april)
        self.assertEqual(self.calculate(date(2026, 5, 1)).refund_deduction, 0)

    def test_full_refund_recovers_a_bonus_cent_allocated_by_monthly_rounding(self):
        self.rule.completed_order_percent = 25
        self.rule.save()
        self.reservation.course_fee = 1
        self.reservation.coach_fee = 0
        self.reservation.discount_amount = 0
        self.reservation.save()
        other = ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus, user=self.user)
        item = Reservation.objects.create(group=other, resort=self.resort, course_type=self.course_type,
            status='completed', course_fee=1)
        Booking.objects.create(reservation=item, date=date(2026, 1, 11), start_time=time(9), end_time=time(11))
        Payment.objects.create(reservation_group=other, user=self.user, status='paid')
        paid = self.pay(self.calculate())
        self.assertEqual(paid.lines.get(group=other).amount, 1)
        CancellationRequest.objects.create(group=other, reason='other', status='refunded',
            original_amount=1, refund_amount=1,
            reviewed_at=timezone.make_aware(__import__('datetime').datetime(2026, 2, 10, 12)))
        self.assertEqual(self.calculate(date(2026, 3, 1)).refund_deduction, 1)

    def test_inactive_rule_stops_new_earnings_but_keeps_refund_obligation(self):
        self.pay(self.calculate())
        self.rule.is_active = False
        self.rule.save()
        self.refund()
        self.assertEqual(self.calculate(date(2026, 3, 1)).refund_deduction, 100)

    def test_month_must_be_first_day_and_publishing_requires_finished_month(self):
        with self.assertRaisesMessage(ValueError, '每月1日'):
            self.calculate(date(2026, 1, 2))
        current = self.calculate(timezone.localdate().replace(day=1))
        with self.assertRaisesMessage(ValueError, '月份結束'):
            confirm_staff_incentive(current, actor=self.employee)

    def test_adjustment_requires_reason_is_preserved_on_recalculate_and_locked_after_confirmation(self):
        statement = self.calculate()
        with self.assertRaisesMessage(ValueError, '原因'):
            adjust_staff_incentive(statement, amount=-30, note='')
        adjust_staff_incentive(statement, amount=-30, note='QA 人工調整')
        self.assertEqual(self.calculate().total_amount, 220)
        self.pay(statement)
        with self.assertRaisesMessage(ValueError, '草稿'):
            adjust_staff_incentive(statement, amount=10, note='QA')

    def test_failure_during_recalculation_preserves_existing_lines_and_totals(self):
        statement = self.calculate()
        old_lines = list(statement.lines.values_list('pk', 'amount'))
        with patch('Coach.staff_incentives.StaffIncentiveLine.objects.create', side_effect=RuntimeError('QA injected failure')):
            with self.assertRaises(RuntimeError):
                self.calculate()
        statement.refresh_from_db()
        self.assertEqual(statement.total_amount, 250)
        self.assertEqual(list(statement.lines.values_list('pk', 'amount')), old_lines)

    def test_rounding_is_based_on_monthly_total_not_each_order(self):
        self.rule.completed_order_percent = 50
        self.rule.save()
        self.reservation.course_fee = 1
        self.reservation.coach_fee = 0
        self.reservation.discount_amount = 0
        self.reservation.save()
        other = ReservationGroup.objects.create(client=self.client_tenant, campus=self.campus, user=self.user)
        item = Reservation.objects.create(group=other, resort=self.resort, course_type=self.course_type, status='completed', course_fee=1)
        Booking.objects.create(reservation=item, date=date(2026, 1, 11), start_time=time(9), end_time=time(11))
        Payment.objects.create(reservation_group=other, user=self.user, status='paid')
        statement = self.calculate()
        self.assertEqual(statement.revenue, 2)
        self.assertEqual(statement.earned_amount, 1)
        self.assertEqual(sum(statement.lines.values_list('amount', flat=True)), 1)

    def test_deleted_course_does_not_move_completion_month_or_inflate_revenue(self):
        deleted = Reservation.objects.create(group=self.group, resort=self.resort,
            course_type=self.course_type, status='deleted', course_fee=9999)
        Booking.objects.create(reservation=deleted, date=date(2026, 4, 1), start_time=time(9), end_time=time(11))
        self.assertEqual(self.calculate().revenue, 10000)
        self.assertEqual(self.calculate(date(2026, 4, 1)).revenue, 0)

    def test_refund_without_completion_date_does_not_erase_existing_draft(self):
        self.pay(self.calculate())
        refund = self.refund()
        march = self.calculate(date(2026, 3, 1))
        ids = list(march.lines.values_list('pk', flat=True))
        refund.reviewed_at = None
        refund.save(update_fields=['reviewed_at'])
        with self.assertRaisesMessage(ValueError, '退款缺少完成日期'):
            self.calculate(date(2026, 3, 1))
        march.refresh_from_db()
        self.assertEqual(march.total_amount, -100)
        self.assertEqual(list(march.lines.values_list('pk', flat=True)), ids)

    def test_zero_percent_and_renamed_order_keep_explicit_snapshot(self):
        self.rule.completed_order_percent = 0
        self.rule.save()
        statement = self.pay(self.calculate())
        snapshot = statement.lines.get()
        old_number = snapshot.order_number
        self.group.order_number = 'changed-order-number'
        self.group.save()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.order_number, old_number)
        self.assertEqual(snapshot.amount, 0)

    def test_paid_order_moved_to_another_month_is_not_earned_again(self):
        self.pay(self.calculate())
        Booking.objects.filter(reservation=self.reservation).update(date=date(2026, 2, 10))
        self.assertEqual(self.calculate(date(2026, 2, 1)).earned_amount, 0)

    def test_paid_order_cannot_earn_again_when_moved_to_another_campus(self):
        from Resorts.models import Campus
        self.pay(self.calculate())
        other = Campus.objects.create(client=self.client_tenant, name='B', code='b')
        StaffIncentiveRule.objects.create(user=self.employee, campus=other, completed_order_percent=10)
        self.group.campus = other
        self.group.save(update_fields=['campus'])
        moved = calculate_staff_incentive(user=self.employee, campus=other, month=self.month)
        self.assertEqual(moved.earned_amount, 0)
        self.refund()
        self.assertEqual(self.calculate(date(2026, 3, 1)).refund_deduction, 100)
        self.assertEqual(calculate_staff_incentive(user=self.employee, campus=other, month=date(2026, 3, 1)).refund_deduction, 0)
