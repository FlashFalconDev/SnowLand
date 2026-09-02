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
from django.urls import path, include
from booking.call_back import call_back
from django.http import HttpResponse
import traceback

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
    """
    首頁：顯示可用的客戶列表，讓用戶選擇
    """
    from Client.models import Client
    clients = Client.objects.filter(is_active=True)

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>選擇客戶</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            .client-list { list-style: none; padding: 0; }
            .client-list li {
                margin: 10px 0;
                padding: 15px;
                background: #f5f5f5;
                border-radius: 5px;
                transition: background 0.3s;
            }
            .client-list li:hover { background: #e0e0e0; }
            .client-list a {
                text-decoration: none;
                color: #1976d2;
                font-size: 18px;
                display: block;
            }
            .client-info { color: #666; font-size: 14px; margin-top: 5px; }
        </style>
    </head>
    <body>
        <h1>🏔️ Snowland 多租戶系統</h1>
        <p>請選擇您的客戶：</p>
        <ul class="client-list">
    """

    for client in clients:
        html += f"""
            <li>
                <a href="/booking/{client.internal_code}/">
                    <strong>{client.name}</strong> ({client.internal_code})
                    <div class="client-info">
                        業務：{client.sales or '未設定'} |
                        方案：{client.program or '未設定'}
                    </div>
                </a>
            </li>
        """

    html += """
        </ul>
    </body>
    </html>
    """

    return HttpResponse(html)


urlpatterns = [
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
