from langchain_anthropic import ChatAnthropic

from app.config import settings
from app.runtime.providers.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    def create_chat_model(self, model: str | None, temperature: float) -> ChatAnthropic:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for Anthropic agents")
        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=model or settings.anthropic_chat_model,
            temperature=temperature,
            streaming=True,
        )
