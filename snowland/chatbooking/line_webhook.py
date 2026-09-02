import hashlib
import json
import logging
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from Client.models import Client
from booking.api_views import TenantResolutionError, resolve_tenant_client

from .ai.orchestrator import AIReply, AIDisabledError, AITurnBusyError, run_ai_turn
from .ai.provider import AIConfigurationError, AIProviderError
from .intents import (
    is_additional_booking_request,
    is_explicit_fresh_order_request,
    is_existing_order_request,
    is_new_booking_request_after_order,
)
from .line import (
    LineAPIError,
    LineConfigurationError,
    LineMessagingClient,
    verify_line_signature,
)
from .line_flex import build_booking_cart_flex, build_booking_confirmation_flex
from .models import (
    ChatBookingDraft,
    ChatBookingEvent,
    ChatBookingMessage,
    ChatBookingSession,
)


logger = logging.getLogger(__name__)

REUSABLE_SESSION_STATUSES = (
    ChatBookingSession.STATUS_ACTIVE,
    ChatBookingSession.STATUS_AWAITING_CONFIRMATION,
    ChatBookingSession.STATUS_CONFIRMED,
    ChatBookingSession.STATUS_ESCALATED,
)


def _event_identity(event):
    hashable_event = {
        key: value
        for key, value in event.items()
        if key not in {"replyToken", "deliveryContext"}
    }
    canonical = json.dumps(
        hashable_event,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload_hash = hashlib.sha256(canonical).hexdigest()
    supplied_id = str(event.get("webhookEventId") or "").strip()
    external_event_id = supplied_id[:255] if supplied_id else f"sha256:{payload_hash}"
    return external_event_id, payload_hash


def _push_retry_key(client, event_record):
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            (
                f"snowland:line:{client.pk}:"
                f"{event_record.external_event_id}:final-response"
            ),
        )
    )


@transaction.atomic
def _acquire_event(client, event):
    external_event_id, payload_hash = _event_identity(event)
    record, created = ChatBookingEvent.objects.get_or_create(
        client=client,
        channel=ChatBookingSession.CHANNEL_LINE,
        external_event_id=external_event_id,
        defaults={
            "payload_hash": payload_hash,
            "status": ChatBookingEvent.STATUS_PROCESSING,
        },
    )
    record = ChatBookingEvent.objects.select_for_update().get(pk=record.pk)
    if created:
        return record, True
    if record.status == ChatBookingEvent.STATUS_PROCESSED:
        return record, False
    if (
        record.status == ChatBookingEvent.STATUS_PROCESSING
        and record.updated_at > timezone.now() - timedelta(minutes=10)
    ):
        return record, False
    record.payload_hash = payload_hash
    record.status = ChatBookingEvent.STATUS_PROCESSING
    record.error = ""
    record.processed_at = None
    record.save(
        update_fields=[
            "payload_hash",
            "status",
            "error",
            "processed_at",
            "updated_at",
        ]
    )
    return record, True


def _create_line_session(client, external_user_id, expires_at):
    session = ChatBookingSession.objects.create(
        client=client,
        channel=ChatBookingSession.CHANNEL_LINE,
        external_user_id=external_user_id,
        access_token_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
        expires_at=expires_at,
    )
    ChatBookingDraft.objects.create(session=session)
    ChatBookingMessage.objects.create(
        session=session,
        direction=ChatBookingMessage.DIRECTION_SYSTEM,
        sender_type=ChatBookingMessage.SENDER_SYSTEM,
        content="LINE AI 客服排課對話已建立",
        metadata={"schema_version": 1, "channel": "line"},
    )
    return session


