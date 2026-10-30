"""
URL configuration for snowland project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.db import DatabaseError, connection
from django.urls import path, include
from booking.call_back import call_back
from django.http import HttpResponse
import traceback


def healthz(request):
    try:
        connection.ensure_connection()
    except DatabaseError:
        response = HttpResponse('unavailable', status=503, content_type='text/plain')
    else:
        response = HttpResponse('ok', content_type='text/plain')
    response['Cache-Control'] = 'no-store'
    return response


def test_view(request):
    return HttpResponse("Hello, World!")

def debug_booking(request):
    try:
        # 尝试导入 booking 相关模块
        from booking import views
        from booking import models
        return HttpResponse("Booking 模块导入成功")
    except Exception as e:
        return HttpResponse(f"错误: {str(e)}<br>堆栈: {traceback.format_exc()}")


def landing_page(request):
    """The public backend root must not enumerate school/customer records."""
    return HttpResponse('<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>課程預約系統</title><h1>課程預約系統</h1><p>請使用學校提供的網站或預約連結。</p></html>')


urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    # ========== 豁免路徑（不需要 client_code）==========
    path("admin/", admin.site.urls),
    path("test/", test_view, name="test"),
    path('accounts/', include('allauth.urls')),  # allauth預設URLs，包含Google OAuth
    path('call_back/<str:tunnel>/', call_back, name='call_back'),

    # ========== 首頁 ==========
    path('', landing_page, name='landing'),

    # ========== 多租戶路由（client_code 在後面）==========
    path('booking/<str:client_code>/api/chat/', include('chatbooking.urls')),
    path('booking/', include('booking.urls')),  # 支持 /booking/<client_code>/
    path('control/', include('Control.urls')),  # 支持 /control/<client_code>/
    path('api/', include('API.urls')),          # 支持 /api/<client_code>/
]
