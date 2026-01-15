"""Unit tests for AI endpoint handlers."""
# ruff: noqa: S101, PLR2004

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from src.routes.ai_endpoint import _normalize_category, _normalize_paper_id, classify_paper, summarize_paper
from src.utils.schemas import ClassifyRequest, SummarizeRequest


# =============================================================================
# summarize_paper Tests
# =============================================================================


def test_summarize_paper_missing_prompt_raises(mock_workflow: Mock, mock_extractor: Mock) -> None:
    """Return 404 when prompt lookup yields no summarizer prompt."""
    request = SummarizeRequest(paper_id="1234.5678", summarizer_prompt=None, category="Physics")
    mock_extractor.query_database.return_value = ["page_1"]
    mock_extractor.extract_settings_from_page.return_value = {"Page Name": "Other"}

    with pytest.raises(HTTPException) as exc_info:
        summarize_paper(request, workflow=mock_workflow, notion_settings_extractor=mock_extractor)

    exc = exc_info.value
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 404


def test_summarize_paper_uses_provided_prompt_and_normalizes(
    mock_workflow: Mock,
    mock_extractor: Mock,
) -> None:
    """Use provided prompt and normalized category without lookup."""
    request = SummarizeRequest(
        paper_id="1234.5678",
        summarizer_prompt="  Summarize this  ",
        category="   ",
    )
    mock_workflow.prepare_paper_summary_and_upload.return_value = "https://notion.so/page"

    result = summarize_paper(request, workflow=mock_workflow, notion_settings_extractor=mock_extractor)

    assert result == "https://notion.so/page"
    mock_extractor.query_database.assert_not_called()
    mock_workflow.prepare_paper_summary_and_upload.assert_called_once_with(
        paper_id="1234.5678",
        summarizer_prompt="Summarize this",
        category="AdHoc Research",
    )


def test_summarize_paper_settings_exception_raises(mock_workflow: Mock, mock_extractor: Mock) -> None:
    """Return 500 when settings lookup fails."""
    request = SummarizeRequest(paper_id="1234.5678", summarizer_prompt=None, category="Physics")
    mock_extractor.query_database.side_effect = Exception("boom")

    with pytest.raises(HTTPException) as exc_info:
        summarize_paper(request, workflow=mock_workflow, notion_settings_extractor=mock_extractor)

    assert exc_info.value.status_code == 500  # type: ignore


def test_summarize_paper_workflow_exception_raises(mock_workflow: Mock, mock_extractor: Mock) -> None:
    """Return 500 when workflow raises an exception."""
    request = SummarizeRequest(
        paper_id="1234.5678",
        summarizer_prompt="Summarize",
        category="Physics",
    )
    mock_workflow.prepare_paper_summary_and_upload.side_effect = Exception("boom")

    with pytest.raises(HTTPException) as exc_info:
        summarize_paper(request, workflow=mock_workflow, notion_settings_extractor=mock_extractor)

    assert exc_info.value.status_code == 500  # type: ignore


def test_summarize_paper_skips_none_settings(mock_workflow: Mock, mock_extractor: Mock) -> None:
    """Skip pages where extract_settings_from_page returns None."""
    request = SummarizeRequest(paper_id="1234.5678", summarizer_prompt=None, category="Physics")
    mock_workflow.prepare_paper_summary_and_upload.return_value = "https://notion.so/page"
    mock_extractor.query_database.return_value = ["page_1", "page_2"]
    mock_extractor.extract_settings_from_page.side_effect = [
        None,  # First page returns None - should be skipped
        {"Page Name": "Physics", "Summarizer Prompt": "Summarize"},  # Second page matches
    ]

    result = summarize_paper(request, workflow=mock_workflow, notion_settings_extractor=mock_extractor)

    assert result == "https://notion.so/page"
    assert mock_extractor.extract_settings_from_page.call_count == 2
    mock_workflow.prepare_paper_summary_and_upload.assert_called_once_with(
        paper_id="1234.5678",
        summarizer_prompt="Summarize",
        category="Physics",
    )


