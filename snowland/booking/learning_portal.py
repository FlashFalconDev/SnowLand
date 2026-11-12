"""Learner identities and authorization shared by course records and albums."""
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from .assessment import learning_reports
from .models import CourseEvaluation, LearnerProfile, MemberDetail


CONFIRMED_COURSE_STATES = ('auto_assigned', 'manually_assigned', 'form_filled', 'completed')


def owned_places(user):
    return Q(guardian=user) | Q(guardian__isnull=True, user=user)


def place_owner_id(place):
    return place.guardian_id or place.user_id


def scoped_profiles(client, owner_id):
    return LearnerProfile.objects.filter(client=client, owner_id=owner_id)


def profile_options(client, owner_id):
    return list(scoped_profiles(client, owner_id).order_by('name', 'pk').values('id', 'name'))


def profile_id(value):
    if type(value) is not int or not 0 < value <= 9223372036854775807:
        raise ValueError('請選擇有效的學員檔案')
    return value


def booking_profile_choices(request, cart):
    choices = request.data.get('learner_selections')
    if choices is None:
        return [None] * len(cart)
    if not isinstance(choices, list) or len(choices) != len(cart):
        raise ValueError('購物車已變更，請重新確認學員')
    return choices


def set_checkout_learners(reservation, choices, user):
    if choices is None:
        return
    if not isinstance(choices, list) or len(choices) != reservation.number_of_people:
        raise ValueError('訂課人數已變更，請重新確認學員')
    ids = [profile_id(value) for value in choices if value is not None]
    profiles = scoped_profiles(reservation.group.client, user.pk).in_bulk(ids)
    if len(ids) != len(set(ids)):
        raise ValueError('同一學員不能佔用同一堂課的兩個名額')
    if len(profiles) != len(ids):
        raise ValueError('找不到可使用的學員檔案，請重新選擇')
    places = list(reservation.members.order_by('pk'))
    if len(places) != len(choices):
        raise ValueError('課程名額已變更，請重新確認學員')
    for place, value in zip(places, choices):
        if value is not None:
            place.learner = profiles[value]
            place.save(update_fields=['learner'])


def bind_profile(place, value, *, client):
    # Caller locks the reservation first, then the seat. Both member and
    # administrative edits take the same locks to prevent duplicate seats.
    owner_id = place_owner_id(place)
    if not owner_id:
        raise ValueError('此學員尚未綁定會員或家長帳號')
    profile = scoped_profiles(client, owner_id).filter(pk=profile_id(value)).first()
    if not profile:
        raise ValueError('找不到這個帳號可使用的學員檔案')
    if MemberDetail.objects.filter(reservation_id=place.reservation_id, learner=profile).exclude(pk=place.pk).exists():
        raise ValueError('這個學員檔案已用於同一堂課的另一個名額')
    place.learner = profile
    place.save(update_fields=['learner'])


def ended_sessions(now=None):
    now = now or timezone.localtime()
    return Q(date__lt=now.date()) | Q(date=now.date(), end_time__lte=now.time())


def coach_history(reservation):
    places = list(reservation.members.select_related('learner', 'user').order_by('pk'))
    profile_ids = {row.learner_id for row in places if row.learner_id and (
        row.learner.client_id == reservation.group.client_id and row.learner.owner_id == place_owner_id(row)
    )}
    now = timezone.localtime()
    evaluations = list(CourseEvaluation.objects.filter(
        member__learner_id__in=profile_ids, member__is_active=True, completed_at__isnull=False,
        booking__reservation__group__client_id=reservation.group.client_id,
        booking__reservation__status='completed',
    ).exclude(booking__reservation=reservation).filter(
        Q(booking__date__lt=now.date()) | Q(booking__date=now.date(), booking__end_time__lte=now.time()),
    ).filter(
        Q(member__guardian_id=F('member__learner__owner_id')) |
        Q(member__guardian__isnull=True, member__user_id=F('member__learner__owner_id')),
    ).select_related('booking', 'member__learner').order_by('-booking__date', '-booking__start_time', '-pk'))
    reports = learning_reports(evaluations)
    history = {}
    for evaluation in evaluations:
        history.setdefault(evaluation.member.learner_id, []).append({
            'date': str(evaluation.booking.date), 'course_name': evaluation.booking.course_name,
            'technical_assessment': reports.get(evaluation.pk, []),
            'learning_progress': evaluation.learning_progress,
            'coach_notes': evaluation.coach_notes,
        })
    return [{
        'id': row.pk,
        'name': row.learner.name if row.learner_id in profile_ids else row.display_name,
        'records': history.get(row.learner_id, []) if row.learner_id in profile_ids else [],
    } for row in places]


def album_asset_payload(asset, client, visible_member_ids):
    return {
        'id': asset.pk, 'type': asset.media_type,
        'url': reverse('booking:api_course_album_file_client', kwargs={
            'client_code': client.internal_code, 'asset_id': asset.pk,
        }),
        'tagged_member_ids': [member.pk for member in asset.tagged_members.all()
                              if member.pk in visible_member_ids],
    }
