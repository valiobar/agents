from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    agent_environment: str = Field(default="production", validation_alias="AGENT_ENV")

    mongodb_url: str = "mongodb://mongodb:27017"
    db_name: str = "agents"

    knowledge_service_url: str = "http://knowledge:8003"

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-5-mini"
    anthropic_api_key: str = ""
    anthropic_chat_model: str = "claude-3-5-haiku-latest"
    deepseek_api_key: str = ""
    deepseek_chat_model: str = "deepseek-chat"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_chat_model: str = "llama3.1"

    default_provider: str = Field(
        default="openai",
        validation_alias="DEFAULT_AGENT_PROVIDER",
    )
    default_agent_type: str = "accountant"
    default_temperature: float = 0.2
    max_history_messages: int = 20
    rag_top_k: int = 5
    companybook_api_key: str = Field(default="", validation_alias="COMPANYBOOK_API_KEY")
    companybook_base_url: str = Field(
        default="https://api.companybook.bg/api",
        validation_alias="COMPANYBOOK_BASE_URL",
    )
    companybook_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="COMPANYBOOK_TIMEOUT_SECONDS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        populate_by_name=True,
    )

    @property
    def is_development(self) -> bool:
        return self.agent_environment.lower() == "development"


settings = Settings()
