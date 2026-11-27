"""Validate spreadsheet rows against the import contract and the tenant's catalog."""

import datetime as dt
import re
from dataclasses import dataclass
from functools import cached_property
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.utils import timezone

from Client.models import ClientMemberProfile
from Client.tenant_settings import manual_payment_posting_date_mode
from Coach.models import Coach
from Coursekit.models import CoursePricing, CourseTemplate
from Resorts.models import Campus, Resorts
from booking.capacity import Slot
from booking.models import ABILITY_LEVEL_CHOICES, Booking, Payment, Reservation

from .parser import HEADERS, blank

FLAG, KEY, NAME, PHONE, EMAIL, CAMPUS, RESORT, TEMPLATE, DAY, START, END, PEOPLE, ABILITY, NAMES, LANGUAGE, COACH, FEE, PAID, METHOD, POSTED, NOTE = HEADERS
ORDER_FIELDS = (NAME, PHONE, EMAIL, CAMPUS, PAID, METHOD, POSTED, NOTE)
REQUIRED_ORDER_FIELDS = (NAME, PHONE, EMAIL, CAMPUS, PAID, METHOD)
LESSON_FIELDS = (RESORT, TEMPLATE, DAY, START, END, PEOPLE, ABILITY, NAMES, LANGUAGE, COACH, FEE)
MAX_INT = 2_147_483_647
ABILITY_RANK = {key: rank for rank, (key, _) in enumerate(ABILITY_LEVEL_CHOICES)}
TAIPEI = ZoneInfo('Asia/Taipei')


def redact(value):
    value = re.sub(r'[\w.+-]+@[\w.-]+', '［信箱已遮罩］', value)
    return re.sub(r'(?<!\w)\+?\d(?:[ -]?\d){7,14}(?!\w)', '［電話已遮罩］', value)


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
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(integer(value, 0))
    return text(value, limit)


def integer(value, minimum):
    if isinstance(value, str) and re.fullmatch(r'[0-9]{1,10}', value.strip()):
        value = int(value.strip())
    if type(value) is float and value.is_integer():
        value = int(value)
    if type(value) is not int or not minimum <= value <= MAX_INT:
        raise ValueError(f'請填 {minimum} 至 {MAX_INT} 的整數')
    return value


def phone(value):
    value = re.sub(r'[ -]', '', text(value, 40))
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
    if isinstance(value, str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value.strip()):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise ValueError('請填有效日期，格式為 YYYY-MM-DD')


def minute(value):
    if type(value) is dt.time and not (value.second or value.microsecond):
        return value
    if isinstance(value, str) and re.fullmatch(r'[0-9]{2}:[0-9]{2}', value.strip()):
        try:
            return dt.time.fromisoformat(value.strip())
        except ValueError:
            pass
    raise ValueError('請填有效時間，格式為 HH:MM，以整分鐘填寫')


def choice(value, choices):
    token = text(value, 40)
    for key, label in choices:
        if token in (key, label):
            return key
    raise ValueError('請填寫範本「選項」中的有效代碼或名稱')


def ability(value, people):
    choices = ABILITY_LEVEL_CHOICES
    value = text(value, 120).replace('：', ':')
    if ':' not in value and '、' not in value:
        return {choice(value, choices): people}
    counts = {}
    for item in value.split('、'):
        name, separator, count = item.partition(':')
        if not separator:
            raise ValueError('多個程度請填「等級 0:1、等級 1:1」格式')
        level = choice(name, choices)
        if level in counts:
            raise ValueError('學員程度不得重複')
        counts[level] = integer(count, 1)
    if sum(counts.values()) != people:
        raise ValueError('各程度人數合計須等於本堂學員人數')
    return counts


def learner_names(value, people):
    names = tuple(text(name, 120) for name in text(value, 2000).split('、'))
    if not all(names) or len(names) != people:
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

    @property
    def highest_level(self):
        return max(self.abilities, key=ABILITY_RANK.__getitem__)


