from datetime import date

from django.utils import timezone

from chatbooking.models import ChatBookingDraft


BRAND_DARK = "#103849"
BRAND_PRIMARY = "#16899A"
TEXT_PRIMARY = "#18323D"
TEXT_SECONDARY = "#6B7C85"
SURFACE = "#F3F8FA"


LANGUAGE_LABELS = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
    "yue": "粵語",
}

EQUIPMENT_LABELS = {
    "self_rent": "自行租借",
    "own_equipment": "自備裝備",
    "class_time_help": "課程時間內協助",
    "extra_time_help": "加購裝備協助",
}


def _text(value, *, limit=160, fallback="—"):
    cleaned = " ".join(str(value or "").split()).strip()
    if not cleaned:
        return fallback
    return cleaned[:limit]


def _money(value):
    try:
        return f"TWD {int(value):,}"
    except (TypeError, ValueError):
        return "TWD —"


def _display_date(raw_value):
    try:
        parsed = date.fromisoformat(str(raw_value))
    except (TypeError, ValueError):
        return _text(raw_value)
    return f"{parsed.year}/{parsed.month:02d}/{parsed.day:02d}"


def _masked_phone(phone):
    digits = "".join(character for character in str(phone or "") if character.isdigit())
    return f"末三碼 {digits[-3:]}" if len(digits) >= 3 else "已提供"


def _detail_row(label, value, *, value_color=TEXT_PRIMARY):
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "md",
        "contents": [
            {
                "type": "text",
                "text": label,
                "size": "sm",
                "color": TEXT_SECONDARY,
                "flex": 3,
            },
            {
                "type": "text",
                "text": _text(value),
                "size": "sm",
                "color": value_color,
                "weight": "bold",
                "align": "end",
                "wrap": True,
                "flex": 7,
            },
        ],
    }


def _expiry_text(expires_at):
    if not expires_at:
        return "報價有效時間以客服訊息為準"
    local_time = timezone.localtime(expires_at) if timezone.is_aware(expires_at) else expires_at
    return f"請於 {local_time.strftime('%H:%M')} 前確認，逾時將重新報價"


def _item_details(item, *, include_contact=None):
    courses = item.get("courses") if isinstance(item.get("courses"), list) else []
    first_course = courses[0] if courses and isinstance(courses[0], dict) else {}
    dates = "、".join(
        _display_date(course.get("date"))
        for course in courses
        if isinstance(course, dict) and course.get("date")
    ) or "—"
    start_time = _text(first_course.get("timeSlotStart"), fallback="")
    end_time = _text(first_course.get("timeSlotEnd"), fallback="")
    time_range = f"{start_time}–{end_time}" if start_time and end_time else "—"

    service_label = "滑雪攝影" if item.get("serviceType") == "photo" else "滑雪課程"
    category = _text(item.get("courseCategory"), fallback="")
    course_type = _text(first_course.get("courseTypeName"), fallback="")
    template = _text(first_course.get("courseTemplateName"), fallback="")
    plan_parts = list(dict.fromkeys(part for part in (category, course_type, template) if part))
    plan_name = "｜".join(plan_parts) or service_label

    details = [
        _detail_row("服務", service_label),
        _detail_row("雪場", item.get("resortName") or item.get("resort")),
        _detail_row("課程", plan_name),
        _detail_row("日期", dates),
        _detail_row("時段", time_range),
    ]
    if item.get("serviceType") != "photo":
        details.extend([
            _detail_row("人數", f"{item.get('peopleCount') or 1} 人"),
            _detail_row("語言", LANGUAGE_LABELS.get(item.get("language"), item.get("language"))),
            _detail_row("教練", item.get("coachName") or "不指定教練"),
            _detail_row(
                "裝備",
                EQUIPMENT_LABELS.get(item.get("equipmentOption"), item.get("equipmentOption")),
            ),
        ])

    if include_contact is not None:
        contact_name = _text(include_contact.get("name"), fallback="聯絡人")
        details.append(
            _detail_row("聯絡", f"{contact_name}／{_masked_phone(include_contact.get('phone'))}")
        )
    return details, dates


