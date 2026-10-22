from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Max, Q

from booking.models import Booking

from .models import Coach, CoachPayRule, PayrollLine, PayrollStatement


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


def _payroll_hours(booking):
    template = booking.reservation.course_template
    if template is not None and template.payroll_hours is not None:
        return template.payroll_hours
    return _hours(booking)


def _rule_for(booking, discipline, *, coach=None):
    coach = coach or booking.reservation.preferred_coach
    rules = CoachPayRule.objects.filter(
        coach=coach,
        discipline=discipline,
        is_active=True,
    )
    specific = rules.filter(course_type_id=booking.reservation.course_type_id)
    applicable = specific if booking.reservation.course_type_id and specific.exists() else rules.filter(course_type__isnull=True)
    matches = list(applicable.order_by('pk')[:2])
    if len(matches) > 1:
        raise ValueError(f'{coach.name} 的同一工作類型及適用課程有多筆啟用薪資規則，請先停用不適用的規則再結算')
    return matches[0] if matches else None


@transaction.atomic
def calculate_payroll_statement(*, coach, campus, period_start, period_end):
    # Serialize creation/recalculation for this coach, including overlapping periods.
    coach = Coach.objects.select_for_update().get(pk=coach.pk)
    overlap = PayrollStatement.objects.filter(
        coach=coach, campus=campus,
        period_start__lte=period_end, period_end__gte=period_start,
    ).exclude(period_start=period_start, period_end=period_end).first()
    if overlap:
        raise ValueError(
            f'此教練已有 {overlap.period_start}～{overlap.period_end} 的薪資單，'
            '結算期間不能重疊；請用相同期間重新計算，或選擇不重疊的日期'
        )
    statement, _ = PayrollStatement.objects.get_or_create(
        coach=coach,
        campus=campus,
        period_start=period_start,
        period_end=period_end,
    )
    statement = PayrollStatement.objects.select_for_update().get(pk=statement.pk)
    if statement.status != 'draft':
        raise ValueError('已送交確認、已確認或已發放的薪資單不能重新計算')
    bookings = list(Booking.objects.filter(
        reservation__preferred_coach=coach,
        reservation__group__campus=campus,
        reservation__status='completed',
        date__range=(period_start, period_end),
    ).select_related('reservation__course_type__category', 'reservation__course_template', 'reservation__group').order_by('date', 'start_time'))
    for booking in bookings:
        discipline = _discipline_for(booking)
        rule = _rule_for(booking, discipline)
        if not rule:
            raise ValueError(f'{coach.name} 的 {discipline} 課程尚未設定薪資規則（{booking.date}），請先設定時薪再結算')
        if not 0 <= rule.referral_percent <= 100 or rule.assistance_hour_factor < 0:
            raise ValueError(f'{coach.name} 的薪資規則有不合法的介紹費百分比或裝備協助時數，請先編輯原規則再結算')
    # Referral ownership is independent of the teacher assigned to a lesson.
    # Resolve the referrer's rules before replacing any existing draft lines.
    referral_bookings = Booking.objects.filter(
        reservation__group__client=coach.client,
        reservation__group__campus=campus,
        reservation__group__referral_user_id=coach.user_id,
        reservation__status='completed',
    ).annotate(referral_completion_date=Max('reservation__group__reservations__bookings__date',
        filter=~Q(reservation__group__reservations__status__in=['cancelled', 'deleted']))).filter(
        referral_completion_date__range=(period_start, period_end),
    ).select_related('reservation__course_type__category').order_by('date', 'start_time', 'pk') if coach.user_id else []
    referrals = []
    referred_reservations = set()
    for booking in referral_bookings:
        if booking.reservation.group.reservations.exclude(status__in=['completed', 'cancelled', 'deleted']).exists():
            continue
        if booking.reservation_id in referred_reservations:
            continue
        referred_reservations.add(booking.reservation_id)
        rule = _rule_for(booking, _discipline_for(booking), coach=coach)
        if not rule or not 0 <= rule.referral_percent <= 100:
            raise ValueError(f'{coach.name} 的介紹費比例尚未正確設定（{booking.date}），請先設定介紹教練的薪資規則再結算')
        if rule.referral_percent > 0:
            referrals.append((booking, rule))
    statement.lines.exclude(line_type='adjustment').delete()

    totals = {'course': 0, 'specified': 0, 'referral': 0, 'assistance': 0, 'allowance': 0}

    used_allowance_rules = set()
    used_specified_reservations = set()
    used_assistance_reservations = set()
    used_shared_classes = set()
    for booking in bookings:
        discipline = _discipline_for(booking)
        rule = _rule_for(booking, discipline)
        hours = _payroll_hours(booking)
        course_total = _money(hours * rule.hourly_rate)
        reservation = booking.reservation
        shared_class_id = reservation.shared_course_class_id
        if not shared_class_id or shared_class_id not in used_shared_classes:
            PayrollLine.objects.create(
                statement=statement, booking=booking, line_type='course',
                description=f'{booking.date} {booking.course_name} {discipline}',
                quantity=hours, unit_amount=rule.hourly_rate, total_amount=course_total,
                metadata={'discipline': discipline, 'certification_level': rule.certification_level,
                          'scheduled_hours': str(_hours(booking)),
                          'payroll_hours_source': 'template' if reservation.course_template and reservation.course_template.payroll_hours is not None else 'schedule'},
            )
            totals['course'] += course_total
            if shared_class_id:
                used_shared_classes.add(shared_class_id)
        if reservation.id not in used_specified_reservations and reservation.coach_fee > 0 and rule.specified_fee > 0:
            PayrollLine.objects.create(
                statement=statement, booking=booking, line_type='specified', description='指定教練費',
                quantity=1, unit_amount=rule.specified_fee, total_amount=rule.specified_fee,
                metadata={'discipline': discipline},
            )
            totals['specified'] += rule.specified_fee
            used_specified_reservations.add(reservation.id)

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

    for booking, rule in referrals:
        reservation = booking.reservation
        referral_base = max(reservation.course_fee - reservation.discount_amount, 0)
        commission = _money(Decimal(referral_base) * rule.referral_percent / Decimal(100))
        PayrollLine.objects.create(
            statement=statement, booking=booking, line_type='referral', description='介紹訂單抽成',
            quantity=rule.referral_percent, unit_amount=referral_base, total_amount=commission,
            metadata={'referral_user_id': coach.user_id, 'discipline': _discipline_for(booking)},
        )
        totals['referral'] += commission

    statement.course_pay = totals['course']
    statement.specified_fees = totals['specified']
    statement.referral_commission = totals['referral']
    statement.assistance_pay = totals['assistance']
    statement.supervisor_allowance = totals['allowance']
    statement.adjustment = sum(statement.lines.filter(line_type='adjustment').values_list('total_amount', flat=True))
    statement.total_amount = sum(totals.values()) + statement.adjustment
    if statement.total_amount < 0:
        raise ValueError('既有手動扣款超過重新計算後的薪資，請先核對')
    statement.save()
    return statement