@transaction.atomic
def _line_session(client, external_user_id, event_record, message_text=""):
    now = timezone.now()
    expires_at = now + timedelta(days=settings.LINE_SESSION_TTL_DAYS)
    Client.objects.select_for_update().get(pk=client.pk)

    # A redelivered event must remain bound to its original session.
    if event_record.session_id:
        existing = ChatBookingSession.objects.select_for_update().filter(
            pk=event_record.session_id,
            client=client,
            channel=ChatBookingSession.CHANNEL_LINE,
            external_user_id=external_user_id,
        ).first()
        if existing:
            return existing

    candidates = ChatBookingSession.objects.select_for_update().filter(
        client=client,
        channel=ChatBookingSession.CHANNEL_LINE,
        external_user_id=external_user_id,
        status__in=REUSABLE_SESSION_STATUSES,
    ).order_by("-updated_at")
    valid_candidates = []
    for candidate in candidates:
        if candidate.expires_at <= now:
            candidate.status = ChatBookingSession.STATUS_EXPIRED
            candidate.save(update_fields=["status", "updated_at"])
            continue
        draft = ChatBookingDraft.objects.filter(session=candidate).first()
        valid_candidates.append((candidate, draft))

    if not valid_candidates:
        return _create_line_session(client, external_user_id, expires_at)

    def use(candidate):
        candidate.expires_at = expires_at
        candidate.save(update_fields=["expires_at", "updated_at"])
        return candidate

    committed = next(
        (
            candidate
            for candidate, draft in valid_candidates
            if draft and draft.status == ChatBookingDraft.STATUS_COMMITTED
        ),
        None,
    )
    if committed and is_existing_order_request(message_text):
        return use(committed)

    working_pair = next(
        (
            (candidate, draft)
            for candidate, draft in valid_candidates
            if candidate.ai_enabled
            and candidate.status in {
                ChatBookingSession.STATUS_ACTIVE,
                ChatBookingSession.STATUS_AWAITING_CONFIRMATION,
            }
            and (not draft or draft.status != ChatBookingDraft.STATUS_COMMITTED)
        ),
        None,
    )
    working = working_pair[0] if working_pair else None

    starts_fresh_order = is_explicit_fresh_order_request(message_text)
    starts_another_booking = is_additional_booking_request(message_text)
    starts_new_after_order = bool(
        committed and is_new_booking_request_after_order(message_text)
    )
    if starts_another_booking or starts_new_after_order:
        latest_session, latest_draft = valid_candidates[0]
        latest_is_working_cart = (
            working
            and latest_session.pk == working.pk
            and (not latest_draft or latest_draft.status != ChatBookingDraft.STATUS_COMMITTED)
        )
        if latest_is_working_cart and not starts_fresh_order:
            logger.info(
                "chatbooking.line.cart_continuation session_id=%s "
                "reason=%s",
                working.pk,
                "explicit_additional" if starts_another_booking else "new_request",
            )
            return use(working)
        logger.info(
            "chatbooking.line.new_booking_session previous_session_id=%s "
            "reason=%s",
            committed.pk if committed else latest_session.pk,
            (
                "explicit_fresh_order"
                if starts_fresh_order
                else "explicit_additional"
                if starts_another_booking
                else "new_request_after_order"
            ),
        )
        return _create_line_session(client, external_user_id, expires_at)

    if working:
        return use(working)

    return use(valid_candidates[0][0])


def _save_inbound_message(session, event, event_record):
    line_message = event["message"]
    message_id = str(line_message.get("id") or "").strip()
    identity = message_id or event_record.external_event_id
    external_key = f"{session.client_id}:line:{identity}"
    if len(external_key) > 320:
        external_key = (
            f"{session.client_id}:line:"
            f"{hashlib.sha256(external_key.encode('utf-8')).hexdigest()}"
        )
    message, _ = ChatBookingMessage.objects.get_or_create(
        external_message_key=external_key,
        defaults={
            "session": session,
            "direction": ChatBookingMessage.DIRECTION_INBOUND,
            "sender_type": ChatBookingMessage.SENDER_CUSTOMER,
            "content": str(line_message.get("text") or "").strip(),
            "metadata": {
                "line_webhook_event_id": event_record.external_event_id,
                "line_message_id": message_id,
                "line_timestamp": event.get("timestamp"),
                "is_redelivery": bool(
                    (event.get("deliveryContext") or {}).get("isRedelivery")
                ),
            },
        },
    )
    if message.session_id != session.id:
        raise RuntimeError("LINE message identity belongs to another session")
    return message


def _mark_processed(event_record, session=None):
    now = timezone.now()
    ChatBookingEvent.objects.filter(pk=event_record.pk).update(
        session=session or event_record.session,
        status=ChatBookingEvent.STATUS_PROCESSED,
        error="",
        processed_at=now,
        updated_at=now,
    )


def _mark_failed(event_record, error, session=None):
    if isinstance(error, (LineAPIError, LineConfigurationError)):
        safe_error = str(error)
    else:
        safe_error = error.__class__.__name__
    ChatBookingEvent.objects.filter(pk=event_record.pk).update(
        session=session or event_record.session,
        status=ChatBookingEvent.STATUS_FAILED,
        error=safe_error[:2000],
        processed_at=None,
        updated_at=timezone.now(),
    )


def _is_supported_text_event(event):
    source = event.get("source") or {}
    message = event.get("message") or {}
    return (
        event.get("type") == "message"
        and message.get("type") == "text"
        and source.get("type") == "user"
        and bool(str(source.get("userId") or "").strip())
        and bool(str(message.get("text") or "").strip())
    )


