from hashlib import sha256
import json
import re

from django.db import transaction
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from Client.models import RecruitmentForm, SiteContent
from Client.site_translations import (
    CONTENT_FIELDS, CONTENT_KINDS, COURSES, INTERFACE_SCOPES, LANGUAGES, SiteTranslation, content_text,
    course_rows, editable_content, entries_for, public_translation_scopes, recruitment_text,
)
from booking.api_views import TenantResolutionError, resolve_tenant_client
from .contact_inbox import InboxPermission


def version(entries):
    return sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()


def record_fields(tenant, scope):
    if scope in INTERFACE_SCOPES:
        return {}
    if scope == 'recruitment':
        fields = RecruitmentForm.objects.filter(client=tenant).values_list('fields', flat=True).first() or []
        return {key: (label, source) for key, label, source in recruitment_text(fields)}
    match = re.fullmatch(r'(content|category|type|template):([1-9][0-9]{0,17})', scope)
    if not match:
        raise serializers.ValidationError({'scope': '無法識別翻譯項目'})
    kind, pk = match.groups()
    if kind in COURSES:
        course = get_object_or_404(course_rows(tenant, kind), pk=pk)
        return {'name': ('課程名稱', course.name)}
    row = get_object_or_404(editable_content(SiteContent.objects.filter(client=tenant)), pk=pk)
    data = {key: getattr(row, key) for key in CONTENT_FIELDS}
    data['metadata'] = row.metadata
    fields = {}

    def collect(key, label, source):
        fields[key] = (label, source)
        return source

    content_text(data, collect)
    return fields


class TranslationInput(serializers.Serializer):
    key = serializers.CharField(max_length=20000, trim_whitespace=False)
    source = serializers.CharField(max_length=30000, trim_whitespace=False)
    values = serializers.DictField(child=serializers.CharField(max_length=30000, allow_blank=True))

    def validate_values(self, values):
        if set(values) != set(LANGUAGES):
            raise serializers.ValidationError('請提供繁體中文、英文與日文欄位')
        return values


class TranslationChanges(serializers.Serializer):
    revision = serializers.RegexField(r'^[a-f0-9]{64}$')
    updates = TranslationInput(many=True, allow_empty=False, max_length=1500)


class SiteTranslationAdminViewSet(ViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [InboxPermission]
    permission_key = 'site_translations'

    def list(self, request, **kwargs):
        kind = request.query_params.get('kind', '')
        search = request.query_params.get('search', '').strip()[:200]
        try:
            page = max(1, min(100000, int(request.query_params.get('page', 1))))
        except ValueError:
            raise serializers.ValidationError({'page': '頁數格式不正確'})
        if kind in COURSES:
            rows = course_rows(request.tenant, kind).filter(name__icontains=search)
            prefix, label = kind, 'name'
        elif kind in CONTENT_KINDS:
            rows = editable_content(SiteContent.objects.filter(client=request.tenant, content_type=kind, title__icontains=search))
            prefix, label = 'content', 'title'
        else:
            raise serializers.ValidationError({'kind': '無法識別翻譯分類'})
        items = list(rows.order_by(label, 'pk').values_list('pk', label)[(page-1)*40:page*40+1])
        return Response({'items': [{'scope': f'{prefix}:{pk}', 'title': title} for pk, title in items[:40]],
                         'more': len(items) > 40})

    @action(detail=False, methods=['get', 'put'], url_path='entries')
    def entries(self, request, **kwargs):
        scope = request.query_params.get('scope', '')
        fields = record_fields(request.tenant, scope)
        entries = entries_for(request.tenant, scope)
        if request.method == 'GET':
            get_token(request._request)
            return Response({'revision': version(entries), 'entries': entries, 'fields': [
                {'key': key, 'label': label, 'source': source} for key, (label, source) in fields.items()
            ]})
        serializer = TranslationChanges(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            saved, _ = SiteTranslation.objects.get_or_create(client=request.tenant, scope=scope)
            saved = SiteTranslation.objects.select_for_update().get(pk=saved.pk)
            if version(saved.entries) != data['revision']:
                return Response({'error': '這份翻譯已由其他人更新，請重新載入後再編輯'}, status=409)
            current_fields = record_fields(request.tenant, scope) if scope not in INTERFACE_SCOPES else fields
            entries = saved.entries.copy()
            for item in data['updates']:
                key, source, values = item['key'], item['source'], item['values']
                if (scope in INTERFACE_SCOPES and key != source) or (scope not in INTERFACE_SCOPES and current_fields.get(key, ('', None))[1] != source):
                    return Response({'error': '原文已變更，請重新載入後再編輯'}, status=409)
                if scope in INTERFACE_SCOPES:
                    tokens = set(re.findall(r'\{[a-zA-Z][a-zA-Z0-9_]*\}', source))
                    if any(value and set(re.findall(r'\{[a-zA-Z][a-zA-Z0-9_]*\}', value)) != tokens
                           for value in values.values()):
                        raise serializers.ValidationError({'values': '介面文字須保留原有的 {變數}'})
                if any(values.values()) or scope in INTERFACE_SCOPES:
                    entries[key] = {'source': source, 'values': values}
                else:
                    entries.pop(key, None)
            saved.entries = entries
            saved.save(update_fields=['entries'])
        return Response({'revision': version(entries), 'entries': entries})


class PublicSiteTranslationsAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, client_code):
        try:
            client = resolve_tenant_client(client_code)
        except TenantResolutionError:
            return Response({'error': '找不到此網站'}, status=404)
        response = Response({'scopes': public_translation_scopes(client)})
        response['Cache-Control'] = 'no-store'
        return response
