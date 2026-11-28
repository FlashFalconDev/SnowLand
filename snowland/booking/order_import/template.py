"""Supply current tenant catalog options without changing the locked import sheet."""

from copy import copy
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.writer.excel import ExcelWriter

from Coursekit.models import CourseCategory, CourseTemplate
from Resorts.models import Campus, Resorts
from booking.models import ABILITY_LEVEL_CHOICES, Payment, Reservation

from .parser import SHEET_NAME
from .validation import (
    ABILITY_ALIASES, ADDON_MARKER, IMPORT_EQUIPMENT_CHOICES, LANGUAGE_ALIASES, METHOD_ALIASES, PAID_ALIASES, PAID_CHOICES,
    course_label, template_resort_ids,
)

TEMPLATE_PATH = Path(__file__).parent / 'assets' / 'snowland-order-import-template.xlsx'


def build_template():
    """Rebuild the bundled workbook as reproducible XLSX bytes."""
    book = load_workbook(TEMPLATE_PATH)
    sheet = book[SHEET_NAME]
    sheet['A2'] = '正式留空\n從第 7 列開始填。'
    sheet['H2'] = f'每列必填\n主課照「選項」填。同單攝影另列填項目，堂次備註寫「{ADDON_MARKER}」。'
    sheet['Q2'] = '每堂必填\n這一堂分到多少錢？填台幣實收。應收＝原價－折扣，有差額也照實填。'
    sheet['R2'] = '只填首列\n必填「已付款」，表示回填已收款項。'
    sheet['V2'] = f'選填／可後補\n同單攝影整格只寫「{ADDON_MARKER}」。日期、時間、人數、程度、金額留空。'
    sheet['Y2'] = '選填\n填正確的折扣前金額。有差價的堂次必填。'
    sheet['Z2'] = '選填\n留空為 0，可填 200 或 -200，折扣不得超過原價。'
    sheet['AB2'] = '只填首列\n這張單實際收到多少錢？有差價必填各堂已付加總，匯入後到後台結清待補款／待退款。'
    sheet.row_dimensions[2].height = 84

    for example_row, source_row in ((5, 3), (6, 4)):
        sheet.row_dimensions[example_row].height = sheet.row_dimensions[source_row].height
        for source, target in zip(sheet[source_row], sheet[example_row]):
            target._style = copy(source._style)
            target.value = source.value if example_row == 5 else None
    sheet['A6'] = '範例'
    sheet['B5'] = sheet['B6'] = 'DEMO-002'
    sheet['E5'] = 'photo-demo@example.com'
    sheet['U5'] = '虛構範例：滑雪主課與攝影同單。'
    sheet['AB5'] = sheet['Q5'].value
    sheet['H6'] = '攝影加購（範例）'
    sheet['V6'] = ADDON_MARKER

    prompt_range = 'V7:V1048576'
    price_prompts = {
        'Y5:Y1048576': '填正確的折扣前金額。原價減折扣為本堂應收，與實收不同時必填原價。',
        'AB5:AB1048576': '有堂次差價時首列必填。整單實收要等於各堂已付金額加總。',
    }
    for rule in list(sheet.data_validations.dataValidation):
        cell_range = str(rule.sqref)
        if cell_range == prompt_range:
            sheet.data_validations.dataValidation.remove(rule)
        elif cell_range in price_prompts:
            rule.prompt = price_prompts[cell_range]
    # Omit the validation type and formulas so any lesson note can be entered.
    prompt = DataValidation(
        allow_blank=True, showInputMessage=True, showErrorMessage=False,
        promptTitle='堂次備註',
        prompt=f'攝影和滑雪課同單時，這格只寫「{ADDON_MARKER}」。加購列的排課資料及金額留空。',
    )
    prompt.add(prompt_range)
    sheet.add_data_validation(prompt)

    guide = book['填寫說明']
    guide['A2'] = '正式資料從第 7 列開始'
    guide['B4'] = '首列填聯絡人、電話、信箱、校區、付款狀態和方式。只匯入已收到款項的台幣訂單。後續列的聯絡和付款欄可留空。'
    guide['B6'] = (
        '原價減折扣是應收金額，折扣留空當 0。本堂已付金額請填這堂分到的真實實收。'
        '例如兩堂各收到 4,000 元、2,500 元，首列已收款金額填 6,500 元。'
        '若應收與實收不同，請填正確的原價與折扣，首列必填已收款金額，須等於各堂已付加總。'
        '整單有差額會建成待補款／待退款，之後在後台「對帳與差額」結清。各堂差額互抵時只顯示警告。'
    )
    guide.row_dimensions[6].height = 84
    guide['B8'] = (
        f'攝影和滑雪課同單時另填一列，匯入訂單編號與主課相同。H 欄填攝影項目，V 欄「堂次備註」整格只寫「{ADDON_MARKER}」。\n'
        '加購列的上課日期、開始與結束時間、學員人數、程度、姓名、語言、教練、協助狀況、各項金額及折扣原因都留空。\n'
        '首列「已收款金額」須等於主課「本堂已付金額」加總。匯入只先建立主課，攝影待補記。攝影若要另排時間或另收費，請交行政處理。'
    )
    guide.row_dimensions[8].height = 84
    guide['B9'] = '課前資料建單後再補。獨立攝影課、跨訂單湊班、外幣、分期及既有退款請由行政個別處理。'
    guide['D30'] = '填「已付款」或「已收清」。有待補或待退時，仍按實際已收款填寫金額。'
    guide['D37'] = '填折扣前的台幣金額。有差價時必填，留空則用本堂已付加折扣推算。'
    guide['D38'] = '填 200 或 -200 均代表折抵 200 元，留空為 0。原價減折扣為本堂應收。'
    guide['D40'] = '有堂次差價時首列必填。金額須等於各堂已付金額加總。'

    serialized = BytesIO()
    with ZipFile(serialized, 'w', ZIP_DEFLATED) as archive:
        # Preserve the workbook's core properties, including its modified time.
        ExcelWriter(book, archive).write_data()

    output = BytesIO()
    with ZipFile(serialized) as source, ZipFile(output, 'w') as target:
        for name in source.namelist():
            data = source.read(name)
            if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                # et_xmlfile writes worksheet XML in text mode with native newlines.
                data = data.replace(b'&#13;', b'\r').replace(b'\r\n', b'\n').replace(b'\r', b'\n')
            member = ZipInfo(name)  # Use the fixed ZIP epoch for every member.
            member.create_system = 0
            target.writestr(member, data, compress_type=ZIP_DEFLATED)
    return output.getvalue()


