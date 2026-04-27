from langchain_openai import ChatOpenAI

from app.config import settings
from app.runtime.providers.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    def create_chat_model(self, model: str | None, temperature: float) -> ChatOpenAI:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI agents")
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=model or settings.openai_chat_model,
            temperature=temperature,
            streaming=True,
        )
