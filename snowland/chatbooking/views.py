import hashlib
import json
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from booking.api_views import TenantResolutionError, resolve_tenant_client

from .ai.orchestrator import AIDisabledError, AITurnBusyError, run_ai_turn
from .ai.provider import AIConfigurationError, AIProviderError
from .flow import apply_updates, missing_fields, next_field
from .models import (
    ChatBookingDraft,
    ChatBookingHandoff,
    ChatBookingMessage,
    ChatBookingSession,
)
from .services import (
    confirm_quoted_session,
    make_quote,
    option_payload,
    payment_snapshot_for_groups,
    public_user,
    submit_bank_transfer,
)


def token_hash(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def session_payload(session, include_messages=False):
    draft = getattr(session, "draft", None)
    payload = {
        "id": str(session.pk),
        "channel": session.channel,
        "status": session.status,
        "current_step": session.current_step,
        "state_version": session.state_version,
        "slot_values": session.slot_values,
        "missing_fields": missing_fields(session.slot_values or {}),
        "expires_at": session.expires_at,
        "quote": None,
        "reservation_group_ids": [],
    }
    if draft:
        payload["quote"] = {
            **(draft.quote or {}),
            "quote_hash": draft.quote_hash,
            "quote_expires_at": draft.quote_expires_at,
            "status": draft.status,
        } if draft.quote else None
        payload["reservation_group_ids"] = draft.reservation_group_ids
    if include_messages:
        payload["messages"] = [
            {
                "id": message.id,
                "direction": message.direction,
                "sender_type": message.sender_type,
                "content": message.content,
                "metadata": message.metadata,
                "created_at": message.created_at,
            }
            for message in session.messages.order_by("-created_at")[:50][::-1]
        ]
    return payload


class ChatSessionCreateThrottle(SimpleRateThrottle):
    scope = "chat_session_create"
    rate = "30/hour"

    def get_cache_key(self, request, view):
        client_code = getattr(view, "kwargs", {}).get("client_code", "")
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{client_code}:{self.get_ident(request)}",
        }


class SessionAccessMixin:
    def get_tenant(self, client_code):
        try:
            return resolve_tenant_client(client_code)
        except TenantResolutionError as exc:
            raise ValueError(str(exc)) from exc

    def get_session(self, request, client_code, session_id, for_update=False):
        tenant = self.get_tenant(client_code)
        queryset = ChatBookingSession.objects.filter(client=tenant)
        if for_update:
            queryset = queryset.select_for_update()
        session = queryset.filter(pk=session_id).first()
        if not session:
            return None, Response({"error": "找不到客服對話"}, status=status.HTTP_404_NOT_FOUND)
        raw_token = request.headers.get("X-Chat-Session-Token", "")
        if not raw_token or not constant_time_compare(session.access_token_hash, token_hash(raw_token)):
            return None, Response({"error": "客服對話憑證無效"}, status=status.HTTP_401_UNAUTHORIZED)
        if session.expires_at <= timezone.now():
            if session.status != ChatBookingSession.STATUS_EXPIRED:
                session.status = ChatBookingSession.STATUS_EXPIRED
                session.save(update_fields=["status", "updated_at"])
            return None, Response({"error": "客服對話已過期"}, status=status.HTTP_410_GONE)
        return session, None