def _system_reply(content):
    return AIReply(
        content=content,
        message_id=0,
        model="snowland-system",
    )


def _reply_for_turn(session, inbound_message):
    try:
        return run_ai_turn(session, inbound_message)
    except AIDisabledError as exc:
        logger.warning(
            "chatbooking.line.ai_unavailable session_id=%s message_id=%s error_type=%s",
            session.pk,
            inbound_message.pk,
            type(exc).__name__,
        )
        return _system_reply("你的需求已登記由真人客服協助，AI 不會再接續處理。")
    except AITurnBusyError as exc:
        logger.warning(
            "chatbooking.line.ai_unavailable session_id=%s message_id=%s error_type=%s",
            session.pk,
            inbound_message.pk,
            type(exc).__name__,
        )
        return _system_reply("上一則訊息仍在處理中，請稍候一下。")
    except AIConfigurationError as exc:
        logger.error(
            "chatbooking.line.ai_unavailable session_id=%s message_id=%s error_type=%s",
            session.pk,
            inbound_message.pk,
            type(exc).__name__,
        )
        return _system_reply("AI 客服目前尚未完成設定，請稍後再試或改由真人客服協助。")
    except AIProviderError as exc:
        logger.error(
            "chatbooking.line.ai_unavailable session_id=%s message_id=%s "
            "error_type=%s error=%s",
            session.pk,
            inbound_message.pk,
            type(exc).__name__,
            str(exc),
        )
        if str(exc) == "AI 工具呼叫超過安全上限":
            return _system_reply(
                "這次提供的資料較多，目前進度已保存。請回覆「繼續」，我會接著完成查詢與報價。"
            )
        return _system_reply("AI 客服目前暫時無法完成回覆，請稍後再試。")


def _quote_flex_for_reply(session, reply):
    tool_names = set(reply.tool_names or [])
    is_quote = "create_booking_quote" in tool_names
    is_cart_view = bool(
        tool_names
        & {
            "add_booking_to_cart",
            "get_booking_cart",
            "remove_cart_item",
        }
    )
    if not is_quote and not is_cart_view:
        return None
    draft = ChatBookingDraft.objects.filter(session=session).first()
    message = (
        build_booking_confirmation_flex(draft)
        if is_quote
        else build_booking_cart_flex(draft)
    )
    if not message:
        logger.warning(
            "chatbooking.line.flex_quote_skipped session_id=%s message_id=%s",
            session.pk,
            reply.message_id,
        )
        return None

    if reply.message_id:
        outbound = ChatBookingMessage.objects.filter(
            pk=reply.message_id,
            session=session,
            sender_type=ChatBookingMessage.SENDER_AI,
        ).first()
        if outbound:
            metadata = dict(outbound.metadata or {})
            if is_quote:
                metadata.update({
                    "line_message_type": "flex_quote_confirmation",
                    "line_flex_quote_hash": draft.quote_hash,
                    "line_flex_quote_total": (draft.quote or {}).get("total"),
                })
            else:
                metadata.update({
                    "line_message_type": "flex_booking_cart",
                    "line_cart_item_count": len(draft.cart or []),
                })
            outbound.metadata = metadata
            outbound.save(update_fields=["metadata"])
    return message


