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


class PaperSearchRequest(BaseModel):
    """Request model for searching papers."""

    query: str
    top_k: int = 10
    threshold: float = 0.65
    start_date_str: str | None = None
    end_date_str: str | None = None


class FindSimilarPapersRequest(BaseModel):
    """Request model for finding similar papers."""

    paper_id: str
    top_k: int = 5
    threshold: float = 0.65
    start_date_str: str | None = None
    end_date_str: str | None = None


class DateRangeRequest(BaseModel):
    """Request model for date range operations."""

    start_date_str: str
    end_date_str: str


class DeletePapersRequest(BaseModel):
    """Request model for deleting papers."""

    paper_ids: list[str]


class WorkflowRunRequest(BaseModel):
    """Request model for running the workflow."""

    start_date_str: str | None = None
    end_date_str: str | None = None
    skip_ingestion: bool = False
    use_classifier: bool = True
    top_k: int = 10
    category: str | None = None


class SummarizeRequest(BaseModel):
    """Request model for summarizing a paper."""

    paper_id: str
    summarizer_prompt: str | None = None
    category: str = "AdHoc Research"


class ClassifyRequest(BaseModel):
    """Request model for classifying a paper."""

    paper_id: str
    classifier_system_prompt: str
