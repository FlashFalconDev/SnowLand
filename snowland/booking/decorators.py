"""
租戶相關裝飾器
用於自動處理多租戶邏輯，讓 view 函數不用每次都手動處理
"""
from functools import wraps
from django.http import HttpResponse


def require_tenant(view_func):
    """
    裝飾器：要求請求必須有 tenant
    自動注入 tenant 和 client_code 到 view 函數的 kwargs 中

    使用方法：
    @require_tenant
    def my_view(request, client_code):
        # request.tenant 已經由 middleware 注入
        # client_code 參數會自動傳入
        tenant = request.tenant
        ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # 檢查 middleware 是否已注入 tenant
        tenant = getattr(request, 'tenant', None)
        client_code = getattr(request, 'client_code', None)

        if not tenant:
            return HttpResponse(
                '無法識別客戶。請訪問 <a href="/">首頁</a> 選擇客戶。',
                status=400
            )

        # 如果 view 函數需要 client_code 參數，自動傳入
        # （從 URL 參數中提取，或使用 request.client_code）
        if 'client_code' not in kwargs and client_code:
            kwargs['client_code'] = client_code

        return view_func(request, *args, **kwargs)

    return wrapper


def auto_filter_tenant(model_name=''):
    """
    裝飾器：自動過濾租戶資料
    在 view 函數執行前，自動注入已過濾的 queryset

    參數：
    - model_name: 模型名稱，用於錯誤訊息

    使用方法：
    @auto_filter_tenant('Coach')
    def coach_list(request, client_code):
        # request.tenant 已經由 middleware 注入
        # 直接使用，所有查詢都會自動過濾該 tenant
        coaches = Coach.objects.filter(client=request.tenant)
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tenant = getattr(request, 'tenant', None)

            if not tenant:
                return HttpResponse(
                    f'無法查詢 {model_name}：未指定客戶。',
                    status=400
                )

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
