from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q, Exists, OuterRef
from django.db import transaction
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

from .models import UserProfile
from Control.funcNav import get_nav_list
from booking.models import ReservationGroup, Reservation, Payment, Booking
from Coach.models import Coach, CoachResort, CoachCourseLevel, CoachLeaveRequest
from Resorts.models import Resorts, ResortFee, EquipmentPricingTier, EquipmentAssistanceTimeSlot
from Coursekit.models import CourseCategory, CourseType as CoursekitCourseType, CourseTemplate as CoursekitCourseTemplate, CourseSession, CoursePricing, CoursePricingTier, SeasonSetting as CoursekitSeasonSetting

import time
import json
import pytz
import calendar as cal
from datetime import datetime, timedelta, date

# 註釋掉暫時未使用的 imports
# from CRM.models import ClientInfo, MemberCard
# from Item.models import ItemOrder, ItemOrderDetail
# from Member.views import logout

RUN_HOST = settings.RUN_HOST

def login_required_control(func):
    """
    驗證用戶登錄狀態的裝飾器
    - 檢查會話或 JWT，如果未登錄則根據請求類型返回錯誤或重定向
    - 從會話中提取 client_sid 並傳遞給視圖函數
    """
    def wrapper(request, *args, **kwargs):
        client_sid = None
        control_info = request.session.get('control')

        # 優先從 JWT token 獲取
        jwt_token = request.headers.get('jwt')
        if jwt_token:
            try:
                client_sid = jwt_token.split('|')[1]
                print(f'client_sid: {client_sid}')
            except IndexError:
                pass  # JWT 格式不正確

        # 如果 JWT 沒有，再從 session 獲取
        if not client_sid and control_info:
            client_sid = control_info.get('client_sid')
        
        # 如果還是沒有，則檢查 Django 的標準登入狀態 (for booking page)
        if not client_sid and request.user.is_authenticated:
            client_sid = request.user.email
            print(f'Authenticated via request.user: {client_sid}')

        # 如果用戶未登入，根據請求類型處理
        if not client_sid:
            # 對於 API (AJAX) 請求，返回 JSON 錯誤並提供登入 URL
            is_api_request = 'api/' in request.path or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if is_api_request:
                # 使用 Referer header 來決定登入後要跳轉回哪個頁面
                # 如果沒有 Referer，則預設跳轉回 booking 主頁
                referer = request.headers.get('Referer')
                next_url = referer or f"{RUN_HOST}/booking/"
                login_url = f"{RUN_HOST}/accounts/google/login/?next={next_url}"
                
                return JsonResponse({
                    'code': 401, 
                    'msg': 'Authentication required. Please log in.',
                    'login_url': login_url # 將登入 URL 返回給前端
                }, status=401)
            
            # 對於一般頁面瀏覽，重定向到登入頁面
            next_url = request.build_absolute_uri()
            login_url = f"{settings.RUN_HOST}/accounts/google/login/?next={next_url}"
            return redirect(login_url)

        try:
            # 獲取實際的User物件
            user = User.objects.get(email=client_sid)
            Client_Info = {
                'client_sid': client_sid,
                'user': user,
                'user_profile': user.userprofile
            }
        except (User.DoesNotExist, UserProfile.DoesNotExist):
            # 處理用戶不存在的情況
            Client_Info = {'client_sid': client_sid, 'user': None} # 確保 user 鍵存在
            
        kwargs['Client_Info'] = Client_Info
        return func(request, *args, **kwargs)
    
    return wrapper

def rate_color(before,after):
    print(f'before: {before}, after: {after}')
    
    if before == 0:
        rate = 0
    else:
        rate = round((after - before) / before*100,1)
    print(f'rate: {rate}')
    if rate > 0:
        rate_str = f'+{rate}%▴'
    else:
        rate_str = f'{rate}%▾'
            
    if rate > 0:
        return rate_str,'color-tag-green'
    else:
        return rate_str,'color-tag-red'

def tmp_page(request, page, page_name):
    print(f'tmp_page: {page}, {page_name}')
    if page == 'Item':
        item_type = request.GET.get('item_type')
        return render(request, f'Control/tmp/{page}/{item_type}/{page_name}', {'RUN_HOST': RUN_HOST})
    elif page == 'coach' and page_name == 'apply_leave.html':
        # 處理申請請假頁面
        try:
            # 檢查用戶是否登入
            control_info = request.session.get('control')
            if not control_info:
                # 用戶未登入，重定向到登入頁面
                return redirect('/control/')
            
            client_sid = control_info.get('client_sid')
            if not client_sid:
                return redirect('/control/')
                
            # 獲取當前登入用戶對應的教練
            user = User.objects.get(email=client_sid)
            coach = Coach.objects.get(user=user)
            
            # 獲取該教練的所有請假申請，按申請時間倒序
            leave_requests = CoachLeaveRequest.objects.filter(
                coach=coach
            ).order_by('-created_at')
            
            context = {
                'RUN_HOST': RUN_HOST,
                'coach': coach,
                'today': timezone.now().date(),
                'leave_requests': leave_requests,
            }
            return render(request, f'Control/tmp/{page}/{page_name}', context)
            
        except (User.DoesNotExist, Coach.DoesNotExist):
            # 如果不是教練，顯示錯誤信息並重定向
            messages.error(request, '您不是註冊教練，無法申請請假。請聯繫管理員。')
            return redirect('/control/')
        except Exception as e:
            print(f'Error in apply_leave tmp_page: {e}')
            messages.error(request, '系統錯誤，請稍後再試。')
            return redirect('/control/')
    elif page == 'coach' and page_name == 'leave_management.html':
        print("\n--- 執行 leave_management 邏輯 (from tmp_page) ---")
        try:
            # 檢查管理員權限
            control_info = request.session.get('control')
            if not control_info:
                return redirect('/control/')
            
            client_sid = control_info.get('client_sid')
            if not client_sid:
                return redirect('/control/')

            user = User.objects.get(email=client_sid)
            user_profile = user.userprofile
            if not user_profile.is_manager:
                messages.error(request, '您沒有權限訪問此頁面')
                return redirect('/control/')
        except (User.DoesNotExist, UserProfile.DoesNotExist):
            messages.error(request, '用戶權限設定不存在')
            return redirect('/')

        # 獲取搜索和篩選參數
        status_filter = request.GET.get('status', '')
        coach_search = request.GET.get('coach', '')
        date_range = request.GET.get('date_range', '')
        
        # 基礎查詢
        leave_requests = CoachLeaveRequest.objects.select_related('coach', 'reviewed_by').all()
        
        # 應用篩選條件
        if status_filter:
            leave_requests = leave_requests.filter(status=status_filter)
        if coach_search:
            leave_requests = leave_requests.filter(coach__name__icontains=coach_search)
        if date_range:
            try:
                start_date, end_date = date_range.split(' - ')
                leave_requests = leave_requests.filter(
                    start_date__gte=start_date,
                    end_date__lte=end_date
                )
            except ValueError:
                pass
        
        # 按申請時間倒序排列
        leave_requests = leave_requests.order_by('-created_at')
        
        # 統計資料
        stats = {
            'total': CoachLeaveRequest.objects.count(),
            'pending': CoachLeaveRequest.objects.filter(status='pending').count(),
            'approved': CoachLeaveRequest.objects.filter(status='approved').count(),
            'rejected': CoachLeaveRequest.objects.filter(status='rejected').count(),
        }
        
        context = {
            'leave_requests': leave_requests,
            'stats': stats,
            'status_filter': status_filter,
            'coach_search': coach_search,
            'date_range': date_range,
            'status_choices': CoachLeaveRequest.STATUS_CHOICES,
            'RUN_HOST': RUN_HOST,
        }
        return render(request, f'Control/tmp/{page}/{page_name}', context)
    else:
        return render(request, f'Control/tmp/{page}/{page_name}', {'RUN_HOST': RUN_HOST})

def login(request):
    print('login')
    return render(request, 'control/index.html', {'RUN_HOST': RUN_HOST})

@csrf_exempt
def api_google_login(request):
    """Google 登入後的處理邏輯 - 前端 JWT 驗證版本"""
    print('=== api_google_login 被調用 ===')
    print(f'Request method: {request.method}')
    print(f'Request body: {request.body}')

    # 🔥 支援兩種登入方式：
    # 1. 前端發送 Google JWT token (前後端分離)
    # 2. Django allauth 已登入 (傳統方式)

    if request.method == 'POST':
        # 🔥 檢查是否有 request body 和 credential
        import json
        credential = None

        if request.body:
            try:
                body = json.loads(request.body)
                print(f'Parsed body: {body}')
                credential = body.get('credential')
            except json.JSONDecodeError:
                print('No JSON body or empty body, will check session instead')

        # 方式 1: 前端發送 Google JWT credential
        if credential:
            print('Found credential in body, verifying...')
            try:
                from google.oauth2 import id_token
                from google.auth.transport import requests as google_requests

                # 🔥 驗證 Google JWT token
                GOOGLE_CLIENT_ID = "754789081671-np8lbocgau68d4rers83v649bnm993vp.apps.googleusercontent.com"

                idinfo = id_token.verify_oauth2_token(
                    credential,
                    google_requests.Request(),
                    GOOGLE_CLIENT_ID
                )

                # 獲取用戶資訊
                email = idinfo.get('email')
                name = idinfo.get('name')
                picture = idinfo.get('picture')

                if not email:
                    return JsonResponse({'code': 400, 'msg': 'Google token 中缺少 email'})

                # 獲取或創建 Django User
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'username': email,
                        'first_name': name.split()[0] if name else '',
                        'last_name': name.split()[-1] if name and len(name.split()) > 1 else '',
                    }
                )

                # 🔥 確保 UserProfile 存在
                user_profile, profile_created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'is_manager': False,
                        'is_coach': False,
                    }
                )

                # 檢查權限
                if not (user_profile.is_manager or user_profile.is_coach):
                    return JsonResponse({
                        'code': 403,
                        'msg': '您沒有權限訪問此系統，請聯繫管理員開通權限。\n首次登入需要管理員設定權限。'
                    })

                # 設置 session (登入用戶)
                from django.contrib.auth import login
                # 🔥 指定 backend 以避免多重認證後端錯誤
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)

                # 設置 Control 面板的會話資訊
                request.session['control'] = {'client_sid': email, 'timestamp': time.time()}

                # 生成 JWT token
                jwt_token = f'1|{email}'

                return JsonResponse({
                    'code': 100,
                    'msg': '登入成功',
                    'data': {
                        'email': email,
                        'name': name,
                        'picture': picture,
                        'jwt': jwt_token,
                    },
                    'jwt': jwt_token,
                })

            except Exception as e:
                print(f'=== Google token 驗證失敗 ===')
                print(f'Error type: {type(e).__name__}')
                print(f'Error message: {str(e)}')
                import traceback
                traceback.print_exc()
                return JsonResponse({'code': 400, 'msg': f'Google token 驗證失敗: {str(e)}'})

    # 方式 2: 傳統 Django allauth 登入
    if not request.user.is_authenticated:
        return JsonResponse({'code': 400, 'msg': '請先完成 Google 登入'})

    # 檢查權限
    try:
        user_profile = request.user.userprofile
        if not (user_profile.is_manager or user_profile.is_coach):
            return JsonResponse({
                'code': 403,
                'msg': '您沒有權限訪問此系統，請聯繫管理員開通權限'
            })
    except UserProfile.DoesNotExist:
        return JsonResponse({
            'code': 403,
            'msg': '用戶權限未設定，請聯繫管理員'
        })

    # 使用 Google 用戶的 email 作為 client_sid
    client_sid = request.user.email
    name = request.user.get_full_name() or request.user.first_name or request.user.email

    # 獲取用戶頭像
    picture = ''
    if request.user.socialaccount_set.exists():
        social_account = request.user.socialaccount_set.first()
        picture = social_account.get_avatar_url()

    # 設置 Control 面板的會話資訊
    request.session['control'] = {'client_sid': client_sid, 'timestamp': time.time()}

    # 生成 JWT token
    jwt_token = f'1|{client_sid}'

    return JsonResponse({
        'code': 100,
        'msg': '登入成功',
        'data': {
            'email': client_sid,
            'name': name,
            'picture': picture,
            'jwt': jwt_token,
        },
        'jwt': jwt_token,
    })

@login_required_control
def nav(request, Client_Info=None):
    print('nav')
    user_profile = Client_Info.get('user_profile')
    if user_profile:
        nav_list = get_nav_list(user_profile)
        data = {'list': nav_list}
        return JsonResponse({'code': 100, 'msg': '取得成功', 'data': data})
    else:
        return JsonResponse({'code': 404, 'msg': '用戶權限設定不存在'})

#處理下載時 丟失範圍
def get_page_size(request):
    if request.GET.get('export', False):
        page = False
        page_size = False
    else:
        # 修復Bug：正確處理沒有page和size參數的情況
        page_param = request.GET.get('page')
        size_param = request.GET.get('size')
        
        page = int(page_param) if page_param else None
        page_size = int(size_param) if size_param else None
        
    if not page:
        page = request.session.get('control',{}).get('page', 1)
    if not page_size:
        page_size = request.session.get('control',{}).get('page_size', 10)
        
    # 確保session存在control鍵
    if 'control' not in request.session:
        request.session['control'] = {}
        
    request.session['control']['page'] = page
    request.session['control']['page_size'] = page_size
    
    # 確保 session 變更被保存
    request.session.modified = True
    
    return page, page_size


@login_required_control
def member_list(request, Client_Info=None):
    """
    獲取用戶列表，僅包含基本資料
    """
    print('member_list')
    
    page, page_size = get_page_size(request)
    
    # 獲取搜索條件
    name_search = request.GET.get('name')
    email_search = request.GET.get('email')
    
    # 創建基本查詢集
    query = User.objects.all()
    
    # 添加篩選條件
    if name_search:
        query = query.filter(Q(username__icontains=name_search) | 
                             Q(first_name__icontains=name_search) | 
                             Q(last_name__icontains=name_search))
    if email_search:
        query = query.filter(email__icontains=email_search)
        
    # 計算符合條件的總數量
    count = query.count()
    
    # 排序並分頁
    users = query.order_by('-date_joined')[(page-1)*page_size:page*page_size]
    
    # 準備返回的數據
    user_list = []
    for user in users:
        is_manager = False
        try:
            # 檢查用戶是否是管理者
            if hasattr(user, 'userprofile') and user.userprofile.is_manager:
                is_manager = True
        except UserProfile.DoesNotExist:
            pass # 沒有 profile 的用戶不是管理者

        user_list.append({
            "RUN_HOST": RUN_HOST,
            "id": user.pk,
            "name": user.get_full_name() or user.username,
            "email": user.email,
            "date_joined": user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
            "is_manager": is_manager,
            "is_coach": user.userprofile.is_coach if hasattr(user, 'userprofile') else False,
            "power": 1  # 添加權限欄位，讓前端的設定按鈕正常顯示
        })

    return JsonResponse({
        'code': 100,
        'msg': '取得成功',
        'data': {
            'count': count,
            'list': user_list
        }
    })

