"""Durable order-change receipts. Uses existing inbox records and audited order mail delivery."""
import uuid
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from .models import NotificationDelivery, NotificationTemplate, OrderAmendment
from .notification_recipients import channel_recipient


def _key(row,event=None,channel='email'):
    identity=f'event:{event.pk}' if event else f'amendment:{row.pk}'
    return uuid.uuid5(uuid.NAMESPACE_URL,f'snowland-amendment-notice:{identity}:{channel}')


def _order_path(group):
    return f'/membership/orders/{group.pk}'


def _order_url(group):
    parts=urlsplit(settings.SNOWLAND_PUBLIC_PAYMENT_URL or '')
    local=parts.scheme=='http' and parts.hostname in {'127.0.0.1','localhost','::1'}
    if not (parts.scheme=='https' or local) or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path.rstrip('/')!='/snowland/payment':return ''
    return urlunsplit((parts.scheme,parts.netloc,'/snowland'+_order_path(group),'',''))


def _content(row,event=None):
    amount=f'NT$ {abs(row.balance_amount):,}'
    if event:
        title,text={
            'report_topup':('補款資料已收到',f'已收到您回報的補款資料，金額{amount}。目前等待 SnowLand 核對，請勿重複匯款。'),
            'refund_account':('退款帳戶資料已收到',f'已收到本次退還差額{amount}的帳戶資料，目前等待 SnowLand 處理，尚不代表退款已入帳。'),
            'confirm_topup':('補款核對完成',f'SnowLand 已核對本次補款{amount}並記錄結清，不會重複收取原訂單款項。'),
            'reject_topup':('補款回報請重新核對',f'本次補款{amount}尚未核對通過。原因：{event.payload.get("note","")}\n請登入後更正資料，請勿未確認就再次匯款。'),
            'confirm_refund':('差額退款已記錄完成',f'SnowLand 已記錄本次差額{amount}於系統外完成退款。實際入帳時間請以銀行或金流紀錄為準。'),
        }[event.action]
    else:
        title='訂單課程已修改'
        balance=('請至訂單詳情查看收款帳戶並回報補款。' if row.balance_amount>0 else '請至訂單詳情填寫退款銀行、帳號及戶名；尚未實際退款。')
        if row.status=='included_in_order':balance='尚未付款的訂單，請依新版總額付款，這不是另外再收一次原單金額。'
        elif not row.balance_amount:balance='目前沒有待收退差額。'
        text=f'原訂單金額：NT$ {row.previous_total:,}\n新訂單金額：NT$ {row.new_total:,}\n本次價差：NT$ {row.difference_amount:+,}\n待收退差額：{amount}\n{balance}'
        for reservation in row.revision.snapshot.get('reservations',[]):
            if reservation.get('status') in {'cancelled','deleted'}:continue
            for booking in reservation.get('bookings',[]):
                text+=f'\n{booking["date"]} {booking["start_time"]}–{booking["end_time"]} · {reservation.get("resort_name","")} · {booking.get("course_name","")}'
        if any(change.get('created_ids') for change in row.participant_changes.values()):text+='\n新增學員欄位尚待填寫，請至會員區補齊課前資料；不會代簽聲明書。'
        if row.revision.member_document_revisions.exists():
            text+='\n本次改期／換課的舊簽署與投保紀錄已留底。已簽學員請登入自己的會員區重新簽署；已投保者由行政重新核對，不會直接沿用原投保狀態或保費。'
    subject=f'SnowLand {title}｜第 {row.revision.version} 版'
    body=f'訂單：{row.group.order_number}\n第 {row.revision.version} 版\n{text}\n\n請使用訂購會員帳號登入「我的訂單」，查看最新課程與差額狀態。'
    url=_order_url(row.group)
    if url:body+=f'\n{url}'
    return subject,body


def prepare_amendment_notice(row,actor,event=None):
    # Called within the business transaction holding the client/order lock.
    owner=row.group.user
    if not owner or not owner.is_active:return
    from API.order_email_notifications import prepare_email, mail_mode
    subject,body=_content(row,event)
    now=timezone.now()
    payload={'amendment_notice':True,'amendment_id':row.pk,'amendment_event_id':event.pk if event else None,
        'expected_owner_id':owner.pk,'notice_updated_at':row.updated_at.isoformat(),
        'in_app_subject':subject,'in_app_body':body,'in_app_group_url':'','in_app_action_path':_order_path(row.group),**mail_mode()}
    template,_=NotificationTemplate.objects.get_or_create(manual_key=_key(row,event,'in_app'),defaults={
        'client':row.group.client,'campus':row.group.campus,'event':'manual','channel':'in_app','name':subject[:100],
        'subject':subject,'body':body,'is_active':False})
    NotificationDelivery.objects.get_or_create(template=template,group=row.group,recipient=str(owner.pk),defaults={
        'status':'sent','scheduled_at':now,'sent_at':now,'payload':payload})
    recipient=channel_recipient('email',owner.email)
    if recipient:
        delivery_id=prepare_email(SimpleNamespace(tenant=row.group.client,user=actor),row.group,{
            'request_key':_key(row,event),'recipient_email':recipient,'subject':subject,'message':body})
        delivery=NotificationDelivery.objects.get(pk=delivery_id)
        # Inbox was created independently; the publisher must not create a second mirror.
        delivery.payload={**delivery.payload,**payload,'intended_account_ids':[]}
        delivery.save(update_fields=['payload'])


def amendment_delivery_is_current(delivery):
    group=delivery.group
    owner=group.user if group else None
    payload=delivery.payload
    if not owner or not owner.is_active or owner.pk!=payload.get('expected_owner_id'):return False
    if delivery.template.channel=='email' and channel_recipient('email',owner.email)!=delivery.recipient:return False
    if group.cancellation_requests.filter(status__in=['requested','approved','refunded']).exists():return False
    row=OrderAmendment.objects.filter(pk=payload.get('amendment_id'),group=group).first()
    return bool(row and row.status!='superseded' and row.updated_at.isoformat()==payload.get('notice_updated_at'))


def notice_receipt(row,event=None):
    from API.order_email_notifications import mail_mode
    site=NotificationDelivery.objects.filter(template__manual_key=_key(row,event,'in_app'),group=row.group).first()
    email=NotificationDelivery.objects.filter(template__manual_key=_key(row,event),group=row.group).first()
    status=email.status if email else 'not_configured'
    if email and status=='sending' and not email.payload.get('email_claimed'):status='queued'
    return {'in_app':site.status if site else 'not_available','email':status,**mail_mode()}


def deliver_amendment_notice(row,event=None):
    from API.order_email_notifications import deliver_order_email
    delivery=NotificationDelivery.objects.filter(template__manual_key=_key(row,event),group=row.group).first()
    if delivery:deliver_order_email(delivery.pk)
    return notice_receipt(row,event)


def dispatch_pending_amendment_notices():
    from API.order_email_notifications import deliver_order_email
    # Missing JSON keys evaluate to SQL NULL, not False (SQLite/MySQL alike).
    ids=NotificationDelivery.objects.filter(status='sending',payload__amendment_notice=True).filter(
        Q(payload__email_claimed=False)|Q(payload__email_claimed__isnull=True),
    ).values_list('pk',flat=True)[:100]
    sent=failed=0
    for delivery_id in list(ids):
        code,_=deliver_order_email(delivery_id)
        sent+=int(code==200);failed+=int(code==502)
    return sent,failed