def workbook_for_tenant(tenant):
    book = load_workbook(TEMPLATE_PATH)
    options = book['選項']
    options['A2'] = '下方是本校目前啟用的選項。請依同一校區與雪場的課程時段填寫。'
    options.delete_rows(4, options.max_row - 3)
    options['C3'] = '名稱'
    options['D3'] = '適用校區或雪場'
    append_standard_options(options)

    for campus in Campus.objects.filter(client=tenant, is_active=True):
        append_option(options, '校區', campus.code, campus.name)
    active_resorts = {}
    for resort in Resorts.objects.filter(campuses__client=tenant, campuses__is_active=True, client=tenant).distinct():
        campuses = resort.campuses.filter(client=tenant, is_active=True)
        append_option(options, '雪場', resort.name, resort.display_name, '、'.join(campus.name for campus in campuses))
        active_resorts[resort.pk] = resort.display_name
    templates = CourseTemplate.objects.filter(
        course_type__category__client=tenant, is_active=True, shared_class_enabled=False,
    ).exclude(course_type__category__service_type=CourseCategory.SERVICE_TYPE_PHOTO).select_related(
        'course_type__category',
    ).prefetch_related('resorts', 'pricing_options', 'sessions')
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
    append_input_examples(options)
    output = BytesIO()
    book.save(output)
    output.seek(0)
    return output


def append_standard_options(options):
    for label, choices in (
        ('學員程度', ABILITY_LEVEL_CHOICES),
        ('上課語言', Reservation.SINGLE_LANGUAGE_CHOICES),
        ('付款方式', Payment.PAYMENT_METHOD_CHOICES),
        ('付款狀態', PAID_CHOICES),
        ('協助狀況', IMPORT_EQUIPMENT_CHOICES),
    ):
        for key, display in choices:
            append_option(options, label, key, display)


def append_input_examples(options):
    options.auto_filter.ref = f'A3:D{options.max_row}'
    append_option(options, '也可以這樣寫', '例子', '系統會記成或如何處理')
    for cell in options[options.max_row]:
        cell.fill = PatternFill('solid', fgColor='DDEBF7')
        cell.font = Font(name='Microsoft JhengHei', size=11, bold=True)
    for field, choices, aliases, examples in (
        ('付款方式', Payment.PAYMENT_METHOD_CHOICES, METHOD_ALIASES, ('轉帳', '匯款轉帳')),
        ('付款狀態', PAID_CHOICES, PAID_ALIASES, ('已收清', '已付清')),
        ('上課語言', Reservation.SINGLE_LANGUAGE_CHOICES, LANGUAGE_ALIASES, ('華語', '英語', '廣東話')),
        ('學員程度', ABILITY_LEVEL_CHOICES, ABILITY_ALIASES, ('等級0', 'lv1')),
    ):
        labels = dict(choices)
        for alias in examples:
            append_option(options, field, alias, labels[aliases[alias]])
    for values in (
        ('上課日期、入帳日', '2027/1/20、2027年1月20日', '同一天。保留四位數年份，推薦填 2027-01-20。'),
        ('開始與結束時間', '9:00、０９：００', '同一時間。用 24 小時制，填到整分鐘。'),
        ('聯絡電話', '保留前導 0 或 + 國碼', '先把儲存格設成文字，再輸入或貼上。'),
        ('匯入訂單編號', '保留前導 0 與完整單號', '先把儲存格設成文字。同一張單的每堂都用相同編號。'),
    ):
        append_option(options, *values)


def append_option(sheet, *values):
    # Catalog names are literal spreadsheet text even when they begin with '='.
    cells = [Cell(sheet, row=sheet.max_row + 1, column=index, value=value) for index, value in enumerate(values, start=1)]
    for cell in cells:
        cell.data_type = 's'
    sheet.append(cells)
    for cell in sheet[sheet.max_row]:
        cell.font = Font(name='Microsoft JhengHei', size=11)
        cell.alignment = Alignment(wrap_text=True, vertical='top')
