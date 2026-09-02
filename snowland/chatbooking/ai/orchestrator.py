import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chatbooking.intents import is_explicit_fresh_order_request
from chatbooking.models import (
    ChatBookingDraft,
    ChatBookingMessage,
    ChatBookingSession,
    ChatBookingToolInvocation,
)
from chatbooking.services import format_course_catalog_reply

from .prompts import build_customer_service_instructions
from .provider import AIConfigurationError, AIProviderError, get_provider
from .tool_schemas import BOOKING_TOOLS
from .tools import (
    BookingToolExecutor,
    course_catalog_service_filter,
    high_confidence_booking_updates,
    is_course_catalog_request,
    tool_output_json,
)


logger = logging.getLogger(__name__)


class AIDisabledError(RuntimeError):
    pass


class AITurnBusyError(RuntimeError):
    pass


@dataclass
class AIReply:
    content: str
    message_id: int
    model: str
    response_id: str = ""
    usage: dict = field(default_factory=dict)
    tool_names: list = field(default_factory=list)
    replayed: bool = False


def _item_value(item, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _dump_item(item):
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)
    raise AIProviderError("OpenAI 回傳了無法處理的輸出格式")


def _dump_usage(usage):
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return usage
    if hasattr(usage, "model_dump"):
        return usage.model_dump(exclude_none=True)
    return {}


def _conversation_input(session, inbound_message):
    messages = list(
        ChatBookingMessage.objects.filter(
            session=session,
            id__lte=inbound_message.id,
        )
        .exclude(sender_type=ChatBookingMessage.SENDER_SYSTEM)
        .order_by("-id")[: settings.OPENAI_MAX_CONTEXT_MESSAGES]
    )
    messages.reverse()
    input_items = []
    for message in messages:
        if message.sender_type == ChatBookingMessage.SENDER_CUSTOMER:
            role = "user"
        elif message.sender_type in (
            ChatBookingMessage.SENDER_AI,
            ChatBookingMessage.SENDER_AGENT,
        ):
            role = "assistant"
        else:
            continue
        input_items.append({"role": role, "content": message.content})
    return input_items


def _ensure_new_cart_marker(session, inbound_message, content):
    """Make a newly opened LINE cart visible before its first item is complete."""
    if session.channel != ChatBookingSession.CHANNEL_LINE:
        return content
    if not is_explicit_fresh_order_request(inbound_message.content):
        return content
    if "預約購物車" in content:
        return content
    customer_message_count = ChatBookingMessage.objects.filter(
        session=session,
        sender_type=ChatBookingMessage.SENDER_CUSTOMER,
        id__lte=inbound_message.id,
    ).count()
    if customer_message_count != 1:
        return content
    return f"已建立新的預約購物車（目前 0 項）。\n\n{content}"


def _existing_reply(turn):
    message_id = (turn.output_data or {}).get("outbound_message_id")
    if not message_id:
        return None
    message = ChatBookingMessage.objects.filter(
        id=message_id,
        session=turn.session,
        sender_type=ChatBookingMessage.SENDER_AI,
    ).first()
    if not message:
        return None
    metadata = message.metadata or {}
    return AIReply(
        content=message.content,
        message_id=message.id,
        model=metadata.get("model", ""),
        response_id=metadata.get("openai_response_id", ""),
        usage=metadata.get("usage", {}),
        tool_names=metadata.get("tool_names", []),
        replayed=True,
    )


