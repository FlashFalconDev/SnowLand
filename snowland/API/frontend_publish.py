"""Website-file publication behind the existing platform release permission gate."""
import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path
from tempfile import SpooledTemporaryFile
from urllib.parse import urlparse
from zipfile import ZipFile, ZIP_DEFLATED

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.files import File
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from Client.models import Client, FrontendDeployment, FrontendRelease

logger = logging.getLogger(__name__)
MAX_FILES = 3000
MAX_BYTES = 1024 * 1024 * 1024
MAX_FILE_BYTES = 100 * 1024 * 1024
PROTECTED = ('static/', 'media/', 'private_course_media/', 'private_frontend_releases/', 'admin/', 'api/', 'booking/', 'control/')


class PublishError(Exception):
    pass


def valid_path(path, prefix=''):
    if not isinstance(path, str) or not path or len(path) > 500 or path != path.strip():
        return False
    if any(c in path for c in '\\:\x00<>|?*') or any(ord(c) < 32 for c in path):
        return False
    static_prefix = urlparse(getattr(settings, 'STATIC_URL', '/static/')).path.strip('/')
    full_path = '/'.join(part for part in (prefix.strip('/'), path) if part).lower()
    overlaps_static = bool(static_prefix) and (full_path == static_prefix.lower() or full_path.startswith(static_prefix.lower() + '/'))
    return all(part and not part.startswith('.') and part == part.rstrip(' .') for part in path.split('/')) and not path.lower().startswith(PROTECTED) and not overlaps_static


class BuildIdentity(HTMLParser):
    name = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == 'meta' and attrs.get('name', '').lower() == 'application-name':
            self.name = attrs.get('content', '')


def validate_build(archive, require_identity=True, prefix=''):
    entries = [entry for entry in archive.infolist() if not entry.is_dir()]
    names = [entry.filename for entry in entries]
    if not names or len(names) > MAX_FILES or sum(e.file_size for e in entries) > MAX_BYTES:
        raise PublishError('建置檔案數或總大小超過限制。')
    if len(set(name.casefold() for name in names)) != len(names) or any(not valid_path(name, prefix) for name in names):
        raise PublishError('建置包含非法、受保護或重複的路徑。')
    if 'index.html' not in names or any(e.flag_bits & 1 or e.file_size > MAX_FILE_BYTES for e in entries):
        raise PublishError('請選擇含根目錄 index.html 的完整建置資料夾。')
    if archive.getinfo('index.html').file_size > 4 * 1024 * 1024 or archive.testzip() is not None:
        raise PublishError('建置檔案無法完整讀取。')
    if not require_identity:
        return set(names)  # A server-generated backup may predate UTF-8/build identity markers.
    identity = BuildIdentity()
    try:
        identity.feed(archive.read('index.html').decode('utf-8-sig'))
    except UnicodeError as exc:
        raise PublishError('index.html 不是可讀取的 UTF-8 網頁。') from exc
    if require_identity and (identity.name or '').lower() != 'snowland':
        raise PublishError('這不是 SnowLand 的建置檔，請重新建置 SnowLand 前端後選擇 dist。')
    return set(names)


def target_configuration():
    database = connection.settings_dict
    local_database = (
        database.get('HOST') in ('127.0.0.1', 'localhost')
        and database.get('NAME') == 'test_snowland' and str(database.get('PORT')) == '3308'
    ) or (database.get('ENGINE', '').endswith('sqlite3') and (str(database.get('NAME')).startswith('file:memorydb_') or database.get('NAME') == ':memory:'))
    if settings.DEBUG and local_database:
        root = getattr(settings, 'SNOWLAND_FRONTEND_LOCAL_ROOT', '')
        config_file = settings.BASE_DIR / 'tmp' / 'frontend-publish-target.json'
        if not root and config_file.exists():
            try:
                root = json.loads(config_file.read_text(encoding='utf-8'))['root']
            except (OSError, ValueError, KeyError, TypeError):
                return None, '本機驗收目標設定不正確。'
            if not Path(root).resolve().is_relative_to((settings.BASE_DIR / 'tmp').resolve()):
                return None, '本機驗收目標不在允許的暫存目錄。'
        if root:
            return {'mode': 'local', 'root': str(Path(root).resolve()), 'label': '本機驗收目標（不影響正式站）'}, ''
    bucket = os.getenv('SNOWLAND_FRONTEND_BUCKET', '').strip()
    owner = os.getenv('SNOWLAND_FRONTEND_BUCKET_OWNER', '').strip()
    distribution = os.getenv('SNOWLAND_FRONTEND_DISTRIBUTION_ID', '').strip()
    prefix = os.getenv('SNOWLAND_FRONTEND_PREFIX', '').strip().strip('/')
    origin = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
    if not bucket or not re.fullmatch(r'\d{12}', owner) or not re.fullmatch(r'E[A-Z0-9]{8,31}', distribution):
        return None, '網站發布位置與快取清除設定尚未完成，暫時無法發布或還原。'
    if bucket == settings.SNOWLAND_PRIVATE_MEDIA_BUCKET or (prefix and not valid_path(prefix + '/index.html')):
        return None, '網站發布位置與私有檔案重疊或路徑不正確，已停止發布。'
    parsed = urlparse(origin)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        return None, '網站網址設定不正確，暫時無法發布。'
    return dict(mode='s3', bucket=bucket, owner=owner, distribution=distribution, prefix=prefix, origin=origin,
                region=os.getenv('AWS_REGION', 'ap-northeast-1'), label=origin), ''


