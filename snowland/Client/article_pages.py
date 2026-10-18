"""Validate editable imported articles without rewriting their original HTML."""
from html.parser import HTMLParser
from datetime import datetime
import re
from urllib.parse import urlsplit


def safe_article_url(value, *, link=False):
    if not isinstance(value, str) or len(value) > 2000 or '\\' in value or any(ord(c) < 32 for c in value):
        return False
    if not value:
        return True
    if value.startswith('/'):
        return not value.startswith('//')
    if link and value.startswith('#'):
        return True
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in ('http', 'https') and bool(parsed.netloc)) or (link and parsed.scheme == 'mailto' and '@' in parsed.path)
    except ValueError:
        return False


class ArticleHTMLValidator(HTMLParser):
    tags = {'p','div','span','h1','h2','h3','h4','h5','h6','ul','ol','li','strong','em','b','i','u','s','a','img','figure','figcaption','br','hr','table','thead','tbody','tfoot','tr','td','th','caption','blockquote'}
    attributes = {'id','class','style','href','src','alt','title','width','height','loading','decoding','aria-describedby','srcset','sizes','target','rel','colspan','rowspan','scope'}

    def __init__(self, published=False):
        super().__init__(convert_charrefs=True)
        self.published = published

    def handle_starttag(self, tag, attrs):
        if tag not in self.tags:
            raise ValueError('文章含不支援的內容，請只使用一般段落、圖片、連結與表格')
        if tag == 'img' and self.published and not (dict(attrs).get('src') or '').strip():
            raise ValueError('公開前請填寫每張圖片的網址')
        for name, value in attrs:
            if name not in self.attributes:
                raise ValueError('文章含不安全的屬性，請重新檢查內容')
            value = value or ''
            if name in ('src', 'href') and not safe_article_url(value, link=name == 'href'):
                raise ValueError('圖片及連結請使用完整http/https網址或站內路徑')
            if name == 'srcset' and any(not safe_article_url(part.strip().split(' ')[0]) for part in value.split(',') if part.strip()):
                raise ValueError('圖片候選網址格式不正確')
            if name == 'style' and re.search(r'expression|url\s*\(|@import|javascript|[\\]', value, re.I):
                raise ValueError('文章樣式含不安全內容')

    def handle_endtag(self, tag):
        if tag not in self.tags:
            raise ValueError('文章含不支援的內容')


def validate_article_metadata(metadata, published):
    if not isinstance(metadata, dict) or not isinstance(metadata.get('article'), dict):
        raise ValueError('請先填寫原文章內容')
    article = metadata['article']
    limits = {'title':500,'date':100,'heroImage':2000,'lead':20000,'html':200000}
    for key, limit in limits.items():
        if not isinstance(article.get(key, ''), str) or len(article.get(key, '')) > limit:
            raise ValueError('文章欄位格式或長度不正確')
    if published and (not article.get('title','').strip() or not article.get('heroImage','').strip() or not article.get('html','').strip()):
        raise ValueError('公開前請填寫文章標題、首圖與內文')
    if not safe_article_url(article.get('heroImage', '')):
        raise ValueError('首圖請使用完整http/https網址或站內圖片路徑')
    parser = ArticleHTMLValidator(published=published)
    parser.feed(article.get('html', '')); parser.close()
    links = article.get('relatedLinks', [])
    if not isinstance(links, list) or len(links) > 100:
        raise ValueError('延伸閱讀連結格式不正確')
    for link in links:
        if not isinstance(link, dict) or not isinstance(link.get('title',''), str) or not safe_article_url(link.get('url',''), link=True):
            raise ValueError('延伸閱讀請填寫有效的名稱與網址')
    return metadata


def validate_guide_article(data, instance=None):
    """One CMS record owns a new article's card, category and complete body."""
    value = lambda key, default='': data.get(key, getattr(instance, key, default))
    metadata = dict(value('metadata', {}))
    category = metadata.get('category', (value('tags', []) or [''])[0])
    if not isinstance(category, str) or len(category) > 60 or category.strip() == 'All':
        raise ValueError('文章分類請填寫60字內的名稱')
    metadata['category'] = category.strip()
    date = metadata.get('date', '')
    if not isinstance(date, str):
        raise ValueError('文章日期格式不正確')
    if date:
        try:
            datetime.strptime(date.replace('.', '-'), '%Y-%m-%d')
        except ValueError:
            raise ValueError('文章日期請填寫有效的年月日')
    mode = metadata.get('article_mode') or ('external' if value('link_url') and not value('body') else 'internal')
    if mode not in ('internal', 'external'):
        raise ValueError('請選擇本站文章或連結既有文章')
    metadata['article_mode'] = mode
    has_text = bool(value('body').strip())
    if 'blocks' in metadata:
        blocks = metadata['blocks']
        if not isinstance(blocks, list) or len(blocks) > 500:
            raise ValueError('文章正文區塊格式不正確')
        has_text = False
        for block in blocks:
            if not isinstance(block, dict) or block.get('type') not in ('heading','paragraph','image','list'):
                raise ValueError('請使用標題、文字、圖片或條列區塊')
            if block['type'] in ('heading','paragraph'):
                if not isinstance(block.get('text',''),str):
                    raise ValueError('正文必須是文字')
                has_text = has_text or bool(block.get('text','').strip())
            elif block['type'] == 'list':
                items = block.get('items', [])
                if not isinstance(items,list) or not all(isinstance(item,str) for item in items):
                    raise ValueError('條列清單格式不正確')
                has_text = has_text or any(item.strip() for item in items)
            else:
                if not isinstance(block.get('alt',''),str):
                    raise ValueError('圖片說明必須是文字')
                if not safe_article_url(block.get('src','')):
                    raise ValueError('文章圖片請使用完整http/https網址或站內路徑')
    if not safe_article_url(value('image_url')) or not safe_article_url(value('link_url')):
        raise ValueError('封面與文章連結請使用完整http/https網址或站內路徑')
    if value('status', 'draft') == 'active':
        if not value('title').strip() or not metadata['category']:
            raise ValueError('公開前請填寫文章標題並選擇分類')
        if mode == 'internal' and not has_text:
            raise ValueError('公開前請至少填寫一段文章內文')
        if mode == 'external' and not value('link_url').strip():
            raise ValueError('請填寫既有文章的連結網址')
        if mode == 'internal' and any(block.get('type') == 'image' and not block.get('src','').strip() for block in metadata.get('blocks', [])):
            raise ValueError('公開前請填寫每張圖片的網址，或移除空白圖片')
    return metadata
