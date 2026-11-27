import csv
import hashlib
import io
import json
from datetime import date, datetime, time, timedelta
from urllib.parse import parse_qs, urlsplit
from itertools import repeat
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.utils.datetime import to_excel
from rest_framework.test import APIClient

from Client.models import Client, ClientMemberProfile, ModuleInfo, ModuleSetting
from Coach.models import Coach, CoachCourseLevel, CoachResort
from Control.models import TenantStaffMembership
from Coursekit.models import CourseCategory, CoursePricing, CourseSession, CourseTemplate, CourseType
from Resorts.models import Campus, Resorts
from booking.capacity import Slot
from booking.models import (
    BookingClosure, NotificationDelivery, NotificationTemplate, OrderImportBatch, OrderLoyalty, Payment, ReservationGroup,
    StaffBookingLink,
)
from booking.order_import.parser import HEADERS, LEGACY_HEADERS, MAX_BYTES, MAX_ROWS, SHEET_NAME
from booking.order_import.service import batch_cipher, json_bytes
from booking.order_import.template import TEMPLATE_PATH
from booking.order_import.validation import (
    ABILITY, BANK_LAST_FIVE, CAMPUS, COACH, DAY, DISCOUNT, DISCOUNT_NOTE, EMAIL, END, EQUIPMENT, FEE, FLAG, KEY,
    LANGUAGE, LESSON_NOTE, MARKETING, METHOD, NAME, NAMES, NOTE, ORIGINAL, PAID, PEOPLE, PHONE, POSTED, RECEIVED,
    RESORT, START, TEMPLATE,
)
from booking.participant_invitations import issue_invitation
from booking.staff_link_holds import create_holds


def xlsx(rows, *, header=HEADERS):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET_NAME
    sheet.append(header)
    sheet.append(['按範本跳過第 2 列'])
    for row in rows:
        sheet.append([row.get(column) for column in header] if isinstance(row, dict) else row)
    binary = io.BytesIO()
    workbook.save(binary)
    return binary.getvalue()