@login_required_control
def member_permission(request, Client_Info=None):
    """
    處理用戶權限設定（管理者和教練）
    GET: 顯示設定頁面
    POST: 更新權限
    """
    if request.method == 'POST':
        try:
            # 檢查 request.body 是否為空
            if not request.body:
                return JsonResponse({'code': 400, 'msg': '請求數據為空'})
            
            # 添加調試信息
            print(f'request.body: {request.body}')
            print(f'request.content_type: {request.content_type}')
            
            # 根據 Content-Type 解析數據
            if request.content_type == 'application/json':
                # JSON 格式
                try:
                    data = json.loads(request.body)
                    user_id = data.get('id')
                    is_manager = data.get('is_manager', False)
                    is_coach = data.get('is_coach', False)
                except json.JSONDecodeError as e:
                    print(f'JSON 解析錯誤: {e}')
                    return JsonResponse({'code': 400, 'msg': f'數據格式錯誤: {str(e)}'})
            else:
                # 表單格式 (application/x-www-form-urlencoded)
                user_id = request.POST.get('user_id')
                is_manager = request.POST.get('is_manager') == 'on'  # checkbox 選中時值為 'on'
                is_coach = request.POST.get('is_coach') == 'on'  # checkbox 選中時值為 'on'
            
            print(f'解析後的數據: user_id={user_id}, is_manager={is_manager}, is_coach={is_coach}')

            # 驗證用戶ID
            if not user_id:
                return JsonResponse({'code': 400, 'msg': '缺少用戶ID參數'})

            user = User.objects.get(pk=user_id)
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            profile.is_manager = is_manager
            profile.is_coach = is_coach
            profile.save()
            
            return JsonResponse({'code': 100, 'msg': '權限設定儲存成功'})
        except User.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '用戶不存在'})
        except Exception as e:
            print(f'member_permission error: {e}')
            return JsonResponse({'code': 500, 'msg': f'更新失敗: {str(e)}'})

    # GET request
    user_id = request.GET.get('id')
    if not user_id:
        return JsonResponse({'code': 400, 'msg': '缺少用戶ID參數'})

    try:
        user = User.objects.get(pk=user_id)
        profile, created = UserProfile.objects.get_or_create(user=user)
        context = {
            'user': user,
            'profile': profile,
            'RUN_HOST': RUN_HOST
        }
        return render(request, 'Control/tmp/Member/member_permission.html', context)
    except User.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '用戶不存在'})

@login_required_control
def upload_image(request, type,Client_Info=None):
    print('upload_image')
    if type == 'item':
        item_id = request.POST.get('item_id')
        print(request.POST.items())
        return JsonResponse({'code': 100, 'msg': '取得成功'})
    else:
        return JsonResponse({'code': 400, 'msg': '錯誤'})

@login_required_control
def all_course_info(request, Client_Info=None):
    """
    獲取預約群組資訊列表，以ReservationGroup為主要單位，包含Payment和Reservation資料
    """
    print('all_course_info')
    
    page, page_size = get_page_size(request)
    
    # 獲取搜索條件
    user_name_search = request.GET.get('user_name')
    payment_status_search = request.GET.get('payment_status')
    reservation_status_search = request.GET.get('reservation_status')
    coach_name_search = request.GET.get('coach_name')
    date_search = request.GET.get('date')
    
    # 創建基本查詢集 - 查詢ReservationGroup並關聯相關資料
    query = ReservationGroup.objects.select_related('user').prefetch_related(
        'reservations',
        'reservations__preferred_coach',
        'reservations__bookings',
        'payments'
    ).all()
    
    # 排除軟刪除的預約群組（即所有預約都是已取消狀態的群組）
    # 只顯示至少有一個未取消預約的群組
    query = query.filter(
        Exists(
            Reservation.objects.filter(
                group=OuterRef('pk')
            ).exclude(status='deleted')
        )
    )
    
    if user_name_search:
        query = query.filter(
            Q(user__username__icontains=user_name_search) |
            Q(user__first_name__icontains=user_name_search) |
            Q(user__last_name__icontains=user_name_search) |
            Q(name__icontains=user_name_search)
        )
        
    if payment_status_search:
        query = query.filter(payments__status=payment_status_search)
        
    if reservation_status_search:
        query = query.filter(reservations__status=reservation_status_search)
        
    if coach_name_search:
        query = query.filter(reservations__preferred_coach__name__icontains=coach_name_search)
        
    if date_search:
        query = query.filter(reservations__bookings__date=date_search)
        
    # 去重並計算總數量
    query = query.distinct()
    count = query.count()
    
    # 排序並分頁
    reservation_groups = query.order_by('-created_at')[(page-1)*page_size:page*page_size]
    
    # 準備返回的數據
    course_list = []
    for group in reservation_groups:
        user = group.user
        
        # 處理用戶名稱顯示
        if user:
            user_display = user.get_full_name() or user.username
            user_email = user.email
        elif group.name:
            user_display = group.name
            user_email = ''
        else:
            user_display = '未知用戶'
            user_email = ''
        
        # 獲取付款資訊
        latest_payment = group.payments.first()
        payment_status = latest_payment.status if latest_payment else 'unpaid'
        payment_status_display = latest_payment.get_status_display() if latest_payment else '未付款'
        payment_method = latest_payment.payment_method if latest_payment else ''
        payment_method_display = latest_payment.get_payment_method_display() if latest_payment else ''
        
        # 統計預約資訊
        reservations = group.reservations.all()
        total_reservations = reservations.count()
        total_people = sum(r.number_of_people for r in reservations)
        total_fee = sum(r.total_fee for r in reservations)
        
        # 獲取預約狀態統計
        status_counts = {}
        course_types = set()
        coaches = set()
        booking_dates = set()
        
        for reservation in reservations:
            # 統計狀態
            status = reservation.status
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
            
            # 收集課程類型
            try:
                if reservation.course_type:
                    course_types.add(reservation.get_course_type_display())
            except Exception:
                # 如果課程類型不存在，跳過
                pass
            
            # 收集教練
            if reservation.preferred_coach:
                coaches.add(reservation.preferred_coach.name)
            
            # 收集預約日期
            for booking in reservation.bookings.all():
                booking_dates.add(booking.date)
        
        # 生成狀態摘要
        status_summary = []
        for status, status_count in status_counts.items():
            status_display = dict(Reservation.STATUS_CHOICES).get(status, '未知')
            status_summary.append(f"{status_display}({status_count})")
        
        course_list.append({
            "RUN_HOST": RUN_HOST,
            "id": group.pk,
            "user_display": user_display,
            "user_email": user_email,
            "total_reservations": total_reservations,
            "total_people": total_people,
            "total_fee": total_fee,
            "course_types": ', '.join(course_types) if course_types else '無',
            "coaches": ', '.join(coaches) if coaches else '無',
            "booking_dates": ', '.join([d.strftime('%m/%d') for d in sorted(booking_dates)]) if booking_dates else '無',
            "status_summary": ', '.join(status_summary),
            "payment_status": payment_status,
            "payment_status_display": payment_status_display,
            "payment_method": payment_method,
            "payment_method_display": payment_method_display,
            "power": 1  # 添加權限欄位，讓前端的設定按鈕正常顯示
        })

    return JsonResponse({
        'code': 100,
        'msg': '取得成功',
        'data': {
            'count': count,
            'list': course_list
        }
    })

@login_required_control
def all_course_permission(request, Client_Info=None):
    """
    處理預約群組設定，包含付款確認等後台操作
    GET: 顯示設定頁面
    POST: 更新預約群組資訊或執行排課
    """
    if request.method == 'POST':
        try:
            # 優先處理 FormData 格式
            if request.content_type and 'application/x-www-form-urlencoded' in request.content_type:
                # FormData 格式
                group_id = request.POST.get('group_id')
                action = request.POST.get('action', 'save')
                payment_status = request.POST.get('payment_status')
                
                # 解析預約更新數據 - 新格式：reservation_123_coach
                reservation_updates = []
                reservation_updates_json = request.POST.get('reservation_updates_final')
                
                if reservation_updates_json:
                    # 舊格式：從隱藏欄位解析 JSON
                    try:
                        reservation_updates = json.loads(reservation_updates_json)
                    except json.JSONDecodeError as e:
                        print(f'解析預約更新數據失敗: {e}')
                else:
                    # 新格式：從 coach_ID 欄位解析
                    for key, value in request.POST.items():
                        if key.startswith('coach_') and key != 'coach_id':
                            # 從 coach_123 中提取 123
                            reservation_id = key.replace('coach_', '')
                            coach_id = value if value else None
                            
                            reservation_updates.append({
                                'reservation_id': reservation_id,
                                'coach_id': coach_id
                            })
                            
            elif request.content_type == 'application/json':
                # JSON 格式（保留兼容性）
                try:
                    data = json.loads(request.body)
                    group_id = data.get('id')
                    action = data.get('action', 'save')
                    payment_status = data.get('payment_status')
                    reservation_updates = data.get('reservation_updates', [])
                except json.JSONDecodeError as e:
                    print(f'JSON 解析錯誤: {e}')
                    return JsonResponse({'code': 400, 'msg': f'數據格式錯誤: {str(e)}'})
            else:
                return JsonResponse({'code': 400, 'msg': '不支援的內容類型'})

            # 驗證預約群組ID
            if not group_id:
                return JsonResponse({'code': 400, 'msg': '缺少預約群組ID參數'})

            group = ReservationGroup.objects.get(pk=group_id)
            
            # 更新付款狀態
            if payment_status:
                payment, created = Payment.objects.get_or_create(
                    reservation_group=group,
                    defaults={'status': payment_status}
                )
                if not created:
                    payment.status = payment_status
                    payment.save()
            
            # 處理預約更新
            coach_changes = []  # 記錄教練變更的預約
            
            for update in reservation_updates:
                reservation_id = update.get('reservation_id')
                new_coach_id = update.get('coach_id')
                
                if reservation_id:
                    try:
                        reservation = group.reservations.get(pk=reservation_id)
                        old_coach_id = reservation.preferred_coach_id
                        
                        # 檢查教練是否有變更
                        if str(old_coach_id) != str(new_coach_id):
                            coach_changes.append({
                                'reservation': reservation,
                                'old_coach_id': old_coach_id,
                                'new_coach_id': new_coach_id
                            })
                        
                    except (Reservation.DoesNotExist, Coach.DoesNotExist) as e:
                        print(f'處理預約 {reservation_id} 時出錯: {e}')
                        pass
            
            # 根據動作類型處理
            if action == 'save':
                # 僅保存，不執行排課
                for change in coach_changes:
                    reservation = change['reservation']
                    new_coach_id = change['new_coach_id']
                    
                    if new_coach_id:
                        coach = Coach.objects.get(pk=new_coach_id)
                        reservation.preferred_coach = coach
                        # 變更為人工指定教練狀態
                        if reservation.status in ['created', 'auto_assigned']:  # 待排課或已排課
                            reservation.status = 'manually_assigned'  # 人工指定教練
                    else:
                        reservation.preferred_coach = None
                        # 變更為待排課狀態
                        if reservation.status in ['auto_assigned', 'manually_assigned']:
                            reservation.status = 'created'  # 待排課
                    
                    reservation.save()
                
                return JsonResponse({'code': 100, 'msg': '保存成功'})
                
            elif action == 'schedule':
                # 嘗試排課
                if not coach_changes:
                    return JsonResponse({'code': 100, 'msg': '沒有教練變更，無需排課'})
                
                # 備份原始狀態
                backup_data = []
                for change in coach_changes:
                    reservation = change['reservation']
                    backup_data.append({
                        'reservation_id': reservation.id,
                        'old_coach_id': change['old_coach_id'],
                        'old_status': reservation.status,
                        'old_bookings_scheduled': [(b.id, b.is_scheduled) for b in reservation.bookings.all()]
                    })
                
                try:
                    # 先應用教練變更
                    for change in coach_changes:
                        reservation = change['reservation']
                        new_coach_id = change['new_coach_id']
                        
                        if new_coach_id:
                            coach = Coach.objects.get(pk=new_coach_id)
                            reservation.preferred_coach = coach
                            # 設為人工指定教練狀態
                            reservation.status = 'manually_assigned'  # 人工指定教練
                        else:
                            reservation.preferred_coach = None
                            # 設為待排課狀態
                            reservation.status = 'created'  # 待排課
                        
                        reservation.save()
                    
                    # 導入排課模組並執行排課
                    try:
                        from booking.scheduler import assign_coachs
                        
                        schedule_success = assign_coachs()
                        
                        if schedule_success:
                            return JsonResponse({
                                'code': 100, 
                                'msg': f'排課成功！已更新 {len(coach_changes)} 筆預約的教練指派。'
                            })
                        else:
                            # 排課失敗，恢復原始狀態
                            for backup in backup_data:
                                reservation = Reservation.objects.get(pk=backup['reservation_id'])
                                
                                # 恢復教練
                                if backup['old_coach_id']:
                                    old_coach = Coach.objects.get(pk=backup['old_coach_id'])
                                    reservation.preferred_coach = old_coach
                                else:
                                    reservation.preferred_coach = None
                                
                                # 恢復其他狀態
                                reservation.status = backup['old_status']
                                reservation.save()
                                
                                # 恢復booking的排課狀態
                                for booking_id, old_scheduled in backup['old_bookings_scheduled']:
                                    booking = Booking.objects.get(pk=booking_id)
                                    booking.is_scheduled = old_scheduled
                                    booking.save()
                            
                            return JsonResponse({
                                'code': 400, 
                                'msg': '排課失敗，教練指派或時間衝突，已恢復原始狀態。請檢查教練可用性或重新安排時間。'
                            })
                            
                    except ImportError:
                        print('無法導入排課模組')
                        # 恢復原始狀態
                        for backup in backup_data:
                            reservation = Reservation.objects.get(pk=backup['reservation_id'])
                            if backup['old_coach_id']:
                                old_coach = Coach.objects.get(pk=backup['old_coach_id'])
                                reservation.preferred_coach = old_coach
                            else:
                                reservation.preferred_coach = None
                            reservation.status = backup['old_status']
                            reservation.save()
                        
                        return JsonResponse({'code': 500, 'msg': '排課模組無法載入，請聯繫技術人員'})
                    
                except Exception as e:
                    print(f'排課過程發生錯誤: {e}')
                    
                    # 恢復原始狀態
                    try:
                        for backup in backup_data:
                            reservation = Reservation.objects.get(pk=backup['reservation_id'])
                            if backup['old_coach_id']:
                                old_coach = Coach.objects.get(pk=backup['old_coach_id'])
                                reservation.preferred_coach = old_coach
                            else:
                                reservation.preferred_coach = None
                            reservation.status = backup['old_status']
                            reservation.save()
                    except Exception as restore_error:
                        print(f'恢復狀態時發生錯誤: {restore_error}')
                    
                    return JsonResponse({'code': 500, 'msg': f'排課過程發生錯誤: {str(e)}'})
            
            else:
                return JsonResponse({'code': 400, 'msg': f'未知的動作類型: {action}'})
            
        except ReservationGroup.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '預約群組不存在'})
        except Exception as e:
            print(f'course_permission error: {e}')
            import traceback
            traceback.print_exc()
            return JsonResponse({'code': 500, 'msg': f'更新失敗: {str(e)}'})

    # GET request
    group_id = request.GET.get('id')
    if not group_id:
        return JsonResponse({'code': 400, 'msg': '缺少預約群組ID參數'})

    try:
        group = ReservationGroup.objects.select_related('user').prefetch_related(
            'reservations',
            'reservations__preferred_coach',
            'reservations__bookings',
            'payments'
        ).get(pk=group_id)
        
        # 獲取所有教練
        coaches = Coach.objects.filter(availability_status__in=['active', 'passive'])
        
        context = {
            'group': group,
            'reservations': group.reservations.all(),
            'latest_payment': group.payments.first(),
            'status_choices': Reservation.STATUS_CHOICES,
            'payment_status_choices': Payment.STATUS_CHOICES,
            'coaches': coaches,
            'RUN_HOST': RUN_HOST
        }
        return render(request, 'Control/tmp/course/all_course_permission.html', context)
    except ReservationGroup.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '預約群組不存在'})

