from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import redirect

class MyAccountAdapter(DefaultAccountAdapter):
    def __init__(self, *args, **kwargs):
        print("DEBUG: MyAccountAdapter 已載入！")
        super().__init__(*args, **kwargs)

    def get_login_redirect_url(self, request):
        print("DEBUG: MyAccountAdapter.get_login_redirect_url 被調用！")
        # 檢查 'next' 參數是否存在於請求中
        next_url = request.GET.get('next')
        if next_url:
            return next_url
        # 🔥 自動判斷前端 URL
        referer = request.META.get('HTTP_REFERER', '')
        if 'ngrok.io' in referer:
            # 生產環境：從 referer 提取前端域名
            import re
            match = re.search(r'(https?://[^/]+)', referer)
            if match:
                return f"{match.group(1)}/auth/callback"
        # 開發環境：預設 localhost
        return "http://localhost:3000/auth/callback"

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
        """🔥 自動判斷前端回調 URL"""
        # 1. 優先使用 next 參數
        next_url = request.GET.get('next')
        if next_url:
            return next_url

        # 2. 從 referer 判斷前端域名
        referer = request.META.get('HTTP_REFERER', '')
        if 'ngrok.io' in referer:
            import re
            match = re.search(r'(https?://[^/]+)', referer)
            if match:
                return f"{match.group(1)}/auth/callback"

        # 3. 預設開發環境
        return "http://localhost:3000/auth/callback"

    def get_login_redirect_url(self, request, sociallogin):
        print("DEBUG: MySocialAccountAdapter.get_login_redirect_url 被調用！")
        return self._get_frontend_callback_url(request)

    def get_signup_redirect_url(self, request, sociallogin):
        print("DEBUG: MySocialAccountAdapter.get_signup_redirect_url 被調用！")
        return self._get_frontend_callback_url(request)

    def get_redirect_url(self, request):
        print("DEBUG: MySocialAccountAdapter.get_redirect_url 被調用！")
        return self._get_frontend_callback_url(request)
