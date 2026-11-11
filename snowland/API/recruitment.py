import json
import logging
from hashlib import sha256
from uuid import uuid4

from django.contrib.auth import SESSION_KEY
from django.core.files.utils import validate_file_name
from django.db import transaction
from django.http import FileResponse
from rest_framework import mixins, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from Client.models import RecruitmentApplication, RecruitmentForm
from Client.recruitment import (
    FILE_FORMATS, MAX_UPLOAD_BYTES, MB, RecruitmentSettingsSerializer,
    digest, form_settings, validate_answers,
)
from booking.api_views import TenantResolutionError, resolve_tenant_client
from booking.media_files import PrivateCourseMediaStorage
from .contact_inbox import ContactPublicThrottle, InboxPermission


logger = logging.getLogger(__name__)


class RecruitmentThrottle(ContactPublicThrottle):
    scope = 'recruitment_public'


class ApplicationInput(serializers.Serializer):
    submission_id = serializers.UUIDField()
    revision = serializers.CharField(max_length=64)
    answers = serializers.CharField(max_length=200000, trim_whitespace=False)


def upload_digest(upload):
    checksum = sha256()
    for chunk in upload.chunks():
        checksum.update(chunk)
    upload.seek(0)
    return checksum.hexdigest()


def save_application(client, request, values, answers):
    files = request.FILES
    if len(files) > 5 or any(len(uploads) != 1 for _, uploads in files.lists()):
        raise serializers.ValidationError('每個附件欄位只能上傳一個檔案')
    if sum(upload.size for upload in files.values()) > MAX_UPLOAD_BYTES:
        raise serializers.ValidationError('附件合計不得超過 20 MB')
    fingerprint = digest({
        'revision': values['revision'], 'answers': answers,
        'files': {key: [upload.name, upload_digest(upload)] for key, upload in files.items()},
    })
    submission_id = values['submission_id']
    saved = {}
    storage = PrivateCourseMediaStorage()
    try:
        with transaction.atomic():
            form = RecruitmentForm.objects.select_for_update().filter(client=client).first()
            previous = RecruitmentApplication.objects.filter(client=client, submission_id=submission_id).first()
            if previous:
                if previous.fingerprint != fingerprint:
                    return Response({'error': '這組送件編號已有不同的內容'}, status=409)
                return Response({'reference': submission_id})
            config = form_settings(form)
            if not config['enabled']:
                return Response({'error': '目前未開放站內應徵'}, status=503)
            if config['revision'] != values['revision']:
                return Response({'error': '表單已更新，請重新載入再填寫', 'reload': True}, status=409)
            fields = config['fields']
            if (set(answers) - {field['id'] for field in fields if field['type'] != 'file'}
                or set(files) - {f'file_{field["id"]}' for field in fields if field['type'] == 'file'}):
                raise serializers.ValidationError('回答包含表單上沒有的欄位')
            clean_answers, file_formats = validate_answers(fields, answers, files)
            for field_id, file_format in file_formats.items():
                upload = files[f'file_{field_id}']
                name = validate_file_name(upload.name)
                extension, _ = FILE_FORMATS[file_format]
                path = storage.save(f'recruitment/{client.pk}/{uuid4().hex}{extension}', upload)
                saved[field_id] = {'name': name, 'format': file_format, 'size': upload.size, 'path': path}
            RecruitmentApplication.objects.create(
                client=client, submission_id=submission_id, fields=fields, answers=clean_answers,
                attachments=saved, fingerprint=fingerprint,
            )
    except Exception:
        for attachment in saved.values():
            try:
                storage.delete(attachment['path'])
            except Exception:
                logger.exception('Unable to clean a failed recruitment upload')
        raise
    return Response({'reference': submission_id}, status=201)


