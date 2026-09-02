"""
自訂認證類別
"""
from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    跨域環境下的 Session 認證（不檢查 CSRF）

    用於前後端分離的情況，前端域名與後端不同，
    無法正常獲取和發送 CSRF token。
    """
    def enforce_csrf(self, request):
        # 不執行 CSRF 檢查
        return
