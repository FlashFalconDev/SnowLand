# from rest_framework_simplejwt.views import TokenRefreshView
# from rest_framework.permissions import AllowAny
# from rest_framework_simplejwt.tokens import RefreshToken
# from rest_framework import status
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from django.db import transaction
# from datetime import datetime, date
# from rest_framework.decorators import api_view, permission_classes
# from django.contrib import auth
# from django.contrib.auth.models import User
# from rest_framework.exceptions import AuthenticationFailed
# from django.utils.timezone import make_aware
# # from manager.models import UserProfile
# import pytz
# from booking.models import Booking, MemberDetail, Reservation, Coach
# from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator

# @api_view(['GET', 'POST'])
# @permission_classes([AllowAny])
# def PassReturn(request):
#     try:
#         return Response({'code': 100, 'msg': '成功', 'data': {
#                         'ok': 'ok',
#                         }})
#     except MemberSignupPlatform.DoesNotExist:
#         return Response({'error': '無效的序號'}, status=status.HTTP_400_BAD_REQUEST)


# class LoginViewsManager(APIView):

#     permission_classes = [AllowAny]

#     def get(self, request):
#         print('LoginViewsManager.get')
#         next_url = request.GET.get('next', '')
#         return Response({
#             'code': 100,
#             'msg': '登入成功',
#             'data': {'next_url': next_url}})

#     def post(self, request):
#         print('LoginViewsManager')
#         client_sid = request.data.get('client_sid')
#         pword = request.data.get('pword', '')
#         # define = request.data.get('define')
#         user_pk = request.session.get('user_pk', False)

#         # Client_Info_F = ClientInfo.objects.filter(client_sid=client_sid)
        
#         return Response({
#             'code': 100,
#             'msg': '登入成功',
#             'data': {
#                 'name': 'eui',
#                 'icon': '',
#                 'refresh': '',
#                 'access': '',
#                 'ClientInfo': 1,
#             }})
#         if Client_Info_F:
#             Client_Info = Client_Info_F.first()
#             name = Client_Info.client_name
#             icon = ''
#             if not Client_Info.check_password(pword):
#                 Allow_List = ['LoginManager']
#                 if user_pk:
#                     User_Info = User.objects.get(pk=user_pk)
#                     Member_Info = User_Info.member_signup_platform.Member_Info
#                     CheckAllow_status = CheckAllow(
#                         Client_Info, Member_Info, Allow_List)
#                     print(CheckAllow_status)
#                     if not CheckAllow_status:
#                         return Response({
#                             'code': 400,
#                             'msg': '密碼錯誤'})

#                     try:
#                         refresh = RefreshToken.for_user(
#                             User_Info)
#                         access = refresh.access_token

#                         print('before is_authenticated',
#                               request.user.is_authenticated)
#                         auth.login(request, User_Info)
#                         request.session['manager'] = {
#                             'client_info_pk': Client_Info.pk}

#                         # if define == 'manager':
#                         return Response({
#                             'code': 100,
#                             'msg': '登入成功',
#                             'data': {
#                                 'name': name,
#                                 'icon': icon,
#                                 'refresh': str(refresh),
#                                 'access': str(access),
#                                 'ClientInfo': Client_Info.pk,
#                             }})
#                         # elif define == 'pos':
#                         #     return Response({
#                         #         'code': 999,
#                         #         'msg': '登入成功',
#                         #         'data': {
#                         #             'name': name,
#                         #             'icon': icon,
#                         #             'refresh': str(refresh),
#                         #             'access': str(access),
#                         #             'ClientInfo': Client_Info.pk,
#                         #             'url': 'https://yahoo.com.tw'
#                         #         }})

#                     except MemberSignupPlatform.DoesNotExist:
#                         return Response({'error': '無效的序號'}, status=status.HTTP_400_BAD_REQUEST)

#                 else:

