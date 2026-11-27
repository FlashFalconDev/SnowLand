"""Preview, audit and commit already-paid orders using the public capacity rules."""

import base64
import datetime as dt
import hashlib
import json
import logging
from collections import Counter, defaultdict

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from Client.memberships import member_profile
from Client.models import Client
from Client.tenant_settings import order_import_enabled
from Coach.models import Coach
from booking.capacity import slot_unavailable_reasons
from booking.closures import active_booking_closures
from booking.currency import initialize_order_currency
from booking.models import Booking, OrderImportBatch, Payment, Reservation, ReservationGroup
from booking.operations import record_order_revision
from booking.participants import ensure_reservation_members
from booking.scheduler import check_manual_assignment, manual_assignment_occupancy

from .parser import InputRow, parse_file
from .validation import (
    BANK_LAST_FIVE, CAMPUS, COACH, DAY, EMAIL, END, MARKETING, METHOD, NAME, NOTE, POSTED, START, TEMPLATE,
    Validator, group_rows, issue, redact,
)

logger = logging.getLogger(__name__)
SOURCE = '內部導入'
PREVIEW_TTL = dt.timedelta(hours=24)
MEMBER_MESSAGES = {
    'existing_member': '綁定既有會員',
    'new_membership': '將建立會員帳號的本校資料，沿用同信箱的登入帳號',
    'new_account': '將建立會員帳號',
}
COACH_MESSAGES = {
    'tenant_mismatch': '教練不屬於本校',
    'campus_mismatch': '教練未分配到此校區',
    'missing_resort': '教練未分配到此雪場',
    'missing_language': '教練未提供指定語言',
    'unavailable_status': '教練目前不可接課',
    'course_type': '教練沒有此課程資格',
    'ability_level': '教練沒有對應程度的資格',
    'template_roster': '教練不在此模板的可指派名單',
    'min_coach_level': '教練未達此模板的最低資格',
    'on_leave': '教練當日已請假',
    'schedule_conflict': '教練在此時段已有課程',
}


def serialize(value):
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.time):
        return value.strftime('%H:%M')
    if isinstance(value, dt.date):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, default=serialize, sort_keys=True, separators=(',', ':')).encode()