def object_headers(name):
    return {'ContentType': mimetypes.guess_type(name)[0] or 'application/octet-stream',
            'CacheControl': 'no-cache, no-store, must-revalidate' if name.endswith('.html') else
            ('public, max-age=31536000, immutable' if name.startswith('assets/') else 'public, max-age=3600')}


class LocalPublisher:
    def __init__(self, target):
        self.root = Path(target['root'])

    def preflight(self):
        self.root.mkdir(parents=True, exist_ok=True)

    def allowed(self, name):
        return valid_path(name)

    def names(self):
        return {p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_file() and not p.is_symlink() and valid_path(p.relative_to(self.root).as_posix())}

    @contextmanager
    def read(self, name):
        path = self.root / name
        if not path.resolve().is_relative_to(self.root.resolve()) or path.is_symlink():
            raise PublishError('本機驗收檔案路徑不正確。')
        with path.open('rb') as body:
            yield body, object_headers(name)

    def write(self, name, body, headers):
        path = self.root / name
        if not valid_path(name) or not path.resolve().is_relative_to(self.root.resolve()):
            raise PublishError('本機驗收檔案路徑不正確。')
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('wb') as output:
                shutil.copyfileobj(body, output, 1024 * 1024)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def delete(self, name):
        path = self.root / name
        if not valid_path(name) or not path.resolve().is_relative_to(self.root.resolve()):
            raise PublishError('本機驗收檔案路徑不正確。')
        path.unlink(missing_ok=True)

    def invalidate(self):
        pass  # No CDN exists for this explicitly isolated local acceptance target.


class S3Publisher:
    def __init__(self, target):
        self.target = target
        config = Config(connect_timeout=10, read_timeout=60, retries={'max_attempts': 2})
        self.s3 = boto3.client('s3', region_name=target['region'], config=config)
        self.cdn = boto3.client('cloudfront', config=config)
        self.prefix = target['prefix'] + '/' if target['prefix'] else ''

    def options(self):
        return {'Bucket': self.target['bucket'], 'ExpectedBucketOwner': self.target['owner']}

    def allowed(self, name):
        return valid_path(name, self.target['prefix'])

    def preflight(self):
        self.s3.head_bucket(**self.options())
        distribution = self.cdn.get_distribution(Id=self.target['distribution'])['Distribution']
        config = distribution['DistributionConfig']
        default = config['DefaultCacheBehavior']['TargetOriginId']
        origin = next((item for item in config['Origins']['Items'] if item['Id'] == default), {})
        if (not config.get('Enabled') or distribution['ARN'].split(':')[4] != self.target['owner']
                or urlparse(self.target['origin']).hostname not in config.get('Aliases', {}).get('Items', [])
                or not origin.get('DomainName', '').startswith(self.target['bucket'] + '.s3')
                or not origin.get('DomainName', '').endswith('.amazonaws.com')
                or origin.get('OriginPath', '').strip('/') != self.target['prefix']):
            raise PublishError('CloudFront 與網站發布位置不一致，網站檔案未變更。')

    def names(self):
        names = set()
        for page in self.s3.get_paginator('list_objects_v2').paginate(Prefix=self.prefix, **self.options()):
            for item in page.get('Contents', []):
                name = item['Key'][len(self.prefix):]
                if self.allowed(name):
                    names.add(name)
                # During replacement both the old and new valid builds coexist.
                if len(names) > MAX_FILES * 2:
                    raise PublishError('網站檔案數超過發布整理上限，請管理員確認目標。')
        return names

    @contextmanager
    def read(self, name):
        item = self.s3.get_object(Key=self.prefix + name, **self.options())
        try:
            yield item['Body'], {key: item[key] for key in ('ContentType', 'CacheControl', 'ContentEncoding') if key in item}
        finally:
            item['Body'].close()

    def write(self, name, body, headers):
        if not self.allowed(name):
            raise PublishError('網站檔案與受保護路徑重疊。')
        self.s3.upload_fileobj(body, self.target['bucket'], self.prefix + name,
                               ExtraArgs={'ExpectedBucketOwner': self.target['owner'], **headers})

    def delete(self, name):
        if not self.allowed(name):
            raise PublishError('網站檔案與受保護路徑重疊。')
        self.s3.delete_object(Key=self.prefix + name, **self.options())

    def invalidate(self):
        item = self.cdn.create_invalidation(DistributionId=self.target['distribution'], InvalidationBatch={
            'Paths': {'Quantity': 1, 'Items': ['/*']}, 'CallerReference': uuid.uuid4().hex,
        })['Invalidation']
        deadline = time.monotonic() + 600
        while item['Status'] != 'Completed':
            if time.monotonic() >= deadline:
                raise PublishError('網站檔案已送出，但快取清除逾時。')
            time.sleep(3)
            item = self.cdn.get_invalidation(DistributionId=self.target['distribution'], Id=item['Id'])['Invalidation']


