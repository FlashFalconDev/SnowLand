from os import name
from re import I
from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.hashers import check_password
from django.db import transaction
# from Item.models import ItemInfo,ItemCategory,ItemTag,ItemInfoTag,ItemOrder
from Control.funcNav import get_nav_list
from .views import get_page_size
from Control.views import login_required_control
from datetime import datetime
from django.utils import timezone
# from Item.models import ITEM_METHOD_CHOICES,ITEM_ORDER_DETAIL_METHOD_STATE_CHOICES

data_item_type = {
    'food': {'name':'餐點',
    'class':'ri-restaurant-line',
    },
    'drink': {'name':'飲料',
    'class':'ri-cup-line',
    },
    'retail': {'name':'零售商品',
    'class':'ri-shopping-basket-line',
    },
    'event': {'name':'活動',
    'class':'ri-calendar-line',
    },
    'booking': {'name':'預約服務',
    'class':'ri-calendar-line',
    },
    'ingredient': {'name':'成分',
    'class':'ri-calendar-line',
    },
}
#改字典


@login_required_control
def item_category(request,item_type,Client_Info=None):
    print('item_category')
    type = request.GET.get('type')
    
    if type:
        id = request.GET.get('id')
        Item_Category = ItemCategory.objects.get(pk=id,Client_Info=Client_Info,item_type=item_type)
        if type == 'del':
            Item_Category.delete()
            return JsonResponse({'code': 100, 'msg': '刪除成功'})
        elif type == 'is_active':
            is_active = True if request.GET.get('is_active') == '1' else False
            print(f'is_active: {is_active}')
            Item_Category.is_active = is_active
            Item_Category.save()
            if is_active:
                return JsonResponse({'code': 100, 'msg': '啟用成功'})
            else:
                return JsonResponse({'code': 100, 'msg': '停用成功'})
    page, page_size = get_page_size(request)
    name = request.GET.get('name')
    query = ItemCategory.objects.filter(Client_Info=Client_Info,item_type=item_type)
    if name:
        query = query.filter(name__icontains=name)
    item_category_list = query[(page-1)*page_size:page*page_size]
    count = query.count()
    data = {'list': [],'count': count}
    for item_category in item_category_list:
        data['list'].append({'name': item_category.name, 'id': item_category.pk,'is_active': 1 if item_category.is_active else 0,'order': item_category.order,'image':'','description':item_category.description})
    return JsonResponse({'code': 100, 'msg': '取得成功', 'data': data})




@login_required_control
@transaction.atomic
def item_category_form(request,item_type,Client_Info=None):
    print('item_category_form')
    id = request.GET.get('id')
    if request.method == 'POST':
        print('POST')
        print(f'request.POST: {request.POST}')
        #request.POST: <QueryDict: {'name': ['234234'], 'order': ['0'], 'is_active': ['1'], 'description': [''], 'id': ['']}>
        name = request.POST.get('name')
        order = int(request.POST.get('order'))
        is_active = True if request.POST.get('is_active') =='1' else False
        description = request.POST.get('description')
        id = request.POST.get('id')
        try:
            if id:
                id = int(id)
                item_category = ItemCategory.objects.get(pk=id,Client_Info=Client_Info,item_type=item_type)
            else:
                item_category = ItemCategory(Client_Info=Client_Info,item_type=item_type)
            item_category.name = name
            item_category.order = order
            item_category.is_active = is_active
            item_category.description = description
            item_category.save()
            return JsonResponse({'code': 100, 'msg': '新增成功'})
        except Exception as e:
            print(f'error: {e}')
            return JsonResponse({'code': 101, 'msg': '新增失敗'})
    else:
        if id:
            item_category = ItemCategory.objects.get(pk=id)
            print(f'item_category: {item_category}')
        else:
            item_category = None
        data = {'item_category': item_category,
                'item_type':item_type,
                'item_type_name':data_item_type[item_type]['name'],
                'item_type_class':data_item_type[item_type]['class'],
                }
        return render(request, 'Control/tmp/Item/item_category_form.html', data)


