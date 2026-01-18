"""Settings for the application."""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the application."""

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE_PATH", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),  # Added to resolve the warning
    )

    api_name: str = Field("Paper Hound API", description="The name of the API")
    api_version: str = Field("0.1.0", description="The version of the API")

    vector_store_collection: str = Field("arxiv_papers", description="The collection name for the vector store")
    processing_cache_collection: str = Field(
        "arxiv_processing_cache",
        description="The collection name for the workflow processing cache (classifier/summarizer results).",
    )
    vector_store_vector_size: int = Field(3072, description="The size of the vector for the vector store")
    vector_store_distance: str = Field("Cosine", description="The distance for the vector store")
    embedding_service_model_name: str = Field(
        "gemini-embedding-001",
        description="The model name for the embedding service",
    )
    embedding_service_batch_size: int = Field(250, description="The batch size for the embedding service")

    notion_token: str = Field(..., description="Notion API token.")
    notion_database_id: str = Field("228f6f75bb0b80babf73d46a6254a459", description="Notion database ID.")
    notion_command_database_id: str = Field(
        "228f6f75-bb0b-8048-aa28-ef08ff55f9bf",
        description="Notion command database ID.",
    )
    aws_access_key_id: str = Field(..., description="AWS access key ID.")
    aws_secret_access_key: str = Field(..., description="AWS secret access key.")
    endpoint_url: str = Field(..., description="AWS endpoint URL.")
    s3_bucket: str = Field(..., description="S3 bucket name.")

    gemini_model_name: str = Field("gemini-3-flash-preview", description="Gemini model name.")
    classifier_thinking_level: str = Field("LOW", description="Thinking level for the classifier LLM.")
    summarizer_thinking_level: str = Field("MEDIUM", description="Thinking level for the summarizer LLM.")
    summarizer_path_to_prompt: str = Field("prompts/summarizer.txt", description="Path to the summarizer prompt.")
    tmp_storage_dir: str = Field("storage/tmp_storage", description="Path to the temporary storage directory.")
    telegram_token: str = Field(..., description="Telegram bot token.")
    telegram_chat_id: int = Field(..., description="Chat ID to send notifications to.")


settings = Settings()
