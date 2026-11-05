import hashlib
import logging
import os
import stat
import uuid
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile
from zlib import error as ZipDataError

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from storages.backends.s3 import S3Storage

from Client.models import Client, FrontendRelease, FrontendDeployment
from . import frontend_publish


logger = logging.getLogger(__name__)
SUPPORT_CLIENT_CODE = 'flashfalcon'
MAX_ARCHIVE_MB = 768
MAX_EXPANDED_MB = 1024
MAX_ARCHIVE_BYTES = MAX_ARCHIVE_MB * 1024 * 1024
MAX_EXPANDED_BYTES = MAX_EXPANDED_MB * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 3000
STORAGE_ERRORS = (OSError, BotoCoreError, ClientError)


def release_storage():
    target, _ = frontend_publish.target_configuration()
    if target and target['mode'] == 'local':
        return FileSystemStorage(location=settings.BASE_DIR / 'tmp' / 'frontend-publish-private')
    if settings.SNOWLAND_PRIVATE_MEDIA_BUCKET:
        return S3Storage(
            bucket_name=settings.SNOWLAND_PRIVATE_MEDIA_BUCKET,
            location='private_frontend_releases',
            region_name=os.getenv('AWS_REGION'),
            default_acl=None,
            custom_domain=None,
            object_parameters={},
            file_overwrite=False,
            max_memory_size=8 * 1024 * 1024,
        )
    if settings.DEBUG:
        return FileSystemStorage(location=settings.BASE_DIR / 'tmp' / 'private_frontend_releases')
    return None


def archive_digest(upload):
    if not upload or not upload.name.lower().endswith('.zip'):
        raise ValidationError({'detail': '請選擇前端建置的 ZIP 檔案。'})
    if upload.size > MAX_ARCHIVE_BYTES:
        raise ValidationError({'detail': f'ZIP 檔案不得超過 {MAX_ARCHIVE_MB} MB。'})

    try:
        with ZipFile(upload) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES or sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES:
                raise ValidationError({'detail': f'ZIP 解壓後不得超過 {MAX_EXPANDED_MB} MB 或 {MAX_ARCHIVE_ENTRIES:,} 個項目。'})
            paths = set()
            has_entrypoint = False
            for entry in entries:
                path = entry.orig_filename.rstrip('/')
                if (
                    not path or '\\' in path or ':' in path or '\x00' in path
                    or any(part in ('', '.', '..') for part in path.split('/'))
                    or path.casefold() in paths or stat.S_ISLNK(entry.external_attr >> 16)
                    or entry.flag_bits & 1 or entry.compress_type not in (ZIP_STORED, ZIP_DEFLATED)
                ):
                    raise ValidationError({'detail': 'ZIP 含有不支援的路徑、重複項目、連結或加密檔案。'})
                paths.add(path.casefold())
                has_entrypoint |= entry.filename == 'index.html' and entry.file_size > 0
            if not has_entrypoint:
                raise ValidationError({'detail': '請壓縮建置資料夾內的檔案，讓 index.html 位於 ZIP 最上層。'})
            if archive.testzip() is not None:
                raise BadZipFile
    except (BadZipFile, EOFError, RuntimeError, OSError, ZipDataError) as exc:
        raise ValidationError({'detail': 'ZIP 檔案已損毀或格式不支援。'}) from exc

    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()


def release_data(release, published_id=None, backup_ids=()):
    return {
        'id': release.pk,
        'filename': release.filename,
        'size': release.size,
        'created_at': release.created_at.isoformat(),
        'is_current': release.pk == published_id,
        'is_backup': release.pk in backup_ids,
    }


def storage_unavailable():
    return Response({'detail': '版本儲存暫時無法使用，請稍後再試。'}, status=503)