def _button(label, text, *, primary=False):
    button = {
        "type": "button",
        "style": "primary" if primary else "secondary",
        "height": "sm",
        "action": {
            "type": "message",
            "label": label,
            "text": text,
        },
    }
    if primary:
        button["color"] = BRAND_PRIMARY
    return button


def _summary_amount_contents(draft, quote):
    amount_rows = [_detail_row("課程小計", _money(quote.get("subtotal")))]
    if int(quote.get("discount_total") or 0) > 0:
        amount_rows.append(
            _detail_row("優惠折抵", f"- {_money(quote.get('discount_total'))}", value_color="#D85B4B")
        )
    total_text = _money(quote.get("total"))
    return [
        *amount_rows,
        {
            "type": "box",
            "layout": "horizontal",
            "margin": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": "總計",
                    "size": "md",
                    "color": TEXT_PRIMARY,
                    "weight": "bold",
                    "flex": 3,
                },
                {
                    "type": "text",
                    "text": total_text,
                    "size": "xl",
                    "color": BRAND_PRIMARY,
                    "weight": "bold",
                    "align": "end",
                    "flex": 7,
                },
            ],
        },
        {
            "type": "text",
            "text": _expiry_text(draft.quote_expires_at),
            "size": "xs",
            "color": "#A05E29",
            "wrap": True,
            "margin": "md",
        },
    ]


def _single_item_bubble(draft, item, quote):
    contact = draft.contact if isinstance(draft.contact, dict) else {}
    details, dates = _item_details(item, include_contact=contact)

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BRAND_DARK,
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "text",
                    "text": "SNOWLAND",
                    "size": "xs",
                    "color": "#9EDCE3",
                    "weight": "bold",
                },
                {
                    "type": "text",
                    "text": "下單前請確認",
                    "size": "xl",
                    "color": "#FFFFFF",
                    "weight": "bold",
                    "margin": "sm",
                },
                {
                    "type": "text",
                    "text": "確認後才會正式建立訂單與安排課程",
                    "size": "xs",
                    "color": "#D7EDF0",
                    "wrap": True,
                    "margin": "sm",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "spacing": "md",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": SURFACE,
                    "cornerRadius": "10px",
                    "paddingAll": "12px",
                    "spacing": "sm",
                    "contents": details,
                },
                {"type": "separator", "margin": "lg", "color": "#D9E5E8"},
                *_summary_amount_contents(draft, quote),
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "paddingAll": "16px",
            "contents": [
                _button("確認下單", "確認下單", primary=True),
                _button("繼續新增", "繼續新增"),
                _button("修改預約資料", "我要修改預約資料"),
            ],
        },
        "_dates": dates,
    }


def _cart_item_bubble(item, index, subtotal, discount):
    details, _ = _item_details(item)
    amount_details = [_detail_row("項目小計", _money(subtotal))]
    if int(discount or 0) > 0:
        amount_details.append(
            _detail_row("分攤優惠", f"- {_money(discount)}", value_color="#D85B4B")
        )
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BRAND_DARK,
            "paddingAll": "18px",
            "contents": [
                {
                    "type": "text",
                    "text": f"購物車項目 {index}",
                    "size": "lg",
                    "color": "#FFFFFF",
                    "weight": "bold",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "16px",
            "spacing": "sm",
            "contents": [*details, {"type": "separator", "margin": "md"}, *amount_details],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "paddingAll": "14px",
            "contents": [
                _button("修改此項", f"修改第 {index} 項"),
                _button("刪除此項", f"刪除第 {index} 項"),
            ],
        },
    }


