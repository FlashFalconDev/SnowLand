from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from Member.models import MemberSignupPlatform
from rest_framework_simplejwt.tokens import RefreshToken


# class EmailPlatformBackend(ModelBackend):
#     def authenticate(self, request, username=None, password=None, platform=None, **kwargs):
#         if not username or not platform:
#             return None

#         try:
#             # 首先查找匹配的 MemberSignupPlatform
#             member_signup = MemberSignupPlatform.objects.get(
#                 email=username, Platform=platform)
#             user = member_signup.Member_Info.user if member_signup.Member_Info else None
#             if user and user.check_password(password):
#                 return user
#         except MemberSignupPlatform.DoesNotExist:
#             return None

#     def get_user(self, user_id):
#         try:
#             return User.objects.get(pk=user_id)
#         except User.DoesNotExist:
#             return None


# def Get_JWT_Token(dataDict):
#     uid = dataDict.get('uid')
#     platform = dataDict.get('platform')
#     print('Get_JWT_Token')
#     try:
#         Member_Signup_Platform = MemberSignupPlatform.objects.get(
#             uid=uid, Platform=platform)

#         user = Member_Signup_Platform.pk  # 假設 MemberInfo 有一個關聯的 User

#         # 生成 JWT token
#         refresh = RefreshToken.for_user(Member_Signup_Platform.user)

#         return str(refresh.access_token)
#         # return {
#         #     'refresh': str(refresh),
#         #     'access': str(refresh.access_token),
#         #     'user_id': user,
#         #     'platform': Member_Signup_Platform.Platform
#         # }

#     except MemberSignupPlatform.DoesNotExist:
#         return {'error': '無效的序號'}
