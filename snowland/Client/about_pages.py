"""Editable values for the existing school and recruitment layouts."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re

from .article_pages import safe_article_url


@lru_cache(maxsize=4)
def _schema(modified, page_key):
    filename = 'about_page_defaults.json' if page_key == 'about' else 'join_page_defaults.json'
    return json.loads((Path(__file__).parent / 'fixtures' / filename).read_text(encoding='utf-8'))


def about_schema(page_key='about'):
    if page_key not in ('about', 'join-us'):
        raise ValueError('原版型頁面不正確')
    path = Path(__file__).parent / 'fixtures' / ('about_page_defaults.json' if page_key == 'about' else 'join_page_defaults.json')
    return deepcopy(_schema(path.stat().st_mtime_ns, page_key))


def about_defaults(metadata=None, page_key='about'):
    metadata = metadata if isinstance(metadata, dict) else {}
    page = metadata.get('page') if isinstance(metadata.get('page'), dict) else {}
    blocks = metadata.get('blocks', page.get('blocks'))
    values = {}
    for section in about_schema(page_key)['sections']:
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
                if field.get('source_contains'):
                    paragraphs = [text for text in paragraphs if field['source_contains'] in text]
                if field.get('source_first'):
                    paragraphs = paragraphs[:1]
                value = '\n'.join(paragraphs)
            values[field['key']] = value
    return {'version': 1, 'page_key': page_key, 'values': values}


def validate_about_metadata(metadata, published, page_key='about'):
    result = dict(metadata)
    layout = result.get('layout')
    if layout is None and not published:
        return result
    name = '學校介紹' if page_key == 'about' else '教練招募'
    if not isinstance(layout, dict) or type(layout.get('version')) is not int or layout.get('version') != 1 or layout.get('page_key') != page_key or not isinstance(layout.get('values'), dict):
        raise ValueError(f'請先載入{name}的原版型欄位，再儲存公開內容')
    fields = {f['key']: f for section in about_schema(page_key)['sections'] for f in section['fields']}
    values = layout['values']
    if set(values) - set(fields):
        raise ValueError(f'{name}欄位與版型不符，請重新載入後再試')
    for key, field in fields.items():
        if key not in values:
            if published:
                raise ValueError(f'{name}內容不完整，請先載入全部原版型欄位')
            continue
        value = values[key]
        if not isinstance(value, str) or len(value) > (20000 if field['kind'] == 'text' else 2000):
            raise ValueError(f"{field['label']}格式或長度不正確")
        if field['kind'] == 'image' and (not safe_article_url(value) or published and not value):
            raise ValueError('圖片請填完整http/https網址或站內路徑，公開圖片不可空白')
        if field['kind'] == 'link' and (not safe_article_url(value) or published and not value):
            raise ValueError('申請連結請填完整http/https網址或站內路徑，公開連結不可空白')
    return result
