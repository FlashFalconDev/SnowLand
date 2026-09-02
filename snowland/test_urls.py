#!/usr/bin/env python
"""測試 Django URL 配置"""
import os
import sys
import django

# 設置 Django 環境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'snowland.settings')
django.setup()

from django.urls import resolve, reverse
from django.urls.exceptions import Resolver404

# 測試 URL 路徑
test_urls = [
    '/control/api/google-login/',
    '/control/api/logout/',
]

print("=" * 60)
print("測試 Django URL 配置")
print("=" * 60)

for url in test_urls:
    try:
        match = resolve(url)
        print(f"\n✅ {url}")
        print(f"   View: {match.func.__name__}")
        print(f"   App: {match.app_name}")
        print(f"   URL name: {match.url_name}")
    except Resolver404 as e:
        print(f"\n❌ {url}")
        print(f"   錯誤: {e}")

print("\n" + "=" * 60)
print("嘗試反向解析 URL")
print("=" * 60)

try:
    url = reverse('control:api_google_login')
    print(f"\n✅ control:api_google_login -> {url}")
except Exception as e:
    print(f"\n❌ control:api_google_login")
    print(f"   錯誤: {e}")
