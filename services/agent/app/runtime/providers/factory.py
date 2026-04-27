from app.models.agent import ProviderName
from app.runtime.providers.anthropic import AnthropicProvider
from app.runtime.providers.base import BaseLLMProvider
from app.runtime.providers.deepseek import DeepSeekProvider
from app.runtime.providers.ollama import OllamaProvider
from app.runtime.providers.openai import OpenAIProvider


class LLMProviderFactory:
    @staticmethod
    def create(provider: ProviderName) -> BaseLLMProvider:
        providers: dict[ProviderName, type[BaseLLMProvider]] = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "deepseek": DeepSeekProvider,
            "ollama": OllamaProvider,
        }
        return providers[provider]()