def batch_cipher():
    secrets = [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
    return MultiFernet([
        Fernet(base64.urlsafe_b64encode(
            salted_hmac('snowland.order_import.staged_input', 'v1', secret=secret, algorithm='sha256').digest()
        ))
        for secret in secrets
    ])


def order_fingerprint(order):
    lessons = []
    for lesson in order.lessons:
        fields = [
            lesson.slot.template.pk, lesson.resort.pk, lesson.slot.date, lesson.slot.start_time, lesson.slot.end_time,
            lesson.people, lesson.abilities, lesson.learner_names, lesson.language, lesson.coach.pk if lesson.coach else None,
            lesson.fee,
        ]
        if lesson.discount or lesson.discount_note or lesson.equipment or lesson.note:
            fields.extend((lesson.discount, lesson.discount_note, lesson.equipment, lesson.note))
        lessons.append(json_bytes(fields).decode())
    lessons.sort()
    data = [order.contact, order.fields[CAMPUS].pk, order.fields[METHOD], order.fields[POSTED], order.fields[NOTE], lessons]
    # Keep identical legacy orders recognizable after adding optional fields.
    marketing = order.fields[MARKETING]
    if order.fields[BANK_LAST_FIVE] or marketing and marketing != SOURCE:
        data.extend((order.fields[BANK_LAST_FIVE], marketing or SOURCE))
    return hashlib.sha256(json_bytes(data)).hexdigest()


def already_imported(tenant, order, fingerprint):
    payments = Payment.all_objects.filter(
        reservation_group__client=tenant, DataJSON__source_order_number=order.key,
    ).select_related('reservation_group').order_by('pk')
    for payment in payments:
        # Keep the source key case-sensitive, including on case-insensitive MySQL.
        if payment.DataJSON.get('source_order_number') != order.key:
            continue
        if payment.DataJSON.get('import_fingerprint') == fingerprint:
            return payment, issue(order.first_row, order.key, 'ok', 'already_imported', '此單已匯入')
        return None, issue(order.first_row, order.key, 'error', 'source_order_conflict', '此單號已存在，匯入內容不一致或無法核對')
    return None, None


def placement_issues(tenant, order, *, prior_slots=None, prior_coaches=None, lock_coaches=False):
    requested = Counter(lesson.slot for lesson in order.lessons)
    dates = [slot.date for slot in requested]
    closures = active_booking_closures(tenant, min(dates), max(dates))
    assigned = [lesson for lesson in order.lessons if lesson.coach]
    ids = {lesson.coach.pk for lesson in assigned}
    if lock_coaches and ids:
        list(Coach.objects.select_for_update().filter(client=tenant, pk__in=ids).order_by('pk').values_list('pk', flat=True))
    busy = manual_assignment_occupancy(ids, {lesson.slot.date for lesson in assigned})
    for coach_id in ids:
        busy[coach_id].extend((0, slot) for slot in (prior_coaches or {}).get(coach_id, ()))

    group = ReservationGroup(client=tenant, campus=order.fields[CAMPUS])
    issues = []
    for lesson in order.lessons:
        slot = lesson.slot
        # The shared service counts reservations and staff-link holds.
        # Preview adds preceding orders to the requested count.
        for reason in slot_unavailable_reasons(
            slot, requested=requested[slot] + (prior_slots or {}).get(slot, 0),
            closures=closures, resort_id=lesson.resort.pk,
        ):
            message = (
                f'{reason.date} {reason.start_time}–{reason.end_time} 名額不足'
                if reason.code == 'full' else reason.message_zh
            )
            issues.append(issue(lesson.row_number, order.key, 'warning', reason.code, message, TEMPLATE, DAY, START, END))
        if lesson.coach:
            reservation = Reservation(
                group=group, resort=lesson.resort, course_template=slot.template, course_type=slot.template.course_type,
                max_ability_level=lesson.highest_level, language=lesson.language,
            )
            when = (slot.date, slot.start_time, slot.end_time)
            candidate, = check_manual_assignment(
                reservation, [Booking(course_template=slot.template)], [lesson.coach], busy, slots=[when],
            )
            if candidate.reason_codes:
                message = '、'.join(COACH_MESSAGES.get(code, '教練不符合指派條件') for code in candidate.reason_codes)
                issues.append(issue(lesson.row_number, order.key, 'error', 'coach_conflict', message, COACH, DAY, START, END))
            else:
                busy[lesson.coach.pk].append((0, when))
    return issues


def has_error(issues):
    return any(item['level'] == 'error' for item in issues)


def order_result(row, key, status, issues, **details):
    summary = next((item for item in issues if item['level'] == 'error'), None)
    if summary is None:
        messages = {'ready': '訂單驗證通過', 'created': '匯入成功', 'skipped': '已跳過'}
        summary = issues[0] if issues else issue(row, key, 'ok', status, messages[status])
    return {
        **summary, 'row_number': row, 'group_key': redact(key), 'status': status, 'issues': issues, **details,
    }


def purge_expired_previews(*, tenant=None, now=None):
    expired = OrderImportBatch.objects.filter(
        status='previewed', created_at__lt=(now or timezone.now()) - PREVIEW_TTL, staged_input__isnull=False,
    )
    if tenant is not None:
        expired = expired.filter(client=tenant)
    expired.update(staged_input=None)


def preview_batch(tenant, actor, filename, content):
    parsed = parse_file(filename, content)
    groups, row_issues = group_rows(parsed.rows)
    validator = Validator(tenant)
    previous_slots = Counter()
    previous_coaches = defaultdict(list)
    results, staged = [], []
    total_amount = 0
    for key, rows in groups.items():
        order, issues, amount = validator.validate(key, rows)
        status = 'error'
        details = {'amount': amount, 'lessons': len(rows)}
        if order:
            total_amount += order.amount
            _, duplicate = already_imported(tenant, order, order_fingerprint(order))
            if duplicate:
                issues.append(duplicate)
                status = 'error' if has_error(issues) else 'skipped'
            else:
                first = order.first_row
                member = issue(first, key, 'ok', order.member_code, MEMBER_MESSAGES[order.member_code], EMAIL)
                details['member'] = member
                issues.extend(placement_issues(tenant, order, prior_slots=previous_slots, prior_coaches=previous_coaches))
                status = 'error' if has_error(issues) else 'ready'
                staged.append([key, [[row.number, row.values] for row in rows]])
                if status == 'ready':
                    previous_slots.update(lesson.slot for lesson in order.lessons)
                    for lesson in order.lessons:
                        if lesson.coach:
                            slot = lesson.slot
                            previous_coaches[lesson.coach.pk].append((slot.date, slot.start_time, slot.end_time))

        first = rows[0].number
        results.append(order_result(first, key, status, issues, **details))
        issues_by_row = defaultdict(list)
        for item in issues:
            issues_by_row[item['row_number']].append(item)
        for row in rows:
            row_issues.extend(issues_by_row[row.number] or [
                issue(row.number, key, 'ok', 'ok', '欄位驗證通過'),
            ])

    row_issues.sort(key=lambda item: item['row_number'])
    summary = {
        'orders': len(groups),
        'lessons': len(parsed.rows),
        'amount': total_amount,
        'errors': sum(item['level'] == 'error' for item in row_issues),
        'full': sum(item['code'] == 'full' for item in row_issues),
        'closed': sum(item['code'] == 'closed' for item in row_issues),
        'skipped_examples': parsed.skipped_examples,
        'committable': len(staged),
    }
    digest = hashlib.sha256(content).hexdigest()
    # Only valid normalized input is kept for the second request. Audit JSON
    # contains row numbers, safe messages and masked keys, never cell values.
    encrypted = batch_cipher().encrypt(json_bytes(staged)) if staged else None
    purge_expired_previews(tenant=tenant)
    return OrderImportBatch.objects.create(
        client=tenant, uploaded_by=actor, filename=redact(filename)[:255], file_sha256=digest,
        summary=summary, row_results=row_issues, order_results=results, staged_input=encrypted,
    )


def member_for_order(tenant, order):
    user = order.user
    if user is None:
        # The legacy import provisions an unusable password. Use a stable
        # username per email so simultaneous imports at different schools
        # converge on one platform login.
        address = order.fields[EMAIL]
        username = 'snowland_import_' + hashlib.sha256(address.encode()).hexdigest()
        user, _ = User.objects.get_or_create(username=username, defaults={
            'email': address, 'first_name': order.fields[NAME], 'password': make_password(None),
        })
        if user.email.lower() != address or not user.is_active:
            raise ValueError('會員帳號衝突')
    member_profile(user, tenant)
    return user


def create_order(tenant, actor, batch, order, fingerprint, *, overbooked):
    contact = order.contact
    user = member_for_order(tenant, order)
    group = ReservationGroup.objects.create(
        client=tenant, campus=order.fields[CAMPUS], user=user, name=contact['name'],
        booking_contact=contact, marketing_source=order.fields[MARKETING] or SOURCE, is_test=False,
    )
    lesson_notes = {}
    for lesson in order.lessons:
        template = lesson.slot.template
        status = 'manual_assignment_needed'
        if lesson.coach:
            status = 'pending_coach_confirmation' if lesson.coach.availability_status == 'passive' else 'manually_assigned'
        # In the locked template, 「指定教練」 is an administrative assignment.
        reservation = Reservation.objects.create(
            group=group, resort=lesson.resort, course_template=template, course_type=template.course_type,
            number_of_people=lesson.people, ability_level_counts=lesson.abilities, max_ability_level=lesson.highest_level,
            course_fee=lesson.original, discount_amount=lesson.discount, discount_name=lesson.discount_note,
            equipment=lesson.equipment, need_equipment=lesson.equipment in ('rentWithoutyourself', 'assistDuringCourse'),
            language=lesson.language, preferred_coach=lesson.coach,
            is_preferred_coach=False, status=status,
        )
        booking = Booking.objects.create(
            reservation=reservation, course_template=template, course_type=template.course_type.name,
            course_name=template.name, date=lesson.slot.date, start_time=lesson.slot.start_time, end_time=lesson.slot.end_time,
            is_scheduled=bool(lesson.coach), fee_snapshot={'course': lesson.original, 'coach': 0},
        )
        if lesson.note:
            lesson_notes[str(booking.pk)] = lesson.note
        members = ensure_reservation_members(reservation)
        for member, name in zip(members, lesson.learner_names):
            member.insurance_data = {'full_name': name}
            member.save(update_fields=['insurance_data'])

    initialize_order_currency(group, 'TWD')
    metadata = {'import_batch_id': batch.pk}
    reason = SOURCE
    if order.fields[NOTE]:
        reason += '：' + order.fields[NOTE]
    if overbooked:
        metadata['overbooked_import'] = True
        reason += f'（超賣匯入：{batch.overbook_reason}）'
    Payment.objects.create(
        reservation_group=group, user=user, status='paid', expires_at=None, payment_method=order.fields[METHOD],
        bank_posted_date=order.fields[POSTED], bank_account=order.fields[BANK_LAST_FIVE], DataJSON={
            'amount': order.amount, 'contact': contact, 'source_order_number': order.key,
            'import_source': SOURCE, 'import_fingerprint': fingerprint, **metadata,
            **({'import_lesson_notes': lesson_notes} if lesson_notes else {}),
        },
    )
    record_order_revision(group, user=actor, change_type='create', reason=reason, import_metadata=metadata)
    return group


class CommitError(ValueError):
    pass


def lock_batch(tenant, batch_id, *, include_input=False):
    batches = OrderImportBatch.objects.select_for_update().filter(pk=batch_id, client=tenant)
    if not include_input:
        batches = batches.defer('staged_input', 'row_results', 'order_results')
    return batches.get()


@transaction.atomic
def prepare_commit(tenant, batch_id, allow_overbook, reason):
    batch = lock_batch(tenant, batch_id, include_input=True)
    if batch.status != 'previewed':
        return batch, []
    if not batch.summary['committable']:
        return batch, []
    if not batch.staged_input or timezone.now() - batch.created_at >= PREVIEW_TTL:
        raise CommitError('沒有可匯入的訂單，或預覽已過期。請重新上傳')
    try:
        staged = json.loads(batch_cipher().decrypt(bytes(batch.staged_input), ttl=int(PREVIEW_TTL.total_seconds())))
    except InvalidToken:
        raise CommitError('預覽已過期或無法讀取，請重新上傳') from None
    if batch.commit_started:
        if batch.allow_overbook != allow_overbook or batch.overbook_reason != reason:
            raise CommitError('此批次已開始匯入，重試時請沿用原本的超賣設定與原因')
    else:
        batch.commit_started = True
        batch.allow_overbook = allow_overbook
        batch.overbook_reason = reason
        batch.save(update_fields=['commit_started', 'allow_overbook', 'overbook_reason'])
    return batch, staged


def commit_one(tenant, actor, batch, key, rows):
    first = rows[0].number
    if not order_import_enabled(tenant):
        return order_result(first, key, 'failed', [
            issue(first, key, 'error', 'import_disabled', '此學校已停用訂單匯入'),
        ])
    order, issues, _ = Validator(tenant).validate(key, rows)
    if order is None:
        return order_result(first, key, 'failed', issues)
    fingerprint = order_fingerprint(order)
    payment, duplicate = already_imported(tenant, order, fingerprint)
    if duplicate:
        if payment and payment.DataJSON.get('import_batch_id') == batch.pk:
            group = payment.reservation_group
            return order_result(first, key, 'created', [duplicate], order_id=group.pk, order_number=group.order_number)
        return order_result(first, key, 'failed' if has_error([duplicate]) else 'skipped', [duplicate])
    issues.extend(placement_issues(tenant, order, lock_coaches=True))
    overbooked = any(item['code'] == 'full' for item in issues)
    if has_error(issues):
        return order_result(first, key, 'failed', issues)
    if overbooked and not batch.allow_overbook:
        return order_result(first, key, 'skipped', issues)
    group = create_order(tenant, actor, batch, order, fingerprint, overbooked=overbooked)
    return order_result(first, key, 'created', issues, order_id=group.pk, order_number=group.order_number, overbooked=overbooked)


def commit_batch(tenant, actor, batch_id, allow_overbook, reason):
    batch, staged = prepare_commit(tenant, batch_id, allow_overbook, redact(reason))
    if batch.status != 'previewed':
        return batch
    for key, raw_rows in staged:
        rows = [InputRow(number, tuple(values)) for number, values in raw_rows]
        index = str(rows[0].number)
        with transaction.atomic():
            tenant = Client.objects.select_for_update().get(pk=tenant.pk)
            batch = lock_batch(tenant, batch_id)
            if batch.status != 'previewed' or index in batch.commit_results:
                continue
            try:
                with transaction.atomic():
                    result = commit_one(tenant, actor, batch, key, rows)
            except (DatabaseError, ValueError) as exc:
                logger.warning('Could not write order import batch %s row %s (%s)', batch.pk, index, type(exc).__name__)
                result = order_result(rows[0].number, key, 'failed', [
                    issue(rows[0].number, key, 'error', 'write_failed', '此單無法建立，請重新預覽並核對資料'),
                ])
            batch.commit_results[index] = result
            batch.save(update_fields=['commit_results'])

    with transaction.atomic():
        batch = lock_batch(tenant, batch_id, include_input=True)
        if batch.status != 'previewed':
            return batch
        for item in batch.order_results:
            batch.commit_results.setdefault(str(item['row_number']), {
                **item, 'status': 'skipped' if item['status'] == 'skipped' else 'failed',
            })
        counts = Counter(item['status'] for item in batch.commit_results.values())
        ungrouped = sum(item['code'] == 'invalid_order_number' for item in batch.row_results)
        if counts['created']:
            batch.status = 'partial' if counts['failed'] or counts['skipped'] or ungrouped else 'committed'
        else:
            batch.status = 'failed' if counts['failed'] or ungrouped else 'committed'
        batch.summary = {**batch.summary, 'created': counts['created'], 'skipped': counts['skipped'], 'failed': counts['failed']}
        batch.committed_at = timezone.now()
        batch.staged_input = None
        batch.save(update_fields=['status', 'summary', 'committed_at', 'staged_input', 'commit_results'])
    return batch