class OrderImportTests(TestCase):
    url = '/api/admin/snowland/order-import/'

    def setUp(self):
        self.tenant = Client.objects.create(name='測試學校', internal_code='snowland')
        self.resort = Resorts.objects.create(client=self.tenant, name='snow', display_name='測試雪場')
        self.campus = Campus.objects.create(client=self.tenant, name='測試校區', code='jp')
        self.campus.resorts.add(self.resort)
        category = CourseCategory.objects.create(client=self.tenant, name='單板')
        self.kind = CourseType.objects.create(category=category, name='私人課')
        self.template = CourseTemplate.objects.create(course_type=self.kind, name='上午', duration_hours=3, max_capacity=1)
        self.template.resorts.add(self.resort)
        self.session = CourseSession.objects.create(template=self.template, start_time=time(9), end_time=time(12))
        price = CoursePricing.objects.create(
            resort=self.resort, base_price_off_peak=1000, peak_season_surcharge=0, additional_person_fee=500,
            max_capacity=3,
        )
        price.templates.add(self.template)
        self.day = date.today() + timedelta(days=15)
        self.actor, self.hq = self.client_for('import-hq', 'hq_admin')

    def client_for(self, username, role, *, tenant=None, grants=None, all_campuses=None):
        user = User.objects.create_user(username)
        membership = TenantStaffMembership.objects.create(
            user=user, client=tenant or self.tenant, is_manager=True, role=role,
            all_campuses=(role == 'hq_admin') if all_campuses is None else all_campuses, admin_permissions=grants,
        )
        if tenant is None:
            membership.campuses.add(self.campus)
        api = APIClient()
        api.force_authenticate(user)
        return user, api

    def row(self, **changes):
        return {
            KEY: '0001', NAME: '買家姓名', PHONE: '0912-345-678', EMAIL: 'import@example.com',
            CAMPUS: 'jp', RESORT: 'snow', TEMPLATE: '單板／私人課／上午', DAY: self.day,
            START: time(9), END: time(12), PEOPLE: 2, ABILITY: '等級 0:1、等級 1：1',
            NAMES: '學員一、學員二', FEE: 1000, PAID: '已付款', METHOD: '匯款', NOTE: '行政備註',
            **changes,
        }

    def preview_response(self, content, filename='orders.xlsx', *, api=None, url=None):
        return (api or self.hq).post((url or self.url) + 'preview/', {
            'file': SimpleUploadedFile(filename, content),
        }, format='multipart')

    def preview(self, *rows, content=None, filename='orders.xlsx'):
        result = self.preview_response(content or xlsx(rows), filename)
        self.assertEqual(result.status_code, 200, result.data)
        return result.data['data']

    def commit_response(self, preview, *, api=None, url=None, **changes):
        return (api or self.hq).post((url or self.url) + 'commit/', {
            'batch_id': preview['batch_id'], 'confirm': True, **changes,
        }, format='json')

    def commit(self, preview, **changes):
        response = self.commit_response(preview, **changes)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['data']

    def flags(self, **settings):
        module, _ = ModuleInfo.objects.get_or_create(module_sid='booking', defaults={'module_name': '訂課'})
        row, _ = ModuleSetting.objects.update_or_create(client=self.tenant, module=module, defaults={'settings': settings})
        return row

    def test_repository_template_matches_exact_header_and_skips_two_examples(self):
        content = TEMPLATE_PATH.read_bytes()
        workbook = load_workbook(TEMPLATE_PATH, read_only=True)
        self.assertEqual(tuple(cell.value for cell in workbook[SHEET_NAME][1]), HEADERS)
        workbook.close()
        preview = self.preview(content=content)
        self.assertEqual(preview['row_results'], [])
        self.assertEqual(preview['summary']['errors'], 0)
        self.assertEqual(preview['summary']['skipped_examples'], 2)
        self.assertEqual(preview['file_sha256'], hashlib.sha256(content).hexdigest())

    def test_template_download_preserves_main_sheet_and_uses_tenant_catalog(self):
        other = Client.objects.create(name='其他學校', internal_code='other')
        Campus.objects.create(client=other, name='外校校區', code='other')
        response = self.hq.get(self.url + 'template/')
        self.assertEqual(response.status_code, 200)
        distributed = load_workbook(io.BytesIO(b''.join(response.streaming_content)))
        locked = load_workbook(TEMPLATE_PATH)
        self.assertEqual(list(distributed[SHEET_NAME].values), list(locked[SHEET_NAME].values))
        self.assertIn('請勿填姓名、電話或 Email。', distributed['說明']['D14'].value)
        options = list(distributed['選項'].values)
        self.assertIn(('校區', 'jp', '測試校區', None), options)
        self.assertIn(('時段', '09:00–12:00', '單板／私人課／上午', '測試雪場'), options)
        self.assertIn(('協助狀況', 'assistDuringCourse', '課程時間內協助', None), options)
        self.assertNotIn('外校校區', str(options))

    def test_native_cells_merge_order_preserve_phone_and_create_audited_paid_order(self):
        native_day = datetime.combine(self.day, time())
        result = self.preview(self.row(**{DAY: native_day, POSTED: date.today()}), self.row(**{
            DAY: self.day + timedelta(days=1), NAME: None, PHONE: '0912345678', EMAIL: 'IMPORT@example.com',
            CAMPUS: '測試校區', PAID: None, METHOD: None, NOTE: None, FEE: 1500,
        }))
        self.assertEqual(result['summary']['errors'], 0, result)
        self.assertEqual(result['summary']['orders'], 1)
        self.assertEqual(result['order_results'][0]['member']['message_zh'], '將建立會員帳號')
        self.assertFalse(ReservationGroup.objects.exists())
        self.assertFalse(User.objects.filter(email='import@example.com').exists())
        batch = OrderImportBatch.objects.get(pk=result['batch_id'])
        self.assertNotIn(b'import@example.com', bytes(batch.staged_input))
        self.assertNotIn('0912345678', json.dumps(batch.row_results))
        before_mail = len(mail.outbox) if hasattr(mail, 'outbox') else 0
        committed = self.commit(result)
        self.assertEqual(committed['summary']['created'], 1, committed)
        group = ReservationGroup.objects.get()
        payment = Payment.objects.get()
        self.assertEqual(group.booking_contact['phone'], '0912345678')
        self.assertEqual(group.marketing_source, '內部導入')
        self.assertFalse(group.is_test)
        self.assertFalse(group.user.has_usable_password())
        self.assertEqual(group.user, payment.user)
        self.assertTrue(ClientMemberProfile.objects.filter(client=self.tenant, user=group.user).exists())
        self.assertEqual(payment.DataJSON['source_order_number'], '0001')
        self.assertEqual(payment.DataJSON['import_batch_id'], batch.pk)
        self.assertEqual((payment.status, payment.payment_method, payment.bank_posted_date), ('paid', 'TT', date.today()))
        self.assertEqual(group.currency_snapshot['base_amount'], 2500)
        revision = group.revisions.get()
        self.assertEqual((revision.change_type, revision.created_by, revision.reason), ('create', self.actor, '內部導入：行政備註'))
        self.assertEqual(revision.snapshot['import_batch_id'], batch.pk)
        for reservation in group.reservations.order_by('pk'):
            self.assertEqual(reservation.status, 'manual_assignment_needed')
            self.assertEqual(reservation.ability_level_counts, {'no_exp': 1, 'level1': 1})
            self.assertEqual(reservation.max_ability_level, 'level1')
            booking = reservation.bookings.get()
            self.assertFalse(booking.is_scheduled)
            self.assertEqual(booking.course_template, self.template)
            self.assertEqual(booking.fee_snapshot, {'coach': 0, 'course': reservation.course_fee})
            members = list(reservation.members.order_by('pk'))
            self.assertEqual([m.insurance_data['full_name'] for m in members], ['學員一', '學員二'])
            self.assertTrue(all(m.age_range == '' for m in members))
            self.assertIsNotNone(issue_invitation(self.tenant, group.user, members[-1].pk))
        self.assertEqual(len(getattr(mail, 'outbox', [])), before_mail)
        self.assertFalse(NotificationDelivery.objects.exists())
        self.assertFalse(OrderLoyalty.objects.exists())
        batch.refresh_from_db()
        self.assertIsNone(batch.staged_input)
        self.assertEqual(batch.committed_at is not None, True)
        self.assertEqual(self.commit(result)['commit_results'], committed['commit_results'])

    def test_validation_reports_each_bad_field_and_returns_mixed_commit(self):
        invalid = self.row(**{
            KEY: 'invalid', FLAG: '任意值', NAME: '甲' * 101, PHONE: 912345678, EMAIL: 'bad',
            CAMPUS: '不存在', RESORT: '不存在', TEMPLATE: '2026-02-30 早課', DAY: '2026-02-30',
            START: time(9, 0, 1), END: '晚點', PEOPLE: True, ABILITY: '等級 0:0',
            NAMES: '甲、', LANGUAGE: '紐約語', COACH: 987, FEE: -1, PAID: '未付款',
            METHOD: '未知', POSTED: '2026-02-30', NOTE: '甲' * 2001,
        })
        preview = self.preview(invalid, self.row())
        columns = {col for item in preview['row_results'] if item['level'] == 'error' for col in item['columns']}
        self.assertEqual(columns, set(LEGACY_HEADERS) - {KEY})
        result = self.commit(preview)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual([item['status'] for item in result['commit_results']], ['failed', 'created'])

    def test_repeated_order_fields_and_lesson_conflicts(self):
        preview = self.preview(self.row(), self.row(**{NAME: '不同姓名', POSTED: date.today()}))
        issues = preview['order_results'][0]['issues']
        errors = [item for item in issues if item['level'] == 'error']
        self.assertEqual({item['code'] for item in errors}, {'order_field_conflict', 'duplicate_lesson'})
        self.assertTrue(all(item['row_number'] == 4 for item in errors))
        self.assertEqual(self.commit(preview)['status'], 'failed')
        self.assertFalse(ReservationGroup.objects.exists())

    def test_old_headers_float_key_and_legacy_lesson_note(self):
        row = self.row(**{KEY: 3123456789.0, POSTED: to_excel(date.today())})
        second = self.row(**{
            KEY: 3123456789, DAY: to_excel(self.day + timedelta(days=1)), NOTE: '第二堂',
            PHONE: '０９１２　３４５－６７８',
        })
        content = io.BytesIO()
        with ZipFile(io.BytesIO(xlsx([row, second], header=LEGACY_HEADERS))) as source, ZipFile(content, 'w') as target:
            for entry in source.namelist():
                value = source.read(entry)
                if entry == 'xl/worksheets/sheet1.xml':
                    # openpyxl writes whole floats as integers. Excel can store an explicit decimal.
                    value = value.replace(b'<v>3123456789</v>', b'<v>3123456789.0</v>', 1)
                target.writestr(entry, value)
        preview = self.preview(content=content.getvalue())
        self.assertEqual(preview['summary']['committable'], 1)
        self.assertEqual(preview['order_results'][0]['amount'], 2000)
        self.assertEqual(
            {item['code'] for item in preview['row_results']}, {'legacy_lesson_note', 'repeated_lesson_amount'},
        )
        # Reproduce a cached preview written before the appended columns existed.
        batch = OrderImportBatch.objects.get(pk=preview['batch_id'])
        key, staged = json.loads(batch_cipher().decrypt(bytes(batch.staged_input)))[0]
        self.assertEqual(key, '3123456789')
        batch.staged_input = batch_cipher().encrypt(json_bytes([
            [key, [[number, values[:len(LEGACY_HEADERS)]] for number, values in staged]],
        ]))
        batch.save(update_fields=['staged_input'])
        self.assertEqual(self.commit(preview)['summary']['created'], 1)
        payment = Payment.objects.get()
        self.assertEqual(payment.bank_posted_date, date.today())
        group = payment.reservation_group
        booking = group.reservations.order_by('pk').last().bookings.get()
        self.assertEqual(payment.DataJSON['import_lesson_notes'], {str(booking.pk): '第二堂'})
        self.assertEqual(group.revisions.get().reason, '內部導入：行政備註')

    def test_partial_optional_headers_are_mapped_by_name_and_have_fixed_order(self):
        first = self.row(**{RECEIVED: 1000, MARKETING: '虛構來源'})
        header = LEGACY_HEADERS + (RECEIVED, MARKETING)
        preview = self.preview(content=xlsx([first], header=header))
        self.assertEqual(self.commit(preview)['summary']['created'], 1)
        self.assertEqual(ReservationGroup.objects.get().marketing_source, '虛構來源')
        for wrong in ((MARKETING, RECEIVED), (RECEIVED, RECEIVED), ('未知欄位',)):
            with self.subTest(wrong=wrong):
                response = self.preview_response(xlsx([first], header=LEGACY_HEADERS + wrong))
                self.assertEqual(response.data['code'], 'invalid_header')

    def test_same_slot_allows_separate_group_labels(self):
        first = self.row(**{NOTE: '第一組', RECEIVED: 2500})
        second = self.row(**{NOTE: '第二組', FEE: 1500})
        preview = self.preview(content=xlsx([first, second], header=LEGACY_HEADERS))
        self.assertEqual(preview['summary']['errors'], 0)
        self.assertEqual(self.commit(preview, allow_overbook=True, overbook_reason='已確認兩組皆收款')['summary']['created'], 1)
        self.assertEqual(ReservationGroup.objects.get().reservations.count(), 2)
        repeating = self.preview(first, second, {**second})
        self.assertIn('duplicate_lesson', [item['code'] for item in repeating['row_results'] if item['row_number'] == 5])

    def test_optional_columns_create_consistent_paid_order(self):
        first = self.row(**{
            LESSON_NOTE: '上午組', EQUIPMENT: '課程時間內協助', BANK_LAST_FIVE: 123.0,
            ORIGINAL: 1200, DISCOUNT: '-200', DISCOUNT_NOTE: '虛構折扣', RECEIVED: 2100, MARKETING: 'Google搜尋',
        })
        second = self.row(**{
            DAY: self.day + timedelta(days=1), FEE: 1100, DISCOUNT: -100, NOTE: '舊標籤', LESSON_NOTE: '下午組',
        })
        preview = self.preview(first, second)
        self.assertEqual(preview['summary']['errors'], 0)
        self.assertEqual(self.commit(preview)['summary']['created'], 1)
        payment = Payment.objects.get()
        group = payment.reservation_group
        self.assertEqual((group.marketing_source, group.marketing_source_override), ('Google搜尋', None))
        self.assertEqual((payment.bank_account, payment.DataJSON['amount']), ('00123', 2100))
        self.assertEqual(payment.DataJSON['import_source'], '內部導入')
        self.assertEqual(group.currency_snapshot['base_amount'], 2100)
        first_reservation, second_reservation = group.reservations.order_by('pk')
        self.assertEqual(
            (first_reservation.course_fee, first_reservation.discount_amount, first_reservation.payment_amount),
            (1200, 200, 1000),
        )
        self.assertEqual((first_reservation.equipment, first_reservation.need_equipment), ('assistDuringCourse', True))
        self.assertEqual(first_reservation.discount_name, '虛構折扣')
        self.assertEqual((second_reservation.course_fee, second_reservation.payment_amount), (1200, 1100))
        self.assertEqual(payment.DataJSON['import_lesson_notes'], {
            str(first_reservation.bookings.get().pk): '上午組', str(second_reservation.bookings.get().pk): '下午組',
        })
        detail = self.hq.get(f'/api/admin/snowland/orders/{group.pk}/')
        self.assertEqual(detail.data['data']['import_lesson_notes'], payment.DataJSON['import_lesson_notes'])
        repeated = self.preview(first, second)
        self.assertEqual(repeated['order_results'][0]['status'], 'skipped')
        first[DISCOUNT_NOTE] = '另一種折扣'
        self.assertEqual(self.preview(first, second)['order_results'][0]['code'], 'source_order_conflict')

    def test_price_checks_and_warnings_have_preview_amounts(self):
        bad = self.preview(self.row(**{RECEIVED: 1000, ORIGINAL: 1100, DISCOUNT: -200}), self.row(**{
            DAY: self.day + timedelta(days=1),
        }))
        self.assertEqual(bad['order_results'][0]['amount'], 2000)
        self.assertEqual(bad['summary']['committable'], 0)
        self.assertEqual({item['code'] for item in bad['row_results'] if item['level'] == 'error'}, {
            'lesson_price_conflict', 'received_total_mismatch',
        })
        good = self.preview(self.row(**{EMAIL: 'fake@example.con', RECEIVED: 2000}), self.row(**{
            EMAIL: None, DAY: self.day + timedelta(days=1),
        }))
        self.assertEqual(good['summary']['committable'], 1)
        self.assertEqual([item['code'] for item in good['row_results'] if item['level'] == 'warning'], ['email_domain_con'])
        self.assertEqual(self.commit(good)['summary']['created'], 1)

    def test_cash_coach_is_rejected_before_lookup_and_conflicts_reference_first_row(self):
        Coach.objects.create(client=self.tenant, name='Cash')
        Campus.objects.create(client=self.tenant, name='另一校區', code='other')
        preview = self.preview(self.row(), self.row(**{
            COACH: 'Ｃａｓｈ', CAMPUS: 'other', PHONE: '0900-000-000', DAY: self.day + timedelta(days=1),
        }))
        errors = [item for item in preview['row_results'] if item['level'] == 'error']
        self.assertIn('付款方式', next(item for item in errors if item['columns'] == [COACH])['message_zh'])
        self.assertEqual({item['columns'][0] for item in errors}, {COACH, PHONE, CAMPUS})
        for item in errors:
            if item['code'] == 'order_field_conflict':
                self.assertIn('第 4 列和首列（第 3 列）不同', item['message_zh'])

    def test_course_matching_uses_resort_pricing_and_distinguishes_catalog_problems(self):
        self.template.resorts.clear()
        self.assertEqual(self.preview(self.row(**{TEMPLATE: '  單板 / 私人課  ／  上午 '}))['summary']['errors'], 0)
        response = self.hq.get(self.url + 'template/')
        workbook = load_workbook(io.BytesIO(b''.join(response.streaming_content)))
        self.assertIn(('時段', '09:00–12:00', '單板／私人課／上午', '測試雪場'), list(workbook['選項'].values))
        other = CourseTemplate.objects.create(course_type=self.kind, name='上午', duration_hours=3)
        other.resorts.add(self.resort)
        CourseSession.objects.create(template=other, start_time=time(10), end_time=time(13))
        self.assertEqual(self.preview(self.row())['summary']['errors'], 0)
        self.assertEqual(self.preview(self.row(**{END: time(13)}))['row_results'][0]['code'], 'unknown_session')
        CourseSession.objects.create(template=other, start_time=time(9), end_time=time(12))
        self.assertEqual(self.preview(self.row())['row_results'][0]['code'], 'course_ambiguous')
        self.assertEqual(self.preview(self.row(**{TEMPLATE: self.template.pk}))['summary']['errors'], 0)
        self.template.is_active = False
        self.template.save(update_fields=['is_active'])
        self.assertEqual(self.preview(self.row(**{TEMPLATE: self.template.pk}))['row_results'][0]['code'], 'course_inactive')
        foreign_tenant = Client.objects.create(name='另一校', internal_code='other')
        foreign_category = CourseCategory.objects.create(client=foreign_tenant, name='另一類')
        foreign_kind = CourseType.objects.create(category=foreign_category, name='另一種')
        foreign_course = CourseTemplate.objects.create(course_type=foreign_kind, name='外校課程', duration_hours=3)
        self.assertEqual(self.preview(self.row(**{TEMPLATE: foreign_course.pk}))['row_results'][0]['code'], 'course_not_found')
        different_resort = Resorts.objects.create(client=self.tenant, name='new-resort', display_name='另一雪場')
        self.campus.resorts.add(different_resort)
        self.assertEqual(self.preview(self.row(**{RESORT: different_resort.name}))['row_results'][0]['code'], 'course_not_at_resort')

    def test_photo_course_or_addon_explains_missing_data(self):
        token = '雪地攝影 / 全家福/寫真 / 滑雪攝影_1H'
        row = self.row(**{TEMPLATE: token, DAY: None, PEOPLE: None, ABILITY: None})
        self.assertEqual(self.preview(row)['row_results'][0]['code'], 'unmatched_addon')
        category = CourseCategory.objects.create(client=self.tenant, name='雪地攝影', service_type='photo')
        kind = CourseType.objects.create(category=category, name='全家福／寫真')
        photo = CourseTemplate.objects.create(course_type=kind, name='滑雪攝影_1H', duration_hours=1)
        photo.resorts.add(self.resort)
        CourseSession.objects.create(template=photo, start_time=time(9), end_time=time(10))
        row[END] = time(10)
        result = self.preview(row)['row_results']
        self.assertEqual([(item['code'], item['columns']) for item in result], [
            ('photo_fields_required', [DAY, PEOPLE, ABILITY]),
        ])
        row.update({DAY: self.day, PEOPLE: 2, ABILITY: '等級 0'})
        self.assertEqual(self.preview(row)['summary']['committable'], 1)

    def coach(self):
        coach = Coach.objects.create(client=self.tenant, name='行政已排教練', languages=['zh'], availability_status='active')
        coach.campuses.add(self.campus)
        CoachResort.objects.create(coach=coach, resort=self.resort, assignment_score=1)
        CoachCourseLevel.objects.create(coach=coach, course_type=self.kind, ability_levels=['level1'], price_level='Lv1')
        return coach

    def test_coach_assignment_is_administrative_and_conflicts_with_earlier_orders(self):
        coach = self.coach()
        preview = self.preview(self.row(**{COACH: coach.name}), self.row(**{KEY: '0002', COACH: coach.pk}))
        self.assertIn('coach_conflict', [issue['code'] for issue in preview['order_results'][1]['issues']])
        result = self.commit(preview, allow_overbook=True, overbook_reason='實售資料')
        self.assertEqual([item['status'] for item in result['commit_results']], ['created', 'failed'])
        reservation = ReservationGroup.objects.get().reservations.get()
        self.assertEqual(reservation.preferred_coach, coach)
        self.assertFalse(reservation.is_preferred_coach)
        self.assertEqual(reservation.status, 'manually_assigned')
        self.assertTrue(reservation.bookings.get().is_scheduled)

    def test_capacity_includes_prior_groups_and_frontend_sees_import(self):
        first = self.row()
        second = self.row(**{KEY: '0002'})
        preview = self.preview(first, second)
        self.assertEqual(preview['summary']['full'], 1)
        result = self.commit(preview)
        self.assertEqual([item['status'] for item in result['commit_results']], ['created', 'skipped'])
        sessions = self.client.get('/booking/snowland/api/course-sessions/', {
            'template_id': self.template.pk, 'date': self.day.isoformat(), 'resort': self.resort.name,
        })
        self.assertEqual(sessions.status_code, 200)
        self.assertTrue(sessions.json()[0]['is_full'])
        preview = self.preview(second)
        self.assertEqual(self.commit_response(preview, allow_overbook=True).status_code, 400)
        result = self.commit(preview, allow_overbook=True, overbook_reason='紙本已收款')
        self.assertTrue(result['commit_results'][0]['overbooked'])
        payment = Payment.objects.get(DataJSON__source_order_number='0002')
        self.assertTrue(payment.DataJSON['overbooked_import'])
        self.assertIn('超賣匯入：紙本已收款', payment.reservation_group.revisions.get().reason)
        self.assertEqual(OrderImportBatch.objects.get(pk=result['batch_id']).overbook_reason, '紙本已收款')

    def test_capacity_includes_staff_link_holds_at_preview_and_commit(self):
        before_hold = self.preview(self.row())
        self.assertEqual(before_hold['summary']['full'], 0)
        link = StaffBookingLink.objects.create(
            client=self.tenant, campus=self.campus, created_by=self.actor,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        slot = Slot(self.template, self.day, self.session.start_time, self.session.end_time)
        create_holds(link, [(slot, self.resort.name)], self.actor)

        preview = self.preview(self.row())
        self.assertEqual(preview['summary']['full'], 1)
        self.assertEqual([issue['code'] for issue in preview['order_results'][0]['issues']], ['full'])
        committed, = self.commit(before_hold)['commit_results']
        self.assertEqual(committed['status'], 'skipped')
        self.assertEqual([issue['code'] for issue in committed['issues']], ['full'])
        self.assertFalse(ReservationGroup.objects.exists())

    def test_commit_rechecks_closure_and_availability(self):
        preview = self.preview(self.row())
        BookingClosure.objects.create(client=self.tenant, resort=self.resort, date_from=self.day, date_to=self.day)
        result = self.commit(preview)
        self.assertEqual(result['commit_results'][0]['status'], 'created')
        self.assertIn('closed', [issue['code'] for issue in result['commit_results'][0]['issues']])
        later = self.preview(self.row(**{KEY: 'later'}))
        self.assertEqual(later['summary']['closed'], 1)
        self.session.is_active = False
        self.session.save(update_fields=['is_active'])
        self.assertEqual(self.commit(later, allow_overbook=True, overbook_reason='紙本已收款')['status'], 'failed')

    def test_idempotency_existing_member_and_different_content(self):
        member = User.objects.create_user('existing', email='import@example.com', password='long test password')
        profile = ClientMemberProfile.objects.create(client=self.tenant, user=member, referral_code='import-existing')
        preview = self.preview(self.row())
        self.assertEqual(preview['order_results'][0]['member']['code'], 'existing_member')
        self.commit(preview)
        group = ReservationGroup.objects.get()
        self.assertEqual(group.user_id, profile.user_id)
        self.assertTrue(group.user.has_usable_password())
        preview = self.preview(self.row(**{EMAIL: 'IMPORT@example.com', METHOD: 'TT'}))
        self.assertEqual(preview['order_results'][0]['issues'][0]['code'], 'already_imported')
        self.assertEqual(self.commit(preview)['commit_results'][0]['status'], 'skipped')
        preview = self.preview(self.row(**{FEE: 999}))
        self.assertEqual(preview['order_results'][0]['issues'][0]['code'], 'source_order_conflict')
        self.assertEqual(self.commit(preview)['status'], 'failed')
        self.assertEqual(ReservationGroup.objects.count(), 1)

    def test_hq_setting_and_tenant_batch_isolation(self):
        preview = self.preview(self.row())
        _, assistant = self.client_for('assistant', 'assistant', grants=['order_edit'])
        _, limited = self.client_for('limited', 'hq_admin', all_campuses=False)
        _, reader = self.client_for('reader', 'hq_admin', grants=['order_view'])
        other = Client.objects.create(name='其他學校', internal_code='other')
        _, outsider = self.client_for('other-hq', 'hq_admin', tenant=other)
        for actor in (assistant, limited, reader, outsider):
            self.assertEqual(actor.get(self.url + 'template/').status_code, 403)
            self.assertEqual(self.preview_response(xlsx([self.row()]), api=actor).status_code, 403)
            self.assertEqual(self.commit_response(preview, api=actor).status_code, 403)
        other_url = self.url.replace('snowland', 'other')
        self.assertEqual(self.commit_response(preview, api=outsider, url=other_url).status_code, 404)
        result = self.preview_response(xlsx([self.row()]), api=outsider, url=other_url)
        self.assertEqual(result.status_code, 200)
        self.assertGreater(result.data['data']['summary']['errors'], 0)
        self.flags(order_import_enabled=False)
        self.assertEqual(self.hq.get(self.url + 'template/').status_code, 403)
        self.assertEqual(self.preview_response(xlsx([self.row()])).status_code, 403)
        self.assertEqual(self.commit_response(preview).status_code, 403)
        self.assertIs(self.hq.get('/api/admin/snowland/me/').data['data']['order_import_enabled'], False)

    def test_cross_school_existing_login_provisions_local_membership(self):
        other = Client.objects.create(name='其他學校', internal_code='other')
        user = User.objects.create_user('shared-login', email='import@example.com', password='long test password')
        ClientMemberProfile.objects.create(client=other, user=user, referral_code='other-member')
        preview = self.preview(self.row())
        self.assertEqual(preview['order_results'][0]['member']['code'], 'new_membership')
        self.commit(preview)
        self.assertEqual(ReservationGroup.objects.get().user, user)
        self.assertEqual(user.school_member_profiles.count(), 2)
        self.assertEqual(User.objects.filter(email=user.email).count(), 1)

    def test_posting_modes_template_periods_people_limits_and_shared_classes(self):
        self.flags(manual_payment_posting_date_mode='required')
        self.assertEqual(self.preview(self.row())['row_results'][0]['columns'], [POSTED])
        self.flags(manual_payment_posting_date_mode='disabled')
        issues = self.preview(self.row(**{POSTED: date.today()}))['row_results']
        self.assertIn('posting_date_disabled', [item['code'] for item in issues])
        self.flags()
        self.template.minimum_student_level = 'level2'
        self.template.course_start_date = self.day + timedelta(days=1)
        self.template.booking_close_date = timezone.localdate() - timedelta(days=2)
        self.template.save()
        issues = self.preview(self.row(**{PEOPLE: 4, NAMES: None, ABILITY: 'level1', POSTED: self.day}))['row_results']
        self.assertEqual({item['code'] for item in issues}, {
            'people_limit', 'ability_limit', 'booking_window', 'course_date_range', 'future_posting_date',
        })
        self.template.shared_class_enabled = True
        self.template.save(update_fields=['shared_class_enabled'])
        self.assertIn('個別處理', self.preview(self.row())['row_results'][0]['message_zh'])

    def test_csv_encodings_and_untrusted_file_limits(self):
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerow(['第 2 列'])
        writer.writerow([' 範例 ', 'discard'])
        row = self.row(**{START: '09:00', END: '12:00'})
        writer.writerow([row.get(column) for column in HEADERS])
        for encoding in ('utf-8-sig', 'cp950'):
            with self.subTest(encoding=encoding):
                preview = self.preview(content=stream.getvalue().encode(encoding), filename='orders.csv')
                self.assertEqual(preview['summary']['errors'], 0)
                self.assertEqual(preview['summary']['skipped_examples'], 1)
        self.assertEqual(self.commit(preview)['summary']['created'], 1)
        cases = [
            (xlsx([], header=(*HEADERS[:-1], ' 備註')), 'invalid_header', 400),
            (xlsx([[*repeat('', len(HEADERS)), '額外資料']]), 'extra_column', 400),
            (xlsx(repeat([None], MAX_ROWS + 1)), 'too_many_rows', 400),
            (b'malformed\x00bytes', 'invalid_xlsx', 400),
            (b'x' * (MAX_BYTES + 1), 'file_too_large', 413),
        ]
        for content, code, status in cases:
            with self.subTest(code=code):
                result = self.preview_response(content)
                self.assertEqual(result.status_code, status, result.data)
                self.assertEqual(result.data['code'], code)
        formula = self.preview(self.row(**{NAME: '=SUM(1,1)'}))
        self.assertEqual(formula['row_results'][0]['code'], 'invalid_cell')

    def test_member_login_reset_and_existing_pre_course_flow(self):
        self.commit(self.preview(self.row()))
        group = ReservationGroup.objects.get()
        member = APIClient()
        with patch('snowland.google_auth.verify_google_oauth2_token', return_value={'email': group.user.email}):
            google = member.post('/booking/snowland/api/google-login/', {'credential': 'test-token'}, format='json')
        self.assertEqual(google.status_code, 200, google.data)

        def verify_portal(client):
            center = client.get('/booking/snowland/api/member-center/')
            self.assertEqual(center.status_code, 200, center.data)
            order, = center.data['orders']
            self.assertEqual(order['id'], group.pk)
            self.assertEqual(len(center.data['pre_course_forms']), 2)
            self.assertTrue(order['reservations'][0]['participants'][0]['can_invite'])

        verify_portal(member)
        auth = '/booking/snowland/api/member-auth/'
        visitor = APIClient()
        with patch('booking.api_views.send_mail') as send:
            result = visitor.post(auth, {'action': 'request_reset', 'email': group.user.email.upper()}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        send.assert_called_once()
        url = send.call_args.args[1].splitlines()[-1]
        params = parse_qs(urlsplit(url).query)
        password = 'a-local-test-password'
        result = visitor.post(auth, {
            'action': 'reset_password', 'uid': params['reset_uid'][0], 'token': params['reset_token'][0], 'password': password,
        }, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        result = visitor.post(auth, {'action': 'login', 'email': group.user.email, 'password': password}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        verify_portal(visitor)

    def test_automatic_jobs_skip_import_notifications_and_erase_expired_staging(self):
        self.commit(self.preview(self.row()))
        expiring = self.preview(self.row(**{KEY: 'expires', DAY: self.day + timedelta(days=1)}))
        OrderImportBatch.objects.filter(pk=expiring['batch_id']).update(created_at=timezone.now() - timedelta(days=2))
        NotificationTemplate.objects.create(
            client=self.tenant, event='pre_course', channel='email', name='通知測試',
            subject='課前提醒', body='測試', days_before=30, is_active=True,
        )
        with patch('booking.management.commands.process_snowland_jobs.send_mail') as send:
            call_command('process_snowland_jobs', stdout=io.StringIO())
        send.assert_not_called()
        self.assertFalse(NotificationDelivery.objects.exists())
        pending = OrderImportBatch.objects.get(pk=expiring['batch_id'])
        self.assertIsNone(pending.staged_input)
        self.assertEqual(pending.status, 'previewed')
        self.assertEqual(self.commit_response(expiring).status_code, 409)

    def test_commit_rolls_back_one_order_without_blocking_the_rest(self):
        from booking.order_import import service

        create = service.create_order

        def write_order(tenant, actor, batch, order, fingerprint, **options):
            group = create(tenant, actor, batch, order, fingerprint, **options)
            if order.key == '0001':
                raise ValueError('test rollback')
            return group

        batch = self.preview(self.row(), self.row(**{KEY: '0002'}))
        with patch.object(service, 'create_order', side_effect=write_order):
            result = self.commit(batch)
        self.assertEqual([item['status'] for item in result['commit_results']], ['failed', 'created'])
        self.assertEqual(Payment.objects.get().DataJSON['source_order_number'], '0002')
