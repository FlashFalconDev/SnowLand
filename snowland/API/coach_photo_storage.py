"""教練官網照片上傳到 S3（仿 FlashFalcon：後端代傳 boto3 upload_fileobj，不使用物件 ACL）。

FlashFalcon 的 External.apiAWS.BytesIO_upload_s3 由後端接收檔案、依副檔名設定 ContentType、
以 upload_fileobj 寫入 bucket，並回傳 https://{bucket}.s3.{region}.amazonaws.com/{key}。
公開讀取由 bucket policy 控制（BucketOwnerEnforced，不送 ACL）。此處沿用同一模式。
"""
import logging
import uuid

from django.conf import settings
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

ALLOWED_FORMATS = {
    'JPEG': ('.jpg', 'image/jpeg'),
    'PNG': ('.png', 'image/png'),
    'WEBP': ('.webp', 'image/webp'),
}


class CoachPhotoError(ValueError):
    """使用者可讀的驗證／設定錯誤。"""


class CoachPhotoStorageUnavailable(RuntimeError):
    """S3 未設定或寫入失敗。"""


def validate_coach_photo(upload):
    if not upload or not getattr(upload, 'size', 0):
        raise CoachPhotoError('請選擇要上傳的照片')
    limit = settings.COACH_PHOTO_MAX_BYTES
    if upload.size > limit:
        raise CoachPhotoError(f'照片不可超過 {limit // (1024 * 1024)} MB')
    try:
        image = Image.open(upload)
        extension = ALLOWED_FORMATS.get(image.format)
        if not extension:
            raise CoachPhotoError('照片僅支援 JPEG、PNG、WebP')
        image.verify()
    except CoachPhotoError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise CoachPhotoError('檔案不是有效的照片（僅支援 JPEG、PNG、WebP）')
    finally:
        upload.seek(0)
    return extension


def _s3_client():
    import boto3
    # 憑證沿用主機 IAM role／環境變數，與既有 static S3 設定一致。
    return boto3.client('s3', region_name=settings.COACH_PHOTO_REGION or None)


def public_url(key):
    base = settings.COACH_PHOTO_PUBLIC_BASE_URL
    if base:
        return f'{base.rstrip("/")}/{key}'
    bucket, region = settings.COACH_PHOTO_BUCKET, settings.COACH_PHOTO_REGION
    host = f'{bucket}.s3.{region}.amazonaws.com' if region else f'{bucket}.s3.amazonaws.com'
    return f'https://{host}/{key}'


def upload_coach_photo(upload, *, tenant_id, coach_id):
    """驗證後上傳，回傳公開 URL。key 由伺服器產生，不使用使用者檔名。"""
    if not settings.COACH_PHOTO_BUCKET:
        raise CoachPhotoStorageUnavailable('尚未設定照片儲存空間，請改貼上照片網址')
    extension, content_type = validate_coach_photo(upload)
    key = f'{settings.COACH_PHOTO_PREFIX.strip("/")}/{tenant_id}/{coach_id}/{uuid.uuid4().hex}{extension}'
    try:
        _s3_client().upload_fileobj(upload, settings.COACH_PHOTO_BUCKET, key,
                                    ExtraArgs={'ContentType': content_type, 'CacheControl': 'public, max-age=31536000'})
    except Exception:
        logger.exception('coach photo upload failed tenant=%s coach=%s', tenant_id, coach_id)
        raise CoachPhotoStorageUnavailable('照片上傳失敗，請稍後再試')
    return public_url(key)