def publisher(target):
    return LocalPublisher(target) if target['mode'] == 'local' else S3Publisher(target)


def save_release(client, storage, buffer, label):
    buffer.seek(0, os.SEEK_END)
    size = buffer.tell()
    buffer.seek(0)
    digest = hashlib.file_digest(buffer, 'sha256').hexdigest()
    buffer.seek(0)
    existing = FrontendRelease.objects.filter(client=client, sha256=digest).first()
    if existing:
        return existing
    name = storage.save(f'{client.pk}/{uuid.uuid4().hex}.zip', File(buffer, name=label))
    try:
        release, created = FrontendRelease.objects.get_or_create(
            client=client, sha256=digest, defaults={'filename': label, 'archive_name': name, 'size': size})
    except Exception:
        storage.delete(name)
        raise
    if not created:
        storage.delete(name)
    return release


def folder_archive(files, paths, prefix=''):
    if not files or len(files) != len(paths) or len(files) > MAX_FILES:
        raise PublishError('檔案與路徑數量不正確，或超過 3,000 個檔案。')
    if sum(f.size for f in files) > MAX_BYTES or any(f.size > MAX_FILE_BYTES for f in files):
        raise PublishError('建置總大小超過 1 GB 或單檔超過 100 MB。')
    if any(not valid_path(p, prefix) for p in paths) or len({p.casefold() for p in paths}) != len(paths):
        raise PublishError('建置包含非法、受保護或重複的路徑。')
    buffer = SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    try:
        with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
            for upload, name in zip(files, paths):
                with archive.open(name, 'w') as output:
                    for chunk in upload.chunks():
                        output.write(chunk)
        buffer.seek(0)
        with ZipFile(buffer) as archive:
            validate_build(archive, prefix=prefix)
        buffer.seek(0)
        return buffer
    except Exception:
        buffer.close()
        raise


def snapshot(provider, storage, client):
    names = provider.names()
    if not names:
        return None, {}
    if len(names) > MAX_FILES:
        raise PublishError('現有網站超過備份檔數上限，網站檔案未變更。')
    if 'index.html' not in names:
        raise PublishError('現有發布位置沒有 index.html，請先確認網站目標。')
    headers, total = {}, 0
    with SpooledTemporaryFile(max_size=8 * 1024 * 1024) as buffer:
        with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
            for name in sorted(names):
                with provider.read(name) as (body, metadata), archive.open(name, 'w') as output:
                    headers[name] = metadata
                    file_bytes = 0
                    while chunk := body.read(1024 * 1024):
                        total += len(chunk)
                        file_bytes += len(chunk)
                        if total > MAX_BYTES or file_bytes > MAX_FILE_BYTES:
                            raise PublishError('現有網站超過備份大小上限，網站檔案未變更。')
                        output.write(chunk)
        release = save_release(client, storage, buffer, 'backup-' + timezone.now().strftime('%Y%m%d-%H%M%S') + '.zip')
    return release, headers


