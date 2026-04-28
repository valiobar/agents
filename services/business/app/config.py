from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://mongodb:27017"
    db_name: str = "agents"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
