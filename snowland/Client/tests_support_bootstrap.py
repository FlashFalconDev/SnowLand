from importlib import import_module

from django.contrib.auth.hashers import is_password_usable
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase, override_settings

from Client.models import Client


bootstrap = import_module('Client.migrations.0015_initialize_frontend_support_client')


class SupportClientBootstrapTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with override_settings(MIGRATION_MODULES={}):
            state = MigrationLoader(None).project_state([
                ('Client', '0014_merge_order_email_frontend_release'),
            ])
        cls.migration_apps = state.apps

    def setUp(self):
        Client.objects.filter(internal_code='flashfalcon').delete()
        self.initial_client_count = Client.objects.count()

    def run_bootstrap(self):
        bootstrap.initialize_support_client(self.migration_apps, connection.schema_editor())

    def test_creates_support_client_without_changing_snowland(self):
        snowland = Client.objects.create(
            internal_code='snowland', name='SnowLand',
            bank_name='Existing bank', bank_account_number='existing-account',
        )
        before = Client.objects.values().get(pk=snowland.pk)

        self.run_bootstrap()

        support = Client.objects.get(internal_code='flashfalcon')
        self.assertEqual(support.name, 'FlashFalcon')
        self.assertTrue(support.is_active)
        self.assertFalse(is_password_usable(support.password))
        self.assertEqual(Client.objects.values().get(pk=snowland.pk), before)
        self.assertEqual(Client.objects.count(), self.initial_client_count + 2)

    def test_preserves_an_existing_support_client(self):
        support = Client.objects.create(
            internal_code='flashfalcon', name='Existing platform',
            is_active=False, bank_name='Existing support bank',
        )
        before = Client.objects.values().get(pk=support.pk)

        self.run_bootstrap()

        self.assertEqual(Client.objects.values().get(pk=support.pk), before)
        self.assertEqual(Client.objects.count(), self.initial_client_count + 1)

    def test_repeat_execution_preserves_created_client(self):
        self.run_bootstrap()
        before = Client.objects.values().get(internal_code='flashfalcon')

        self.run_bootstrap()

        self.assertEqual(Client.objects.values().get(internal_code='flashfalcon'), before)
        self.assertEqual(Client.objects.count(), self.initial_client_count + 1)

    def test_reverse_keeps_client_data(self):
        self.run_bootstrap()
        before = Client.objects.values().get(internal_code='flashfalcon')

        bootstrap.Migration.operations[0].reverse_code(self.migration_apps, connection.schema_editor())

        self.assertEqual(Client.objects.values().get(internal_code='flashfalcon'), before)
