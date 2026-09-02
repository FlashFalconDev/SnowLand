import uuid

from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from API.admin_views import IsTenantManager

from .flow import next_field
from .line import LineAPIError, LineConfigurationError, LineMessagingClient
from .models import (
    ChatBookingDraft,
    ChatBookingHandoff,
    ChatBookingMessage,
    ChatBookingSession,
)


def _display_name(user):
    if not user:
        return None
    full_name = user.get_full_name().strip()
    return full_name or user.email or user.username


def _handoff_for(session):
    try:
        return session.handoff
    except ChatBookingHandoff.DoesNotExist:
        return None


def _handoff_payload(handoff):
    if not handoff:
        return None
    return {
        "status": handoff.status,
        "reason": handoff.reason,
        "assigned_to": handoff.assigned_to_id,
        "assigned_to_name": _display_name(handoff.assigned_to),
        "requested_at": handoff.requested_at,
        "updated_at": handoff.updated_at,
        "resolved_at": handoff.resolved_at,
    }


def _message_payload(message):
    return {
        "id": message.id,
        "direction": message.direction,
        "sender_type": message.sender_type,
        "content": message.content,
        "metadata": message.metadata or {},
        "created_at": message.created_at,
    }


def _session_payload(session, *, include_messages=False):
    draft = getattr(session, "draft", None)
    handoff = _handoff_for(session)
    values = session.slot_values or {}
    contact = draft.contact if draft and isinstance(draft.contact, dict) else {}
    contact_name = values.get("contact_name") or contact.get("name") or ""
    contact_phone = values.get("contact_phone") or contact.get("phone") or ""
    payload = {
        "id": session.id,
        "channel": session.channel,
        "external_user_id": session.external_user_id,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "status": session.status,
        "current_step": session.current_step,
        "ai_enabled": session.ai_enabled,
        "updated_at": session.updated_at,
        "last_message": getattr(session, "last_message_content", "") or "",
        "last_message_at": getattr(session, "last_message_at", None),
        "last_sender_type": getattr(session, "last_sender_type", "") or "",
        "handoff": _handoff_payload(handoff),
        "cart_item_count": len(draft.cart or []) if draft else 0,
        "reservation_group_ids": draft.reservation_group_ids if draft else [],
    }
    if include_messages:
        payload["messages"] = [
            _message_payload(message)
            for message in session.messages.order_by("created_at", "id")[:500]
        ]
    return payload


def _resume_step(session, draft):
    if draft and draft.status == ChatBookingDraft.STATUS_COMMITTED:
        return (
            ChatBookingSession.STATUS_CONFIRMED,
            "payment"
            if (draft.payment_snapshot or {}).get("payment_allowed") is True
            else "scheduling_support",
        )
    if (
        draft
        and draft.status == ChatBookingDraft.STATUS_QUOTED
        and draft.quote_expires_at
        and draft.quote_expires_at > timezone.now()
    ):
        return ChatBookingSession.STATUS_AWAITING_CONFIRMATION, "confirmation"
    return ChatBookingSession.STATUS_ACTIVE, next_field(session.slot_values or {})


def _agent_retry_key(session, client_message_id):
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"snowland:line:agent:{session.client_id}:{session.pk}:{client_message_id}",
        )
    )


