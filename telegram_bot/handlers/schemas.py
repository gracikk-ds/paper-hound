"""Schemas for the telegram bot."""

from typing import Literal

from pydantic import BaseModel

from telegram_bot.handlers.defaults import DEFAULT_CATEGORY, DEFAULT_THRESHOLD, DEFAULT_TOP_K


class SearchParams(BaseModel):
    """Parsed search parameters from user input."""

    query: str
    top_k: int = DEFAULT_TOP_K
    threshold: float = DEFAULT_THRESHOLD
    start_date_str: str | None = None
    end_date_str: str | None = None


class SummarizeParams(BaseModel):
    """Parsed summarize parameters from user input."""

    paper_id: str
    category: str = DEFAULT_CATEGORY
    model_name: str | None = None
    thinking_level: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    raw_thinking_level: str | None = None  # Store raw input for validation messages
