from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import mimetypes
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO
from rest_framework_simplejwt.views import TokenRefreshView
from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import qrcode
import io
import base64
from django.http import JsonResponse, HttpResponse
import json

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uid = request.data.get('uid')
        platform = request.data.get('platform')
        print('LoginView')
        try:
            # 嘗試根據序號找到對應的 MemberSignupPlatform 記錄
            Member_Signup_Platform = MemberSignupPlatform.objects.get(
                uid=uid, Platform=platform)

            user = Member_Signup_Platform.pk  # 假設 MemberInfo 有一個關聯的 User

            # 生成 JWT token
            refresh = RefreshToken.for_user(Member_Signup_Platform.user)

            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_id': user,
                'platform': Member_Signup_Platform.Platform
            })

        except MemberSignupPlatform.DoesNotExist:
            return Response({'error': '無效的序號'}, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenRefreshView(TokenRefreshView):
    # permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        print('CustomTokenRefreshView')
        print(*args, **kwargs)
        print(request.body)
        response = super().post(request, *args, **kwargs)
        # 如果需要，可以在這裡添加自定義邏輯
        return response

@csrf_exempt  # 如果需要，可以使用這個裝飾器來跳過 CSRF 檢查
def client_ip(request):
    if request.method == 'POST':
        # 檢查 CSRF token
        csrf_token = request.POST.get('csrf_token')
        # 在這裡驗證 CSRF token
        # 你的處理邏輯
        print(request.META.get('REMOTE_ADDR'), request)
        return JsonResponse({'status': 'success'})
    

