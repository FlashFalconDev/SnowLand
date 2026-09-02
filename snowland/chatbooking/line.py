import base64
import hashlib
import hmac
import uuid

import requests
from django.conf import settings
from django.utils.crypto import constant_time_compare


class LineConfigurationError(RuntimeError):
    """LINE Messaging API server-side configuration is incomplete."""


class LineAPIError(RuntimeError):
    """LINE Messaging API did not accept a request."""


def verify_line_signature(raw_body, signature, channel_secret):
    """Verify X-Line-Signature against the unmodified request body."""
    if not isinstance(raw_body, bytes):
        return False
    signature = str(signature or "").strip()
    channel_secret = str(channel_secret or "").strip()
    if not signature or not channel_secret:
        return False
    digest = hmac.new(
        channel_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return constant_time_compare(expected, signature)


def _text_messages(text):
    text = str(text or "").strip() or "目前無法產生回覆，請稍後再試。"
    max_text_length = 5000
    max_messages = 5
    limit = max_text_length * max_messages
    was_truncated = len(text) > limit
    text = text[:limit]
    chunks = [
        text[index:index + max_text_length]
        for index in range(0, len(text), max_text_length)
    ]
    if was_truncated:
        chunks[-1] = f"{chunks[-1][:-1]}…"
    return [{"type": "text", "text": chunk} for chunk in chunks]


def _outbound_messages(text, message=None):
    if message is None:
        return _text_messages(text)
    if not isinstance(message, dict) or message.get("type") != "flex":
        raise LineConfigurationError("LINE rich message 格式錯誤")
    if not str(message.get("altText") or "").strip() or not isinstance(
        message.get("contents"),
        dict,
    ):
        raise LineConfigurationError("LINE Flex Message 缺少 altText 或 contents")
    return [message]


class LineMessagingClient:
    REPLY_URL = "https://api.line.me/v2/bot/message/reply"
    PUSH_URL = "https://api.line.me/v2/bot/message/push"
    LOADING_URL = "https://api.line.me/v2/bot/chat/loading/start"

    def __init__(self, *, access_token=None, timeout=None, http_client=None):
        self.access_token = str(
            settings.LINE_CHANNEL_ACCESS_TOKEN
            if access_token is None
            else access_token
        ).strip()
        self.timeout = (
            settings.LINE_API_TIMEOUT_SECONDS
            if timeout is None
            else timeout
        )
        self.http_client = http_client or requests

    def reply(self, reply_token, text, *, message=None):
        if not self.access_token:
            raise LineConfigurationError("LINE_CHANNEL_ACCESS_TOKEN 尚未設定")
        reply_token = str(reply_token or "").strip()
        if not reply_token:
            raise LineAPIError("LINE webhook 缺少 reply token")

        try:
            response = self.http_client.post(
                self.REPLY_URL,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "replyToken": reply_token,
                    "messages": _outbound_messages(text, message),
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LineAPIError("LINE reply API 暫時無法連線") from exc

        if not 200 <= response.status_code < 300:
            raise LineAPIError(
                f"LINE reply API 回傳 HTTP {response.status_code}"
            )

    def push(self, to, text, *, retry_key, message=None):
        if not self.access_token:
            raise LineConfigurationError("LINE_CHANNEL_ACCESS_TOKEN 尚未設定")
        to = str(to or "").strip()
        if not to:
            raise LineAPIError("LINE push API 缺少收件者")
        try:
            retry_key = str(uuid.UUID(str(retry_key)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise LineConfigurationError("LINE push retry key 格式錯誤") from exc

        try:
            response = self.http_client.post(
                self.PUSH_URL,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "X-Line-Retry-Key": retry_key,
                },
                json={
                    "to": to,
                    "messages": _outbound_messages(text, message),
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LineAPIError("LINE push API 暫時無法連線") from exc

        # A 409 with x-line-accepted-request-id means the same retry key was
        # already accepted. Treat it as success to make webhook redelivery safe.
        if (
            response.status_code == 409
            and response.headers.get("x-line-accepted-request-id")
        ):
            return
        if not 200 <= response.status_code < 300:
            raise LineAPIError(
                f"LINE push API 回傳 HTTP {response.status_code}"
            )

    def start_loading(self, chat_id, loading_seconds=None):
        if not self.access_token:
            raise LineConfigurationError("LINE_CHANNEL_ACCESS_TOKEN 尚未設定")
        chat_id = str(chat_id or "").strip()
        if not chat_id:
            raise LineAPIError("LINE webhook 缺少 chat ID")
        loading_seconds = (
            settings.LINE_LOADING_SECONDS
            if loading_seconds is None
            else int(loading_seconds)
        )
        if (
            loading_seconds < 5
            or loading_seconds > 60
            or loading_seconds % 5 != 0
        ):
            raise LineConfigurationError(
                "LINE_LOADING_SECONDS 必須是 5 到 60 間的 5 秒倍數"
            )

        try:
            response = self.http_client.post(
                self.LOADING_URL,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "chatId": chat_id,
                    "loadingSeconds": loading_seconds,
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LineAPIError("LINE loading API 暫時無法連線") from exc

        if not 200 <= response.status_code < 300:
            raise LineAPIError(
                f"LINE loading API 回傳 HTTP {response.status_code}"
            )