@login_required_control
def coach_courses(request, Client_Info=None):
    """
    獲取教練專用的課程列表，只顯示該教練的預約課程
    以Reservation為主要單位，不是整個ReservationGroup
    """
    print('coach_courses')
    
    page, page_size = get_page_size(request)
    
    # 獲取當前登入用戶對應的教練
    current_user = Client_Info.get('user')
    if not current_user:
        return JsonResponse({'code': 403, 'msg': '用戶信息不存在'})
    
    try:
        coach = Coach.objects.get(user=current_user)
    except Coach.DoesNotExist:
        # 檢查是否有其他教練有關聯的用戶
        coaches_with_users = Coach.objects.filter(user__isnull=False)
        
        return JsonResponse({
            'code': 403, 
            'msg': f'您({current_user.email})不是註冊教練，無法查看課程資訊。請聯繫管理員將您的帳號關聯到教練檔案。',
            'debug_info': {
                'current_user': current_user.email,
                'coaches_with_users': [f"{c.name}({c.user.email})" for c in coaches_with_users]
            }
        })
    
    # 獲取搜索條件
    user_name_search = request.GET.get('user_name')
    course_type_search = request.GET.get('course_type')
    status_search = request.GET.get('status')
    date_search = request.GET.get('date')
    
    # 創建基本查詢集 - 查詢Reservation並過濾該教練的課程
    query = Reservation.objects.select_related(
        'group',
        'group__user',
        'preferred_coach'
    ).prefetch_related(
        'bookings'
    ).filter(
        preferred_coach=coach  # 只顯示該教練的課程
    ).exclude(
        status='deleted'  # 排除狀態為'deleted'的預約
    )
    
    # 添加篩選條件
    if user_name_search:
        query = query.filter(
            Q(group__user__username__icontains=user_name_search) |
            Q(group__user__first_name__icontains=user_name_search) |
            Q(group__user__last_name__icontains=user_name_search) |
            Q(group__name__icontains=user_name_search)
        )
    if course_type_search:
        query = query.filter(course_type=course_type_search)
    if status_search:
        query = query.filter(status=int(status_search))
    if date_search:
        # 解析日期範圍
        try:
            start_date, end_date = date_search.split(' - ')
            query = query.filter(bookings__date__gte=start_date, bookings__date__lte=end_date)
        except:
            pass
        
    # 去重並計算總數量
    query = query.distinct()
    count = query.count()
    
    # 排序並分頁 - 修復字段名
    reservations = query.order_by('-mdt_add')[(page-1)*page_size:page*page_size]
    
    # 準備返回的數據
    course_list = []
    for reservation in reservations:
        group = reservation.group
        user = group.user
        
        # 處理用戶名稱顯示
        if user:
            user_display = user.get_full_name() or user.username
            user_email = user.email
        elif group.name:
            user_display = group.name
            user_email = ''
        else:
            user_display = '未知用戶'
            user_email = ''
        
        # 獲取課程時段資訊並計算課程堂數
        bookings = reservation.bookings.all()
        booking_dates = []
        booking_times = []
        
        # 計算課程堂數 - 特別處理全天5小時課程
        lesson_count = 0
        daily_bookings = {}  # 按日期分組
        
        for booking in bookings:
            date_str = booking.date.strftime('%Y-%m-%d')
            if date_str not in daily_bookings:
                daily_bookings[date_str] = []
            daily_bookings[date_str].append(booking)
            
            booking_dates.append(booking.date.strftime('%m/%d'))
            booking_times.append(f"{booking.start_time.strftime('%H:%M')}-{booking.end_time.strftime('%H:%M')}")
        
        # 計算每日的課程堂數
        for date_str, day_bookings in daily_bookings.items():
            if len(day_bookings) >= 2:
                # 檢查是否為全天5小時課程（兩個時段）
                total_hours = 0
                for booking in day_bookings:
                    start_time = booking.start_time
                    end_time = booking.end_time
                    # 計算時長（小時）
                    duration = (end_time.hour - start_time.hour) + (end_time.minute - start_time.minute) / 60.0
                    total_hours += duration
                
                # 如果當日總時長接近5小時，算作1堂全天課程
                if 4.5 <= total_hours <= 5.5:
                    lesson_count += 1
                else:
                    # 否則按時段數計算
                    lesson_count += len(day_bookings)
            else:
                # 單個時段直接計算
                lesson_count += len(day_bookings)
        
        # 處理建立時間 - 使用正確的字段
        created_at_display = reservation.mdt_add.strftime('%Y-%m-%d %H:%M') if reservation.mdt_add else '未知時間'
        
        # 安全獲取 course_type 信息
        try:
            course_type_id = reservation.course_type.id if reservation.course_type else None
            course_type_name = reservation.course_type.name if reservation.course_type else "未知課程"
        except Exception:
            course_type_id = None
            course_type_name = "未知課程"
        
        course_list.append({
            "RUN_HOST": RUN_HOST,
            "id": reservation.pk,
            "user_display": user_display,
            "user_email": user_email,
            "course_type": course_type_id,
            "course_type_name": course_type_name,
            "course_type_display": reservation.get_course_type_display(),
            "equipment_display": reservation.get_equipment_display() if hasattr(reservation, 'get_equipment_display') else '未設定',
            "equipment_assistance_time_display": reservation.get_equipment_assistance_time_display(),
            "language_display": reservation.get_language_display(),
            "resort_display": reservation.get_resort_display(),
            "max_ability_level_display": reservation.get_max_ability_level_display() if hasattr(reservation, 'get_max_ability_level_display') else '未設定',
            "number_of_people": reservation.number_of_people,
            "lesson_count": lesson_count,
            "booking_dates": ', '.join(booking_dates) if booking_dates else '無',
            "booking_times": ', '.join(booking_times) if booking_times else '無',
            "status": reservation.status,
            "status_display": reservation.get_status_display(),
            "total_fee": reservation.total_fee,
            "created_at": created_at_display,
            "power": 1  # 添加權限欄位，讓前端的設定按鈕正常顯示
        })

    return JsonResponse({
        'code': 100,
        'msg': '取得成功',
        'data': {
            'count': count,
            'list': course_list
        },
        'debug_info': {
            'coach_name': coach.name,
            'coach_id': coach.id,
            'total_reservations': count
        }
    })

@login_required_control
def reservation_detail(request, Client_Info=None):
    """
    顯示單個預約的詳細資料
    """
    print('reservation_detail')
    
    reservation_id = request.GET.get('id')
    if not reservation_id:
        return JsonResponse({'code': 400, 'msg': '缺少預約ID參數'})

    try:
        # 獲取預約詳細信息
        reservation = Reservation.objects.select_related(
            'group',
            'group__user',
            'preferred_coach'
        ).prefetch_related(
            'bookings',
            'group__payments'
        ).get(pk=reservation_id)
        
        group = reservation.group
        user = group.user
        
        # 處理用戶信息
        if user:
            user_display = user.get_full_name() or user.username
            user_email = user.email
            user_phone = getattr(user, 'phone', '') if hasattr(user, 'phone') else ''
        elif group.name:
            user_display = group.name
            user_email = group.email if hasattr(group, 'email') else ''
            user_phone = group.phone if hasattr(group, 'phone') else ''
        else:
            user_display = '未知用戶'
            user_email = ''
            user_phone = ''
        
        # 獲取預約時段信息
        bookings = reservation.bookings.all().order_by('date', 'start_time')
        booking_list = []
        for booking in bookings:
            booking_list.append({
                'date': booking.date.strftime('%Y-%m-%d (%a)'),
                'start_time': booking.start_time.strftime('%H:%M'),
                'end_time': booking.end_time.strftime('%H:%M'),
                'duration': f"{booking.start_time.strftime('%H:%M')}-{booking.end_time.strftime('%H:%M')}"
            })
        
        # 計算課程堂數
        lesson_count = 0
        daily_bookings = {}
        for booking in bookings:
            date_str = booking.date.strftime('%Y-%m-%d')
            if date_str not in daily_bookings:
                daily_bookings[date_str] = []
            daily_bookings[date_str].append(booking)
        
        for date_str, day_bookings in daily_bookings.items():
            if len(day_bookings) >= 2:
                total_hours = 0
                for booking in day_bookings:
                    duration = (booking.end_time.hour - booking.start_time.hour) + (booking.end_time.minute - booking.start_time.minute) / 60.0
                    total_hours += duration
                
                if 4.5 <= total_hours <= 5.5:
                    lesson_count += 1
                else:
                    lesson_count += len(day_bookings)
            else:
                lesson_count += len(day_bookings)

        # 獲取付款信息
        latest_payment = group.payments.first()
        payment_info = None
        current_user = Client_Info.get('user')
        control_user = UserProfile.objects.get(user=current_user)
        if control_user.is_manager:
            payment_info = {
                'status': latest_payment.status,
                'status_display': latest_payment.get_status_display(),
                'payment_method': latest_payment.payment_method,
                'payment_method_display': latest_payment.get_payment_method_display() if latest_payment.payment_method else '',
                'amount': latest_payment.amount if hasattr(latest_payment, 'amount') else reservation.total_fee,
                'created_at': latest_payment.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(latest_payment, 'created_at') else ''
            }
        
        context = {
            'RUN_HOST': RUN_HOST,
            'reservation': reservation,
            'group': group,
            'user_display': user_display,
            'user_email': user_email,
            'user_phone': user_phone,
            'bookings': booking_list,
            'lesson_count': lesson_count,
            'payment_info': payment_info,
            'is_manager': control_user.is_manager,  # 添加管理員權限標識
            'course_type_display': reservation.get_course_type_display(),
            'equipment_display': reservation.get_equipment_display() if hasattr(reservation, 'get_equipment_display') else '未設定',
            'equipment_assistance_time_display': reservation.get_equipment_assistance_time_display(),
            'language_display': reservation.get_language_display(),
            'resort_display': reservation.get_resort_display(),
            'max_ability_level_display': reservation.get_max_ability_level_display() if hasattr(reservation, 'get_max_ability_level_display') else '未設定',
            'status_display': reservation.get_status_display(),
            'coach_name': reservation.preferred_coach.name if reservation.preferred_coach else '未指定',
            'created_at': reservation.mdt_add.strftime('%Y-%m-%d %H:%M') if reservation.mdt_add else '未知時間'
        }
        
        return render(request, 'Control/tmp/course/reservation_detail.html', context)
        
    except Reservation.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '預約不存在'})
    except Exception as e:
        print(f'reservation_detail error: {e}')
        return JsonResponse({'code': 500, 'msg': f'獲取預約詳情失敗: {str(e)}'})

@login_required_control
def calendar_courses(request, Client_Info=None):
    """
    獲取指定年月的所有教練課程數據，用於行事曆顯示
    """
    print('calendar_courses')
    
    # 獲取年月參數
    year = request.GET.get('year')
    month = request.GET.get('month')
    
    if not year or not month:
        return JsonResponse({'code': 400, 'msg': '缺少年月參數'})
    
    try:
        year = int(year)
        month = int(month)
        
        # 獲取該月的第一天和最後一天
        first_day = date(year, month, 1)
        last_day = date(year, month, cal.monthrange(year, month)[1])
        
        # 查詢該月所有有預約時段的Reservation
        reservations = Reservation.objects.select_related(
            'group',
            'group__user',
            'preferred_coach'
        ).prefetch_related(
            'bookings',
            'group__payments'  # 預載入付款資訊
        ).filter(
            bookings__date__gte=first_day,
            bookings__date__lte=last_day,
            preferred_coach__isnull=False  # 只顯示有指定教練的課程
        ).distinct().exclude(status='deleted')
        
        # 按日期組織課程數據
        courses_by_date = {}
        coaches_set = set()
        
        for reservation in reservations:
            coach = reservation.preferred_coach
            if not coach:
                continue
                
            coaches_set.add(coach)
            
            # 處理用戶名稱
            group = reservation.group
            user = group.user
            if user:
                user_name = user.get_full_name() or user.username
            elif group.name:
                user_name = group.name
            else:
                user_name = '未知用戶'
            
            # 獲取付款狀態
            latest_payment = group.payments.order_by('-created_at').first()
            payment_status = latest_payment.status if latest_payment else 'unpaid'
            
            # 獲取該預約在這個月的所有時段
            bookings = reservation.bookings.filter(
                date__gte=first_day,
                date__lte=last_day
            ).order_by('date', 'start_time')
            
            for booking in bookings:
                day = booking.date.day
                
                if day not in courses_by_date:
                    courses_by_date[day] = []
                
                courses_by_date[day].append({
                    'reservation_id': reservation.id,
                    'coach_id': coach.id,
                    'coach_name': coach.name,
                    'user_name': user_name,
                    'start_time': booking.start_time.strftime('%H:%M'),
                    'end_time': booking.end_time.strftime('%H:%M'),
                    'course_type': reservation.get_course_type_display(),
                    'number_of_people': reservation.number_of_people,
                    'status': reservation.status,
                    'status_display': reservation.get_status_display(),
                    'payment_status': payment_status,  # 新增付款狀態
                    'payment_status_display': latest_payment.get_status_display() if latest_payment else '未付款'  # 新增付款狀態顯示
                })
        
        # 準備教練列表
        coaches_list = []
        for coach in coaches_set:
            coaches_list.append({
                'id': coach.id,
                'name': coach.name
            })
        
        # 按教練ID排序確保顏色分配的一致性
        coaches_list.sort(key=lambda x: x['id'])
        
        return JsonResponse({
            'code': 100,
            'msg': '取得成功',
            'data': {
                'courses': courses_by_date,
                'coaches': coaches_list,
                'year': year,
                'month': month
            }
        })
        
    except ValueError:
        return JsonResponse({'code': 400, 'msg': '年月參數格式錯誤'})
    except Exception as e:
        print(f'calendar_courses error: {e}')
        return JsonResponse({'code': 500, 'msg': f'獲取行事曆數據失敗: {str(e)}'})

