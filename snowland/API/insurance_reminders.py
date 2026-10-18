"""Document reminders use the existing audited order-email delivery, not a second mailer."""
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as InvalidEmail
from rest_framework import serializers
from .manual_notifications import NotificationConflict
from .order_email_notifications import mail_mode


class InsuranceReminderInput(serializers.Serializer):
    field = serializers.ChoiceField(choices=['insurance', 'waiver'])
    recipient_email = serializers.EmailField(max_length=200)
    request_key = serializers.UUIDField()

    def validate(self, attrs):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('只接受資料種類、預覽收件人及寄信識別碼')
        return attrs


def reminder_preview(member, field):
    if field not in {'insurance','waiver'}:
        raise serializers.ValidationError({'field':'請選擇保險資料或聲明書'})
    if member.reservation.status in {'cancelled','deleted'}:
        raise NotificationConflict('課程已取消或刪除，不發送課前資料提醒')
    if getattr(member, f'{field}_completed_at'):
        raise NotificationConflict('這份資料已完成，不需要再提醒')
    group = member.reservation.group
    data = member.insurance_data if isinstance(member.insurance_data, dict) else {}
    contact = group.booking_contact if isinstance(group.booking_contact, dict) else {}
    # Explicitly linked guardian/member takes priority. Never look up an arbitrary
    # account merely because it shares an Email address with an order contact.
    candidates = [user.email for user in (member.guardian, member.user) if user and user.is_active]
    candidates += [data.get('email'), getattr(group.user,'email',''), contact.get('email')]
    recipient = ''
    for value in candidates:
        if not isinstance(value,str) or len(value.strip()) > 200:
            continue
        try:
            validate_email(value.strip())
        except InvalidEmail:
            continue
        recipient = value.strip().lower(); break
    if not recipient:
        raise serializers.ValidationError({'recipient_email':'此學員、家長及訂購人尚無可用信箱，請先確認聯絡資料'})
    label = '保險資料' if field == 'insurance' else '課前聲明書'
    return {'field':field,'recipient_email':recipient,'subject':f'SnowLand {label}待完成提醒',
        'message':f'您好，您的課程尚有{label}未完成。請登入 SnowLand 網站的會員專區，開啟「我的訂單」或「同行課程」的課前資料，完成填寫。若由家長協助，請使用已綁定的家長帳號。謝謝。',
        **mail_mode()}
