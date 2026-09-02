from django.conf import settings
from django.http import JsonResponse
from Control.views import login_required_control
from django.shortcuts import render
from django.db import transaction
# from External.models import PrintSetInfo,PrintAction,PRINT_VENDOR_CHOICES,PRINT_ACTION_CHOICES
# from Finance.models import INVOICE_VENDOR_CHOICES
import json
RUN_HOST = settings.RUN_HOST


@login_required_control
@transaction.atomic
def finance (request,finance_type,Client_Info=None):
    print('linepay')
    data = {'RUN_HOST': RUN_HOST}
    if finance_type == 'linepay':
        Payment_Set_Info, _ = Client_Info.PaymentSetInfo_ClientInfo.get_or_create(
            vendor_code='LINEPay')
        data['id'] = Payment_Set_Info.DataJSON.get('id','')
        data['secret'] = Payment_Set_Info.DataJSON.get('secret','')
        data['is_active'] = 1 if Payment_Set_Info.is_active else 0
        if request.method == 'POST':
            id = request.POST.get('id')
            secret = request.POST.get('secret')
            is_active = request.POST.get('is_active')
            print(f'is_active: {is_active}')
            Payment_Set_Info.DataJSON = {'id': id, 'secret': secret}
            Payment_Set_Info.is_active = True if is_active == '1' else False
            print(f'Payment_Set_Info.DataJSON: {Payment_Set_Info.DataJSON}')
            print(f'Payment_Set_Info.is_active: {Payment_Set_Info.is_active}')
            Payment_Set_Info.save()
            return JsonResponse({'code': 100, 'msg': '保存成功'})
        
    elif finance_type == 'jokpay':
        Payment_Set_Info, _ = Client_Info.PaymentSetInfo_ClientInfo.get_or_create(
            vendor_code='JkoPay')
        data['store_id'] = Payment_Set_Info.DataJSON.get('store_id','')
        data['apikey'] = Payment_Set_Info.DataJSON.get('apikey','')
        data['sekey'] = Payment_Set_Info.DataJSON.get('sekey','')
        data['is_active'] = 1 if Payment_Set_Info.is_active else 0
        if request.method == 'POST':
            store_id = request.POST.get('store_id')
            apikey = request.POST.get('apikey')
            sekey = request.POST.get('sekey')
            is_active = request.POST.get('is_active')
            Payment_Set_Info.DataJSON = {
                'store_id': store_id, 'apikey': apikey, 'sekey': sekey}
            Payment_Set_Info.is_active = True if is_active == '1' else False
            Payment_Set_Info.save()
            return JsonResponse({'code': 100, 'msg': '保存成功'})
        
    elif finance_type == 'acpay':
        Payment_Set_Info, _ = Client_Info.PaymentSetInfo_ClientInfo.get_or_create(
            vendor_code='ACPay')
        data['POS_Unique_No'] = Payment_Set_Info.DataJSON.get('POS_Unique_No','')
        data['port'] = Payment_Set_Info.DataJSON.get('port','')
        data['is_active'] = 1 if Payment_Set_Info.is_active else 0

        if request.method == 'POST':
            is_active = request.POST.get('is_active')
            POS_Unique_No = request.POST.get('POS_Unique_No')
            port = request.POST.get('port')
            Payment_Set_Info.DataJSON = {
                'POS_Unique_No': POS_Unique_No, 'port': port}
            Payment_Set_Info.is_active = True if is_active == '1' else False
            Payment_Set_Info.save()
            return JsonResponse({'code': 100, 'msg': '保存成功'})
    
    return render(request, f'Control/tmp/set/{finance_type}.html', data)

