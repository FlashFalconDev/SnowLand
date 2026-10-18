from functools import lru_cache
from pathlib import Path

from Client.models import SiteContent
from django.utils import timezone

from .participant_forms import GUARDIAN_AGE_LIMIT


WAIVER_LOCATION_KEY = 'membership.waiver'
WAIVER_DEFAULT_VERSION = 'V0-2026-10-08'
WAIVER_SOURCE_URL = (
    'https://docs.google.com/document/d/'
    '1x-tLZo3DHYJpIY21FmF5KhoFuLoXn2O7QAmJLGwnAKw/edit'
)


def waiver_requires_resign(member, document):
    """A recorded online signature belongs to its version, not every future version.

    A timestamp-only administrative/paper acknowledgement is a separate legacy
    workflow and is not silently converted into an online signature here.
    """
    return bool(member.waiver_signature and member.waiver_document_version != document['version'])


@lru_cache(maxsize=1)
def _default_waiver_body():
    path = Path(__file__).resolve().parent / 'legal' / 'snowland_waiver_v0.md'
    return path.read_text(encoding='utf-8')


def get_current_waiver(client):
    """Return the active CMS waiver, falling back to the customer-provided V0 draft."""
    item = SiteContent.objects.filter(
        client=client,
        content_type='page',
        location_key=WAIVER_LOCATION_KEY,
        status='active',
    ).order_by('-updated_at', '-id').first()
    if item:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        return {
            'title': item.title or 'SnowLand 滑雪運動安全聲明書',
            'version': str(metadata.get('version') or item.external_id or item.updated_at.strftime('%Y%m%d%H%M%S')),
            'body': item.body,
            'source_url': item.link_url or WAIVER_SOURCE_URL,
            'is_draft': bool(metadata.get('is_draft', False)),
            'guardian_age_limit': GUARDIAN_AGE_LIMIT,
            'reference_date': timezone.localdate().isoformat(),
        }
    return {
        'title': 'SnowLand 滑雪運動安全聲明書',
        'version': WAIVER_DEFAULT_VERSION,
        'body': _default_waiver_body(),
        'source_url': WAIVER_SOURCE_URL,
        'is_draft': True,
        'guardian_age_limit': GUARDIAN_AGE_LIMIT,
        'reference_date': timezone.localdate().isoformat(),
    }
