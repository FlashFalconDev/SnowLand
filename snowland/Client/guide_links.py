"""Resolve known old-site links at read time without changing the editor's original HTML."""
from html import escape, unescape
from html.parser import HTMLParser
import re
from urllib.parse import quote, unquote, urlsplit

from Client.models import SiteContent


def source_path(url):
    try:
        parsed = urlsplit(unescape(url))
        if parsed.scheme in ('http','https') and parsed.netloc in ('land110602.com','www.land110602.com'):
            return unquote(parsed.path).rstrip('/').lower()
    except (TypeError, ValueError):
        pass
    return None


def guide_link_index(client):
    base = '/' + quote(client.internal_code, safe='')
    paths = {'': '/', '/contact':'/contact', '/coach':'/coach', '/brand-introduction':'/about',
             '/about/brand-introduction':'/about', '/off-piste_guide':'/course/off-piste-guide',
             '/reserve':'/booking', '/reservation_2526':'/booking'}
    for resort in ('tomamu','furano','rusutsu','kiroro','kamui','teine'):
        paths['/'+resort] = '/course/'+resort
        paths['/price_'+resort] = '/course/'+resort
        for season in ('2526','2627'):
            paths['/price_'+resort+season] = '/course/'+resort
    special = {'/林間雪道':'/guides/best-hokkaido-tree-runs','/packing-checklist':'/guides/packing-checklist',
               '/第一次滑雪，新手懶人包':'/guides/preparation'}
    titles = {}
    rows = SiteContent.objects.filter(client=client,location_key='guides.articles').values('id','title','body','link_url','metadata__url','metadata__article_mode')
    for row in rows:
        path = source_path(row['link_url'] or row['metadata__url'] or '')
        if path is None:
            continue
        mode = row['metadata__article_mode'] or ('external' if row['link_url'] and not row['body'] else 'internal')
        target = '/guides/articles/'+str(row['id']) if mode=='internal' else special.get(path)
        if target:
            paths[path] = target
            title = row['title'].strip()
            titles[title] = target if title not in titles else None
    return base, paths, titles


def resolve_guide_link(original, index, label=''):
    base, paths, titles = index
    path = source_path(original)
    target = paths.get(path) if path is not None else None
    if not target and path is not None:
        target = titles.get(label)
    if not target:
        return original
    fragment = urlsplit(original).fragment
    return base+target+('#'+fragment if fragment else '')


def rewrite_guide_links(html, index):
    class OpeningTag(HTMLParser):
        def handle_starttag(self, tag, attrs):
            self.attrs = attrs
    def anchor(match):
        parser = OpeningTag(convert_charrefs=True)
        parser.feed('<a'+match.group(1)+'>')
        hrefs = [value for name,value in parser.attrs if name=='href']
        if len(hrefs) != 1 or not isinstance(hrefs[0],str):
            return match.group(0)
        original = hrefs[0]
        label = unescape(re.sub(r'<[^>]*>', '', match.group(2))).strip()
        replacement = resolve_guide_link(original,index,label)
        if replacement == original:
            return match.group(0)
        attrs = ''.join(' '+name+(f'="{escape(replacement if name=="href" else value,quote=True)}"' if value is not None else '') for name,value in parser.attrs)
        return '<a'+attrs+'>'+match.group(2)+'</a>'
    return re.sub(r'<a\b((?:[^>\"\']|\"[^\"]*\"|\'[^\']*\')*)>([\s\S]*?)</a\s*>', anchor, html, flags=re.I)