@dataclass(frozen=True)
class ImportOrder:
    key: str
    first_row: int
    fields: dict
    lessons: list
    user: User | None
    member_code: str

    @property
    def amount(self):
        return sum(lesson.fee for lesson in self.lessons)

    @property
    def contact(self):
        return {'name': self.fields[NAME], 'phone': self.fields[PHONE], 'email': self.fields[EMAIL]}


def unique(matches, message):
    matches = list(matches[:2])
    if len(matches) != 1:
        raise ValueError(message)
    return matches[0]


class Validator:
    def __init__(self, tenant):
        self.tenant = tenant
        self.today = timezone.localdate(timezone=TAIPEI)

    @cached_property
    def posting_mode(self):
        return manual_payment_posting_date_mode(self.tenant)

    def campus(self, value):
        token = text(value, 100)
        return unique(Campus.objects.filter(
            Q(code=token) | Q(name=token), client=self.tenant, is_active=True,
        ), '找不到唯一的啟用校區，請核對校區名稱或代碼')

    def resort(self, value, campus):
        token = text(value, 100)
        resorts = Resorts.objects.filter(Q(name=token) | Q(display_name=token), client=self.tenant)
        if campus:
            resorts = resorts.filter(campuses=campus)
        return unique(resorts, '找不到此校區可使用的唯一雪場，請核對名稱')

    def template(self, value, resort):
        token = identifier(value, 302)
        templates = CourseTemplate.objects.filter(course_type__category__client=self.tenant, is_active=True)
        if resort:
            templates = templates.filter(resorts=resort)
        if re.fullmatch(r'[0-9]+', token):
            templates = templates.filter(pk=integer(token, 1))
        elif token.count('／') == 2:
            category, kind, name = token.split('／')
            templates = templates.filter(course_type__category__name=category, course_type__name=kind, name=name)
        else:
            templates = templates.filter(name=token)
        template = unique(templates.select_related('course_type__category'), '找不到此雪場可用的唯一課程模板，請核對名稱或改填模板 ID')
        if template.shared_class_enabled:
            raise ValueError('此課程使用跨訂單湊班，請由行政個別處理')
        if len(template.name) > Booking._meta.get_field('course_name').max_length or len(
            template.course_type.name
        ) > Booking._meta.get_field('course_type').max_length:
            raise ValueError('課程名稱超過堂次欄位長度，請由行政個別處理')
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
        seen_lessons = set()
        for index, row in enumerate(rows):
            values = dict(zip(HEADERS, row.values))
            row_issue = lambda level, code, message, *columns: issue(row.number, key, level, code, message, *columns)
            invalid = {HEADERS[i] for i in row.invalid_cells}
            for field in HEADERS:
                if field in invalid:
                    issues.append(row_issue('error', 'invalid_cell', '此欄含公式、Excel 錯誤、控制字元或過長文字', field))

            if not blank(values[FLAG]) and FLAG not in invalid:
                issues.append(row_issue('error', 'invalid_flag', '正式資料請將「是否範例」留空', FLAG))

            def read(field, normalize, *, required=False, default=None):
                if field in invalid:
                    return default
                if blank(values[field]):
                    if required:
                        issues.append(row_issue('error', 'required', '請填寫此欄', field))
                    return default
                try:
                    return normalize(values[field])
                except ValueError as exc:
                    issues.append(row_issue('error', 'invalid_value', str(exc), field))
                    return default

            order_normalizers = {
                NAME: lambda v: text(v, 100), PHONE: phone, EMAIL: email, CAMPUS: self.campus,
                PAID: lambda v: choice(v, (('paid', '已付款'),)),
                METHOD: lambda v: choice(v, Payment.PAYMENT_METHOD_CHOICES),
                POSTED: day, NOTE: lambda v: text(v, 1000),
            }
            for field in ORDER_FIELDS:
                if index and blank(values[field]):
                    continue
                required = not index and (field in REQUIRED_ORDER_FIELDS or (
                    field == POSTED and self.posting_mode == 'required'
                ))
                value = read(field, order_normalizers[field], required=required)
                if field == POSTED and value is not None:
                    if self.posting_mode == 'disabled':
                        issues.append(row_issue('error', 'posting_date_disabled', '此學校已停用手動入帳日，請將此欄留空', POSTED))
                    elif value > self.today:
                        issues.append(row_issue('error', 'future_posting_date', '入帳日不得晚於台北時間今天', POSTED))
                if not index:
                    order_fields[field] = value
                elif value is not None and value != order_fields[field]:
                    issues.append(row_issue('error', 'order_field_conflict', '同單欄位須在首列填寫，後續列只能留空或填相同值', field))

            resort = read(RESORT, lambda v: self.resort(v, order_fields[CAMPUS]), required=True)
            template = read(TEMPLATE, lambda v: self.template(v, resort), required=True)
            course_day = read(DAY, day, required=True)
            start = read(START, minute, required=True)
            end = read(END, minute, required=True)
            people = read(PEOPLE, lambda v: integer(v, 1), required=True)
            abilities = read(ABILITY, lambda v: ability(v, people), required=True)
            names = read(NAMES, lambda v: learner_names(v, people), default=())
            language = read(LANGUAGE, lambda v: choice(v, Reservation.SINGLE_LANGUAGE_CHOICES), default='zh')
            coach = read(COACH, self.coach)
            fee = read(FEE, lambda v: integer(v, 0), required=True)

            if template:
                issues.extend(self.validate_lesson(template, resort, course_day, start, end, people, abilities, row_issue))
            elif start is not None and end is not None and start >= end:
                issues.append(row_issue('error', 'invalid_time_range', '結束時間須晚於開始時間', START, END))

            if not any(value is None for value in (resort, template, course_day, start, end, people, abilities, fee)):
                slot = Slot(template, course_day, start, end)
                lesson_key = (resort.pk, slot, coach.pk if coach else None)
                if lesson_key in seen_lessons:
                    issues.append(row_issue('error', 'duplicate_lesson', '同一張訂單有重複堂次，請核對', RESORT, TEMPLATE, DAY, START, END, COACH))
                seen_lessons.add(lesson_key)
                lessons.append(Lesson(row.number, resort, slot, people, abilities, names, language, coach, fee))

        if issues:
            return None, issues
        first = rows[0].number
        if not 0 < sum(lesson.fee for lesson in lessons) <= MAX_INT:
            return None, [issue(first, key, 'error', 'invalid_total', '整單實收須大於 0 且在可記錄的整數範圍內', FEE)]
        try:
            user, member_code = self.pick_member(order_fields[EMAIL])
        except ValueError as exc:
            return None, [issue(first, key, 'error', 'member_conflict', str(exc), EMAIL)]
        return ImportOrder(key, first, order_fields, lessons, user, member_code), []

    def validate_lesson(self, template, resort, course_day, start, end, people, abilities, row_issue):
        if course_day and (
            (template.course_start_date and course_day < template.course_start_date)
            or (template.course_end_date and course_day > template.course_end_date)
        ):
            yield row_issue('error', 'course_date_range', '上課日期超出課程開放期間', DAY)
        if (
            (template.booking_open_date and self.today < template.booking_open_date)
            or (template.booking_close_date and self.today > template.booking_close_date)
        ):
            yield row_issue('error', 'booking_window', '目前日期超出此課程報名窗口，請由行政核對', TEMPLATE, DAY)
        if start is not None and end is not None:
            if start >= end:
                yield row_issue('error', 'invalid_time_range', '結束時間須晚於開始時間', START, END)
            elif not template.sessions.filter(is_active=True, start_time=start, end_time=end).exists():
                yield row_issue('error', 'unknown_session', '起訖時間須符合此模板同一個啟用時段', START, END)
        if people is not None:
            price = CoursePricing.objects.filter(templates=template, resort=resort, is_active=True).first()
            maximum = price.max_capacity if price else template.max_capacity or 6
            if not template.minimum_group_size <= people <= maximum:
                yield row_issue('error', 'people_limit', f'此堂人數須介於 {template.minimum_group_size} 至 {maximum} 人', PEOPLE)
        minimum = ABILITY_RANK.get(template.minimum_student_level, 0)
        if abilities and any(ABILITY_RANK[level] < minimum for level in abilities):
            yield row_issue('error', 'ability_limit', '有學員程度低於此模板的最低等級', ABILITY)
