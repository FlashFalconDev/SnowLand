from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlsplit


def _frontend_callback_url(request):
    next_url = request.GET.get('next')
    allowed_hosts = {request.get_host(), urlsplit(settings.FRONTEND_URL).netloc}
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts=allowed_hosts, require_https=request.is_secure(),
    ):
        return next_url
    # OAuth providers may omit Referer or send their own origin; never infer a
    # trusted frontend from that header (including arbitrary ngrok substrings).
    return settings.LOGIN_REDIRECT_URL


class MyAccountAdapter(DefaultAccountAdapter):
    def __init__(self, *args, **kwargs):
        print("DEBUG: MyAccountAdapter 已載入！")
        super().__init__(*args, **kwargs)

    def get_login_redirect_url(self, request):
        print("DEBUG: MyAccountAdapter.get_login_redirect_url 被調用！")
        return _frontend_callback_url(request)

    def logout(self, request):
        print("DEBUG: MyAccountAdapter.logout 被調用！")
        # 在此处添加自定义注销逻辑
        # 例如，重定向到特定页面或执行其他操作
        next_url = request.GET.get('next')
        response = super().logout(request)
        if next_url:
            return redirect(next_url)
        return response

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def __init__(self, *args, **kwargs):
        print("DEBUG: MySocialAccountAdapter 已載入！")
        super().__init__(*args, **kwargs)

    def _get_frontend_callback_url(self, request):
        """Use the configured frontend and retain only trusted next targets."""
        return _frontend_callback_url(request)

    def get_login_redirect_url(self, request, sociallogin):
        print("DEBUG: MySocialAccountAdapter.get_login_redirect_url 被調用！")
        return self._get_frontend_callback_url(request)

    def get_signup_redirect_url(self, request, sociallogin):
        print("DEBUG: MySocialAccountAdapter.get_signup_redirect_url 被調用！")
        return self._get_frontend_callback_url(request)

    def get_redirect_url(self, request):
        print("DEBUG: MySocialAccountAdapter.get_redirect_url 被調用！")
        return self._get_frontend_callback_url(request)
