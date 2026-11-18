"""Measure the existing scheduler without coupling metrics to booking writes."""

import logging
from contextvars import ContextVar
from datetime import datetime, time
from functools import wraps
from time import perf_counter_ns

from django.db import DatabaseError, transaction
from django.db.models import Avg, Count
from django.utils import timezone

from .models import SchedulingRun

logger = logging.getLogger(__name__)
_runs = ContextVar('scheduling_runs', default=None)
Source = SchedulingRun.Source


def collect_scheduling_metrics(view):
    """Apply outside the view's order transaction, including on rollback."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        runs = []
        token = _runs.set(runs)
        try:
            return view(*args, **kwargs)
        finally:
            _runs.reset(token)
            if runs:
                try:
                    with transaction.atomic():
                        SchedulingRun.objects.bulk_create(runs)
                except DatabaseError:
                    logger.warning('Could not store scheduler timing data')
    return wrapped


def measure_scheduling(client_id, source, schedule, *args, **kwargs):
    runs = _runs.get()
    if runs is None or client_id is None:
        return schedule(*args, **kwargs)
    started_at = timezone.now()
    start = perf_counter_ns()
    try:
        return schedule(*args, **kwargs)
    finally:
        runs.append(SchedulingRun(
            client_id=client_id, source=source, started_at=started_at,
            elapsed_ms=(perf_counter_ns() - start) // 1_000_000,
        ))


def scheduling_metrics(client, start, end):
    """Use execution dates in the site's timezone, not lesson dates."""
    rows = SchedulingRun.objects.filter(
        client=client,
        started_at__range=(
            timezone.make_aware(datetime.combine(start, time.min)),
            timezone.make_aware(datetime.combine(end, time.max)),
        ),
    ).values('source').annotate(run_count=Count('id'), average_ms=Avg('elapsed_ms'))
    by_source = {row['source']: row for row in rows}
    return [
        by_source.get(source, {'source': source, 'run_count': 0, 'average_ms': None})
        for source in Source.values
    ]
