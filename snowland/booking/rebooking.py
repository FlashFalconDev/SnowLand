"""Reuse learner preferences, never old consents or another adult's private data."""
from django.db import transaction
from django.db.models import Q

from .models import MemberDetail, Reservation
from .participants import ensure_reservation_members


def rebook_source_details(reservation, user):
    return {
        'reservationId': reservation.pk,
        'peopleCount': reservation.number_of_people,
        'learnerCount': reservation.members.filter(Q(user=user) | Q(guardian=user)).count(),
    }


@transaction.atomic
def copy_rebook_learners(reservation, reference, user):
    if reference is None:
        return
    raw_id = str(reference.get('reservationId') or '') if isinstance(reference, dict) else ''
    if (not raw_id.isascii() or not raw_id.isdecimal() or len(raw_id) > 19
            or not 0 < int(raw_id) <= 9223372036854775807):
        raise ValueError('上次學員資料連結無效，請重新從會員訂單開始預約')
    source = Reservation.objects.select_for_update().select_related('group').filter(
        pk=int(raw_id), group__client_id=reservation.group.client_id, group__user=user,
    ).exclude(group_id=reservation.group_id).first()
    if not source or source.status == 'deleted':
        raise ValueError('找不到可沿用的上次學員資料，請重新從自己的訂單開始預約')
    if source.number_of_people != reservation.number_of_people:
        raise ValueError('學員人數已變更，請重新確認學員，不會自動猜測沿用哪幾位')

    sources = list(source.members.select_for_update().order_by('pk'))
    targets = ensure_reservation_members(reservation)
    copied = 0
    for previous, current in zip(sources, targets):
        if user.pk not in {previous.user_id, previous.guardian_id}:
            continue
        basic = previous.insurance_data if isinstance(previous.insurance_data, dict) else {}
        name = str(basic.get('full_name') or '').strip()
        current.insurance_data = {'full_name': name} if name else {}
        current.age_range = previous.age_range if previous.age_range in dict(MemberDetail.AGE_CHOICES) else ''
        current.snowboard_skills = previous.snowboard_skills
        current.ski_skills = previous.ski_skills
        # Existing parent authority may carry forward; other adults must accept a new invitation.
        current.guardian_id = user.pk if previous.guardian_id == user.pk else None
        current.user_id = None if current.guardian_id else user.pk
        current.save(update_fields=['insurance_data','age_range','snowboard_skills','ski_skills','guardian','user'])
        copied += 1
    contact = dict(reservation.group.booking_contact or {})
    contact['rebook'] = {'source_reservation_id': source.pk, 'copied_learner_count': copied}
    reservation.group.booking_contact = contact
    reservation.group.save(update_fields=['booking_contact'])