@login_required_control
def coach_calendar(request, Client_Info=None):
    """
    獲取指定年月的當前教練個人課程數據，用於教練專用行事曆顯示
    """
    print('coach_calendar')
    
    # 獲取年月參數
    year = request.GET.get('year')
    month = request.GET.get('month')
    
    if not year or not month:
        return JsonResponse({'code': 400, 'msg': '缺少年月參數'})
    
    try:
        year = int(year)
        month = int(month)
        
        # 獲取當前登入用戶對應的教練
        current_user = Client_Info.get('user')
        if not current_user:
            return JsonResponse({'code': 403, 'msg': '用戶信息不存在'})
        
        try:
            coach = Coach.objects.get(user=current_user)
        except Coach.DoesNotExist:
            return JsonResponse({
                'code': 403, 
                'msg': f'您({current_user.email})不是註冊教練，無法查看個人課程行事曆。請聯繫管理員將您的帳號關聯到教練檔案。'
            })
        
        # 獲取該月的第一天和最後一天
        first_day = date(year, month, 1)
        last_day = date(year, month, cal.monthrange(year, month)[1])
        
        # 查詢該月該教練的所有預約時段
        reservations = Reservation.objects.select_related(
            'group',
            'group__user',
            'preferred_coach'
        ).prefetch_related(
            'bookings'
        ).filter(
            bookings__date__gte=first_day,
            bookings__date__lte=last_day,
            preferred_coach=coach  # 只顯示該教練的課程
        ).distinct().exclude(status='deleted')
        
        # 按日期組織課程數據
        courses_by_date = {}
        total_lessons = 0
        total_students = 0
        total_hours = 0
        working_days = set()
        course_types = {}
        
        for reservation in reservations:
            # 處理用戶名稱
            group = reservation.group
            user = group.user
            if user:
                user_name = user.get_full_name() or user.username
            elif group.name:
                user_name = group.name
            else:
                user_name = '未知用戶'
            
            # 獲取該預約在這個月的所有時段
            bookings = reservation.bookings.filter(
                date__gte=first_day,
                date__lte=last_day
            ).order_by('date', 'start_time')
            
            # 統計課程類型
            course_type_display = reservation.get_course_type_display()
            if course_type_display not in course_types:
                course_types[course_type_display] = 0
            
            for booking in bookings:
                day = booking.date.day
                working_days.add(booking.date)
                
                if day not in courses_by_date:
                    courses_by_date[day] = []
                
                # 計算時數
                start_time = booking.start_time
                end_time = booking.end_time
                duration = (end_time.hour - start_time.hour) + (end_time.minute - start_time.minute) / 60.0
                total_hours += duration
                
                courses_by_date[day].append({
                    'reservation_id': reservation.id,
                    'user_name': user_name,
                    'start_time': booking.start_time.strftime('%H:%M'),
                    'end_time': booking.end_time.strftime('%H:%M'),
                    'course_type': course_type_display,
                    'number_of_people': reservation.number_of_people,
                    'status': reservation.status,
                    'status_display': reservation.get_status_display()
                })
                
                # 統計學員數和課程類型
                total_students += reservation.number_of_people
                course_types[course_type_display] += 1
        
        # 計算課程堂數（按照智能算法）
        daily_bookings = {}
        for reservation in reservations:
            bookings = reservation.bookings.filter(
                date__gte=first_day,
                date__lte=last_day
            )
            for booking in bookings:
                date_str = booking.date.strftime('%Y-%m-%d')
                if date_str not in daily_bookings:
                    daily_bookings[date_str] = []
                daily_bookings[date_str].append(booking)
        
        # 智能計算課程堂數
        for date_str, day_bookings in daily_bookings.items():
            if len(day_bookings) >= 2:
                # 檢查是否為全天5小時課程
                total_hours_day = 0
                for booking in day_bookings:
                    duration = (booking.end_time.hour - booking.start_time.hour) + (booking.end_time.minute - booking.start_time.minute) / 60.0
                    total_hours_day += duration
                
                if 4.5 <= total_hours_day <= 5.5:
                    total_lessons += 1
                else:
                    total_lessons += len(day_bookings)
            else:
                total_lessons += len(day_bookings)
        
        # 準備統計數據
        stats = {
            'total_lessons': total_lessons,
            'total_students': total_students,
            'total_hours': round(total_hours, 1),
            'working_days': len(working_days),
            'course_types': course_types
        }
        
        # 準備教練信息
        coach_info = {
            'id': coach.id,
            'name': coach.name,
            'email': coach.user.email if coach.user else ''
        }
        
        print(f'統計結果: {stats}')
        
        return JsonResponse({
            'code': 100,
            'msg': '取得成功',
            'data': {
                'courses': courses_by_date,
                'coach_info': coach_info,
                'stats': stats,
                'year': year,
                'month': month
            }
        })
        
    except ValueError:
        return JsonResponse({'code': 400, 'msg': '年月參數格式錯誤'})
    except Exception as e:
        print(f'coach_calendar error: {e}')
        return JsonResponse({'code': 500, 'msg': f'獲取教練行事曆數據失敗: {str(e)}'})

def logout(request):
    """
    處理登出邏輯
    """
    print('logout')
    
    # 清除session中的控制面板信息
    if 'control' in request.session:
        del request.session['control']
    
    # 清除所有session數據
    request.session.flush()
    
    # 如果使用Django的認證系統，也要登出
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    
    # 重定向到控制面板登錄頁面
    return redirect('/control/')

@csrf_exempt  # 前後端分離：允許不帶CSRF token調用
def api_logout(request):
    """
    API形式的登出，返回JSON響應 - 前後端分離版本
    """
    print('api_logout')

    try:
        # 清除session中的控制面板信息
        if 'control' in request.session:
            del request.session['control']

        # 清除所有session數據
        request.session.flush()

        # 如果使用Django的認證系統，也要登出
        from django.contrib.auth import logout as auth_logout
        auth_logout(request)

        return JsonResponse({
            'code': 200,  # 改為200與前端統一
            'msg': '登出成功',
        })

    except Exception as e:
        print(f'logout error: {e}')
        return JsonResponse({
            'code': 500,
            'msg': f'登出失敗: {str(e)}'
        })

@login_required_control
def coach_list(request, Client_Info=None):
    """
    獲取教練列表
    """
    print('coach_list')
    
    page, page_size = get_page_size(request)
    
    # 獲取搜索條件
    name_search = request.GET.get('name')
    email_search = request.GET.get('email')
    language_search = request.GET.get('language')
    
    # 創建基本查詢集
    query = Coach.objects.select_related('user').prefetch_related(
        'coachresort_set',
        'course_levels'
    ).all()
    
    # 添加篩選條件
    if name_search:
        query = query.filter(name__icontains=name_search)
    if email_search:
        query = query.filter(user__email__icontains=email_search)
    if language_search:
        query = query.filter(languages__contains=language_search)
        
    # 計算符合條件的總數量
    count = query.count()
    
    # 排序並分頁
    coaches = query.order_by('-created_at')[(page-1)*page_size:page*page_size]
    
    # 準備返回的數據
    coach_list = []
    for coach in coaches:
        # 語言顯示
        language_map = dict(Coach.LANGUAGE_CHOICES)
        languages_display = ', '.join([language_map.get(lang, lang) for lang in coach.languages])
        
        # 統計雪場數量
        resort_count = coach.coachresort_set.count()
        
        # 統計課程類型數量
        course_type_count = coach.course_levels.count()
        
        coach_list.append({
            "RUN_HOST": RUN_HOST,
            "id": coach.pk,
            "name": coach.name,
            "user_email": coach.user.email if coach.user else '',
            "img": coach.img,
            "languages_display": languages_display,
            "resort_count": resort_count,
            "course_type_count": course_type_count,
            "availability_status": coach.availability_status,
            "availability_status_display": coach.get_availability_status_display(),
            "created_at": coach.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "power": 1  # 添加權限欄位，讓前端的設定按鈕正常顯示
        })

    return JsonResponse({
        'code': 100,
        'msg': '取得成功',
        'data': {
            'count': count,
            'list': coach_list
        }
    })

@login_required_control
def coach_form(request, Client_Info=None):
    """
    處理教練新增/編輯表單
    GET: 顯示表單頁面
    POST: 處理表單提交
    """
    if request.method == 'POST':
        try:
            # 導入必要的模組
            import json
            from Resorts.models import Resorts, ResortFee
            
            coach_id = request.POST.get('coach_id')
            name = request.POST.get('name')
            user_id = request.POST.get('user_id')
            img = request.POST.get('img')
            availability_status = request.POST.get('availability_status', 'active')
            
            # 處理語言能力 - 優先使用處理後的數據
            languages_str = request.POST.get('languages_final') or request.POST.get('languages', '')
            languages = [lang.strip() for lang in languages_str.split(',') if lang.strip()]
            
            # 如果沒有從 languages_final 獲得數據，嘗試從 data-language 複選框收集
            if not languages:
                # 從原始POST數據中查找語言相關的欄位
                for key, value in request.POST.items():
                    if key.startswith('language_') and value == 'on':
                        lang_code = key.replace('language_', '')
                        if lang_code in [choice[0] for choice in Coach.LANGUAGE_CHOICES]:
                            languages.append(lang_code)
            
            print(f"語言數據: languages_str={languages_str}, languages={languages}")
            
            # 處理雪場和課程等級數據 - 優先使用處理後的數據
            resorts_json = request.POST.get('resorts_final', '')
            course_levels_json = request.POST.get('course_levels_final', '')
            
            # 收集雪場數據
            resorts_data = []
            try:
                if resorts_json and resorts_json != '[]':
                    resorts_data = json.loads(resorts_json)
                else:
                    # 從原始POST數據收集雪場資料
                    resort_indices = set()
                    for key in request.POST.keys():
                        # 只處理實際的雪場選擇器，排除優先級字段
                        if key.startswith('resort_') and not key.startswith('resort_priority_'):
                            index = key.replace('resort_', '')
                            resort_indices.add(index)
                    
                    # 獲取所有有效的雪場名稱用於驗證
                    valid_resort_names = [resort.name for resort in Resorts.objects.all()]
                    
                    for index in sorted(resort_indices):
                        resort_value = request.POST.get(f'resort_{index}')
                        priority_value = request.POST.get(f'resort_priority_{index}', '0')
                        
                        # 只處理有效的雪場值（不是空值、不是索引數字）
                        if resort_value and resort_value.strip():
                            if resort_value in valid_resort_names:
                                resorts_data.append({
                                    'resort': resort_value,
                                    'priority': int(priority_value) if priority_value.isdigit() else 0
                                })
                            else:
                                print(f"✗ 雪場名稱不存在於資料庫: '{resort_value}'，可用的雪場: {valid_resort_names}")
                
            except json.JSONDecodeError as e:
                print(f"雪場數據解析錯誤: {e}")
            
            # 收集課程等級數據
            course_levels_data = []
            try:
                if course_levels_json and course_levels_json != '[]':
                    course_levels_data = json.loads(course_levels_json)
                else:
                    # 從原始POST數據收集課程等級資料
                    course_indices = set()
                    for key in request.POST.keys():
                        if key.startswith('course_type_'):
                            index = key.replace('course_type_', '')
                            course_indices.add(index)
                    
                    for index in sorted(course_indices):
                        course_type_value = request.POST.get(f'course_type_{index}')
                        price_level_value = request.POST.get(f'price_level_{index}')
                        
                        if course_type_value and price_level_value:
                            # 收集該課程的能力等級
                            ability_levels = []
                            for key, value in request.POST.items():
                                if key.startswith(f'ability_levels_{index}_') and value:
                                    ability_levels.append(value)
                            
                            course_order_value = request.POST.get(f'course_order_{index}', '0')

                            course_levels_data.append({
                                'course_type': course_type_value,
                                'price_level': price_level_value,
                                'ability_levels': ability_levels,
                                'course_order': int(course_order_value) if course_order_value.isdigit() else 0
                            })
                
            except json.JSONDecodeError as e:
                print(f"課程等級數據解析錯誤: {e}")
            
            print(f"最終收集到的數據:")
            print(f"- 雪場: {resorts_data}")
            print(f"- 課程等級: {course_levels_data}")
            
            # 驗證必填欄位
            if not name:
                return JsonResponse({'code': 400, 'msg': '姓名為必填欄位'})
            
            # 檢查雪場數據的有效性
            if not resorts_data:
                # 檢查是否有嘗試添加雪場但都失敗了
                attempted_resorts = []
                for key, value in request.POST.items():
                    if key.startswith('resort_') and not key.startswith('resort_priority_') and value:
                        attempted_resorts.append(value)
                
                if attempted_resorts:
                    return JsonResponse({
                        'code': 400, 
                        'msg': f'所選擇的雪場名稱不存在於系統中: {attempted_resorts}。請聯繫管理員添加雪場數據或選擇有效的雪場。'
                    })

            # 檢查 user_id 是否已被其他教練使用
            if user_id:
                existing_coach = None
                if coach_id:
                    # 更新現有教練時，排除當前教練
                    existing_coach = Coach.objects.filter(user_id=user_id).exclude(pk=coach_id).first()
                else:
                    # 創建新教練時，檢查所有教練
                    existing_coach = Coach.objects.filter(user_id=user_id).first()
                
                if existing_coach:
                    return JsonResponse({
                        'code': 400, 
                        'msg': f'該用戶已經關聯到教練「{existing_coach.name}」，無法重複關聯'
                    })

            # 創建或更新教練
            if coach_id:
                coach = Coach.objects.get(pk=coach_id)
                coach.name = name
                coach.img = img or ''
                coach.availability_status = availability_status
                coach.languages = languages
                # 設置 user_id，如果為空字符串則設為 None
                coach.user_id = user_id if user_id else None
                coach.save()
            else:
                coach = Coach.objects.create(
                    name=name,
                    img=img or None,
                    availability_status=availability_status,
                    languages=languages,
                    user_id=user_id if user_id else None
                )
            
            # 處理雪場資料
            try:
                # 刪除舊的雪場資料
                coach.coachresort_set.all().delete()
                # 新增新的雪場資料
                for resort_data in resorts_data:
                    from Coach.models import CoachResort
                    from Resorts.models import Resorts, ResortFee
                    
                    # 根據雪場名稱獲取 Resorts 對象
                    try:
                        resort_obj = Resorts.objects.get(name=resort_data['resort'])
                        CoachResort.objects.create(
                            coach=coach,
                            resort=resort_obj,  # 使用 Resorts 對象而不是字符串
                            resort_priority=int(resort_data['priority'])
                        )
                    except Resorts.DoesNotExist:
                        print(f"雪場不存在: {resort_data['resort']}")
                        # 可以選擇跳過這個雪場或返回錯誤
                        continue
            except Exception as e:
                print(f"雪場數據處理錯誤: {e}")
                import traceback
                traceback.print_exc()
            
            # 處理課程等級資料
            try:
                # 刪除舊的課程等級資料
                coach.course_levels.all().delete()
                # 新增新的課程等級資料
                for level_data in course_levels_data:
                    from Coach.models import CoachCourseLevel
                    from Coursekit.models import CourseType
                    
                    # 將 course_type 字符串轉換為 CourseType 實例
                    try:
                        course_type_obj = CourseType.objects.get(id=level_data['course_type'])
                    except CourseType.DoesNotExist:
                        print(f"找不到課程類型 ID: {level_data['course_type']}")
                        continue
                    
                    CoachCourseLevel.objects.create(
                        coach=coach,
                        course_type=course_type_obj,
                        price_level=level_data['price_level'],
                        ability_levels=level_data['ability_levels'],
                        course_order=level_data.get('course_order', 0)
                    )
            except Exception as e:
                print(f"課程等級數據處理錯誤: {e}")
                import traceback
                traceback.print_exc()
            
            return JsonResponse({'code': 100, 'msg': '保存成功'})
            
        except Coach.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '教練不存在'})
        except Exception as e:
            print(f'coach_form error: {e}')
            import traceback
            traceback.print_exc()
            return JsonResponse({'code': 500, 'msg': f'保存失敗: {str(e)}'})

    # GET request - 顯示表單
    coach_id = request.GET.get('id')
    coach = None
    if coach_id:
        try:
            coach = Coach.objects.select_related('user').prefetch_related(
                'coachresort_set',
                'course_levels'
            ).get(pk=coach_id)
        except Coach.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '教練不存在'})
    
    # 獲取所有用戶（用於關聯選擇）- 只顯示被標記為教練的用戶
    coach_user_profiles = UserProfile.objects.filter(is_coach=True).select_related('user')
    users = [profile.user for profile in coach_user_profiles]
    
    # 按email排序
    users = sorted(users, key=lambda x: x.email)
    
    # 準備選擇項數據
    from Coach.models import ABILITY_LEVEL_CHOICES, CoachCourseLevel
    from Resorts.models import Resorts, ResortFee
    from Coursekit.models import CourseType
    
    # 將 Resorts QuerySet 轉換為 choices 格式
    resort_choices = [(resort.name, resort.display_name) for resort in Resorts.objects.all()]
    
    # 獲取課程類型選擇項
    course_type_choices = [(ct.id, ct.name) for ct in CourseType.objects.all().order_by('display_order', 'id')]
    
    context = {
        'coach': coach,
        'users': users,
        'language_choices': Coach.LANGUAGE_CHOICES,
        'availability_choices': Coach.AVAILABILITY_CHOICES,
        'resort_choices': resort_choices,
        'course_type_choices': course_type_choices,
        'ability_level_choices': ABILITY_LEVEL_CHOICES,
        'price_level_choices': CoachCourseLevel.PRICE_LEVEL_CHOICES,
        'RUN_HOST': RUN_HOST
    }
     
    return render(request, 'Control/tmp/coach/coach_form.html', context)

