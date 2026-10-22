import os
import re
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.urls import reverse
from PIL import Image, UnidentifiedImageError
from storages.backends.s3 import S3Storage


class _LocalPrivateCourseMediaStorage(FileSystemStorage):
    @property
    def base_location(self):
        return getattr(settings, 'PRIVATE_COURSE_MEDIA_ROOT', settings.BASE_DIR / 'private_course_media')

    @property
    def location(self):
        return os.path.abspath(self.base_location)


_PrivateCourseMediaBackend = (
    S3Storage if settings.SNOWLAND_PRIVATE_MEDIA_BUCKET else _LocalPrivateCourseMediaStorage
)


class PrivateCourseMediaStorage(_PrivateCourseMediaBackend):
    if settings.SNOWLAND_PRIVATE_MEDIA_BUCKET:
        bucket_name = settings.SNOWLAND_PRIVATE_MEDIA_BUCKET
        location = 'private_course_media'
        default_acl = None
        querystring_auth = True
        # Do not inherit public static-file URLs or upload ACLs.
        custom_domain = None
        object_parameters = {}
        file_overwrite = False
        region_name = os.getenv('AWS_REGION')

    def url(self, name):
        raise ValueError('課程附件必須經登入權限檢查後讀取')


def course_media_url(media):
    if not media.file:
        return media.url
    return reverse('booking:api_course_media_file_client', kwargs={
        'client_code': media.evaluation.booking.reservation.group.client.internal_code,
        'media_id': media.pk,
    })


def validate_course_upload(upload):
    if not upload or not upload.size:
        raise ValueError('請選擇要上傳的照片或影片')
    header = upload.read(32)
    upload.seek(0)
    video_ext = '.mp4' if len(header) >= 12 and header[4:8] == b'ftyp' else '.webm' if header.startswith(b'\x1aE\xdf\xa3') else None
    if video_ext:
        limit = getattr(settings, 'COURSE_MEDIA_MAX_VIDEO_BYTES', 100 * 1024 * 1024)
        if upload.size > limit:
            raise ValueError(f'影片不可超過 {limit // (1024 * 1024)} MB')
        return 'video', video_ext
    limit = getattr(settings, 'COURSE_MEDIA_MAX_PHOTO_BYTES', 20 * 1024 * 1024)
    if upload.size > limit:
        raise ValueError(f'照片不可超過 {limit // (1024 * 1024)} MB')
    try:
        image = Image.open(upload)
        extension = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}.get(image.format)
        if not extension:
            raise ValueError('照片僅支援 JPEG、PNG、WebP；影片支援 MP4／MOV、WebM')
        image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise ValueError('檔案不是有效的照片或支援的影片格式')
    finally:
        upload.seek(0)
    return 'photo', extension


def save_course_upload(evaluation, user, upload):
    from .models import CourseMedia
    media_type, extension = validate_course_upload(upload)
    media = CourseMedia(evaluation=evaluation, uploaded_by=user, media_type=media_type, is_public=False)
    try:
        media.file.save(f'{evaluation.pk}/{uuid.uuid4().hex}{extension}', upload, save=False)
        media.save()
    except Exception:
        if media.file.name:
            media.file.storage.delete(media.file.name)
        raise
    return media


def private_file_response(media, range_header=None):
    content_types = {'.jpg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.mp4': 'video/mp4', '.webm': 'video/webm'}
    extension = os.path.splitext(media.file.name)[1].lower()
    content_type = content_types.get(extension, 'application/octet-stream')
    stream = media.file.open('rb')
    size = media.file.size
    if range_header:
        match = re.fullmatch(r'bytes=(\d{0,20})-(\d{0,20})', range_header)
        start, end = 0, size - 1
        if match and any(match.groups()):
            first, last = match.groups()
            if first:
                start, end = int(first), min(int(last), size - 1) if last else size - 1
            else:
                start = max(size - int(last), 0)
        else:
            start = size
        if start > end or start >= size:
            stream.close()
            response = HttpResponse(status=416)
            response['Content-Range'] = f'bytes */{size}'
        else:
            stream.seek(start)
            class RangeReader:
                remaining = end - start + 1

                def __iter__(self):
                    return self

                def __next__(self):
                    data = stream.read(min(64 * 1024, self.remaining)) if self.remaining else b''
                    if not data:
                        self.close()
                        raise StopIteration
                    self.remaining -= len(data)
                    return data

                def close(self):
                    stream.close()

            response = StreamingHttpResponse(RangeReader(), status=206, content_type=content_type)
            response['Content-Range'] = f'bytes {start}-{end}/{size}'
            response['Content-Length'] = str(end - start + 1)
    else:
        response = FileResponse(stream, content_type=content_type, filename=f'course-record{extension}')
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
