"""Mechanically generate the CMS bootstrap fixture from a reviewed literal export."""
import json
from html.parser import HTMLParser
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'snowland'))
from Client.guide_source import convert_reference_article


class ArticleFidelity(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.images, self.links, self.videos = [], [], [], []
        self.tables = self.styles = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'style': self.styles += 1
        if tag == 'img': self.images.append(values.get('src'))
        if tag == 'a': self.links.append(values.get('href'))
        if tag == 'iframe': self.videos.append((values.get('src') or '').split('?',1)[0])
        if tag == 'table': self.tables += 1

    def handle_endtag(self, tag):
        if tag == 'style': self.styles = max(0, self.styles-1)

    def handle_data(self, data):
        if not self.styles: self.text.append(data)


def assert_fidelity(original, converted):
    before, after = ArticleFidelity(), ArticleFidelity()
    before.feed(original); after.feed(converted)
    # Removing a CSS element can join adjacent data callbacks, not change text.
    before.text, after.text = ''.join(before.text), ''.join(after.text)
    for field in ('text','images','links','videos','tables'):
        if getattr(before,field) != getattr(after,field):
            raise ValueError(f'Article conversion lost or changed original {field}')


def prepare(snapshot):
    rows = snapshot['articles']
    urls = set()
    for row in rows:
        if row['card']['url'] in urls:
            raise ValueError('Duplicate article URL')
        urls.add(row['card']['url'])
    result = []
    for row in rows:
        article = convert_reference_article(row['article'])
        assert_fidelity(row['article']['html'],article['html'])
        result.append({'card':row['card'], 'article':article})
    return {**snapshot, 'articles':result}


if __name__ == '__main__':
    source, destination = map(Path, sys.argv[1:])
    snapshot = prepare(json.loads(source.read_text(encoding='utf-8')))
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(snapshot, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(f"Prepared {len(snapshot['articles'])} complete CMS articles; no database changes.")
