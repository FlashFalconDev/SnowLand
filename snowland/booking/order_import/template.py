"""Supply current tenant catalog options without changing the locked import sheet."""

from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font

from Coursekit.models import CourseTemplate
from Resorts.models import Campus, Resorts
from booking.models import ABILITY_LEVEL_CHOICES, Payment, Reservation

from .validation import IMPORT_EQUIPMENT_CHOICES, course_label, template_resort_ids

TEMPLATE_PATH = Path(__file__).parent / 'assets' / 'snowland-order-import-template.xlsx'


def workbook_for_tenant(tenant):
    book = load_workbook(TEMPLATE_PATH)
    options = book['選項']
    options['A2'] = '下方是本校目前啟用的選項。請依同一校區與雪場的課程時段填寫。'
    options.delete_rows(4, options.max_row - 3)
    options['C3'] = '名稱'
    options['D3'] = '適用校區或雪場'
    for label, choices in (
        ('學員程度', ABILITY_LEVEL_CHOICES),
        ('上課語言', Reservation.SINGLE_LANGUAGE_CHOICES),
        ('付款方式', Payment.PAYMENT_METHOD_CHOICES),
        ('付款狀態', [('paid', '已付款')]),
        ('協助狀況', IMPORT_EQUIPMENT_CHOICES),
    ):
        for key, display in choices:
            append_option(options, label, key, display)

    for campus in Campus.objects.filter(client=tenant, is_active=True):
        append_option(options, '校區', campus.code, campus.name)
    active_resorts = {}
    for resort in Resorts.objects.filter(campuses__client=tenant, campuses__is_active=True, client=tenant).distinct():
        campuses = resort.campuses.filter(client=tenant, is_active=True)
        append_option(options, '雪場', resort.name, resort.display_name, '、'.join(campus.name for campus in campuses))
        active_resorts[resort.pk] = resort.display_name
    templates = CourseTemplate.objects.filter(
        course_type__category__client=tenant, is_active=True, shared_class_enabled=False,
    ).select_related('course_type__category').prefetch_related('resorts', 'pricing_options', 'sessions')
    for template in templates:
        resort_ids = template_resort_ids(template)
        resort_names = '、'.join(name for pk, name in active_resorts.items() if pk in resort_ids)
        if not resort_names:
            continue
        course = course_label(template)
        append_option(options, '課程代碼或名稱', str(template.pk), course, resort_names)
        for session in template.sessions.all():
            if session.is_active:
                window = f'{session.start_time:%H:%M}–{session.end_time:%H:%M}'
                append_option(options, '時段', window, course, resort_names)
    if options.auto_filter.ref:
        options.auto_filter.ref = f'A3:D{options.max_row}'
    output = BytesIO()
    book.save(output)
    output.seek(0)
    return output


def append_option(sheet, *values):
    # Catalog names are literal spreadsheet text even when they begin with '='.
    cells = [Cell(sheet, row=sheet.max_row + 1, column=index, value=value) for index, value in enumerate(values, start=1)]
    for cell in cells:
        cell.data_type = 's'
    sheet.append(cells)
    for cell in sheet[sheet.max_row]:
        cell.font = Font(name='Microsoft JhengHei', size=11)
        cell.alignment = Alignment(wrap_text=True, vertical='top')
