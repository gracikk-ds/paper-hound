"""Settings for the application."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the application."""

    model_config = SettingsConfigDict(env_prefix="PAPER_HOUND_")

    api_name: str = Field("Paper Hound API", description="The name of the API")
    api_version: str = Field("0.1.0", description="The version of the API")

    vector_store_collection: str = Field("arxiv_papers", description="The collection name for the vector store")
    vector_store_vector_size: int = Field(2560, description="The size of the vector for the vector store")
    vector_store_distance: str = Field("Cosine", description="The distance for the vector store")
    embedding_service_model_name: str = Field(
        "Qwen/Qwen3-Embedding-4B",
        description="The model name for the embedding service",
    )
    embedding_service_device: str = Field("cpu", description="The device for the embedding service")
    embedding_service_batch_size: int = Field(32, description="The batch size for the embedding service")


settings = Settings()  # type: ignore
