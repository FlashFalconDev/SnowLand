import base64
import hashlib
import hmac
import json
import os
import uuid
from copy import deepcopy
from datetime import time, timedelta
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from Client.models import Client, SiteContent
from Coach.models import Coach, CoachCourseLevel, CoachResort
from Coursekit.models import CourseCategory, CoursePricing, CourseSession, CourseTemplate, CourseType
from Resorts.models import Resorts
from booking.models import Booking, Payment, Reservation, ReservationGroup

from .ai.orchestrator import AIReply, run_ai_turn
from .ai.provider import OpenAIResponseProvider
from .ai.tool_schemas import UPDATE_PROPERTIES
from .ai.tools import (
    BookingToolExecutor,
    course_catalog_service_filter,
    has_explicit_order_confirmation,
    has_explicit_policy_consent,
    high_confidence_booking_updates,
    is_course_catalog_request,
)
from .flow import (
    apply_updates,
    checkout_missing_fields,
    item_missing_fields,
    missing_fields,
    validate_business_answers,
)
from .intents import (
    is_additional_booking_request,
    is_explicit_fresh_order_request,
    is_explicit_human_support_request,
    is_new_booking_request_after_order,
)
from .line import LineAPIError, LineMessagingClient, verify_line_signature
from .line_flex import build_booking_cart_flex, build_booking_confirmation_flex
from .models import (
    ChatBookingDraft,
    ChatBookingEvent,
    ChatBookingHandoff,
    ChatBookingMessage,
    ChatBookingSession,
    ChatBookingToolInvocation,
)
from .services import (
    add_current_booking_to_cart,
    confirm_quoted_session,
    edit_cart_item,
    make_quote,
    remove_cart_item,
    start_new_cart_item,
    submit_bank_transfer,
)


class ChatBookingFlowTests(SimpleTestCase):
    def test_new_booking_intent_is_distinct_from_order_changes(self):
        self.assertTrue(is_additional_booking_request("不，我是要多新增一個預約"))
        self.assertTrue(is_additional_booking_request("不需要真人客服，你直接幫我新增就好"))
        self.assertTrue(is_additional_booking_request("我要新增一筆測試預約"))
        self.assertTrue(is_additional_booking_request("我要新下一單"))
        self.assertTrue(is_additional_booking_request("我要一個新的訂單"))
        self.assertTrue(is_additional_booking_request("我要新預約"))
        self.assertTrue(is_additional_booking_request("繼續新增"))
        self.assertTrue(is_explicit_fresh_order_request("我要新下一單"))
        self.assertTrue(is_explicit_fresh_order_request("我要新預約"))
        self.assertFalse(is_explicit_fresh_order_request("我不要新預約"))
        self.assertFalse(is_explicit_fresh_order_request("繼續新增"))
        self.assertFalse(is_explicit_fresh_order_request("再加一筆"))
        self.assertTrue(is_additional_booking_request("再預約"))
        self.assertTrue(is_additional_booking_request("在預約"))
        self.assertTrue(is_additional_booking_request("我要怎麼另外開？"))
        self.assertTrue(is_new_booking_request_after_order(
            "我要預約 2026 年 12 月 11 日星野 Tomamu 的單板 Snowboard 課程"
        ))
        self.assertFalse(is_new_booking_request_after_order("把原本 12/10 改成 12/11"))
        self.assertFalse(is_new_booking_request_after_order("請問訂單付款資料"))
        self.assertFalse(is_explicit_human_support_request("不需要真人客服"))
        self.assertTrue(is_explicit_human_support_request("請幫我轉真人客服"))

    def test_course_catalog_intent_uses_natural_language_without_prefix(self):
        self.assertTrue(is_course_catalog_request("你們的課程有什麼介紹介紹"))
        self.assertTrue(is_course_catalog_request("星野有哪些攝影方案？"))
        self.assertEqual(course_catalog_service_filter("介紹單板課程"), "ski")
        self.assertEqual(course_catalog_service_filter("有哪些攝影方案"), "photo")
        self.assertFalse(is_course_catalog_request("我想預約明天的課程"))

    def test_changing_resort_invalidates_downstream_answers(self):
        current = {
            "service_type": "ski",
            "category_id": 1,
            "resort": "A",
            "course_type_id": 2,
            "template_id": 3,
            "course_dates": ["2027-01-10"],
            "session_id": 4,
            "coach_id": 5,
            "contact_phone": "0912345678",
        }
        result = apply_updates(current, {"resort": "B"})
        self.assertEqual(result["resort"], "B")
        self.assertNotIn("course_type_id", result)
        self.assertNotIn("template_id", result)
        self.assertNotIn("course_dates", result)
        self.assertNotIn("session_id", result)
        self.assertNotIn("coach_id", result)
        self.assertEqual(result["contact_phone"], "0912345678")

    def test_photo_flow_does_not_require_ski_answers(self):
        state = {
            "service_type": "photo",
            "category_id": 1,
            "resort": "A",
            "course_type_id": 2,
            "template_id": 3,
            "course_dates": ["2027-01-10"],
            "session_id": 4,
            "contact_phone": "0912345678",
            "policy_accepted": True,
        }
        self.assertEqual(missing_fields(state), [])

    def test_cart_item_and_checkout_fields_are_evaluated_separately(self):
        state = {
            "service_type": "photo",
            "category_id": 1,
            "resort": "A",
            "course_type_id": 2,
            "template_id": 3,
            "course_dates": ["2027-01-10"],
            "session_id": 4,
        }
        self.assertEqual(item_missing_fields(state), [])
        self.assertEqual(
            checkout_missing_fields(state),
            ["contact_phone", "policy_accepted"],
        )

    def test_ski_ability_counts_must_match_people(self):
        state = {
            "service_type": "ski",
            "people_count": 3,
            "has_under_6": False,
            "ability_level_counts": {"no_exp": 2},
            "language": "zh",
            "equipment_option": "self_rent",
        }
        with self.assertRaisesRegex(ValueError, "加總"):
            validate_business_answers(state)

    def test_non_self_skiing_child_requires_one_to_one(self):
        state = {
            "service_type": "ski",
            "people_count": 2,
            "has_under_6": True,
            "under_7_can_self_ski": False,
            "ability_level_counts": {"no_exp": 2},
            "language": "zh",
            "equipment_option": "self_rent",
        }
        with self.assertRaisesRegex(ValueError, "一對一"):
            validate_business_answers(state)

    def test_high_impact_text_requires_explicit_words(self):
        self.assertTrue(has_explicit_order_confirmation("確認下單"))
        self.assertTrue(has_explicit_order_confirmation("請幫我下單，謝謝"))
        self.assertTrue(has_explicit_order_confirmation("我已閱讀取消政策，確認下單"))
        self.assertFalse(has_explicit_order_confirmation("好，可以"))
        self.assertFalse(has_explicit_order_confirmation("先不要下單"))
        self.assertTrue(has_explicit_policy_consent("我同意預約與取消政策"))
        self.assertFalse(has_explicit_policy_consent("同意"))
        self.assertFalse(has_explicit_policy_consent("好"))
        self.assertFalse(has_explicit_policy_consent("我不同意政策"))

    def test_empty_ability_counts_remains_missing(self):
        self.assertIn(
            "ability_level_counts",
            missing_fields({
                "service_type": "ski",
                "ability_level_counts": {},
            }),
        )

    def test_high_confidence_service_type_extraction(self):
        self.assertEqual(
            high_confidence_booking_updates("我要預約滑雪課程"),
            {"service_type": "ski"},
        )
        self.assertEqual(
            high_confidence_booking_updates("想預約滑雪攝影跟拍"),
            {"service_type": "photo"},
        )
        self.assertEqual(
            high_confidence_booking_updates("滑雪課程和攝影方案差在哪？"),
            {},
        )