class ChatSessionCollectionAPI(SessionAccessMixin, APIView):
    permission_classes = []
    throttle_classes = [ChatSessionCreateThrottle]

    def post(self, request, client_code):
        try:
            tenant = self.get_tenant(client_code)
            service_type = request.data.get("service_type")
            if service_type not in (None, "", "ski", "photo"):
                return Response({"error": "service_type 必須是 ski 或 photo"}, status=400)
            raw_token = secrets.token_urlsafe(32)
            slot_values = {"service_type": service_type} if service_type else {}
            user = public_user(request)
            session = ChatBookingSession.objects.create(
                client=tenant,
                user=user,
                channel=ChatBookingSession.CHANNEL_API,
                slot_values=slot_values,
                current_step=next_field(slot_values),
                access_token_hash=token_hash(raw_token),
                expires_at=timezone.now() + timedelta(days=7),
            )
            ChatBookingDraft.objects.create(session=session)
            ChatBookingMessage.objects.create(
                session=session,
                direction=ChatBookingMessage.DIRECTION_SYSTEM,
                sender_type=ChatBookingMessage.SENDER_SYSTEM,
                content="客服排課對話已建立",
                metadata={"schema_version": 1},
            )
            return Response(
                {
                    "session": session_payload(session),
                    "session_token": raw_token,
                    "token_note": "只會回傳一次，請勿寫入日誌或網址",
                },
                status=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class ChatSessionDetailAPI(SessionAccessMixin, APIView):
    permission_classes = []

    def get(self, request, client_code, session_id):
        session, error = self.get_session(request, client_code, session_id)
        if error:
            return error
        return Response({"session": session_payload(session, include_messages=True)})


class ChatSessionStateAPI(SessionAccessMixin, APIView):
    permission_classes = []

    @transaction.atomic
    def patch(self, request, client_code, session_id):
        session, error = self.get_session(request, client_code, session_id, for_update=True)
        if error:
            return error
        expected_version = request.data.get("state_version")
        if expected_version is None:
            return Response({"error": "缺少 state_version"}, status=status.HTTP_400_BAD_REQUEST)
        if int(expected_version) != session.state_version:
            return Response(
                {
                    "error": "對話資料已更新，請重新取得最新狀態",
                    "current_state_version": session.state_version,
                },
                status=status.HTTP_409_CONFLICT,
            )
        draft, _ = ChatBookingDraft.objects.get_or_create(session=session)
        if draft.status == ChatBookingDraft.STATUS_COMMITTED:
            return Response(
                {"error": "此對話已建立訂單；如需新課程請建立新的客服對話"},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            next_values = apply_updates(session.slot_values, request.data.get("updates"))
        except (TypeError, ValueError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        session.slot_values = next_values
        session.state_version += 1
        session.current_step = next_field(next_values)
        session.status = (
            ChatBookingSession.STATUS_AWAITING_CONFIRMATION
            if not missing_fields(next_values)
            else ChatBookingSession.STATUS_ACTIVE
        )
        session.save(update_fields=[
            "slot_values", "state_version", "current_step", "status", "updated_at",
        ])
        draft.status = ChatBookingDraft.STATUS_DRAFT
        draft.cart = [
            item
            for item in (draft.cart or [])
            if isinstance(item, dict) and item.get("_chat_saved") is True
        ]
        draft.contact = {}
        draft.quote = {}
        draft.quote_hash = ""
        draft.quote_expires_at = None
        draft.last_error = ""
        draft.save()
        return Response({"session": session_payload(session)})


class ChatSessionOptionsAPI(SessionAccessMixin, APIView):
    permission_classes = []

    def get(self, request, client_code, session_id):
        session, error = self.get_session(request, client_code, session_id)
        if error:
            return error
        field = request.GET.get("field", "")
        try:
            options = option_payload(
                session.client,
                session.slot_values or {},
                field,
                month=request.GET.get("month"),
            )
            return Response({"field": field, "options": options})
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ChatSessionMessagesAPI(SessionAccessMixin, APIView):
    permission_classes = []

    def post(self, request, client_code, session_id):
        session, error = self.get_session(request, client_code, session_id)
        if error:
            return error
        content = str(request.data.get("content") or "").strip()
        if not content:
            return Response({"error": "訊息不可為空"}, status=status.HTTP_400_BAD_REQUEST)
        if len(content) > 4000:
            return Response({"error": "訊息不可超過 4000 字"}, status=status.HTTP_400_BAD_REQUEST)
        metadata = request.data.get("metadata") or {}
        if not isinstance(metadata, dict):
            return Response({"error": "metadata 必須是物件"}, status=status.HTTP_400_BAD_REQUEST)
        if len(json.dumps(metadata, ensure_ascii=False).encode("utf-8")) > 16384:
            return Response({"error": "metadata 不可超過 16 KB"}, status=status.HTTP_400_BAD_REQUEST)
        external_message_id = str(request.data.get("external_message_id") or "").strip()
        external_key = (
            f"{session.client_id}:{session.channel}:{external_message_id}"
            if external_message_id else None
        )
        try:
            message, created = ChatBookingMessage.objects.get_or_create(
                external_message_key=external_key,
                defaults={
                    "session": session,
                    "direction": ChatBookingMessage.DIRECTION_INBOUND,
                    "sender_type": ChatBookingMessage.SENDER_CUSTOMER,
                    "content": content,
                    "metadata": metadata,
                },
            ) if external_key else (
                ChatBookingMessage.objects.create(
                    session=session,
                    direction=ChatBookingMessage.DIRECTION_INBOUND,
                    sender_type=ChatBookingMessage.SENDER_CUSTOMER,
                    content=content,
                    metadata=metadata,
                ),
                True,
            )
        except IntegrityError:
            message = ChatBookingMessage.objects.get(external_message_key=external_key)
            created = False
        if message.session_id != session.id:
            return Response(
                {"error": "external_message_id 已由另一個對話使用"},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            reply = run_ai_turn(session, message)
        except AIDisabledError:
            return Response(
                {
                    "message_id": message.id,
                    "created": created,
                    "ai_status": "disabled_for_human_support",
                    "reply": None,
                    "session": session_payload(session),
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except AITurnBusyError as exc:
            return Response(
                {
                    "message_id": message.id,
                    "created": created,
                    "ai_status": "busy",
                    "error": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except AIConfigurationError:
            return Response(
                {
                    "message_id": message.id,
                    "created": created,
                    "ai_status": "not_configured",
                    "error": "AI 客服尚未設定完成",
                    "code": "openai_not_configured",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except AIProviderError:
            return Response(
                {
                    "message_id": message.id,
                    "created": created,
                    "ai_status": "provider_error",
                    "error": "AI 客服暫時無法回覆，請稍後再試",
                    "code": "openai_provider_error",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        session.refresh_from_db()
        return Response(
            {
                "message_id": message.id,
                "created": created,
                "ai_status": "replayed" if reply.replayed else "completed",
                "reply": {
                    "message_id": reply.message_id,
                    "content": reply.content,
                },
                "session": session_payload(session),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ChatSessionQuoteAPI(SessionAccessMixin, APIView):
    permission_classes = []

    @transaction.atomic
    def post(self, request, client_code, session_id):
        session, error = self.get_session(request, client_code, session_id, for_update=True)
        if error:
            return error
        existing_draft = ChatBookingDraft.objects.filter(session=session).first()
        if existing_draft and existing_draft.status == ChatBookingDraft.STATUS_COMMITTED:
            return Response(
                {"error": "此對話已建立訂單；如需新課程請建立新的客服對話"},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            draft = make_quote(session)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        session.status = ChatBookingSession.STATUS_AWAITING_CONFIRMATION
        session.current_step = "confirmation"
        session.save(update_fields=["status", "current_step", "updated_at"])
        return Response({
            "quote": {
                **draft.quote,
                "quote_hash": draft.quote_hash,
                "quote_expires_at": draft.quote_expires_at,
            },
            "state_version": session.state_version,
        })


class ChatSessionConfirmAPI(SessionAccessMixin, APIView):
    permission_classes = []

    @transaction.atomic
    def post(self, request, client_code, session_id):
        session, error = self.get_session(request, client_code, session_id, for_update=True)
        if error:
            return error
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key or len(idempotency_key) > 128:
            return Response(
                {"error": "請提供 1 至 128 字元的 Idempotency-Key"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.data.get("confirmed") is not True:
            return Response({"error": "confirmed 必須是 true"}, status=status.HTTP_400_BAD_REQUEST)

        result = confirm_quoted_session(
            session,
            public_user(request),
            idempotency_key=idempotency_key,
            expected_state_version=request.data.get("state_version"),
            expected_quote_hash=request.data.get("quote_hash"),
            input_data=dict(request.data),
        )
        if not result.ok:
            return Response({"error": result.error}, status=result.status_code)
        return Response(result.output)


class ChatSessionPaymentAPI(SessionAccessMixin, APIView):
    permission_classes = []

    def get(self, request, client_code, session_id):
        session, error = self.get_session(request, client_code, session_id)
        if error:
            return error
        draft = ChatBookingDraft.objects.filter(session=session).first()
        if not draft or draft.status != ChatBookingDraft.STATUS_COMMITTED:
            return Response({"error": "尚未建立可付款訂單"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            snapshot = payment_snapshot_for_groups(session.client, draft.reservation_group_ids)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        payment_allowed = draft.payment_snapshot.get("payment_allowed") is True
        snapshot["payment_allowed"] = payment_allowed
        if not payment_allowed:
            snapshot["payment_methods"] = []
            snapshot["card_status"] = "unavailable_until_scheduled"
        return Response({"payment": snapshot})

    def post(self, request, client_code, session_id):
        session, error = self.get_session(request, client_code, session_id)
        if error:
            return error
        payment_type = request.data.get("payment_type")
        if payment_type != "bank_transfer":
            return Response(
                {
                    "error": "信用卡需要安全付款閘道 adapter；目前僅開放銀行匯款資料提交",
                    "code": "card_gateway_adapter_required",
                },
                status=status.HTTP_409_CONFLICT,
            )
        try:
            snapshot = submit_bank_transfer(session, str(request.data.get("sender_account") or ""))
        except (ChatBookingDraft.DoesNotExist, ValueError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "匯款帳戶後五碼已提交，等待確認", "payment": snapshot})


class ChatSessionHandoffAPI(SessionAccessMixin, APIView):
    permission_classes = []

    @transaction.atomic
    def post(self, request, client_code, session_id):
        session, error = self.get_session(request, client_code, session_id, for_update=True)
        if error:
            return error
        reason = str(request.data.get("reason") or "").strip()[:2000]
        handoff, _ = ChatBookingHandoff.objects.update_or_create(
            session=session,
            defaults={"status": ChatBookingHandoff.STATUS_REQUESTED, "reason": reason},
        )
        session.ai_enabled = False
        session.status = ChatBookingSession.STATUS_ESCALATED
        session.current_step = "human_support"
        session.save(update_fields=["ai_enabled", "status", "current_step", "updated_at"])
        return Response({
            "handoff": {
                "status": handoff.status,
                "reason": handoff.reason,
                "requested_at": handoff.requested_at,
            },
        })
