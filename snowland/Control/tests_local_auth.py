from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from Client.models import Client
from Resorts.models import Campus
from snowland.middleware import LOCAL_DEV_USERNAME, LocalAuthBypassMiddleware


class LocalAuthBypassMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = LocalAuthBypassMiddleware(lambda request: HttpResponse("OK"))

    @override_settings(DEBUG=True, LOCAL_AUTH_BYPASS=True)
    def test_authenticates_loopback_request_as_local_superuser(self):
        request = self.factory.get("/api/admin/snowland/me/", HTTP_HOST="127.0.0.1:8999")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.user = AnonymousUser()

        self.middleware(request)

        self.assertTrue(request.user.is_authenticated)
        self.assertTrue(request.user.is_superuser)
        self.assertEqual(request.user.username, LOCAL_DEV_USERNAME)
        self.assertFalse(request.user.has_usable_password())
        self.assertTrue(Client.objects.filter(internal_code="snowland", is_active=True).exists())

    @override_settings(DEBUG=True, LOCAL_AUTH_BYPASS=True)
    def test_does_not_override_member_site_session(self):
        request = self.factory.get("/booking/snowland/api/member-center/", HTTP_HOST="127.0.0.1:8999")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.user = AnonymousUser()

        self.middleware(request)

        self.assertFalse(request.user.is_authenticated)

    @override_settings(DEBUG=True, LOCAL_AUTH_BYPASS=True)
    def test_local_dashboard_request_is_not_forbidden(self):
        response = self.client.get(
            "/api/admin/snowland/dashboard/",
            HTTP_HOST="127.0.0.1:8999",
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True, LOCAL_AUTH_BYPASS=True)
    def test_real_campus_manager_session_is_not_replaced_by_local_superuser(self):
        tenant = Client.objects.create(internal_code='snowland', name='SnowLand')
        campus = Campus.objects.create(client=tenant, name='測試校區', code='manager-test')
        user = get_user_model().objects.create_user(username='qa-campus-manager', password='local-only-test')
        profile = user.userprofile
        profile.is_manager = True
        profile.role = 'campus_manager'
        profile.manager_client = tenant
        profile.save(update_fields=['is_manager', 'role', 'manager_client'])
        profile.campuses.add(campus)
        self.client.force_login(user)

        response = self.client.get(
            '/api/admin/snowland/me/', HTTP_HOST='127.0.0.1:8999', REMOTE_ADDR='127.0.0.1',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['username'], user.username)
        self.assertEqual(response.data['data']['assigned_campus_ids'], [campus.id])

    @override_settings(DEBUG=True, LOCAL_AUTH_BYPASS=True)
    def test_logged_in_coach_and_member_are_never_elevated_to_local_admin(self):
        for username, is_coach in [('qa-real-coach', True), ('qa-real-member', False)]:
            with self.subTest(username=username):
                user = get_user_model().objects.create_user(username)
                profile = user.userprofile
                profile.is_coach = is_coach
                profile.save(update_fields=['is_coach'])
                request = self.factory.get('/api/admin/snowland/me/', HTTP_HOST='127.0.0.1:8999')
                request.META['REMOTE_ADDR'] = '127.0.0.1'
                request.user = user
                self.middleware(request)
                self.assertEqual(request.user.pk, user.pk)
                self.assertFalse(request.user.is_superuser)

    @override_settings(DEBUG=True, LOCAL_AUTH_BYPASS=True)
    def test_does_not_authenticate_non_loopback_request(self):
        request = self.factory.get("/", HTTP_HOST="dev.flashfalcon.info")
        request.META["REMOTE_ADDR"] = "203.0.113.10"
        request.user = AnonymousUser()

        self.middleware(request)

        self.assertFalse(request.user.is_authenticated)

    @override_settings(DEBUG=True, LOCAL_AUTH_BYPASS=False)
    def test_does_not_authenticate_when_switch_is_disabled(self):
        request = self.factory.get("/", HTTP_HOST="127.0.0.1:8999")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.user = AnonymousUser()

        self.middleware(request)

        self.assertFalse(request.user.is_authenticated)
