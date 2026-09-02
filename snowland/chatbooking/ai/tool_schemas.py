NULLABLE_STRING = ["string", "null"]
NULLABLE_INTEGER = ["integer", "null"]
NULLABLE_BOOLEAN = ["boolean", "null"]


def _empty_tool(name, description):
    return {
        "type": "function",
        "name": name,
        "description": description,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    }


ABILITY_COUNTS_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "no_exp": {"type": NULLABLE_INTEGER},
        "level1": {"type": NULLABLE_INTEGER},
        "level2": {"type": NULLABLE_INTEGER},
        "level3": {"type": NULLABLE_INTEGER},
        "level4": {"type": NULLABLE_INTEGER},
        "level5": {"type": NULLABLE_INTEGER},
        "level6": {"type": NULLABLE_INTEGER},
    },
    "required": ["no_exp", "level1", "level2", "level3", "level4", "level5", "level6"],
    "additionalProperties": False,
}


UPDATE_PROPERTIES = {
    "service_type": {"type": NULLABLE_STRING, "enum": ["ski", "photo", None]},
    "category_id": {"type": NULLABLE_INTEGER},
    "resort": {"type": NULLABLE_STRING},
    "course_type_id": {"type": NULLABLE_INTEGER},
    "people_count": {"type": NULLABLE_INTEGER},
    "has_under_6": {"type": NULLABLE_BOOLEAN},
    "under_7_can_self_ski": {"type": NULLABLE_BOOLEAN},
    "ability_level_counts": ABILITY_COUNTS_SCHEMA,
    "coach_id": {
        "type": ["integer", "string", "null"],
        "description": "後端選項的教練 ID，或不指定時使用 any。",
    },
    "language": {"type": NULLABLE_STRING, "enum": ["zh", "en", "ja", "yue", None]},
    "template_id": {"type": NULLABLE_INTEGER},
    "course_dates": {
        "type": ["array", "null"],
        "items": {"type": "string", "description": "YYYY-MM-DD"},
    },
    "session_id": {"type": NULLABLE_INTEGER},
    "equipment_option": {
        "type": NULLABLE_STRING,
        "enum": ["self_rent", "own_equipment", "class_time_help", "extra_time_help", None],
    },
    "equipment_assistance_time_slot_id": {"type": NULLABLE_INTEGER},
    "contact_name": {"type": NULLABLE_STRING},
    "contact_email": {"type": NULLABLE_STRING},
    "contact_phone": {"type": NULLABLE_STRING},
    "referral_source": {"type": NULLABLE_STRING},
    "discount_code": {"type": NULLABLE_STRING},
    "policy_accepted": {"type": NULLABLE_BOOLEAN},
}