class LineAdapterTests(SimpleTestCase):
    def test_signature_uses_raw_body_and_channel_secret(self):
        raw_body = b'{"events":[]}'
        secret = "test-secret"
        signature = base64.b64encode(
            hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
        ).decode("ascii")
        self.assertTrue(verify_line_signature(raw_body, signature, secret))
        self.assertFalse(
            verify_line_signature(b'{"events": []}', signature, secret)
        )

    def test_reply_client_uses_bearer_token_and_reply_endpoint(self):
        class FakeResponse:
            status_code = 200

        class FakeHTTPClient:
            def __init__(self):
                self.call = None

            def post(self, url, **kwargs):
                self.call = (url, kwargs)
                return FakeResponse()

        http_client = FakeHTTPClient()
        client = LineMessagingClient(
            access_token="test-access-token",
            timeout=7,
            http_client=http_client,
        )
        client.reply("test-reply-token", "您好")
        url, kwargs = http_client.call
        self.assertEqual(url, LineMessagingClient.REPLY_URL)
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer test-access-token",
        )
        self.assertEqual(kwargs["json"]["replyToken"], "test-reply-token")
        self.assertEqual(kwargs["json"]["messages"][0]["text"], "您好")
        self.assertEqual(kwargs["timeout"], 7)

    def test_reply_client_can_send_flex_message(self):
        class FakeResponse:
            status_code = 200

        class FakeHTTPClient:
            def __init__(self):
                self.call = None

            def post(self, url, **kwargs):
                self.call = (url, kwargs)
                return FakeResponse()

        flex_message = {
            "type": "flex",
            "altText": "下單前確認",
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [{"type": "text", "text": "確認資料"}],
                },
            },
        }
        http_client = FakeHTTPClient()
        client = LineMessagingClient(
            access_token="test-access-token",
            timeout=7,
            http_client=http_client,
        )

        client.reply(
            "test-reply-token",
            "文字備援",
            message=flex_message,
        )

        url, kwargs = http_client.call
        self.assertEqual(url, LineMessagingClient.REPLY_URL)
        self.assertEqual(kwargs["json"]["messages"], [flex_message])

    def test_push_client_uses_retry_key_and_accepts_safe_replay(self):
        retry_key = str(uuid.uuid4())

        class FakeResponse:
            status_code = 409
            headers = {"x-line-accepted-request-id": "accepted-request"}

        class FakeHTTPClient:
            def __init__(self):
                self.call = None

            def post(self, url, **kwargs):
                self.call = (url, kwargs)
                return FakeResponse()

        http_client = FakeHTTPClient()
        client = LineMessagingClient(
            access_token="test-access-token",
            timeout=7,
            http_client=http_client,
        )
        client.push(
            "U-test-customer",
            "正式回覆",
            retry_key=retry_key,
        )
        url, kwargs = http_client.call
        self.assertEqual(url, LineMessagingClient.PUSH_URL)
        self.assertEqual(kwargs["headers"]["X-Line-Retry-Key"], retry_key)
        self.assertEqual(kwargs["json"]["to"], "U-test-customer")
        self.assertEqual(kwargs["json"]["messages"][0]["text"], "正式回覆")

    def test_push_client_can_send_flex_message(self):
        retry_key = str(uuid.uuid4())

        class FakeResponse:
            status_code = 200
            headers = {}

        class FakeHTTPClient:
            def __init__(self):
                self.call = None

            def post(self, url, **kwargs):
                self.call = (url, kwargs)
                return FakeResponse()

        flex_message = {
            "type": "flex",
            "altText": "下單前確認",
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [{"type": "text", "text": "確認資料"}],
                },
            },
        }
        http_client = FakeHTTPClient()
        client = LineMessagingClient(
            access_token="test-access-token",
            timeout=7,
            http_client=http_client,
        )

        client.push(
            "U-test-customer",
            "文字備援",
            retry_key=retry_key,
            message=flex_message,
        )

        _, kwargs = http_client.call
        self.assertEqual(kwargs["json"]["messages"], [flex_message])

    def test_quote_flex_uses_authoritative_draft_and_masks_phone(self):
        draft = SimpleNamespace(
            status=ChatBookingDraft.STATUS_QUOTED,
            quote_hash="quote-hash",
            quote={
                "subtotal": 12000,
                "discount_total": 1000,
                "total": 11000,
            },
            quote_expires_at=timezone.now() + timedelta(minutes=15),
            cart=[{
                "serviceType": "ski",
                "resort": "tomamu",
                "resortName": "星野 Tomamu",
                "courseCategory": "單板 Snowboard",
                "peopleCount": 1,
                "language": "zh",
                "coachName": "不指定",
                "equipmentOption": "own_equipment",
                "courses": [{
                    "date": "2026-12-10",
                    "courseTypeName": "半天 3H",
                    "courseTemplateName": "基礎滑行",
                    "timeSlotStart": "09:00",
                    "timeSlotEnd": "12:00",
                }],
            }],
            contact={"name": "王小明", "phone": "0912345678"},
        )

        message = build_booking_confirmation_flex(draft)
        serialized = json.dumps(message, ensure_ascii=False)

        self.assertEqual(message["type"], "flex")
        self.assertIn("TWD 11,000", serialized)
        self.assertIn("末三碼 678", serialized)
        self.assertNotIn("0912345678", serialized)
        footer = message["contents"]["footer"]["contents"]
        self.assertEqual(footer[0]["action"]["text"], "確認下單")
        self.assertEqual(footer[1]["action"]["text"], "繼續新增")
        self.assertEqual(footer[2]["action"]["text"], "我要修改預約資料")

    def test_multi_item_quote_flex_uses_cart_carousel_and_summary(self):
        base_item = {
            "serviceType": "ski",
            "resort": "tomamu",
            "resortName": "星野 Tomamu",
            "courseCategory": "單板 Snowboard",
            "peopleCount": 1,
            "language": "zh",
            "coachName": "不指定",
            "equipmentOption": "own_equipment",
            "totalPrice": 11700,
            "courses": [{
                "date": "2026-12-10",
                "courseTypeName": "半天 3H",
                "courseTemplateName": "基礎滑行",
                "timeSlotStart": "09:00",
                "timeSlotEnd": "12:00",
            }],
        }
        second_item = deepcopy(base_item)
        second_item["courseCategory"] = "雙板 Ski"
        second_item["courses"][0]["date"] = "2026-12-11"
        draft = SimpleNamespace(
            status=ChatBookingDraft.STATUS_QUOTED,
            quote_hash="multi-quote",
            quote={
                "subtotal": 23400,
                "discount_total": 2340,
                "total": 21060,
                "item_subtotals": [11700, 11700],
                "item_discount_amounts": [1170, 1170],
            },
            quote_expires_at=timezone.now() + timedelta(minutes=15),
            cart=[base_item, second_item],
            contact={"name": "王小明", "phone": "0912345678"},
        )

        message = build_booking_confirmation_flex(draft)
        serialized = json.dumps(message, ensure_ascii=False)

        self.assertEqual(message["contents"]["type"], "carousel")
        self.assertEqual(len(message["contents"]["contents"]), 3)
        self.assertIn("購物車項目 1", serialized)
        self.assertIn("購物車項目 2", serialized)
        self.assertIn("整車下單確認", serialized)
        self.assertIn("TWD 21,060", serialized)
        self.assertIn("修改第 1 項", serialized)
        self.assertIn("刪除第 2 項", serialized)
        self.assertNotIn("0912345678", serialized)

    def test_unquoted_cart_flex_has_cart_actions_without_confirming_order(self):
        draft = SimpleNamespace(
            status=ChatBookingDraft.STATUS_DRAFT,
            cart=[{
                "serviceType": "ski",
                "resortName": "星野 Tomamu",
                "courseCategory": "單板 Snowboard",
                "peopleCount": 1,
                "language": "zh",
                "coachName": "不指定",
                "equipmentOption": "own_equipment",
                "totalPrice": 11700,
                "courses": [{
                    "date": "2026-12-10",
                    "courseTypeName": "半天 3H",
                    "courseTemplateName": "基礎滑行",
                    "timeSlotStart": "09:00",
                    "timeSlotEnd": "12:00",
                }],
            }],
        )

        message = build_booking_cart_flex(draft)
        serialized = json.dumps(message, ensure_ascii=False)

        self.assertEqual(message["contents"]["type"], "carousel")
        self.assertIn("我的預約購物車", serialized)
        self.assertIn('"text": "結帳"', serialized)
        self.assertIn('"text": "繼續新增"', serialized)
        self.assertIn('"text": "清空購物車"', serialized)
        self.assertNotIn('"text": "確認下單"', serialized)

    @override_settings(LINE_LOADING_SECONDS=60)
    def test_loading_client_uses_chat_id_and_configured_duration(self):
        class FakeResponse:
            status_code = 202

        class FakeHTTPClient:
            def __init__(self):
                self.call = None

            def post(self, url, **kwargs):
                self.call = (url, kwargs)
                return FakeResponse()

        http_client = FakeHTTPClient()
        client = LineMessagingClient(
            access_token="test-access-token",
            timeout=7,
            http_client=http_client,
        )
        client.start_loading("U-test-customer")
        url, kwargs = http_client.call
        self.assertEqual(url, LineMessagingClient.LOADING_URL)
        self.assertEqual(
            kwargs["json"],
            {
                "chatId": "U-test-customer",
                "loadingSeconds": 60,
            },
        )
        self.assertEqual(kwargs["timeout"], 7)


