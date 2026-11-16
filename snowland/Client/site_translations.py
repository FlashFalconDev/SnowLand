from copy import deepcopy
from html import escape
from html.parser import HTMLParser
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from .recruitment_models import RecruitmentForm
from .translation_models import SiteTranslation


LANGUAGES = ('zh-Hant', 'en', 'ja')
INTERFACE_SCOPES = ('ui', 'navigation')
CONTENT_KINDS = ('article', 'page', 'faq')
COURSES = {
    'category': (CourseCategory, 'client'),
    'type': (CourseType, 'category__client'),
    'template': (CourseTemplate, 'course_type__category__client'),
}
CONTENT_FIELDS = {'title': '標題', 'subtitle': '副標題', 'summary': '摘要', 'body': '正文'}


def course_rows(client, kind):
    model, owner = COURSES[kind]
    return model.objects.filter(**{owner: client})


def editable_content(query):
    return query.filter(content_type__in=CONTENT_KINDS).exclude(
        location_key__in=('membership.waiver', 'membership.assessment-rubric'),
    ).exclude(location_key__startswith='policy.').exclude(location_key__startswith='internal.')


def entries_for(client, scope):
    return SiteTranslation.objects.filter(client=client, scope=scope).values_list('entries', flat=True).first() or {}


def translated(entries, key, source, locale):
    row = entries.get(key, {})
    return (row.get('values', {}).get(locale) or source) if row.get('source') == source else source


class ArticleText(HTMLParser):
    """Index visible text, then escape replacements before restoring the source markup."""

    def __init__(self, visit, prefix='article.html'):
        super().__init__(convert_charrefs=True)
        self.visit = visit
        self.parts = []
        self.index = 0
        self.prefix = prefix

    def handle_starttag(self, tag, attrs):
        self.parts.append(self.get_starttag_text())

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        self.parts.append(f'</{tag}>')

    def handle_data(self, text):
        source = text.strip()
        if source:
            self.index += 1
            key = f'{self.prefix}.{self.index}'
            edited = self.visit(key, f'原版文章文字 {self.index}', source)
            offset = len(text) - len(text.lstrip())
            text = text[:offset] + edited + text[offset + len(source):]
        self.parts.append(escape(text, quote=False))


def content_text(row, visit, *, include_body=True):
    """Walk the same fields for the Console and the public response."""
    def field(parent, name, path, label):
        value = parent.get(name)
        if isinstance(value, str) and value.strip():
            parent[name] = visit(path, label, value)

    def text_lines(parent, name, path, label):
        source = parent.get(name)
        if not isinstance(source, str):
            return
        parts = source.splitlines(keepends=True)
        for index, line in enumerate(parts, 1):
            text = line.rstrip('\r\n')
            if text.strip():
                parts[index - 1] = visit(f'{path}.{index}', f'{label} {index}', text) + line[len(text):]
        parent[name] = ''.join(parts)

    def blocks(values, prefix):
        if not isinstance(values, list):
            return
        for index, item in enumerate(values, 1):
            if not isinstance(item, dict):
                continue
            base = f'{prefix}.{index}'
            kind = {'heading': '標題', 'paragraph': '段落', 'image': '圖片說明', 'list': '清單'}.get(item.get('type'), '區塊')
            text_lines(item, 'text', base + '.text', f'{kind} {index}')
            field(item, 'alt', base + '.alt', f'圖片說明 {index}')
            items = item.get('items')
            if isinstance(items, list):
                for position, source in enumerate(items):
                    if isinstance(source, str) and source.strip():
                        items[position] = visit(f'{base}.items.{position}', f'清單 {index} · 項目 {position + 1}', source)

    result = deepcopy(row)
    for key, label in CONTENT_FIELDS.items():
        if key == 'body':
            if include_body:
                text_lines(result, key, key, label)
        else:
            field(result, key, key, label)
    metadata = result.get('metadata')
    if not isinstance(metadata, dict):
        return result

    if include_body:
        blocks(metadata.get('blocks'), 'blocks')
        if isinstance(metadata.get('answer_html'), str):
            parser = ArticleText(visit, 'faq.answer')
            parser.feed(metadata['answer_html'])
            parser.close()
            metadata['answer_html'] = ''.join(parser.parts)
    field(metadata, 'question', 'faq.question', '問題')
    page = metadata.get('page')
    if isinstance(page, dict):
        for key in ('title', 'subtitle', 'summary'):
            field(page, key, f'page.{key}', '頁面' + CONTENT_FIELDS[key])
        if include_body:
            blocks(page.get('blocks'), 'page.blocks')
    layout = metadata.get('layout')
    if isinstance(layout, dict) and layout.get('page_key') in ('about', 'join-us') and isinstance(layout.get('values'), dict):
        from .about_pages import about_schema
        for section in about_schema(layout['page_key'])['sections']:
            for entry in section['fields']:
                if entry['kind'] == 'text':
                    key = entry['key']
                    text_lines(layout['values'], key, f'layout.{key}', entry['label'])
    article = metadata.get('article')
    if isinstance(article, dict):
        for key, label in (('title', '原版標題'), ('excerpt', '原版摘要'), ('description', '原版說明')):
            field(article, key, f'article.{key}', label)
        if include_body and isinstance(article.get('html'), str):
            parser = ArticleText(visit)
            parser.feed(article['html'])
            parser.close()
            article['html'] = ''.join(parser.parts)
        links = article.get('relatedLinks')
        if include_body and isinstance(links, list):
            for index, link in enumerate(links, 1):
                if isinstance(link, dict):
                    field(link, 'title', f'article.link.{index}', f'相關連結 {index}')
    return result


def recruitment_text(fields):
    for question in fields:
        key = question['id']
        yield f'{key}.label', '題目', question['label']
        for index, value in enumerate(question.get('options', [])):
            yield f'{key}.option.{index}', f'{question["label"]} · 選項 {index + 1}', value


def localize_content_rows(rows, client, locale, *, include_body=True):
    if locale not in LANGUAGES or not rows:
        return rows
    scopes = [f'content:{row["id"]}' for row in rows if row['content_type'] in CONTENT_KINDS and
              not row['location_key'].startswith('policy.') and row['location_key'] != 'membership.waiver']
    configured = dict(SiteTranslation.objects.filter(client=client, scope__in=scopes).values_list('scope', 'entries'))
    return [
        content_text(row, lambda key, _label, source: translated(entries, key, source, locale), include_body=include_body)
        if (entries := configured.get(f'content:{row["id"]}')) else row
        for row in rows
    ]


def public_translation_scopes(client):
    saved = dict(SiteTranslation.objects.filter(client=client).exclude(scope__startswith='content:').values_list('scope', 'entries'))
    result = {scope: saved[scope] for scope in INTERFACE_SCOPES if scope in saved}
    if 'recruitment' in saved:
        fields = RecruitmentForm.objects.filter(client=client, enabled=True).values_list('fields', flat=True).first()
        if fields:
            entries = saved['recruitment']
            result['recruitment'] = {key: entries[key] for key, _, source in recruitment_text(fields)
                                     if key in entries and entries[key].get('source') == source}
    for kind in COURSES:
        prefix = kind + ':'
        ids = [int(key[len(prefix):]) for key in saved if key.startswith(prefix)]
        if not ids:
            continue
        rows = course_rows(client, kind).filter(pk__in=ids)
        if kind == 'template':
            rows = rows.filter(is_active=True)
        for row_id, name in rows.values_list('pk', 'name'):
            key = f'{prefix}{row_id}'
            entry = saved[key].get('name')
            if entry and entry.get('source') == name:
                result[key] = {'name': entry}
    return result
