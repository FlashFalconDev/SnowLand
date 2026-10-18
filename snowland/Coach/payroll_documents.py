import hashlib
import json
import uuid
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone
from PIL import Image

from booking.media_files import validate_course_upload, private_file_response
from .models import PayrollDocumentSettings, PayrollStatement


def document_digest(snapshot):
    if not snapshot:
        return ''
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def build_document_snapshot(statement):
    settings = PayrollDocumentSettings.objects.filter(client_id=statement.coach.client_id, is_active=True).first()
    if not settings or not settings.body.strip():
        return {}
    return {'version': 1, 'title': settings.title, 'body': settings.body, 'template_updated_at': settings.updated_at.isoformat(),
        'statement_id': statement.pk, 'coach_name': statement.coach.name, 'campus_name': statement.campus.name,
        'period_start': statement.period_start.isoformat(), 'period_end': statement.period_end.isoformat(),
        'currency': 'TWD', 'total_amount': statement.total_amount, 'generated_at': timezone.now().isoformat(),
        'lines': list(statement.lines.order_by('pk').values('line_type', 'description', 'quantity', 'unit_amount', 'total_amount'))}


@transaction.atomic
def ensure_document(statement, required=True):
    statement = PayrollStatement.objects.select_for_update().get(pk=statement.pk)
    if statement.status not in {'confirmed', 'paid'}:
        raise ValueError('確認薪資後才能產生報酬單')
    if statement.document_snapshot:
        return statement
    snapshot = build_document_snapshot(statement)
    if not snapshot:
        if not required:
            return statement
        raise ValueError('請先由總部設定並啟用報酬單正式內容')
    # Decimal values are serialized as strings to preserve exact monetary inputs.
    snapshot['lines'] = [{**line, 'quantity': str(line['quantity']), 'unit_amount': str(line['unit_amount'])} for line in snapshot['lines']]
    statement.document_snapshot = snapshot
    statement.save(update_fields=['document_snapshot', 'updated_at'])
    return statement


def save_signature(statement, user, upload, digest, signer_name, accepted):
    signer_name = str(signer_name or '').strip()
    if accepted is not True or not signer_name or len(signer_name) > 100:
        raise ValueError('請填寫簽署姓名並確認本人已核對報酬單')
    if not upload or not upload.size or upload.size > 5*1024*1024:
        raise ValueError('請選擇5 MB以內的簽名圖片')
    kind, extension = validate_course_upload(upload)
    if kind != 'photo':
        raise ValueError('簽名僅接受PNG、JPEG或WebP圖片')
    image = Image.open(upload)
    if max(image.size) > 4096:
        upload.seek(0)
        raise ValueError('簽名圖片長寬不可超過4096像素')
    upload.seek(0)
    sha = hashlib.sha256(upload.read()).hexdigest(); upload.seek(0)
    new_name = None
    storage = statement.signature_file.storage
    try:
        with transaction.atomic():
            statement = PayrollStatement.objects.select_for_update().get(pk=statement.pk)
            if statement.coach.user_id != user.pk or statement.status not in {'confirmed', 'paid'}:
                raise ValueError('只能簽署自己已確認的報酬單')
            if not statement.document_snapshot or not digest or digest != document_digest(statement.document_snapshot):
                raise ValueError('報酬單版本已變更，請重新載入核對後再簽署')
            if statement.signed_at:
                if statement.signature_sha256 == sha and statement.signer_name == signer_name:
                    return statement
                raise ValueError('此報酬單已簽署，不能覆蓋簽名；如需更正請聯絡管理員')
            statement.signature_file.save(f'{statement.coach.client_id}/{statement.pk}/{uuid.uuid4().hex}{extension}', upload, save=False)
            new_name = statement.signature_file.name
            statement.signature_sha256 = sha
            statement.signer_name = signer_name
            statement.signed_at = timezone.now()
            statement.save(update_fields=['signature_file', 'signature_sha256', 'signer_name', 'signed_at', 'updated_at'])
            return statement
    except Exception:
        if new_name:
            storage.delete(new_name)
        raise


def signature_response(statement):
    if not statement.signed_at or not statement.signature_file:
        return None
    return private_file_response(SimpleNamespace(file=statement.signature_file))