def apply_archive(provider, archive, metadata=None, progress=None):
    names = {e.filename for e in archive.infolist() if not e.is_dir()}
    if any(not provider.allowed(name) for name in names) or 'index.html' not in names:
        raise PublishError('版本檔案路徑不正確。')
    for index, name in enumerate(sorted(names - {'index.html'}) + ['index.html']):
        with archive.open(name) as body:
            provider.write(name, body, (metadata or {}).get(name) or object_headers(name))
        if progress and index % 10 == 0:
            progress(f'已更新 {index + 1} / {len(names)} 個檔案')
    return names


def cleanup(provider, names):
    for name in provider.names() - names:
        provider.delete(name)


def job_data(job):
    if not job:
        return None
    return dict(id=job.pk, status=job.status, operation=job.operation, message=job.message,
                release_id=job.release_id, backup_id=job.backup_id, updated_at=job.updated_at.isoformat())


def touch(job, status, message):
    job.status, job.message, job.updated_at = status, message, timezone.now()
    job.save(update_fields=['status', 'message', 'updated_at'])


def run_deployment(job_id):
    from API.frontend_releases import release_storage
    storage, provider, backup, headers, changed = None, None, None, {}, False
    close_old_connections()
    try:
        with transaction.atomic():
            job = FrontendDeployment.objects.select_for_update().select_related('client', 'release').get(pk=job_id)
            if job.status != 'queued':
                return
            touch(job, 'backing_up', '確認網站目標並備份現有網站')
        if not job.client.is_active or job.client.internal_code != 'flashfalcon':
            raise PublishError('平台入口已停用，網站檔案未變更。')
        storage = release_storage()
        if storage is None:
            raise PublishError('版本備份儲存暫時無法使用。')
        with storage.open(job.release.archive_name, 'rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != job.release.sha256:
                raise PublishError('版本檔案校驗失敗，網站檔案未變更。')
            source.seek(0)
            with ZipFile(source) as archive:
                original_backup = FrontendDeployment.objects.filter(backup=job.release).order_by('-id').first()
                validate_build(archive, require_identity=original_backup is None, prefix=job.target.get('prefix', ''))
                provider = publisher(job.target)
                provider.preflight()
                backup, headers = snapshot(provider, storage, job.client)
                job.backup, job.backup_headers = backup, headers
                job.save(update_fields=['backup', 'backup_headers'])
                restore_headers = original_backup.backup_headers if original_backup else {}
                touch(job, 'publishing', '已備份原網站，正在更新網站檔案')
                changed = True
                names = apply_archive(provider, archive, restore_headers,
                                      lambda message: touch(job, 'publishing', message))
        touch(job, 'invalidating', '網站檔案已更新，正在等待快取清除完成')
        provider.invalidate()
        touch(job, 'cleaning', '快取已清除，正在整理舊檔案')
        cleanup(provider, names)
        with transaction.atomic():
            Client.objects.select_for_update().get(pk=job.client_id)
            FrontendRelease.objects.filter(client=job.client, is_current=True).update(is_current=False)
            FrontendRelease.objects.filter(pk=job.release_id).update(is_current=True)
            job.finished_at = timezone.now()
            job.save(update_fields=['finished_at'])
            touch(job, 'succeeded', '網站已發布完成' if job.operation == 'publish' else '網站已還原完成')
    except Exception as exc:
        logger.exception('Frontend website publication failed (job %s)', job_id)
        message = str(exc) if isinstance(exc, PublishError) else '發布未完成，請檢查網站儲存及快取權限。'
        if changed and provider:
            try:
                if backup:
                    with storage.open(backup.archive_name, 'rb') as source, ZipFile(source) as archive:
                        old_names = apply_archive(provider, archive, headers)
                    cleanup(provider, old_names)
                else:
                    for name in provider.names():
                        provider.delete(name)
                message += ' 原網站檔案已回復。'
                provider.invalidate()
            except Exception:
                logger.exception('Frontend rollback or cache confirmation failed (job %s)', job_id)
                message += ' 回復或快取確認未完成，請管理員檢查；不要連續重送。'
        FrontendDeployment.objects.filter(pk=job_id).update(status='failed', message=message[:500],
                                                            updated_at=timezone.now(), finished_at=timezone.now())
    finally:
        close_old_connections()


def start_deployment(job_id):
    try:
        threading.Thread(target=run_deployment, args=(job_id,), name=f'frontend-publish-{job_id}', daemon=True).start()
    except Exception:
        logger.exception('Unable to start frontend publication worker (job %s)', job_id)
        FrontendDeployment.objects.filter(pk=job_id).update(status='failed', message='發布工作無法啟動，網站檔案未變更。',
                                                            updated_at=timezone.now(), finished_at=timezone.now())
