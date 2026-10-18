from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase

from Client.models import Client
from booking.models import NotificationTemplate


create_snowland_template = import_module(
    'booking.migrations.0017_shared_class_ready_notification'
).create_snowland_template


class SharedClassNotificationMigrationTests(TestCase):
    def test_creates_editable_default_only_for_snowland_without_overwriting_it(self):
        snowland = Client.objects.create(name='SnowLand', internal_code='snowland')
        other = Client.objects.create(name='Other', internal_code='other')
        editor = SimpleNamespace(connection=connection)

        create_snowland_template(apps, editor)
        template = NotificationTemplate.objects.get(client=snowland, event='shared_class_ready')
        self.assertEqual(template.channel, 'email')
        self.assertIn('{payment_url}', template.body)
        self.assertTrue(template.is_active)
        self.assertFalse(NotificationTemplate.objects.filter(client=other, event='shared_class_ready').exists())

        template.body = 'SnowLand 自訂通知 {payment_url}'
        template.save(update_fields=['body'])
        create_snowland_template(apps, editor)
        self.assertEqual(NotificationTemplate.objects.filter(client=snowland, event='shared_class_ready').count(), 1)
        template.refresh_from_db()
        self.assertEqual(template.body, 'SnowLand 自訂通知 {payment_url}')
