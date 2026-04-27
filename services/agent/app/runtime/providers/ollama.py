from langchain_ollama import ChatOllama

from app.config import settings
from app.runtime.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    def create_chat_model(self, model: str | None, temperature: float) -> ChatOllama:
        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=model or settings.ollama_chat_model,
            temperature=temperature,
        )
