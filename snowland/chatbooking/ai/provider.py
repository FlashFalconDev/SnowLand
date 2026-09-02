import logging

from django.conf import settings


logger = logging.getLogger(__name__)


class AIConfigurationError(RuntimeError):
    """The AI provider cannot be used until its server-side configuration is fixed."""


class AIProviderError(RuntimeError):
    """The provider was configured but did not complete the request."""


class OpenAIResponseProvider:
    def __init__(self, client=None):
        self.model = settings.OPENAI_MODEL
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        api_key = str(settings.OPENAI_API_KEY or "").strip()
        if not api_key:
            raise AIConfigurationError("OPENAI_API_KEY 尚未設定")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIConfigurationError("OpenAI SDK 尚未安裝") from exc
        self._client = OpenAI(
            api_key=api_key,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
            max_retries=2,
        )
        if not hasattr(self._client, "responses"):
            raise AIConfigurationError("OpenAI SDK 版本不支援 Responses API")
        return self._client

    def create(self, *, instructions, input_items, tools):
        try:
            return self._get_client().responses.create(
                model=self.model,
                instructions=instructions,
                input=input_items,
                tools=tools,
                parallel_tool_calls=False,
                store=False,
                max_output_tokens=settings.OPENAI_MAX_OUTPUT_TOKENS,
            )
        except AIConfigurationError:
            raise
        except Exception as exc:
            # Keep diagnostics useful without logging request bodies, customer
            # messages, credentials, or the raw provider exception body.
            logger.error(
                "chatbooking.openai.request_failed model=%s error_type=%s "
                "status_code=%s request_id=%s",
                self.model,
                type(exc).__name__,
                getattr(exc, "status_code", None),
                getattr(exc, "request_id", None),
            )
            raise AIProviderError("OpenAI 暫時無法完成回覆") from exc


def get_provider():
    return OpenAIResponseProvider()
