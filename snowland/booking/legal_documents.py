from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from Client.models import SiteContent
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .participant_forms import GUARDIAN_AGE_LIMIT


WAIVER_LOCATION_KEY = 'membership.waiver'
WAIVER_DEFAULT_VERSION = 'V0-2026-10-08'
WAIVER_SOURCE_URL = (
    'https://docs.google.com/document/d/'
    '1x-tLZo3DHYJpIY21FmF5KhoFuLoXn2O7QAmJLGwnAKw/edit'
)


def waiver_version(item):
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    return str(metadata.get('version') or item.external_id or item.updated_at.strftime('%Y%m%d%H%M%S'))


def versioned_waiver_metadata(attrs, instance=None):
    metadata = dict(attrs.get('metadata', getattr(instance, 'metadata', {})) or {})
    changed = instance is None or instance.location_key != WAIVER_LOCATION_KEY or any(attrs.get(field, getattr(instance, field)) != getattr(instance, field) for field in ('title','body'))
    metadata['version'] = 'V'+timezone.now().strftime('%Y%m%d%H%M%S')+'-'+uuid4().hex[:10] if changed else waiver_version(instance)
    publishing = instance is not None and instance.status != 'active' and attrs.get('status') == 'active'
    previous = instance.metadata if instance and isinstance(instance.metadata, dict) else {}
    metadata['_waiver_updated_at'] = timezone.now().isoformat() if changed or publishing else previous.get('_waiver_updated_at') or instance.updated_at.isoformat()
    return metadata


def waiver_document_time(item):
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    value = metadata.get('_waiver_updated_at')
    try:
        parsed = parse_datetime(value) if isinstance(value, str) else None
    except ValueError:
        parsed = None
    return parsed if parsed and timezone.is_aware(parsed) else item.updated_at


def waiver_requires_resign(member, document):
    """A recorded online signature belongs to its version, not every future version.

    A timestamp-only administrative/paper acknowledgement is a separate legacy
    workflow and is not silently converted into an online signature here.
    """
    return bool(member.waiver_resign_required or (member.waiver_signature and member.waiver_document_version != document['version']))


def course_waiver_revision(member):
    return member.course_document_revisions.order_by('-pk').values_list('pk', flat=True).first() or 0


@lru_cache(maxsize=1)
def _default_waiver_body():
    path = Path(__file__).resolve().parent / 'legal' / 'snowland_waiver_v0.md'
    return path.read_text(encoding='utf-8')


def get_current_waiver(client):
    """Return the active CMS waiver, falling back to the customer-provided V0 draft."""
    documents = SiteContent.objects.filter(
        client=client,
        content_type='page',
        location_key=WAIVER_LOCATION_KEY,
        status='active',
    )
    item = max(documents, key=lambda row:(waiver_document_time(row),row.pk), default=None)
    if item:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        return {
            'title': item.title or 'SnowLand 滑雪運動安全聲明書',
            'version': waiver_version(item),
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
