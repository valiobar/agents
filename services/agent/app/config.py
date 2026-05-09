from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    agent_environment: str = Field(default="production", validation_alias="AGENT_ENV")
    agent_debug_tool_traces: bool = Field(
        default=False,
        validation_alias="AGENT_DEBUG_TOOL_TRACES",
    )

    mongodb_url: str = "mongodb://mongodb:27017"
    db_name: str = "agents"

    knowledge_service_url: str = "http://knowledge:8003"
    knowledge_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="KNOWLEDGE_TIMEOUT_SECONDS",
    )
    business_service_url: str = Field(
        default="http://business:8005",
        validation_alias="BUSINESS_SERVICE_URL",
    )
    business_timeout_seconds: float = Field(
        default=15.0,
        validation_alias="BUSINESS_TIMEOUT_SECONDS",
    )

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4.1-mini"
    openai_chat_timeout_seconds: float = Field(
        default=60.0,
        validation_alias="OPENAI_CHAT_TIMEOUT_SECONDS",
    )
    openai_chat_max_retries: int = Field(
        default=2,
        validation_alias="OPENAI_CHAT_MAX_RETRIES",
    )
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
    default_temperature: float = 0.3
    max_history_messages: int = 20
    rag_top_k: int = 3
    max_agent_iterations: int = Field(
        default=20,
        validation_alias="MAX_AGENT_ITERATIONS",
    )
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

    @property
    def should_emit_tool_traces(self) -> bool:
        return self.is_development and self.agent_debug_tool_traces


settings = Settings()
