from langchain_deepseek import ChatDeepSeek

from app.config import settings
from app.runtime.providers.base import BaseLLMProvider


class DeepSeekProvider(BaseLLMProvider):
    def create_chat_model(self, model: str | None, temperature: float) -> ChatDeepSeek:
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required for DeepSeek agents")
        return ChatDeepSeek(
            api_key=settings.deepseek_api_key,
            model=model or settings.deepseek_chat_model,
            temperature=temperature,
            streaming=True,
        )
