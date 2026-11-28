"""Validate spreadsheet rows against the import contract and the tenant's catalog."""

import datetime as dt
import re
from dataclasses import dataclass
from functools import cached_property
from unicodedata import normalize
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from Client.models import ClientMemberProfile
from Client.tenant_settings import manual_payment_posting_date_mode
from Coach.models import Coach
from Coursekit.models import CourseCategory, CoursePricing, CourseTemplate
from Resorts.models import Campus, Resorts
from booking.capacity import Slot
from booking.models import ABILITY_LEVEL_CHOICES, EQUIPMENT_CHOICES, Booking, Payment, Reservation, ReservationGroup

from .parser import HEADERS, blank

(
    FLAG, KEY, NAME, PHONE, EMAIL, CAMPUS, RESORT, TEMPLATE, DAY, START, END, PEOPLE, ABILITY, NAMES, LANGUAGE,
    COACH, FEE, PAID, METHOD, POSTED, NOTE, LESSON_NOTE, EQUIPMENT, BANK_LAST_FIVE, ORIGINAL, DISCOUNT,
    DISCOUNT_NOTE, RECEIVED, MARKETING,
) = HEADERS
ORDER_FIELDS = (NAME, PHONE, EMAIL, CAMPUS, PAID, METHOD, POSTED, BANK_LAST_FIVE, RECEIVED, MARKETING)
REQUIRED_ORDER_FIELDS = (NAME, PHONE, EMAIL, CAMPUS, PAID, METHOD)
CONTACT_FIELDS = (NAME, PHONE, EMAIL, MARKETING)
MAX_INT = 2_147_483_647
IMPORT_CURRENCY = 'TWD'
IMPORT_EQUIPMENT_CHOICES = tuple((key, label) for key, label in EQUIPMENT_CHOICES if key != 'purchaseAssistanceTime')
PAID_CHOICES = (('paid', '已付款'),)
METHOD_ALIASES = dict.fromkeys(('轉帳', '匯款轉帳', '銀行轉帳', '轉賬', 'bank transfer'), 'TT')
PAID_ALIASES = dict.fromkeys(('已收清', '已付清', '已全額付款', '全額付清'), 'paid')
LANGUAGE_ALIASES = {
    '國語': 'zh', '華語': 'zh', '普通話': 'zh', '英語': 'en', 'english': 'en', '廣東話': 'yue', '廣東語': 'yue',
}
PAYMENT_TOKENS = {'cash', '現金', *METHOD_ALIASES} | {
    value.casefold() for pair in Payment.PAYMENT_METHOD_CHOICES for value in pair
}
ABILITY_RANK = {key: rank for rank, (key, _) in enumerate(ABILITY_LEVEL_CHOICES)}
ABILITY_ALIASES = {
    alias: key for rank, key in enumerate(ABILITY_RANK)
    for alias in (str(rank), f'等級{rank}', f'level {rank}', f'lv{rank}')
}
ADDON_MARKER = '隨單加購'
ADDON_HINTS = ('攝影', '寫真', '相簿', '加購')
TAIPEI = ZoneInfo('Asia/Taipei')


def redact(value):
    value = re.sub(r'[\w.+-]+@[\w.-]+', '［信箱已遮罩］', value)
    return re.sub(r'(?<!\w)\+?\d(?:[ -]?\d){6,14}(?!\w)', '［電話已遮罩］', value)


def issue(row, key, level, code, message, *columns):
    return {
        'row_number': row, 'group_key': redact(key), 'level': level, 'code': code,
        'message_zh': message, 'columns': list(columns),
    }


def text(value, limit):
    if not isinstance(value, str):
        raise ValueError('請以文字填寫')
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f'最多可填 {limit} 字')
    return value


def identifier(value, limit=150):
    if type(value) in (int, float):
        if not 0 <= value < 10**15 or (type(value) is float and not value.is_integer()):
            raise ValueError('請填有效整數編號。超過 15 位或含前導 0 時，請以文字填寫')
        return str(int(value))
    return text(value, limit)


def integer(value, minimum):
    if isinstance(value, str):
        token = normalize('NFKC', value.strip())
        if re.fullmatch(r'[0-9]{1,10}|[0-9]{1,3}(?:,[0-9]{3}){1,3}', token):
            value = int(token.replace(',', ''))
    if type(value) is float and value.is_integer():
        value = int(value)
    if type(value) is not int or not minimum <= value <= MAX_INT:
        raise ValueError(f'請填 {minimum} 至 {MAX_INT} 的整數')
    return value


