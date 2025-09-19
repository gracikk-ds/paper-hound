"""Settings for the application."""

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class QdrantConnectionConfig(BaseSettings):
    """Configuration for Qdrant connection."""

    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    host: str = "localhost"
    port: int = 6333
    api_key: str | None = None


class Paper(BaseModel):
    """Pydantic model representing an arXiv paper."""

    paper_id: str
    title: str
    authors: list[str]
    summary: str
    published_date: str
    published_date_ts: float
    updated_date: str
    updated_date_ts: float
    pdf_url: str
    primary_category: str
