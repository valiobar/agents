from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret: str = "change-me-in-production"
    redis_url: str = "redis://redis:6379"
    rate_limit_per_hour: int = 1500

    auth_service_url: str = "http://auth:8001"
    agent_service_url: str = "http://agent:8002"
    business_service_url: str = "http://business:8005"
    knowledge_service_url: str = "http://knowledge:8003"
    orchestrator_service_url: str = "http://orchestrator:8004"

    # Browser origins allowed to call the gateway directly.
    # npm run dev uses :3000. Compose publishes the frontend on host :3010.
    cors_origins: str = (
        "http://localhost:3000,"
        "http://localhost:3010,"
        "http://159.89.26.67:3010"
    )

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