def phone(value):
    value = normalize('NFKC', text(value, 40))
    value = re.sub(r'\((\+?[0-9]+)\)', r'\1', value)
    value = re.sub(r'[\s\-‐‑‒–—−]', '', value)
    if not re.fullmatch(r'\+?[0-9]{7,15}', value):
        raise ValueError('請填 7 至 15 碼電話，可使用 + 國碼，請保留前導 0')
    return value


def email(value):
    value = text(value, 254).lower()
    try:
        validate_email(value)
    except ValidationError:
        raise ValueError('請填有效的電子郵件') from None
    return value


def day(value):
    if isinstance(value, dt.datetime) and value.time() == dt.time():
        return value.date()
    if type(value) is dt.date:
        return value
    if isinstance(value, str):
        token = normalize('NFKC', value.strip())
        token = re.sub(r'^([0-9]{4})\s*年\s*([0-9]{1,2})\s*月\s*([0-9]{1,2})\s*日$', r'\1-\2-\3', token)
        match = re.fullmatch(r'([0-9]{4})([-/.])([0-9]{1,2})\2([0-9]{1,2})', token)
        if match:
            try:
                return dt.date(int(match[1]), int(match[3]), int(match[4]))
            except ValueError:
                pass
    raise ValueError('請填有效日期，建議使用 YYYY-MM-DD')


def minute(value):
    if type(value) is dt.time and not (value.second or value.microsecond):
        return value
    if isinstance(value, str):
        token = normalize('NFKC', value.strip())
        match = re.fullmatch(r'([0-9]{1,2})\s*:\s*([0-9]{2})(?::00)?', token)
        if match:
            try:
                return dt.time(*map(int, match.groups()))
            except ValueError:
                pass
    raise ValueError('請填有效時間，格式為 HH:MM，以整分鐘填寫')


def choice_token(value):
    return ' '.join(normalize('NFKC', value).split()).casefold()


def choice(value, choices, aliases=None):
    token = choice_token(text(value, 40))
    if aliases and token in aliases:
        return aliases[token]
    for key, label in choices:
        if token in (choice_token(key), choice_token(label)):
            return key
    raise ValueError('請填寫範本「選項」中的有效代碼或名稱')


def bank_last_five(value):
    if type(value) in (int, float):
        token = identifier(value).zfill(5)
    else:
        token = normalize('NFKC', text(value, 100))
    if not re.fullmatch(r'[0-9]{5}', token):
        raise ValueError('請只填匯款帳號的最後五位數字，勿填完整帳號')
    return token


def equipment(value):
    if isinstance(value, str) and choice_token(value) in ('purchaseassistancetime', '加購協助時間'):
        raise ValueError('加購協助時間請建單後由行政另排')
    return choice(value, IMPORT_EQUIPMENT_CHOICES)


def marketing_source(value):
    source = text(value, ReservationGroup._meta.get_field('marketing_source').max_length)
    if choice_token(source) in ('不知道', '未知', '不清楚', 'n/a', 'unknown', '?', '-'):
        raise ValueError('請填已知的來源')
    return source


def discount_amount(value):
    if isinstance(value, str):
        value = normalize('NFKC', value.strip()).replace('−', '-').removeprefix('-')
    elif type(value) in (int, float):
        value = abs(value)
    return integer(value, 0)


def ability(value, people):
    choices = ABILITY_LEVEL_CHOICES
    token = normalize('NFKC', text(identifier(value), 120))
    if not re.search(r'[:,、;\n]', token):
        return {choice(token, choices, ABILITY_ALIASES): people}
    counts = {}
    for item in re.split(r'[,、;\n]', token):
        name, separator, count = item.partition(':')
        if not separator:
            raise ValueError('多個程度請填「等級 0:1、等級 1:1」格式')
        level = choice(name, choices, ABILITY_ALIASES)
        if level in counts:
            raise ValueError('學員程度不得重複')
        counts[level] = integer(count, 1)
    total = sum(counts.values())
    if people is not None and total != people:
        raise ValueError(f'學員人數填了 {people} 人，各程度合計為 {total} 人。請修正這兩欄，讓人數相同')
    return counts


def learner_names(value, people):
    names = tuple(text(name, 120) for name in text(value, 2000).split('、'))
    if not all(names) or (people is not None and len(names) != people):
        raise ValueError('請用「、」分隔每位學員姓名，姓名數量須等於本堂學員人數')
    return names


def group_rows(rows):
    groups = {}
    issues = []
    for row in rows:
        try:
            if 1 in row.invalid_cells or blank(row.values[1]):
                raise ValueError
            key = identifier(row.values[1])
        except ValueError:
            issues.append(issue(row.number, '', 'error', 'invalid_order_number', '請填有效的匯入訂單編號（最多 150 字）', KEY))
            continue
        groups.setdefault(key, []).append(row)
    return groups, issues


