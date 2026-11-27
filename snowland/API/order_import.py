"""Headquarters-only template, preview and commit endpoints."""

from pathlib import PurePosixPath

from django.http import FileResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from booking.models import OrderImportBatch
from booking.order_import.parser import FileError, MAX_BYTES
from booking.order_import.service import CommitError, commit_batch, preview_batch
from booking.order_import.template import TEMPLATE_PATH, workbook_for_tenant
from Client.tenant_settings import order_import_enabled

from .admin_permissions import user_has_admin_permission
from .admin_views import IsTenantManager, _is_headquarters


def batch_response(batch, *, committed=False):
    data = {
        'batch_id': batch.pk, 'file_sha256': batch.file_sha256, 'status': batch.status,
        'summary': batch.summary, 'row_results': batch.row_results, 'order_results': batch.order_results,
    }
    if committed:
        data['commit_results'] = sorted(batch.commit_results.values(), key=lambda result: result['row_number'])
    return Response({'code': 200, 'data': data})


class OrderImportAdminViewSet(ViewSet):
    permission_classes = [IsTenantManager]
    permission_key = 'order_edit'

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not (_is_headquarters(request) and user_has_admin_permission(request.user, 'order_edit', request.tenant)):
            raise PermissionDenied('只有具修改與排課權限的總部管理員可以匯入訂單')
        if not order_import_enabled(request.tenant):
            raise PermissionDenied('此學校已停用訂單匯入')
        if request.method == 'POST':
            SessionAuthentication().enforce_csrf(request)

    @action(detail=False, methods=['get'])
    def template(self, request, client_code=None):
        return FileResponse(
            workbook_for_tenant(request.tenant), as_attachment=True, filename=TEMPLATE_PATH.name,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser])
    def preview(self, request, client_code=None):
        files = request.FILES.getlist('file')
        if len(files) != 1:
            raise ValidationError({'detail': '請選擇一份 .xlsx 或 .csv 檔案'})
        uploaded = files[0]
        if uploaded.size > MAX_BYTES:
            return Response({'detail': '檔案不可超過 5 MB', 'code': 'file_too_large'}, status=413)
        filename = PurePosixPath(uploaded.name.replace('\\', '/')).name
        try:
            batch = preview_batch(request.tenant, request.user, filename, uploaded.read(MAX_BYTES + 1))
        except FileError as exc:
            return Response({'detail': str(exc), 'code': exc.code, 'columns': exc.columns}, status=400)
        return batch_response(batch)

    @action(detail=False, methods=['post'], parser_classes=[JSONParser])
    def commit(self, request, client_code=None):
        data = request.data
        if not isinstance(data, dict) or data.get('confirm') is not True:
            raise ValidationError({'detail': '請先確認已核對預覽'})
        batch_id = data.get('batch_id')
        if type(batch_id) is not int or not 0 < batch_id < 2**63:
            raise ValidationError({'detail': '無效的批次編號'})
        allow = data.get('allow_overbook', False)
        reason = data.get('overbook_reason', '')
        if type(allow) is not bool or not isinstance(reason, str):
            raise ValidationError({'detail': '超賣設定或原因格式錯誤'})
        reason = reason.strip()
        if allow and (not reason or len(reason) > 1000 or '\x00' in reason):
            raise ValidationError({'detail': '允許超賣時，請填寫 1 至 1000 字的原因'})
        try:
            batch = commit_batch(request.tenant, request.user, batch_id, allow, reason if allow else '')
        except OrderImportBatch.DoesNotExist:
            raise NotFound('找不到此學校的匯入批次')
        except CommitError as exc:
            return Response({'detail': str(exc)}, status=409)
        return batch_response(batch, committed=True)
