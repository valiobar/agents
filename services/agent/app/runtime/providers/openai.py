import httpx
import inspect
import logging
from langchain_openai import ChatOpenAI

from app.config import settings
from app.runtime.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    def create_chat_model(self, model: str | None, temperature: float) -> ChatOpenAI:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI agents")
        # Bound the worst-case latency of every OpenAI chat call.
        # `connect` is kept short so a flaky network surfaces fast; `read` and
        # `write` use the configured chat timeout so a stalled stream doesn't
        # hang the agent loop indefinitely (the OpenAI SDK default is 600s).
        chat_timeout = httpx.Timeout(
            timeout=settings.openai_chat_timeout_seconds,
            connect=10.0,
        )
        resolved_model = model or settings.openai_chat_model
        if settings.is_development:
            logger.info(
                "openai_provider config model=%s timeout=%.0fs retries=%d temperature=%.2f",
                resolved_model,
                settings.openai_chat_timeout_seconds,
                settings.openai_chat_max_retries,
                temperature,
            )
        init_kwargs = {
            "api_key": settings.openai_api_key,
            "model": resolved_model,
            "temperature": temperature,
            "streaming": True,
            "timeout": chat_timeout,
            "max_retries": settings.openai_chat_max_retries,
        }
        if "stream_usage" in inspect.signature(ChatOpenAI.__init__).parameters:
            init_kwargs["stream_usage"] = True
        elif settings.is_development:
            logger.info("openai_provider stream_usage unsupported by installed langchain-openai; continuing without it")

        return ChatOpenAI(
            **init_kwargs,
        )
