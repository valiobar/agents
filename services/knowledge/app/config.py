from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://mongodb:27017"
    db_name: str = "agents"

    business_service_url: str = "http://business:8005"

    chromadb_host: str = "chromadb"
    chromadb_port: int = 8000
    chromadb_ssl: bool = False

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_batch_size: int = 64

    chunk_size: int = 800
    chunk_overlap: int = 200
    max_upload_size_bytes: int = 10 * 1024 * 1024
    allowed_content_types: list[str] = [
        "application/pdf",
        "text/plain",
        "text/markdown",
    ]

    tax_docs_path: str = "data/knowledgebase/tax"
    preload_tax_docs: bool = False

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