#                     if Client_Info.password == pword:
#                         User_Info, _ = User.objects.get_or_create(
#                             username=client_sid+'_Manager')
#                         refresh = RefreshToken.for_user(
#                             User_Info)
#                         access = refresh.access_token
#                         auth.login(request, User_Info)
#                         request.session['manager'] = {
#                             'client_info_pk': Client_Info.pk}
#                         return Response({
#                             'code': 100,
#                             'msg': '登入成功',
#                             'data': {
#                                 'name': name,
#                                 'icon': icon,
#                                 'refresh': str(refresh),
#                                 'access': str(access),
#                                 'ClientInfo': Client_Info.pk,
#                             }})
#                     else:
#                         return Response({
#                             'code': 400,
#                             'msg': '密碼錯誤'})
#             else:
#                 User_Info, _ = User.objects.get_or_create(
#                     username=client_sid+'_Manager')
#                 refresh = RefreshToken.for_user(
#                     User_Info)
#                 access = refresh.access_token
#                 auth.login(request, User_Info)
#                 request.session['manager'] = {
#                     'client_info_pk': Client_Info.pk}
#                 # if define == 'manager':
#                 return Response({
#                     'code': 100,
#                     'msg': '登入成功',
#                     'data': {
#                         'name': name,
#                         'icon': icon,
#                         'refresh': str(refresh),
#                         'access': str(access),
#                         'ClientInfo': Client_Info.pk
#                     }})

#         else:
#             return Response({
#                 'code': 400,
#                 'msg': '無此帳號'})


# class CustomTokenRefreshView(TokenRefreshView):
#     def post(self, request, *args, **kwargs):
#         response = super().post(request, *args, **kwargs)
#         return response

# class CustomerInfoViewsManager(APIView):
#     def handle_exception(self, exc):
#         if isinstance(exc, AuthenticationFailed):
#             return Response({
#                 'code': 401,
#                 'msg': '已逾期,重新登入'
#             })
#         return super().handle_exception(exc)

#     @ transaction.atomic
#     def get(self, request, action_type):
#         print('CustomerInfoViewsManager')
#         try:
#             if action_type == 'get':
#                 users = User.objects.all()
#                 user_list = [{
#                     'pk': user.pk,
#                     'name': user.get_full_name(),
#                     'email': user.email,
#                     'img_pic': user.socialaccount_set.first().get_avatar_url() if user.socialaccount_set.exists() else 'https://fflinebotstatic.s3.ap-northeast-1.amazonaws.com/files/1/logo_inverse.png',
#                     'manager': 1 if user.userprofile.is_manager else 0,
#                     'coach': 1 if user.userprofile.is_coach else 0
#                 } for user in users]
#                 print(user_list)
#                 return Response({
#                     'code': 100,
#                     'msg': '取得成功',
#                     'data': {
#                         'count': len(user_list),
#                         'list': user_list
#                     }
#                 })
#             elif action_type == 'put':
#                 type_ = request.GET.get('type')
#                 pk = request.GET.get('pk', False)
#                 user = User.objects.get(pk=pk)
#                 user_profile= UserProfile.objects.get(user=user)
#                 if type_ == 'manager':
#                     manager = request.GET.get('manager', False)
#                     if manager == '0':
#                         user_profile.is_manager = False
#                     else:
#                         user_profile.is_manager = True
#                     user_profile.save()
#                 elif type_ == 'coach':
#                     coach = request.GET.get('coach', False)
#                     if coach == '0':
#                         user_profile.is_coach = False
#                     else:
#                         user_profile.is_coach = True
#                     user_profile.save()
#                 return Response({'code': 100, 'msg': '已修改'})
#             else:
#                 return Response({'code': 500, 'msg': '已逾期，請重新登入'})
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# class CoachViewsManager(APIView):

#     def handle_exception(self, exc):
#         if isinstance(exc, AuthenticationFailed):
#             return Response({
#                 'code': 401,
#                 'msg': '已逾期,重新登入'
#             })
#         return super().handle_exception(exc)

