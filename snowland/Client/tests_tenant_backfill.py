from importlib import import_module
from types import SimpleNamespace
from django.apps import apps
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from Client.models import Client, ClientMemberProfile
from Control.models import TenantStaffMembership
from Resorts.models import Campus
from booking.models import MemberProfile, ReservationGroup


class BackfillTests(TestCase):
    def setUp(self):
        self.a=Client.objects.create(name='A',internal_code='school-a')
        self.b=Client.objects.create(name='B',internal_code='school-b')
        self.user=User.objects.create_user('legacy',first_name='Original')
        self.editor=SimpleNamespace(connection=connection)

    def test_old_staff_roles_and_only_owned_campuses_are_preserved_once(self):
        campus=Campus.objects.create(client=self.a,name='A',code='main')
        foreign=Campus.objects.create(client=self.b,name='B',code='main')
        old=self.user.userprofile
        old.is_manager=True;old.manager_client=self.a;old.role='campus_principal';old.admin_permissions=['orders'];old.save()
        old.campuses.add(campus,foreign)
        run=import_module('Control.migrations.0009_backfill_tenant_staff').backfill_staff
        run(apps,self.editor)
        row=TenantStaffMembership.objects.get(user=self.user,client=self.a)
        self.assertEqual(row.role,'campus_principal')
        self.assertEqual(list(row.campuses.all()),[campus])
        self.assertEqual(row.admin_permissions,['orders'])
        row.is_manager=False;row.save()
        run(apps,self.editor)
        row.refresh_from_db();self.assertFalse(row.is_manager)
        self.assertFalse(TenantStaffMembership.objects.filter(client=self.b).exists())
        old.refresh_from_db();self.assertTrue(old.is_manager)

    def test_member_backfill_retains_single_school_legacy_but_never_shares_line(self):
        old=MemberProfile.objects.create(user=self.user,line_user_id='legacy-line')
        ReservationGroup.objects.create(client=self.a,user=self.user)
        run=import_module('Client.migrations.0012_backfill_school_members').backfill_members
        run(apps,self.editor)
        row=ClientMemberProfile.objects.get(user=self.user,client=self.a)
        self.assertEqual(row.referral_code,old.referral_code)
        self.assertEqual(row.line_user_id,old.line_user_id)
        row.display_name='Locally edited';row.save()
        ReservationGroup.objects.create(client=self.b,user=self.user)
        run(apps,self.editor)
        row.refresh_from_db();self.assertEqual(row.display_name,'Locally edited')
        second=ClientMemberProfile.objects.get(user=self.user,client=self.b)
        self.assertEqual(second.line_user_id,'')
        self.assertNotEqual(second.referral_code,old.referral_code)
        self.assertEqual(ClientMemberProfile.objects.count(),2)