def process_line_event(client, event, line_client):
    event_record, should_process = _acquire_event(client, event)
    if not should_process:
        return "duplicate"

    session = None
    try:
        if not _is_supported_text_event(event):
            _mark_processed(event_record)
            return "ignored"

        external_user_id = str(event["source"]["userId"]).strip()
        session = _line_session(
            client,
            external_user_id,
            event_record,
            message_text=str((event.get("message") or {}).get("text") or ""),
        )
        ChatBookingEvent.objects.filter(pk=event_record.pk).update(
            session=session,
            updated_at=timezone.now(),
        )
        inbound_message = _save_inbound_message(session, event, event_record)
        logger.info(
            "chatbooking.line.event_started event_id=%s session_id=%s message_id=%s",
            event_record.pk,
            session.pk,
            inbound_message.pk,
        )
        if not session.ai_enabled:
            _mark_processed(event_record, session)
            logger.info(
                "chatbooking.line.event_queued_for_agent event_id=%s "
                "session_id=%s message_id=%s",
                event_record.pk,
                session.pk,
                inbound_message.pk,
            )
            return "processed"
        try:
            line_client.start_loading(external_user_id)
        except (LineAPIError, LineConfigurationError):
            # The loading indicator is only a user experience enhancement. A
            # temporary failure must never prevent the booking turn or reply.
            logger.warning(
                "LINE loading animation failed event_id=%s",
                event_record.external_event_id,
            )
        ai_reply = _reply_for_turn(session, inbound_message)
        flex_message = None
        try:
            flex_message = _quote_flex_for_reply(session, ai_reply)
        except Exception:
            # A rendering issue must not hide the authoritative text reply.
            logger.exception(
                "chatbooking.line.flex_quote_failed session_id=%s message_id=%s",
                session.pk,
                ai_reply.message_id,
            )
        delivery_method = "existing"
        if not event_record.response_sent_at:
            reply_kwargs = {}
            if flex_message:
                reply_kwargs["message"] = flex_message
            try:
                line_client.reply(
                    event.get("replyToken"),
                    ai_reply.content,
                    **reply_kwargs,
                )
                delivery_method = "reply"
            except LineAPIError:
                # Reply tokens are short-lived. Only use paid push delivery as
                # a fallback so a slow AI turn never leaves the customer
                # without a response.
                logger.warning(
                    "LINE final reply failed; falling back to push event_id=%s",
                    event_record.external_event_id,
                )
                push_kwargs = {
                    "retry_key": _push_retry_key(client, event_record),
                    **reply_kwargs,
                }
                line_client.push(
                    external_user_id,
                    ai_reply.content,
                    **push_kwargs,
                )
                delivery_method = "push_fallback"
            response_sent_at = timezone.now()
            ChatBookingEvent.objects.filter(pk=event_record.pk).update(
                response_sent_at=response_sent_at,
                updated_at=response_sent_at,
            )
            event_record.response_sent_at = response_sent_at
        _mark_processed(event_record, session)
        logger.info(
            "chatbooking.line.event_succeeded event_id=%s session_id=%s "
            "message_id=%s response_sent=%s delivery_method=%s",
            event_record.pk,
            session.pk,
            inbound_message.pk,
            bool(event_record.response_sent_at),
            delivery_method,
        )
        return "processed"
    except Exception as exc:
        _mark_failed(event_record, exc, session)
        raise


class LineWebhookAPI(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def post(self, request, client_code):
        channel_secret = str(settings.LINE_CHANNEL_SECRET or "").strip()
        if not channel_secret:
            return Response(
                {"error": "LINE webhook 尚未完成伺服器設定"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            content_length = int(request.META.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            content_length = 0
        if content_length > settings.LINE_WEBHOOK_MAX_BODY_BYTES:
            return Response(
                {"error": "LINE webhook payload 過大"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        raw_body = request.body
        if len(raw_body) > settings.LINE_WEBHOOK_MAX_BODY_BYTES:
            return Response(
                {"error": "LINE webhook payload 過大"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        signature = request.META.get("HTTP_X_LINE_SIGNATURE", "")
        if not verify_line_signature(raw_body, signature, channel_secret):
            return Response(
                {"error": "LINE webhook 簽章無效"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        configured_client_code = str(settings.LINE_CLIENT_CODE or "").strip()
        if configured_client_code and configured_client_code != client_code:
            return Response(
                {"error": "此 LINE Channel 未綁定該 client_code"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response(
                {"error": "LINE webhook JSON 格式錯誤"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        events = payload.get("events") if isinstance(payload, dict) else None
        if not isinstance(events, list):
            return Response(
                {"error": "LINE webhook events 格式錯誤"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            client = resolve_tenant_client(client_code)
        except TenantResolutionError:
            return Response(
                {"error": "找不到啟用中的 SnowLand client_code"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not events:
            return Response({"ok": True, "processed": 0})

        line_client = LineMessagingClient()
        counts = {"processed": 0, "ignored": 0, "duplicate": 0, "failed": 0}
        configuration_failed = False
        for event in events:
            if not isinstance(event, dict):
                counts["ignored"] += 1
                continue
            external_event_id, _ = _event_identity(event)
            try:
                outcome = process_line_event(client, event, line_client)
                counts[outcome] += 1
            except LineConfigurationError:
                configuration_failed = True
                counts["failed"] += 1
                logger.error(
                    "LINE webhook server configuration failed event_id=%s",
                    external_event_id,
                )
            except LineAPIError:
                counts["failed"] += 1
                logger.warning(
                    "LINE reply failed event_id=%s",
                    external_event_id,
                )
            except Exception:
                counts["failed"] += 1
                logger.exception(
                    "LINE webhook event processing failed event_id=%s",
                    external_event_id,
                )

        response_status = status.HTTP_200_OK
        if configuration_failed:
            response_status = status.HTTP_503_SERVICE_UNAVAILABLE
        elif counts["failed"]:
            response_status = status.HTTP_502_BAD_GATEWAY
        return Response({"ok": not counts["failed"], **counts}, status=response_status)
