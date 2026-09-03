from ipaddress import ip_address
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model


LOCAL_DEV_USERNAME = "local-dev-admin"
LOCAL_DEV_EMAIL = "local-dev@snowland.test"


def _is_loopback(value):
    if not value:
        return False
    if value.lower() == "localhost":
        return True
    try:
        return ip_address(value).is_loopback
    except ValueError:
        return False


class LocalAuthBypassMiddleware:
    """Authenticate one local-only admin when the explicit dev switch is enabled."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_enabled_for(request):
            self._ensure_local_tenant()
            request.user = self._get_local_admin()
        return self.get_response(request)

    @staticmethod
    def _is_enabled_for(request):
        if not settings.DEBUG or not settings.LOCAL_AUTH_BYPASS:
            return False

        hostname = urlsplit(f"//{request.get_host()}").hostname
        remote_address = request.META.get("REMOTE_ADDR")
        return _is_loopback(hostname) and _is_loopback(remote_address)

    @staticmethod
    def _get_local_admin():
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=LOCAL_DEV_USERNAME,
            defaults={
                "email": LOCAL_DEV_EMAIL,
                "first_name": "Local",
                "last_name": "Developer",
                "is_staff": True,
                "is_superuser": True,
            },
        )

        fields_to_update = []
        for field, value in (
            ("email", LOCAL_DEV_EMAIL),
            ("is_active", True),
            ("is_staff", True),
            ("is_superuser", True),
        ):
            if getattr(user, field) != value:
                setattr(user, field, value)
                fields_to_update.append(field)

        if created:
            user.set_unusable_password()
            fields_to_update.append("password")

        if fields_to_update:
            user.save(update_fields=fields_to_update)
        return user

    @staticmethod
    def _ensure_local_tenant():
        from Client.models import Client

        tenant, _ = Client.objects.get_or_create(
            internal_code="snowland",
            defaults={
                "name": "SnowLand 本機測試",
                "is_active": True,
            },
        )
        if not tenant.is_active:
            tenant.is_active = True
            tenant.save(update_fields=["is_active"])
