"""Read the locked workbook or CSV without evaluating cells."""

import csv
import io
import re
from dataclasses import dataclass
from zipfile import BadZipFile, ZipFile
from xml.etree.ElementTree import ParseError
from zlib import error as ZipError

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from openpyxl.utils.exceptions import InvalidFileException


LEGACY_HEADERS = (
    '是否範例', '匯入訂單編號', '聯絡人姓名', '聯絡電話', '聯絡信箱', '校區', '雪場',
    '課程代碼或名稱', '上課日期', '開始時間', '結束時間', '學員人數', '學員程度',
    '學員姓名', '上課語言', '指定教練', '本堂已付金額', '付款狀態', '付款方式', '入帳日', '備註',
)
OPTIONAL_HEADERS = ('堂次備註', '協助狀況', '後五碼', '原價', '折扣金額', '扣內容', '已收款金額', '行銷統計')
HEADERS = LEGACY_HEADERS + OPTIONAL_HEADERS
DATE_COLUMNS = tuple(HEADERS.index(label) for label in ('上課日期', '入帳日'))
SHEET_NAME = '訂單匯入'
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 2000
MAX_CELL = 2000
MAX_EXPANDED_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class InputRow:
    number: int
    values: tuple
    invalid_cells: tuple = ()


@dataclass
class ParsedFile:
    rows: list
    skipped_examples: int


class FileError(ValueError):
    def __init__(self, code, message, columns=()):
        super().__init__(message)
        self.code = code
        self.columns = list(columns)


def blank(value):
    return value is None or isinstance(value, str) and not value.strip()


def check_header(row):
    required_width = len(LEGACY_HEADERS)
    wrong = [index for index, header in enumerate(LEGACY_HEADERS) if index >= len(row) or row[index] != header]
    if wrong:
        differences = [f'第 {index + 1} 欄應為「{HEADERS[index]}」' for index in wrong]
        raise FileError('invalid_header', '表頭不符。' + '、'.join(differences), [HEADERS[i] for i in wrong])
    end = max(index for index, value in enumerate(row) if not blank(value)) + 1
    optional = tuple(row[required_width:end])
    if optional != tuple(header for header in OPTIONAL_HEADERS if header in optional):
        raise FileError('invalid_header', '「備註」後只能使用新版範本的選填欄位，請保留欄位名稱及順序')
    return [HEADERS.index(header) for header in row[:end]]


def read_rows(rows, *, date_epoch=None):
    data = ParsedFile(rows=[], skipped_examples=0)
    rows = iter(rows)
    header, _ = next(rows, ((), ()))
    columns = check_header(header)
    for number, (values, invalid) in enumerate(rows, start=2):
        if number == 2:
            continue
        if number > MAX_ROWS + 2:
            raise FileError('too_many_rows', f'檔案最多可有 {MAX_ROWS} 列資料（另加表頭與第 2 列說明）')
        flag = values[0] if values else None
        if isinstance(flag, str) and flag.strip() == '範例':
            data.skipped_examples += 1
            continue
        if all(blank(value) for value in values):
            continue
        if any(not blank(value) for value in values[len(columns):]):
            raise FileError('extra_column', f'第 {number} 列第 {len(columns) + 1} 欄起有資料，但沒有表頭')
        canonical = [None] * len(HEADERS)
        for index, value in zip(columns, values):
            if date_epoch and index in DATE_COLUMNS and type(value) in (int, float):
                try:
                    value = from_excel(value, epoch=date_epoch)
                except (OverflowError, ValueError):
                    pass
            canonical[index] = value
        invalid = {columns[index] for index in invalid if index < len(columns)}
        invalid.update(
            index for index, value in enumerate(canonical)
            if isinstance(value, str) and (
                len(value) > MAX_CELL or value.lstrip().startswith('=') or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value)
            )
        )
        data.rows.append(InputRow(number, tuple(canonical), tuple(sorted(invalid))))
    return data


def parse_xlsx(content):
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 256 or sum(item.file_size for item in entries) > MAX_EXPANDED_BYTES:
                raise FileError('expanded_file_too_large', 'Excel 解壓縮後過大，請另存精簡檔案再上傳')
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False, keep_links=False)
        try:
            if SHEET_NAME not in workbook.sheetnames:
                raise FileError('missing_sheet', 'Excel 須包含「訂單匯入」工作表')
            sheet = workbook[SHEET_NAME]
            # Read actual rows even when the XLSX dimension metadata is inaccurate.
            sheet.reset_dimensions()
            return read_rows(((
                [cell.value for cell in row],
                [index for index, cell in enumerate(row[:len(HEADERS)])
                 if cell.data_type in ('f', 'e') or '%' in (getattr(cell, 'number_format', '') or '')],
            ) for row in sheet.iter_rows()), date_epoch=workbook.epoch)
        finally:
            workbook.close()
    except FileError:
        raise
    except (BadZipFile, InvalidFileException, ParseError, ZipError, TypeError, ValueError, KeyError, IndexError, OSError, OverflowError, RuntimeError):
        raise FileError('invalid_xlsx', '無法讀取 Excel，請以原範本另存成 .xlsx 後重試') from None


def parse_csv(content):
    try:
        try:
            decoded = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            decoded = content.decode('cp950')
        rows = csv.reader(io.StringIO(decoded, newline=''), strict=True)
        return read_rows((row, ()) for row in rows)
    except (UnicodeDecodeError, csv.Error):
        raise FileError('invalid_csv', '無法讀取 CSV，請另存成 UTF-8 或 CP950 編碼的 CSV') from None


def parse_file(filename, content):
    if len(content) > MAX_BYTES:
        raise FileError('file_too_large', '檔案不可超過 5 MB')
    if filename.lower().endswith('.xlsx'):
        return parse_xlsx(content)
    if filename.lower().endswith('.csv'):
        return parse_csv(content)
    raise FileError('unsupported_file', '請上傳 .xlsx 或 .csv 檔案')
