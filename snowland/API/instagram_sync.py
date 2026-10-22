import secrets
import time
from hmac import compare_digest

from django.db import transaction
from django.shortcuts import redirect
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from Client.models import InstagramConnection
from Client.instagram_sync import InstagramError, authorization_url, configuration, connect_account, run_sync
from .admin_views import IsTenantManager, _require_headquarters
from .payroll_security import PayrollCsrfMixin


class ConnectionInput(serializers.Serializer):
    expected_username = serializers.RegexField(r'^[A-Za-z0-9_.]{1,30}$')


class InstagramSyncViewSet(PayrollCsrfMixin, GenericViewSet):
    permission_classes = [IsTenantManager]
    permission_key = 'cms'

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_headquarters(request)

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