BOOKING_TOOLS = [
    _empty_tool(
        "get_booking_state",
        "取得目前已蒐集資料、缺少欄位、報價與訂單狀態。需要確認目前進度時使用。",
    ),
    {
        "type": "function",
        "name": "update_booking_details",
        "description": "只寫入客人已明確提供、且後端 ID 已由選項工具確認的預約資料。沒有更新的欄位傳 null。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": UPDATE_PROPERTIES,
            "required": list(UPDATE_PROPERTIES),
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "list_booking_options",
        "description": "依目前預約狀態查詢後端真實可選項與 ID。選課、日期、時段或教練前必須使用。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": [
                        "service_type",
                        "category_id",
                        "resort",
                        "course_type_id",
                        "people_count",
                        "ability_level",
                        "language",
                        "equipment_option",
                        "template_id",
                        "course_dates",
                        "session_id",
                        "coach_id",
                        "equipment_assistance_time_slot_id",
                    ],
                },
                "month": {
                    "type": NULLABLE_STRING,
                    "description": "查詢日期時可傳 YYYY-MM；其他情況傳 null。",
                },
            },
            "required": ["field", "month"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_course_catalog",
        "description": "查詢 SnowLand 後台目前可預約的正式課程與攝影方案目錄。客人詢問課程介紹、有哪些課程、方案差異、推薦課程或某雪場能上什麼時，優先使用本工具，不可改用 FAQ 搜尋代替。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "service_type": {
                    "type": NULLABLE_STRING,
                    "enum": ["ski", "photo", None],
                    "description": "只查滑雪課程用 ski，只查攝影用 photo；查全部傳 null。",
                },
                "category_id": {
                    "type": NULLABLE_INTEGER,
                    "description": "已知課程大類時傳後端真實 ID，否則傳 null。",
                },
                "resort": {
                    "type": NULLABLE_STRING,
                    "description": "只查特定雪場時傳後端雪場代碼，否則傳 null。",
                },
            },
            "required": ["service_type", "category_id", "resort"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_customer_knowledge",
        "description": "查詢 SnowLand 後台已發布的 FAQ、文章、優惠、頁面與行前須知。禁止把查不到的內容自行補完。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "content_type": {
                    "type": NULLABLE_STRING,
                    "enum": ["page", "offer", "article", "faq", "review", "media", "social", "setting", None],
                },
            },
            "required": ["query", "content_type"],
            "additionalProperties": False,
        },
    },
    _empty_tool(
        "get_booking_cart",
        "查看目前尚未下單的購物車項目、順序與金額。客人說查看購物車或需要確認內容時使用。",
    ),
    _empty_tool(
        "add_booking_to_cart",
        "目前這一項預約資料完整後，將它加入購物車並清空課程欄位，以便繼續新增其他預約。只加入購物車，不報價也不下單。",
    ),
    _empty_tool(
        "start_new_cart_item",
        "購物車已有項目或已有報價，而客人明確說繼續新增、再加一筆或再加一堂時，保留購物車並開始填寫新項目。",
    ),
    {
        "type": "function",
        "name": "remove_cart_item",
        "description": "客人明確要求刪除購物車中的某一項時使用。index 為畫面上從 1 開始的項目編號。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer"},
            },
            "required": ["index"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "edit_cart_item",
        "description": "客人明確要求修改購物車中的某一項時，將該項移回編輯狀態。index 為從 1 開始的項目編號。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer"},
            },
            "required": ["index"],
            "additionalProperties": False,
        },
    },
    _empty_tool(
        "clear_booking_cart",
        "只有客人本次訊息明確要求清空購物車時使用；尚未成立的項目會全部移除。",
    ),
    _empty_tool(
        "create_booking_quote",
        "客人說結帳、購物車至少一項、聯絡電話完整且已同意政策後，使用後端權威價格建立整車 15 分鐘有效報價。只報價，不建立訂單。",
    ),
    {
        "type": "function",
        "name": "confirm_booking",
        "description": "高影響動作：只在客人看過目前報價後，以新的訊息明確確認下單時建立訂單並排課。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "confirmed": {"type": "boolean"},
                "confirmation_text": {
                    "type": "string",
                    "description": "逐字帶入客人本次明確確認下單的短句。",
                },
            },
            "required": ["confirmed", "confirmation_text"],
            "additionalProperties": False,
        },
    },
    _empty_tool(
        "get_payment_info",
        "訂單建立且允許付款後，取得該對話訂單的應付金額、付款狀態與後台銀行資料。",
    ),
    {
        "type": "function",
        "name": "submit_bank_transfer",
        "description": "只有客人本次訊息實際提供匯款帳號後五碼時，才能登記銀行匯款待核對。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "sender_account": {
                    "type": "string",
                    "description": "客人本次訊息中的匯款帳號後五碼。",
                },
            },
            "required": ["sender_account"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "request_human_support",
        "description": "客人要求真人，或遇到取消、退款、改期、申訴、特殊風險與無法可靠處理的情況時轉接真人。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
            "additionalProperties": False,
        },
    },
]
