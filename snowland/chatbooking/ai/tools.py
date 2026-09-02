import json
import re
from copy import deepcopy

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import strip_tags

from Client.models import SiteContent
from chatbooking.flow import (
    apply_updates,
    checkout_missing_fields,
    item_missing_fields,
    missing_fields,
    next_field,
)
from chatbooking.intents import (
    is_additional_booking_request,
    is_explicit_human_support_request,
)
from chatbooking.models import (
    ChatBookingDraft,
    ChatBookingHandoff,
    ChatBookingSession,
    ChatBookingToolInvocation,
)
from chatbooking.services import (
    add_current_booking_to_cart,
    cart_summary,
    clear_booking_cart,
    confirm_quoted_session,
    course_catalog_payload,
    edit_cart_item,
    make_quote,
    option_payload,
    payment_snapshot_for_groups,
    remove_cart_item,
    start_new_cart_item,
    submit_bank_transfer,
)


class BookingToolError(ValueError):
    pass


def _compact_text(value):
    return re.sub(r"[\s，。！？、,.!?:：；;「」『』（）()]+", "", str(value or "")).lower()


def has_explicit_policy_consent(text):
    normalized = _compact_text(text)
    if any(item in normalized for item in ("不同意", "不接受", "先不要", "還沒同意", "未同意")):
        return False
    exact = {"同意條款", "同意政策", "同意取消政策", "接受條款", "接受政策"}
    return normalized in exact or (
        any(word in normalized for word in ("同意", "接受"))
        and any(subject in normalized for subject in ("政策", "條款", "規定", "取消"))
    )


def has_explicit_order_confirmation(text):
    normalized = _compact_text(text)
    if any(
        item in normalized
        for item in (
            "不要下單", "不確認", "取消下單", "取消預約", "先等等", "等一下",
            "先不要", "要修改", "想修改", "想改", "改成",
        )
    ):
        return False
    exact = {"確認下單", "確認預約", "同意下單", "幫我下單", "請幫我下單", "正式下單"}
    return normalized in exact or any(
        item in normalized
        for item in ("確認下單", "確認預約", "同意下單", "幫我下單", "請建立訂單")
    )


def high_confidence_booking_updates(text):
    normalized = _compact_text(text)
    photo_terms = ("滑雪攝影", "攝影服務", "攝影方案", "跟拍")
    ski_terms = ("滑雪課程", "滑雪課", "教練課")
    has_photo = any(term in normalized for term in photo_terms)
    has_ski = any(term in normalized for term in ski_terms)
    if has_photo == has_ski:
        return {}
    return {"service_type": "photo" if has_photo else "ski"}


def is_course_catalog_request(text):
    normalized = _compact_text(text)
    subjects = ("課程", "方案", "教學", "單板", "雙板", "snowboard", "ski", "攝影", "跟拍")
    discovery_terms = ("介紹", "有哪些", "有什麼", "推薦", "差別", "區別", "內容", "選擇")
    return (
        any(subject in normalized for subject in subjects)
        and any(term in normalized for term in discovery_terms)
    )


def course_catalog_service_filter(text):
    normalized = _compact_text(text)
    photo_terms = ("攝影", "跟拍", "全家福", "寫真")
    ski_terms = ("滑雪課程", "教練課", "單板", "雙板", "snowboard", "ski", "山岳滑雪", "野雪")
    has_photo = any(term in normalized for term in photo_terms)
    has_ski = any(term in normalized for term in ski_terms)
    if has_photo == has_ski:
        return None
    return "photo" if has_photo else "ski"


def _state_result(session):
    draft = ChatBookingDraft.objects.filter(session=session).first()
    booking_details = session.slot_values or {}
    saved_cart = draft.cart if draft and isinstance(draft.cart, list) else []
    return {
        "session_status": session.status,
        "current_step": session.current_step,
        "state_version": session.state_version,
        "booking_details": booking_details,
        "missing_fields": missing_fields(booking_details),
        "current_item_missing_fields": item_missing_fields(booking_details),
        "checkout_missing_fields": checkout_missing_fields(booking_details),
        "cart": {
            "item_count": len(saved_cart),
            "items": cart_summary(saved_cart),
        },
        "quote": {
            **(draft.quote or {}),
            "status": draft.status,
            "quote_expires_at": (
                draft.quote_expires_at.isoformat() if draft.quote_expires_at else None
            ),
        } if draft and draft.quote else None,
        "reservation_group_ids": draft.reservation_group_ids if draft else [],
    }


