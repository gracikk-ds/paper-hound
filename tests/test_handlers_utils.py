"""Unit tests for telegram bot handlers utilities."""
# ruff: noqa: S101

from telegram_bot.handlers.handlers_utils import (
    get_available_models,
    is_valid_model_name,
    parse_summarize_params,
    validate_summarize_params,
)
from telegram_bot.handlers.schemas import SummarizeParams

# =============================================================================
# parse_summarize_params Tests
# =============================================================================


class TestParseSummarizeParams:
    """Tests for parse_summarize_params function."""

    def test_paper_id_only(self) -> None:
        """Parse paper ID without any options."""
        result = parse_summarize_params(["2601.02242"])
        assert result.paper_id == "2601.02242"
        assert result.category == "AdHoc Research"
        assert result.model_name is None
        assert result.thinking_level is None

    def test_paper_id_with_category(self) -> None:
        """Parse paper ID with category option."""
        result = parse_summarize_params(["2601.02242", "cat:Image Editing"])
        assert result.paper_id == "2601.02242"
        assert result.category == "Image Editing"

    def test_paper_id_with_model(self) -> None:
        """Parse paper ID with model option."""
        result = parse_summarize_params(["2601.02242", "model:gemini-2.5-pro"])
        assert result.paper_id == "2601.02242"
        assert result.model_name == "gemini-2.5-pro"

    def test_paper_id_with_thinking_level_uppercase(self) -> None:
        """Parse paper ID with uppercase thinking level."""
        result = parse_summarize_params(["2601.02242", "think:HIGH"])
        assert result.paper_id == "2601.02242"
        assert result.thinking_level == "HIGH"
        assert result.raw_thinking_level == "HIGH"

    def test_paper_id_with_thinking_level_lowercase(self) -> None:
        """Parse paper ID with lowercase thinking level (normalized to uppercase)."""
        result = parse_summarize_params(["2601.02242", "think:low"])
        assert result.paper_id == "2601.02242"
        assert result.thinking_level == "LOW"
        assert result.raw_thinking_level == "low"

    def test_paper_id_with_thinking_level_mixed_case(self) -> None:
        """Parse paper ID with mixed case thinking level."""
        result = parse_summarize_params(["2601.02242", "think:Medium"])
        assert result.paper_id == "2601.02242"
        assert result.thinking_level == "MEDIUM"
        assert result.raw_thinking_level == "Medium"

    def test_invalid_thinking_level_stores_raw(self) -> None:
        """Invalid thinking level stores raw value but thinking_level is None."""
        result = parse_summarize_params(["2601.02242", "think:INVALID"])
        assert result.paper_id == "2601.02242"
        assert result.thinking_level is None
        assert result.raw_thinking_level == "INVALID"

    def test_all_options_combined(self) -> None:
        """Parse paper ID with all options."""
        result = parse_summarize_params(
            [
                "2601.02242",
                "cat:ML Research",
                "model:gemini-2.5-flash",
                "think:MEDIUM",
            ],
        )
        assert result.paper_id == "2601.02242"
        assert result.category == "ML Research"
        assert result.model_name == "gemini-2.5-flash"
        assert result.thinking_level == "MEDIUM"

    def test_options_in_any_order(self) -> None:
        """Options can appear in any order."""
        result = parse_summarize_params(
            [
                "think:HIGH",
                "model:gemini-2.5-pro",
                "2601.02242",
                "cat:Physics",
            ],
        )
        assert result.paper_id == "2601.02242"
        assert result.category == "Physics"
        assert result.model_name == "gemini-2.5-pro"
        assert result.thinking_level == "HIGH"

    def test_arxiv_url_normalized(self) -> None:
        """ArXiv URL is normalized to paper ID."""
        result = parse_summarize_params(["https://arxiv.org/abs/2601.02242"])
        assert result.paper_id == "2601.02242"

    def test_arxiv_url_with_version_normalized(self) -> None:
        """ArXiv URL with version suffix is normalized."""
        result = parse_summarize_params(["https://arxiv.org/abs/2601.02242v2"])
        assert result.paper_id == "2601.02242"

    def test_empty_args_returns_empty_paper_id(self) -> None:
        """Empty args returns empty paper_id with defaults."""
        result = parse_summarize_params([])
        assert result.paper_id == ""
        assert result.category == "AdHoc Research"
        assert result.model_name is None
        assert result.thinking_level is None


