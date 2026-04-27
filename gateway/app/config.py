from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret: str = "change-me-in-production"
    redis_url: str = "redis://redis:6379"
    rate_limit_per_hour: int = 1500

    auth_service_url: str = "http://auth:8001"
    agent_service_url: str = "http://agent:8002"
    knowledge_service_url: str = "http://knowledge:8003"
    orchestrator_service_url: str = "http://orchestrator:8004"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
