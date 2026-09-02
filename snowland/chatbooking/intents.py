import re


def _compact_intent_text(text):
    return re.sub(r"[\s，。！？、,.!?：:；;（）()]+", "", str(text or "")).lower()


def is_explicit_fresh_order_request(text):
    """Return True when the customer asks for a separate new order, not another cart item."""
    value = _compact_intent_text(text)
    if any(
        phrase in value
        for phrase in (
            "不要新訂單",
            "取消新訂單",
            "先不開新訂單",
            "不要新預約",
            "取消新預約",
            "先不開新預約",
        )
    ):
        return False
    return (
        any(
            phrase in value
            for phrase in (
                "新訂單",
                "新預約",
                "新的一單",
                "新下一單",
                "新的訂單",
                "新的預約",
                "另外開新訂單",
                "另外開新預約",
                "開另一張訂單",
                "開另一個預約",
            )
        )
        and any(action in value for action in ("要", "開", "建", "下", "另外"))
    )


def is_additional_booking_request(text):
    """Return True only for an explicit request to open another booking."""
    value = _compact_intent_text(text)
    if any(phrase in value for phrase in ("不要新增", "取消新增", "先不新增")):
        return False
    if is_explicit_fresh_order_request(text):
        return True
    if "新增" in value and "預約" in value:
        return True
    if value in {
        "再預約",
        "在預約",
        "再下一單",
        "我要再下一單",
        "我要新下一單",
        "我要一個新的訂單",
        "開新訂單",
        "建立新訂單",
        "繼續新增",
        "再加一筆",
        "再加一堂",
        "再訂一筆",
        "再訂一堂",
        "新增一筆",
        "新增一個",
    }:
        return True
    return any(
        phrase in value
        for phrase in (
            "新增一個預約",
            "新增一筆預約",
            "新增預約",
            "多新增一個預約",
            "多新增一筆預約",
            "再新增一個預約",
            "再新增一筆預約",
            "另外一個預約",
            "另外一筆預約",
            "另一個預約",
            "另一筆預約",
            "第二個預約",
            "第二筆預約",
            "再預約一堂",
            "再預約一個",
            "再預約一筆",
            "多預約一堂",
            "多預約一個",
            "多預約一筆",
            "幫我新增",
            "另外開一筆",
            "另外開一個",
            "幫我另外開",
            "怎麼另外開",
            "如何另外開",
            "開新的預約",
            "新開一筆預約",
            "另外下一單",
            "另外開新訂單",
            "新增購物車項目",
        )
    )


def is_new_booking_request_after_order(text):
    """Distinguish a new purchase from changes to an already committed order."""
    if is_additional_booking_request(text):
        return True

    value = _compact_intent_text(text)
    if any(
        phrase in value
        for phrase in (
            "改期",
            "改成",
            "更改日期",
            "修改日期",
            "換日期",
            "換成",
            "延後",
            "提前",
            "取消原本",
            "原訂單",
        )
    ):
        return False
    if any(
        phrase in value
        for phrase in (
            "付款",
            "匯款",
            "訂單狀態",
            "預約狀態",
            "查詢訂單",
            "取消訂單",
            "退款",
        )
    ):
        return False

    has_booking_action = any(
        phrase in value
        for phrase in (
            "我要預約",
            "我想預約",
            "想要預約",
            "請幫我預約",
            "幫我預約",
        )
    )
    has_booking_detail = bool(
        re.search(r"20\d{2}年?\d{1,2}月|\d{1,2}月\d{1,2}日", value)
    ) or any(
        term in value
        for term in (
            "單板",
            "雙板",
            "snowboard",
            "ski",
            "滑雪課程",
            "滑雪攝影",
            "跟拍",
            "tomamu",
            "雪場",
        )
    )
    return has_booking_action and has_booking_detail


def is_explicit_human_support_request(text):
    value = _compact_intent_text(text)
    if any(
        phrase in value
        for phrase in (
            "不需要真人",
            "不用真人",
            "不要真人",
            "不用客服",
            "不要客服",
        )
    ):
        return False
    return any(
        phrase in value
        for phrase in (
            "轉真人",
            "真人客服",
            "人工客服",
            "客服人員",
            "找真人",
            "請真人處理",
        )
    )


def is_existing_order_request(text):
    value = _compact_intent_text(text)
    return any(
        phrase in value
        for phrase in (
            "付款",
            "匯款",
            "信用卡",
            "訂單狀態",
            "預約狀態",
            "查詢訂單",
            "我的訂單",
            "取消訂單",
            "取消預約",
            "退款",
            "改期",
            "更改訂單",
            "發票",
        )
    )
