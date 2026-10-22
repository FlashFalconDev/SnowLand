from django.middleware.csrf import get_token
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import SAFE_METHODS


class PayrollCsrfMixin:
    """Financial/document actions must not inherit CSRF-free auth fallbacks."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in SAFE_METHODS:
            get_token(request._request)
        else:
            SessionAuthentication().enforce_csrf(request)