class PublicRecruitmentAPI(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser]

    def get_throttles(self):
        return [RecruitmentThrottle()] if self.request.method == 'POST' else []

    def get(self, request, client_code):
        try:
            client = resolve_tenant_client(client_code)
        except TenantResolutionError:
            return Response({'error': '找不到此網站'}, status=404)
        config = form_settings(RecruitmentForm.objects.filter(client=client).first())
        response = Response(config if config['enabled'] else {'enabled': False})
        response['Cache-Control'] = 'no-store'
        return response

    def post(self, request, client_code):
        try:
            client = resolve_tenant_client(client_code)
        except TenantResolutionError:
            return Response({'error': '找不到此網站'}, status=404)
        try:
            size = int(request.META.get('CONTENT_LENGTH') or '0')
        except ValueError:
            return Response({'error': '請求大小不正確'}, status=400)
        if size > MAX_UPLOAD_BYTES + MB:
            return Response({'error': '附件合計不得超過 20 MB'}, status=413)
        serializer = ApplicationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            answers = json.loads(values['answers'])
        except (ValueError, RecursionError):
            raise serializers.ValidationError('回答格式不正確')
        if not isinstance(answers, dict) or any(
            not isinstance(value, str)
            and (not isinstance(value, list) or any(not isinstance(option, str) for option in value))
            for value in answers.values()
        ):
            raise serializers.ValidationError('回答格式不正確')
        return save_application(client, request, values, answers)


class RecruitmentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecruitmentApplication
        fields = ('id', 'submission_id', 'submitted_at')


class RecruitmentDetailSerializer(RecruitmentListSerializer):
    attachments = serializers.SerializerMethodField()

    class Meta(RecruitmentListSerializer.Meta):
        fields = (*RecruitmentListSerializer.Meta.fields, 'fields', 'answers', 'attachments')

    def get_attachments(self, application):
        return {
            field_id: {key: attachment[key] for key in ('name', 'format', 'size')}
            for field_id, attachment in application.attachments.items()
        }


class RecruitmentPagination(PageNumberPagination):
    page_size = 20


class RecruitmentSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        # Applicant data requires a real login even with the local admin bypass enabled.
        if SESSION_KEY not in request.session:
            return None
        return super().authenticate(request)


class RecruitmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    authentication_classes = [RecruitmentSessionAuthentication]
    permission_classes = [InboxPermission]
    permission_key = 'recruitment'
    serializer_class = RecruitmentDetailSerializer
    pagination_class = RecruitmentPagination

    def get_queryset(self):
        queryset = RecruitmentApplication.objects.filter(client=self.request.tenant)
        if self.action == 'list':
            return queryset.only('id', 'submission_id', 'submitted_at')
        return queryset

    def get_serializer_class(self):
        return RecruitmentListSerializer if self.action == 'list' else self.serializer_class

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response

    @action(detail=False, methods=['get', 'put'], url_path='settings')
    def form_settings(self, request, **kwargs):
        if request.method == 'GET':
            return Response(form_settings(RecruitmentForm.objects.filter(client=request.tenant).first()))
        serializer = RecruitmentSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        with transaction.atomic():
            form, _ = RecruitmentForm.objects.get_or_create(client=request.tenant)
            form = RecruitmentForm.objects.select_for_update().get(pk=form.pk)
            if values['revision'] != form_settings(form)['revision']:
                return Response({'error': '設定已由其他人修改，請重新載入'}, status=409)
            form.enabled = values['enabled']
            form.fields = values['fields']
            form.save(update_fields=['enabled', 'fields'])
        return Response(form_settings(form))

    @action(detail=True, methods=['get'], url_path=r'attachments/(?P<field_id>[a-z0-9_-]{1,64})')
    def attachment(self, request, field_id, **kwargs):
        application = self.get_object()
        attachment = application.attachments.get(field_id)
        if attachment is None:
            return Response({'error': '找不到附件'}, status=404)
        storage = PrivateCourseMediaStorage()
        try:
            stream = storage.open(attachment['path'], 'rb')
        except FileNotFoundError:
            return Response({'error': '找不到附件'}, status=404)
        response = FileResponse(
            stream, as_attachment=True, filename=attachment['name'],
            content_type=FILE_FORMATS[attachment['format']][1],
        )
        response['X-Content-Type-Options'] = 'nosniff'
        return response
