"""Settings for the application."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class QdrantConnectionConfig(BaseSettings):
    """Configuration for Qdrant connection."""

    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    host: str = "localhost"
    port: int = 6333
    api_key: str | None = None
