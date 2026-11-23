"""Bearer-only entry points for the FlashFalcon frontend publishing service."""
import hashlib
import hmac
import logging
import os
import re
from uuid import UUID

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, NotFound, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from Client.models import Client, FrontendDeployment, FrontendRelease

from . import frontend_publish as publish
from .frontend_cli_archive import validate_archive
from .frontend_releases import MAX_ARCHIVE_BYTES, STORAGE_ERRORS, SUPPORT_CLIENT_CODE, release_storage, storage_unavailable

logger = logging.getLogger(__name__)
CURRENT_TOKEN_DIGEST = 'SNOWLAND_FRONTEND_CLI_TOKEN_SHA256'
PREVIOUS_TOKEN_DIGEST = 'SNOWLAND_FRONTEND_CLI_TOKEN_PREVIOUS_SHA256'


class PublisherIdentity:
    # Both rotation slots represent the same service identity, with no Django user privileges.
    is_authenticated = True


def configured_digest(name):
    value = os.getenv(name, '').strip()
    return value.lower() if re.fullmatch(r'[0-9a-fA-F]{64}', value) else None


class PublisherAuthentication(BaseAuthentication):
    @sensitive_variables()
    def authenticate(self, request):
        # Remove credentials from the request before parsing uploads or calling the publisher.
        parts = request.META.pop('HTTP_AUTHORIZATION', '').split()
        request._request.__dict__.pop('headers', None)  # Drop any cached HttpHeaders copy.
        current = configured_digest(CURRENT_TOKEN_DIGEST)
        if not current:
            raise NotFound()
        if len(parts) != 2 or parts[0].lower() != 'bearer' or not re.fullmatch(r'[!-~]{1,512}', parts[1]):
            raise AuthenticationFailed('需要有效的發布憑證。')
        candidate = hashlib.sha256(parts[1].encode('ascii')).hexdigest()
        previous = configured_digest(PREVIOUS_TOKEN_DIGEST)
        matches_current = hmac.compare_digest(candidate, current)
        matches_previous = hmac.compare_digest(candidate, previous or '0' * 64)
        if not (matches_current or (previous and matches_previous)):
            raise AuthenticationFailed('需要有效的發布憑證。')
        return PublisherIdentity(), None

    def authenticate_header(self, request):
        return 'Bearer'


def job_response(job, status=200):
    return Response({'request_id': str(job.cli_request_id), 'deployment': publish.job_data(job)}, status=status)


@method_decorator(never_cache, name='dispatch')
class PublisherView(APIView):
    authentication_classes = [PublisherAuthentication]
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = get_object_or_404(Client, internal_code=SUPPORT_CLIENT_CODE, is_active=True)
        if tenant.internal_code != SUPPORT_CLIENT_CODE:
            raise NotFound()
        self.client_id = tenant.pk

    def jobs(self):
        return FrontendDeployment.objects.filter(client_id=self.client_id, cli_request_id__isnull=False, operation='publish')


class PublisherJobView(PublisherView):
    http_method_names = ['get']

    def get(self, request, request_id):
        return job_response(get_object_or_404(self.jobs(), cli_request_id=request_id))


class PublisherUploadView(PublisherView):
    http_method_names = ['post']
    parser_classes = [MultiPartParser]

    def post(self, request):
        key = request.META.get('HTTP_IDEMPOTENCY_KEY', '')
        try:
            request_id = UUID(key)
            if str(request_id) != key.lower():
                raise ValueError
        except ValueError:
            raise ValidationError({'detail': 'Idempotency-Key 必須是 UUID。'}) from None

        uploads = request.FILES.getlist('archive')
        if (len(uploads) != 1 or set(request.data) != {'archive'} or len(request.data.getlist('archive')) != 1
                or not uploads[0].name.lower().endswith('.zip')):
            raise ValidationError({'detail': '請以 archive 欄位上傳單一 ZIP 檔案。'})
        upload = uploads[0]
        if upload.size > MAX_ARCHIVE_BYTES:
            return Response({'detail': 'ZIP 檔案不得超過 768 MiB。'}, status=413)
        digest = hashlib.file_digest(upload, 'sha256').hexdigest()
        upload.seek(0)

        storage = None
        new_archive = None
        try:
            with transaction.atomic():
                tenant = get_object_or_404(Client.objects.select_for_update(), pk=self.client_id,
                                           internal_code=SUPPORT_CLIENT_CODE, is_active=True)
                if tenant.internal_code != SUPPORT_CLIENT_CODE:
                    raise NotFound()
                existing = self.jobs().select_related('release').filter(cli_request_id=request_id).first()
                if existing:
                    if existing.release.sha256 == digest:
                        return job_response(existing, status=202)
                    return Response({'code': 'idempotency_conflict', 'detail': '此 UUID 已用於不同的 ZIP。'}, status=409)
                if publish.active_deployment(tenant):
                    return Response({'code': 'publication_in_progress', 'detail': '已有發布工作進行中，請等待完成。'}, status=409)

                target, reason = publish.target_configuration()
                if target is None:
                    return Response({'detail': reason}, status=503)
                try:
                    validate_archive(upload, target.get('prefix', ''))
                except publish.PublishError as exc:
                    raise ValidationError({'detail': str(exc)}) from exc
                storage = release_storage()
                if storage is None:
                    return storage_unavailable()
                label = 'snowland-' + timezone.now().strftime('%Y%m%d-%H%M%S') + '.zip'
                release, created = publish.store_release(tenant, storage, upload, label, digest, upload.size)
                if created:
                    new_archive = release.archive_name
                job = publish.queue_publication(tenant, release, target, 'publish', cli_request_id=request_id)
            return job_response(job, status=202)
        except Exception as exc:
            if new_archive:
                try:
                    if not FrontendRelease.objects.filter(archive_name=new_archive).exists():
                        storage.delete(new_archive)
                except Exception:
                    logger.warning('Unused CLI frontend archive cleanup failed')
            if isinstance(exc, STORAGE_ERRORS):
                logger.warning('CLI frontend archive storage failed')
                return storage_unavailable()
            raise