@login_required_control
@transaction.atomic
def print_settings(request,Client_Info=None):
    data = {'RUN_HOST': RUN_HOST}
    data['PRINT_VENDOR_CHOICES'] = {'0': '請選擇'}
    for key, value in PRINT_VENDOR_CHOICES.items():
        data['PRINT_VENDOR_CHOICES'][key] = value
    data['PRINT_ACTION_CHOICES'] = {'0': '請選擇'}
    for key, value in PRINT_ACTION_CHOICES.items():
        data['PRINT_ACTION_CHOICES'][key] = value
    print_set_info_list = []
    print_set_info_F = PrintSetInfo.objects.filter(Client_Info=Client_Info)
    for print_set_info in print_set_info_F:
        action_str=''
        action_must_str=''
        for action in print_set_info.PrintAction_PrintSetInfo.filter(must=False):
            action_str += action.action + ','
        action_str = action_str[:-1]
        for action in print_set_info.PrintAction_PrintSetInfo.filter(must=True):
            action_must_str += action.action + ','
        action_must_str = action_must_str[:-1]
        print_set_info_list.append({
            'id': print_set_info.id,
            'vendor_code': print_set_info.vendor_code,
            'device_id': print_set_info.device_id,
            'label': print_set_info.label,
            'action': action_str,
            'action_must': action_must_str,
        })
    data['print_set_info_F'] = print_set_info_list
    if request.method == 'POST':
        import json
        try:
            # 解析 JSON 數據
            json_data = json.loads(request.body)
            print(f'json_data: {json_data}')
            
            # 收集所有處理過的ID
            processed_ids = []
            # 用於去重的集合
            processed_records = set()
            
            # 處理表單數組數據
            for form_item in json_data:
                vendor_code = form_item.get('vendor_code')
                device_id = form_item.get('device_id') 
                label = form_item.get('label')
                action = form_item.get('action')
                action_must = form_item.get('action_must')
                id = form_item.get('id')
                
                # 更嚴格的過濾條件：確保所有必要字段都有值且不為空字符串
                if not vendor_code or not device_id or not label or \
                   vendor_code.strip() == '' or device_id.strip() == '' or label.strip() == '':
                    print(f'跳過無效記錄 - vendor_code: {vendor_code}, device_id: {device_id}, label: {label}')
                    continue
                
                # 去重邏輯：如果有ID，檢查是否已處理過
                if id and id.strip():  # 確保ID不是空字符串
                    if id in processed_records:
                        print(f'跳過重複記錄 - id: {id}')
                        continue  # 跳過重複的記錄
                    processed_records.add(id)
                
                print(f'處理記錄 - id: {id}, vendor_code: {vendor_code}, device_id: {device_id}, label: {label}')
                
                if id and id.strip():  # 如果有ID且不為空，表示是更新現有記錄
                    print_set_info = PrintSetInfo.objects.get(pk=id, Client_Info=Client_Info)
                    print_set_info.vendor_code = vendor_code
                    print_set_info.device_id = device_id
                    print_set_info.label = label
                    print_set_info.save()
                    processed_ids.append(int(id))
                else:  # 如果沒有ID或ID為空，表示是新建記錄
                    print_set_info = PrintSetInfo.objects.create(
                        Client_Info=Client_Info,
                        vendor_code=vendor_code,
                        device_id=device_id,
                        label=label,
                    )
                    processed_ids.append(print_set_info.pk)
                
                # 先清除該PrintSetInfo的所有PrintAction
                PrintAction.objects.filter(Print_Set_Info=print_set_info).delete()
                
                # 處理action
                if action:
                    action_list = action.split(',')
                    for action_item in action_list:
                        if action_item.strip():  # 確保不是空字符串
                            PrintAction.objects.create(
                                Print_Set_Info=print_set_info,
                                action=action_item.strip(),
                                must=False
                            )
                print(print_set_info.PrintAction_PrintSetInfo.filter(must=False))
                # 處理action_must
                if action_must:
                    action_must_list = action_must.split(',')
                    for action_must_item in action_must_list:
                        if action_must_item.strip():  # 確保不是空字符串
                            Print_Action, _ = PrintAction.objects.get_or_create(
                                Print_Set_Info=print_set_info,
                                action=action_must_item.strip(),
                            )
                            Print_Action.must = True
                            Print_Action.save()
            # 刪除沒有在此次POST中處理到的記錄
            PrintSetInfo.objects.filter(Client_Info=Client_Info).exclude(id__in=processed_ids).delete()
            
            print(f'最終處理的IDs: {processed_ids}')
                
        except json.JSONDecodeError:
            return JsonResponse({'code': 400, 'msg': 'Invalid JSON data'})
            
        return JsonResponse({'code': 100, 'msg': '保存成功'})
    return render(request, f'Control/tmp/set/print.html', data)