class ChatSupportViewSet(ViewSet):
    """SnowLand 後台的 LINE AI／真人客服接手窗口。"""

    permission_classes = [IsTenantManager]
    permission_key = "chat_support"
    lookup_value_regex = "[0-9a-fA-F-]{36}"

    def _session(self, request, pk):
        return get_object_or_404(
            ChatBookingSession.objects.select_related(
                "draft",
                "handoff",
                "handoff__assigned_to",
            ),
            pk=pk,
            client=request.tenant,
            channel=ChatBookingSession.CHANNEL_LINE,
        )

    def list(self, request, *args, **kwargs):
        latest_messages = ChatBookingMessage.objects.filter(
            session=OuterRef("pk"),
        ).order_by("-created_at", "-id")
        queryset = (
            ChatBookingSession.objects.filter(
                client=request.tenant,
                channel=ChatBookingSession.CHANNEL_LINE,
            )
            .select_related("draft", "handoff", "handoff__assigned_to")
            .annotate(
                last_message_content=Subquery(latest_messages.values("content")[:1]),
                last_message_at=Subquery(latest_messages.values("created_at")[:1]),
                last_sender_type=Subquery(latest_messages.values("sender_type")[:1]),
            )
        )

        queue = str(request.query_params.get("queue") or "all").strip()
        if queue == "waiting":
            queryset = queryset.filter(handoff__status=ChatBookingHandoff.STATUS_REQUESTED)
        elif queue == "assigned":
            queryset = queryset.filter(handoff__status=ChatBookingHandoff.STATUS_ASSIGNED)
        elif queue == "mine":
            queryset = queryset.filter(
                handoff__status=ChatBookingHandoff.STATUS_ASSIGNED,
                handoff__assigned_to=request.user,
            )
        elif queue == "ai":
            queryset = queryset.filter(ai_enabled=True)
        elif queue == "resolved":
            queryset = queryset.filter(handoff__status=ChatBookingHandoff.STATUS_RESOLVED)

        search = str(request.query_params.get("search") or "").strip()[:100]
        if search:
            queryset = queryset.filter(
                Q(external_user_id__icontains=search)
                | Q(messages__content__icontains=search)
                | Q(slot_values__contact_name__icontains=search)
                | Q(slot_values__contact_phone__icontains=search)
            ).distinct()

        try:
            page = max(1, int(request.query_params.get("page") or 1))
            page_size = min(100, max(1, int(request.query_params.get("page_size") or 50)))
        except (TypeError, ValueError):
            return Response(
                {"code": 400, "msg": "分頁參數格式錯誤"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        total = queryset.count()
        start = (page - 1) * page_size
        sessions = queryset.order_by("-updated_at", "-created_at")[start:start + page_size]
        return Response({
            "code": 200,
            "msg": "success",
            "data": {
                "list": [_session_payload(session) for session in sessions],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        })

    def retrieve(self, request, pk=None, *args, **kwargs):
        session = self._session(request, pk)
        return Response({
            "code": 200,
            "msg": "success",
            "data": _session_payload(session, include_messages=True),
        })

    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None, *args, **kwargs):
        with transaction.atomic():
            session = get_object_or_404(
                ChatBookingSession.objects.select_for_update(),
                pk=pk,
                client=request.tenant,
                channel=ChatBookingSession.CHANNEL_LINE,
            )
            handoff, _ = ChatBookingHandoff.objects.select_for_update().get_or_create(
                session=session,
                defaults={"reason": "後台客服主動接手"},
            )
            if (
                handoff.status == ChatBookingHandoff.STATUS_ASSIGNED
                and handoff.assigned_to_id
                and handoff.assigned_to_id != request.user.id
                and not request.user.is_superuser
            ):
                return Response(
                    {
                        "code": 409,
                        "msg": f"此對話已由 {_display_name(handoff.assigned_to)} 接手",
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            handoff.status = ChatBookingHandoff.STATUS_ASSIGNED
            handoff.assigned_to = request.user
            handoff.resolved_at = None
            handoff.save(
                update_fields=[
                    "status",
                    "assigned_to",
                    "resolved_at",
                    "updated_at",
                ]
            )
            session.ai_enabled = False
            session.status = ChatBookingSession.STATUS_ESCALATED
            session.current_step = "human_support"
            session.save(
                update_fields=["ai_enabled", "status", "current_step", "updated_at"]
            )

        session = self._session(request, pk)
        return Response({
            "code": 200,
            "msg": "已接手對話，AI 已暫停",
            "data": _session_payload(session, include_messages=True),
        })

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None, *args, **kwargs):
        content = str(request.data.get("content") or "").strip()
        client_message_id = str(request.data.get("client_message_id") or "").strip()
        if not content:
            return Response(
                {"code": 400, "msg": "請輸入回覆內容"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(content) > 5000:
            return Response(
                {"code": 400, "msg": "單次人工回覆不可超過 5000 字"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            client_message_id = str(uuid.UUID(client_message_id))
        except (ValueError, TypeError, AttributeError):
            return Response(
                {"code": 400, "msg": "client_message_id 格式錯誤"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = self._session(request, pk)
        external_key = (
            f"{session.client_id}:line-agent:{session.pk}:{client_message_id}"
        )
        existing = ChatBookingMessage.objects.filter(
            session=session,
            external_message_key=external_key,
            sender_type=ChatBookingMessage.SENDER_AGENT,
        ).first()
        if existing:
            return Response({
                "code": 200,
                "msg": "此回覆已傳送",
                "data": {"message": _message_payload(existing), "replayed": True},
            })

        claim_response = self.claim(request, pk=pk)
        if claim_response.status_code >= 400:
            return claim_response
        session = self._session(request, pk)
        if not session.external_user_id:
            return Response(
                {"code": 409, "msg": "此對話沒有可用的 LINE user ID"},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            LineMessagingClient().push(
                session.external_user_id,
                content,
                retry_key=_agent_retry_key(session, client_message_id),
            )
        except LineConfigurationError as exc:
            return Response(
                {"code": 503, "msg": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except LineAPIError as exc:
            return Response(
                {"code": 502, "msg": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        message, _ = ChatBookingMessage.objects.get_or_create(
            external_message_key=external_key,
            defaults={
                "session": session,
                "direction": ChatBookingMessage.DIRECTION_OUTBOUND,
                "sender_type": ChatBookingMessage.SENDER_AGENT,
                "content": content,
                "metadata": {
                    "line_message_type": "agent_text",
                    "sent_by_user_id": request.user.id,
                    "sent_by_name": _display_name(request.user),
                    "client_message_id": client_message_id,
                    "delivery_status": "sent",
                },
            },
        )
        ChatBookingSession.objects.filter(pk=session.pk).update(updated_at=timezone.now())
        return Response({
            "code": 200,
            "msg": "已由官方 LINE 傳送",
            "data": {"message": _message_payload(message), "replayed": False},
        })

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None, *args, **kwargs):
        resume_ai = request.data.get("resume_ai", False)
        if not isinstance(resume_ai, bool):
            return Response(
                {"code": 400, "msg": "resume_ai 必須是布林值"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            session = get_object_or_404(
                ChatBookingSession.objects.select_for_update(),
                pk=pk,
                client=request.tenant,
                channel=ChatBookingSession.CHANNEL_LINE,
            )
            handoff = ChatBookingHandoff.objects.select_for_update().filter(
                session=session,
            ).first()
            if not handoff:
                return Response(
                    {"code": 409, "msg": "此對話目前沒有真人接手案件"},
                    status=status.HTTP_409_CONFLICT,
                )
            handoff.status = ChatBookingHandoff.STATUS_RESOLVED
            handoff.assigned_to = handoff.assigned_to or request.user
            handoff.resolved_at = timezone.now()
            handoff.save(
                update_fields=[
                    "status",
                    "assigned_to",
                    "resolved_at",
                    "updated_at",
                ]
            )

            if resume_ai:
                draft = ChatBookingDraft.objects.select_for_update().filter(
                    session=session,
                ).first()
                session.status, session.current_step = _resume_step(session, draft)
                session.ai_enabled = True
            else:
                session.status = ChatBookingSession.STATUS_ESCALATED
                session.current_step = "human_support"
                session.ai_enabled = False
            session.save(
                update_fields=["status", "current_step", "ai_enabled", "updated_at"]
            )
            ChatBookingMessage.objects.create(
                session=session,
                direction=ChatBookingMessage.DIRECTION_SYSTEM,
                sender_type=ChatBookingMessage.SENDER_SYSTEM,
                content=(
                    "真人客服已結案，AI 客服已恢復"
                    if resume_ai
                    else "真人客服已結案，對話維持人工模式"
                ),
                metadata={
                    "resolved_by_user_id": request.user.id,
                    "resolved_by_name": _display_name(request.user),
                    "resume_ai": resume_ai,
                },
            )

        session = self._session(request, pk)
        return Response({
            "code": 200,
            "msg": "已結案並恢復 AI" if resume_ai else "已結案並維持人工模式",
            "data": _session_payload(session, include_messages=True),
        })
