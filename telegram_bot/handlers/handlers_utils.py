"""Handlers utilities for the telegram bot."""

import re
from urllib.parse import urlparse

from loguru import logger

from src.service.notion_db.extract_page_content import NotionPageExtractor
from src.settings import settings as api_settings
from src.utils.price_caculation import GEMINI_PRICE
from telegram_bot.handlers.defaults import ALLOWED_THINKING_LEVELS, DEFAULT_CATEGORY, DEFAULT_THRESHOLD, DEFAULT_TOP_K
from telegram_bot.handlers.schemas import SearchParams, SummarizeParams


def normalize_paper_id(paper_id: str) -> str:
    """Normalize a paper identifier or arXiv URL.

    Handles various input formats:
        - Plain ID: "2601.02242"
        - With version: "2301.07041v2"
        - arXiv abs URL: "https://arxiv.org/abs/2601.02242"
        - arXiv PDF URL: "https://arxiv.org/pdf/2601.02242.pdf"
        - alphaxiv URL: "https://alphaxiv.org/abs/2601.02242"

    Args:
        paper_id: Raw paper ID or URL.

    Returns:
        Normalized paper ID string (without version suffix).
    """
    cleaned = paper_id.strip()

    # Handle URLs
    if cleaned.startswith(("http://", "https://")):
        parsed = urlparse(cleaned)
        if parsed.netloc.endswith(("arxiv.org", "alphaxiv.org")):
            path = parsed.path.strip("/")
            if path.startswith(("abs/", "pdf/")):
                cleaned = path.split("/", 1)[1].replace(".pdf", "")

    # Strip version suffix (e.g., "2301.07041v2" -> "2601.02242")
    match = re.match(r"^(\d{4}\.\d{5})(?:v\d+)?$", cleaned)
    return match.group(1) if match else cleaned


def parse_search_params(args: list[str], default_k: int = DEFAULT_TOP_K) -> SearchParams:
    """Parse search arguments extracting optional parameters.

    Supports the following options in any order:
        k:N         - Number of results
        t:N         - Similarity threshold (0-1)
        from:DATE   - Start date (YYYY-MM-DD)
        to:DATE     - End date (YYYY-MM-DD)

    Args:
        args: List of arguments from the command.
        default_k: Default number of results.

    Returns:
        SearchParams with parsed values.

    Examples:
        >>> parse_search_params(["neural", "networks", "k:10", "t:0.5"])
        SearchParams(query="neural networks", top_k=10, threshold=0.5, ...)
    """
    query_parts: list[str] = []
    top_k = default_k
    threshold = DEFAULT_THRESHOLD
    start_date_str: str | None = None
    end_date_str: str | None = None

    # Patterns for parameter extraction
    param_patterns = {
        "k": re.compile(r"^k:(\d+)$"),
        "t": re.compile(r"^t:([0-9.]+)$"),
        "from": re.compile(r"^from:(\d{4}-\d{2}-\d{2})$"),
        "to": re.compile(r"^to:(\d{4}-\d{2}-\d{2})$"),
    }

    for arg in args:
        matched = False
        for param_name, pattern in param_patterns.items():
            match = pattern.match(arg)
            if match:
                matched = True
                value = match.group(1)
                if param_name == "k":
                    top_k = max(1, min(int(value), 50))  # Clamp between 1-50
                elif param_name == "t":
                    threshold = max(0.0, min(float(value), 1.0))  # Clamp between 0-1
                elif param_name == "from":
                    start_date_str = value
                elif param_name == "to":
                    end_date_str = value
                break

        if not matched:
            query_parts.append(arg)

    return SearchParams(
        query=" ".join(query_parts),
        top_k=top_k,
        threshold=threshold,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
    )