def test_summarize_paper_empty_prompt_triggers_lookup(mock_workflow: Mock, mock_extractor: Mock) -> None:
    """Empty string prompt after strip becomes None, triggering lookup."""
    request = SummarizeRequest(
        paper_id="1234.5678",
        summarizer_prompt="   ",  # Whitespace-only becomes None after strip
        category="Physics",
    )
    mock_workflow.prepare_paper_summary_and_upload.return_value = "https://notion.so/page"
    mock_extractor.query_database.return_value = ["page_1"]
    mock_extractor.extract_settings_from_page.return_value = {
        "Page Name": "Physics",
        "Summarizer Prompt": "Looked up prompt",
    }

    result = summarize_paper(request, workflow=mock_workflow, notion_settings_extractor=mock_extractor)

    assert result == "https://notion.so/page"
    mock_extractor.query_database.assert_called_once()
    mock_workflow.prepare_paper_summary_and_upload.assert_called_once_with(
        paper_id="1234.5678",
        summarizer_prompt="Looked up prompt",
        category="Physics",
    )


def test_summarize_paper_iterates_to_find_matching_category(
    mock_workflow: Mock,
    mock_extractor: Mock,
) -> None:
    """Correctly iterates through pages to find matching category."""
    request = SummarizeRequest(paper_id="1234.5678", summarizer_prompt=None, category="Biology")
    mock_workflow.prepare_paper_summary_and_upload.return_value = "https://notion.so/page"
    mock_extractor.query_database.return_value = ["page_1", "page_2", "page_3"]
    mock_extractor.extract_settings_from_page.side_effect = [
        {"Page Name": "Physics", "Summarizer Prompt": "Physics prompt"},
        {"Page Name": "Chemistry", "Summarizer Prompt": "Chemistry prompt"},
        {"Page Name": "Biology", "Summarizer Prompt": "Biology prompt"},
    ]

    result = summarize_paper(request, workflow=mock_workflow, notion_settings_extractor=mock_extractor)

    assert result == "https://notion.so/page"
    assert mock_extractor.extract_settings_from_page.call_count == 3
    mock_workflow.prepare_paper_summary_and_upload.assert_called_once_with(
        paper_id="1234.5678",
        summarizer_prompt="Biology prompt",
        category="Biology",
    )


# =============================================================================
# classify_paper Tests
# =============================================================================


def test_classify_paper_uses_fetcher_when_missing(
    mock_processor: Mock,
    mock_classifier: Mock,
    mock_fetcher: Mock,
    sample_paper: SimpleNamespace,
) -> None:
    """Use fetched paper when processor misses the record."""
    request = ClassifyRequest(paper_id="1234.5678", classifier_system_prompt="Prompt")
    mock_processor.get_paper_by_id.return_value = None
    mock_fetcher.extract_paper_by_name_or_id.return_value = sample_paper
    mock_classifier.classify.return_value = False

    result = classify_paper(
        request,
        arxiv_fetcher=mock_fetcher,
        classifier=mock_classifier,
        processor=mock_processor,
    )

    assert result is False
    mock_classifier.classify.assert_called_once_with(
        title="Paper",
        summary="Summary",
        system_prompt="Prompt",
    )


def test_classify_paper_normalizes_url_and_version(
    mock_processor: Mock,
    mock_classifier: Mock,
    mock_fetcher: Mock,
    sample_paper: SimpleNamespace,
) -> None:
    """Normalize arXiv URL and version suffix for lookups."""
    request = ClassifyRequest(
        paper_id="https://arxiv.org/abs/1234.56789v2",
        classifier_system_prompt="Prompt",
    )
    mock_processor.get_paper_by_id.return_value = None
    mock_fetcher.extract_paper_by_name_or_id.return_value = sample_paper
    mock_classifier.classify.return_value = True

    result = classify_paper(
        request,
        arxiv_fetcher=mock_fetcher,
        classifier=mock_classifier,
        processor=mock_processor,
    )

    assert result is True
    mock_processor.get_paper_by_id.assert_called_once_with("1234.56789")
    mock_fetcher.extract_paper_by_name_or_id.assert_called_once_with("1234.56789")