@method_decorator([never_cache, ensure_csrf_cookie], name='dispatch')
class FrontendReleaseViewSet(ViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    lookup_value_regex = r'\d+'

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if kwargs.get('client_code') != SUPPORT_CLIENT_CODE:
            raise NotFound()
        if not request.user.is_superuser:
            raise PermissionDenied()
        self.tenant = get_object_or_404(Client, internal_code=SUPPORT_CLIENT_CODE, is_active=True)
        if self.tenant.internal_code != SUPPORT_CLIENT_CODE:
            raise NotFound()

    def releases(self):
        return FrontendRelease.objects.filter(client=self.tenant)

    def list(self, request, **kwargs):
        jobs = FrontendDeployment.objects.filter(client=self.tenant)
        published = jobs.filter(status='succeeded').first()
        target, reason = frontend_publish.target_configuration()
        latest = jobs.first()
        if published and (published.target != target or (latest and latest.status != 'succeeded')):
            published = None
        backups = set(jobs.exclude(backup=None).values_list('backup_id', flat=True))
        return Response({
            'versions': [release_data(release, published.release_id if published else None, backups) for release in self.releases()],
            'storage_ready': release_storage() is not None,
            'publish_ready': target is not None,
            'publish_reason': reason,
            'target_label': target['label'] if target else '',
            'deployment': frontend_publish.job_data(jobs.first()),
        })

    def queue_publication(self, request, release, target, operation):
        with transaction.atomic():
            get_object_or_404(Client.objects.select_for_update(), pk=self.tenant.pk, is_active=True)
            active = FrontendDeployment.objects.filter(client=self.tenant, status__in=FrontendDeployment.ACTIVE).first()
            if active:
                return Response({'detail': '已有發布工作進行中，請等待完成。',
                                 'deployment': frontend_publish.job_data(active)}, status=409)
            job = FrontendDeployment.objects.create(client=self.tenant, release=release, target=target,
                                                     requested_by=request.user, operation=operation)
            transaction.on_commit(lambda: frontend_publish.start_deployment(job.pk))
        return Response({'deployment': frontend_publish.job_data(job)}, status=202)

    def create(self, request, **kwargs):
        storage = release_storage()
        if storage is None:
            return storage_unavailable()
        if request.FILES.getlist('files'):
            target, reason = frontend_publish.target_configuration()
            if target is None:
                return Response({'detail': reason}, status=503)
            try:
                with frontend_publish.folder_archive(request.FILES.getlist('files'), request.data.getlist('paths'), target.get('prefix', '')) as buffer:
                    release = frontend_publish.save_release(self.tenant, storage, buffer, 'snowland-' + timezone.now().strftime('%Y%m%d-%H%M%S') + '.zip')
            except frontend_publish.PublishError as exc:
                raise ValidationError({'detail': str(exc)}) from exc
            return self.queue_publication(request, release, target, 'publish')
        upload = request.FILES.get('archive')
        digest = archive_digest(upload)
        existing = self.releases().filter(sha256=digest).first()
        if existing:
            return Response(release_data(existing))

        try:
            name = storage.save(f'{self.tenant.pk}/{uuid.uuid4().hex}.zip', upload)
        except STORAGE_ERRORS:
            logger.exception('Frontend release archive upload failed')
            return storage_unavailable()

        keep_archive = False
        try:
            version, keep_archive = self.releases().get_or_create(
                sha256=digest,
                defaults={
                    'client': self.tenant, 'filename': upload.name,
                    'archive_name': name, 'size': upload.size,
                },
            )
        finally:
            if not keep_archive:
                try:
                    storage.delete(name)
                except STORAGE_ERRORS:
                    logger.exception('Unused frontend release archive cleanup failed')
        return Response(release_data(version), status=201 if keep_archive else 200)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None, **kwargs):
        version = get_object_or_404(self.releases(), pk=pk)
        storage = release_storage()
        if storage is None:
            return storage_unavailable()
        try:
            if not storage.exists(version.archive_name):
                return Response({'detail': '這個版本的 ZIP 已遺失，無法回復。'}, status=409)
        except STORAGE_ERRORS:
            logger.exception('Frontend release archive check failed')
            return storage_unavailable()
        target, reason = frontend_publish.target_configuration()
        if target is None:
            return Response({'detail': reason}, status=503)
        return self.queue_publication(request, version, target, 'restore')

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None, **kwargs):
        version = get_object_or_404(self.releases(), pk=pk)
        storage = release_storage()
        if storage is None:
            return storage_unavailable()
        try:
            archive = storage.open(version.archive_name, 'rb')
        except FileNotFoundError as exc:
            raise NotFound('這個版本的 ZIP 已遺失。') from exc
        except STORAGE_ERRORS:
            logger.exception('Frontend release archive download failed')
            return storage_unavailable()
        response = FileResponse(archive, as_attachment=True, filename=version.filename, content_type='application/zip')
        response['X-Content-Type-Options'] = 'nosniff'
        return response
