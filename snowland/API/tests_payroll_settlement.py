from copy import deepcopy
from django.test import TestCase
from API import tests_payroll_review as fixtures
from Coach.models import PayrollDocumentSettings
from Coach.payroll import add_payroll_adjustment
from Coach.payroll_review import publish_statement, confirm_statement, withdraw_statement
from Coach.payroll_settlement import save_settlement


class PayrollSettlementTests(TestCase):
    def setUp(self):
        fixtures.PayrollReviewTests.setUp(self)
        self.payload={'currency':'JPY','rate':'4.5','base_amount':1000,'deductions':[
            {'name':'QA扣項A','basis':'4500','percent':'20'},
            {'name':'QA扣項B','basis':'3600','percent':'10'}], 'reviewed':True,'note':'僅QA比例，非正式稅率'}

    def save(self, **changes):
        self.statement.refresh_from_db()
        return save_settlement(self.statement, {**deepcopy(self.payload),'expected_reviewed_at':self.statement.settlement_snapshot.get('reviewed_at'),**changes},self.hq)

    def test_exact_jpy_rounding_and_twd_reconciliation(self):
        row=self.save();snap=row.settlement_snapshot
        self.assertEqual((snap['gross_amount'],snap['deduction_total'],snap['net_amount']),(4500,1260,3240))
        self.assertEqual((snap['base_net_amount'],snap['base_deduction_total']),(720,280))
        self.assertEqual(row.total_amount,1000);self.assertEqual(snap['reviewed_by'],self.hq.pk)

    def test_round_per_deduction_and_reconcile_residual(self):
        row=self.save(rate='4.5005',deductions=[{'name':'QA','basis':'4501','percent':'0.5'}])
        snap=row.settlement_snapshot
        self.assertEqual(snap['gross_amount'],4501);self.assertEqual(snap['deduction_total'],23)
        self.assertEqual(snap['base_net_amount']+snap['base_deduction_total'],1000)

    def test_explicit_no_tax_twd_and_zero_salary(self):
        self.assertEqual(self.save(currency='TWD',rate='1',deductions=[]).settlement_snapshot['net_amount'],1000)
        self.statement.total_amount=0;self.statement.save()
        self.assertEqual(self.save(base_amount=0,deductions=[]).settlement_snapshot['net_amount'],0)

    def test_malformed_and_excess_deductions_never_save(self):
        cases=[{'rate':'NaN'},{'rate':'Infinity'},{'rate':True},{'rate':4.5},{'rate':'0'},
            {'rate':'0.00000001'},{'currency':'USD'},{'currency':'TWD','rate':'4.5'},
            {'reviewed':False},{'base_amount':999},{'deductions':{}},
            {'deductions':[{'name':'QA','basis':'4501','percent':'1'}]},
            {'deductions':[{'name':'','basis':'0','percent':'1'}]},
            {'deductions':[{'name':'QA','basis':'4500','percent':'100'}]*2}]
        for changes in cases:
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.save(**changes)
        self.statement.refresh_from_db();self.assertEqual(self.statement.settlement_snapshot,{})

    def test_publishing_requires_review_and_stale_amount_blocks(self):
        with self.assertRaisesMessage(ValueError,'核對結果'):publish_statement(self.statement,self.deadline)
        self.save();add_payroll_adjustment(statement=self.statement,description='QA',amount=1)
        with self.assertRaisesMessage(ValueError,'已變更'):publish_statement(self.statement,self.deadline)

    def test_published_snapshot_locks_and_signed_document_contains_same_values(self):
        saved=self.save().settlement_snapshot
        row=publish_statement(self.statement,self.deadline)
        with self.assertRaisesMessage(ValueError,'僅草稿'):self.save(rate='5')
        PayrollDocumentSettings.objects.create(client=self.client_tenant,is_active=True,body='QA非正式文件')
        confirmed=confirm_statement(row,self.coach_user,str(row.review_token))
        self.assertEqual(confirmed.document_snapshot['settlement'],saved)
        self.assertEqual(confirmed.status,'confirmed')

    def test_withdraw_allows_revised_snapshot_but_not_change_after_confirmation(self):
        self.save();row=publish_statement(self.statement,self.deadline)
        withdraw_statement(row)
        self.assertEqual(self.save(rate='5').settlement_snapshot['gross_amount'],5000)

    def test_api_permission_scope_and_csrf(self):
        response=self.api.post(self.admin_url+'settlement/',self.payload,format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.api.force_authenticate(self.coach_user)
        self.assertEqual(self.api.post(self.admin_url+'settlement/',self.payload,format='json').status_code,403)
        from rest_framework.test import APIClient
        api=APIClient(enforce_csrf_checks=True);api.force_login(self.hq)
        self.assertEqual(api.post(self.admin_url+'settlement/',self.payload,format='json').status_code,403)

    def test_old_editor_cannot_overwrite_or_publish_a_new_tax_snapshot(self):
        old=self.save().settlement_snapshot['reviewed_at']
        self.save(rate='5')
        with self.assertRaisesMessage(ValueError,'版本已變更'):self.save(expected_reviewed_at=old)
        with self.assertRaisesMessage(ValueError,'版本已變更'):publish_statement(self.statement,self.deadline,expected_reviewed_at=old)