@login_required_control
def coach_delete(request, Client_Info=None):
    """
    刪除教練
    """
    if request.method == 'POST':
        try:
            coach_id = request.POST.get('id')
            if not coach_id:
                return JsonResponse({'code': 400, 'msg': '缺少教練ID參數'})
            
            coach = Coach.objects.get(pk=coach_id)
            
            # 檢查是否有相關的預約記錄
            reservations_count = Reservation.objects.filter(preferred_coach=coach).count()
            
            if reservations_count > 0:
                return JsonResponse({
                    'code': 400, 
                    'msg': f'無法刪除教練，因為還有 {reservations_count} 筆相關的預約記錄。請先處理相關預約再進行刪除。'
                })
            
            coach.delete()
            
            return JsonResponse({'code': 100, 'msg': '刪除成功'})
            
        except Coach.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '教練不存在'})
        except Exception as e:
            print(f'coach_delete error: {e}')
            return JsonResponse({'code': 500, 'msg': f'刪除失敗: {str(e)}'})
    
    return JsonResponse({'code': 405, 'msg': '方法不允許'})


@login_required_control
def course_delete(request, Client_Info=None):
    """
    軟刪除預約群組（將相關預約狀態設置為已取消）
    """
    if request.method == 'POST':
        try:
            group_id = request.POST.get('id')
            if not group_id:
                return JsonResponse({'code': 400, 'msg': '缺少預約群組ID參數'})
            
            group = ReservationGroup.objects.get(pk=group_id)
            
            # 檢查預約群組是否已經被軟刪除（所有預約都是已取消狀態）
            active_reservations = group.reservations.exclude(status='deleted')
            if not active_reservations.exists():
                return JsonResponse({'code': 400, 'msg': '該預約群組已經被刪除'})
            
            # 軟刪除：將所有相關預約的狀態設置為已取消
            updated_count = active_reservations.update(status='deleted')
            
            return JsonResponse({
                'code': 100, 
                'msg': f'刪除成功，已將 {updated_count} 個預約設置為已取消狀態'
            })
            
        except ReservationGroup.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '預約群組不存在'})
        except Exception as e:
            print(f'course_delete error: {e}')
            import traceback
            traceback.print_exc()
            return JsonResponse({'code': 500, 'msg': f'刪除失敗: {str(e)}'})
    
    return JsonResponse({'code': 405, 'msg': '方法不允許'})


# ==================== 教練請假功能 ====================

@login_required_control
def apply_leave(request, Client_Info=None):
    """申請請假頁面"""
    try:
        # 獲取當前登入用戶對應的教練
        current_user = Client_Info.get('user')
        if not current_user:
            messages.error(request, '用戶信息不存在')
            return redirect('/')
            
        coach = Coach.objects.get(user=current_user)
    except Coach.DoesNotExist:
        messages.error(request, '您不是註冊教練，無法申請請假。請聯繫管理員。')
        return redirect('/')
    
    context = {
        'coach': coach,
        'today': timezone.now().date(),
    }
    return render(request, 'Control/coach/apply_leave.html', context)

