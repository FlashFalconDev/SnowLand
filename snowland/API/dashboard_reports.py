"""Export only the authorized dashboard summary, never member/contact records."""
import csv
import io
import re

from django.http import HttpResponse


_ILLEGAL_SPREADSHEET_CHARACTERS = re.compile(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]')


def dashboard_report(data, *, file_format, start, end, date_basis, resort_name):
    rows = [
        ['SnowLand 營運統計'],
        ['開始日期', start], ['結束日期（含當日）', end],
        ['日期依據', '訂單建立日期' if date_basis == 'created' else '最後有效課程完成日期'],
        ['雪場', resort_name],
        ['說明', '營業額僅計最新付款為已付款、且整筆有效課程已完成；不含未付款、取消與已退款訂單。'],
        [], ['統計項目', '數值'],
    ]
    for key, label in (
        ('orders', '篩選後訂單數'), ('completed_orders', '已完成訂單數'),
        ('revenue', '已完成訂單營業額'), ('avg_order_value', '已完成訂單平均金額'),
        ('members', '下單會員數'), ('student_visits', '已完成學員人次（每堂）'),
        ('teaching_hours', '已完成授課時數（團體班不重複）'),
    ):
        rows.append([label, data['stats'][key]])
    for title, source in (('校區', 'campus_summary'), ('行銷來源', 'marketing_sources')):
        rows.extend([[], [title, '訂單數', '已完成營業額']])
        rows.extend([item['name'], item['orders'], item['revenue']] for item in data[source])
    rows.extend([[], ['付款狀態', '訂單數']])
    rows.extend([item['name'], item['orders']] for item in data['payment_statuses'])
    rows.extend([[], ['已完成熱門課程 TOP 5', '預約堂次', '營業額']])
    rows.extend([item['name'], item['quantity'], item['revenue']] for item in data['top_items'])
    # Pasted text may contain characters prohibited in XLSX XML. Keep the
    # source record intact and sanitize before checking CSV formula prefixes.
    rows = [[_ILLEGAL_SPREADSHEET_CHARACTERS.sub('', value) if isinstance(value, str) else value
             for value in row] for row in rows]
    if file_format == 'csv':
        stream = io.StringIO(newline='')
        # A quoted CSV field can still execute as a spreadsheet formula.
        csv.writer(stream).writerows([
            ["'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value
             for value in row] for row in rows
        ])
        response = HttpResponse(stream.getvalue().encode('utf-8-sig'), content_type='text/csv; charset=utf-8')
    else:
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = '營運統計'
        for row in rows:
            sheet.append(row)
            for cell in sheet[sheet.max_row]:
                if isinstance(cell.value, str):
                    cell.data_type = 's'
        sheet.column_dimensions['A'].width = 48
        sheet.column_dimensions['B'].width = 28
        sheet.column_dimensions['C'].width = 20
        sheet.freeze_panes = 'A9'
        stream = io.BytesIO()
        book.save(stream)
        response = HttpResponse(stream.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="SnowLand-report-{start}-{end}.{file_format}"'
    response['Cache-Control'] = 'private, no-store'
    return response
