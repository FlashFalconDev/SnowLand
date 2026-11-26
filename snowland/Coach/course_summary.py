from decimal import Decimal

from booking.order_testing import exclude_test_orders

from .models import CoachPayRule
from .payroll import discipline_for, pay_rule_for, payroll_course_key, payroll_hours, specified_payroll_fee


def summarize_course_payroll(bookings, *, coach):
    """Summarize the coach's visible booking queryset without reading or creating a payroll statement."""
    bookings = exclude_test_orders(bookings, 'reservation__group')
    summary = {
        period: {
            'total_hours': Decimal(0),
            'disciplines': {
                discipline: {'hours': Decimal(0), 'specified_count': 0, 'specified_amount': 0}
                for discipline, _ in CoachPayRule.DISCIPLINE_CHOICES
            },
        }
        for period in ('actual', 'estimated')
    }
    unresolved_fees = {period: set() for period in summary}
    used_courses = set()
    used_specified_reservations = set()
    rules = {}
    # A completed booking takes precedence if another order in the same class is still open.
    for booking in sorted(bookings, key=lambda item: item.reservation.status != 'completed'):
        reservation = booking.reservation
        period = 'actual' if reservation.status == 'completed' else 'estimated'
        discipline = discipline_for(booking)
        totals = summary[period]
        discipline_totals = totals['disciplines'][discipline]
        course_key = payroll_course_key(booking)
        if course_key not in used_courses:
            # Match the two decimal places stored in each payroll line.
            hours = payroll_hours(booking).quantize(Decimal('0.01'))
            totals['total_hours'] += hours
            discipline_totals['hours'] += hours
            used_courses.add(course_key)

        if reservation.coach_fee <= 0 or reservation.pk in used_specified_reservations:
            continue
        rule_key = (discipline, reservation.course_type_id, booking.date)
        if rule_key not in rules:
            try:
                rules[rule_key] = pay_rule_for(booking, discipline, coach=coach)
            except ValueError:  # Ambiguous effective rules prevent a fee from being determined.
                rules[rule_key] = None
        rule = rules[rule_key]
        if rule is None:
            unresolved_fees[period].add(reservation.pk)
            continue
        fee = specified_payroll_fee(booking, rule, used_specified_reservations)
        if fee:
            discipline_totals['specified_count'] += 1
            discipline_totals['specified_amount'] += fee

    for period, totals in summary.items():
        totals['unresolved_specified_count'] = len(unresolved_fees[period])
    return summary