# =============================================================================
# get_available_models Tests
# =============================================================================


class TestGetAvailableModels:
    """Tests for get_available_models function."""

    def test_returns_list(self) -> None:
        """Returns a list of model names."""
        models = get_available_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_contains_known_models(self) -> None:
        """Contains expected model names."""
        models = get_available_models()
        assert "gemini-2.5-flash" in models
        assert "gemini-2.5-pro" in models


# =============================================================================
# is_valid_model_name Tests
# =============================================================================


class TestIsValidModelName:
    """Tests for is_valid_model_name function."""

    def test_exact_match_valid(self) -> None:
        """Exact model name match is valid."""
        assert is_valid_model_name("gemini-2.5-flash") is True
        assert is_valid_model_name("gemini-2.5-pro") is True

    def test_model_with_suffix_valid(self) -> None:
        """Model name with additional suffix is valid (endpoint variants)."""
        assert is_valid_model_name("gemini-2.5-flash-001") is True
        assert is_valid_model_name("gemini-2.5-pro-latest") is True

    def test_unknown_model_invalid(self) -> None:
        """Unknown model name is invalid."""
        assert is_valid_model_name("gpt-4") is False
        assert is_valid_model_name("unknown-model") is False

    def test_empty_string_invalid(self) -> None:
        """Empty string is invalid."""
        assert is_valid_model_name("") is False

    def test_partial_match_invalid(self) -> None:
        """Partial match that doesn't contain full base name is invalid."""
        assert is_valid_model_name("gemini-2") is False
        assert is_valid_model_name("flash") is False

    def test_substring_not_at_start_invalid(self) -> None:
        """Model name containing known model as substring (not prefix) is invalid."""
        assert is_valid_model_name("not-gemini-2.5-flash") is False
        assert is_valid_model_name("my-gemini-2.5-pro-clone") is False


# =============================================================================
# validate_summarize_params Tests
# =============================================================================


class TestValidateSummarizeParams:
    """Tests for validate_summarize_params function."""

    def test_valid_params_returns_none(self) -> None:
        """Valid parameters return None (no error)."""
        params = SummarizeParams(
            paper_id="2601.02242",
            category="ML",
            model_name="gemini-2.5-pro",
            thinking_level="HIGH",
        )
        assert validate_summarize_params(params) is None

    def test_no_optional_params_returns_none(self) -> None:
        """Parameters with no model/thinking specified are valid."""
        params = SummarizeParams(paper_id="2601.02242")
        assert validate_summarize_params(params) is None

    def test_invalid_model_returns_error(self) -> None:
        """Invalid model name returns error message."""
        params = SummarizeParams(
            paper_id="2601.02242",
            model_name="invalid-model",
        )
        error = validate_summarize_params(params)
        assert error is not None
        assert "Unknown model: 'invalid-model'" in error
        assert "Available models:" in error

    def test_invalid_thinking_level_returns_error(self) -> None:
        """Invalid thinking level returns error message."""
        params = SummarizeParams(
            paper_id="2601.02242",
            thinking_level=None,
            raw_thinking_level="INVALID",
        )
        error = validate_summarize_params(params)
        assert error is not None
        assert "Invalid thinking level: 'INVALID'" in error
        assert "Allowed values:" in error

    def test_multiple_errors_combined(self) -> None:
        """Multiple validation errors are combined."""
        params = SummarizeParams(
            paper_id="2601.02242",
            model_name="bad-model",
            thinking_level=None,
            raw_thinking_level="BAD",
        )
        error = validate_summarize_params(params)
        assert error is not None
        assert "Unknown model:" in error
        assert "Invalid thinking level:" in error

    def test_valid_thinking_with_raw_returns_none(self) -> None:
        """Valid thinking level with raw value returns no error."""
        params = SummarizeParams(
            paper_id="2601.02242",
            thinking_level="HIGH",
            raw_thinking_level="high",  # lowercase input that was normalized
        )
        assert validate_summarize_params(params) is None