@login_required_control
@transaction.atomic
def invoice(request,Client_Info=None):
    data = {'RUN_HOST': RUN_HOST,'Invoice_Set_Info':{'is_active':1}}
    data['INVOICE_VENDOR_CHOICES'] = {'0': '請選擇'}
    for key, value in INVOICE_VENDOR_CHOICES.items():
        data['INVOICE_VENDOR_CHOICES'][key] = value
    if Client_Info.InvoiceSetInfo_ClientInfo.all():
        Invoice_Set_Info = Client_Info.InvoiceSetInfo_ClientInfo.all().first()
        data['Invoice_Set_Info'] = Invoice_Set_Info.DataJSON
        data['Invoice_Set_Info']['vendor_code'] = Invoice_Set_Info.vendor_code
        data['Invoice_Set_Info']['is_active'] = 1 if Invoice_Set_Info.is_active else 0
    if request.method == 'POST':
        import json
        try:
            # 解析 JSON 數據
            json_data = json.loads(request.body)
            print(f'json_data: {json_data}')
            for item in json_data:
                print(f'item: {item}')
                vendor_code = item.get('vendor_code')
                merchant_id = item.get('merchant_id')
                hash_key = item.get('hash_key')
                hash_iv = item.get('hash_iv')
                is_active = item.get('is_active')
                print(f'is_active: {is_active}')
                if vendor_code and merchant_id and hash_key and hash_iv:
                    Invoice_Set_Info_all = Client_Info.InvoiceSetInfo_ClientInfo.all()
                    if Invoice_Set_Info_all:
                        Invoice_Set_Info = Invoice_Set_Info_all.first()
                    else:
                        Invoice_Set_Info = Client_Info.InvoiceSetInfo_ClientInfo.create(
                            vendor_code=vendor_code,
                            is_active=is_active
                        )

                    Invoice_Set_Info.vendor_code = vendor_code
                    Invoice_Set_Info.is_active = is_active
                    Invoice_Set_Info.DataJSON = {
                        'MerchantID': merchant_id,
                        'HashKEY': hash_key,
                        'HashIV': hash_iv
                    }
                    Invoice_Set_Info.save()                
        except json.JSONDecodeError:
            return JsonResponse({'code': 400, 'msg': 'Invalid JSON data'})
        return JsonResponse({'code': 100, 'msg': '保存成功'})
    return render(request, f'Control/tmp/set/invoice.html', data)

@login_required_control
@transaction.atomic
def table(request,Client_Info=None):
    data = {'RUN_HOST': RUN_HOST}
    grid_size = 25
    tables_layout = get_table(Client_Info,grid_size)
    
    data = {
        'RUN_HOST': RUN_HOST,
        'tables_layout': tables_layout,  # 傳遞桌子布局數據
    }
    print(data)
    if request.method == 'POST':
        import json
        try:
            # 解析 JSON 數據
            json_data = json.loads(request.body)
            print(f'json_data: {json_data}')
            for item in json_data:
                print(f'item: {item}')
                table_name = item.get('table_name')
                table_type = item.get('table_type')
                table_x = item.get('table_x')
                table_y = item.get('table_y')
                table_width = item.get('table_width')
                table_height = item.get('table_height')
                table_capacity = item.get('table_capacity')
                table_radius = item.get('table_radius')
                table_id = item.get('id')
                if table_id:
                    table_obj = Client_Info.TableType_ClientInfo.get(pk=table_id)
                    table_obj.table_name = table_name
                    table_obj.table_type = table_type
                    table_obj.table_x = table_x*grid_size
                    table_obj.table_y = table_y*grid_size
                    table_obj.table_width = table_width*grid_size
                    table_obj.table_height = table_height*grid_size
                    table_obj.table_capacity = table_capacity
                    table_obj.table_radius = table_radius*grid_size
                    table_obj.save()
                else:
                    table_obj = Client_Info.TableType_ClientInfo.create(
                        table_name=table_name,
                        table_type=table_type,
                        table_x=table_x*grid_size,
                        table_y=table_y*grid_size,
                        table_width=table_width*grid_size,
                        table_height=table_height*grid_size,
                        table_capacity=table_capacity,
                        table_radius=table_radius*grid_size
                    )
        except json.JSONDecodeError:
            return JsonResponse({'code': 400, 'msg': 'Invalid JSON data'})
        return JsonResponse({'code': 100, 'msg': '保存成功'})
    if request.method == 'DELETE':
        table_id = request.GET.get('id')
        table_obj = Client_Info.TableType_ClientInfo.get(pk=table_id)
        table_obj.delete()
        return JsonResponse({'code': 100, 'msg': '刪除成功'})
    
    return render(request, f'Control/tmp/set/table.html', data)



def get_table(Client_Info,grid_size=25):
    table_type_list = Client_Info.TableType_ClientInfo.all()
    tables_layout = [
        {
            'id': table.pk,
            'name': table.table_name,
            'type': table.table_type,
            'gridX': table.table_x/grid_size,
            'gridY': table.table_y/grid_size,
            'gridWidth': table.table_width/grid_size,
            'gridHeight': table.table_height/grid_size,
            'capacity': table.table_capacity,
            'radius': getattr(table, 'table_radius', 0)/grid_size
        }
        for table in table_type_list
    ]
    return tables_layout