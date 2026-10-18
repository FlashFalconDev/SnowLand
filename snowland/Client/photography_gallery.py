"""Validation for public gallery metadata; never changes private course media."""
import re
from urllib.parse import urlsplit


def validate_gallery(metadata, image_url, published):
    result = dict(metadata)
    kind = result.get('media_type', 'photo')
    if kind not in ('photo', 'video'):
        raise ValueError('作品類型只能選照片或影片')
    result['media_type'] = kind
    for key in ('location', 'section'):
        value = result.get(key, '')
        if not isinstance(value, str) or len(value) > 80:
            raise ValueError('拍攝地點與景點名稱請填寫80字以內的文字')
        if key in result:
            result[key] = value.strip()
    types = result.get('shoot_types', [])
    if not isinstance(types, list) or len(types) > 20 or any(
        not isinstance(value, str) or not value.strip() or len(value) > 50 for value in types
    ):
        raise ValueError('拍攝分類最多20項，每項請填寫1至50字')
    result['shoot_types'] = list(dict.fromkeys(value.strip() for value in types))
    if kind == 'photo':
        image = image_url or ''
        if not image and published:
            raise ValueError('公開照片前請填寫作品照片網址')
        if image:
            if '\\' in image or any(ord(char) < 32 for char in image):
                raise ValueError('照片網址格式不正確')
            try:
                url = urlsplit(image)
                valid = (image.startswith('/') and not image.startswith('//')) or (
                    url.scheme in ('http', 'https') and bool(url.netloc))
            except ValueError:
                valid = False
            if not valid:
                raise ValueError('照片請使用完整http/https網址或以/開頭的站內圖片路徑')
    else:
        video = result.get('video_id', '')
        if not isinstance(video, str) or (video and not re.fullmatch(r'[A-Za-z0-9_-]{11}', video)):
            raise ValueError('請填寫正確的YouTube影片網址或11碼影片代號')
        if not video and published:
            raise ValueError('公開影片前請填寫YouTube影片')
    return result
