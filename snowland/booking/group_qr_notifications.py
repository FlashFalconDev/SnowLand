"""Embed group QR bytes in authorized mail, never publish a private file URL."""
from email.mime.image import MIMEImage
from pathlib import PurePosixPath
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.html import escape
from .media_files import validate_course_upload


def notification_qr_name(delivery):
    return delivery.group.line_group_qr.name if delivery.template.event == 'line_group' else ''


def body_with_group_qr(body, delivery):
    if not notification_qr_name(delivery):
        return body
    instruction = '上課群組 QR 碼請登入會員專區的「我的訂單」查看。'
    if delivery.template.channel == 'email':
        instruction = '上課群組 QR 碼請查看信中附圖，或登入會員專區的「我的訂單」查看。'
    return f'{body}\n\n{instruction}'


def send_inline_group_qr(subject, body, delivery):
    """None means no QR: caller keeps its existing plain-text mail transport."""
    name = notification_qr_name(delivery)
    if not name:
        return None
    subtype = {'.png': 'png', '.jpg': 'jpeg', '.jpeg': 'jpeg', '.webp': 'webp'}.get(PurePosixPath(name).suffix.lower())
    if not subtype:
        raise ValueError('上課群組 QR 碼圖片格式不正確，請重新上傳')
    try:
        with delivery.group.line_group_qr.open('rb') as stream:
            image_bytes = stream.read(5 * 1024 * 1024 + 1)
    except OSError:
        raise ValueError('上課群組 QR 碼圖片無法讀取，請重新上傳') from None
    if not image_bytes or len(image_bytes) > 5 * 1024 * 1024:
        raise ValueError('上課群組 QR 碼圖片遺失或超過 5 MB，請重新上傳')
    kind, extension = validate_course_upload(SimpleUploadedFile('qr', image_bytes))
    if kind != 'photo' or {'.png': 'png', '.jpg': 'jpeg', '.webp': 'webp'}.get(extension) != subtype:
        raise ValueError('上課群組 QR 碼圖片已損壞，請重新上傳')
    cid = f'class-group-qr-{delivery.pk}@snowland'
    message = EmailMultiAlternatives(subject or 'SnowLand 通知', body, settings.DEFAULT_FROM_EMAIL, [delivery.recipient])
    message.mixed_subtype = 'related'
    html = '<p>' + str(escape(body)).replace('\n', '<br>') + '</p>'
    if delivery.group.line_group_url:
        from .operations import validate_class_group_url
        invite_url = str(escape(validate_class_group_url(delivery.group.line_group_url)))
        if invite_url:
            html = html.replace(invite_url, f'<a href="{invite_url}">{invite_url}</a>')
    html += f'<p><img src="cid:{cid}" alt="上課聯絡群組 QR 碼" width="240" style="max-width:100%;height:auto"></p>'
    message.attach_alternative(html, 'text/html')
    image = MIMEImage(image_bytes, _subtype=subtype)
    image.add_header('Content-ID', f'<{cid}>')
    image.add_header('Content-Disposition', 'inline', filename='class-group-qr'+PurePosixPath(name).suffix.lower())
    message.attach(image)
    return message.send()