@override_settings(
    LINE_CHANNEL_SECRET="test-line-secret",
    LINE_CHANNEL_ACCESS_TOKEN="test-line-access-token",
    LINE_CLIENT_CODE="snowland-test",
    LINE_API_TIMEOUT_SECONDS=3,
    LINE_LOADING_SECONDS=60,
    LINE_SESSION_TTL_DAYS=30,
    LINE_WEBHOOK_MAX_BODY_BYTES=1024 * 1024,
)
class LineWebhookTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(
            name="SnowLand Test",
            internal_code="snowland-test",
        )
        self.url = "/booking/snowland-test/api/chat/line/webhook/"
        self.loading_patcher = patch(
            "chatbooking.line_webhook.LineMessagingClient.start_loading"
        )
        self.line_loading = self.loading_patcher.start()
        self.addCleanup(self.loading_patcher.stop)
        self.push_patcher = patch(
            "chatbooking.line_webhook.LineMessagingClient.push"
        )
        self.line_push = self.push_patcher.start()
        self.addCleanup(self.push_patcher.stop)

    def signed_post(self, payload, *, signature=None):
        raw_body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        valid_signature = base64.b64encode(
            hmac.new(
                b"test-line-secret",
                raw_body,
                hashlib.sha256,
            ).digest()
        ).decode("ascii")
        return self.client.post(
            self.url,
            data=raw_body,
            content_type="application/json",
            HTTP_X_LINE_SIGNATURE=(
                valid_signature if signature is None else signature
            ),
        )

    def text_payload(self):
        return {
            "destination": "test-bot-user-id",
            "events": [{
                "type": "message",
                "mode": "active",
                "timestamp": 1784545200000,
                "source": {
                    "type": "user",
                    "userId": "U-test-customer",
                },
                "webhookEventId": "line-event-001",
                "deliveryContext": {"isRedelivery": False},
                "replyToken": "temporary-reply-token",
                "message": {
                    "id": "line-message-001",
                    "type": "text",
                    "text": "我要預約滑雪課程",
                },
            }],
        }

    def test_verify_request_with_empty_events_returns_200(self):
        response = self.signed_post({"events": []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["processed"], 0)
        self.assertEqual(ChatBookingEvent.objects.count(), 0)

    def test_invalid_signature_is_rejected_before_event_creation(self):
        response = self.signed_post(self.text_payload(), signature="invalid")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(ChatBookingEvent.objects.count(), 0)
        self.assertEqual(ChatBookingSession.objects.count(), 0)

    @override_settings(LINE_CHANNEL_SECRET="")
    def test_missing_channel_secret_returns_503(self):
        response = self.signed_post({"events": []})
        self.assertEqual(response.status_code, 503)

    def test_text_event_creates_line_session_runs_ai_and_replies(self):
        fake_reply = AIReply(
            content="好的，請問想去哪一個雪場？",
            message_id=999,
            model="fake",
        )
        with (
            patch(
                "chatbooking.line_webhook.run_ai_turn",
                return_value=fake_reply,
            ) as ai_turn,
            patch(
                "chatbooking.line_webhook.LineMessagingClient.reply",
            ) as line_reply,
        ):
            response = self.signed_post(self.text_payload())

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["processed"], 1)
        session = ChatBookingSession.objects.get()
        self.assertEqual(session.client, self.tenant)
        self.assertEqual(session.channel, ChatBookingSession.CHANNEL_LINE)
        self.assertEqual(session.external_user_id, "U-test-customer")
        inbound = ChatBookingMessage.objects.get(
            session=session,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
        )
        self.assertEqual(inbound.content, "我要預約滑雪課程")
        self.assertNotIn("replyToken", inbound.metadata)
        self.assertNotIn(
            "temporary-reply-token",
            json.dumps(inbound.metadata, ensure_ascii=False),
        )
        event = ChatBookingEvent.objects.get()
        self.assertEqual(event.status, ChatBookingEvent.STATUS_PROCESSED)
        self.assertEqual(event.session, session)
        self.assertNotIn("temporary-reply-token", event.payload_hash)
        self.assertNotIn("temporary-reply-token", event.error)
        ai_turn.assert_called_once_with(session, inbound)
        line_reply.assert_called_once_with(
            "temporary-reply-token",
            "好的，請問想去哪一個雪場？",
        )
        self.line_push.assert_not_called()
        self.assertIsNone(event.acknowledged_at)
        self.assertIsNotNone(event.response_sent_at)
        self.line_loading.assert_called_once_with("U-test-customer")

    def test_successful_quote_is_replied_as_flex_confirmation(self):
        def create_quote_reply(session, inbound):
            session.status = ChatBookingSession.STATUS_AWAITING_CONFIRMATION
            session.current_step = "confirmation"
            session.save(update_fields=["status", "current_step", "updated_at"])
            draft = ChatBookingDraft.objects.get(session=session)
            draft.status = ChatBookingDraft.STATUS_QUOTED
            draft.quote_hash = "quote-hash"
            draft.quote_expires_at = timezone.now() + timedelta(minutes=15)
            draft.quote = {
                "subtotal": 12000,
                "discount_total": 0,
                "total": 12000,
            }
            draft.cart = [{
                "serviceType": "ski",
                "resort": "tomamu",
                "resortName": "星野 Tomamu",
                "courseCategory": "單板 Snowboard",
                "peopleCount": 1,
                "language": "zh",
                "coachName": "不指定",
                "equipmentOption": "own_equipment",
                "courses": [{
                    "date": "2026-12-10",
                    "courseTypeName": "半天 3H",
                    "courseTemplateName": "基礎滑行",
                    "timeSlotStart": "09:00",
                    "timeSlotEnd": "12:00",
                }],
            }]
            draft.contact = {"name": "王小明", "phone": "0912345678"}
            draft.save()
            outbound = ChatBookingMessage.objects.create(
                session=session,
                direction=ChatBookingMessage.DIRECTION_OUTBOUND,
                sender_type=ChatBookingMessage.SENDER_AI,
                content="資料齊全，請確認下單。",
                metadata={"quote_hash_at_reply": draft.quote_hash},
            )
            return AIReply(
                content=outbound.content,
                message_id=outbound.id,
                model="fake",
                tool_names=["create_booking_quote"],
            )

        with (
            patch(
                "chatbooking.line_webhook.run_ai_turn",
                side_effect=create_quote_reply,
            ),
            patch(
                "chatbooking.line_webhook.LineMessagingClient.reply",
            ) as line_reply,
        ):
            response = self.signed_post(self.text_payload())

        self.assertEqual(response.status_code, 200, response.content)
        reply_args = line_reply.call_args
        self.assertEqual(
            reply_args.args,
            ("temporary-reply-token", "資料齊全，請確認下單。"),
        )
        flex_message = reply_args.kwargs["message"]
        self.assertEqual(flex_message["type"], "flex")
        self.assertIn("TWD 12,000", json.dumps(flex_message, ensure_ascii=False))
        self.line_push.assert_not_called()
        outbound = ChatBookingMessage.objects.filter(
            sender_type=ChatBookingMessage.SENDER_AI,
        ).get()
        self.assertEqual(
            outbound.metadata["line_message_type"],
            "flex_quote_confirmation",
        )

    def test_added_cart_item_is_replied_as_cart_flex(self):
        def add_cart_reply(session, inbound):
            draft = ChatBookingDraft.objects.get(session=session)
            draft.status = ChatBookingDraft.STATUS_DRAFT
            draft.cart = [{
                "serviceType": "ski",
                "resort": "tomamu",
                "resortName": "星野 Tomamu",
                "courseCategory": "單板 Snowboard",
                "peopleCount": 1,
                "language": "zh",
                "coachName": "不指定",
                "equipmentOption": "own_equipment",
                "totalPrice": 11700,
                "courses": [{
                    "date": "2026-12-10",
                    "courseTypeName": "半天 3H",
                    "courseTemplateName": "基礎滑行",
                    "timeSlotStart": "09:00",
                    "timeSlotEnd": "12:00",
                }],
            }]
            draft.save()
            outbound = ChatBookingMessage.objects.create(
                session=session,
                direction=ChatBookingMessage.DIRECTION_OUTBOUND,
                sender_type=ChatBookingMessage.SENDER_AI,
                content="已加入購物車，請選擇繼續新增或結帳。",
            )
            return AIReply(
                content=outbound.content,
                message_id=outbound.id,
                model="fake",
                tool_names=["add_booking_to_cart"],
            )

        with (
            patch(
                "chatbooking.line_webhook.run_ai_turn",
                side_effect=add_cart_reply,
            ),
            patch(
                "chatbooking.line_webhook.LineMessagingClient.reply",
            ) as line_reply,
        ):
            response = self.signed_post(self.text_payload())

        self.assertEqual(response.status_code, 200, response.content)
        reply_kwargs = line_reply.call_args.kwargs
        self.assertEqual(reply_kwargs["message"]["type"], "flex")
        self.assertIn(
            "我的預約購物車",
            json.dumps(reply_kwargs["message"], ensure_ascii=False),
        )
        self.line_push.assert_not_called()
        outbound = ChatBookingMessage.objects.filter(
            sender_type=ChatBookingMessage.SENDER_AI,
        ).get()
        self.assertEqual(
            outbound.metadata["line_message_type"],
            "flex_booking_cart",
        )
        self.assertEqual(outbound.metadata["line_cart_item_count"], 1)

    def test_new_booking_after_committed_order_opens_fresh_session(self):
        old_session = ChatBookingSession.objects.create(
            client=self.tenant,
            channel=ChatBookingSession.CHANNEL_LINE,
            external_user_id="U-test-customer",
            status=ChatBookingSession.STATUS_ESCALATED,
            current_step="human_support",
            access_token_hash="old-hash",
            ai_enabled=False,
            expires_at=timezone.now() + timedelta(days=1),
        )
        ChatBookingDraft.objects.create(
            session=old_session,
            status=ChatBookingDraft.STATUS_COMMITTED,
            quote={"total": 10530},
            quote_hash="old-quote",
            reservation_group_ids=[101],
        )
        ChatBookingHandoff.objects.create(
            session=old_session,
            status=ChatBookingHandoff.STATUS_REQUESTED,
            reason="誤判為改期",
        )
        payload = self.text_payload()
        payload["events"][0]["message"]["text"] = "我要新預約"
        fake_reply = AIReply(
            content="好的，這會建立為另一筆新預約。",
            message_id=999,
            model="fake",
        )
        with (
            patch(
                "chatbooking.line_webhook.run_ai_turn",
                return_value=fake_reply,
            ) as ai_turn,
            patch(
                "chatbooking.line_webhook.LineMessagingClient.reply",
            ),
        ):
            response = self.signed_post(payload)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(ChatBookingSession.objects.count(), 2)
        new_session = ChatBookingSession.objects.exclude(pk=old_session.pk).get()
        self.assertTrue(new_session.ai_enabled)
        self.assertEqual(new_session.status, ChatBookingSession.STATUS_ACTIVE)
        inbound = ChatBookingMessage.objects.get(
            session=new_session,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
        )
        ai_turn.assert_called_once_with(new_session, inbound)
        old_session.refresh_from_db()
        self.assertEqual(old_session.status, ChatBookingSession.STATUS_ESCALATED)
        self.assertFalse(old_session.ai_enabled)

    def test_escalated_session_saves_customer_message_without_repeating_bot_reply(self):
        session = ChatBookingSession.objects.create(
            client=self.tenant,
            channel=ChatBookingSession.CHANNEL_LINE,
            external_user_id="U-test-customer",
            status=ChatBookingSession.STATUS_ESCALATED,
            current_step="human_support",
            access_token_hash="handoff-hash",
            ai_enabled=False,
            expires_at=timezone.now() + timedelta(days=1),
        )
        ChatBookingDraft.objects.create(session=session)
        ChatBookingHandoff.objects.create(
            session=session,
            status=ChatBookingHandoff.STATUS_ASSIGNED,
            reason="客人要求真人客服",
        )
        with (
            patch("chatbooking.line_webhook.run_ai_turn") as ai_turn,
            patch("chatbooking.line_webhook.LineMessagingClient.reply") as line_reply,
        ):
            response = self.signed_post(self.text_payload())

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["processed"], 1)
        inbound = ChatBookingMessage.objects.get(
            session=session,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
        )
        self.assertEqual(inbound.content, "我要預約滑雪課程")
        event = ChatBookingEvent.objects.get()
        self.assertEqual(event.status, ChatBookingEvent.STATUS_PROCESSED)
        self.assertIsNone(event.acknowledged_at)
        self.assertIsNone(event.response_sent_at)
        ai_turn.assert_not_called()
        line_reply.assert_not_called()
        self.line_push.assert_not_called()
        self.line_loading.assert_not_called()

    def test_continue_adding_keeps_latest_uncommitted_cart_session(self):
        session = ChatBookingSession.objects.create(
            client=self.tenant,
            channel=ChatBookingSession.CHANNEL_LINE,
            external_user_id="U-test-customer",
            status=ChatBookingSession.STATUS_ACTIVE,
            current_step="cart_action",
            access_token_hash="cart-hash",
            ai_enabled=True,
            expires_at=timezone.now() + timedelta(days=1),
        )
        ChatBookingDraft.objects.create(
            session=session,
            status=ChatBookingDraft.STATUS_DRAFT,
            cart=[{"id": "cart-item-1", "_chat_saved": True}],
        )
        payload = self.text_payload()
        payload["events"][0]["message"]["text"] = "繼續新增"
        fake_reply = AIReply(
            content="好的，下一項想預約滑雪課程還是攝影？",
            message_id=999,
            model="fake",
        )
        with (
            patch(
                "chatbooking.line_webhook.run_ai_turn",
                return_value=fake_reply,
            ) as ai_turn,
            patch(
                "chatbooking.line_webhook.LineMessagingClient.reply",
            ),
        ):
            response = self.signed_post(payload)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(ChatBookingSession.objects.count(), 1)
        inbound = ChatBookingMessage.objects.get(
            session=session,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
        )
        ai_turn.assert_called_once_with(session, inbound)

    def test_explicit_fresh_order_does_not_reuse_uncommitted_cart(self):
        old_cart_session = ChatBookingSession.objects.create(
            client=self.tenant,
            channel=ChatBookingSession.CHANNEL_LINE,
            external_user_id="U-test-customer",
            status=ChatBookingSession.STATUS_ACTIVE,
            current_step="cart_action",
            access_token_hash="cart-hash",
            ai_enabled=True,
            expires_at=timezone.now() + timedelta(days=1),
        )
        ChatBookingDraft.objects.create(
            session=old_cart_session,
            status=ChatBookingDraft.STATUS_DRAFT,
            cart=[{"id": "cart-item-1", "_chat_saved": True}],
        )
        payload = self.text_payload()
        payload["events"][0]["message"]["text"] = "我要新下一單"
        fake_reply = AIReply(
            content="好的，已建立新的預約購物車。",
            message_id=999,
            model="fake",
        )
        with (
            patch(
                "chatbooking.line_webhook.run_ai_turn",
                return_value=fake_reply,
            ) as ai_turn,
            patch(
                "chatbooking.line_webhook.LineMessagingClient.reply",
            ),
        ):
            response = self.signed_post(payload)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(ChatBookingSession.objects.count(), 2)
        new_session = ChatBookingSession.objects.exclude(pk=old_cart_session.pk).get()
        inbound = ChatBookingMessage.objects.get(
            session=new_session,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
        )
        ai_turn.assert_called_once_with(new_session, inbound)
        old_cart_session.refresh_from_db()
        self.assertEqual(old_cart_session.status, ChatBookingSession.STATUS_ACTIVE)
        self.assertEqual(
            len(ChatBookingDraft.objects.get(session=old_cart_session).cart),
            1,
        )

    def test_redelivery_does_not_run_ai_or_reply_twice(self):
        fake_reply = AIReply(content="請選擇雪場", message_id=999, model="fake")
        payload = self.text_payload()
        with (
            patch(
                "chatbooking.line_webhook.run_ai_turn",
                return_value=fake_reply,
            ) as ai_turn,
            patch(
                "chatbooking.line_webhook.LineMessagingClient.reply",
            ) as line_reply,
        ):
            first = self.signed_post(payload)
            payload["events"][0]["deliveryContext"]["isRedelivery"] = True
            second = self.signed_post(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["duplicate"], 1)
        self.assertEqual(ChatBookingEvent.objects.count(), 1)
        self.assertEqual(
            ChatBookingMessage.objects.filter(
                sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            ).count(),
            1,
        )
        self.assertEqual(ai_turn.call_count, 1)
        self.assertEqual(line_reply.call_count, 1)
        self.line_push.assert_not_called()
        self.assertEqual(self.line_loading.call_count, 1)

    def test_group_message_is_ignored_to_protect_booking_privacy(self):
        payload = self.text_payload()
        payload["events"][0]["source"] = {
            "type": "group",
            "groupId": "test-group",
            "userId": "U-test-customer",
        }
        with patch(
            "chatbooking.line_webhook.LineMessagingClient.reply",
        ) as line_reply:
            response = self.signed_post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ignored"], 1)
        self.assertEqual(ChatBookingSession.objects.count(), 0)
        line_reply.assert_not_called()
        self.line_push.assert_not_called()
        self.line_loading.assert_not_called()

    def test_loading_failure_does_not_block_ai_reply(self):
        self.line_loading.side_effect = LineAPIError(
            "LINE loading API 回傳 HTTP 500"
        )
        fake_reply = AIReply(content="請選擇課程", message_id=999, model="fake")
        with (
            patch(
                "chatbooking.line_webhook.run_ai_turn",
                return_value=fake_reply,
            ),
            patch(
                "chatbooking.line_webhook.LineMessagingClient.reply",
            ) as line_reply,
        ):
            response = self.signed_post(self.text_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["processed"], 1)
        line_reply.assert_called_once_with(
            "temporary-reply-token",
            "請選擇課程",
        )
        self.line_push.assert_not_called()

    def test_reply_failure_falls_back_to_push(self):
        fake_reply = AIReply(content="請稍候", message_id=999, model="fake")
        with (
            patch(
                "chatbooking.line_webhook.run_ai_turn",
                return_value=fake_reply,
            ),
            patch(
                "chatbooking.line_webhook.LineMessagingClient.reply",
                side_effect=LineAPIError("LINE reply API 回傳 HTTP 500"),
            ),
        ):
            response = self.signed_post(self.text_payload())
        self.assertEqual(response.status_code, 200)
        event = ChatBookingEvent.objects.get()
        self.assertEqual(event.status, ChatBookingEvent.STATUS_PROCESSED)
        self.assertEqual(event.error, "")
        self.assertIsNone(event.acknowledged_at)
        self.assertIsNotNone(event.response_sent_at)
        push_args = self.line_push.call_args
        self.assertEqual(push_args.args, ("U-test-customer", "請稍候"))
        uuid.UUID(push_args.kwargs["retry_key"])

    def test_fallback_push_failure_retries_with_same_key(self):
        fake_reply = AIReply(content="請選擇雪場", message_id=999, model="fake")
        self.line_push.side_effect = LineAPIError(
            "LINE push API 回傳 HTTP 500"
        )
        payload = self.text_payload()
        with (
            patch(
                "chatbooking.line_webhook.run_ai_turn",
                return_value=fake_reply,
            ),
            patch(
                "chatbooking.line_webhook.LineMessagingClient.reply",
                side_effect=LineAPIError("LINE reply API 回傳 HTTP 400"),
            ) as line_reply,
        ):
            first = self.signed_post(payload)
            self.line_push.side_effect = None
            payload["events"][0]["deliveryContext"]["isRedelivery"] = True
            payload["events"][0]["replyToken"] = "redelivery-reply-token"
            second = self.signed_post(payload)

        self.assertEqual(first.status_code, 502)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(line_reply.call_count, 2)
        self.assertEqual(self.line_push.call_count, 2)
        event = ChatBookingEvent.objects.get()
        self.assertEqual(event.status, ChatBookingEvent.STATUS_PROCESSED)
        self.assertIsNone(event.acknowledged_at)
        self.assertIsNotNone(event.response_sent_at)
        retry_keys = [
            call.kwargs["retry_key"]
            for call in self.line_push.call_args_list
        ]
        self.assertEqual(retry_keys[0], retry_keys[1])


