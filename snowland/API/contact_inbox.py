from collections.abc import Mapping
from ipaddress import ip_address
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers, mixins
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from Client.models import ContactMessage, ContactInboxSettings
from Client.contact_inbox import send_contact_notification
from booking.api_views import resolve_tenant_client, TenantResolutionError
from .admin_views import IsTenantManager, _require_headquarters


class ContactPublicThrottle(SimpleRateThrottle):
    scope = 'contact_public'
    rate = getattr(settings, 'SNOWLAND_CONTACT_RATE', '5/min')

    def get_cache_key(self, request, view):
        # Do not trust arbitrary client-supplied X-Forwarded-For headers.
        ident = request.META.get('REMOTE_ADDR', '')
        trusted = set(getattr(settings, 'SNOWLAND_CONTACT_TRUSTED_PROXY_IPS', ()))
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if ident in trusted and forwarded and len(forwarded) <= 1000:
            for part in reversed(forwarded.split(',')):
                try:
                    candidate = str(ip_address(part.strip()))
                except ValueError:
                    ident = request.META.get('REMOTE_ADDR', '')
                    break
                if candidate not in trusted:
                    ident = candidate
                    break
        return self.cache_format % {'scope': self.scope, 'ident': view.kwargs.get('client_code', '') + ':' + ident}


class ContactInputSerializer(serializers.Serializer):
    submission_id = serializers.UUIDField()
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=50, allow_blank=True, required=False, default='')
    subject = serializers.CharField(max_length=200)
    message = serializers.CharField(max_length=10000)

    def validate(self, attrs):
        if any('\x00' in value for value in attrs.values() if isinstance(value, str)):
            raise serializers.ValidationError('內容含不支援的字元')
        return attrs


class PublicContactAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def get_throttles(self):
        return [ContactPublicThrottle()] if self.request.method == 'POST' else []

    def get(self, request, client_code):
        try:
            client = resolve_tenant_client(client_code)
        except TenantResolutionError:
            return Response({'error': '找不到此網站'}, status=404)
        config = ContactInboxSettings.objects.filter(client=client).first()
        return Response({'enabled': bool(config and config.enabled)})

    def post(self, request, client_code):
        try:
            client = resolve_tenant_client(client_code)
        except TenantResolutionError:
            return Response({'error': '找不到此網站'}, status=404)
        config = ContactInboxSettings.objects.filter(client=client).first()
        if not config or not config.enabled:
            return Response({'error': '聯絡表單暫未開放，請使用本頁的Email或LINE聯絡'}, status=503)
        data = ContactInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data
        with transaction.atomic():
            row, created = ContactMessage.objects.get_or_create(
                client=client, submission_id=fields['submission_id'],
                defaults={**{k: v for k, v in fields.items() if k != 'submission_id'}, 'notification_status': 'pending' if config.notify_enabled else 'off'},
            )
            if not created and any(getattr(row, key) != value for key, value in fields.items()):
                return Response({'error': '送出資料已變更，請重新送出'}, status=409)
            if created and row.notification_status == 'pending':
                transaction.on_commit(lambda: send_contact_notification(row.pk))
        return Response({'ok': True, 'reference': str(row.submission_id), 'message': '已收到您的訊息，我們會盡快回覆。'}, status=201 if created else 200)


class InboxPermission(IsTenantManager):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.can_view_all_campuses


class InboxSettingsSerializer(serializers.ModelSerializer):
    notify_emails = serializers.ListField(child=serializers.EmailField(), max_length=10, required=False)

    class Meta:
        model = ContactInboxSettings
        fields = ['enabled', 'notify_enabled', 'notify_emails']

    def validate(self, attrs):
        enabled = attrs.get('notify_enabled', getattr(self.instance, 'notify_enabled', False))
        emails = attrs.get('notify_emails', getattr(self.instance, 'notify_emails', []))
        if enabled and not emails:
            raise serializers.ValidationError({'notify_emails': '啟用通知信前請填寫收件信箱'})
        if 'notify_emails' in attrs:
            attrs['notify_emails'] = list(dict.fromkeys(emails))
        return attrs


class ContactMessageSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True, default='')

    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'phone', 'subject', 'message', 'status', 'admin_note', 'notification_status', 'updated_by_name', 'created_at', 'updated_at']
        read_only_fields = [f for f in fields if f not in ('status', 'admin_note')]
        extra_kwargs = {'admin_note': {'max_length': 10000}}

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        if set(data) - {'status', 'admin_note'}:
            raise ValidationError({'non_field_errors': ['此處僅可修改處理狀態與內部備註，不可更改訪客原文']})
        return super().to_internal_value(data)


class ContactInboxViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, GenericViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [InboxPermission]
    permission_key = 'contact_inbox'
    serializer_class = ContactMessageSerializer
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    def get_queryset(self):
        qs = ContactMessage.objects.filter(client=self.request.tenant).select_related('updated_by')
        state = self.request.query_params.get('status', '')
        if state:
            if state not in ('new', 'processing', 'resolved'):
                raise ValidationError('處理狀態不正確')
            qs = qs.filter(status=state)
        search = self.request.query_params.get('search', '').strip()[:200]
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search) | Q(subject__icontains=search))
        return qs

    def list(self, request, *args, **kwargs):
        try:
            page = max(1, int(request.query_params.get('page', '1')))
        except (TypeError, ValueError):
            raise ValidationError('頁碼請填寫整數')
        rows = self.get_queryset()
        return Response({'code': 200, 'msg': 'OK', 'data': {'list': self.get_serializer(rows[(page-1)*20:page*20], many=True).data, 'total': rows.count(), 'page': page}})

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=['get', 'patch'], url_path='settings')
    def inbox_settings(self, request, *args, **kwargs):
        if request.method == 'PATCH':
            _require_headquarters(request)
        config = ContactInboxSettings.objects.filter(client=request.tenant).first()
        if request.method == 'GET':
            return Response({'code': 200, 'data': InboxSettingsSerializer(config).data if config else {'enabled': False, 'notify_enabled': False, 'notify_emails': []}})
        serializer = InboxSettingsSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            config, _ = ContactInboxSettings.objects.get_or_create(client=request.tenant)
            config = ContactInboxSettings.objects.select_for_update().get(pk=config.pk)
            serializer = InboxSettingsSerializer(config, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response({'code': 200, 'msg': '設定已儲存', 'data': serializer.data})

    @action(detail=True, methods=['post'], url_path='retry-notification')
    def retry_notification(self, request, *args, **kwargs):
        row = self.get_object()
        with transaction.atomic():
            locked = ContactMessage.objects.select_for_update().get(pk=row.pk, client=request.tenant)
            if locked.notification_status != 'failed':
                return Response({'error': '只有發送失敗的通知可重試'}, status=409)
            config = ContactInboxSettings.objects.filter(client=request.tenant, notify_enabled=True).first()
            if not config or not config.notify_emails:
                return Response({'error': '請先啟用通知並設定收件信箱'}, status=400)
            locked.notification_status = 'pending'
            locked.save(update_fields=['notification_status'])
            transaction.on_commit(lambda: send_contact_notification(locked.pk))
        return Response({'code': 200, 'msg': '已安排重試；請重新載入確認通知結果'})