@login_required_control
def item_info(request,item_type,Client_Info=None):
    print('item_info')
    tag_list = []
    page, page_size = get_page_size(request)
    item_name = request.GET.get('item_name')
    item_category = request.GET.get('item_category')
    query = ItemInfo.objects.filter(    
                Client_Info=Client_Info,item_type=item_type)
    if item_name:
        query = query.filter(name__icontains=item_name)
    if item_category:
        query = query.filter(Item_Category__id=item_category)
    Item_s = query.order_by('-created_at')[(page-1)*page_size:page*page_size]
    #計算所有數量
    count = query.count()
    
    for Item_ in Item_s:
        ItemImage = []
        Item_Image = Item_.ItemImage_ItemInfo.all()
        for Item_Image_ in Item_Image:
            ItemImage.append(Item_Image_.Static_Usage_Record.file_url)
        try:
            tag_list.append(
                {
                    "item_id": Item_.pk,
                    "item_name": Item_.name,
                    "item_base_price": Item_.base_price,
                    "item_description": Item_.description,
                    "item_image": ItemImage,
                    "item_unit": Item_.unit,
                    "item_create_time": Item_.created_at,
                    "item_update_time": Item_.updated_at,
                    "is_active": 1 if Item_.is_active else 0,
                    "sku": Item_.sku,
                    "item_tags": [tag.Item_Tag.name for tag in ItemInfoTag.objects.filter(Item_Info=Item_,is_hidden=False)],
                    "item_tags_hidden": [tag.Item_Tag.name for tag in ItemInfoTag.objects.filter(Item_Info=Item_,is_hidden=True)],
                    "item_category": Item_.Item_Category.name if Item_.Item_Category else ''
                }
            )
        except Exception as e:
            print(f'error: {e}')
    # print(f'tag_list: {tag_list}')
    return JsonResponse({
        'code': 100,
        'msg': '取得成功',
        'data': {
            'count': count,
            'list': tag_list
        }})


