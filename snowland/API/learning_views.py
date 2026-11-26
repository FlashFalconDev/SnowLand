from collections.abc import Mapping
import logging

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.learning_portal import (
    CONFIRMED_COURSE_STATES, album_asset_payload, bind_profile, coach_history,
    ended_sessions, place_owner_id, profile_id, profile_options,
)
from booking.media_files import save_album_upload
from booking.models import Booking, CourseAlbumAsset, MemberDetail, Reservation
from Client.tenant_settings import course_album_coach_delete_enabled
from .admin_views import (
    CourseEvaluationAdminViewSet, IsTenantCoach, IsTenantManager, PayrollCsrfMixin,
    _coach_can_view_full_schedule, _coach_visible_window, _with_current_schedule_payment,
    evaluation_is_readonly_assistant,
)


logger = logging.getLogger(__name__)


def coach_bookings(request):
    return Booking.objects.filter(
        reservation__group__client=request.tenant,
        reservation__status__in=CONFIRMED_COURSE_STATES,
        reservation__preferred_coach__user=request.user,
        reservation__preferred_coach__client=request.tenant,
    ).select_related('reservation__preferred_coach', 'reservation__group')


def coach_album_bookings(request):
    return _with_current_schedule_payment(
        coach_bookings(request).filter(ended_sessions()), 'reservation__group_id', historical=True,
    )


def manager_album_bookings(request):
    bookings = Booking.objects.filter(reservation__group__client=request.tenant)
    if not request.can_view_all_campuses or request.selected_campus_id is not None:
        bookings = bookings.filter(reservation__group__campus_id__in=request.campus_ids)
    return bookings


def album_response(request, booking, can_delete):
    places = list(booking.reservation.members.select_related('learner', 'user').order_by('pk'))
    ids = {row.pk for row in places}
    return Response({'code': 200, 'data': {
        'photo_limit_bytes': settings.COURSE_MEDIA_MAX_PHOTO_BYTES,
        'video_limit_bytes': settings.COURSE_MEDIA_MAX_VIDEO_BYTES,
        'members': [{'id': row.pk, 'name': row.learner.name if row.learner_id else row.display_name} for row in places],
        'assets': [{**album_asset_payload(asset, request.tenant, ids), 'can_delete': can_delete(asset)}
                   for asset in booking.album_assets.order_by('pk').prefetch_related('tagged_members')],
    }})


def delete_album_asset(request, bookings, booking_id, *, manager=False):
    try:
        asset_id = profile_id(int(request.query_params.get('asset_id', '')))
    except ValueError:
        return Response({'msg': '請指定要刪除的相簿附件'}, status=400)

    try:
        with transaction.atomic():
            booking = get_object_or_404(bookings.select_for_update(), pk=booking_id)
            asset = booking.album_assets.select_for_update().filter(pk=asset_id).first()
            audit = {
                'content_type': ContentType.objects.get_for_model(CourseAlbumAsset),
                'object_id': str(asset_id),
                'action_flag': DELETION,
                'change_message': f'刪除共用相簿附件（租戶 {request.tenant.pk}、堂次 {booking.pk}）',
            }
            if asset is None:
                previous = LogEntry.objects.filter(**audit)
                if not manager:
                    previous = previous.filter(user=request.user)
                if previous.exists():
                    return Response(status=204)
                raise Http404
            if not manager and asset.uploaded_by_id != request.user.pk:
                raise PermissionDenied('只能刪除自己上傳的相簿附件')
            LogEntry.objects.create(**audit, user=request.user, object_repr=f'共用相簿附件 {asset_id}')
            asset.delete()
            # A storage error rolls back the row, tags and audit entry so the same request can retry.
            asset.file.delete(save=False)
    except (OSError, BotoCoreError, ClientError):
        logger.exception('Course album file deletion failed (tenant=%s booking=%s asset=%s actor=%s)',
                         request.tenant.pk, booking_id, asset_id, request.user.pk)
        return Response({'msg': '暫時無法刪除相簿檔案，請稍後重試'}, status=503)
    return Response(status=204)


class CoachLearnerHistoryAPI(APIView):
    permission_classes = [IsTenantCoach]

    def get(self, request, client_code, reservation_id):
        bookings = _with_current_schedule_payment(
            coach_bookings(request).live().filter(reservation_id=reservation_id), 'reservation__group_id',
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
        booking = get_object_or_404(coach_album_bookings(request), pk=booking_id)
        enabled = course_album_coach_delete_enabled(request.tenant)
        return album_response(request, booking, lambda asset: enabled and asset.uploaded_by_id == request.user.pk)

    @transaction.atomic
    def post(self, request, client_code, booking_id):
        booking = get_object_or_404(coach_album_bookings(request).select_for_update(), pk=booking_id)
        try:
            asset = save_album_upload(booking, request.user, request.FILES.get('file'))
        except ValueError as exc:
            return Response({'msg': str(exc)}, status=400)
        except (OSError, BotoCoreError, ClientError):
            return Response({'msg': '檔案暫時無法儲存，請稍後再試'}, status=503)
        return Response({'code': 201, 'data': album_asset_payload(asset, request.tenant, set())}, status=201)

    @transaction.atomic
    def patch(self, request, client_code, booking_id):
        booking = get_object_or_404(coach_album_bookings(request).select_for_update(), pk=booking_id)
        if not isinstance(request.data, Mapping):
            return Response({'msg': '相簿標籤資料格式錯誤'}, status=400)
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

    def delete(self, request, client_code, booking_id):
        if not course_album_coach_delete_enabled(request.tenant):
            raise PermissionDenied('此學校的相簿附件由管理者刪除')
        return delete_album_asset(request, coach_album_bookings(request), booking_id)


class ManagerCourseAlbumAPI(PayrollCsrfMixin, APIView):
    permission_classes = [IsTenantManager]
    permission_key = 'evaluations'

    def get(self, request, client_code, booking_id):
        booking = get_object_or_404(manager_album_bookings(request), pk=booking_id)
        can_delete = not evaluation_is_readonly_assistant(request)
        return album_response(request, booking, lambda asset: can_delete)

    def delete(self, request, client_code, booking_id):
        if evaluation_is_readonly_assistant(request):
            raise PermissionDenied('行政無法刪除相簿附件')
        return delete_album_asset(request, manager_album_bookings(request), booking_id, manager=True)


class EvaluationLearnerLinkViewSet(CourseEvaluationAdminViewSet):
    """Use the existing evaluation and campus authorization for legacy links."""
    http_method_names = ['get', 'patch', 'head', 'options']

    def profile_choices(self, request, *args, **kwargs):
        evaluation = self.get_object()
        place = evaluation.member
        if request.method in {'GET', 'HEAD'}:
            return Response({'code': 200, 'data': {
                'profiles': profile_options(request.tenant, place_owner_id(place)),
                'current_id': place.learner_id,
            }})
        if not isinstance(request.data, Mapping) or request.data.get('verified') is not True:
            return Response({'msg': '請先核對這兩筆資料屬於同一位學員'}, status=400)
        with transaction.atomic():
            get_object_or_404(Reservation.objects.live().select_for_update(), pk=place.reservation_id)
            place = get_object_or_404(MemberDetail.objects.live().select_for_update(), pk=place.pk)
            try:
                bind_profile(place, request.data.get('profile_id'), client=request.tenant)
            except ValueError as exc:
                return Response({'msg': str(exc)}, status=400)
        return Response({'code': 200, 'data': {'current_id': place.learner_id}})