@transaction.atomic
def _acquire_turn(session, inbound_message):
    locked_session = ChatBookingSession.objects.select_for_update().get(pk=session.pk)
    if not locked_session.ai_enabled:
        raise AIDisabledError("此對話已轉由真人客服處理")

    # A tool-heavy turn can legitimately make several provider calls. Keep the
    # lease longer than the configured worst-case request window.
    stale_before = timezone.now() - timedelta(minutes=10)
    processing = list(
        ChatBookingToolInvocation.objects.select_for_update().filter(
            session=locked_session,
            tool_key="ai_turn",
            status=ChatBookingToolInvocation.STATUS_PROCESSING,
        )
    )
    current_key = f"message-{inbound_message.id}"
    for item in processing:
        if item.idempotency_key == current_key:
            if item.updated_at >= stale_before:
                raise AITurnBusyError("這則訊息仍在處理中")
            item.status = ChatBookingToolInvocation.STATUS_FAILED
            item.error = "AI turn lease expired"
            item.save(update_fields=["status", "error", "updated_at"])
        elif item.updated_at >= stale_before:
            raise AITurnBusyError("前一則訊息仍在處理中")
        else:
            item.status = ChatBookingToolInvocation.STATUS_FAILED
            item.error = "AI turn lease expired"
            item.save(update_fields=["status", "error", "updated_at"])

    turn, created = ChatBookingToolInvocation.objects.select_for_update().get_or_create(
        session=locked_session,
        tool_key="ai_turn",
        idempotency_key=current_key,
        defaults={"input_data": {"inbound_message_id": inbound_message.id}},
    )
    if not created and turn.status == ChatBookingToolInvocation.STATUS_SUCCEEDED:
        reply = _existing_reply(turn)
        if reply:
            return turn, reply
    if not created:
        turn.status = ChatBookingToolInvocation.STATUS_PROCESSING
        turn.output_data = {}
        turn.error = ""
        turn.save(update_fields=["status", "output_data", "error", "updated_at"])
    return turn, None


def _fail_turn(turn, error):
    ChatBookingToolInvocation.objects.filter(pk=turn.pk).update(
        status=ChatBookingToolInvocation.STATUS_FAILED,
        error=str(error)[:2000],
        updated_at=timezone.now(),
    )


def _complete_turn(
    turn,
    session,
    inbound_message,
    *,
    content,
    model,
    response_id="",
    usage=None,
    tool_names=None,
):
    usage = usage or {}
    tool_names = tool_names or []
    content = _ensure_new_cart_marker(session, inbound_message, content)
    draft = ChatBookingDraft.objects.filter(session=session).first()
    outbound = ChatBookingMessage.objects.create(
        session=session,
        direction=ChatBookingMessage.DIRECTION_OUTBOUND,
        sender_type=ChatBookingMessage.SENDER_AI,
        content=content,
        metadata={
            "in_reply_to_message_id": inbound_message.id,
            "model": model,
            "openai_response_id": response_id,
            "usage": usage,
            "tool_names": tool_names,
            "openai_store": False,
            "quote_hash_at_reply": draft.quote_hash if draft and draft.quote else "",
        },
    )
    ChatBookingToolInvocation.objects.filter(pk=turn.pk).update(
        status=ChatBookingToolInvocation.STATUS_SUCCEEDED,
        output_data={"outbound_message_id": outbound.id},
        error="",
        updated_at=timezone.now(),
    )
    return AIReply(
        content=content,
        message_id=outbound.id,
        model=model,
        response_id=response_id,
        usage=usage,
        tool_names=tool_names,
    )


