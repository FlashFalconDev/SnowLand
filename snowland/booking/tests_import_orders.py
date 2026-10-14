from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase
from openpyxl import Workbook

from Client.models import Client
from Coursekit.models import CourseCategory, CourseTemplate, CourseType
from Resorts.models import Campus, Resorts
from booking.models import Booking, MemberDetail, Payment, ReservationGroup


class ImportSnowLandOrdersTests(TestCase):
    def setUp(self):
        self.client_record = Client.objects.create(name='SnowLand', internal_code='snowland')
        self.resort = Resorts.objects.create(client=self.client_record, name='Tomamu', display_name='星野 Tomamu')
        self.campus = Campus.objects.create(client=self.client_record, name='北海道', code='hokkaido')
        self.campus.resorts.add(self.resort)
        category = CourseCategory.objects.create(client=self.client_record, name='單板 Snowboard')
        course_type = CourseType.objects.create(category=category, name='一般課程')
        self.template = CourseTemplate.objects.create(
            course_type=course_type, name='全天包班', duration_hours=6, max_capacity=6,
        )
        self.template.resorts.add(self.resort)

    def make_workbook(self, *, email='member@example.com'):
        directory = TemporaryDirectory()
        path = Path(directory.name) / 'orders.xlsx'
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = '訂單統計表'
        sheet['P2'] = '編號'; sheet['V2'] = '訂課姓名'; sheet['W2'] = 'Email'
        sheet['P3'] = '001'; sheet['V3'] = '測試會員'; sheet['W3'] = email
        sheet['AB3'] = '星野'; sheet['AD3'] = '全天'; sheet['AE3'] = datetime(2027, 1, 10)
        sheet['AF3'] = 2; sheet['AG3'] = 2; sheet['AI3'] = '單板-2人'
        sheet['AQ3'] = 30; sheet['BA3'] = 8
        sheet['AU3'] = '雪場S turn'; sheet['BE3'] = '無經驗'
        sheet['DA3'] = 270101001; sheet['DF3'] = 20000; sheet['DM3'] = '✔銀行'
        workbook.save(path)
        return directory, path

    def test_dry_run_does_not_write(self):
        directory, path = self.make_workbook()
        self.addCleanup(directory.cleanup)
        output = StringIO()
        call_command('import_snowland_orders', str(path), stdout=output)
        self.assertIn('DRY RUN', output.getvalue())
        self.assertFalse(ReservationGroup.objects.exists())

    def test_commit_imports_and_second_run_skips_existing_order(self):
        directory, path = self.make_workbook()
        self.addCleanup(directory.cleanup)
        call_command('import_snowland_orders', str(path), '--commit')
        group = ReservationGroup.objects.get(order_number='270101001')
        self.assertEqual(group.user.email, 'member@example.com')
        self.assertEqual(group.reservations.count(), 1)
        self.assertEqual(Booking.objects.filter(reservation__group=group).count(), 2)
        self.assertEqual(MemberDetail.objects.filter(reservation__group=group).count(), 2)
        self.assertEqual(Payment.objects.get(reservation_group=group).status, 'paid')

        output = StringIO()
        call_command('import_snowland_orders', str(path), '--commit', stdout=output)
        self.assertIn('已存在略過 1 筆', output.getvalue())
        self.assertEqual(ReservationGroup.objects.count(), 1)

    def test_missing_email_is_reported_and_not_imported(self):
        directory, path = self.make_workbook(email='')
        self.addCleanup(directory.cleanup)
        output = StringIO()
        call_command('import_snowland_orders', str(path), stdout=output)
        self.assertIn('缺少有效 Email', output.getvalue())
        self.assertFalse(ReservationGroup.objects.exists())
