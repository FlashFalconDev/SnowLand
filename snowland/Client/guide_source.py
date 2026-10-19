"""Convert the supplied public article export without executing its code or CSS."""
from html import escape
from html.parser import HTMLParser
import re
from Client.article_pages import ArticleHTMLValidator, validate_article_metadata, youtube_embed


class ReferenceArticleParser(HTMLParser):
    wrappers = {'article':'div', 'header':'div', 'footer':'div', 'section':'div', 'time':'span'}
    void = {'img','br','hr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'style':
            self.suppressed += 1
            return
        if self.suppressed:
            return
        tag = self.wrappers.get(tag, tag)
        if tag == 'iframe':
            source = dict(attrs).get('src')
            if not youtube_embed(source):
                raise ValueError('來源影片不是受支援的YouTube嵌入網址')
            # Do not carry origin/jsapi/autoplay settings from the old website.
            source = source.split('?', 1)[0]
            attrs = [('src', source), ('title', dict(attrs).get('title') or 'YouTube影片'), ('loading','lazy'), ('allowfullscreen','')]
        elif tag not in ArticleHTMLValidator.tags:
            raise ValueError(f'來源含未知標記: {tag}')
        else:
            attrs = [(name, value or '') for name, value in attrs if name in ArticleHTMLValidator.attributes and name not in ('allowfullscreen',)]
            attrs = [(name, value) for name, value in attrs if name != 'style' or not re.search(r'expression|url\s*\(|@import|javascript|[\\]', value, re.I)]
        self.output.append('<' + tag + ''.join(f' {name}="{escape(value, quote=True)}"' for name, value in attrs) + '>')

    def handle_endtag(self, tag):
        if tag == 'style':
            self.suppressed = max(0, self.suppressed - 1)
            return
        if self.suppressed:
            return
        tag = self.wrappers.get(tag, tag)
        if tag not in self.void:
            self.output.append(f'</{tag}>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not self.suppressed:
            self.output.append(escape(data))


def convert_reference_article(article):
    if not isinstance(article, dict) or not isinstance(article.get('html'), str):
        raise ValueError('來源文章格式不正確')
    parser = ReferenceArticleParser()
    parser.feed(article['html'])
    parser.close()
    converted = {key:value for key,value in article.items() if key != 'slug'}
    converted['html'] = ''.join(parser.output)
    validate_article_metadata({'article':converted}, True)
    return converted
