from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.learning_portal import (
    CONFIRMED_COURSE_STATES, album_asset_payload, bind_profile, coach_history,
    ended_sessions, place_owner_id, profile_id, profile_options,
)
from booking.media_files import save_album_upload
from booking.models import Booking, CourseAlbumAsset, MemberDetail, Reservation
from .admin_views import (
    CourseEvaluationAdminViewSet, IsTenantCoach, PayrollCsrfMixin,
    _coach_can_view_full_schedule, _coach_visible_window, _with_current_schedule_payment,
)


def coach_bookings(request):
    return Booking.objects.filter(
        reservation__group__client=request.tenant,
        reservation__status__in=CONFIRMED_COURSE_STATES,
        reservation__preferred_coach__user=request.user,
        reservation__preferred_coach__client=request.tenant,
    ).select_related('reservation__preferred_coach', 'reservation__group')


class CoachLearnerHistoryAPI(APIView):
    permission_classes = [IsTenantCoach]

    def get(self, request, client_code, reservation_id):
        bookings = _with_current_schedule_payment(
            coach_bookings(request).filter(reservation_id=reservation_id), 'reservation__group_id',
        )
        booking = bookings.first()
        if not booking:
            raise Http404
        if not _coach_can_view_full_schedule(booking.reservation.preferred_coach):
            start, end = _coach_visible_window()
            if start:
                bookings = bookings.filter(date__gte=start)
            if end:
                bookings = bookings.filter(date__lte=end)
            if not bookings.exists():
                raise Http404
        return Response({'code': 200, 'data': coach_history(booking.reservation)})


class CoachCourseAlbumAPI(PayrollCsrfMixin, APIView):
    permission_classes = [IsTenantCoach]
    parser_classes = [JSONParser, MultiPartParser]

    def get(self, request, client_code, booking_id):
        booking = get_object_or_404(coach_bookings(request).filter(ended_sessions()), pk=booking_id)
        places = list(booking.reservation.members.select_related('learner', 'user').order_by('pk'))
        ids = {row.pk for row in places}
        return Response({'code': 200, 'data': {
            'photo_limit_bytes': settings.COURSE_MEDIA_MAX_PHOTO_BYTES,
            'video_limit_bytes': settings.COURSE_MEDIA_MAX_VIDEO_BYTES,
            'members': [{'id': row.pk, 'name': row.learner.name if row.learner_id else row.display_name} for row in places],
            'assets': [album_asset_payload(asset, request.tenant, ids)
                       for asset in booking.album_assets.prefetch_related('tagged_members')],
        }})

    @transaction.atomic
    def post(self, request, client_code, booking_id):
        booking = get_object_or_404(coach_bookings(request).filter(ended_sessions()).select_for_update(), pk=booking_id)
        try:
            asset = save_album_upload(booking, request.user, request.FILES.get('file'))
        except ValueError as exc:
            return Response({'msg': str(exc)}, status=400)
        except OSError:
            return Response({'msg': '檔案暫時無法儲存，請稍後再試'}, status=503)
        return Response({'code': 201, 'data': album_asset_payload(asset, request.tenant, set())}, status=201)

    @transaction.atomic
    def patch(self, request, client_code, booking_id):
        booking = get_object_or_404(coach_bookings(request).filter(ended_sessions()).select_for_update(), pk=booking_id)
        try:
            asset_id = profile_id(request.data.get('asset_id'))
            member_id = profile_id(request.data.get('member_id'))
            if type(request.data.get('tagged')) is not bool:
                raise ValueError('請選擇加入或移除標籤')
        except ValueError as exc:
            return Response({'msg': str(exc)}, status=400)
        asset = get_object_or_404(booking.album_assets, pk=asset_id)
        place = get_object_or_404(booking.reservation.members.select_for_update(), pk=member_id)
        if request.data['tagged']:
            asset.tagged_members.add(place)
        else:
            asset.tagged_members.remove(place)
        return Response({'code': 200})


class EvaluationLearnerLinkViewSet(CourseEvaluationAdminViewSet):
    """Use the existing evaluation and campus authorization for legacy links."""
    http_method_names = ['get', 'patch', 'head', 'options']

    def profile_choices(self, request, *args, **kwargs):
        evaluation = self.get_object()
        place = evaluation.member
        if request.method == 'GET':
            return Response({'code': 200, 'data': {
                'profiles': profile_options(request.tenant, place_owner_id(place)),
                'current_id': place.learner_id,
            }})
        if request.data.get('verified') is not True:
            return Response({'msg': '請先核對這兩筆資料屬於同一位學員'}, status=400)
        with transaction.atomic():
            Reservation.objects.select_for_update().get(pk=place.reservation_id)
            place = get_object_or_404(MemberDetail.objects.select_for_update(), pk=place.pk)
            try:
                bind_profile(place, request.data.get('profile_id'), client=request.tenant)
            except ValueError as exc:
                return Response({'msg': str(exc)}, status=400)
        return Response({'code': 200, 'data': {'current_id': place.learner_id}})
