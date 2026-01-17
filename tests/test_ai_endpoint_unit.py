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


def test_summarize_paper_success(mock_workflow: Mock) -> None:
    """Return Notion URL on successful summarization."""
    request = SummarizeRequest(paper_id="1234.5678", category="Physics")
    mock_workflow.prepare_paper_summary_and_upload.return_value = "https://notion.so/page"

    result = summarize_paper(request, workflow=mock_workflow)

    assert result == "https://notion.so/page"
    mock_workflow.prepare_paper_summary_and_upload.assert_called_once_with(
        paper_id="1234.5678",
        category="Physics",
    )


def test_summarize_paper_normalizes_empty_category(mock_workflow: Mock) -> None:
    """Empty category is normalized to 'AdHoc Research'."""
    request = SummarizeRequest(paper_id="1234.5678", category="   ")
    mock_workflow.prepare_paper_summary_and_upload.return_value = "https://notion.so/page"

    result = summarize_paper(request, workflow=mock_workflow)

    assert result == "https://notion.so/page"
    mock_workflow.prepare_paper_summary_and_upload.assert_called_once_with(
        paper_id="1234.5678",
        category="AdHoc Research",
    )


def test_summarize_paper_workflow_exception_raises(mock_workflow: Mock) -> None:
    """Return 500 when workflow raises an exception."""
    request = SummarizeRequest(paper_id="1234.5678", category="Physics")
    mock_workflow.prepare_paper_summary_and_upload.side_effect = Exception("boom")

    with pytest.raises(HTTPException) as exc_info:
        summarize_paper(request, workflow=mock_workflow)

    assert exc_info.value.status_code == 500  # type: ignore


def test_summarize_paper_workflow_returns_none_raises(mock_workflow: Mock) -> None:
    """Return 500 when workflow returns None."""
    request = SummarizeRequest(paper_id="1234.5678", category="Physics")
    mock_workflow.prepare_paper_summary_and_upload.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        summarize_paper(request, workflow=mock_workflow)

    assert exc_info.value.status_code == 500  # type: ignore


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
