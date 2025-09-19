"""Settings for the application."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the application."""

    model_config = SettingsConfigDict(env_prefix="PAPER_HOUND_")

    api_name = Field(..., default="Paper Hound API")
    api_version = Field(..., default="0.1.0")


settings = Settings()