@login_required_control
@transaction.atomic
def item_info_form(request,item_type,Client_Info=None):
    print('item_food_form')
    id = request.GET.get('id')
    if request.method == 'POST':
        print('POST')
        print(f'request.POST: {request.POST}')
        name = request.POST.get('name')
        sku = request.POST.get('sku')
        unit = request.POST.get('unit')
        base_price = request.POST.get('base_price')
        cost_price = request.POST.get('cost_price')
        item_category_id = request.POST.get('item_category')
        is_active = request.POST.get('is_active')
        description = request.POST.get('description')   
        id = request.POST.get('id')
        item_tags = request.POST.getlist('item_tags')
        item_tags_hidden = request.POST.getlist('item_tags_hidden')
        print(f'item_tags: {item_tags}')
        try:
            if id:
                id = int(id)
                Item_Info = ItemInfo.objects.get(pk=id,Client_Info=Client_Info,item_type=item_type)
            else:
                Item_Info = ItemInfo(Client_Info=Client_Info,item_type=item_type)
            Item_Info.name = name
            Item_Info.sku = sku
            Item_Info.unit = unit
            Item_Info.base_price = base_price
            Item_Info.cost_price = cost_price
            Item_Info.is_active = is_active
            Item_Info.description = description
            if item_category_id:
                print(f'item_category_id: {item_category_id}')
                Item_Info.Item_Category = ItemCategory.objects.get(pk=item_category_id,Client_Info=Client_Info,item_type=item_type)   
            

            Item_Info_Tag = ItemInfoTag.objects.filter(Item_Info=Item_Info)
            Item_Info_Tag.delete()
            if item_tags:
                for item_info_tag in item_tags[0].split(','):
                    ItemInfoTag.objects.get_or_create(Item_Info=Item_Info,Item_Tag=ItemTag.objects.get(pk=item_info_tag),is_hidden=False)
            if item_tags_hidden:
                for item_info_tag in item_tags_hidden[0].split(','):
                    try:
                        ItemInfoTag.objects.get_or_create(Item_Info=Item_Info,Item_Tag=ItemTag.objects.get(pk=item_info_tag),is_hidden=True)
                    except Exception as e:
                        print(f'error: {e}')
            Item_Info.save()
            return JsonResponse({'code': 100, 'msg': '新增成功' if not id else '修改成功'})
        except Exception as e:
            print(f'error: {e}')
            return JsonResponse({'code': 101, 'msg': '新增失敗' if not id else '修改失敗'})
    try:
        item_tags = []
        item_tags_hidden = []
        item_image_main = []
        item_image_list = []
        if id:
            print(f'id: {id}')
            Item_Info = ItemInfo.objects.get(pk=id,Client_Info=Client_Info,item_type=item_type)
            if request.GET.get('type') == 'is_active':
                Item_Info.is_active = True if request.GET.get('is_active') == '1' else False
                Item_Info.save()
                return JsonResponse({'code': 100, 'msg': '已上架' if Item_Info.is_active else '已下架'})
            elif request.GET.get('type') == 'del':
                print(f'刪除')
                Item_Info.delete()
                return JsonResponse({'code': 100, 'msg': '刪除成功'})
            Item_Info_Tag = ItemInfoTag.objects.filter(Item_Info=Item_Info)
            item_tags = [tag.Item_Tag.pk for tag in Item_Info_Tag if not tag.is_hidden]
            item_tags_hidden = [tag.Item_Tag.pk for tag in Item_Info_Tag if tag.is_hidden]
            Item_Image = Item_Info.ItemImage_ItemInfo.all()
            if Item_Image:
                for Item_Image_ in Item_Image:
                    if Item_Image_.order == 0:
                        item_image_main.append(Item_Image_.Static_Usage_Record.file_url)
                    else:
                        item_image_list.append(Item_Image_.Static_Usage_Record.file_url)
        else:
            Item_Info = ItemInfo(Client_Info=Client_Info,item_type=item_type)
        Item_Category = ItemCategory.objects.filter(Client_Info=Client_Info,item_type=item_type)
        Item_Tag_List = [{"id":tag.pk,"name":tag.name} for tag in ItemTag.objects.filter(Client_Info=Client_Info)]
        Item_Tag_List.insert(0, {"id":'0','name':'請選擇標籤'})
        print(f'Item_Tag: {Item_Tag_List}')
    except Exception as e:
        print(f'error: {e}')
    return render(request, f'Control/tmp/Item/{item_type}/item_info_form.html', {'Item_Info': Item_Info,'Item_Category': Item_Category,'Item_Tag_List': Item_Tag_List,'item_tags': item_tags,'item_tags_hidden': item_tags_hidden,'item_image_main': item_image_main,'item_image_list': item_image_list})

@login_required_control
def item_info_image(request,item_type,Client_Info=None):
    print('item_info_image')
    id = request.GET.get('id')
    item_image_main = []
    item_image_list = []
    Item_Info = ItemInfo.objects.get(pk=id,Client_Info=Client_Info,item_type=item_type)
    Item_Image = Item_Info.ItemImage_ItemInfo.all()
    if Item_Image:
        for Item_Image_ in Item_Image:
            if Item_Image_.order == 0:
                item_image_main.append(Item_Image_.Static_Usage_Record.file_url)
            else:   
                item_image_list.append(Item_Image_.Static_Usage_Record.file_url)
    return render(request, f'Control/tmp/Item/{item_type}/item_info_image.html', {'Item_Info': Item_Info,'item_image_main': item_image_main,'item_image_list': item_image_list})

