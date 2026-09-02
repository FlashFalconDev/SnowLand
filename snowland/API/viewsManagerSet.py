from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from urllib.parse import parse_qs


class ViewsManagerSet(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, AuthenticationFailed):
            return Response({
                'code': 401,
                'msg': '已逾期,重新登入'
            })
        return super().handle_exception(exc)

    @ transaction.atomic
    def post(self, request, category, subcategory):
        print('ViewsManagerSet')
        client_info_pk = request.headers.get('ClientInfoPK')
        Client_Info = ClientInfo.objects.get(pk=client_info_pk)
        try:
            if category == 'finance':
                if subcategory == 'linepay':
                    id = request.data.get('id')
                    secret = request.data.get('secret')
                    Payment_Set_Info, _ = Client_Info.PaymentSetInfo_ClientInfo.get_or_create(
                        vendor_code='LinePay')
                    Payment_Set_Info.DataJSON = {'id': id, 'secret': secret}
                    Payment_Set_Info.save()
                elif subcategory == 'jokpay':
                    store_id = request.data.get('store_id')
                    apikey = request.data.get('apikey')
                    sekey = request.data.get('sekey')
                    Payment_Set_Info, _ = Client_Info.PaymentSetInfo_ClientInfo.get_or_create(
                        vendor_code='JkoPay')
                    Payment_Set_Info.DataJSON = {
                        'store_id': store_id, 'apikey': apikey, 'sekey': sekey}
                    Payment_Set_Info.save()
                elif subcategory == 'invoice':
                    vendor_code = request.data.get('vendor_code')
                    MerchantID = request.data.get('MerchantID')
                    HashKEY = request.data.get('HashKEY')
                    HashIV = request.data.get('HashIV')
                    if Client_Info.InvoiceSetInfo_ClientInfo.all():
                        Client_Info.InvoiceSetInfo_ClientInfo.all().update(is_active=False)
                    Invoice_Set_Info, _ = Client_Info.InvoiceSetInfo_ClientInfo.get_or_create(
                        vendor_code=vendor_code)
                    Invoice_Set_Info.DataJSON = {
                        'MerchantID': MerchantID, 'HashKEY': HashKEY, 'HashIV': HashIV}
                    Invoice_Set_Info.is_active = True
                    Invoice_Set_Info.save()
                elif subcategory == 'acpay':
                    POS_Unique_No = request.data.get('POS_Unique_No')
                    port = request.data.get('port')
                    Payment_Set_Info, _ = Client_Info.PaymentSetInfo_ClientInfo.get_or_create(
                        vendor_code='AcPay')
                    Payment_Set_Info.DataJSON = {
                        'POS_Unique_No': POS_Unique_No, 'port': port}
                    Payment_Set_Info.save()
            elif category == 'external':
                if subcategory == 'print':
                    vendor_code = request.data.get('vendor_code')
                    device_id = request.data.get('device_id')
                    label = request.data.get('label')
                    Print_Set_Info, _ = Client_Info.PrintSetInfo_ClientInfo.get_or_create(
                        vendor_code=vendor_code)
                    Print_Set_Info.device_id = device_id
                    Print_Set_Info.label = label
                    Print_Set_Info.save()
            elif category == 'ai':
                if subcategory == 'ai_account':
                    account_id = request.data.get('Account_id')
                    secret_key = request.data.get('secret_key')
                    Ai_Account_Info, _ = Client_Info.AiAccountInfo_ClientInfo.get_or_create(
                        Client_Info=Client_Info)
                    Ai_Account_Info.account_id = account_id
                    Ai_Account_Info.secret_key = secret_key
                    Ai_Account_Info.save()
            elif category == 'order':
                if subcategory == 'shipping':
                    # 解析查询参数
                    query_string = request.body.decode('utf-8')
                    parsed_data = parse_qs(query_string)
                    print('parsed_data', parsed_data)

                    # 获取 shipping_supplier, shipping_fee, free_shipping_threshold
                    shipping_suppliers = parsed_data.get('shipping_supplier', [])
                    # 检查是否有重复的 shipping_supplier
                    if len(shipping_suppliers) != len(set(shipping_suppliers)):
                        return Response({
                            'code': 400,
                            'msg': '存在重复的供应商ID'})
                    shipping_fees = parsed_data.get('shipping_fee', [])
                    free_shipping_thresholds = parsed_data.get('free_shipping_threshold', [])

                    # 遍历每个 shipping_supplier
                    for index, supplier_id in enumerate(shipping_suppliers):
                        # 获取对应的 shipping_fee 和 free_shipping_threshold
                        shipping_fee = shipping_fees[index] if index < len(shipping_fees) else None
                        free_shipping_threshold = free_shipping_thresholds[index] if index < len(free_shipping_thresholds) else None

                        # 获取 ShippingSupplierInfo 实例
                        try:
                            supplier_instance = ShippingSupplierInfo.objects.get(id=supplier_id)
                        except ShippingSupplierInfo.DoesNotExist:
                            return Response({'error': f'无效的供应商ID: {supplier_id}'}, status=status.HTTP_400_BAD_REQUEST)

                        # 查找或创建新的记录
                        Shipping_Info, _ = Client_Info.ShippingInfo_ClientInfo.get_or_create(
                            Shipping_Supplier_Info=supplier_instance
                        )
                        # 更新或新增 shipping_fee 和 free_shipping_threshold
                        if shipping_fee is not None:
                            Shipping_Info.shipping_fee = shipping_fee
                        if free_shipping_threshold is not None:
                            Shipping_Info.free_shipping_threshold = free_shipping_threshold
                        Shipping_Info.save()
            elif category == 'divination':
                if subcategory == 'button':
                    divination_button = request.data.get('divination_button')
                    Divination_Button_Info, _ = Client_Info.DivinationButtonInfo_ClientInfo.get_or_create(
                        Client_Info=Client_Info)
                    Divination_Button_Info.divination_button = divination_button
                    Divination_Button_Info.save()
                elif subcategory == 'page':
                    text = request.data.get('text')
                    audio_src = request.data.get('audio_src')
                    print('text', text)
                    print('audio_src', audio_src)
                    Divination_Page_Info, _ = Client_Info.DivinationPageInfo_ClientInfo.get_or_create(
                        Client_Info=Client_Info)
                    Divination_Page_Info.text = text
                    Divination_Page_Info.audio_src = audio_src
                    Divination_Page_Info.save()
            return Response({
                'code': 100,
                'msg': '更新成功'})
        except MemberSignupPlatform.DoesNotExist:
            return Response({'error': '無效的序號'}, status=status.HTTP_400_BAD_REQUEST)
