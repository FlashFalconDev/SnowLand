from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase

from Client.models import Client


bind_existing_managers = import_module(
    'Control.migrations.0007_userprofile_manager_client'
).bind_existing_managers


class ManagerClientMigrationTests(TestCase):
    def test_unassigned_legacy_manager_uses_sole_active_client(self):
        client = Client.objects.create(name='SnowLand', internal_code='snowland')
        Client.objects.exclude(pk=client.pk).update(is_active=False)
        manager = User.objects.create_user('legacy-hq')
        profile = manager.userprofile
        profile.is_manager = True
        profile.save(update_fields=['is_manager'])

        bind_existing_managers(apps, None)

        profile.refresh_from_db()
        self.assertEqual(profile.manager_client_id, client.id)

    def test_ambiguous_legacy_manager_remains_unassigned(self):
        Client.objects.create(name='SnowLand', internal_code='snowland')
        Client.objects.create(name='Other', internal_code='other')
        manager = User.objects.create_user('legacy-hq')
        profile = manager.userprofile
        profile.is_manager = True
        profile.save(update_fields=['is_manager'])

        bind_existing_managers(apps, None)

        profile.refresh_from_db()
        self.assertIsNone(profile.manager_client_id)
