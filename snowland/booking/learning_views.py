from collections.abc import Mapping

from django.db import transaction
from django.http import Http404
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .learning_portal import (
    CONFIRMED_COURSE_STATES, album_asset_payload, bind_profile, ended_sessions,
    owned_places, profile_id, profile_options,
)
from .media_files import private_file_response
from .models import Booking, CourseAlbumAsset, LearnerProfile, MemberDetail, Reservation


def tenant_for(code):
    from .api_views import TenantResolutionError, resolve_tenant_client

    try:
        return resolve_tenant_client(code)
    except TenantResolutionError as exc:
        raise Http404 from exc


def member_album_bookings(tenant, user):
    reservations = MemberDetail.objects.filter(owned_places(user), reservation__group__client=tenant).values('reservation_id')
    return Booking.objects.filter(
        ended_sessions(), reservation_id__in=reservations,
        reservation__status__in=CONFIRMED_COURSE_STATES, reservation__group__client=tenant,
    )


class PrivateLearningAPI(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {'GET', 'HEAD'}:
            get_token(request._request)


class LearnerProfileAPI(PrivateLearningAPI):
    def get(self, request, client_code):
        return Response({'profiles': profile_options(tenant_for(client_code), request.user.pk)})

    @transaction.atomic
    def post(self, request, client_code):
        tenant = tenant_for(client_code)
        if not isinstance(request.data, Mapping):
            return Response({'error': '學員資料格式錯誤'}, status=400)
        action = request.data.get('action')
        if action == 'create':
            name = request.data.get('name')
            if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
                return Response({'error': '請填寫學員姓名（最多 120 字）'}, status=400)
            profile = LearnerProfile.objects.create(client=tenant, owner=request.user, name=name.strip())
            return Response({'id': profile.pk, 'name': profile.name}, status=201)
        if action != 'bind':
            return Response({'error': '不支援的學員操作'}, status=400)
        try:
            member_id = profile_id(request.data.get('member_id'))
            place_query = MemberDetail.objects.filter(owned_places(request.user), pk=member_id, reservation__group__client=tenant)
            candidate = get_object_or_404(place_query)
            reservation = get_object_or_404(Reservation.objects.select_for_update(), pk=candidate.reservation_id)
            place = get_object_or_404(place_query.select_for_update())
            if reservation.status in {'completed', 'cancelled', 'deleted'} or place.evaluations.filter(completed_at__isnull=False).exists():
                return Response({'error': '已結束的課程須請學校核對學員紀錄'}, status=409)
            if place.learner_id:
                return Response({'error': '此名額已連結學員，若需更正請聯繫學校'}, status=409)
            bind_profile(place, request.data.get('profile_id'), client=tenant)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)
        return Response({'id': place.learner_id})


class MemberCourseAlbumsAPI(PrivateLearningAPI):
    def get(self, request, client_code):
        tenant = tenant_for(client_code)
        bookings = member_album_bookings(tenant, request.user).filter(
            album_assets__isnull=False,
        ).distinct().select_related('reservation__group', 'reservation__resort').prefetch_related(
            'album_assets__tagged_members', 'reservation__members__learner',
        ).order_by('-date', 'start_time', 'pk')
        albums = []
        for booking in bookings:
            own = [place for place in booking.reservation.members.all() if (place.guardian_id or place.user_id) == request.user.pk]
            ids = {place.pk for place in own}
            albums.append({
                'id': booking.pk, 'date': str(booking.date), 'start_time': str(booking.start_time)[:5],
                'course_name': booking.course_name, 'order_number': booking.reservation.group.order_number,
                'members': [{'id': place.pk, 'name': place.learner.name if place.learner_id else place.display_name}
                            for place in own],
                'assets': [album_asset_payload(asset, tenant, ids) for asset in booking.album_assets.all()],
            })
        return Response({'albums': albums})

    @transaction.atomic
    def patch(self, request, client_code):
        tenant = tenant_for(client_code)
        if not isinstance(request.data, Mapping):
            return Response({'error': '相簿資料格式錯誤'}, status=400)
        try:
            asset_id = profile_id(request.data.get('asset_id'))
            member_id = profile_id(request.data.get('member_id'))
            if type(request.data.get('tagged')) is not bool:
                raise ValueError('請選擇認領或取消認領')
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)
        asset = get_object_or_404(CourseAlbumAsset.objects.select_related('booking'), pk=asset_id,
                                  booking__in=member_album_bookings(tenant, request.user))
        place = get_object_or_404(MemberDetail.objects.select_for_update().filter(owned_places(request.user)),
                                   pk=member_id, reservation_id=asset.booking.reservation_id)
        if request.data['tagged']:
            asset.tagged_members.add(place)
        else:
            asset.tagged_members.remove(place)
        return Response({'tagged': request.data['tagged']})


class CourseAlbumFileAPI(PrivateLearningAPI):
    def get(self, request, client_code, asset_id):
        tenant = tenant_for(client_code)
        asset = get_object_or_404(CourseAlbumAsset.objects.select_related('booking__reservation'),
                                  pk=asset_id, booking__reservation__group__client=tenant)
        from API.admin_views import IsTenantCoach
        booking = asset.booking
        allowed = member_album_bookings(tenant, request.user).filter(pk=booking.pk).exists()
        if not allowed:
            allowed = IsTenantCoach().has_permission(request, self) and Booking.objects.filter(
                ended_sessions(), pk=booking.pk, reservation__group__client=tenant,
                reservation__preferred_coach__user=request.user, reservation__preferred_coach__client=tenant,
                reservation__status__in=CONFIRMED_COURSE_STATES,
            ).exists()
        if not allowed:
            raise Http404
        try:
            return private_file_response(asset, request.headers.get('Range'))
        except OSError as exc:
            raise Http404 from exc
