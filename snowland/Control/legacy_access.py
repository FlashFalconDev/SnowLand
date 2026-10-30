"""Unscoped legacy management is platform-only; schools use the scoped Console."""
from functools import wraps
from django.http import JsonResponse


def platform_only(view):
    @wraps(view)
    def protected(request,*args,**kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'code':401,'msg':'請先登入'},status=401)
        if not request.user.is_superuser:
            return JsonResponse({'code':403,'msg':'舊版管理入口僅限平台管理者；請使用所屬學校的 Console。'},status=403)
        return view(request,*args,**kwargs)
    return protected