def run_ai_turn(session, inbound_message, provider=None):
    turn, replay = _acquire_turn(session, inbound_message)
    if replay:
        logger.info(
            "chatbooking.ai_turn.replayed session_id=%s message_id=%s turn_id=%s",
            session.pk,
            inbound_message.pk,
            turn.pk,
        )
        return replay

    provider = provider or get_provider()
    input_items = _conversation_input(session, inbound_message)
    executor = BookingToolExecutor(session, inbound_message)
    tool_names = []
    course_catalog = None
    logger.info(
        "chatbooking.ai_turn.started session_id=%s message_id=%s turn_id=%s "
        "max_tool_rounds=%s current_step=%s",
        session.pk,
        inbound_message.pk,
        turn.pk,
        settings.OPENAI_MAX_TOOL_ROUNDS,
        session.current_step,
    )
    deterministic_updates = high_confidence_booking_updates(inbound_message.content)
    if deterministic_updates:
        prefill_result = executor.execute(
            "update_booking_details",
            deterministic_updates,
            f"deterministic-message-{inbound_message.id}",
        )
        if prefill_result.get("ok"):
            tool_names.append("update_booking_details")
    if is_course_catalog_request(inbound_message.content):
        catalog_result = executor.execute(
            "get_course_catalog",
            {
                "service_type": course_catalog_service_filter(inbound_message.content),
                "category_id": None,
                "resort": None,
            },
            f"deterministic-catalog-message-{inbound_message.id}",
        )
        if catalog_result.get("ok"):
            course_catalog = catalog_result.get("catalog")
            tool_names.append("get_course_catalog")
            try:
                return _complete_turn(
                    turn,
                    session,
                    inbound_message,
                    content=format_course_catalog_reply(course_catalog),
                    model="snowland-course-catalog-v1",
                    tool_names=tool_names,
                )
            except Exception as exc:
                _fail_turn(turn, "課程目錄回覆失敗")
                raise AIProviderError("AI 客服處理失敗") from exc

    try:
        for round_index in range(1, settings.OPENAI_MAX_TOOL_ROUNDS + 1):
            session.refresh_from_db()
            logger.info(
                "chatbooking.ai_turn.provider_round session_id=%s message_id=%s "
                "turn_id=%s round=%s current_step=%s",
                session.pk,
                inbound_message.pk,
                turn.pk,
                round_index,
                session.current_step,
            )
            response = provider.create(
                instructions=build_customer_service_instructions(
                    session,
                    course_catalog=course_catalog,
                ),
                input_items=input_items,
                tools=BOOKING_TOOLS,
            )
            output_items = list(_item_value(response, "output", []) or [])
            input_items.extend(_dump_item(item) for item in output_items)
            function_calls = [
                item for item in output_items if _item_value(item, "type") == "function_call"
            ]

            if not function_calls:
                content = str(_item_value(response, "output_text", "") or "").strip()
                if not content:
                    raise AIProviderError("OpenAI 未產生可傳送的文字回覆")
                usage = _dump_usage(_item_value(response, "usage"))
                model = str(_item_value(response, "model", getattr(provider, "model", "")) or "")
                response_id = str(_item_value(response, "id", "") or "")
                reply = _complete_turn(
                    turn,
                    session,
                    inbound_message,
                    content=content,
                    model=model,
                    response_id=response_id,
                    usage=usage,
                    tool_names=tool_names,
                )
                logger.info(
                    "chatbooking.ai_turn.succeeded session_id=%s message_id=%s "
                    "turn_id=%s rounds=%s tool_count=%s outbound_message_id=%s",
                    session.pk,
                    inbound_message.pk,
                    turn.pk,
                    round_index,
                    len(tool_names),
                    reply.message_id,
                )
                return reply

            for call in function_calls:
                name = str(_item_value(call, "name", "") or "")
                call_id = str(_item_value(call, "call_id", "") or "")
                raw_arguments = _item_value(call, "arguments", "{}") or "{}"
                try:
                    arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                    if not isinstance(arguments, dict):
                        raise ValueError
                    result = executor.execute(name, arguments, call_id)
                except (json.JSONDecodeError, ValueError):
                    result = {"ok": False, "error": "工具參數不是有效的 JSON 物件"}
                tool_names.append(name)
                executor.session.refresh_from_db()
                logger.info(
                    "chatbooking.ai_turn.tool_finished session_id=%s message_id=%s "
                    "turn_id=%s round=%s tool=%s ok=%s current_step=%s",
                    session.pk,
                    inbound_message.pk,
                    turn.pk,
                    round_index,
                    name,
                    result.get("ok") is True,
                    executor.session.current_step,
                )
                input_items.append({
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": tool_output_json(result),
                })

        raise AIProviderError("AI 工具呼叫超過安全上限")
    except (AIConfigurationError, AIProviderError, AIDisabledError, AITurnBusyError) as exc:
        _fail_turn(turn, exc)
        logger.error(
            "chatbooking.ai_turn.failed session_id=%s message_id=%s turn_id=%s "
            "error_type=%s error=%s tool_count=%s",
            session.pk,
            inbound_message.pk,
            turn.pk,
            type(exc).__name__,
            str(exc),
            len(tool_names),
        )
        raise
    except Exception as exc:
        _fail_turn(turn, "AI 客服處理失敗")
        logger.error(
            "chatbooking.ai_turn.failed session_id=%s message_id=%s turn_id=%s "
            "error_type=%s error=unexpected tool_count=%s",
            session.pk,
            inbound_message.pk,
            turn.pk,
            type(exc).__name__,
            len(tool_names),
        )
        raise AIProviderError("AI 客服處理失敗") from exc
