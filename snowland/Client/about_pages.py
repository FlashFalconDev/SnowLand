"""Editable values for the existing school introduction, not a new layout."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re

from .article_pages import safe_article_url


@lru_cache(maxsize=2)
def _schema(modified):
    return json.loads((Path(__file__).parent / 'fixtures' / 'about_page_defaults.json').read_text(encoding='utf-8'))


def about_schema():
    path = Path(__file__).parent / 'fixtures' / 'about_page_defaults.json'
    return deepcopy(_schema(path.stat().st_mtime_ns))


def about_defaults(metadata=None):
    metadata = metadata if isinstance(metadata, dict) else {}
    page = metadata.get('page') if isinstance(metadata.get('page'), dict) else {}
    blocks = metadata.get('blocks', page.get('blocks'))
    values = {}
    for section in about_schema()['sections']:
        for field in section['fields']:
            value = field['value']
            if field.get('source_heading') and isinstance(blocks, list):
                heading = field['source_heading']
                start = next((i for i, b in enumerate(blocks) if isinstance(b, dict) and b.get('type') == 'heading' and b.get('text') == heading), None)
                paragraphs = []
                if start is not None:
                    for block in blocks[start + 1:]:
                        if not isinstance(block, dict):
                            continue
                        if block.get('type') == 'heading':
                            break
                        if block.get('type') == 'paragraph' and isinstance(block.get('text'), str):
                            paragraphs.extend(filter(None, re.split(r'(?<=[。！？])\s*', re.sub(r'\s+', ' ', block['text']).strip())))
                value = '\n'.join(paragraphs)
            values[field['key']] = value
    return {'version': 1, 'page_key': 'about', 'values': values}


def validate_about_metadata(metadata, published):
    result = dict(metadata)
    layout = result.get('layout')
    if layout is None and not published:
        return result
    if not isinstance(layout, dict) or type(layout.get('version')) is not int or layout.get('version') != 1 or layout.get('page_key') != 'about' or not isinstance(layout.get('values'), dict):
        raise ValueError('請先載入學校介紹的原版型欄位，再儲存公開內容')
    fields = {f['key']: f for section in about_schema()['sections'] for f in section['fields']}
    values = layout['values']
    if set(values) - set(fields):
        raise ValueError('學校介紹欄位與版型不符，請重新載入後再試')
    for key, field in fields.items():
        if key not in values:
            if published:
                raise ValueError('學校介紹內容不完整，請先載入全部原版型欄位')
            continue
        value = values[key]
        if not isinstance(value, str) or len(value) > (20000 if field['kind'] == 'text' else 2000):
            raise ValueError(f"{field['label']}格式或長度不正確")
        if field['kind'] == 'image' and (not safe_article_url(value) or published and not value):
            raise ValueError('圖片請填完整http/https網址或站內路徑，公開圖片不可空白')
    return result
