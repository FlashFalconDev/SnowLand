from django.shortcuts import render
import binascii
import hashlib
import requests
import json
from Crypto.Cipher import AES
from Crypto.Cipher.AES import MODE_GCM, MODE_CBC
from Crypto.Util.Padding import pad, unpad
import time
import urllib.parse
from hashlib import sha256
import base64
import time
from django.http import HttpResponse, JsonResponse
import datetime


def aes256_cbc_encrypt(parameter, key, iv):
    parameter, key, iv = parameter.encode(), key.encode(), iv.encode()
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    encrypt_data = str(binascii.b2a_hex(cipher.encrypt(
        pad(parameter, block_size=16))), "utf-8")  # 改為 block_size=16
    return encrypt_data


# AES256-GCM加密 (parameter=dic型態的參數, key=商店HashKey, iv=商店HashIV)
def aes256_gcm_encrypt(parameter, key, iv):
    parameter, key, iv = parameter.encode(), key.encode(), iv.encode()
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    encrypt_data = cipher.encrypt(pad(parameter, AES.block_size))
    authTag = cipher.digest()
    encrypt_data = str(binascii.b2a_hex(encrypt_data), "utf-8")
    authTag = str(binascii.b2a_hex(authTag), "utf-8")
    iv = iv.decode("utf-8")
    encrypt_data = iv+"." + encrypt_data + "." + authTag
    return encrypt_data  # , authTag


# AES256-CBC解密 (encrypt_data=交易完成系統回傳之參數, key=商店HashKey, iv=商店HashIV)
def aes256_cbc_decrypt(encrypt_data, key, iv):
    encrypt_data, key, iv = encrypt_data.encode(), key.encode(), iv.encode()
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    parameter = unpad(cipher.decrypt(binascii.a2b_hex(
        encrypt_data)), block_size=32).decode("utf-8")
    return parameter


# AES256-GCM解密 (encrypt_data=交易完成系統回傳之參數, key=商店HashKey, iv=商店HashIV, authTag=加密時產生的解密用隨機數)
def aes256_gcm_decrypt(encrypt_data, key, iv):
    encrypt_data, key, iv = encrypt_data.encode(), key.encode(), iv.encode()
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    parameter = unpad(cipher.decrypt(binascii.a2b_hex(
        encrypt_data)), AES.block_size).decode("utf-8")
    return parameter


# SHA256壓碼 (encrypt_data=AES256加密後的值, key=商店HashKey, iv=商店HashIV)
def sha256_hash(encrypt_data, key, iv):
    TradeValue = f"HashKey={key}&{encrypt_data}&HashIV={iv}"  # 確認順序正確
    hashs = hashlib.sha256(TradeValue.encode("utf-8")).hexdigest()
    hashs = str.upper(hashs)
    return hashs