#     @method_decorator(csrf_exempt)
#     @transaction.atomic
#     def get(self, request, action_type):
#         try:
#             print('CoachViewsManager')
#             if action_type == 'get':
#                 coachs = Coach.objects.all()
#                 coach_list = [{
#                     'pk': coach.pk,
#                     'user': coach.user.get_full_name() if coach.user else '',
#                     'name': coach.name,
#                     'picture_url': coach.picture_url if coach.picture_url else 'https://fflinebotstatic.s3.ap-northeast-1.amazonaws.com/files/1/logo_inverse.png',
#                     'ski_resort': coach.get_resort_display(),
#                     'course_tags': coach.get_courses_display(),
#                     'language': coach.get_languages_display(),
#                     'availability_status': coach.availability_status,
#                     'availability_status_display': coach.get_availability_status_display(),
#                 } for coach in coachs]
#                 return Response({
#                     'code': 100,
#                     'msg': '取得成功',
#                     'data': {
#                         'count': len(coach_list),
#                         'list': coach_list
#                     }
#                 })
#             elif action_type == 'del':
#                 pk = request.GET.get('pk', False)
#                 Coach.objects.get(pk=pk).delete()
#                 return Response({'code': 100, 'msg': '已刪除'})
#             elif action_type == 'put':
#                 type_ = request.GET.get('type')
#                 pk = request.GET.get('pk', False)
#                 coach_ = Coach.objects.get(pk=pk)
#                 print(coach_)
#                 if type_ == 'availability_status':
#                     availability_status = request.GET.get('availability_status', 'active')
#                     # 驗證狀態值
#                     valid_statuses = ['active', 'passive', 'unavailable']
#                     if availability_status in valid_statuses:
#                         coach_.availability_status = availability_status
#                         coach_.save()
#                         return Response({'code': 100, 'msg': '已修改'})
#                     else:
#                         return Response({'code': 400, 'msg': '無效的狀態值'})
#                 else:
#                     return Response({'code': 500, 'msg': '已逾期，請重新登入'})
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
#     @method_decorator(csrf_exempt)
#     @transaction.atomic
#     def post(self, request, action_type):
#         print('CoachViewsManager.post')
#         data = request.data

#         # 获取表单数据
#         pk = data.get('pk', False)
#         name = data.get('name')
#         user_id = data.get('user_pk')
#         languages = data.getlist('languages')
#         resort = data.get('resort')
#         availability_status = data.get('availability_status', 'active')
#         picture_url = data.get('picture_url')
#         if picture_url == 'None':
#             picture_url = ''
#         courses = data.getlist('courses')

#         # 获取用户对象
#         user = User.objects.get(pk=user_id) if user_id else None
        
#         # 驗證狀態值
#         valid_statuses = ['active', 'passive', 'unavailable']
#         if availability_status not in valid_statuses:
#             availability_status = 'active'
            
#         # 创建或更新教练对象
#         if pk:
#             coach_instance = Coach.objects.get(pk=pk)
#             coach_instance.user = user
#             coach_instance.name = name
#             coach_instance.languages = languages
#             coach_instance.resort = resort
#             coach_instance.availability_status = availability_status
#             coach_instance.picture_url = picture_url
#             coach_instance.save()
#             return Response({'code': 100, 'msg': '已修改'})
#         else:
#             coach_instance = Coach.objects.create(
#                 user=user,
#                 name=name,
#                 languages=languages,
#                 resort=resort,
#                 availability_status=availability_status,
#                 picture_url=picture_url,
#                 courses=courses,
#             )
#             return Response({'code': 100, 'msg': '已新增'})
        
# class ReservationViewsManager(APIView):
#     def handle_exception(self, exc):
#         if isinstance(exc, AuthenticationFailed):
#             return Response({
#                 'code': 401,
#                 'msg': '已逾期,重新登入'
#             })
#         return super().handle_exception(exc)
    
#     @method_decorator(csrf_exempt)
#     @transaction.atomic
#     def get(self, request, action_type):
#         print('ReservationViewsManager')
#         user_pk = request.GET.get('user_pk', False)
#         if user_pk == 'all':
#             reservations = Reservation.objects.all()
#         else:
#             print('user_pk', user_pk)
#             coach_user_pk = Coach.objects.get(user=user_pk).pk
#             reservations = Reservation.objects.filter(preferred_coach=coach_user_pk)
#         print('reservations', reservations)
#         reservation_list = [{
#             'pk': reservation.pk,
#             'user': reservation.user.get_full_name(),
#             'is_preferred_coach': '是' if reservation.is_preferred_coach else '否',
#             'preferred_coach': reservation.preferred_coach.name if reservation.preferred_coach else '無排定教練',
#             'language': reservation.get_language_display(),
#             'resort': reservation.get_resort_display(),
#             'course_type': reservation.get_course_type_display(),
#             'status': reservation.get_status_display(),
#             'number_of_people': reservation.number_of_people,
#             # 'reservation_date': reservation.mdt_add.strftime('%Y-%m-%d'),
#         } for reservation in reservations]
#         return Response({
#             'code': 100,
#             'msg': '取得成功',
#             'data': {
#                 'count': len(reservation_list),
#                 'list': reservation_list
#             }
#         })