def _cart_summary_bubble(draft, quote, item_count):
    contact = draft.contact if isinstance(draft.contact, dict) else {}
    contact_name = _text(contact.get("name"), fallback="聯絡人")
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BRAND_DARK,
            "paddingAll": "18px",
            "contents": [
                {
                    "type": "text",
                    "text": "整車下單確認",
                    "size": "xl",
                    "color": "#FFFFFF",
                    "weight": "bold",
                },
                {
                    "type": "text",
                    "text": f"共 {item_count} 個預約項目",
                    "size": "sm",
                    "color": "#D7EDF0",
                    "margin": "sm",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "18px",
            "spacing": "md",
            "contents": [
                _detail_row("聯絡", f"{contact_name}／{_masked_phone(contact.get('phone'))}"),
                {"type": "separator", "margin": "md", "color": "#D9E5E8"},
                *_summary_amount_contents(draft, quote),
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "paddingAll": "14px",
            "contents": [
                _button("確認整車下單", "確認下單", primary=True),
                _button("繼續新增", "繼續新增"),
                _button("查看購物車", "查看購物車"),
            ],
        },
    }


def _cart_action_bubble(cart):
    item_count = len(cart)
    current_subtotal = sum(
        int(item.get("totalPrice") or 0)
        for item in cart
        if isinstance(item, dict)
    )
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BRAND_DARK,
            "paddingAll": "18px",
            "contents": [
                {
                    "type": "text",
                    "text": "我的預約購物車",
                    "size": "xl",
                    "color": "#FFFFFF",
                    "weight": "bold",
                },
                {
                    "type": "text",
                    "text": f"目前共 {item_count} 個項目",
                    "size": "sm",
                    "color": "#D7EDF0",
                    "margin": "sm",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "18px",
            "spacing": "md",
            "contents": [
                _detail_row("目前小計", _money(current_subtotal)),
                {
                    "type": "text",
                    "text": "優惠、可預約狀態與最終金額會在結帳時由後台重新確認。",
                    "size": "xs",
                    "color": TEXT_SECONDARY,
                    "wrap": True,
                    "margin": "sm",
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "paddingAll": "14px",
            "contents": [
                _button("前往結帳", "結帳", primary=True),
                _button("繼續新增", "繼續新增"),
                _button("清空購物車", "清空購物車"),
            ],
        },
    }


def build_booking_cart_flex(draft):
    """Build a cart-management Flex message before the customer checks out."""
    if not draft or draft.status == ChatBookingDraft.STATUS_COMMITTED:
        return None
    cart = [
        item
        for item in (draft.cart if isinstance(draft.cart, list) else [])
        if isinstance(item, dict)
    ]
    if not cart:
        return None

    bubbles = [
        _cart_item_bubble(item, index, item.get("totalPrice"), 0)
        for index, item in enumerate(cart[:10], start=1)
    ]
    bubbles.append(_cart_action_bubble(cart))
    return {
        "type": "flex",
        "altText": _text(
            f"預約購物車｜共 {len(cart)} 項｜可繼續新增或結帳",
            limit=300,
        ),
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }


def build_booking_confirmation_flex(draft):
    """Build a trusted LINE Flex quote card from the persisted backend draft."""
    if not draft or draft.status != ChatBookingDraft.STATUS_QUOTED:
        return None
    if not draft.quote_hash or not draft.quote:
        return None
    if draft.quote_expires_at and draft.quote_expires_at <= timezone.now():
        return None

    cart = [
        item
        for item in (draft.cart if isinstance(draft.cart, list) else [])
        if isinstance(item, dict)
    ]
    if not cart:
        return None
    quote = draft.quote if isinstance(draft.quote, dict) else {}
    if quote.get("total") is None:
        return None

    if len(cart) == 1:
        bubble = _single_item_bubble(draft, cart[0], quote)
        dates = bubble.pop("_dates", "")
        alt_text = _text(
            f"下單前確認｜{cart[0].get('resortName') or cart[0].get('resort')}｜"
            f"{dates}｜總計 {_money(quote.get('total'))}",
            limit=300,
        )
        return {
            "type": "flex",
            "altText": alt_text,
            "contents": bubble,
        }

    subtotals = quote.get("item_subtotals") or []
    discounts = quote.get("item_discount_amounts") or []
    bubbles = []
    for index, item in enumerate(cart[:10], start=1):
        subtotal = subtotals[index - 1] if index - 1 < len(subtotals) else item.get("totalPrice")
        discount = discounts[index - 1] if index - 1 < len(discounts) else 0
        bubbles.append(_cart_item_bubble(item, index, subtotal, discount))
    bubbles.append(_cart_summary_bubble(draft, quote, len(cart)))
    return {
        "type": "flex",
        "altText": _text(
            f"購物車下單前確認｜共 {len(cart)} 項｜總計 {_money(quote.get('total'))}",
            limit=300,
        ),
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }
