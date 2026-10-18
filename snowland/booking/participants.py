"""Prepare one learner record per booked place without replacing existing forms."""

from django.db import transaction

from .models import CourseEvaluation, MemberDetail, Reservation


@transaction.atomic
def ensure_reservation_members(reservation):
    reservation = Reservation.objects.select_for_update().select_related('group').get(pk=reservation.pk)
    if reservation.status in {'cancelled', 'deleted'}:
        raise ValueError('此課程已取消，無法建立學員資料')
    if reservation.number_of_people < 1:
        raise ValueError('訂單學員人數未設定，請聯繫客服確認')
    members = list(reservation.members.order_by('id'))
    for _ in range(max(reservation.number_of_people - len(members), 0)):
        members.append(MemberDetail.objects.create(
            reservation=reservation, user=reservation.group.user,
            filled_by='user', age_range='',
        ))
    if reservation.status == 'completed':
        for booking in reservation.bookings.all():
            for member in members:
                CourseEvaluation.objects.get_or_create(
                    booking=booking, member=member,
                    defaults={'coach': reservation.preferred_coach},
                )
    return members
