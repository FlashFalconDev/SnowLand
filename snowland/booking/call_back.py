from django.http import HttpResponse
from booking.Newebpay import aes256_cbc_decrypt, sha256_hash
from booking.models import Reservation, Payment
import json
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User

@csrf_exempt
def call_back(request, tunnel):
    if tunnel == 'NewebPay':
        if request.method == 'POST':
            trade_info = request.POST.get('TradeInfo', '')
            trade_sha = request.POST.get('TradeSha', '')
            merchant_id = request.POST.get('MerchantID', '')

            try:
                stored_merchant_id = 'MS3680822811'
                HashKey = 'tXnG2aLtEnVzACrJY3CW0SLCLyFYZDEf'
                HashIV = 'PKmJnNJCcJyXpqcC'

                # 驗證 TradeSha
                expected_sha = sha256_hash(trade_info, HashKey, HashIV)

                if expected_sha != trade_sha:
                    return HttpResponse("Invalid TradeSha", status=400)

                # 解密 TradeInfo
                try:
                    decrypt_str = aes256_cbc_decrypt(trade_info, HashKey, HashIV)

                    # 将解密后的字符串解析为字典
                    decrypt_data = json.loads(decrypt_str)

                    # 處理交易結果
                    status = decrypt_data.get('Status', '')
                    result = decrypt_data.get('Result', {})
                    merchant_order_no = result.get('MerchantOrderNo', '')

                    if status == 'SUCCESS':
                        try:
                            user_id = request.GET.get('user_id', '')
                            user = User.objects.get(id=user_id)
                            # 使用藍新金流付款
                            payment = Payment.objects.get(reservation_group=merchant_order_no)
                            payment.status = 'paid'
                            payment.payment_method = 'newebpay'
                            payment.user = user
                            payment.DataJSON = decrypt_data
                            payment.save()

                            # 返回成功响应
                            return HttpResponse('OK')
                        except Reservation.DoesNotExist:
                            return HttpResponse("Order not found", status=404)
                    else:
                        return HttpResponse("Payment failed", status=400)

                except Exception as decrypt_error:
                    return HttpResponse(f"Decrypt error: {str(decrypt_error)}", status=500)
            except Exception as e:
                return HttpResponse(f"Internal server error: {str(e)}", status=500)