@login_required_control
def submit_leave(request, Client_Info=None):
    """提交請假申請"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '請求方法錯誤'})
    
    # 增加對用戶身份的明確驗證
    current_user = Client_Info.get('user')
    
    if not current_user:
        return JsonResponse({
            'success': False, 
            'message': '您的登入已逾時，請重新登入後再提交。',
            'redirect_to_login': True  # 增加一個標記，讓前端知道需要跳轉
        }, status=401)

    try:
        # 獲取當前登入用戶對應的教練
        coach = Coach.objects.get(user=current_user)
    except Coach.DoesNotExist:
        return JsonResponse({'success': False, 'message': '您不是註冊教練，無法申請請假'})
    
    try:
        data = json.loads(request.body)
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()
        reason = data.get('reason', '').strip()
        
        # 驗證數據
        if not start_date or not end_date or not reason:
            return JsonResponse({'success': False, 'message': '請填寫完整資料'})
        
        if start_date > end_date:
            return JsonResponse({'success': False, 'message': '開始日期不能晚於結束日期'})
        
        if start_date < timezone.now().date():
            return JsonResponse({'success': False, 'message': '請假開始日期不能是過去的日期'})
        
        # 檢查是否有重疊的請假申請
        overlapping_requests = CoachLeaveRequest.objects.filter(
            coach=coach,
            status__in=['pending', 'approved'],
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        
        if overlapping_requests.exists():
            return JsonResponse({
                'success': False, 
                'message': '該時間段已有請假申請，請檢查您的申請記錄'
            })
        
        # 檢查課程衝突
        from booking.models import Reservation, Booking
        
        # 查找在請假期間有課程的預約
        conflicting_reservations = Reservation.objects.filter(
            bookings__date__gte=start_date,
            bookings__date__lte=end_date,
            preferred_coach=coach
        ).distinct()
        
        # 分類衝突的預約
        blocking_reservations = []  # 會阻止請假的預約（已指定該教練且狀態是確認的）
        affected_reservations = []  # 會受影響但不阻止請假的預約
        
        for reservation in conflicting_reservations:
            # 只有明確指定教練的預約才會阻止請假
            if reservation.is_preferred_coach and reservation.preferred_coach == coach:
                # 獲取該預約在請假期間的具體課程時段
                conflicting_bookings = reservation.bookings.filter(
                    date__gte=start_date,
                    date__lte=end_date
                )
                
                if conflicting_bookings.exists():
                    booking_details = []
                    for booking in conflicting_bookings:
                        booking_details.append(f"{booking.date.strftime('%m/%d')} {booking.start_time.strftime('%H:%M')}-{booking.end_time.strftime('%H:%M')}")
                    
                    blocking_reservations.append({
                        'id': reservation.id,
                        'user_name': reservation.group.user.get_full_name() if reservation.group.user else reservation.group.name,
                        'bookings': booking_details,
                        'status_display': reservation.get_status_display()
                    })
            elif reservation.preferred_coach == coach and not reservation.is_preferred_coach:
                # 非指定教練但被安排到該教練的課程會受影響
                conflicting_bookings = reservation.bookings.filter(
                    date__gte=start_date,
                    date__lte=end_date
                )
                
                if conflicting_bookings.exists():
                    affected_reservations.append(reservation)
        
        # 如果有阻止請假的課程，拒絕申請
        if blocking_reservations:
            conflict_details = []
            for res in blocking_reservations:
                user_info = f"客戶：{res['user_name']}"
                status_info = f"狀態：{res['status_display']}"
                bookings_info = f"課程時間：{', '.join(res['bookings'])}"
                conflict_details.append(f"• {user_info}\n  {status_info}\n  {bookings_info}")
            
            error_message = "❌ 無法申請請假，因為您在此期間有已指定的課程：\n\n" + '\n\n'.join(conflict_details) + "\n\n💡 請先聯繫管理員調整這些課程安排後再申請請假。"
            
            return JsonResponse({
                'success': False, 
                'message': error_message,
                'blocking_courses': blocking_reservations  # 添加結構化數據給前端使用
            })
        
        # 創建請假申請
        with transaction.atomic():
            leave_request = CoachLeaveRequest.objects.create(
                coach=coach,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                status='pending'
            )
            
            # 如果有受影響的預約，添加到 affected_reservations 中
            if affected_reservations:
                leave_request.affected_reservations.set(affected_reservations)
        
        # 準備返回信息
        response_data = {
            'success': True, 
            'message': '請假申請提交成功，等待管理員審核',
            'request_id': leave_request.id
        }
        
        # 如果有受影響的預約，添加相關信息
        if affected_reservations:
            affected_info = []
            for reservation in affected_reservations:
                user_name = reservation.group.user.get_full_name() if reservation.group.user else reservation.group.name
                conflicting_bookings = reservation.bookings.filter(
                    date__gte=start_date,
                    date__lte=end_date
                )
                booking_count = conflicting_bookings.count()
                affected_info.append({
                    'user_name': user_name,
                    'booking_count': booking_count,
                    'status_display': reservation.get_status_display()
                })
            
            response_data['affected_reservations'] = affected_info
        
        return JsonResponse(response_data)
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': '數據格式錯誤'})
    except ValueError as e:
        return JsonResponse({'success': False, 'message': '日期格式錯誤'})
    except Exception as e:
        print(f'submit_leave error: {e}')
        return JsonResponse({'success': False, 'message': f'系統錯誤：{str(e)}'})

@login_required_control
def leave_list(request, Client_Info=None):
    """請假記錄列表"""
    try:
        current_user = Client_Info.get('user')
        if not current_user:
            messages.error(request, '用戶信息不存在')
            return redirect('/')
            
        coach = Coach.objects.get(user=current_user)
    except Coach.DoesNotExist:
        messages.error(request, '您不是註冊教練。')
        return redirect('/')
    
    # 獲取該教練的所有請假申請，按申請時間倒序
    leave_requests = CoachLeaveRequest.objects.filter(
        coach=coach
    ).order_by('-created_at')
    
    context = {
        'coach': coach,
        'leave_requests': leave_requests,
    }
    return render(request, 'Control/coach/leave_list.html', context)

@login_required_control
def leave_management(request, Client_Info=None):
    """管理員 - 請假申請管理頁面"""
    # 檢查管理員權限
    current_user = Client_Info.get('user')
    if not current_user:
        messages.error(request, '用戶信息不存在')
        return redirect('/')
    
    try:
        user_profile = current_user.userprofile
        if not user_profile.is_manager:
            messages.error(request, '您沒有權限訪問此頁面')
            return redirect('/')
    except UserProfile.DoesNotExist:
        messages.error(request, '用戶權限設定不存在')
        return redirect('/')
    
    # 獲取搜索和篩選參數
    status_filter = request.GET.get('status', '')
    coach_search = request.GET.get('coach', '')
    date_range = request.GET.get('date_range', '')
    
    # 基礎查詢
    leave_requests = CoachLeaveRequest.objects.select_related('coach', 'reviewed_by').all()
    
    # 應用篩選條件
    if status_filter:
        leave_requests = leave_requests.filter(status=status_filter)
    
    if coach_search:
        leave_requests = leave_requests.filter(coach__name__icontains=coach_search)
    
    if date_range:
        try:
            start_date, end_date = date_range.split(' - ')
            leave_requests = leave_requests.filter(
                start_date__gte=start_date,
                end_date__lte=end_date
            )
        except ValueError:
            pass  # 忽略無效的日期範圍
    
    # 按申請時間倒序排列
    leave_requests = leave_requests.order_by('-created_at')
    
    # 統計資料
    stats = {
        'total': CoachLeaveRequest.objects.count(),
        'pending': CoachLeaveRequest.objects.filter(status='pending').count(),
        'approved': CoachLeaveRequest.objects.filter(status='approved').count(),
        'rejected': CoachLeaveRequest.objects.filter(status='rejected').count(),
    }
    
    context = {
        'leave_requests': leave_requests,
        'stats': stats,
        'status_filter': status_filter,
        'coach_search': coach_search,
        'date_range': date_range,
        'status_choices': CoachLeaveRequest.STATUS_CHOICES,
    }
    return render(request, 'Control/tmp/coach/leave_management.html', context)

@login_required_control
def leave_review(request, Client_Info=None):
    """管理員 - 審核請假申請"""
    print(f"\n{'='*50}")
    print(f"🔍 [LEAVE_REVIEW] 開始處理請假審核請求")
    print(f"{'='*50}")
    
    if request.method != 'POST':
        print(f"❌ [LEAVE_REVIEW] 請求方法錯誤: {request.method}")
        return JsonResponse({'success': False, 'message': '請求方法錯誤'})
    
    print(f"✓ [LEAVE_REVIEW] 請求方法正確: POST")
    
    # 檢查管理員權限
    current_user = Client_Info.get('user')
    print(f"🔍 [LEAVE_REVIEW] 檢查用戶權限...")
    
    if not current_user:
        print(f"❌ [LEAVE_REVIEW] 用戶信息不存在")
        return JsonResponse({'success': False, 'message': '用戶信息不存在'})
    
    print(f"✓ [LEAVE_REVIEW] 當前用戶: {current_user.username} ({current_user.email})")
    
    try:
        user_profile = current_user.userprofile
        print(f"✓ [LEAVE_REVIEW] 用戶Profile存在")
        
        if not user_profile.is_manager:
            print(f"❌ [LEAVE_REVIEW] 用戶不是管理員: is_manager={user_profile.is_manager}")
            return JsonResponse({'success': False, 'message': '您沒有權限執行此操作'})
        
        print(f"✓ [LEAVE_REVIEW] 管理員權限驗證通過")
        
    except UserProfile.DoesNotExist:
        print(f"❌ [LEAVE_REVIEW] UserProfile不存在")
        return JsonResponse({'success': False, 'message': '用戶權限設定不存在'})
    
    try:
        print(f"🔍 [LEAVE_REVIEW] 解析請求數據...")
        print(f"📝 [LEAVE_REVIEW] Raw request body: {request.body}")
        
        data = json.loads(request.body)
        request_id = data.get('request_id')
        action = data.get('action')  # 'approve' 或 'reject'
        review_comment = data.get('review_comment', '').strip()
        
        print(f"✓ [LEAVE_REVIEW] 解析成功:")
        print(f"   - request_id: {request_id}")
        print(f"   - action: {action}")
        print(f"   - review_comment: '{review_comment}'")
        
        # 驗證參數
        if not request_id or action not in ['approve', 'reject']:
            print(f"❌ [LEAVE_REVIEW] 參數驗證失敗:")
            print(f"   - request_id存在: {bool(request_id)}")
            print(f"   - action有效: {action in ['approve', 'reject']}")
            return JsonResponse({'success': False, 'message': '參數錯誤'})
        
        print(f"✓ [LEAVE_REVIEW] 參數驗證通過")
        
        # 獲取請假申請
        print(f"🔍 [LEAVE_REVIEW] 查詢請假申請 ID: {request_id}")
        leave_request = CoachLeaveRequest.objects.get(pk=request_id)
        
        print(f"✓ [LEAVE_REVIEW] 找到請假申請:")
        print(f"   - 教練: {leave_request.coach.name}")
        print(f"   - 日期: {leave_request.start_date} 到 {leave_request.end_date}")
        print(f"   - 目前狀態: {leave_request.status} ({leave_request.get_status_display()})")
        print(f"   - 請假原因: {leave_request.reason[:50]}...")
        print(f"   - 受影響預約數量: {leave_request.affected_reservations.count()}")
        
        # 檢查狀態是否可以審核
        if leave_request.status != 'pending':
            print(f"❌ [LEAVE_REVIEW] 申請狀態不允許審核: {leave_request.status}")
            return JsonResponse({
                'success': False, 
                'message': f'該申請已處理，目前狀態為：{leave_request.get_status_display()}'
            })
        
        print(f"✓ [LEAVE_REVIEW] 申請狀態允許審核")
        
        if action == 'approve':
            try:
                with transaction.atomic():
                    affected_reservations = leave_request.affected_reservations.all()
                    
                    if not affected_reservations.exists():
                        print(f"✓ [LEAVE_REVIEW] 無受影響的預約課程，直接批准")
                    else:
                        # 有受影響的預約課程，嘗試重新排課
                        failed_reassignments = []
                        from booking.scheduler import reassign_single_reservation

                        for reservation in affected_reservations:
                            print(f"  -> 正在處理預約 ID: {reservation.id}")
                            coach_on_leave = leave_request.coach
                            reservation.rejected_coaches.add(coach_on_leave)
                            reservation.status = 'created'  # 重置為待排課
                            reservation.preferred_coach = None
                            reservation.save()
                            for booking in reservation.bookings.all():
                                booking.is_scheduled = False
                                booking.save()
                            
                            reassign_success = reassign_single_reservation(reservation.id)
                            reservation.refresh_from_db()
                            
                            if not reassign_success or reservation.status == 'manual_assignment_needed':  # 10: 需人工排定教練
                                failed_reassignments.append(reservation)
                                print(f"    ❌ [FAILURE] 預約 {reservation.id} 重新排課失敗. 狀態: {reservation.get_status_display()}")
                            else:
                                print(f"    ✓ [SUCCESS] 預約 {reservation.id} 成功重新排課. 新教練: {reservation.preferred_coach}, 狀態: {reservation.get_status_display()}")

                        if failed_reassignments:
                            failed_clients = [r.group.user.get_full_name() if r.group.user else r.group.name for r in failed_reassignments]
                            error_message = f"無法批准請假，客戶 '{', '.join(failed_clients)}' 的課程無法自動重新排課。請手動處理或拒絕申請。"
                            raise Exception(error_message)

                    # 如果執行到這裡，表示所有檢查都通過了
                    print(f"✓ [LEAVE_REVIEW] 所有檢查通過，批准請假申請")
                    leave_request.status = 'approved'
                    leave_request.reviewed_by = current_user
                    leave_request.reviewed_at = timezone.now()
                    leave_request.processing_result = review_comment
                    leave_request.save()
                    
                    response_data = {
                        'success': True,
                        'message': '請假申請已批准，所有受影響課程已自動重新排課。',
                        'new_status': leave_request.get_status_display()
                    }
                    return JsonResponse(response_data)

            except Exception as e:
                print(f"❌ [LEAVE_REVIEW] 批准過程中發生錯誤: {e}")
                return JsonResponse({'success': False, 'message': str(e)})

        elif action == 'reject':
            with transaction.atomic():
                leave_request.status = 'rejected'
                leave_request.reviewed_by = current_user
                leave_request.reviewed_at = timezone.now()
                leave_request.processing_result = review_comment
                leave_request.save()
            
            response_data = {
                'success': True,
                'message': '請假申請已拒絕',
                'new_status': leave_request.get_status_display()
            }
            return JsonResponse(response_data)

        # Fallback for invalid action, though already checked before
        return JsonResponse({'success': False, 'message': '無效的操作'})
        
    except CoachLeaveRequest.DoesNotExist:
        print(f"❌ [LEAVE_REVIEW] 請假申請不存在: ID={request_id}")
        return JsonResponse({'success': False, 'message': '請假申請不存在'})
    except json.JSONDecodeError as e:
        print(f"❌ [LEAVE_REVIEW] JSON解析錯誤: {e}")
        print(f"   Raw body: {request.body}")
        return JsonResponse({'success': False, 'message': '數據格式錯誤'})
    except Exception as e:
        print(f"❌ [LEAVE_REVIEW] 系統錯誤: {e}")
        print(f"   錯誤類型: {type(e).__name__}")
        import traceback
        print(f"   堆疊追蹤:")
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'系統錯誤：{str(e)}'})

@login_required_control
def coach_confirm_course(request, Client_Info=None):
    """教練確認課程"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '請求方法錯誤'})
    
    # 檢查是否為教練
    current_user = Client_Info.get('user')
    if not current_user:
        return JsonResponse({'success': False, 'message': '用戶信息不存在'})
    
    try:
        coach = Coach.objects.get(user=current_user)
    except Coach.DoesNotExist:
        return JsonResponse({'success': False, 'message': '您不是註冊教練，無法確認課程'})
    
    try:
        data = json.loads(request.body)
        reservation_id = data.get('reservation_id')
        action = data.get('action')  # 'accept' 或 'reject'
        
        if not reservation_id or action not in ['accept', 'reject']:
            return JsonResponse({'success': False, 'message': '參數錯誤'})
        
        # 獲取預約
        reservation = Reservation.objects.get(pk=reservation_id)
        
        # 檢查預約是否屬於該教練且狀態為等待確認
        if reservation.preferred_coach != coach:
            return JsonResponse({'success': False, 'message': '此預約不屬於您'})
        
        if reservation.status != 'pending_coach_confirmation':
            return JsonResponse({'success': False, 'message': '此預約不是等待確認狀態'})
        
        if action == 'accept':
            # 教練接受課程
            reservation.status = 'manually_assigned'  # 已自動排定教練
            reservation.save()
            
            return JsonResponse({
                'success': True, 
                'message': '已確認接受此課程',
                'new_status': reservation.get_status_display()
            })
        
        elif action == 'reject':
            # 教練拒絕課程，記錄拒絕的教練並重新排課
            print(f"教練 {coach.name} 拒絕預約 {reservation_id}")
            
            # 1. 將該教練添加到拒絕列表
            reservation.rejected_coaches.add(coach)
            
            # 2. 重置為待排課狀態
            reservation.status = 'created'  # 創建預約（待排課）
            reservation.preferred_coach = None  # 清除教練指派
            reservation.save()
            
            # 3. 清除相關 booking 的排程狀態
            for booking in reservation.bookings.all():
                booking.is_scheduled = False
                booking.save()
            
            print(f"已將教練 {coach.name} 添加到預約 {reservation_id} 的拒絕列表")
            
            # 4. 重新執行排課系統
            try:
                from booking.scheduler import reassign_single_reservation
                print("開始重新執行單個預約排課...")
                
                schedule_success = reassign_single_reservation(reservation.id)
                
                if schedule_success:
                    # 重新獲取更新後的預約狀態
                    reservation.refresh_from_db()
                    
                    if reservation.status == 'auto_assigned':
                        # 成功重新分配給其他教練
                        new_coach_name = reservation.preferred_coach.name if reservation.preferred_coach else "系統分配"
                        return JsonResponse({
                            'success': True, 
                            'message': f'已拒絕此課程，系統已重新安排給教練：{new_coach_name}',
                            'new_status': reservation.get_status_display()
                        })
                    elif reservation.status == 'pending_coach_confirmation':
                        # 重新分配給 passive 教練，等待確認
                        new_coach_name = reservation.preferred_coach.name if reservation.preferred_coach else "其他教練"
                        return JsonResponse({
                            'success': True, 
                            'message': f'已拒絕此課程，系統已安排給教練 {new_coach_name}，等待確認',
                            'new_status': reservation.get_status_display()
                        })
                    elif reservation.status == 'manual_assignment_needed':
                        # 需要人工處理
                        return JsonResponse({
                            'success': True, 
                            'message': '已拒絕此課程，因無其他可用教練，已轉為人工安排',
                            'new_status': reservation.get_status_display()
                        })
                    else:
                        # 其他狀態
                        return JsonResponse({
                            'success': True, 
                            'message': f'已拒絕此課程，目前狀態：{reservation.get_status_display()}',
                            'new_status': reservation.get_status_display()
                        })
                else:
                    # 排課失敗，狀態已經在函數中設為需要人工處理
                    reservation.refresh_from_db()
                    
                    return JsonResponse({
                        'success': True, 
                        'message': '已拒絕此課程，因無其他可用教練，已轉為人工安排',
                        'new_status': reservation.get_status_display()
                    })
                    
            except ImportError:
                print('無法導入排課模組')
                # 如果無法執行排課，設為需要人工處理
                reservation.status = 'manual_assignment_needed'  # 需人工排定教練
                reservation.save()
                
                return JsonResponse({
                    'success': True, 
                    'message': '已拒絕此課程，排課系統暫時無法使用，已轉為人工安排',
                    'new_status': reservation.get_status_display()
                })
            except Exception as e:
                print(f'重新排課過程發生錯誤: {e}')
                # 如果排課過程出錯，設為需要人工處理
                reservation.status = 'manual_assignment_needed'  # 需人工排定教練
                reservation.save()
                
                return JsonResponse({
                    'success': True, 
                    'message': f'已拒絕此課程，重新排課時發生錯誤，已轉為人工安排',
                    'new_status': reservation.get_status_display()
                })
            
    except Reservation.DoesNotExist:
        return JsonResponse({'success': False, 'message': '預約不存在'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': '數據格式錯誤'})
    except Exception as e:
        print(f'coach_confirm_course error: {e}')
        return JsonResponse({'success': False, 'message': f'系統錯誤：{str(e)}'})

@login_required_control
def pending_confirmations(request, Client_Info=None):
    """獲取等待教練確認的課程列表"""
    print('pending_confirmations')
    
    # 獲取當前登入用戶對應的教練
    current_user = Client_Info.get('user')
    if not current_user:
        return JsonResponse({'code': 403, 'msg': '用戶信息不存在'})
    
    try:
        coach = Coach.objects.get(user=current_user)
    except Coach.DoesNotExist:
        return JsonResponse({
            'code': 403, 
            'msg': f'您({current_user.email})不是註冊教練，無法查看待確認課程。'
        })
    
    # 查詢狀態為'pending_coach_confirmation'（等待教練確認）且指派給該教練的預約
    pending_reservations = Reservation.objects.select_related(
        'group',
        'group__user',
        'preferred_coach'
    ).prefetch_related(
        'bookings'
    ).filter(
        preferred_coach=coach,
        status='pending_coach_confirmation'  # 等待教練確認
    ).order_by('-mdt_add')
    
    # 準備返回的數據
    course_list = []
    for reservation in pending_reservations:
        group = reservation.group
        user = group.user
        
        # 處理用戶名稱顯示
        if user:
            user_display = user.get_full_name() or user.username
            user_email = user.email
        elif group.name:
            user_display = group.name
            user_email = ''
        else:
            user_display = '未知用戶'
            user_email = ''
        
        # 獲取課程時段資訊
        bookings = reservation.bookings.all()
        booking_dates = []
        booking_times = []
        
        for booking in bookings:
            booking_dates.append(booking.date.strftime('%m/%d'))
            booking_times.append(f"{booking.start_time.strftime('%H:%M')}-{booking.end_time.strftime('%H:%M')}")
        
        # 安全獲取 course_type 信息
        try:
            course_type_id = reservation.course_type.id if reservation.course_type else None
        except Exception:
            course_type_id = None
        
        course_list.append({
            "RUN_HOST": RUN_HOST,
            "id": reservation.pk,
            "user_display": user_display,
            "user_email": user_email,
            "course_type": course_type_id,
            "course_type_display": reservation.get_course_type_display(),
            "language_display": reservation.get_language_display(),
            "resort_display": reservation.get_resort_display(),
            "number_of_people": reservation.number_of_people,
            "booking_dates": ', '.join(booking_dates) if booking_dates else '無',
            "booking_times": ', '.join(booking_times) if booking_times else '無',
            "status": reservation.status,
            "status_display": reservation.get_status_display(),
            "total_fee": reservation.total_fee,
            "created_at": reservation.mdt_add.strftime('%Y-%m-%d %H:%M') if reservation.mdt_add else '未知時間'
        })

    return JsonResponse({
        'code': 100,
        'msg': '取得成功',
        'data': {
            'count': len(course_list),
            'list': course_list,
            'coach_info': {
                'name': coach.name,
                'id': coach.id
            }
        }
    })

@login_required_control
def send_email_form(request, Client_Info=None):
    """郵件發送表單 - 參考coach_form的處理模式"""
    
    # 處理POST請求（發送郵件）
    if request.method == 'POST':
        try:
            # 獲取表單數據
            group_id = request.POST.get('group_id')
            recipient_email = request.POST.get('recipient_email')
            subject = request.POST.get('subject')
            message = request.POST.get('message')
            
            print(f"郵件表單數據: group_id={group_id}, email={recipient_email}, subject={subject[:30]}...")
            
            # 驗證必填欄位
            if not all([group_id, recipient_email, subject, message]):
                return JsonResponse({'code': 400, 'msg': '請填寫所有必填欄位'})
            
            # 驗證email格式
            import re
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', recipient_email):
                return JsonResponse({'code': 400, 'msg': 'Email格式不正確'})
            
            # 驗證預約群組
            try:
                group = ReservationGroup.objects.get(pk=group_id)
            except ReservationGroup.DoesNotExist:
                return JsonResponse({'code': 404, 'msg': '預約群組不存在'})
            
            # 發送郵件
            try:
                from booking.scheduler import send_gmail
                
                # 組成完整郵件內容
                full_message = f"""{message}

──────────────────────────
雪域創遊 SNOWLAND
官網：{RUN_HOST}
客服信箱：service@snowland.com.tw

此郵件為系統自動發送，請勿直接回覆。
如有問題請透過官方客服聯繫我們。
"""
                
                result = send_gmail(subject, full_message, recipient_email)
                
                # 記錄發送
                current_user = Client_Info.get('user')
                print(f"郵件發送: {current_user.email} -> {recipient_email} 主旨:{subject}")
                
                return JsonResponse({'code': 100, 'msg': '郵件發送成功'})
                
            except Exception as e:
                print(f'發送郵件錯誤: {e}')
                return JsonResponse({'code': 500, 'msg': f'發送失敗: {str(e)}'})
                
        except Exception as e:
            print(f'處理POST請求錯誤: {e}')
            return JsonResponse({'code': 500, 'msg': f'系統錯誤: {str(e)}'})
    
    # 處理GET請求（顯示表單）
    group_id = request.GET.get('id')
    if not group_id:
        return JsonResponse({'code': 400, 'msg': '缺少預約群組ID'})

    try:
        # 導入付款主機設定
        from snowland.settings import PAYMENT_HOST
        
        # 獲取預約群組資料
        group = ReservationGroup.objects.select_related('user').prefetch_related(
            'reservations', 'payments'
        ).get(pk=group_id)
        
        # 生成付款連結
        payment_url = PAYMENT_HOST + '?reservation_group=' + str(group.pk)
        
        # 準備客戶資訊
        user = group.user
        if user:
            customer_info = {
                'name': user.get_full_name() or user.username,
                'email': user.email
            }
        elif group.name:
            customer_info = {
                'name': group.name,
                'email': getattr(group, 'email', '')
            }
        else:
            customer_info = {
                'name': '未知用戶',
                'email': ''
            }
        
        # 付款資訊
        latest_payment = group.payments.first()
        payment_info = {
            'status': latest_payment.status if latest_payment else 'unpaid',
            'status_display': latest_payment.get_status_display() if latest_payment else '未付款'
        }
        
        # 總費用
        total_fee = sum(r.total_fee for r in group.reservations.all())
        
        context = {
            'group': group,
            'customer_info': customer_info,
            'payment_info': payment_info,
            'total_fee': total_fee,
            'payment_url': payment_url,  # 添加付款連結
            'RUN_HOST': RUN_HOST
        }
        
        return render(request, 'Control/tmp/course/send_email_form.html', context)
        
    except ReservationGroup.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '預約群組不存在'})
    except Exception as e:
        print(f'顯示表單錯誤: {e}')
        return JsonResponse({'code': 500, 'msg': f'系統錯誤: {str(e)}'})

@login_required_control
def send_email(request, Client_Info=None):
    """處理郵件發送"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '請求方法錯誤'})
    
    try:
        group_id = request.POST.get('group_id')
        recipient_email = request.POST.get('recipient_email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # 驗證必填欄位
        if not all([group_id, recipient_email, subject, message]):
            return JsonResponse({'success': False, 'message': '請填寫所有必填欄位'})
        
        # 驗證 email 格式
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, recipient_email):
            return JsonResponse({'success': False, 'message': 'Email 格式不正確'})
        
        # 驗證預約群組存在
        try:
            group = ReservationGroup.objects.get(pk=group_id)
        except ReservationGroup.DoesNotExist:
            return JsonResponse({'success': False, 'message': '預約群組不存在'})
        
        # 發送郵件
        try:
            from booking.scheduler import send_gmail
            
            # 添加郵件簽名
            full_message = f"""{message}

──────────────────────────
雪域創遊 SNOWLAND
官網：{RUN_HOST}
客服信箱：service@snowland.com.tw
電話：(02) 1234-5678