def get_available_topics(notion_extractor: NotionPageExtractor) -> list[str]:
    """Get list of available subscription topics from Notion database.

    Args:
        notion_extractor: The Notion page extractor instance.

    Returns:
        List of topic names (excluding AdHoc Research).
    """
    database_id = api_settings.notion_command_database_id
    if not database_id:
        return []

    topics = []
    try:
        for page_id in notion_extractor.query_database(database_id):
            page_settings = notion_extractor.extract_settings_from_page(page_id)
            if page_settings is None:
                continue
            page_name = page_settings.get("Page Name", None)
            if page_name is None:
                continue
            # Skip AdHoc Research - it's not a subscribable topic
            if page_name == "AdHoc Research":
                continue
            topics.append(page_name)
    except Exception:
        logger.exception("Error fetching available topics")

    return topics


def parse_summarize_params(args: list[str]) -> SummarizeParams:
    """Parse summarize arguments extracting optional parameters.

    Supports the following options:
        cat:CategoryName - Research category (default: AdHoc Research)
        model:ModelName - Model name to use for summarization
        think:LEVEL - Thinking level (LOW, MEDIUM, HIGH)

    Args:
        args: List of arguments from the command.

    Returns:
        SummarizeParams with parsed values.

    Examples:
        >>> parse_summarize_params(["2601.02242"])
        SummarizeParams(paper_id="2601.02242", category="AdHoc Research")

        >>> parse_summarize_params(["2601.02242", "cat:Image Editing"])
        SummarizeParams(paper_id="2601.02242", category="Image Editing")

        >>> parse_summarize_params(["2601.02242", "model:gemini-2.5-pro", "think:HIGH"])
        SummarizeParams(paper_id="2601.02242", model_name="gemini-2.5-pro", thinking_level="HIGH")
    """
    paper_id = ""
    category = DEFAULT_CATEGORY
    model_name: str | None = None
    thinking_level: str | None = None
    raw_thinking_level: str | None = None

    category_pattern = re.compile(r"^cat:(.+)$")
    model_pattern = re.compile(r"^model:(.+)$")
    think_pattern = re.compile(r"^think:(.+)$", re.IGNORECASE)

    for arg in args:
        cat_match = category_pattern.match(arg)
        model_match = model_pattern.match(arg)
        think_match = think_pattern.match(arg)

        if cat_match:
            category = cat_match.group(1).strip()
        elif model_match:
            model_name = model_match.group(1).strip()
        elif think_match:
            raw_thinking_level = think_match.group(1).strip()
            level = raw_thinking_level.upper()
            if level in ALLOWED_THINKING_LEVELS:
                thinking_level = level
        elif not paper_id:
            # First non-option argument is the paper_id
            paper_id = normalize_paper_id(arg)

    return SummarizeParams(
        paper_id=paper_id,
        category=category,
        model_name=model_name,
        thinking_level=thinking_level,  # type: ignore[arg-type]
        raw_thinking_level=raw_thinking_level,
    )


def get_available_models() -> list[str]:
    """Get list of available model names from GEMINI_PRICE dict.

    Returns:
        List of available model names.
    """
    return list(GEMINI_PRICE.keys())


def is_valid_model_name(model_name: str) -> bool:
    """Check if the model name is valid.

    Validates that the model name starts with a known base model name.
    This allows endpoint variants like 'gemini-2.5-flash-001' while rejecting
    arbitrary strings that happen to contain a model name as a substring.

    Args:
        model_name: The model name to check.

    Returns:
        True if the model name starts with a known base model, False otherwise.
    """
    return any(model_name.startswith(base_name) for base_name in GEMINI_PRICE)


def validate_summarize_params(params: SummarizeParams) -> str | None:
    """Validate summarize parameters and return error message if invalid.

    Args:
        params: The parsed summarize parameters.

    Returns:
        Error message string if validation fails, None if all params are valid.
    """
    errors: list[str] = []

    # Validate model name if provided
    if params.model_name is not None and not is_valid_model_name(params.model_name):
        available = ", ".join(get_available_models())
        errors.append(f"Unknown model: '{params.model_name}'\nAvailable models: {available}")

    # Validate thinking level - check if raw input was provided but not valid
    if params.raw_thinking_level is not None and params.thinking_level is None:
        allowed = ", ".join(sorted(ALLOWED_THINKING_LEVELS))
        errors.append(f"Invalid thinking level: '{params.raw_thinking_level}'\nAllowed values: {allowed}")

    if errors:
        return "\n\n".join(errors)
    return None