@dataclass(frozen=True)
class Lesson:
    row_number: int
    resort: Resorts
    slot: Slot
    people: int
    abilities: dict
    learner_names: tuple
    language: str
    coach: Coach | None
    fee: int
    original: int
    discount: int
    discount_note: str
    equipment: str | None
    note: str | None

    @property
    def highest_level(self):
        return max(self.abilities, key=ABILITY_RANK.__getitem__)


@dataclass(frozen=True)
class Addon:
    row_number: int
    label: str
    note: str
    resort_id: int | None


@dataclass(frozen=True)
class ImportOrder:
    key: str
    first_row: int
    fields: dict
    lessons: list
    user: User | None
    member_code: str
    addons: tuple
    expected_amount: int

    @property
    def amount(self):
        return sum(lesson.fee for lesson in self.lessons)

    @property
    def balance_amount(self):
        return self.expected_amount - self.amount

    @property
    def contact(self):
        return {'name': self.fields[NAME], 'phone': self.fields[PHONE], 'email': self.fields[EMAIL]}


def unique(matches, message):
    matches = list(matches[:2])
    if len(matches) != 1:
        raise ValueError(message)
    return matches[0]


class CourseError(ValueError):
    def __init__(self, code, message, *columns):
        super().__init__(message)
        self.code = code
        self.columns = columns or (TEMPLATE,)


def course_label(template):
    return f'{template.course_type.category.name}／{template.course_type.name}／{template.name}'


def course_token(value):
    return re.sub(r'\s+', '', normalize('NFKC', value)).casefold()


def course_identifier(value):
    token = course_token(identifier(value, 302))
    if re.fullmatch(r'[0-9]+', token):
        return token.lstrip('0') or '0'
    return token


def candidate_hint(token, choices):
    candidates = [
        label for label, aliases in choices
        if len(token) >= 2 and any(token in alias for alias in aliases)
    ]
    if len(candidates) == 1:
        return f' 可核對這個選項並照填「{redact(candidates[0])}」。'
    return ''


def catalog_entry(value, entries, message):
    token = course_token(text(value, 100))
    matches = [entry for entry, aliases in entries if token in aliases]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(message + candidate_hint(token, [
        (str(entry), aliases) for entry, aliases in entries
    ]))


def template_resort_ids(template):
    direct = {resort.pk for resort in template.resorts.all()}
    # Like staff booking links, accept active resort pricing only when there are no explicit bindings.
    return direct or {price.resort_id for price in template.pricing_options.all() if price.is_active}


def in_course_period(template, course_day):
    return (
        (not template.course_start_date or course_day >= template.course_start_date)
        and (not template.course_end_date or course_day <= template.course_end_date)
    )


def active_windows(template):
    return {(session.start_time, session.end_time) for session in template.sessions.all() if session.is_active}


def matching_windows(template, start, end):
    return [
        (left, right) for left, right in active_windows(template)
        if (start is None or start == left) and (end is None or end == right)
    ]


def addon_marked(*notes):
    return any(
        part.strip() == ADDON_MARKER
        for note in notes if note
        for part in re.split(r'[\n、;|,。]', normalize('NFKC', note))
    )


def session_error(templates):
    windows = sorted(set().union(*(active_windows(template) for template in templates)))
    if windows:
        allowed = '、'.join(f'{start:%H:%M}–{end:%H:%M}' for start, end in windows[:8])
        message = f'開始與結束時間不符。這個課程可填的時段有 {allowed}，也可在範本「選項」查詢。'
    else:
        message = '這個課程尚無啟用時段，請由行政確認課程設定。'
        if any(template.course_type.category.service_type == CourseCategory.SERVICE_TYPE_PHOTO for template in templates):
            message += '若這筆是同單加購，請依範本「填寫說明」標記並重新預覽。'
    return CourseError('unknown_session', message, START, END)


