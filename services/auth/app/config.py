from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://mongodb:27017"
    db_name: str = "agents"

    jwt_secret: str = "change-me-in-production"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7

    google_client_id: str = ""
    google_client_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