def npay(data):

    store_data = data['store']
    # 这里假设 JSON 資料结构中包含了 'body' 键
    body_data = data['body']
    # url = "https://core.newebpay.com/MPG/mpg_gateway"  # 藍新金流正試環境的 URL
    url = "https://ccore.newebpay.com/MPG/mpg_gateway"  # 藍新金流測式環境的 URL
    # 商店的 API 資訊
    MerchantID = store_data['MerchantID']  # 商店代號
    HashKey = store_data['HashKey']
    HashIV = store_data['HashIV']
    # 生成請求參數
    data = {
        "MerchantID": MerchantID,
        "RespondType": "JSON",
        "TimeStamp": int(time.time()),  # 使用當前的 Unix timestamp
        "Version": "2.0",
        "MerchantOrderNo": body_data['OrderNo'],  # 商店自訂訂單編號
        "Amt": body_data['price'],  # 訂單金額
        "ItemDesc": body_data['product'],
        "NotifyURL": body_data['NotifyURL'],
    }

    query_str = urllib.parse.urlencode(data)
    encrypt_data = aes256_cbc_encrypt(query_str, HashKey, HashIV)
    hashs = sha256_hash(encrypt_data, HashKey, HashIV)

    params = {
        "url": url,
        "MerchantID": MerchantID,
        "TradeInfo": encrypt_data,
        "TradeSha": hashs,
        "Version": "2.0"
    }
    # HTTP 請求標頭，包含 User-Agent
    htmls = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        <title>線上付款</title>
    </head>
    <body>
        <form style='display:none' id='form1' name='Newebpay' method='post' action='{params['url']}'>
            <input type='hidden' name='MerchantID' value='{params['MerchantID']}'>
            <input type='hidden' name='TradeInfo' value='{params['TradeInfo']}'>
            <input type='hidden' name='TradeSha' value='{params['TradeSha']}'>
            <input type='hidden' name='Version' value='{params['Version']}'>
            <input type='submit' value='Submit'>
        </form>
        <script type='text/javascript'>document.getElementById('form1').submit();</script>
    </body>
    </html>
    """
    return htmls

# def npay(data):
#     store_data = data['store']
#     body_data = data['body']

#     url = "https://ccore.newebpay.com/MPG/mpg_gateway"  # 測試環境
#     MerchantID = store_data['MerchantID']
#     HashKey = store_data['HashKey']
#     HashIV = store_data['HashIV']

#     params = {
#         "MerchantID": MerchantID,
#         "RespondType": "JSON",
#         "TimeStamp": int(time.time()),
#         "Version": "2.0",
#         "MerchantOrderNo": body_data['OrderNo'],
#         "Amt": body_data['price'],
#         "ItemDesc": body_data['product'],
#         "NotifyURL": body_data['NotifyURL'],
#     }

#     query_str = urllib.parse.urlencode(params)
#     encrypt_data = aes256_cbc_encrypt(query_str, HashKey, HashIV)
#     TradeSha = sha256_hash(encrypt_data, HashKey, HashIV)

#     post_data = {
#         "MerchantID": MerchantID,
#         "TradeInfo": encrypt_data,
#         "TradeSha": TradeSha,
#         "Version": "2.0"
#     }

#     # 在標頭中加入User-Agent
#     headers = {
#         "User-Agent": "newebpay_46617703",   # 根據藍新要求代入User-Agent字串
#         "Content-Type": "application/x-www-form-urlencoded"
#     }

#     # 發送 POST 請求
#     response = requests.post(url, data=post_data, headers=headers)

#     # 藍新會回傳HTML（付款頁面），非JSON
#     # 如果要在後端處理這個回傳值是不合適的，該HTML應該直接顯示給使用者
#     print("回傳HTML：", response.text)

#     # 正確流程：將post_data產生出HTML表單，前端瀏覽器提交該表單給藍新，
#     # 瀏覽器會自動帶User-Agent，不須您在後端寫死。
#     # 以下為回傳表單的範例（供前端顯示，並由前端自動submit）

#     htmls = f"""
#     <!DOCTYPE html>
#     <html>
#     <head>
#         <meta charset='utf-8'>
#         <title>線上付款</title>
#     </head>
#     <body>
#         載入中請稍候.....
#         <form style='display:none' id='form1' name='Newebpay' method='post' action='{url}'>
#             <input type='hidden' name='MerchantID' value='{MerchantID}'>
#             <input type='hidden' name='TradeInfo' value='{encrypt_data}'>
#             <input type='hidden' name='TradeSha' value='{TradeSha}'>
#             <input type='hidden' name='Version' value='2.0'>
#         </form>
#         <script type='text/javascript'>
#             document.getElementById('form1').submit();
#         </script>
#     </body>
#     </html>
#     """
#     return htmls

# 定期定額
def napy_ndnp(data):
    store_data = data['store']
    body_data = data['body']
    url = "https://ccore.newebpay.com/MPG/period"  # 藍新金流測試環境的 URL

    MerchantID = store_data['MerchantID']
    HashKey = store_data['HashKey']
    HashIV = store_data['HashIV']
    # now = datetime.datetime.now()

# 印出現在時間
    # print("現在時間:", now)
    post_data = {
        "RespondType": "JSON",
        "TimeStamp": int(time.time()),
        "Version": "1.5",
        "LangType": "zh-Tw",
        "MerOrderNo": body_data['OrderNo'],
        "ProdDesc": body_data['product'],
        "PeriodAmt": body_data['price'],
        "PeriodType": "M",  # D=固定天期制, W=每週, M=每月, Y=每年
        "PeriodPoint": "15",  # 週期點
        "PeriodStartType": 2,  # 1=立即執行十元授權, 2=立即執行委託金額授權, 3=不檢查信用卡資訊，不授權
        "PeriodTimes": "3",  # 授權期數
        "PayerEmail": "dkgbfdoy@gmail.com",
        "NotifyURL": body_data['NotifyURL']
    }
    # print(post_data)
    query_str = urllib.parse.urlencode(post_data)
    encrypt_data = aes256_cbc_encrypt(query_str, HashKey, HashIV)
    hashs = sha256_hash(encrypt_data, HashKey, HashIV)

    params = {
        "MerchantID": MerchantID,
        "PostData_": encrypt_data,
        "PostSha_": hashs
    }
    # print(params)
    html_form = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        <title>線上付款</title>
    </head>
    <body>
        載入中請稍候.....
        <form style='display:none' id='form1' name='Newebpay' method='post' action='{url}'>
            <input type='hidden' name='MerchantID_' value='{params['MerchantID']}'>
            <input type='hidden' name='PostData_' value='{params['PostData_']}'>
            <input type='hidden' name='PostSha_' value='{params['PostSha_']}'>
            <input type='submit' value='Submit'>
        </form>
        <script type='text/javascript'>document.getElementById('form1').submit();</script>
    </body>
    </html>
    """

    return html_form
