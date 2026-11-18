import re
import secrets
import time
from hmac import compare_digest

from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect
from django.views.decorators.debug import sensitive_variables
from rest_framework import serializers
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from Client.models import Client, InstagramConnection
from Client.instagram_sync import InstagramError, authorization_url, configuration, connect_account, run_sync
from Control.tenant_memberships import staff_profile
from chatbooking import meta_binding
from chatbooking.channel_binding import bind_line, connection_status
from chatbooking.models import LineChannelBinding, MetaPageBinding
from .admin_permissions import user_has_admin_permission
from .admin_views import IsTenantManager, _campus_scope_for_user, _require_headquarters
from .payroll_security import PayrollCsrfMixin


class ConnectionInput(serializers.Serializer):
    expected_username = serializers.RegexField(r'^[A-Za-z0-9_.]{1,30}$')


@api_view(['GET'])
@sensitive_variables('code', 'credential')
def meta_callback(request):
    pending = request.session.pop('meta_social_oauth', None)
    state = request.query_params.get('state', '')
    if (not isinstance(pending, dict) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', state)
            or not compare_digest(state, pending['state']) or not request.user.is_authenticated
            or pending['user'] != request.user.pk or not 0 <= time.time() - pending['at'] <= 600):
        return HttpResponseBadRequest('授權驗證逾時或不符，請從 Console 重新開始')
    tenant = Client.objects.filter(pk=pending['tenant'], is_active=True).first()
    if not tenant or not user_has_admin_permission(request.user, 'social_sync', tenant):
        return HttpResponseForbidden('沒有官方社群管理權限')
    if not request.user.is_superuser:
        profile = staff_profile(request.user, tenant)
        if not profile or profile.role != 'hq_admin' or not _campus_scope_for_user(request.user, tenant)[1]:
            return HttpResponseForbidden('沒有官方社群管理權限')
    code = request.query_params.get('code', '')
    result = 'declined' if request.query_params.get('error') else 'failed'
    if result == 'failed' and 0 < len(code) <= 4096:
        try:
            if pending.get('page'):
                meta_binding.bind_page(tenant, code, pending['page'])
                result = 'bound'
            else:
                pages, credential = meta_binding.page_choices(code)
                request.session['meta_page_choices'] = {'tenant': tenant.pk, 'user': request.user.pk, 'at': time.time(),
                                                         'pages': pages, 'credential': credential}
                result = 'choose'
        except meta_binding.MetaBindingError:
            pass
    response = redirect(f'/{tenant.internal_code}/console/social-sync?meta={result}')
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


