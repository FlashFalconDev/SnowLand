from django.test import SimpleTestCase

from .models import ReservationGroup, StaffBookingLink


class LegacyInsertDefaultsTests(SimpleTestCase):
    def test_new_fields_keep_database_defaults_for_legacy_inserts(self):
        self.assertIs(ReservationGroup._meta.get_field('is_test').db_default, False)
        self.assertEqual(StaffBookingLink._meta.get_field('snapshot_version').db_default, 0)
