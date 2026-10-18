"""Editable content for the two existing photography layouts."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from urllib.parse import urlsplit

from .photography_gallery import validate_gallery


@lru_cache(maxsize=2)
def _schemas(_modified_at):
    path = Path(__file__).parent / 'fixtures' / 'photography_page_defaults.json'
    return {row['season']: row for row in json.loads(path.read_text(encoding='utf-8'))}


def photography_schema(season):
    # The editable-field catalog may change between deployments; do not keep
    # returning stale definitions after its fixture has been updated.
    path = Path(__file__).parent / 'fixtures' / 'photography_page_defaults.json'
    schemas = _schemas(path.stat().st_mtime_ns)
    if season not in schemas:
        raise ValueError('請選擇冬季或夏季攝影頁面')
    return deepcopy(schemas[season])


def photography_defaults(season):
    schema = photography_schema(season)
    return {'version': 1, 'season': season, 'values': {
        field['key']: field['value'] for section in schema['sections'] for field in section['fields']}}


def validate_photography_metadata(metadata, season, published):
    result = dict(metadata)
    content = result.get('photography')
    if content is None and not published:
        return result
    if not isinstance(content, dict) or type(content.get('version')) is not int or content.get('version') != 1 or content.get('season') != season:
        raise ValueError('請先載入此季攝影版型欄位，再儲存公開內容')
    values = content.get('values')
    if not isinstance(values, dict):
        raise ValueError('攝影頁面欄位必須是物件')
    fields = {field['key']: field for section in photography_schema(season)['sections'] for field in section['fields']}
    if set(values) - set(fields):
        raise ValueError('攝影欄位與版型不符，請重新載入後再試')
    for key, field in fields.items():
        if key not in values:
            if published:
                raise ValueError('攝影內容不完整，請先載入全部版型欄位')
            continue
        value = values[key]
        if not isinstance(value, str) or len(value) > (20000 if field['kind'] == 'text' else 500):
            raise ValueError(f"{field['label']}格式或長度不正確")
        if field['kind'] == 'image':
            validate_gallery({}, value, published)
        if field['kind'] == 'link':
            try:
                url = urlsplit(value)
                valid = url.scheme in ('http', 'https') and bool(url.netloc) and '\\' not in value and not any(ord(c) < 32 for c in value)
            except ValueError:
                valid = False
            if value and not valid:
                raise ValueError('外部連結請使用完整http/https網址')
            if not value and published:
                raise ValueError('公開前請填寫外部連結')
    return result