@login_required_control
def item_order(request,item_type,Client_Info=None):
    print('item_order')
    Item_Order_list = []
    if item_type == 'dashboard':
        Item_Order = ItemOrder.objects.filter(Client_Info=Client_Info).order_by('-created_at').exclude(status='deleted')[:8]
        count = 0
    else:
        item_order_status = request.GET.get('item_order_status')
        # item_order_status = 'issued'
        date_range = request.GET.get('date_range')  
        query = ItemOrder.objects.filter(Client_Info=Client_Info,ItemOrderDetail_ItemOrder__item_type=item_type).order_by('-created_at').exclude(status='deleted').distinct()
        if item_order_status:
            query = query.filter(status=item_order_status)
        if date_range:
            # 解析日期範圍，格式為 "YYYY-MM-DD,YYYY-MM-DD"
            try:
                start_date, end_date = date_range.split(',')
                start_datetime = timezone.make_aware(datetime.strptime(start_date.strip(), '%Y-%m-%d'))
                end_datetime = timezone.make_aware(datetime.strptime(end_date.strip(), '%Y-%m-%d').replace(hour=23, minute=59, second=59))
                query = query.filter(created_at__range=[start_datetime, end_datetime])
            except ValueError as e:
                print(f'日期範圍格式錯誤: {e}')
                # 如果日期格式錯誤，忽略日期篩選
        page, page_size = get_page_size(request)
        Item_Order = query[(page-1)*page_size:page*page_size]
        count = query.count()
        
    for Item_Order_ in Item_Order:
        print(f'Item_Order_: {Item_Order_.sn}')
        print(f'Item_Order_: {Item_Order_.status}')
        if Item_Order_.Member_Card:
            item_order_member_name = Item_Order_.Member_Card.Member_Info.name
        else:
            item_order_member_name = '非會員'
        item_order_type = []
        item_order_method = []
        item_order_method_state = []
        for item_order_detail in Item_Order_.ItemOrderDetail_ItemOrder.all():
            if item_order_detail.item_type == 'food':
                item_order_type.append('餐點')
            elif item_order_detail.item_type == 'event':
                item_order_type.append('活動')
            elif item_order_detail.item_type == 'booking':
                item_order_type.append('預約')
            elif item_order_detail.item_type == 'ingredient':
                item_order_type.append('成分')
            elif item_order_detail.item_type == 'retail':
                item_order_type.append('商品')
            try:
                item_order_method.append(ITEM_METHOD_CHOICES[item_order_detail.consume_method.method])
            except Exception as e:
                item_order_method.append('')
            try:
                item_order_method_state.append(ITEM_ORDER_DETAIL_METHOD_STATE_CHOICES[item_order_detail.consume_method.state])
            except Exception as e:
                item_order_method.append('')
        try:
            Item_Order_list.append(
                {
                    "item_order_id": Item_Order_.pk,
                    "item_order_sn": Item_Order_.sn,
                    "item_order_status": Item_Order_.status,
                    "item_order_total_amount": Item_Order_.total_amount,
                    "item_order_discount_amount": Item_Order_.discount_amount,
                    "item_order_payment_amount": Item_Order_.payment_amount,
                    "item_order_create_time": Item_Order_.created_at,
                    "item_order_member_name": item_order_member_name,
                    "item_order_type": item_order_type,
                    "item_order_method": item_order_method,
                    "item_order_method_state": item_order_method_state
                }
            )
        except Exception as e:
            print(f'error: {e}')
    return JsonResponse({
        'code': 100,
        'msg': '取得成功',
        'data': {
            'list': Item_Order_list,
            'count': count
        }})

@login_required_control
def item_order_status(request,Client_Info=None):
    print('item_order_status')
    type = request.GET.get('type')
    item_order_sn = request.GET.get('item_order_sn')
    if item_order_sn:
        item_order_sn_list = item_order_sn.split(',')
        n = 0
        for item_order_sn_ in item_order_sn_list:
            Item_Order = ItemOrder.objects.get(sn=item_order_sn_,Client_Info=Client_Info)
            if type == 'del':
                Item_Order.status = 'deleted'
                msg = '已刪除'
            elif type == 'paid':
                Item_Order.status = 'paid'
                msg = '已付款'
            elif type == 'partially_paid':
                Item_Order.status = 'partially_paid'
                msg = '部分付款'
            elif type == 'error':
                Item_Order.status = 'error'
                msg = '付款異常'
            elif type == 'refunded':
                Item_Order.status = 'refunded'
                msg = '已退款'
            elif type == 'cancelled':
                Item_Order.status = 'cancelled'
                msg = '已取消'
            elif type == 'pending':
                Item_Order.status = 'pending'
                msg = '待付款'
            n+=1

            Item_Order.save()
        return JsonResponse({'code': 100, 'msg': f'{n}筆訂單已更新為[{msg}]'})
    else:
        return JsonResponse({'code': 401, 'msg': '請選擇訂單'})
   