@transaction.atomic
def add_payroll_adjustment(*, statement, description, amount):
    statement = PayrollStatement.objects.select_for_update().get(pk=statement.pk)
    if statement.status != 'draft':
        raise ValueError('僅草稿薪資單可新增手動項目')
    description, amount = _adjustment_values(description, amount)
    if statement.total_amount + amount < 0:
        raise ValueError('調整後應付薪資不可小於 0')
    line = PayrollLine.objects.create(
        statement=statement, line_type='adjustment', description=description,
        quantity=1, unit_amount=amount, total_amount=amount,
    )
    statement.adjustment += amount
    statement.total_amount += amount
    statement.save(update_fields=['adjustment', 'total_amount', 'updated_at'])
    return line


def _adjustment_values(description, amount):
    description = str(description).strip()
    if not description or len(description) > 200:
        raise ValueError('請填寫 200 字以內的項目說明')
    try:
        raw_amount = amount
        amount = int(raw_amount)
    except (TypeError, ValueError):
        raise ValueError('金額須為整數')
    if isinstance(raw_amount, bool) or str(amount) != str(raw_amount).strip():
        raise ValueError('金額須為整數')
    if amount == 0 or abs(amount) > 10000000:
        raise ValueError('金額須介於 -1000 萬至 1000 萬，且不可為 0')
    return description, amount


@transaction.atomic
def change_payroll_adjustment(*, statement, line_id, description='', amount=None, delete=False):
    statement = PayrollStatement.objects.select_for_update().get(pk=statement.pk)
    if statement.status != 'draft':
        raise ValueError('僅草稿薪資單可修改或刪除手動項目')
    line = statement.lines.filter(pk=line_id, line_type='adjustment').first()
    if not line:
        raise ValueError('此薪資單找不到可修改的手動項目')
    if delete:
        new_amount = 0
    else:
        description, new_amount = _adjustment_values(description, amount)
    difference = new_amount - line.total_amount
    if statement.total_amount + difference < 0:
        raise ValueError('調整後應付薪資不可小於 0')
    if delete:
        line.delete()
    else:
        line.description = description
        line.unit_amount = line.total_amount = new_amount
        line.save(update_fields=['description', 'unit_amount', 'total_amount'])
    statement.adjustment += difference
    statement.total_amount += difference
    statement.save(update_fields=['adjustment', 'total_amount', 'updated_at'])
    return statement
