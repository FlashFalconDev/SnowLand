from datetime import date

from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from booking.models import Booking
from .dashboard_reports import csv_report


def export_orders(queryset, params):
    basis = params.get('date_basis', 'created')
    direction = params.get('sort', 'asc')
    if basis not in ('created', 'lesson') or direction not in ('asc', 'desc'):
        raise ValidationError({'msg': '日期依據或排序方式不正確'})
    try:
        start, end = (date.fromisoformat(params.get(key, '')) for key in ('start', 'end'))
    except ValueError as exc:
        raise ValidationError({'msg': '請選擇有效的開始與結束日期'}) from exc
    if not 0 <= (end - start).days <= 365:
        raise ValidationError({'msg': '請選擇最多 366 天的有效日期區間'})

    if basis == 'created':
        queryset = queryset.filter(created_at__date__range=(start, end))
    else:
        matching = Booking.objects.filter(
            reservation__group_id=OuterRef('pk'), date__range=(start, end),
        ).exclude(reservation__status__in=['cancelled', 'deleted'])
        queryset = queryset.filter(Exists(matching))

    rows = []
    for group in queryset.iterator(chunk_size=100):
        created = timezone.localtime(group.created_at).isoformat(timespec='minutes')
        prefix = (group.order_number or str(group.pk), created, group.campus.name if group.campus else '')
        sessions = [
            (resort, lesson)
            for reservation in group.reservations.all()
            if reservation.status not in ('cancelled', 'deleted')
            for resort in [reservation.resort.display_name if reservation.resort else '']
            for lesson in reservation.bookings.all()
            if basis == 'created' or start <= lesson.date <= end
        ]
        if not sessions and basis == 'created':
            rows.append((*prefix, '', '', '', '', ''))
        for resort, lesson in sessions:
            rows.append((*prefix, lesson.date.isoformat(), lesson.start_time.isoformat(timespec='minutes'),
                         lesson.end_time.isoformat(timespec='minutes'), resort, lesson.course_name))
        if len(rows) > 20000:
            raise ValidationError({'msg': '匯出超過 20,000 列，請縮小日期區間'})

    sort_columns = (1, 3, 4, 0) if basis == 'created' else (3, 4, 1, 0)
    rows.sort(key=lambda row: tuple(row[column] for column in sort_columns), reverse=direction == 'desc')
    header = ('訂單編號', '下單時間', '校區', '上課日期', '開始時間', '結束時間', '雪場', '課程')
    return csv_report([header, *rows], f'SnowLand-orders-{start}-{end}.csv')