# class ScheduleViewsManager(APIView):
#     def handle_exception(self, exc):
#         if isinstance(exc, AuthenticationFailed):
#             return Response({
#                 'code': 401,
#                 'msg': '已逾期,重新登入'
#             })
#         return super().handle_exception(exc)
    
#     @method_decorator(csrf_exempt)
#     @transaction.atomic
#     def get(self, request, action_type=None):
#         if action_type is None:
#             return Response({'error': 'action_type is required'}, status=400)

#         print('ScheduleViewsManager')
#         pk = request.GET.get('user_pk', False)
#         if pk == 'all':
#             reservations = Reservation.objects.all()
#         else:
#             coach_user_pk = Coach.objects.get(user=pk).pk
#             reservations = Reservation.objects.filter(preferred_coach=coach_user_pk)
#         bookings = Booking.objects.filter(reservation__in=reservations)
        
#         # 将预订信息转换为指定格式
#         booking_list = [{
#             'title': f"{booking.course_name}",
#             'start': datetime.combine(booking.date, booking.start_time).strftime('%Y-%m-%dT%H:%M:%S'),
#             'end': datetime.combine(booking.date, booking.end_time).strftime('%Y-%m-%dT%H:%M:%S'),
#             "subtitle": f"{booking.reservation.user.get_full_name()} - {booking.reservation.preferred_coach.name if booking.reservation.preferred_coach else '無法排定教練'} {'(不指定)' if booking.reservation.preferred_coach and not booking.reservation.is_preferred_coach else ''}"
#         } for booking in bookings]

#         return Response({
#             'code': 100,
#             'msg': '取得成功',
#             'data': booking_list
#         })

# class MemberDetailInfoViewsManager(APIView):
#     def handle_exception(self, exc):
#         if isinstance(exc, AuthenticationFailed):
#             return Response({
#                 'code': 401,
#                 'msg': '已逾期,重新登入'
#             })
#         return super().handle_exception(exc)
    
#     @method_decorator(csrf_exempt)
#     @transaction.atomic
#     def post(self, request, action_type):
#         print('MemberDetailInfoViewsManager.post')
#         data = request.data
#         print('data', data)

#         # 假设数据是以 form-0-pk, form-1-pk 这样的格式传递
#         for key, value in data.items():
#             if key.startswith('form-') and key.endswith('-pk'):
#                 form_index = key.split('-')[1]
#                 pk = value
#                 age_range = data.get(f'form-{form_index}-age_range')
#                 snowboard_skills = data.getlist(f'form-{form_index}-snowboard_skills')
#                 ski_skills = data.getlist(f'form-{form_index}-ski_skills')

#                 # 更新或创建 MemberDetail
#                 try:
#                     member_detail = MemberDetail.objects.get(pk=pk)
#                     if member_detail.filled_by == 'user':
#                         # 如果 filled_by 是 'user'，创建新的记录
#                         MemberDetail.objects.create(
#                             user=member_detail.user,
#                             reservation=member_detail.reservation,
#                             filled_by='coach',
#                             age_range=age_range,
#                             snowboard_skills=snowboard_skills,
#                             ski_skills=ski_skills,
#                         )
#                     elif member_detail.filled_by == 'coach':
#                         # 如果 filled_by 是 'coach'，更新现有记录
#                         member_detail.age_range = age_range
#                         member_detail.snowboard_skills = snowboard_skills
#                         member_detail.ski_skills = ski_skills
#                         member_detail.save()
#                 except MemberDetail.DoesNotExist:
#                     return Response({'error': f'MemberDetail with pk {pk} does not exist'}, status=status.HTTP_400_BAD_REQUEST)

#         return Response({'code': 100, 'msg': '已更新'})

