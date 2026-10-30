from django.contrib.auth.models import User
from django.http import JsonResponse
from django.test import TestCase,RequestFactory
from rest_framework.test import APIClient
from Control.legacy_access import platform_only


class LegacyControlAccessTests(TestCase):
    def setUp(self):
        self.api=APIClient()
        self.user=User.objects.create_user('school-staff',email='staff@example.test')
        self.user.userprofile.is_manager=True;self.user.userprofile.save()

    def test_email_header_is_not_authentication(self):
        response=self.api.get('/control/api/manager/member_list/',HTTP_JWT='1|staff@example.test')
        self.assertEqual(response.status_code,401)

    def test_school_staff_cannot_use_old_unscoped_management_but_can_logout(self):
        self.api.force_login(self.user)
        response=self.api.get('/control/api/manager/member_list/')
        self.assertEqual(response.status_code,403)
        response=self.api.post('/control/api/logout/')
        self.assertEqual(response.status_code,200,response.content)

    def test_platform_account_can_use_legacy_wrapper(self):
        self.user.is_superuser=True;self.user.save()
        request=RequestFactory().get('/control/api/manager/member_list/');request.user=self.user
        response=platform_only(lambda req:JsonResponse({'ok':True}))(request)
        self.assertEqual(response.status_code,200)
