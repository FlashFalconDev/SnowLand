from django.db import transaction
from rest_framework import serializers
from rest_framework.response import Response

from Coach.models import PayrollDocumentSettings
from Coach.payroll_documents import ensure_document, save_signature, signature_response


class DocumentSettingsInput(serializers.ModelSerializer):
    class Meta:
        model = PayrollDocumentSettings
        fields = ['title', 'body', 'is_active']
        extra_kwargs = {'body': {'max_length': 30000}}

    def validate(self, values):
        if values.get('is_active', getattr(self.instance, 'is_active', False)) and not values.get('body', getattr(self.instance, 'body', '')).strip():
            raise serializers.ValidationError({'body': '啟用前請填入已確認的文件內容，不會自動產生法律條文'})
        return values


def document_settings(view, request):
    from .admin_views import _require_headquarters
    current = PayrollDocumentSettings.objects.filter(client=request.tenant).first()
    if request.method == 'GET':
        data = DocumentSettingsInput(current).data if current else {'title': '勞務報酬單', 'body': '', 'is_active': False}
        return Response({'code': 200, 'data': data})
    _require_headquarters(request)
    with transaction.atomic():
        # One shared tenant template; do not allow a campus editor to overwrite it.
        request.tenant.__class__.objects.select_for_update().get(pk=request.tenant.pk)
        current = PayrollDocumentSettings.objects.filter(client=request.tenant).first()
        serializer = DocumentSettingsInput(current, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(client=request.tenant)
    return Response({'code': 200, 'msg': '文件內容已儲存，既有報酬單不會改變', 'data': serializer.data})


def generate_document(view, request):
    try:
        statement = ensure_document(view.get_object())
    except ValueError as exc:
        return Response({'code': 409, 'msg': str(exc)}, status=409)
    return Response({'code': 200, 'data': view.get_serializer(statement).data})


class SignatureInput(serializers.Serializer):
    document_digest = serializers.RegexField(r'^[a-f0-9]{64}$')
    signer_name = serializers.CharField(max_length=100)
    accepted = serializers.BooleanField()


def upload_signature(view, request):
    statement = view.get_object()
    serializer = SignatureInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        statement = save_signature(statement, request.user, request.FILES.get('file'),
            serializer.validated_data['document_digest'], serializer.validated_data['signer_name'], serializer.validated_data['accepted'])
    except ValueError as exc:
        return Response({'code': 400, 'msg': str(exc)}, status=400)
    except OSError:
        return Response({'code': 503, 'msg': '簽名檔暫時無法儲存，請稍後再試'}, status=503)
    return Response({'code': 200, 'msg': '簽名已保存，報酬單內容已鎖定', 'data': view.get_serializer(statement).data})


def read_signature(view):
    statement = view.get_object()
    try:
        response = signature_response(statement)
    except OSError:
        response = None
    return response if response is not None else Response({'code': 404, 'msg': '找不到簽名圖片'}, status=404)
