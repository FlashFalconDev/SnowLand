from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from Client.models import Client
from snowland.middleware import LOCAL_DEV_USERNAME, LocalAuthBypassMiddleware


class LocalAuthBypassMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = LocalAuthBypassMiddleware(lambda request: HttpResponse("OK"))

    @override_settings(DEBUG=True, LOCAL_AUTH_BYPASS=True)
    def test_authenticates_loopback_request_as_local_superuser(self):
        request = self.factory.get("/", HTTP_HOST="127.0.0.1:8999")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.user = AnonymousUser()

        self.middleware(request)

        self.assertTrue(request.user.is_authenticated)
        self.assertTrue(request.user.is_superuser)
        self.assertEqual(request.user.username, LOCAL_DEV_USERNAME)
        self.assertFalse(request.user.has_usable_password())
        self.assertTrue(Client.objects.filter(internal_code="snowland", is_active=True).exists())

    @override_settings(DEBUG=True, LOCAL_AUTH_BYPASS=True)
    def test_local_dashboard_request_is_not_forbidden(self):
        response = self.client.get(
            "/api/admin/snowland/dashboard/",
            HTTP_HOST="127.0.0.1:8999",
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)

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
