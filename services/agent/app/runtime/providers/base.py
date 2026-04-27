from abc import ABC, abstractmethod

from langchain_core.language_models.chat_models import BaseChatModel


class BaseLLMProvider(ABC):
    @abstractmethod
    def create_chat_model(self, model: str | None, temperature: float) -> BaseChatModel:
        raise NotImplementedError