此郵件為系統自動發送，請勿直接回覆此信箱。
如有任何問題，歡迎透過官方客服管道聯繫我們。
"""
            
            result = send_gmail(subject, full_message, recipient_email)
            
            if result == 'ok':
                # 記錄發送日誌（可選）
                current_user = Client_Info.get('user')
                print(f"郵件發送成功：{current_user.email} 向 {recipient_email} 發送了 '{subject}'")
                
                return JsonResponse({
                    'success': True, 
                    'message': '郵件發送成功'
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'message': f'郵件發送失敗：{result}'
                })
                
        except Exception as e:
            print(f'發送郵件時發生錯誤: {e}')
            return JsonResponse({
                'success': False, 
                'message': f'郵件發送失敗：{str(e)}'
            })
        
    except Exception as e:
        print(f'send_email error: {e}')
        return JsonResponse({
            'success': False, 
            'message': f'系統錯誤：{str(e)}'
        })


# ============ 課程大類 CRUD API ============




# ============ 課程模板 CRUD API ============




# ============ 課程時段 CRUD API ============







# ============ 定價策略 CRUD API ============




# ==================== 季節設定 CRUD ====================




# ==================== 定價策略 CRUD ====================




# ============ 統一路由動作包裝 ============











# ===== 新版課程設定管理系統 =====

@login_required_control
def course_settings_new(request, Client_Info=None):
    """新的課程設定管理頁面數據API"""
    try:
        # 獲取所有課程大類
        course_categories = []
        for category in CourseCategory.objects.all():
            course_categories.append({
                'id': category.id,
                'name': category.name,
                'display_order': category.display_order,
                'available_resorts': list(category.available_resorts.values_list('id', flat=True))
            })
        
        # 獲取所有課程類型
        course_types = []
        for course_type in CoursekitCourseType.objects.all():
            course_types.append({
                'id': course_type.id,
                'category': course_type.category_id,
                'name': course_type.name,
                'display_order': course_type.display_order,
                'available_resorts': list(course_type.available_resorts.values_list('id', flat=True))
            })
        
        # 獲取所有課程模板
        templates = []
        for template in CoursekitCourseTemplate.objects.all():
            templates.append({
                'id': template.id,
                'course_type': template.course_type_id,
                'name': template.name,
                'duration_hours': template.duration_hours,
                'max_capacity': template.max_capacity,
                'is_active': template.is_active,
                'resorts': list(template.resorts.values_list('id', flat=True)),
                'booking_open_date': template.booking_open_date.isoformat() if template.booking_open_date else None,
                'booking_close_date': template.booking_close_date.isoformat() if template.booking_close_date else None,
                'course_start_date': template.course_start_date.isoformat() if template.course_start_date else None,
                'course_end_date': template.course_end_date.isoformat() if template.course_end_date else None
            })
        
        # 獲取所有上課時段
        sessions = []
        for session in CourseSession.objects.all():
            sessions.append({
                'id': session.id,
                'template': session.template_id,
                'start_time': session.start_time.strftime('%H:%M'),
                'end_time': session.end_time.strftime('%H:%M'),
                'is_active': session.is_active
            })
        
        # 獲取所有課程定價
        pricing = []
        for price in CoursePricing.objects.prefetch_related('templates', 'people_tiers').all():
            pricing.append({
                'id': price.id,
                'templates': list(price.templates.values_list('id', flat=True)),  # 改為多對多關係
                'resort': price.resort_id,
                'base_price_off_peak': price.base_price_off_peak,
                'peak_season_surcharge': price.peak_season_surcharge,
                'additional_person_fee': price.additional_person_fee,
                'max_capacity': price.max_capacity,
                'people_tiers': [
                    {
                        'id': tier.id,
                        'min_people': tier.min_people,
                        'max_people': tier.max_people,
                        'price': tier.price,
                        'is_active': tier.is_active,
                        'display_order': tier.display_order,
                    }
                    for tier in price.people_tiers.all()
                ],
                'is_active': price.is_active
            })
        
        # 獲取所有雪場
        resorts = []
        for resort in Resorts.objects.all():
            resorts.append({
                'id': resort.id,
                'display_name': resort.display_name
            })
        
        data = {
            'courseCategories': course_categories,
            'courseTypes': course_types,
            'templates': templates,
            'sessions': sessions,
            'pricing': pricing,
            'resorts': resorts
        }
        
        return JsonResponse({
            'code': 100,
            'msg': '成功',
            'data': data
        })
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'msg': f'獲取數據失敗: {str(e)}',
            'data': None
        })

@login_required_control
def course_categories_action(request, category_id=None, Client_Info=None):
    """課程大類CRUD操作"""
    try:
        # 安全地解析JSON，处理空body的情况
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        action = request.GET.get('action', 'create')
        
        if action == 'delete':
            if category_id:
                category = CourseCategory.objects.get(id=category_id)
                category.delete()
                return JsonResponse({'code': 100, 'msg': '刪除成功'})
            else:
                return JsonResponse({'code': 400, 'msg': '缺少ID參數'})
        
        elif action in ['create', 'update']:
            name = data.get('name')
            display_order = data.get('display_order', 0)
            available_resorts = data.get('available_resorts', [])
            
            if not name:
                return JsonResponse({'code': 400, 'msg': '課程大類名稱不能為空'})
            
            if action == 'update' and category_id:
                category = CourseCategory.objects.get(id=category_id)
                category.name = name
                category.display_order = display_order
                category.save()
                
                # 更新多對多關係
                category.available_resorts.clear()
                for resort_id in available_resorts:
                    try:
                        resort = Resorts.objects.get(id=resort_id)
                        category.available_resorts.add(resort)
                    except Resorts.DoesNotExist:
                        continue
                
                return JsonResponse({'code': 100, 'msg': '更新成功'})
            else:
                # 創建新的課程大類
                category = CourseCategory.objects.create(
                    name=name,
                    display_order=display_order
                )
                
                # 添加多對多關係
                for resort_id in available_resorts:
                    try:
                        resort = Resorts.objects.get(id=resort_id)
                        category.available_resorts.add(resort)
                    except Resorts.DoesNotExist:
                        continue
                
                return JsonResponse({'code': 100, 'msg': '創建成功'})
        
        else:
            return JsonResponse({'code': 400, 'msg': '無效的操作'})
            
    except CourseCategory.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '課程大類不存在'})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': f'操作失敗: {str(e)}'})

@login_required_control
def course_types_action_new(request, type_id=None, Client_Info=None):
    """課程類型CRUD操作"""
    try:
        # 安全地解析JSON，处理空body的情况
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        action = request.GET.get('action', 'create')
        
        if action == 'delete':
            if type_id:
                course_type = CoursekitCourseType.objects.get(id=type_id)
                course_type.delete()
                return JsonResponse({'code': 100, 'msg': '刪除成功'})
            else:
                return JsonResponse({'code': 400, 'msg': '缺少ID參數'})
        
        elif action in ['create', 'update']:
            category_id = data.get('category')
            name = data.get('name')
            display_order = data.get('display_order', 0)
            available_resorts = data.get('available_resorts', [])
            
            if not category_id or not name:
                return JsonResponse({'code': 400, 'msg': '課程大類和課程類型名稱不能為空'})
            
            try:
                category = CourseCategory.objects.get(id=category_id)
            except CourseCategory.DoesNotExist:
                return JsonResponse({'code': 400, 'msg': '課程大類不存在'})
            
            if action == 'update' and type_id:
                course_type = CoursekitCourseType.objects.get(id=type_id)
                course_type.category = category
                course_type.name = name
                course_type.display_order = display_order
                course_type.save()
                
                # 更新多對多關係
                course_type.available_resorts.clear()
                for resort_id in available_resorts:
                    try:
                        resort = Resorts.objects.get(id=resort_id)
                        course_type.available_resorts.add(resort)
                    except Resorts.DoesNotExist:
                        continue
                
                return JsonResponse({'code': 100, 'msg': '更新成功'})
            else:
                # 創建新的課程類型
                course_type = CoursekitCourseType.objects.create(
                    category=category,
                    name=name,
                    display_order=display_order
                )
                
                # 添加多對多關係
                for resort_id in available_resorts:
                    try:
                        resort = Resorts.objects.get(id=resort_id)
                        course_type.available_resorts.add(resort)
                    except Resorts.DoesNotExist:
                        continue
                
                return JsonResponse({'code': 100, 'msg': '創建成功'})
        
        else:
            return JsonResponse({'code': 400, 'msg': '無效的操作'})
            
    except CoursekitCourseType.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '課程類型不存在'})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': f'操作失敗: {str(e)}'})

@login_required_control
def templates_action_new(request, template_id=None, Client_Info=None):
    """課程模板CRUD操作"""
    try:
        # 安全地解析JSON，处理空body的情况
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        action = request.GET.get('action', 'create')
        
        if action == 'delete':
            if template_id:
                template = CoursekitCourseTemplate.objects.get(id=template_id)
                template.delete()
                return JsonResponse({'code': 100, 'msg': '刪除成功'})
            else:
                return JsonResponse({'code': 400, 'msg': '缺少ID參數'})
        
        elif action in ['create', 'update']:
            course_type_id = data.get('course_type')
            name = data.get('name')
            duration_hours = data.get('duration_hours')
            max_capacity = data.get('max_capacity', 6)
            is_active = data.get('is_active', True)
            resorts = data.get('resorts', [])
            booking_open_date = data.get('booking_open_date')
            booking_close_date = data.get('booking_close_date')
            course_start_date = data.get('course_start_date')
            course_end_date = data.get('course_end_date')
            
            if not course_type_id or not name or not duration_hours:
                return JsonResponse({'code': 400, 'msg': '課程類型、模板名稱和時長不能為空'})
            
            try:
                course_type = CoursekitCourseType.objects.get(id=course_type_id)
            except CoursekitCourseType.DoesNotExist:
                return JsonResponse({'code': 400, 'msg': '課程類型不存在'})
            
            if action == 'update' and template_id:
                template = CoursekitCourseTemplate.objects.get(id=template_id)
                template.course_type = course_type
                template.name = name
                template.duration_hours = duration_hours
                template.max_capacity = max_capacity
                template.is_active = is_active
                template.booking_open_date = booking_open_date
                template.booking_close_date = booking_close_date
                template.course_start_date = course_start_date
                template.course_end_date = course_end_date
                template.save()
                
                # 更新多對多關係
                template.resorts.clear()
                for resort_id in resorts:
                    try:
                        resort = Resorts.objects.get(id=resort_id)
                        template.resorts.add(resort)
                    except Resorts.DoesNotExist:
                        continue
                
                return JsonResponse({'code': 100, 'msg': '更新成功'})
            else:
                # 創建新的課程模板
                template = CoursekitCourseTemplate.objects.create(
                    course_type=course_type,
                    name=name,
                    duration_hours=duration_hours,
                    max_capacity=max_capacity,
                    is_active=is_active,
                    booking_open_date=booking_open_date,
                    booking_close_date=booking_close_date,
                    course_start_date=course_start_date,
                    course_end_date=course_end_date
                )
                
                # 添加多對多關係
                for resort_id in resorts:
                    try:
                        resort = Resorts.objects.get(id=resort_id)
                        template.resorts.add(resort)
                    except Resorts.DoesNotExist:
                        continue
                
                return JsonResponse({'code': 100, 'msg': '創建成功'})
        
        else:
            return JsonResponse({'code': 400, 'msg': '無效的操作'})
            
    except CoursekitCourseTemplate.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '課程模板不存在'})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': f'操作失敗: {str(e)}'})

@login_required_control
def sessions_action(request, session_id=None, Client_Info=None):
    """上課時段CRUD操作"""
    try:
        # 安全地解析JSON，处理空body的情况
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        action = request.GET.get('action', 'create')
        
        if action == 'delete':
            if session_id:
                session = CourseSession.objects.get(id=session_id)
                session.delete()
                return JsonResponse({'code': 100, 'msg': '刪除成功'})
            else:
                return JsonResponse({'code': 400, 'msg': '缺少ID參數'})
        
        elif action in ['create', 'update']:
            template_id = data.get('template')
            start_time = data.get('start_time')
            end_time = data.get('end_time')
            is_active = data.get('is_active', True)
            
            if not template_id or not start_time or not end_time:
                return JsonResponse({'code': 400, 'msg': '課程模板、開始時間和結束時間不能為空'})
            
            try:
                template = CoursekitCourseTemplate.objects.get(id=template_id)
            except CoursekitCourseTemplate.DoesNotExist:
                return JsonResponse({'code': 400, 'msg': '課程模板不存在'})
            
            if action == 'update' and session_id:
                session = CourseSession.objects.get(id=session_id)
                session.template = template
                session.start_time = start_time
                session.end_time = end_time
                session.is_active = is_active
                session.save()
                
                return JsonResponse({'code': 100, 'msg': '更新成功'})
            else:
                # 創建新的上課時段
                session = CourseSession.objects.create(
                    template=template,
                    start_time=start_time,
                    end_time=end_time,
                    is_active=is_active
                )
                
                return JsonResponse({'code': 100, 'msg': '創建成功'})
        
        else:
            return JsonResponse({'code': 400, 'msg': '無效的操作'})
            
    except CourseSession.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '上課時段不存在'})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': f'操作失敗: {str(e)}'})

def _prepare_people_tiers(tiers_data, max_capacity):
    tiers = []
    active_ranges = []
    for item in tiers_data or []:
        try:
            min_people = int(item.get('min_people') or 0)
            max_people = int(item.get('max_people') or 0)
            price = int(item.get('price') or 0)
        except (TypeError, ValueError):
            raise ValueError('人數級距格式錯誤')

        if min_people == 0 and max_people == 0 and price == 0:
            continue
        if min_people < 1 or max_people < min_people:
            raise ValueError('人數級距範圍錯誤')
        if max_capacity and max_people > int(max_capacity):
            raise ValueError('人數級距不能超過最大容量')
        if price < 0:
            raise ValueError('人數級距價格不能小於 0')

        is_active = item.get('is_active', True)
        if is_active:
            for start, end in active_ranges:
                if min_people <= end and max_people >= start:
                    raise ValueError('啟用中的人數級距不能重疊')
            active_ranges.append((min_people, max_people))

        tiers.append({
            'min_people': min_people,
            'max_people': max_people,
            'price': price,
            'is_active': is_active,
        })

    tiers.sort(key=lambda tier: (tier['min_people'], tier['max_people']))
    return tiers

def _sync_course_pricing_tiers(pricing, tiers_data):
    pricing.people_tiers.all().delete()
    for index, tier in enumerate(_prepare_people_tiers(tiers_data, pricing.max_capacity)):
        CoursePricingTier.objects.create(
            pricing=pricing,
            min_people=tier['min_people'],
            max_people=tier['max_people'],
            price=tier['price'],
            is_active=tier['is_active'],
            display_order=index,
        )

@login_required_control
def pricing_action(request, pricing_id=None, Client_Info=None):
    """課程定價CRUD操作"""
    try:
        # 安全地解析JSON，处理空body的情况
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        action = request.GET.get('action', 'create')
        
        if action == 'delete':
            if pricing_id:
                pricing = CoursePricing.objects.get(id=pricing_id)
                pricing.delete()
                return JsonResponse({'code': 100, 'msg': '刪除成功'})
            else:
                return JsonResponse({'code': 400, 'msg': '缺少ID參數'})
        
        elif action in ['create', 'update']:
            template_ids = data.get('templates', [])  # 改為多個模板ID
            resort_id = data.get('resort')
            base_price_off_peak = data.get('base_price_off_peak')
            peak_season_surcharge = data.get('peak_season_surcharge', 0)
            additional_person_fee = data.get('additional_person_fee')
            max_capacity = data.get('max_capacity')
            people_tiers_provided = 'people_tiers' in data
            people_tiers = data.get('people_tiers', [])
            is_active = data.get('is_active', True)
            
            if not all([template_ids, resort_id, base_price_off_peak, additional_person_fee, max_capacity]):
                return JsonResponse({'code': 400, 'msg': '所有必填欄位不能為空'})
            
            if not isinstance(template_ids, list) or len(template_ids) == 0:
                return JsonResponse({'code': 400, 'msg': '請至少選擇一個課程模板'})
            
            try:
                templates = CoursekitCourseTemplate.objects.filter(id__in=template_ids)
                if templates.count() != len(template_ids):
                    return JsonResponse({'code': 400, 'msg': '部分課程模板不存在'})
                
                resort = Resorts.objects.get(id=resort_id)
            except Resorts.DoesNotExist:
                return JsonResponse({'code': 400, 'msg': '雪場不存在'})
            
            if people_tiers_provided:
                try:
                    _prepare_people_tiers(people_tiers, max_capacity)
                except ValueError as e:
                    return JsonResponse({'code': 400, 'msg': str(e)})

            with transaction.atomic():
                if action == 'update' and pricing_id:
                    pricing = CoursePricing.objects.get(id=pricing_id)
                    pricing.templates.set(templates)  # 設置多對多關係
                    pricing.resort = resort
                    pricing.base_price_off_peak = base_price_off_peak
                    pricing.peak_season_surcharge = peak_season_surcharge
                    pricing.additional_person_fee = additional_person_fee
                    pricing.max_capacity = max_capacity
                    pricing.is_active = is_active
                    pricing.save()
                    if people_tiers_provided:
                        _sync_course_pricing_tiers(pricing, people_tiers)

                    return JsonResponse({'code': 100, 'msg': '更新成功'})
                else:
                    # 創建新的課程定價
                    pricing = CoursePricing.objects.create(
                        resort=resort,
                        base_price_off_peak=base_price_off_peak,
                        peak_season_surcharge=peak_season_surcharge,
                        additional_person_fee=additional_person_fee,
                        max_capacity=max_capacity,
                        is_active=is_active
                    )
                    pricing.templates.set(templates)  # 設置多對多關係
                    if people_tiers_provided:
                        _sync_course_pricing_tiers(pricing, people_tiers)

                    return JsonResponse({'code': 100, 'msg': '創建成功'})
        
        else:
            return JsonResponse({'code': 400, 'msg': '無效的操作'})
            
    except CoursePricing.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '課程定價不存在'})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': f'操作失敗: {str(e)}'})


# ==================== 雪場設定管理 ====================

def _prepare_equipment_tiers(tiers_data):
    tiers = []
    active_ranges = []
    for item in tiers_data or []:
        try:
            min_people = int(item.get('min_people') or 0)
            max_people = int(item.get('max_people') or 0)
            price = int(item.get('price') or 0)
        except (TypeError, ValueError):
            raise ValueError('裝備租借級距格式錯誤')

        if min_people == 0 and max_people == 0 and price == 0:
            continue
        if min_people < 1 or max_people < min_people:
            raise ValueError('裝備租借級距範圍錯誤')
        if price < 0:
            raise ValueError('裝備租借價格不能小於 0')

        is_active = item.get('is_active', True)
        if is_active:
            for start, end in active_ranges:
                if min_people <= end and max_people >= start:
                    raise ValueError('啟用中的裝備租借級距不能重疊')
            active_ranges.append((min_people, max_people))

        tiers.append({
            'min_people': min_people,
            'max_people': max_people,
            'price': price,
            'is_active': is_active,
            'description': item.get('description', ''),
        })

    tiers.sort(key=lambda tier: (tier['min_people'], tier['max_people']))
    return tiers

def _sync_equipment_tiers(resort, tiers_data):
    EquipmentPricingTier.objects.filter(resort=resort).delete()
    for index, tier in enumerate(_prepare_equipment_tiers(tiers_data)):
        EquipmentPricingTier.objects.create(
            resort=resort,
            min_people=tier['min_people'],
            max_people=tier['max_people'],
            price=tier['price'],
            is_active=tier['is_active'],
            display_order=index,
            description=tier['description'],
        )


def _prepare_equipment_time_slots(slots_data):
    slots = []
    active_labels = set()
    for item in slots_data or []:
        equipment_option = item.get('equipment_option') or 'purchaseAssistanceTime'
        lesson_duration = item.get('lesson_duration') or 'any'
        session_period = item.get('session_period') or 'any'
        day_type = item.get('day_type') or 'same_day'
        course_template_ids = []
        for template_id in item.get('course_template_ids') or item.get('course_templates') or []:
            try:
                course_template_ids.append(int(template_id))
            except (TypeError, ValueError):
                raise ValueError('適用課程項目 ID 必須是數字')
        label = (item.get('label') or '').strip()
        start_time = item.get('start_time') or None
        end_time = item.get('end_time') or None
        description = item.get('description', '')
        if not label and not start_time and not end_time and not description:
            continue
        if not label:
            raise ValueError('裝備協助時段需要填寫名稱')
        is_active = item.get('is_active', True)
        if is_active:
            key = (equipment_option, lesson_duration, session_period, day_type, label.lower())
            if key in active_labels:
                raise ValueError('同一個綁定條件下，啟用中的裝備協助時段名稱不能重複')
            active_labels.add(key)
        slots.append({
            'equipment_option': equipment_option,
            'lesson_duration': lesson_duration,
            'session_period': session_period,
            'day_type': day_type,
            'course_template_ids': sorted(set(course_template_ids)),
            'label': label,
            'start_time': start_time,
            'end_time': end_time,
            'is_active': is_active,
            'description': description,
        })
    return slots


def _sync_equipment_time_slots(resort, slots_data):
    prepared_slots = _prepare_equipment_time_slots(slots_data)
    valid_template_ids = set(
        CoursekitCourseTemplate.objects.filter(
            id__in={template_id for slot in prepared_slots for template_id in slot['course_template_ids']},
            resorts=resort,
        ).values_list('id', flat=True)
    )
    invalid_template_ids = sorted(
        {template_id for slot in prepared_slots for template_id in slot['course_template_ids']} - valid_template_ids
    )
    if invalid_template_ids:
        raise ValueError(f'適用課程項目不屬於此雪場: {invalid_template_ids}')

    EquipmentAssistanceTimeSlot.objects.filter(resort=resort).delete()
    for index, slot in enumerate(prepared_slots):
        created_slot = EquipmentAssistanceTimeSlot.objects.create(
            resort=resort,
            equipment_option=slot['equipment_option'],
            lesson_duration=slot['lesson_duration'],
            session_period=slot['session_period'],
            day_type=slot['day_type'],
            label=slot['label'],
            start_time=slot['start_time'],
            end_time=slot['end_time'],
            is_active=slot['is_active'],
            display_order=index,
            description=slot['description'],
        )
        if slot['course_template_ids']:
            created_slot.course_templates.set(
                CoursekitCourseTemplate.objects.filter(id__in=slot['course_template_ids'], resorts=resort).distinct()
            )


@login_required_control
def resort_settings_new(request, Client_Info=None):
    """雪場設定管理頁面數據API"""
    try:
        # 獲取所有雪場
        resorts = []
        for resort in Resorts.objects.prefetch_related(
            'equipment_pricing_tiers',
            'equipment_assistance_time_slots',
            'equipment_assistance_time_slots__course_templates',
        ).all():
            # 計算每個雪場的統計數據
            course_count = CourseCategory.objects.filter(available_resorts=resort).count()
            fee_count = ResortFee.objects.filter(resort=resort, is_active=True).count()
            
            resorts.append({
                'id': resort.id,
                'name': resort.name,
                'display_name': resort.display_name,
                'auto_scheduling_enabled': resort.auto_scheduling_enabled,
                'course_count': course_count,
                'fee_count': fee_count,
                'equipment_tiers': [
                    {
                        'id': tier.id,
                        'min_people': tier.min_people,
                        'max_people': tier.max_people,
                        'price': tier.price,
                        'is_active': tier.is_active,
                        'display_order': tier.display_order,
                        'description': tier.description,
                    }
                    for tier in resort.equipment_pricing_tiers.all()
                ],
                'equipment_time_slots': [
                    {
                        'id': slot.id,
                        'equipment_option': slot.equipment_option,
                        'lesson_duration': slot.lesson_duration,
                        'session_period': slot.session_period,
                        'day_type': slot.day_type,
                        'course_template_ids': list(slot.course_templates.values_list('id', flat=True)),
                        'label': slot.display_label(),
                        'start_time': slot.start_time.strftime('%H:%M') if slot.start_time else '',
                        'end_time': slot.end_time.strftime('%H:%M') if slot.end_time else '',
                        'is_active': slot.is_active,
                        'display_order': slot.display_order,
                        'description': slot.description,
                    }
                    for slot in resort.equipment_assistance_time_slots.all()
                ]
            })
        
        # 獲取所有費用類型
        fee_types = []
        for fee_type, display_name in ResortFee.FEE_TYPE_CHOICES:
            fee_types.append({
                'value': fee_type,
                'display': display_name
            })
        
        # 獲取所有費用設定
        resort_fees = []
        for fee in ResortFee.objects.all():
            resort_fees.append({
                'id': fee.id,
                'resort_id': fee.resort.id,
                'fee_type': fee.fee_type,
                'fee_type_display': fee.get_fee_type_display(),
                'price': fee.price,
                'is_active': fee.is_active,
                'description': fee.description
            })

        course_templates = [
            {
                'id': template.id,
                'name': template.name,
                'course_type_name': template.course_type.name if template.course_type else '',
                'duration_hours': template.duration_hours,
                'resorts': list(template.resorts.values_list('id', flat=True)),
            }
            for template in CoursekitCourseTemplate.objects.select_related('course_type').prefetch_related('resorts').all()
        ]
        
        data = {
            'resorts': resorts,
            'feeTypes': fee_types,
            'resortFees': resort_fees,
            'courseTemplates': course_templates,
        }
        
        return JsonResponse({
            'code': 100,
            'msg': '成功',
            'data': data
        })
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'msg': f'獲取數據失敗: {str(e)}',
            'data': None
        })

@login_required_control
def resort_action(request, resort_id=None, Client_Info=None):
    """雪場CRUD操作"""
    try:
        # 安全地解析JSON，处理空body的情况
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        action = request.GET.get('action', 'create')
        
        if action == 'delete':
            if resort_id:
                resort = Resorts.objects.get(id=resort_id)
                resort.delete()
                return JsonResponse({'code': 100, 'msg': '刪除成功'})
            else:
                return JsonResponse({'code': 400, 'msg': '缺少ID參數'})
        
        elif action in ['create', 'update']:
            name = data.get('name')
            display_name = data.get('display_name')
            auto_scheduling_enabled = data.get('auto_scheduling_enabled', True)
            
            if not name or not display_name:
                return JsonResponse({'code': 400, 'msg': '雪場名稱和顯示名稱不能為空'})
            
            if action == 'update' and resort_id:
                resort = Resorts.objects.get(id=resort_id)
                resort.name = name
                resort.display_name = display_name
                resort.auto_scheduling_enabled = auto_scheduling_enabled
                resort.save()
                
                return JsonResponse({'code': 100, 'msg': '更新成功'})
            else:
                # 創建新的雪場
                resort = Resorts.objects.create(
                    name=name,
                    display_name=display_name,
                    auto_scheduling_enabled=auto_scheduling_enabled
                )
                
                return JsonResponse({'code': 100, 'msg': '創建成功', 'data': {'id': resort.id}})
        
        else:
            return JsonResponse({'code': 400, 'msg': '無效的操作'})
            
    except Resorts.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '雪場不存在'})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': f'操作失敗: {str(e)}'})

@login_required_control
def resort_fee_action(request, fee_id=None, Client_Info=None):
    """雪場費用CRUD操作"""
    try:
        # 安全地解析JSON，处理空body的情况
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        action = request.GET.get('action', 'create')
        
        if action == 'delete':
            if fee_id:
                fee = ResortFee.objects.get(id=fee_id)
                fee.delete()
                return JsonResponse({'code': 100, 'msg': '刪除成功'})
            else:
                return JsonResponse({'code': 400, 'msg': '缺少ID參數'})
        
        elif action in ['create', 'update']:
            resort_id = data.get('resort_id')
            fee_type = data.get('fee_type')
            price = data.get('price')
            is_active = data.get('is_active', True)
            description = data.get('description', '')
            
            if not resort_id or not fee_type or price is None:
                return JsonResponse({'code': 400, 'msg': '雪場、費用類型和價格不能為空'})
            
            try:
                resort = Resorts.objects.get(id=resort_id)
            except Resorts.DoesNotExist:
                return JsonResponse({'code': 400, 'msg': '雪場不存在'})
            
            if action == 'update' and fee_id:
                fee = ResortFee.objects.get(id=fee_id)
                fee.resort = resort
                fee.fee_type = fee_type
                fee.price = price
                fee.is_active = is_active
                fee.description = description
                fee.save()
                
                return JsonResponse({'code': 100, 'msg': '更新成功'})
            else:
                # 創建新的費用設定
                fee, created = ResortFee.objects.get_or_create(
                    resort=resort,
                    fee_type=fee_type,
                    defaults={
                        'price': price,
                        'is_active': is_active,
                        'description': description
                    }
                )
                
                if not created:
                    # 如果已存在，則更新
                    fee.price = price
                    fee.is_active = is_active
                    fee.description = description
                    fee.save()
                
                return JsonResponse({'code': 100, 'msg': '創建成功', 'data': {'id': fee.id}})
        
        else:
            return JsonResponse({'code': 400, 'msg': '無效的操作'})
            
    except ResortFee.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '費用設定不存在'})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': f'操作失敗: {str(e)}'})

@login_required_control
def bulk_update_resort_fees(request, resort_id, Client_Info=None):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            resort = Resorts.objects.get(id=resort_id)
            is_structured_payload = isinstance(data, dict)
            if isinstance(data, dict):
                equipment_tiers_provided = 'equipment_tiers' in data
                equipment_tiers = data.get('equipment_tiers', [])
                equipment_time_slots_provided = 'equipment_time_slots' in data
                equipment_time_slots = data.get('equipment_time_slots', [])
                data = data.get('fees', [])
            else:
                equipment_tiers_provided = False
                equipment_tiers = None
                equipment_time_slots_provided = False
                equipment_time_slots = None
            
            fee_types_submitted = {item['fee_type'] for item in data}
            all_fee_types = {choice[0] for choice in ResortFee.FEE_TYPE_CHOICES}
            if is_structured_payload:
                all_fee_types = {fee_type for fee_type in all_fee_types if not fee_type.startswith('equipment_')}

            with transaction.atomic():
                # 更新或創建提交的費用
                for item in data:
                    fee_type = item.get('fee_type')
                    price = item.get('price')
                    is_active = item.get('is_active', False)

                    if fee_type not in all_fee_types:
                        continue # Skip invalid fee types

                    #
                    # 轉換 price 確保它是整數
                    try:
                        price = int(price) if price is not None else 0
                    except (ValueError, TypeError):
                        price = 0 # 
                    
                    ResortFee.objects.update_or_create(
                        resort=resort,
                        fee_type=fee_type,
                        defaults={'price': price, 'is_active': is_active}
                    )
                
                # 對於沒有提交的費用類型，將其設置為 inactive
                fees_to_deactivate = all_fee_types - fee_types_submitted
                for fee_type in fees_to_deactivate:
                    ResortFee.objects.update_or_create(
                        resort=resort,
                        fee_type=fee_type,
                        defaults={'price': 0, 'is_active': False}
                    )
                if equipment_tiers_provided:
                    _sync_equipment_tiers(resort, equipment_tiers)
                if equipment_time_slots_provided:
                    _sync_equipment_time_slots(resort, equipment_time_slots)

            return JsonResponse({'code': 100, 'msg': '費用已成功更新'})
        except Resorts.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '找不到指定的雪場'})
        except Exception as e:
            return JsonResponse({'code': 400, 'msg': f'更新失敗: {str(e)}'})
    return JsonResponse({'code': 405, 'msg': '僅允許POST請求'})



@login_required_control
def resort_fee_action(request, fee_id=None, Client_Info=None):
    pass