def test_classify_paper_classifier_exception(
    mock_processor: Mock,
    mock_classifier: Mock,
    mock_fetcher: Mock,
    sample_paper: SimpleNamespace,
) -> None:
    """Return 500 when classifier raises."""
    request = ClassifyRequest(paper_id="1234.5678", classifier_system_prompt="Prompt")
    mock_processor.get_paper_by_id.return_value = sample_paper
    mock_classifier.classify.side_effect = Exception("boom")

    with pytest.raises(HTTPException) as exc_info:
        classify_paper(
            request,
            arxiv_fetcher=mock_fetcher,
            classifier=mock_classifier,
            processor=mock_processor,
        )

    assert exc_info.value.status_code == 500  # type: ignore


def test_classify_paper_alphaxiv_url(
    mock_processor: Mock,
    mock_classifier: Mock,
    mock_fetcher: Mock,
    sample_paper: SimpleNamespace,
) -> None:
    """Normalize alphaxiv.org URL for classification."""
    request = ClassifyRequest(
        paper_id="https://alphaxiv.org/abs/1234.56789",
        classifier_system_prompt="Prompt",
    )
    mock_processor.get_paper_by_id.return_value = sample_paper
    mock_classifier.classify.return_value = True

    result = classify_paper(
        request,
        arxiv_fetcher=mock_fetcher,
        classifier=mock_classifier,
        processor=mock_processor,
    )

    assert result is True
    mock_processor.get_paper_by_id.assert_called_once_with("1234.56789")


def test_classify_paper_non_matching_format_passed_through(
    mock_processor: Mock,
    mock_classifier: Mock,
    mock_fetcher: Mock,
    sample_paper: SimpleNamespace,
) -> None:
    """Non-matching paper ID format is passed through unchanged."""
    request = ClassifyRequest(
        paper_id="hep-th/9901001",
        classifier_system_prompt="Prompt",
    )
    mock_processor.get_paper_by_id.return_value = sample_paper
    mock_classifier.classify.return_value = False

    result = classify_paper(
        request,
        arxiv_fetcher=mock_fetcher,
        classifier=mock_classifier,
        processor=mock_processor,
    )

    assert result is False
    mock_processor.get_paper_by_id.assert_called_once_with("hep-th/9901001")


# =============================================================================
# _normalize_paper_id Tests
# =============================================================================


def test_normalize_paper_id_handles_pdf_urls() -> None:
    """Strip pdf URL prefix and extension."""
    assert _normalize_paper_id("https://arxiv.org/pdf/1234.56789.pdf") == "1234.56789"


def test_normalize_paper_id_plain_id() -> None:
    """Plain paper ID returns unchanged."""
    assert _normalize_paper_id("1234.56789") == "1234.56789"


def test_normalize_paper_id_with_version_no_url() -> None:
    """Paper ID with version suffix (no URL) strips version."""
    assert _normalize_paper_id("1234.56789v3") == "1234.56789"


def test_normalize_paper_id_alphaxiv_url() -> None:
    """Handle alphaxiv.org URLs."""
    assert _normalize_paper_id("https://alphaxiv.org/abs/1234.56789") == "1234.56789"


def test_normalize_paper_id_non_matching_format() -> None:
    """Non-matching format (old arXiv IDs) returned as-is."""
    assert _normalize_paper_id("hep-th/9901001") == "hep-th/9901001"


def test_normalize_paper_id_whitespace_stripped() -> None:
    """Whitespace is stripped from paper ID."""
    assert _normalize_paper_id("  1234.56789  ") == "1234.56789"


# =============================================================================
# _normalize_category Tests
# =============================================================================


def test_normalize_category_none_returns_default() -> None:
    """None category returns 'AdHoc Research'."""
    assert _normalize_category(None) == "AdHoc Research"


def test_normalize_category_empty_string_returns_default() -> None:
    """Empty string category returns 'AdHoc Research'."""
    assert _normalize_category("") == "AdHoc Research"


def test_normalize_category_whitespace_returns_default() -> None:
    """Whitespace-only category returns 'AdHoc Research'."""
    assert _normalize_category("   ") == "AdHoc Research"


def test_normalize_category_strips_whitespace() -> None:
    """Category with surrounding whitespace is stripped."""
    assert _normalize_category("  Physics  ") == "Physics"


def test_normalize_category_valid_category() -> None:
    """Valid category is returned unchanged."""
    assert _normalize_category("Machine Learning") == "Machine Learning"