@override_settings(LINE_CHANNEL_ACCESS_TOKEN="test-line-token")
class ChatSupportAdminAPITests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(
            name="SnowLand Test",
            internal_code="snowland-test",
        )
        self.other_tenant = Client.objects.create(
            name="Other Tenant",
            internal_code="other-tenant",
        )
        self.manager = User.objects.create_user(
            username="support-manager",
            email="support@example.com",
            password="test-password",
        )
        self.manager.userprofile.is_manager = True
        self.manager.userprofile.admin_permissions = ["chat_support"]
        self.manager.userprofile.save(
            update_fields=["is_manager", "admin_permissions"],
        )
        self.client.force_login(self.manager)
        self.session = ChatBookingSession.objects.create(
            client=self.tenant,
            channel=ChatBookingSession.CHANNEL_LINE,
            external_user_id="U-support-customer",
            status=ChatBookingSession.STATUS_ESCALATED,
            current_step="human_support",
            access_token_hash="support-hash",
            ai_enabled=False,
            slot_values={
                "service_type": "ski",
                "contact_name": "王小明",
                "contact_phone": "0912345678",
            },
            expires_at=timezone.now() + timedelta(days=1),
        )
        ChatBookingDraft.objects.create(session=self.session)
        ChatBookingHandoff.objects.create(
            session=self.session,
            status=ChatBookingHandoff.STATUS_REQUESTED,
            reason="客人要求真人客服",
        )
        ChatBookingMessage.objects.create(
            session=self.session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="請真人幫我確認改期",
        )
        self.base = "/api/admin/snowland-test/chat-support/"

    def test_list_and_detail_return_tenant_line_conversations(self):
        hidden = ChatBookingSession.objects.create(
            client=self.other_tenant,
            channel=ChatBookingSession.CHANNEL_LINE,
            external_user_id="U-other-customer",
            access_token_hash="other-hash",
            expires_at=timezone.now() + timedelta(days=1),
        )
        ChatBookingDraft.objects.create(session=hidden)

        response = self.client.get(f"{self.base}?queue=waiting")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["data"]
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["list"][0]["id"], str(self.session.pk))
        self.assertEqual(payload["list"][0]["contact_name"], "王小明")
        self.assertEqual(
            payload["list"][0]["handoff"]["status"],
            ChatBookingHandoff.STATUS_REQUESTED,
        )

        detail = self.client.get(f"{self.base}{self.session.pk}/")
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(
            detail.json()["data"]["messages"][-1]["content"],
            "請真人幫我確認改期",
        )

    def test_agent_reply_claims_session_pushes_line_and_saves_audit_message(self):
        client_message_id = str(uuid.uuid4())
        with patch("chatbooking.admin_views.LineMessagingClient.push") as line_push:
            response = self.client.post(
                f"{self.base}{self.session.pk}/reply/",
                data=json.dumps({
                    "content": "您好，我來協助確認改期。",
                    "client_message_id": client_message_id,
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        line_push.assert_called_once()
        self.assertEqual(
            line_push.call_args.args,
            ("U-support-customer", "您好，我來協助確認改期。"),
        )
        uuid.UUID(line_push.call_args.kwargs["retry_key"])
        self.session.refresh_from_db()
        self.assertFalse(self.session.ai_enabled)
        self.assertEqual(self.session.status, ChatBookingSession.STATUS_ESCALATED)
        handoff = ChatBookingHandoff.objects.get(session=self.session)
        self.assertEqual(handoff.status, ChatBookingHandoff.STATUS_ASSIGNED)
        self.assertEqual(handoff.assigned_to, self.manager)
        outbound = ChatBookingMessage.objects.get(
            session=self.session,
            sender_type=ChatBookingMessage.SENDER_AGENT,
        )
        self.assertEqual(outbound.content, "您好，我來協助確認改期。")
        self.assertEqual(outbound.metadata["sent_by_user_id"], self.manager.id)
        self.assertEqual(outbound.metadata["delivery_status"], "sent")

    def test_duplicate_agent_reply_is_idempotent(self):
        client_message_id = str(uuid.uuid4())
        body = json.dumps({
            "content": "這是一則只應傳送一次的訊息。",
            "client_message_id": client_message_id,
        })
        with patch("chatbooking.admin_views.LineMessagingClient.push") as line_push:
            first = self.client.post(
                f"{self.base}{self.session.pk}/reply/",
                data=body,
                content_type="application/json",
            )
            second = self.client.post(
                f"{self.base}{self.session.pk}/reply/",
                data=body,
                content_type="application/json",
            )

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertTrue(second.json()["data"]["replayed"])
        self.assertEqual(line_push.call_count, 1)
        self.assertEqual(
            ChatBookingMessage.objects.filter(
                session=self.session,
                sender_type=ChatBookingMessage.SENDER_AGENT,
            ).count(),
            1,
        )

    def test_resolve_can_restore_ai_at_saved_booking_step(self):
        claim = self.client.post(f"{self.base}{self.session.pk}/claim/", data={})
        self.assertEqual(claim.status_code, 200, claim.content)

        response = self.client.post(
            f"{self.base}{self.session.pk}/resolve/",
            data=json.dumps({"resume_ai": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.session.refresh_from_db()
        self.assertTrue(self.session.ai_enabled)
        self.assertEqual(self.session.status, ChatBookingSession.STATUS_ACTIVE)
        self.assertEqual(self.session.current_step, "category_id")
        handoff = ChatBookingHandoff.objects.get(session=self.session)
        self.assertEqual(handoff.status, ChatBookingHandoff.STATUS_RESOLVED)
        self.assertIsNotNone(handoff.resolved_at)
        self.assertTrue(
            ChatBookingMessage.objects.filter(
                session=self.session,
                sender_type=ChatBookingMessage.SENDER_SYSTEM,
                content="真人客服已結案，AI 客服已恢復",
            ).exists()
        )


class ChatBookingSessionAPITests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name="SnowLand Test", internal_code="snowland-test")
        self.base = "/booking/snowland-test/api/chat/sessions/"

    def create_session(self):
        response = self.client.post(
            self.base,
            data=json.dumps({"service_type": "ski"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        return payload["session"], payload["session_token"]

    def test_session_token_is_required_and_not_stored_raw(self):
        session_data, raw_token = self.create_session()
        session = ChatBookingSession.objects.get(pk=session_data["id"])
        self.assertNotEqual(session.access_token_hash, raw_token)
        response = self.client.get(f'{self.base}{session.pk}/')
        self.assertEqual(response.status_code, 401)
        response = self.client.get(
            f'{self.base}{session.pk}/',
            HTTP_X_CHAT_SESSION_TOKEN=raw_token,
        )
        self.assertEqual(response.status_code, 200)

    def test_state_uses_optimistic_version_and_invalidates_quote(self):
        session_data, raw_token = self.create_session()
        url = f'{self.base}{session_data["id"]}/state/'
        response = self.client.patch(
            url,
            data=json.dumps({
                "state_version": session_data["state_version"],
                "updates": {"contact_phone": "0912345678"},
            }),
            content_type="application/json",
            HTTP_X_CHAT_SESSION_TOKEN=raw_token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session"]["state_version"], 2)
        stale = self.client.patch(
            url,
            data=json.dumps({
                "state_version": 1,
                "updates": {"contact_name": "測試"},
            }),
            content_type="application/json",
            HTTP_X_CHAT_SESSION_TOKEN=raw_token,
        )
        self.assertEqual(stale.status_code, 409)

    def test_external_message_id_is_idempotent(self):
        session_data, raw_token = self.create_session()
        url = f'{self.base}{session_data["id"]}/messages/'
        body = json.dumps({"content": "我要預約", "external_message_id": "event-123"})
        fake_reply = AIReply(content="您好，想預約哪一種服務？", message_id=999, model="fake")
        with patch("chatbooking.views.run_ai_turn", return_value=fake_reply):
            first = self.client.post(
                url,
                data=body,
                content_type="application/json",
                HTTP_X_CHAT_SESSION_TOKEN=raw_token,
            )
            second = self.client.post(
                url,
                data=body,
                content_type="application/json",
                HTTP_X_CHAT_SESSION_TOKEN=raw_token,
            )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])
        self.assertEqual(
            ChatBookingMessage.objects.filter(external_message_key__endswith="event-123").count(),
            1,
        )

    @override_settings(OPENAI_API_KEY="")
    def test_message_endpoint_reports_missing_openai_configuration(self):
        session_data, raw_token = self.create_session()
        response = self.client.post(
            f'{self.base}{session_data["id"]}/messages/',
            data=json.dumps({"content": "我要預約"}),
            content_type="application/json",
            HTTP_X_CHAT_SESSION_TOKEN=raw_token,
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "openai_not_configured")
        self.assertEqual(ChatBookingMessage.objects.filter(
            session_id=session_data["id"],
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
        ).count(), 1)

    def test_ai_cannot_accept_policy_on_ambiguous_message(self):
        session_data, _ = self.create_session()
        session = ChatBookingSession.objects.get(pk=session_data["id"])
        inbound = ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="好",
        )
        result = BookingToolExecutor(session, inbound).execute(
            "update_booking_details",
            {"policy_accepted": True},
            "policy-call-1",
        )
        self.assertFalse(result["ok"])
        session.refresh_from_db()
        self.assertNotIn("policy_accepted", session.slot_values)

    def test_ai_cannot_quote_before_an_item_is_in_the_cart(self):
        session_data, _ = self.create_session()
        session = ChatBookingSession.objects.get(pk=session_data["id"])
        session.slot_values["policy_accepted"] = True
        session.save(update_fields=["slot_values", "updated_at"])
        inbound = ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="結帳",
        )

        result = BookingToolExecutor(session, inbound).execute(
            "create_booking_quote",
            {},
            "quote-empty-cart",
        )

        self.assertFalse(result["ok"])
        self.assertIn("購物車目前沒有項目", result["error"])

    def test_additional_booking_request_cannot_be_misrouted_to_human(self):
        session_data, _ = self.create_session()
        session = ChatBookingSession.objects.get(pk=session_data["id"])
        inbound = ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="不需要真人客服，你直接幫我新增一筆預約",
        )

        result = BookingToolExecutor(session, inbound).execute(
            "request_human_support",
            {"reason": "新增另一筆預約"},
            "no-false-handoff",
        )

        self.assertFalse(result["ok"])
        self.assertFalse(ChatBookingHandoff.objects.filter(session=session).exists())
        session.refresh_from_db()
        self.assertTrue(session.ai_enabled)

    def test_short_policy_consent_requires_previous_policy_question(self):
        session_data, _ = self.create_session()
        session = ChatBookingSession.objects.get(pk=session_data["id"])
        ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_OUTBOUND,
            sender_type=ChatBookingMessage.SENDER_AI,
            content="請問你是否同意預約與取消政策？",
        )
        inbound = ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="同意",
        )
        result = BookingToolExecutor(session, inbound).execute(
            "update_booking_details",
            {"policy_accepted": True},
            "policy-call-2",
        )
        self.assertTrue(result["ok"], result)
        session.refresh_from_db()
        self.assertTrue(session.slot_values["policy_accepted"])

    def test_knowledge_search_only_returns_visible_same_tenant_content(self):
        session_data, _ = self.create_session()
        session = ChatBookingSession.objects.get(pk=session_data["id"])
        SiteContent.objects.create(
            client=self.tenant,
            content_type="faq",
            location_key="faq.cancellation",
            title="取消政策",
            body="取消與退款依提出時間處理。",
            status="active",
        )
        SiteContent.objects.create(
            client=self.tenant,
            content_type="faq",
            location_key="faq.hidden",
            title="隱藏取消說明",
            body="不可公開",
            status="hidden",
        )
        other = Client.objects.create(name="Other", internal_code="other")
        SiteContent.objects.create(
            client=other,
            content_type="faq",
            location_key="faq.cancellation",
            title="取消政策",
            body="其他租戶內容",
            status="active",
        )
        inbound = ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="請問取消政策怎麼算？",
        )
        result = BookingToolExecutor(session, inbound).execute(
            "search_customer_knowledge",
            {"query": inbound.content, "content_type": "faq"},
            "knowledge-call-1",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["title"], "取消政策")

    def test_course_catalog_returns_active_tenant_courses(self):
        session_data, _ = self.create_session()
        session = ChatBookingSession.objects.get(pk=session_data["id"])
        resort = Resorts.objects.create(
            client=self.tenant,
            name="TestResort",
            display_name="測試雪場",
        )
        category = CourseCategory.objects.create(
            client=self.tenant,
            name="單板 Snowboard",
            service_type="ski",
        )
        course_type = CourseType.objects.create(
            category=category,
            name="半天課程",
        )
        template = CourseTemplate.objects.create(
            course_type=course_type,
            name="基礎滑行",
            duration_hours=3,
            max_capacity=6,
        )
        template.resorts.add(resort)
        inbound = ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="你們有哪些課程？",
        )
        result = BookingToolExecutor(session, inbound).execute(
            "get_course_catalog",
            {"service_type": None, "category_id": None, "resort": None},
            "catalog-call-1",
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["catalog"]["category_count"], 1)
        self.assertEqual(
            result["catalog"]["categories"][0]["course_types"][0]["templates"][0]["name"],
            "基礎滑行",
        )

    def test_ai_cannot_confirm_quote_created_in_same_customer_turn(self):
        session_data, _ = self.create_session()
        session = ChatBookingSession.objects.get(pk=session_data["id"])
        inbound = ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="確認下單",
        )
        session.slot_values["policy_accepted"] = True
        session.save(update_fields=["slot_values", "updated_at"])
        draft = ChatBookingDraft.objects.get(session=session)
        draft.status = ChatBookingDraft.STATUS_QUOTED
        draft.quote = {"total": 10000, "currency": "TWD"}
        draft.quote_hash = "test-hash"
        draft.quote_expires_at = timezone.now() + timedelta(minutes=15)
        draft.save()
        result = BookingToolExecutor(session, inbound).execute(
            "confirm_booking",
            {"confirmed": True, "confirmation_text": "確認下單"},
            "confirm-call-1",
        )
        self.assertFalse(result["ok"])
        self.assertIn("看過本次報價", result["error"])

    def test_handoff_turns_off_ai(self):
        session_data, raw_token = self.create_session()
        response = self.client.post(
            f'{self.base}{session_data["id"]}/handoff/',
            data=json.dumps({"reason": "客人要求真人"}),
            content_type="application/json",
            HTTP_X_CHAT_SESSION_TOKEN=raw_token,
        )
        self.assertEqual(response.status_code, 200)
        session = ChatBookingSession.objects.get(pk=session_data["id"])
        self.assertFalse(session.ai_enabled)
        self.assertEqual(session.status, ChatBookingSession.STATUS_ESCALATED)
        self.assertTrue(ChatBookingHandoff.objects.filter(session=session).exists())

    def test_static_service_options_are_available(self):
        session_data, raw_token = self.create_session()
        response = self.client.get(
            f'{self.base}{session_data["id"]}/options/?field=service_type',
            HTTP_X_CHAT_SESSION_TOKEN=raw_token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["value"] for item in response.json()["options"]],
            ["ski", "photo"],
        )

    def test_confirm_rejects_invalid_state_version_without_server_error(self):
        session_data, raw_token = self.create_session()
        response = self.client.post(
            f'{self.base}{session_data["id"]}/confirm/',
            data=json.dumps({
                "confirmed": True,
                "state_version": "not-a-number",
                "quote_hash": "not-a-quote",
            }),
            content_type="application/json",
            HTTP_X_CHAT_SESSION_TOKEN=raw_token,
            HTTP_IDEMPOTENCY_KEY="invalid-state-version",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("格式錯誤", response.json()["error"])


class FakeOpenAIProvider:
    model = "fake-model"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class ChatBookingAIOrchestratorTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name="SnowLand Test", internal_code="snowland-test")
        self.session = ChatBookingSession.objects.create(
            client=self.tenant,
            channel=ChatBookingSession.CHANNEL_API,
            slot_values={"service_type": "ski"},
            current_step="category_id",
            access_token_hash="hash",
            expires_at=timezone.now() + timedelta(days=1),
        )
        ChatBookingDraft.objects.create(session=self.session)

    def test_first_line_reply_marks_new_booking_cart(self):
        self.session.channel = ChatBookingSession.CHANNEL_LINE
        self.session.slot_values = {}
        self.session.current_step = "service_type"
        self.session.save(update_fields=["channel", "slot_values", "current_step", "updated_at"])
        inbound = ChatBookingMessage.objects.create(
            session=self.session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="我要新預約",
        )
        provider = FakeOpenAIProvider([{
            "id": "resp-new-cart",
            "model": "fake-model",
            "output": [],
            "output_text": "好的，請問要預約滑雪課程還是滑雪攝影？",
        }])

        reply = run_ai_turn(self.session, inbound, provider=provider)

        self.assertEqual(
            reply.content,
            "已建立新的預約購物車（目前 0 項）。\n\n"
            "好的，請問要預約滑雪課程還是滑雪攝影？",
        )
        outbound = ChatBookingMessage.objects.get(pk=reply.message_id)
        self.assertEqual(outbound.content, reply.content)

    def test_tool_loop_updates_state_and_saves_ai_reply_locally(self):
        inbound = ChatBookingMessage.objects.create(
            session=self.session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="我的電話是 0912345678",
        )
        updates = {key: None for key in UPDATE_PROPERTIES}
        updates["contact_phone"] = "0912345678"
        provider = FakeOpenAIProvider([
            {
                "id": "resp-tool",
                "model": "fake-model",
                "output": [{
                    "type": "function_call",
                    "call_id": "call-update-1",
                    "name": "update_booking_details",
                    "arguments": json.dumps(updates),
                }],
                "output_text": "",
                "usage": {"input_tokens": 100, "output_tokens": 20},
            },
            {
                "id": "resp-final",
                "model": "fake-model",
                "output": [],
                "output_text": "電話已記下，請問想去哪一個雪場？",
                "usage": {"input_tokens": 140, "output_tokens": 18},
            },
        ])
        reply = run_ai_turn(self.session, inbound, provider=provider)
        self.session.refresh_from_db()
        self.assertEqual(self.session.slot_values["contact_phone"], "0912345678")
        self.assertEqual(reply.content, "電話已記下，請問想去哪一個雪場？")
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(
            provider.calls[1]["input_items"][-1]["type"],
            "function_call_output",
        )
        outbound = ChatBookingMessage.objects.get(pk=reply.message_id)
        self.assertFalse(outbound.metadata["openai_store"])
        self.assertEqual(outbound.metadata["in_reply_to_message_id"], inbound.id)

        replay = run_ai_turn(self.session, inbound, provider=provider)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.message_id, reply.message_id)

    @override_settings(OPENAI_MAX_TOOL_ROUNDS=16)
    def test_tool_loop_can_finish_after_more_than_eight_provider_rounds(self):
        inbound = ChatBookingMessage.objects.create(
            session=self.session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="一次提供完整預約資料",
        )
        responses = []
        for index in range(1, 10):
            responses.append({
                "id": f"resp-tool-{index}",
                "model": "fake-model",
                "output": [{
                    "type": "function_call",
                    "call_id": f"call-state-{index}",
                    "name": "get_booking_state",
                    "arguments": "{}",
                }],
                "output_text": "",
            })
        responses.append({
            "id": "resp-final",
            "model": "fake-model",
            "output": [],
            "output_text": "已完成處理。",
        })
        provider = FakeOpenAIProvider(responses)

        reply = run_ai_turn(self.session, inbound, provider=provider)

        self.assertEqual(reply.content, "已完成處理。")
        self.assertEqual(len(provider.calls), 10)
        self.assertEqual(reply.tool_names.count("get_booking_state"), 9)

    def test_provider_forces_responses_api_privacy_and_serial_tools(self):
        class FakeResponses:
            def __init__(self):
                self.kwargs = None

            def create(self, **kwargs):
                self.kwargs = kwargs
                return {"output": [], "output_text": "ok"}

        class FakeClient:
            def __init__(self):
                self.responses = FakeResponses()

        client = FakeClient()
        provider = OpenAIResponseProvider(client=client)
        provider.create(instructions="test", input_items=[], tools=[])
        self.assertFalse(client.responses.kwargs["store"])
        self.assertFalse(client.responses.kwargs["parallel_tool_calls"])
        self.assertEqual(client.responses.kwargs["model"], provider.model)

    def test_course_intro_prefetches_authoritative_catalog(self):
        resort = Resorts.objects.create(
            client=self.tenant,
            name="TestResort",
            display_name="測試雪場",
        )
        category = CourseCategory.objects.create(
            client=self.tenant,
            name="單板 Snowboard",
            service_type="ski",
        )
        course_type = CourseType.objects.create(category=category, name="半天課程")
        template = CourseTemplate.objects.create(
            course_type=course_type,
            name="基礎滑行",
            duration_hours=3,
            max_capacity=6,
        )
        template.resorts.add(resort)
        inbound = ChatBookingMessage.objects.create(
            session=self.session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="你們的課程有什麼介紹介紹",
        )
        provider = FakeOpenAIProvider([])

        reply = run_ai_turn(self.session, inbound, provider=provider)

        self.assertIn("get_course_catalog", reply.tool_names)
        self.assertEqual(provider.calls, [])
        self.assertEqual(reply.model, "snowland-course-catalog-v1")
        self.assertIn("單板 Snowboard", reply.content)
        self.assertIn("半天課程", reply.content)
        self.assertIn("基礎滑行", reply.content)
        self.assertIn("測試雪場", str(
            ChatBookingToolInvocation.objects.get(
                tool_key="ai_tool:get_course_catalog",
            ).output_data
        ))

