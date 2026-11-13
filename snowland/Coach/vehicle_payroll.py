from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.utils import timezone

from .vehicle_models import VehicleCharge, VehicleDeduction

JAPAN_TIME = ZoneInfo('Asia/Tokyo')


def next_month(day):
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def payroll_cutoff(month, payroll_day):
    payment_month = next_month(month)
    return payment_month.replace(day=min(payroll_day, monthrange(payment_month.year, payment_month.month)[1]))


def create_trip_charges(trip, policy, coach_ids, approved_at):
    from .payroll_settlement import rounded
    distance = trip.return_km - trip.departure_km
    trip.yen_per_km = policy.yen_per_km
    trip.yen_per_twd = policy.yen_per_twd
    trip.payroll_day = policy.payroll_day
    trip.amount_yen = rounded(distance * policy.yen_per_km)
    trip.amount_twd = rounded(Decimal(trip.amount_yen) / policy.yen_per_twd)
    returned = timezone.localdate(trip.returned_at, JAPAN_TIME)
    approved = timezone.localdate(approved_at, JAPAN_TIME)
    first = returned.replace(day=1)
    # The payroll date is in the calendar month after the work month.
    while approved > payroll_cutoff(first, policy.payroll_day):
        first = next_month(first)
    april = date(returned.year + (returned.month > 4), 4, 1)
    share, remainder = divmod(trip.amount_twd, len(coach_ids))
    VehicleCharge.objects.bulk_create([
        VehicleCharge(trip=trip, coach_id=coach_id, first_month=first, last_month=april, amount_twd=share + (index < remainder))
        for index, coach_id in enumerate(coach_ids) if share + (index < remainder)
    ])


def charge_balance(charge, *, include_drafts=True, exclude_statement=None, today=None):
    today = today or timezone.localdate(timezone=JAPAN_TIME)
    allocated = sum(
        deduction.amount_twd
        for deduction in charge.deductions.exclude(statement_id=exclude_statement).select_related('statement')
        if deduction.statement.status != 'draft' or (
            include_drafts and today <= payroll_cutoff(deduction.statement.period_end, charge.trip.payroll_day or 1)
        )
    )
    return charge.amount_twd - allocated - charge.collected_twd


def vehicle_deduction_plan(statement, base_net, payment_net, payment_rate):
    from .payroll_settlement import rounded

    today = timezone.localdate(timezone=JAPAN_TIME)
    month = statement.period_end.replace(day=1)
    period_limit = datetime.combine(statement.period_end + timedelta(days=1), time.min, JAPAN_TIME)
    charges = (VehicleCharge.objects.select_related('trip')
               .filter(coach_id=statement.coach_id, first_month__lte=month, last_month__gte=month,
                       trip__campus_id=statement.campus_id, trip__returned_at__lt=period_limit)
               .order_by('pk'))
    allocations = []
    reservations = []
    remaining = base_net
    deducted_in_payment_currency = 0
    for charge in charges:
        if today > payroll_cutoff(month, charge.trip.payroll_day or 1):
            continue
        amount = min(remaining, charge_balance(charge, exclude_statement=statement.pk, today=today))
        if amount <= 0:
            continue
        total_payment = rounded(Decimal(base_net - remaining + amount) * payment_rate)
        if total_payment > payment_net:
            # An already-rounded foreign net can be one minor unit below its TWD equivalent.
            total_payment = payment_net
        allocations.append({'trip_id': charge.trip_id, 'amount_twd': amount,
                            'amount': total_payment - deducted_in_payment_currency})
        deducted_in_payment_currency = total_payment
        remaining -= amount
        reservations.append(VehicleDeduction(charge=charge, statement=statement, amount_twd=amount))
        if remaining == 0:
            break
    if not allocations:
        return {}, reservations
    return {'vehicle_deductions': allocations, 'vehicle_deduction_twd': base_net - remaining,
            'vehicle_deduction_amount': deducted_in_payment_currency,
            'net_after_vehicle': payment_net - deducted_in_payment_currency,
            'base_net_after_vehicle': remaining}, reservations


def apply_vehicle_deductions(statement, base_net, payment_net, payment_rate):
    snapshot, reservations = vehicle_deduction_plan(statement, base_net, payment_net, payment_rate)
    VehicleDeduction.objects.filter(statement=statement).delete()
    VehicleDeduction.objects.bulk_create(reservations)
    return snapshot