def _audit_input(arguments):
    value = deepcopy(arguments)
    if "sender_account" in value:
        value["sender_account"] = "*****"
    return value


class BookingToolExecutor:
    def __init__(self, session, inbound_message):
        self.session = session
        self.inbound_message = inbound_message

    def execute(self, name, arguments, call_id):
        idempotency_key = str(call_id or "")[:128]
        if not idempotency_key:
            return {"ok": False, "error": "工具呼叫缺少識別碼"}

        with transaction.atomic():
            invocation, created = ChatBookingToolInvocation.objects.select_for_update().get_or_create(
                session=self.session,
                tool_key=f"ai_tool:{name}",
                idempotency_key=idempotency_key,
                defaults={"input_data": _audit_input(arguments)},
            )
            if not created:
                if invocation.status == ChatBookingToolInvocation.STATUS_SUCCEEDED:
                    return invocation.output_data
                if invocation.status == ChatBookingToolInvocation.STATUS_FAILED:
                    return invocation.output_data or {"ok": False, "error": invocation.error}
                return {"ok": False, "error": "相同工具呼叫仍在處理"}

        try:
            handler = getattr(self, f"_tool_{name}", None)
            if handler is None:
                raise BookingToolError("不允許的工具")
            output = handler(arguments)
            result = {"ok": True, **output}
            status = ChatBookingToolInvocation.STATUS_SUCCEEDED
            error = ""
        except (BookingToolError, ValueError, TypeError, ChatBookingDraft.DoesNotExist) as exc:
            result = {"ok": False, "error": str(exc)}
            status = ChatBookingToolInvocation.STATUS_FAILED
            error = str(exc)

        ChatBookingToolInvocation.objects.filter(pk=invocation.pk).update(
            status=status,
            output_data=result,
            error=error,
            updated_at=timezone.now(),
        )
        return result

    def _locked_session(self):
        return ChatBookingSession.objects.select_for_update().select_related("client", "user").get(
            pk=self.session.pk,
        )

    def _policy_consent_is_allowed(self):
        if has_explicit_policy_consent(self.inbound_message.content):
            return True
        if _compact_text(self.inbound_message.content) not in {"同意", "我同意", "接受", "我接受"}:
            return False
        previous = (
            self.inbound_message.session.messages.filter(
                id__lt=self.inbound_message.id,
                sender_type__in=[
                    self.inbound_message.SENDER_AI,
                    self.inbound_message.SENDER_AGENT,
                ],
            )
            .order_by("-created_at", "-id")
            .first()
        )
        previous_text = _compact_text(previous.content if previous else "")
        return any(subject in previous_text for subject in ("政策", "條款", "取消規定"))

    def _tool_get_booking_state(self, arguments):
        self.session.refresh_from_db()
        return {"state": _state_result(self.session)}

    @transaction.atomic
    def _tool_update_booking_details(self, arguments):
        session = self._locked_session()
        draft, _ = ChatBookingDraft.objects.select_for_update().get_or_create(session=session)
        if draft.status == ChatBookingDraft.STATUS_COMMITTED:
            raise BookingToolError("訂單已建立，不可再修改本次預約")

        updates = {key: value for key, value in arguments.items() if value is not None}
        counts = updates.get("ability_level_counts")
        if isinstance(counts, dict):
            updates["ability_level_counts"] = {
                key: value for key, value in counts.items() if value is not None
            }

        if updates.get("policy_accepted") is True and not self._policy_consent_is_allowed():
            raise BookingToolError("本次客人訊息沒有明確同意政策，不能代為同意")

        next_values = apply_updates(session.slot_values, updates)
        if next_values != (session.slot_values or {}):
            session.slot_values = next_values
            session.state_version += 1
            session.current_step = next_field(next_values)
            session.status = (
                ChatBookingSession.STATUS_AWAITING_CONFIRMATION
                if not missing_fields(next_values)
                else ChatBookingSession.STATUS_ACTIVE
            )
            session.save(
                update_fields=[
                    "slot_values",
                    "state_version",
                    "current_step",
                    "status",
                    "updated_at",
                ],
            )
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

        self.session = session
        return {"state": _state_result(session)}

    def _tool_list_booking_options(self, arguments):
        self.session.refresh_from_db()
        field = str(arguments.get("field") or "")
        options = option_payload(
            self.session.client,
            self.session.slot_values or {},
            field,
            month=arguments.get("month"),
        )
        return {"field": field, "options": options}

    def _tool_get_course_catalog(self, arguments):
        service_type = arguments.get("service_type")
        category_id = arguments.get("category_id")
        resort = str(arguments.get("resort") or "").strip() or None
        catalog = course_catalog_payload(
            self.session.client,
            service_type=service_type,
            category_id=category_id,
            resort=resort,
        )
        return {
            "catalog": catalog,
            "note": (
                "目前沒有符合條件且已啟用、已綁定雪場的課程方案。"
                if not catalog["categories"]
                else "只能依這份後端課程目錄介紹；價格、日期與時段仍須另外查詢。"
            ),
        }

    def _tool_search_customer_knowledge(self, arguments):
        query = str(arguments.get("query") or "").strip()[:200]
        if not query:
            raise BookingToolError("請提供要查詢的問題")
        content_type = arguments.get("content_type")
        allowed_types = {choice[0] for choice in SiteContent.CONTENT_TYPE_CHOICES}
        if content_type and content_type not in allowed_types:
            raise BookingToolError("不支援的內容類型")

        now = timezone.now()
        queryset = SiteContent.objects.filter(
            client=self.session.client,
            status="active",
        ).filter(
            Q(start_at__isnull=True) | Q(start_at__lte=now),
        ).filter(
            Q(end_at__isnull=True) | Q(end_at__gte=now),
        )
        if content_type:
            queryset = queryset.filter(content_type=content_type)

        known_terms = [
            item
            for item in (
                "取消", "退款", "改期", "政策", "條款", "裝備", "租借", "優惠", "折扣",
                "付款", "匯款", "信用卡", "交通", "接送", "兒童", "年齡", "攝影",
                "滑雪", "保險", "天氣", "集合", "行前", "雪場", "教練",
            )
            if item.lower() in query.lower()
        ]
        split_terms = [
            term for term in re.findall(r"[A-Za-z0-9_-]{2,}", query) if len(term) >= 2
        ]
        trimmed = query
        for phrase in ("我想知道", "想了解", "請問", "可以告訴我", "關於", "怎麼辦", "如何", "嗎"):
            trimmed = trimmed.replace(phrase, "")
        terms = list(dict.fromkeys(known_terms + split_terms))
        if not terms and 2 <= len(trimmed.strip()) <= 30:
            terms.append(trimmed.strip())

        text_query = Q()
        for term in terms[:8]:
            text_query |= (
                Q(title__icontains=term)
                | Q(subtitle__icontains=term)
                | Q(summary__icontains=term)
                | Q(body__icontains=term)
                | Q(location_key__icontains=term)
            )
        if terms:
            queryset = queryset.filter(text_query)
        else:
            queryset = queryset.none()

        results = []
        for item in queryset.order_by("-is_pinned", "display_order", "-updated_at")[:5]:
            text = strip_tags(item.summary or item.body or item.subtitle or "")
            text = re.sub(r"\s+", " ", text).strip()
            results.append({
                "id": item.id,
                "content_type": item.content_type,
                "title": item.title,
                "location_key": item.location_key,
                "snippet": text[:800],
                "link_url": item.link_url,
            })
        return {
            "query": query,
            "results": results,
            "note": "沒有結果時必須說查不到，不可自行補充政策或優惠。" if not results else "",
        }

    def _tool_get_booking_cart(self, arguments):
        self.session.refresh_from_db()
        draft = ChatBookingDraft.objects.filter(session=self.session).first()
        cart = draft.cart if draft and isinstance(draft.cart, list) else []
        return {
            "cart": {
                "item_count": len(cart),
                "items": cart_summary(cart),
                "quote": draft.quote if draft and draft.quote else None,
            },
        }

    def _tool_add_booking_to_cart(self, arguments):
        session, draft = add_current_booking_to_cart(self.session)
        self.session = session
        return {
            "cart": {
                "item_count": len(draft.cart),
                "items": cart_summary(draft.cart),
            },
            "state": _state_result(session),
            "instruction": "本項已加入購物車。請詢問客人要繼續新增、查看購物車或結帳。",
        }

    def _tool_start_new_cart_item(self, arguments):
        if not is_additional_booking_request(self.inbound_message.content):
            raise BookingToolError("客人本次訊息沒有要求繼續新增購物車項目")
        session, draft = start_new_cart_item(self.session)
        self.session = session
        return {
            "cart": {
                "item_count": len(draft.cart),
                "items": cart_summary(draft.cart),
            },
            "state": _state_result(session),
            "instruction": "已保留購物車，請從新項目的服務類型開始詢問。",
        }

    def _tool_remove_cart_item(self, arguments):
        normalized = _compact_text(self.inbound_message.content)
        if not any(word in normalized for word in ("刪除", "移除", "拿掉", "不要第")):
            raise BookingToolError("客人本次訊息沒有明確要求刪除購物車項目")
        session, draft, _ = remove_cart_item(self.session, arguments.get("index"))
        self.session = session
        return {
            "cart": {
                "item_count": len(draft.cart),
                "items": cart_summary(draft.cart),
            },
            "state": _state_result(session),
        }

    def _tool_edit_cart_item(self, arguments):
        normalized = _compact_text(self.inbound_message.content)
        if not any(word in normalized for word in ("修改", "編輯", "改第", "調整")):
            raise BookingToolError("客人本次訊息沒有明確要求編輯購物車項目")
        session, draft = edit_cart_item(self.session, arguments.get("index"))
        self.session = session
        return {
            "cart": {
                "item_count": len(draft.cart),
                "items": cart_summary(draft.cart),
            },
            "state": _state_result(session),
            "instruction": "指定項目已載入編輯區，請詢問客人要修改哪個欄位。",
        }

    def _tool_clear_booking_cart(self, arguments):
        normalized = _compact_text(self.inbound_message.content)
        if "清空" not in normalized:
            raise BookingToolError("客人本次訊息沒有明確要求清空購物車")
        session, draft, removed_count = clear_booking_cart(self.session)
        self.session = session
        return {
            "removed_count": removed_count,
            "cart": {
                "item_count": len(draft.cart),
                "items": [],
            },
            "state": _state_result(session),
        }

    @transaction.atomic
    def _tool_create_booking_quote(self, arguments):
        session = self._locked_session()
        draft = ChatBookingDraft.objects.select_for_update().filter(session=session).first()
        if draft and draft.status == ChatBookingDraft.STATUS_COMMITTED:
            raise BookingToolError("訂單已建立")
        if not draft or not draft.cart:
            raise BookingToolError("購物車目前沒有項目，請先將完整預約加入購物車")
        if (
            draft.cart
            and not item_missing_fields(session.slot_values or {})
            and (session.slot_values or {}).get("service_type")
        ):
            raise BookingToolError("目前這筆預約尚未加入購物車，請先加入再結帳")
        if (session.slot_values or {}).get("policy_accepted") is not True:
            raise BookingToolError("請先取得客人對預約與取消政策的明確同意")
        draft = make_quote(session)
        session.status = ChatBookingSession.STATUS_AWAITING_CONFIRMATION
        session.current_step = "confirmation"
        session.save(update_fields=["status", "current_step", "updated_at"])
        self.session = session
        return {
            "quote": {
                **draft.quote,
                "quote_expires_at": draft.quote_expires_at.isoformat(),
            },
            "state_version": session.state_version,
            "instruction": "請先向客人完整摘要並詢問是否確認下單；本次工具呼叫不可接著建立訂單。",
        }

    def _tool_confirm_booking(self, arguments):
        if arguments.get("confirmed") is not True:
            raise BookingToolError("客人尚未確認下單")
        confirmation_text = str(arguments.get("confirmation_text") or "").strip()
        raw_text = self.inbound_message.content
        if not has_explicit_order_confirmation(raw_text):
            raise BookingToolError("本次客人訊息沒有明確確認下單")
        if (
            not _compact_text(confirmation_text)
            or _compact_text(confirmation_text) not in _compact_text(raw_text)
        ):
            raise BookingToolError("確認文字必須來自客人本次訊息")

        self.session.refresh_from_db()
        draft = ChatBookingDraft.objects.filter(session=self.session).first()
        if not draft or draft.status != ChatBookingDraft.STATUS_QUOTED:
            raise BookingToolError("請先建立並向客人顯示有效報價")
        prior_ai_messages = self.inbound_message.session.messages.filter(
            id__lt=self.inbound_message.id,
            sender_type=self.inbound_message.SENDER_AI,
        ).order_by("-id")[:10]
        quote_total = str((draft.quote or {}).get("total", ""))

        def amount_is_visible(message):
            metadata = message.metadata or {}
            if (
                metadata.get("line_message_type") == "flex_quote_confirmation"
                and metadata.get("line_flex_quote_hash") == draft.quote_hash
                and str(metadata.get("line_flex_quote_total")) == quote_total
            ):
                return True
            compact = re.sub(r"[\s,，]", "", message.content).lower()
            return any(
                marker in compact
                for marker in (
                    f"twd{quote_total}",
                    f"nt${quote_total}",
                    f"ntd{quote_total}",
                    f"總價{quote_total}",
                    f"總金額{quote_total}",
                    f"應付{quote_total}",
                )
            )

        quote_was_presented = any(
            (message.metadata or {}).get("quote_hash_at_reply") == draft.quote_hash
            and quote_total
            and amount_is_visible(message)
            for message in prior_ai_messages
        )
        if not quote_was_presented:
            raise BookingToolError("客人尚未在看過本次報價後，以新的訊息確認下單")

        result = confirm_quoted_session(
            self.session,
            self.session.user,
            idempotency_key=f"ai-confirm-message-{self.inbound_message.id}",
            expected_state_version=self.session.state_version,
            expected_quote_hash=draft.quote_hash,
            input_data={
                "confirmed": True,
                "confirmation_text": confirmation_text,
                "inbound_message_id": self.inbound_message.id,
            },
        )
        if not result.ok:
            raise BookingToolError(result.error)
        return {"booking": result.output, "replayed": result.replayed}

    def _tool_get_payment_info(self, arguments):
        self.session.refresh_from_db()
        draft = ChatBookingDraft.objects.filter(session=self.session).first()
        if not draft or draft.status != ChatBookingDraft.STATUS_COMMITTED:
            raise BookingToolError("尚未建立可付款訂單")
        snapshot = payment_snapshot_for_groups(
            self.session.client,
            draft.reservation_group_ids,
        )
        payment_allowed = draft.payment_snapshot.get("payment_allowed") is True
        snapshot["payment_allowed"] = payment_allowed
        if not payment_allowed:
            snapshot["payment_methods"] = []
            snapshot["card_status"] = "unavailable_until_scheduled"
        return {"payment": snapshot}

    def _tool_submit_bank_transfer(self, arguments):
        sender_account = str(arguments.get("sender_account") or "").strip()
        if not re.fullmatch(r"\d{5}", sender_account):
            raise BookingToolError("請提供匯款帳戶後五碼")
        if not re.search(rf"(?<!\d){re.escape(sender_account)}(?!\d)", self.inbound_message.content):
            raise BookingToolError("本次客人訊息中找不到這組匯款後五碼")
        self.session.refresh_from_db()
        snapshot = submit_bank_transfer(self.session, sender_account)
        return {"payment": snapshot, "message": "匯款帳戶後五碼已提交，等待人工核對"}

    @transaction.atomic
    def _tool_request_human_support(self, arguments):
        reason = str(arguments.get("reason") or "").strip()[:2000]
        if not reason:
            raise BookingToolError("請提供轉接原因")
        if (
            is_additional_booking_request(self.inbound_message.content)
            and not is_explicit_human_support_request(self.inbound_message.content)
        ):
            raise BookingToolError("客人要新增另一筆預約，不是改期；請建立新的預約流程，不得轉真人")
        session = self._locked_session()
        handoff, _ = ChatBookingHandoff.objects.update_or_create(
            session=session,
            defaults={
                "status": ChatBookingHandoff.STATUS_REQUESTED,
                "reason": reason,
            },
        )
        session.ai_enabled = False
        session.status = ChatBookingSession.STATUS_ESCALATED
        session.current_step = "human_support"
        session.save(update_fields=["ai_enabled", "status", "current_step", "updated_at"])
        self.session = session
        return {
            "handoff": {
                "status": handoff.status,
                "reason": handoff.reason,
                "requested_at": handoff.requested_at.isoformat(),
            },
            "instruction": "已轉接真人，請告知客人並停止其他操作。",
        }


def tool_output_json(result):
    return json.dumps(result, ensure_ascii=False, default=str)