class ChatBookingOrderIntegrationTests(TestCase):
    def setUp(self):
        self.tenant = Client.objects.create(name="SnowLand Test", internal_code="snowland-test")
        self.resort = Resorts.objects.create(
            client=self.tenant,
            name="TestResort",
            display_name="測試雪場",
            auto_scheduling_enabled=False,
        )
        self.category = CourseCategory.objects.create(
            client=self.tenant,
            name="雙板",
            service_type="ski",
        )
        self.category.available_resorts.add(self.resort)
        self.course_type = CourseType.objects.create(category=self.category, name="一般課程")
        self.course_type.available_resorts.add(self.resort)
        today = timezone.localdate()
        self.template = CourseTemplate.objects.create(
            course_type=self.course_type,
            name="三小時課程",
            duration_hours=3,
            max_capacity=6,
            booking_open_date=today - timedelta(days=1),
            booking_close_date=today + timedelta(days=90),
            course_start_date=today,
            course_end_date=today + timedelta(days=90),
        )
        self.template.resorts.add(self.resort)
        self.course_session = CourseSession.objects.create(
            template=self.template,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        pricing = CoursePricing.objects.create(
            resort=self.resort,
            base_price_off_peak=10000,
            peak_season_surcharge=2000,
            additional_person_fee=1500,
            max_capacity=6,
            is_active=True,
        )
        pricing.templates.add(self.template)
        self.course_date = (today + timedelta(days=30)).isoformat()
        self.base = "/booking/snowland-test/api/chat/sessions/"
        self.complete_values = {
            "service_type": "ski",
            "category_id": self.category.id,
            "resort": self.resort.name,
            "course_type_id": self.course_type.id,
            "people_count": 1,
            "has_under_6": False,
            "ability_level_counts": {"no_exp": 1},
            "coach_id": "any",
            "language": "zh",
            "template_id": self.template.id,
            "course_dates": [self.course_date],
            "session_id": self.course_session.id,
            "equipment_option": "self_rent",
            "contact_name": "測試客人",
            "contact_phone": "0912345678",
            "policy_accepted": True,
        }

    def create_complete_chat_session(self):
        session = ChatBookingSession.objects.create(
            client=self.tenant,
            channel=ChatBookingSession.CHANNEL_API,
            slot_values=self.complete_values,
            current_step="confirmation",
            access_token_hash="hash",
            expires_at=timezone.now() + timedelta(days=1),
        )
        ChatBookingDraft.objects.create(session=session)
        return session

    def quote_and_confirm(self, session, idempotency_key):
        draft = make_quote(session)
        return confirm_quoted_session(
            session,
            None,
            idempotency_key=idempotency_key,
            expected_state_version=session.state_version,
            expected_quote_hash=draft.quote_hash,
            input_data={"confirmed": True},
        )

    def test_quote_confirm_and_duplicate_confirm_create_one_order(self):
        created = self.client.post(
            self.base,
            data=json.dumps({"service_type": "ski"}),
            content_type="application/json",
        ).json()
        session = created["session"]
        token = created["session_token"]
        state_response = self.client.patch(
            f'{self.base}{session["id"]}/state/',
            data=json.dumps({
                "state_version": session["state_version"],
                "updates": self.complete_values,
            }),
            content_type="application/json",
            HTTP_X_CHAT_SESSION_TOKEN=token,
        )
        self.assertEqual(state_response.status_code, 200, state_response.content)
        state_version = state_response.json()["session"]["state_version"]

        quote_response = self.client.post(
            f'{self.base}{session["id"]}/quote/',
            data="{}",
            content_type="application/json",
            HTTP_X_CHAT_SESSION_TOKEN=token,
        )
        self.assertEqual(quote_response.status_code, 200, quote_response.content)
        quote = quote_response.json()["quote"]
        self.assertEqual(quote["total"], 10000)

        confirm_body = json.dumps({
            "confirmed": True,
            "state_version": state_version,
            "quote_hash": quote["quote_hash"],
        })
        headers = {
            "content_type": "application/json",
            "HTTP_X_CHAT_SESSION_TOKEN": token,
            "HTTP_IDEMPOTENCY_KEY": "confirm-message-001",
        }
        first = self.client.post(
            f'{self.base}{session["id"]}/confirm/',
            data=confirm_body,
            **headers,
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(ReservationGroup.objects.count(), 1)
        self.assertEqual(first.json()["payment"]["total_amount"], 10000)

        second = self.client.post(
            f'{self.base}{session["id"]}/confirm/',
            data=confirm_body,
            **headers,
        )
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(ReservationGroup.objects.count(), 1)

    def test_two_cart_items_quote_and_confirm_create_two_orders_once(self):
        session = self.create_complete_chat_session()

        session, first_draft = add_current_booking_to_cart(session)
        self.assertEqual(len(first_draft.cart), 1)
        self.assertEqual(session.current_step, "cart_action")
        self.assertNotIn("service_type", session.slot_values)
        self.assertEqual(session.slot_values["contact_phone"], "0912345678")

        session.slot_values = deepcopy(self.complete_values)
        session.current_step = "confirmation"
        session.save(update_fields=["slot_values", "current_step", "updated_at"])
        session, second_draft = add_current_booking_to_cart(session)
        self.assertEqual(len(second_draft.cart), 2)

        draft = make_quote(session)
        self.assertEqual(draft.quote["subtotal"], 20000)
        self.assertEqual(draft.quote["total"], 20000)
        result = confirm_quoted_session(
            session,
            None,
            idempotency_key="two-cart-items",
            expected_state_version=session.state_version,
            expected_quote_hash=draft.quote_hash,
            input_data={"confirmed": True},
        )

        self.assertTrue(result.ok, result.error)
        self.assertEqual(len(result.output["reservation_group_ids"]), 2)
        self.assertEqual(ReservationGroup.objects.count(), 2)
        self.assertEqual(Reservation.objects.count(), 2)
        self.assertEqual(Payment.objects.count(), 2)
        self.assertEqual(result.output["payment"]["total_amount"], 20000)

        replay = confirm_quoted_session(
            session,
            None,
            idempotency_key="two-cart-items",
            expected_state_version=session.state_version,
            expected_quote_hash=draft.quote_hash,
            input_data={"confirmed": True},
        )
        self.assertTrue(replay.replayed)
        self.assertEqual(ReservationGroup.objects.count(), 2)

    def test_cart_item_can_be_reopened_for_editing_and_removed(self):
        session = self.create_complete_chat_session()
        session, draft = add_current_booking_to_cart(session)

        session, draft = start_new_cart_item(session)
        self.assertEqual(len(draft.cart), 1)
        self.assertEqual(session.current_step, "service_type")
        inbound = ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="滑雪課程",
        )
        update_result = BookingToolExecutor(session, inbound).execute(
            "update_booking_details",
            {"service_type": "ski"},
            "cart-next-service",
        )
        self.assertTrue(update_result["ok"], update_result)
        draft.refresh_from_db()
        self.assertEqual(len(draft.cart), 1)
        session.refresh_from_db()

        session, draft = edit_cart_item(session, 1)
        self.assertEqual(draft.cart, [])
        self.assertEqual(session.current_step, "editing_cart_item")
        self.assertEqual(session.slot_values["service_type"], "ski")
        self.assertEqual(session.slot_values["course_dates"], [self.course_date])

        session, draft = add_current_booking_to_cart(session)
        session, draft, removed = remove_cart_item(session, 1)
        self.assertEqual(removed["serviceType"], "ski")
        self.assertEqual(draft.cart, [])
        self.assertEqual(session.current_step, "service_type")

    def test_ai_confirmation_tool_creates_one_real_order(self):
        session = ChatBookingSession.objects.create(
            client=self.tenant,
            channel=ChatBookingSession.CHANNEL_API,
            slot_values=self.complete_values,
            current_step="confirmation",
            access_token_hash="hash",
            expires_at=timezone.now() + timedelta(days=1),
        )
        ChatBookingDraft.objects.create(session=session)
        draft = make_quote(session)
        session.status = ChatBookingSession.STATUS_AWAITING_CONFIRMATION
        session.save(update_fields=["status", "updated_at"])
        ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_OUTBOUND,
            sender_type=ChatBookingMessage.SENDER_AI,
            content=f"本次總價為 TWD {draft.quote['total']}，請確認是否下單。",
            metadata={"quote_hash_at_reply": draft.quote_hash},
        )
        inbound = ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="確認下單",
        )
        provider = FakeOpenAIProvider([
            {
                "id": "resp-confirm",
                "model": "fake-model",
                "output": [{
                    "type": "function_call",
                    "call_id": "call-confirm-order",
                    "name": "confirm_booking",
                    "arguments": json.dumps({
                        "confirmed": True,
                        "confirmation_text": "確認下單",
                    }),
                }],
                "output_text": "",
            },
            {
                "id": "resp-confirmed",
                "model": "fake-model",
                "output": [],
                "output_text": "訂單已建立，接下來為你說明付款方式。",
                "usage": {"input_tokens": 200, "output_tokens": 25},
            },
        ])
        reply = run_ai_turn(session, inbound, provider=provider)
        session.refresh_from_db()
        tool_audit = list(
            session.tool_invocations.order_by("id").values(
                "tool_key", "status", "output_data", "error",
            )
        )
        self.assertEqual(ReservationGroup.objects.count(), 1, tool_audit)
        self.assertEqual(session.status, ChatBookingSession.STATUS_CONFIRMED)
        self.assertIn("confirm_booking", reply.tool_names)
        self.assertIn("訂單已建立", reply.content)

    def test_auto_scheduling_success_allows_payment_and_bank_transfer(self):
        self.resort.auto_scheduling_enabled = True
        self.resort.save(update_fields=["auto_scheduling_enabled"])
        coach = Coach.objects.create(
            client=self.tenant,
            name="測試教練",
            languages=["zh"],
            availability_status="active",
        )
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach,
            course_type=self.course_type,
            ability_levels=["no_exp", "level1"],
            price_level="Lv1",
        )
        session = self.create_complete_chat_session()

        result = self.quote_and_confirm(session, "auto-schedule-success")

        self.assertTrue(result.ok, result.error)
        self.assertFalse(result.output["scheduling_failed"])
        self.assertTrue(result.output["requires_payment"])
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.status, "auto_assigned")
        self.assertEqual(reservation.preferred_coach, coach)
        self.assertTrue(Booking.objects.get().is_scheduled)
        self.assertEqual(Payment.objects.get().status, "unpaid")
        self.assertTrue(result.output["payment"]["payment_allowed"])

        payment = submit_bank_transfer(session, "12345")

        self.assertTrue(payment["payment_allowed"])
        stored_payment = Payment.objects.get()
        self.assertEqual(stored_payment.status, "pending")
        self.assertEqual(stored_payment.bank_account, "12345")

    def test_auto_scheduling_failure_keeps_order_but_blocks_payment(self):
        self.resort.auto_scheduling_enabled = True
        self.resort.save(update_fields=["auto_scheduling_enabled"])
        session = self.create_complete_chat_session()

        result = self.quote_and_confirm(session, "auto-schedule-failure")

        self.assertTrue(result.ok, result.error)
        self.assertTrue(result.output["scheduling_failed"])
        self.assertFalse(result.output["requires_payment"])
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.status, "auto_assignment_failed")
        self.assertIsNone(reservation.preferred_coach)
        self.assertFalse(Booking.objects.get().is_scheduled)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertFalse(result.output["payment"]["payment_allowed"])
        session.refresh_from_db()
        self.assertEqual(session.current_step, "scheduling_support")
        with self.assertRaisesMessage(ValueError, "目前不可付款"):
            submit_bank_transfer(session, "12345")

    @skipUnless(
        os.getenv("RUN_OPENAI_LIVE_TESTS") == "1",
        "Set RUN_OPENAI_LIVE_TESTS=1 to call the real OpenAI API.",
    )
    def test_live_openai_explicit_confirmation_creates_scheduled_order(self):
        self.resort.auto_scheduling_enabled = True
        self.resort.save(update_fields=["auto_scheduling_enabled"])
        coach = Coach.objects.create(
            client=self.tenant,
            name="測試教練",
            languages=["zh"],
            availability_status="active",
        )
        CoachResort.objects.create(coach=coach, resort=self.resort)
        CoachCourseLevel.objects.create(
            coach=coach,
            course_type=self.course_type,
            ability_levels=["no_exp", "level1"],
            price_level="Lv1",
        )
        session = self.create_complete_chat_session()
        draft = make_quote(session)
        session.status = ChatBookingSession.STATUS_AWAITING_CONFIRMATION
        session.save(update_fields=["status", "updated_at"])
        ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_OUTBOUND,
            sender_type=ChatBookingMessage.SENDER_AI,
            content=f"本次總價為 TWD {draft.quote['total']}，請確認是否下單。",
            metadata={"quote_hash_at_reply": draft.quote_hash},
        )
        inbound = ChatBookingMessage.objects.create(
            session=session,
            direction=ChatBookingMessage.DIRECTION_INBOUND,
            sender_type=ChatBookingMessage.SENDER_CUSTOMER,
            content="確認下單",
        )

        reply = run_ai_turn(session, inbound)

        self.assertIn("confirm_booking", reply.tool_names)
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.status, "auto_assigned")
        self.assertEqual(reservation.preferred_coach, coach)
        self.assertTrue(Booking.objects.get().is_scheduled)
        self.assertTrue(
            ChatBookingDraft.objects.get(session=session).payment_snapshot["payment_allowed"]
        )