class InstagramSyncViewSet(PayrollCsrfMixin, GenericViewSet):
    permission_classes = [IsTenantManager]
    permission_key = 'social_sync'

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_headquarters(request)

    @action(detail=False, methods=['get', 'put', 'delete'], url_path='line-channel')
    def line_channel(self, request, *args, **kwargs):
        if request.method == 'PUT':
            try:
                bind_line(request.tenant, request.data)
            except ValueError as exc:
                return Response({'code': 400, 'msg': str(exc)}, status=400)
        elif request.method == 'DELETE':
            LineChannelBinding.objects.filter(client=request.tenant).update(
                enabled=False, credentials='', webhook_verified_at=None,
            )
        return Response({'code': 200, 'data': connection_status(request.tenant)})

    @action(detail=False, methods=['get', 'post', 'put', 'delete'], url_path='meta-channel')
    def meta_channel(self, request, *args, **kwargs):
        if request.method == 'DELETE':
            MetaPageBinding.objects.filter(client=request.tenant).delete()
            request.session.pop('meta_social_oauth', None)
            request.session.pop('meta_page_choices', None)
        elif request.method == 'POST':
            if not isinstance(request.data, dict) or set(request.data) - {'page_id'}:
                return Response({'code': 400, 'msg': 'Meta 授權參數錯誤'}, status=400)
            page = request.data.get('page_id')
            if 'page_id' in request.data and (not isinstance(page, str) or not re.fullmatch(r'[0-9]{1,32}', page)):
                return Response({'code': 400, 'msg': 'Facebook 粉絲專頁 ID 格式錯誤'}, status=400)
            state = secrets.token_urlsafe(32)
            try:
                target = meta_binding.authorization_url(state)
            except meta_binding.MetaBindingError as exc:
                return Response({'code': 409, 'msg': str(exc)}, status=409)
            request.session['meta_social_oauth'] = {'state': state, 'tenant': request.tenant.pk,
                                                   'user': request.user.pk, 'at': time.time(), 'page': page}
            request.session.pop('meta_page_choices', None)
            return Response({'code': 200, 'data': {'authorization_url': target}})
        pending = request.session.get('meta_page_choices')
        if not pending or pending['tenant'] != request.tenant.pk or pending['user'] != request.user.pk or not 0 <= time.time() - pending['at'] <= 600:
            pending = None
        if request.method == 'PUT':
            page = request.data.get('page_id') if isinstance(request.data, dict) else None
            if not pending or not isinstance(page, str) or not any(item['id'] == page for item in pending['pages']):
                return Response({'code': 409, 'msg': '請先完成 Meta 授權，再選擇可綁定的粉絲專頁'}, status=409)
            try:
                meta_binding.bind_page_choice(request.tenant, pending['credential'], page)
            except meta_binding.MetaBindingError as exc:
                return Response({'code': 409, 'msg': str(exc)}, status=409)
            request.session.pop('meta_page_choices', None)
            pending = None
        return Response({'code': 200, 'data': {**meta_binding.status(request.tenant), 'available_pages': pending['pages'] if pending else []}},
                        headers={'Cache-Control': 'private, no-store'})

    def list(self, request, *args, **kwargs):
        row = InstagramConnection.objects.filter(client=request.tenant).first()
        _, missing = configuration()
        return Response({'code': 200, 'data': {
            'expected_username': row.expected_username if row else ('snowlandcz' if request.tenant.internal_code == 'snowland' else ''),
            'username': row.username if row else '', 'enabled': bool(row and row.enabled),
            'connected': bool(row and row.encrypted_token), 'missing_configuration': missing,
            'token_expires_at': row.token_expires_at if row else None,
            'last_synced_at': row.last_synced_at if row else None,
            'last_error': row.last_error if row else '',
        }})

    @action(detail=False, methods=['post'])
    def connect(self, request, *args, **kwargs):
        serializer = ConnectionInput(data=request.data); serializer.is_valid(raise_exception=True)
        state = secrets.token_urlsafe(32)
        try:
            url = authorization_url(state)
        except InstagramError as exc:
            return Response({'code': 409, 'msg': str(exc)}, status=409)
        with transaction.atomic():
            request.tenant.__class__.objects.select_for_update().get(pk=request.tenant.pk)
            row, _ = InstagramConnection.objects.get_or_create(client=request.tenant)
            username = serializer.validated_data['expected_username'].lower()
            if row.enabled and row.username.lower() != username:
                return Response({'code': 409, 'msg': '如需更換官方帳號，請先停用現有連線'}, status=409)
            row.expected_username = username; row.save(update_fields=['expected_username'])
        request.session['instagram_oauth'] = {'state': state, 'client': request.tenant.pk,
            'user': request.user.pk, 'created_at': time.time()}
        return Response({'code': 200, 'data': {'authorization_url': url}})

    @action(detail=False, methods=['get'])
    def callback(self, request, *args, **kwargs):
        pending = request.session.pop('instagram_oauth', None)
        state, code = request.query_params.get('state', ''), request.query_params.get('code', '')
        valid = isinstance(pending, dict) and isinstance(state, str) and len(state) <= 200 and (
            compare_digest(state, pending.get('state', '')) and pending.get('client') == request.tenant.pk
            and pending.get('user') == request.user.pk and 0 <= time.time() - pending.get('created_at', 0) <= 600)
        result = 'invalid_state'
        if valid:
            if request.query_params.get('error'):
                result = 'declined'
            elif code and len(code) <= 4096:
                try:
                    connect_account(request.tenant, code)
                    result = 'connected'
                except InstagramError as exc:
                    InstagramConnection.objects.filter(client=request.tenant).update(last_error=str(exc)[:200])
                    result = 'failed'
        # Always return to our own fixed route; never reflect provider/user URLs.
        return redirect(f'/{request.tenant.internal_code}/console/social-sync?ig={result}')

    @action(detail=False, methods=['post'])
    def sync(self, request, *args, **kwargs):
        row = InstagramConnection.objects.filter(client=request.tenant, enabled=True).first()
        if not row:
            return Response({'code': 409, 'msg': '請先由官方帳號管理者完成 IG 授權'}, status=409)
        try:
            count = run_sync(row.pk)
        except InstagramError as exc:
            return Response({'code': 409, 'msg': str(exc)}, status=409)
        return Response({'code': 200, 'msg': f'已同步 {count} 則 IG 貼文', 'data': {'count': count}})

    @action(detail=False, methods=['post'])
    def disconnect(self, request, *args, **kwargs):
        # Local revocation removes stored access; imported posts are retained.
        with transaction.atomic():
            request.tenant.__class__.objects.select_for_update().get(pk=request.tenant.pk)
            row = InstagramConnection.objects.select_for_update().filter(client=request.tenant).first()
            if row:
                row.enabled = False; row.encrypted_token = ''; row.token_expires_at = None
                row.save(update_fields=['enabled', 'encrypted_token', 'token_expires_at'])
            request.session.pop('instagram_oauth', None)
        return Response({'code': 200, 'msg': '已停用並清除本系統的 IG 授權，既有貼文保留；Meta 平台授權可至 IG 帳號設定撤銷'})
