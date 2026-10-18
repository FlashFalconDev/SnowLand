from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from API import tests_operations as fixtures
from Coach.models import PayrollStatement, PayrollLine
from Coach.payroll_review import confirm_due_statements


class PayrollReviewTests(TestCase):
    def setUp(self):
        fixtures.OperationsTests.setUp(self)
        self.hq = User.objects.create_superuser('review-hq', 'review-hq@example.test', 'QA-only')
        self.api = APIClient(); self.api.force_authenticate(self.hq)
        today = timezone.localdate()
        self.statement = PayrollStatement.objects.create(coach=self.coach, campus=self.campus,
            period_start=today-timedelta(days=35), period_end=today-timedelta(days=5), course_pay=1000, total_amount=1000)
        PayrollLine.objects.create(statement=self.statement, line_type='course', description='QA review', total_amount=1000)
        profile = self.coach_user.userprofile
        profile.is_coach = True; profile.save(update_fields=['is_coach'])
        self.admin_url = f'/api/admin/snowland/payroll-statements/{self.statement.pk}/'
        self.coach_url = f'/api/admin/snowland/coach/payroll/{self.statement.pk}/'
        self.deadline = today + timedelta(days=2)

    def publish(self):
        response = self.api.post(self.admin_url+'publish/', {'confirmation_deadline': self.deadline.isoformat()}, format='json')
        self.assertEqual(response.status_code, 200, getattr(response, 'data', 'not an API response'))
        self.statement.refresh_from_db()
        return response

    def test_publish_hides_drafts_then_exposes_only_own_statement_and_locks_editing(self):
        self.api.force_authenticate(self.coach_user)
        self.assertEqual(self.api.get(self.coach_url).status_code, 404)
        self.api.force_authenticate(self.hq); self.publish()
        self.assertEqual(self.statement.status, 'review')
        self.assertEqual(self.api.delete(self.admin_url).status_code, 400)
        self.assertEqual(self.api.post(self.admin_url+'adjustments/', {'description': 'QA', 'amount': 1}, format='json').status_code, 400)
        self.api.force_authenticate(self.coach_user)
        self.assertEqual(self.api.get(self.coach_url).status_code, 200)

    def test_coach_confirm_is_idempotent_and_never_marks_paid(self):
        self.publish(); self.api.force_authenticate(self.coach_user)
        for _ in range(2):
            response = self.api.post(self.coach_url+'confirm/', {'review_token': str(self.statement.review_token)}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
        self.statement.refresh_from_db()
        self.assertEqual(self.statement.status, 'confirmed')
        self.assertEqual(self.statement.confirmed_by, self.coach_user)
        self.assertEqual(self.statement.confirmation_method, 'coach')
        self.assertEqual(self.statement.total_amount, 1000)

    def test_deadline_boundary_dry_run_and_repeat_do_not_touch_drafts_or_paid(self):
        import uuid
        paid = PayrollStatement.objects.create(coach=self.coach, campus=self.campus,
            period_start=self.statement.period_start-timedelta(days=50), period_end=self.statement.period_start-timedelta(days=40),
            status='paid', total_amount=250, review_token=uuid.uuid4(), published_at=timezone.now(),
            confirmation_deadline=timezone.localdate()-timedelta(days=2))
        self.publish()
        now = timezone.now()
        with patch('Coach.payroll_review.timezone.localdate', return_value=self.deadline):
            self.assertEqual(confirm_due_statements(now), 0)
        with patch('Coach.payroll_review.timezone.localdate', return_value=self.deadline+timedelta(days=1)):
            self.assertEqual(confirm_due_statements(now, dry_run=True), 1)
            self.statement.refresh_from_db(); self.assertEqual(self.statement.status, 'review')
            self.assertEqual(confirm_due_statements(now), 1)
            self.assertEqual(confirm_due_statements(now), 0)
        self.statement.refresh_from_db()
        self.assertEqual(self.statement.confirmation_method, 'automatic')
        self.assertIsNone(self.statement.confirmed_by)
        paid.refresh_from_db()
        self.assertEqual((paid.status, paid.total_amount, paid.confirmed_at), ('paid', 250, None))

    def test_withdraw_and_republish_rejects_stale_coach_confirmation(self):
        self.publish(); old_token = str(self.statement.review_token)
        self.assertEqual(self.api.post(self.admin_url+'withdraw/').status_code, 200)
        self.statement.refresh_from_db(); self.assertEqual(self.statement.status, 'draft')
        self.publish(); self.assertNotEqual(str(self.statement.review_token), old_token)
        self.api.force_authenticate(self.coach_user)
        self.assertEqual(self.api.post(self.coach_url+'confirm/', {'review_token': old_token}, format='json').status_code, 409)
        self.statement.refresh_from_db(); self.assertEqual(self.statement.status, 'review')

    def test_missing_past_or_invalid_deadline_and_empty_statement_rejected(self):
        for value in [None, 'bad', (timezone.localdate()-timedelta(days=1)).isoformat()]:
            response = self.api.post(self.admin_url+'publish/', {'confirmation_deadline': value}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.statement.lines.all().delete()
        self.assertEqual(self.api.post(self.admin_url+'publish/', {'confirmation_deadline': self.deadline.isoformat()}, format='json').status_code, 400)
        self.statement.refresh_from_db(); self.assertEqual(self.statement.status, 'draft')

    def test_regular_member_and_unrelated_coach_cannot_read_or_confirm(self):
        self.publish(); self.api.force_authenticate(self.user)
        self.assertEqual(self.api.get(self.coach_url).status_code, 403)
        self.assertEqual(self.api.post(self.admin_url+'withdraw/').status_code, 403)
        from Coach.models import Coach
        other = User.objects.create_user('other-coach')
        other.userprofile.is_coach = True; other.userprofile.save()
        Coach.objects.create(client=self.client_tenant, user=other, name='QA other')
        self.api.force_authenticate(other)
        self.assertEqual(self.api.get(self.coach_url).status_code, 404)
        self.assertEqual(self.api.post(self.coach_url+'confirm/', {'review_token': str(self.statement.review_token)}, format='json').status_code, 404)

    def test_expired_review_cannot_be_withdrawn_and_manual_confirmation_records_auto(self):
        self.publish()
        with patch('Coach.payroll_review.timezone.localdate', return_value=self.deadline+timedelta(days=1)):
            self.assertEqual(self.api.post(self.admin_url+'withdraw/').status_code, 409)
            self.api.force_authenticate(self.coach_user)
            response = self.api.post(self.coach_url+'confirm/', {'review_token': str(self.statement.review_token)}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
        self.statement.refresh_from_db(); self.assertEqual(self.statement.confirmation_method, 'automatic')

    def test_other_campus_and_other_tenant_admin_cannot_publish_or_withdraw(self):
        from Resorts.models import Campus
        other = Campus.objects.create(client=self.client_tenant, code='review-other', name='QA other')
        self.assertEqual(self.api.post(self.admin_url+'publish/', {'confirmation_deadline':self.deadline.isoformat()}, format='json', HTTP_X_CAMPUS_ID=str(other.pk)).status_code, 404)
        self.assertEqual(self.api.post(self.admin_url+'withdraw/', HTTP_X_CAMPUS_ID=str(other.pk)).status_code, 404)
        from Client.models import Client
        Client.objects.create(name='QA other tenant', internal_code='review-other')
        other_url = self.admin_url.replace('/snowland/', '/review-other/')
        self.assertEqual(self.api.post(other_url+'publish/', {'confirmation_deadline':self.deadline.isoformat()}, format='json').status_code, 404)
        self.assertEqual(self.api.post(other_url+'withdraw/').status_code, 404)

    def test_job_dispatch_and_dry_run_only_confirm_published_review(self):
        from django.core.management import call_command
        from io import StringIO
        with patch('Coach.payroll_review.timezone.localdate', return_value=self.deadline+timedelta(days=1)):
            self.assertEqual(confirm_due_statements(), 0)  # draft remains draft
        self.publish()
        PayrollStatement.objects.filter(pk=self.statement.pk).update(confirmation_deadline=timezone.localdate()-timedelta(days=1))
        output = StringIO()
        call_command('process_snowland_jobs', dry_run=True, stdout=output)
        self.statement.refresh_from_db(); self.assertEqual(self.statement.status, 'review')
        self.assertIn('payroll_confirmed=1', output.getvalue())
        call_command('process_snowland_jobs', stdout=StringIO())
        self.statement.refresh_from_db(); self.assertEqual(self.statement.status, 'confirmed')
        self.assertEqual(self.statement.confirmation_method, 'automatic')

    def test_browser_publish_and_confirm_require_csrf_tokens(self):
        from django.test import Client as BrowserClient
        admin = BrowserClient(enforce_csrf_checks=True); admin.force_login(self.hq)
        data = {'confirmation_deadline':self.deadline.isoformat()}
        self.assertEqual(admin.post(self.admin_url+'publish/',data).status_code, 403)
        self.assertEqual(admin.get(self.admin_url).status_code, 200)
        self.assertEqual(admin.post(self.admin_url+'publish/',data,HTTP_X_CSRFTOKEN=admin.cookies['csrftoken'].value).status_code, 200)
        coach = BrowserClient(enforce_csrf_checks=True); coach.force_login(self.coach_user)
        self.statement.refresh_from_db(); data = {'review_token':str(self.statement.review_token)}
        self.assertEqual(coach.post(self.coach_url+'confirm/',data).status_code, 403)
        self.assertEqual(coach.get(self.coach_url).status_code, 200)
        self.assertEqual(coach.post(self.coach_url+'confirm/',data,HTTP_X_CSRFTOKEN=coach.cookies['csrftoken'].value).status_code, 200)
