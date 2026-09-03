from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q

from booking.models import Booking

from .models import CoachPayRule, PayrollLine, PayrollStatement


def _discipline_for(booking):
    category = getattr(getattr(booking.reservation.course_type, 'category', None), 'name', '')
    service_type = getattr(getattr(booking.reservation.course_type, 'category', None), 'service_type', '')
    text = f'{category} {booking.course_type} {booking.course_name}'.lower()
    if service_type == 'photo' or '攝影' in text or 'photo' in text:
        return 'photo'
    if '單板' in text or 'snowboard' in text:
        return 'snowboard'
    return 'ski'


def _hours(booking):
    start_minutes = booking.start_time.hour * 60 + booking.start_time.minute
    end_minutes = booking.end_time.hour * 60 + booking.end_time.minute
    return Decimal(max(end_minutes - start_minutes, 0)) / Decimal(60)


def _money(value):
    return int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _rule_for(booking, discipline):
    coach = booking.reservation.preferred_coach
    return CoachPayRule.objects.filter(
        coach=coach,
        discipline=discipline,
        is_active=True,
    ).filter(Q(course_type=booking.reservation.course_type) | Q(course_type__isnull=True)).order_by('-course_type_id').first()


@transaction.atomic
def calculate_payroll_statement(*, coach, campus, period_start, period_end):
    statement, _ = PayrollStatement.objects.get_or_create(
        coach=coach,
        campus=campus,
        period_start=period_start,
        period_end=period_end,
    )
    if statement.status == 'paid':
        raise ValueError('已發放的薪資單不能重新計算')
    statement.lines.all().delete()

    totals = {'course': 0, 'specified': 0, 'referral': 0, 'assistance': 0, 'allowance': 0}
    bookings = Booking.objects.filter(
        reservation__preferred_coach=coach,
        reservation__group__campus=campus,
        reservation__status='completed',
        date__range=(period_start, period_end),
    ).select_related('reservation__course_type__category', 'reservation__group').order_by('date', 'start_time')

    used_allowance_rules = set()
    used_specified_reservations = set()
    used_referral_reservations = set()
    used_assistance_reservations = set()
    for booking in bookings:
        discipline = _discipline_for(booking)
        rule = _rule_for(booking, discipline)
        if not rule:
            continue
        hours = _hours(booking)
        course_total = _money(hours * rule.hourly_rate)
        PayrollLine.objects.create(
            statement=statement, booking=booking, line_type='course',
            description=f'{booking.date} {booking.course_name} {discipline}',
            quantity=hours, unit_amount=rule.hourly_rate, total_amount=course_total,
            metadata={'discipline': discipline, 'certification_level': rule.certification_level},
        )
        totals['course'] += course_total

        reservation = booking.reservation
        if reservation.id not in used_specified_reservations and reservation.coach_fee > 0 and rule.specified_fee > 0:
            PayrollLine.objects.create(
                statement=statement, booking=booking, line_type='specified', description='指定教練費',
                quantity=1, unit_amount=rule.specified_fee, total_amount=rule.specified_fee,
                metadata={'discipline': discipline},
            )
            totals['specified'] += rule.specified_fee
            used_specified_reservations.add(reservation.id)

        if reservation.id not in used_referral_reservations and reservation.group.referral_user_id == coach.user_id and rule.referral_percent > 0:
            referral_base = max(reservation.course_fee - reservation.discount_amount, 0)
            commission = _money(Decimal(referral_base) * rule.referral_percent / Decimal(100))
            PayrollLine.objects.create(
                statement=statement, booking=booking, line_type='referral', description='介紹訂單抽成',
                quantity=rule.referral_percent, unit_amount=referral_base, total_amount=commission,
            )
            totals['referral'] += commission
            used_referral_reservations.add(reservation.id)

        if reservation.id not in used_assistance_reservations and reservation.equipment_assistance_time_slot_id and rule.assistance_hour_factor > 0:
            assistance_pay = _money(rule.hourly_rate * rule.assistance_hour_factor)
            PayrollLine.objects.create(
                statement=statement, booking=booking, line_type='assistance', description='裝備協助',
                quantity=rule.assistance_hour_factor, unit_amount=rule.hourly_rate, total_amount=assistance_pay,
            )
            totals['assistance'] += assistance_pay
            used_assistance_reservations.add(reservation.id)

        if rule.supervisor_allowance and rule.id not in used_allowance_rules:
            PayrollLine.objects.create(
                statement=statement, line_type='allowance', description='當期主管加給',
                quantity=1, unit_amount=rule.supervisor_allowance, total_amount=rule.supervisor_allowance,
            )
            totals['allowance'] += rule.supervisor_allowance
            used_allowance_rules.add(rule.id)

    statement.course_pay = totals['course']
    statement.specified_fees = totals['specified']
    statement.referral_commission = totals['referral']
    statement.assistance_pay = totals['assistance']
    statement.supervisor_allowance = totals['allowance']
    statement.total_amount = sum(totals.values()) + statement.adjustment
    statement.save()
    return statement