class Validator:
    def __init__(self, tenant):
        self.tenant = tenant
        self.today = timezone.localdate(timezone=TAIPEI)

    @cached_property
    def posting_mode(self):
        return manual_payment_posting_date_mode(self.tenant)

    @cached_property
    def campuses(self):
        return [
            (campus, {course_token(campus.code), course_token(campus.name)})
            for campus in Campus.objects.filter(client=self.tenant, is_active=True)
        ]

    def campus(self, value):
        return catalog_entry(value, self.campuses, '找不到唯一的啟用校區，請核對「選項」的校區名稱或代碼。')

    @cached_property
    def resorts(self):
        return [
            (resort, {course_token(resort.name), course_token(resort.display_name or resort.name)},
             {campus.pk for campus in resort.campuses.all()})
            for resort in Resorts.objects.filter(client=self.tenant).prefetch_related('campuses')
        ]

    def resort(self, value, campus):
        return catalog_entry(value, [
            (resort, aliases) for resort, aliases, campuses in self.resorts if not campus or campus.pk in campuses
        ], '找不到此校區可使用的唯一雪場，請核對「選項」的雪場名稱。')

    @cached_property
    def templates(self):
        return list(CourseTemplate.objects.filter(course_type__category__client=self.tenant).select_related(
            'course_type__category',
        ).prefetch_related('resorts', 'pricing_options', 'sessions'))

    @cached_property
    def course_index(self):
        index = {}
        for template in self.templates:
            for token in {str(template.pk), course_token(template.name), course_token(course_label(template))}:
                index.setdefault(token, []).append(template)
        return index

    def template(self, token, resort, course_day, start, end):
        templates = self.course_index.get(token, ())
        if not templates:
            if any(hint in token for hint in ADDON_HINTS):
                raise CourseError('unmatched_addon', '這一列像加購、攝影或寫真。若是同單加購，請依「填寫說明」標記並重新預覽。'
                                  '若是正式課程，請填「選項」中的課程或課程 ID，並補日期、人數及程度。')
            candidates = [
                (str(template.pk), {course_token(template.name), course_token(course_label(template))})
                for template in self.templates
                if resort and resort.pk in template_resort_ids(template) and template.is_active
                and not template.shared_class_enabled
            ]
            raise CourseError('course_not_found', '找不到這個課程名稱或代碼，請對照範本「選項」或填課程 ID。'
                              + candidate_hint(token, candidates))
        if resort is None:
            return None
        templates = [template for template in templates if resort.pk in template_resort_ids(template)]
        if not templates:
            raise CourseError('course_not_at_resort', '找到這個課程，但這個雪場未開設。請核對雪場與課程。', TEMPLATE, RESORT)
        templates = [template for template in templates if template.is_active]
        if not templates:
            raise CourseError('course_inactive', '這個雪場的課程尚未啟用，請由行政核對。')
        templates = [template for template in templates if not template.shared_class_enabled]
        if not templates:
            raise CourseError('shared_course', '此課程使用跨訂單湊班，請由行政個別處理')
        if len(templates) > 1 and course_day:
            templates = [template for template in templates if in_course_period(template, course_day)]
            if not templates:
                raise CourseError('course_date_range', '上課日期不在此課程開放期間，請核對日期或課程。', DAY)
        if len(templates) > 1 and (start or end) and (not start or not end or start < end):
            matching = [template for template in templates if matching_windows(template, start, end)]
            if not matching:
                raise session_error(templates)
            templates = matching
        if len(templates) > 1:
            raise CourseError('course_ambiguous', '找到多個符合的課程，請填完整課程名稱或「選項」內的課程 ID。')
        template = templates[0]
        if len(template.name) > Booking._meta.get_field('course_name').max_length or len(
            template.course_type.name
        ) > Booking._meta.get_field('course_type').max_length:
            raise CourseError('course_name_too_long', '課程名稱超過可匯入的長度，請由行政個別處理')
        return template

    def coach(self, value):
        token = identifier(value, 150)
        matches = Coach.objects.filter(client=self.tenant)
        matches = matches.filter(pk=integer(token, 1)) if re.fullmatch(r'[0-9]+', token) else matches.filter(name=token)
        return unique(matches, '找不到此學校的唯一教練，請核對姓名或改填教練 ID')

    def pick_member(self, address):
        # Login identities are global. Prefer the tenant's school membership,
        # and provision local membership for an existing shared login if needed.
        candidates = list(User.objects.filter(email__iexact=address).order_by('pk')[:2])
        if len(candidates) > 1 or (candidates and not candidates[0].is_active):
            raise ValueError('此信箱對應多個帳號或帳號已停用，請先由行政核對會員')
        user = candidates[0] if candidates else None
        if user and ClientMemberProfile.objects.filter(client=self.tenant, user=user).exists():
            return user, 'existing_member'
        return user, 'new_membership' if user else 'new_account'

    def validate(self, key, rows):
        issues = []
        order_fields = {}
        lessons = []
        fees = {}
        payables = []
        price_gaps = []
        addons = []
        first = rows[0].number
        seen_lessons = {}
        order_normalizers = {
            NAME: lambda v: text(v, 100), PHONE: phone, EMAIL: email, CAMPUS: self.campus,
            PAID: lambda v: choice(v, PAID_CHOICES, PAID_ALIASES),
            METHOD: lambda v: choice(v, Payment.PAYMENT_METHOD_CHOICES, METHOD_ALIASES),
            POSTED: day, BANK_LAST_FIVE: bank_last_five, RECEIVED: lambda v: integer(v, 0),
            MARKETING: marketing_source,
        }
        order_aliases = {
            PAID: (PAID_ALIASES, dict(PAID_CHOICES)), METHOD: (METHOD_ALIASES, dict(Payment.PAYMENT_METHOD_CHOICES)),
        }
        for index, row in enumerate(rows):
            values = dict.fromkeys(HEADERS)
            values.update(zip(HEADERS, row.values))
            row_issue = lambda level, code, message, *columns: issue(row.number, key, level, code, message, *columns)
            invalid = {HEADERS[i] for i in row.invalid_cells}
            for field in HEADERS:
                if field in invalid:
                    issues.append(row_issue('error', 'invalid_cell', '請貼上純值並改為一般格式。欄位不可含公式、Excel 錯誤、百分比、控制字元或過長文字。', field))

            if not blank(values[FLAG]) and FLAG not in invalid:
                issues.append(row_issue('error', 'invalid_flag', '正式資料請將「是否範例」留空', FLAG))

            def read(field, normalizer, *, required=False, default=None, warning=None, columns=None):
                if field in invalid:
                    return default
                if blank(values[field]):
                    if required:
                        issues.append(row_issue('error', 'required', '請填寫此欄', field))
                    return default
                try:
                    return normalizer(values[field])
                except ValueError as exc:
                    if warning:
                        code, message = warning
                        issues.append(row_issue('warning', code, message or f'{exc}。此欄留空待後台補。', field))
                    else:
                        issues.append(row_issue('error', 'invalid_value', str(exc), *(columns or (field,))))
                    return default

            contact_differences = []
            campus_differs = False
            for field in ORDER_FIELDS:
                if index and blank(values[field]):
                    continue
                if index and field in CONTACT_FIELDS:
                    if field not in invalid:
                        try:
                            same = order_normalizers[field](values[field]) == order_fields[field]
                        except ValueError:
                            same = False
                        if not same:
                            contact_differences.append(field)
                    continue
                required = not index and (field in REQUIRED_ORDER_FIELDS or (
                    field == POSTED and self.posting_mode == 'required'
                ))
                normalizer = order_normalizers[field]
                if field == MARKETING and not blank(values[field]):
                    value = read(field, normalizer, default='', warning=(
                        'marketing_pending', '行銷統計不明確或超過欄位長度，已留空。請建單後到訂單後台補填。',
                    ))
                else:
                    value = read(field, normalizer, required=required)
                if field == EMAIL and value and value.endswith('.con'):
                    issues.append(row_issue('warning', 'email_domain_con', '信箱網域以 .con 結尾，請確認。系統會用原信箱登入與綁定。', EMAIL))
                if value and field in order_aliases and isinstance(values[field], str):
                    aliases, labels = order_aliases[field]
                    if choice_token(values[field]) in aliases:
                        issues.append(row_issue('warning', 'choice_normalized', f'已整理為「{labels[value]}」，請核對。', field))
                if field == POSTED and value is not None:
                    if self.posting_mode == 'disabled':
                        issues.append(row_issue('error', 'posting_date_disabled', '此學校已停用手動入帳日，請將此欄留空', POSTED))
                    elif value > self.today:
                        issues.append(row_issue('error', 'future_posting_date', '入帳日不得晚於台北時間今天', POSTED))
                if not index:
                    order_fields[field] = value
                elif field == CAMPUS:
                    campus_differs = value is not None and value != order_fields[CAMPUS]
                    if value is None and field not in invalid:
                        issues.append(row_issue('error', 'order_campus_conflict',
                                                f'無法確認本列與首列（第 {first} 列）屬於同一校區。請核對校區或拆單後重傳。', CAMPUS))
                elif value is not None and value != order_fields[field]:
                    issues.append(row_issue(
                        'error', 'order_field_conflict',
                        f'同一張訂單的{field}要一致。第 {row.number} 列和首列（第 {first} 列）不同，後續列可留空。', field,
                    ))
            if contact_differences and all(order_fields[field] is not None for field in (NAME, PHONE, EMAIL)):
                issues.append(row_issue(
                    'warning', 'use_first_contact',
                    f'本列的{"、".join(contact_differences)}與首列（第 {first} 列）不同或無法辨識，已沿用首列。若應分開記錄，請拆單後重傳。',
                    *contact_differences,
                ))
            if not index and order_fields[BANK_LAST_FIVE] and order_fields[METHOD] not in (None, 'TT'):
                issues.append(row_issue('error', 'bank_last_five_method', '後五碼只用於匯款訂單。請核對付款方式或將後五碼留空。', BANK_LAST_FIVE, METHOD))

            note = read(NOTE, lambda v: text(v, 1000))
            lesson_note = read(LESSON_NOTE, lambda v: text(v, 1000))
            if not index:
                order_fields[NOTE] = note

            token = read(TEMPLATE, course_identifier, required=True)
            templates = self.course_index.get(token, ())
            addon = token and addon_marked(note, lesson_note) and (
                all(t.course_type.category.service_type == CourseCategory.SERVICE_TYPE_PHOTO for t in templates)
                if templates else any(hint in token for hint in ADDON_HINTS)
            )
            resort = read(RESORT, lambda v: self.resort(v, order_fields[CAMPUS]), required=not addon)
            if addon:
                scheduling = [field for field in (DAY, START, END, PEOPLE, ABILITY, NAMES, LANGUAGE, COACH, EQUIPMENT)
                              if not blank(values[field])]
                money_fields = [field for field in (FEE, ORIGINAL, DISCOUNT)
                                if not blank(values[field]) and read(field, discount_amount) != 0]
                if not blank(values[DISCOUNT_NOTE]):
                    money_fields.append(DISCOUNT_NOTE)
                if scheduling or money_fields:
                    issues.append(row_issue('error', 'addon_has_details',
                                            '隨單加購列有獨立金額或排課資料，請由行政核對後再處理。',
                                            *scheduling, *money_fields))
                elif campus_differs:
                    issues.append(row_issue('error', 'order_campus_conflict',
                                            f'加購列與首列（第 {first} 列）校區不同，請核對歸屬後重傳。', CAMPUS))
                else:
                    addons.append(Addon(row.number, str(values[TEMPLATE]).strip(), lesson_note or note, resort.pk if resort else None))
                continue

            if index and note and note != order_fields[NOTE] and not lesson_note:
                lesson_note = note
                issues.append(row_issue('warning', 'legacy_lesson_note', '這列的備註已當作堂次備註，整單備註沿用首列。', NOTE, LESSON_NOTE))

            course_day = read(DAY, day)
            start = read(START, minute)
            end = read(END, minute)
            for field, value, canonical in ((DAY, course_day, '%Y-%m-%d'), (START, start, '%H:%M'), (END, end, '%H:%M')):
                if value is not None and isinstance(values[field], str) and values[field].strip() != value.strftime(canonical):
                    issues.append(row_issue('warning', 'time_format_normalized', f'已整理為 {value.strftime(canonical)}，請核對。', field))
            people = read(PEOPLE, lambda v: integer(v, 1))
            abilities = read(ABILITY, lambda v: ability(v, people), columns=(ABILITY, PEOPLE))
            names = read(NAMES, lambda v: learner_names(v, people), default=())
            language = read(LANGUAGE, lambda v: choice(v, Reservation.SINGLE_LANGUAGE_CHOICES, LANGUAGE_ALIASES), default='zh')
            if LANGUAGE not in invalid and isinstance(values[LANGUAGE], str) and choice_token(values[LANGUAGE]) in LANGUAGE_ALIASES:
                issues.append(row_issue('warning', 'choice_normalized',
                                        f'已整理為「{dict(Reservation.SINGLE_LANGUAGE_CHOICES)[language]}」，請核對。', LANGUAGE))
            coach = None
            if COACH not in invalid and isinstance(values[COACH], str) and choice_token(values[COACH]) in PAYMENT_TOKENS:
                issues.append(row_issue('warning', 'coach_pending',
                                        '教練欄填了付款方式，已忽略。這堂會先建單、教練待排，請由行政補排。', COACH))
            else:
                coach = read(COACH, self.coach)
            fee = read(FEE, lambda v: integer(v, 0), required=True)
            fees[row.number] = fee
            original = read(ORIGINAL, lambda v: integer(v, 0))
            discount = 0 if blank(values[DISCOUNT]) and DISCOUNT not in invalid else read(DISCOUNT, discount_amount)
            discount_note = read(DISCOUNT_NOTE, lambda v: text(v, 255), default='')
            equipment_option = read(EQUIPMENT, equipment, warning=('equipment_pending', None))
            payable = None
            if discount is not None:
                if original is None and blank(values[ORIGINAL]) and ORIGINAL not in invalid and fee is not None:
                    original = fee + discount
                    if original > MAX_INT:
                        issues.append(row_issue('error', 'lesson_price_conflict', '推算原價超過整數上限，請核對本堂已付金額與折扣。', ORIGINAL, DISCOUNT, FEE))
                if original is not None:
                    if discount > original:
                        issues.append(row_issue('error', 'lesson_price_conflict', '本堂折扣不得超過原價，請核對這兩欄。', ORIGINAL, DISCOUNT))
                    elif original <= MAX_INT:
                        payable = original - discount
                        if fee is not None and payable != fee:
                            price_gaps.append((row.number, payable, fee))
            payables.append(payable)

            template = None
            unmatched_addon = False
            if token:
                try:
                    template = self.template(token, resort, course_day, start, end)
                except CourseError as exc:
                    unmatched_addon = exc.code == 'unmatched_addon'
                    issues.append(row_issue('error', exc.code, str(exc), *exc.columns))
            if campus_differs:
                if template and resort and order_fields[CAMPUS]:
                    issues.append(row_issue('warning', 'use_first_campus',
                                            f'本列校區與首列（第 {first} 列）不同。雪場與課程適用首列校區，已沿用首列。若應分開排課，請拆單後重傳。', CAMPUS))
                else:
                    issues.append(row_issue('error', 'order_campus_conflict',
                                            f'本列校區與首列（第 {first} 列）不同，雪場或課程無法依首列校區建單。請核對校區或拆單後重傳。',
                                            CAMPUS, RESORT, TEMPLATE))
            for field in (START, END):
                if field in invalid or not blank(values[field]):
                    continue
                windows = matching_windows(template, start, end) if template and (start or end) else []
                if len(windows) == 1:
                    start, end = windows[0]
                    time = start if field == START else end
                    issues.append(row_issue('warning', 'session_time_completed',
                                            f'依唯一啟用時段補上 {time:%H:%M}，請核對開始與結束時間。', field))
                else:
                    issues.append(row_issue('error', 'required', '請填寫此欄並對照「選項」的啟用時段。', field))
            missing = [field for field in (DAY, PEOPLE, ABILITY) if field not in invalid and blank(values[field])]
            if missing and not unmatched_addon:
                if template and template.course_type.category.service_type == CourseCategory.SERVICE_TYPE_PHOTO:
                    issues.append(row_issue('error', 'photo_fields_required', f'這堂攝影課還需填寫{"、".join(missing)}。', *missing))
                else:
                    for field in missing:
                        issues.append(row_issue('error', 'required', f'請填寫本堂的{field}。', field))

            if template:
                issues.extend(self.validate_lesson(template, resort, course_day, start, end, people, abilities, row_issue))
                if not missing and template.course_type.category.service_type == CourseCategory.SERVICE_TYPE_PHOTO:
                    issues.append(row_issue('error', 'standalone_photo',
                                            '獨立攝影課的收款與排課請交行政處理。'
                                            f'若是跟滑雪課同一張單的加購，請在這列「堂次備註」整格只寫「{ADDON_MARKER}」，'
                                            '並把日期、時間、人數、程度、金額留空。', TEMPLATE))
            elif start is not None and end is not None and start >= end:
                issues.append(row_issue('error', 'invalid_time_range', '結束時間須晚於開始時間', START, END))

            if not any(value is None for value in (resort, template, course_day, start, end, people, abilities, fee)):
                slot = Slot(template, course_day, start, end)
                lesson_key = (resort.pk, slot, coach.pk if coach else None)
                labels = seen_lessons.setdefault(lesson_key, set())
                if labels and (not lesson_note or lesson_note in labels):
                    issues.append(row_issue(
                        'error', 'duplicate_lesson',
                        '同一張訂單已有相同雪場、課程和時段的堂次。若是不同組，請在堂次備註填不同組別；若是重複列，請刪除。',
                        RESORT, TEMPLATE, DAY, START, END, COACH, LESSON_NOTE,
                    ))
                labels.add(lesson_note or (order_fields[NOTE] if not index else None))
                lessons.append(Lesson(
                    row.number, resort, slot, people, abilities, names, language, coach, fee, original, discount,
                    discount_note, equipment_option, lesson_note,
                ))

        amount = None if not fees or None in fees.values() else sum(fees.values())
        expected_amount = None if not payables or None in payables else sum(payables)
        reported = order_fields[RECEIVED]
        for addon in addons:
            addon_issue = lambda level, code, message, *columns: issue(addon.row_number, key, level, code, message, *columns)
            if not lessons or (addon.resort_id and not any(lesson.resort.pk == addon.resort_id for lesson in lessons)):
                issues.append(addon_issue('error', 'addon_no_main', '找不到可對應的同單主課。請核對單號與雪場後重傳。', KEY, RESORT, TEMPLATE))
            elif reported is None or amount is None or reported != amount:
                issues.append(addon_issue('error', 'addon_total_unverified', f'請核對首列（第 {first} 列）的已收款金額與主課加總，再重新上傳。', RECEIVED, FEE))
            elif not any(item['level'] == 'error' for item in issues):
                issues.append(addon_issue('warning', 'addon_pending', '主課可先匯入。這筆隨單加購會在堂次與訂單備註留痕，待後台補記。', TEMPLATE, LESSON_NOTE))

        totals = {
            'amount': amount, 'reported_amount': reported,
            'amount_difference': amount - reported if amount is not None and reported is not None else None,
            'lesson_amounts': [{'row_number': number, 'amount': fee} for number, fee in fees.items()],
        }
        if amount is not None:
            if not 0 < amount <= MAX_INT:
                issues.append(issue(first, key, 'error', 'invalid_total', '整單實收須大於 0 且在可記錄的整數範圍內', FEE))
            if reported is not None and reported != amount:
                issues.append(issue(
                    first, key, 'error', 'received_total_mismatch',
                    f'本單各堂加總為 {amount:,} 元，和已收款金額 {reported:,} 元不同。請按實際收款分攤到各堂。', RECEIVED, FEE,
                ))
            elif reported is None and len(fees) > 1 and amount > 0 and len(set(fees.values())) == 1:
                issues.append(issue(
                    first, key, 'warning', 'repeated_lesson_amount',
                    f'本單各堂填了相同金額，加總為 {amount:,} 元。請確認是否把整單金額複製到每堂，若是請按實際收款分攤。', FEE,
                ))
        if price_gaps:
            for number, payable, fee in price_gaps:
                direction = '少收' if payable > fee else '多收'
                issues.append(issue(
                    number, key, 'warning', 'lesson_price_gap',
                    f'本堂應收 {payable:,} 元，已付 {fee:,} 元，{direction} {abs(payable - fee):,} 元。'
                    '整單有差額時，匯入會建立待後台結清的紀錄。', ORIGINAL, DISCOUNT, FEE,
                ))
            if reported is None:
                issues.append(issue(first, key, 'error', 'price_gap_receipt_required',
                                    '本單有堂次差額，請在首列填寫整單實際已收款金額，須等於各堂已付金額加總。', RECEIVED, FEE))
            if expected_amount is not None and not 0 <= expected_amount <= MAX_INT:
                issues.append(issue(first, key, 'error', 'invalid_expected_total',
                                    '整單應收超過可記錄的整數範圍，請核對各堂原價與折扣。', ORIGINAL, DISCOUNT))
            if expected_amount is not None and amount is not None:
                balance = expected_amount - amount
                totals['price_gap'] = {'expected_amount': expected_amount, 'balance_amount': balance}
                if reported == amount and not any(item['level'] == 'error' for item in issues):
                    direction = f'待補款 {balance:,} 元' if balance > 0 else f'待退款 {-balance:,} 元'
                    message = f'{direction}，匯入後請到後台結清。' if balance else '各堂差額互抵，整單差額 0 元，匯入後無待收退差額。'
                    issues.append(issue(
                        first, key, 'warning', 'order_price_gap',
                        f'整單應收 {expected_amount:,} 元，實收 {amount:,} 元。{message}', ORIGINAL, DISCOUNT, FEE, RECEIVED,
                    ))
        if any(item['level'] == 'error' for item in issues):
            return None, issues, totals
        try:
            user, member_code = self.pick_member(order_fields[EMAIL])
        except ValueError as exc:
            issues.append(issue(first, key, 'error', 'member_conflict', str(exc), EMAIL))
            return None, issues, totals
        return ImportOrder(key, first, order_fields, lessons, user, member_code, tuple(addons), expected_amount), issues, totals

    def validate_lesson(self, template, resort, course_day, start, end, people, abilities, row_issue):
        if course_day and not in_course_period(template, course_day):
            yield row_issue('error', 'course_date_range', '上課日期不在此課程開放期間，請核對日期或課程。', DAY)
        if (
            (template.booking_open_date and self.today < template.booking_open_date)
            or (template.booking_close_date and self.today > template.booking_close_date)
        ):
            yield row_issue('warning', 'booking_window', '目前不在這個課程開放報名的期間。若是補登已付款的訂單，可以繼續匯入。', TEMPLATE, DAY)
        if start is not None and end is not None:
            if start >= end:
                yield row_issue('error', 'invalid_time_range', '結束時間須晚於開始時間', START, END)
            elif (start, end) not in active_windows(template):
                error = session_error([template])
                yield row_issue('error', error.code, str(error), *error.columns)
        if people is not None:
            price = CoursePricing.objects.filter(templates=template, resort=resort, is_active=True).first()
            maximum = price.max_capacity if price else template.max_capacity or 6
            if not template.minimum_group_size <= people <= maximum:
                yield row_issue('error', 'people_limit', f'此堂人數須介於 {template.minimum_group_size} 至 {maximum} 人', PEOPLE)
        minimum = ABILITY_RANK.get(template.minimum_student_level, 0)
        if abilities and any(ABILITY_RANK[level] < minimum for level in abilities):
            yield row_issue('error', 'ability_limit', '有學員程度低於此模板的最低等級', ABILITY)
