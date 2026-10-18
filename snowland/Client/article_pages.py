"""Validate editable imported articles without rewriting their original HTML."""
from html.parser import HTMLParser
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
