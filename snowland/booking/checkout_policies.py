"""Versioned checkout documents shared by the website, checkout and order audit."""
import hashlib
import json
import re
from functools import lru_cache
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from django.db.models import Q
from django.utils import timezone
from Client.models import SiteContent


POLICY_PAGES = {
    'membershipTerms': 'policy.membership-terms',
    'privacyPolicy': 'policy.privacy-policy',
    'cancellationPolicy': 'policy.cancellation-policy',
}


class PolicyText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'h2', 'h3', 'h4', 'br', 'li'):
            self.parts.append('\n' + ('• ' if tag == 'li' else ''))

    def handle_endtag(self, tag):
        if tag in ('p', 'h2', 'h3', 'h4', 'li', 'ul', 'ol'):
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)


@lru_cache(maxsize=1)
def default_policy_pages():
    return json.loads((Path(__file__).parent / 'legal' / 'checkout_policies.json').read_text(encoding='utf-8'))


def checkout_policy_payload(client):
    now = timezone.now()
    overrides = SiteContent.objects.filter(client=client, content_type='page',
        location_key__in=POLICY_PAGES.values(), status='active').filter(
        Q(start_at__isnull=True) | Q(start_at__lte=now),
        Q(end_at__isnull=True) | Q(end_at__gte=now)).order_by('-updated_at', '-pk')
    latest = {}
    for item in overrides:
        latest.setdefault(item.location_key, item)
    pages = {}
    for name, location in POLICY_PAGES.items():
        item = latest.get(location)
        if item:
            title = item.title.strip()
            body = item.body.strip()
            html = escape(body).replace('\n', '<br>')
        else:
            original = default_policy_pages()[name]
            title, html = original['title'], original['html']
            parser = PolicyText(); parser.feed(html)
            body = re.sub(r'\n{3,}', '\n\n', ''.join(parser.parts)).strip()
        if not title or not body:
            raise ValueError('訂課條款尚未設定完整，請聯絡管理員')
        pages[name] = {'title': title, 'body': body, 'html': html}
    combined = pages['membershipTerms']['title'] + '\n\n' + pages['membershipTerms']['body'] + '\n\n' + pages['cancellationPolicy']['title'] + '\n\n' + pages['cancellationPolicy']['body']
    documents = {'terms': {'title': '服務條款與退費規則', 'body': combined},
                 'privacy': {'title': '隱私政策與個資使用', 'body': pages['privacyPolicy']['title'] + '\n\n' + pages['privacyPolicy']['body']}}
    for key, document in documents.items():
        document['version'] = hashlib.sha256(f"{client.internal_code}:{key}:{document['title']}:{document['body']}".encode()).hexdigest()
    return {'pages': pages, 'documents': documents}


def accepted_checkout_policies(client, proof):
    if not isinstance(proof, dict) or any(proof.get(key) is not True for key in ('terms', 'privacy')):
        raise ValueError('請分別閱讀並同意服務條款與隱私政策')
    documents = checkout_policy_payload(client)['documents']
    if any(proof.get(key + '_version') != document['version'] for key, document in documents.items()):
        raise ValueError('訂課條款已更新，請重新閱讀並確認後再送出')
    return {**documents, 'accepted_at': timezone.now().isoformat()}
