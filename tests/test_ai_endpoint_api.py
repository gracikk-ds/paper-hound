"""API-level tests for AI endpoints."""
# ruff: noqa: S101, PLR2004

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.containers.containers import AppContainer, init_app_container
from src.routes import ai_endpoint
from src.routes.routers import processor_router
from src.settings import settings
from tests.conftest import override_providers

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_app() -> tuple[FastAPI, AppContainer]:
    """Create a minimal FastAPI app for endpoint tests."""
    app = FastAPI()
    container = init_app_container([ai_endpoint], settings)
    app.container = container  # type: ignore[attr-defined]
    app.include_router(processor_router, prefix="/processor")
    return app, container


# =============================================================================
# /summarize-paper Tests
# =============================================================================


def test_summarize_paper_success(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
    mock_extractor: Mock,
) -> None:
    """Return 200 and Notion URL when prompt is resolved."""
    app, container = test_app
    mock_workflow.prepare_paper_summary_and_upload.return_value = "https://notion.so/page"
    mock_extractor.query_database.return_value = ["page_1"]
    mock_extractor.extract_settings_from_page.return_value = {
        "Page Name": "Physics",
        "Summarizer Prompt": "Summarize this paper",
    }

    with override_providers(
        (container.workflow, mock_workflow),
        (container.notion_settings_extractor, mock_extractor),
    ):
        client = TestClient(app)
        response = client.post(
            "/processor/summarize-paper",
            json={"paper_id": "1234.5678", "category": "Physics"},
        )

    assert response.status_code == 200
    assert response.json() == "https://notion.so/page"
    mock_workflow.prepare_paper_summary_and_upload.assert_called_once_with(
        paper_id="1234.5678",
        summarizer_prompt="Summarize this paper",
        category="Physics",
    )


def test_summarize_paper_prompt_not_found(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
    mock_extractor: Mock,
) -> None:
    """Return 404 when prompt cannot be resolved."""
    app, container = test_app
    mock_extractor.query_database.return_value = ["page_1"]
    mock_extractor.extract_settings_from_page.return_value = {"Page Name": "Other"}

    with override_providers(
        (container.workflow, mock_workflow),
        (container.notion_settings_extractor, mock_extractor),
    ):
        client = TestClient(app)
        response = client.post(
            "/processor/summarize-paper",
            json={"paper_id": "1234.5678", "category": "Physics"},
        )

    assert response.status_code == 404


def test_summarize_paper_workflow_failure(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
    mock_extractor: Mock,
) -> None:
    """Return 500 when workflow returns None."""
    app, container = test_app
    mock_workflow.prepare_paper_summary_and_upload.return_value = None
    mock_extractor.query_database.return_value = ["page_1"]
    mock_extractor.extract_settings_from_page.return_value = {
        "Page Name": "Physics",
        "Summarizer Prompt": "Summarize this paper",
    }

    with override_providers(
        (container.workflow, mock_workflow),
        (container.notion_settings_extractor, mock_extractor),
    ):
        client = TestClient(app)
        response = client.post(
            "/processor/summarize-paper",
            json={"paper_id": "1234.5678", "category": "Physics"},
        )

    assert response.status_code == 500


def test_summarize_paper_invalid_body(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
    mock_extractor: Mock,
) -> None:
    """Return 422 when request payload is invalid."""
    app, container = test_app

    with override_providers(
        (container.workflow, mock_workflow),
        (container.notion_settings_extractor, mock_extractor),
    ):
        client = TestClient(app)
        response = client.post("/processor/summarize-paper", json={"category": "Physics"})

    assert response.status_code == 422


# =============================================================================
# /classify-paper Tests
# =============================================================================


def test_classify_paper_success(
    test_app: tuple[FastAPI, AppContainer],
    mock_processor: Mock,
    mock_classifier: Mock,
    mock_fetcher: Mock,
    sample_paper: SimpleNamespace,
) -> None:
    """Return classifier result when processor finds a paper."""
    app, container = test_app
    mock_classifier.classify.return_value = True
    mock_processor.get_paper_by_id.return_value = sample_paper

    with override_providers(
        (container.processor, mock_processor),
        (container.classifier, mock_classifier),
        (container.arxiv_fetcher, mock_fetcher),
    ):
        client = TestClient(app)
        response = client.post(
            "/processor/classify-paper",
            json={"paper_id": "1234.5678", "classifier_system_prompt": "Prompt"},
        )

    assert response.status_code == 200
    assert response.json() is True
    mock_classifier.classify.assert_called_once_with(
        title="Paper",
        summary="Summary",
        system_prompt="Prompt",
    )
    mock_fetcher.extract_paper_by_name_or_id.assert_not_called()


def test_classify_paper_fetcher_exception(
    test_app: tuple[FastAPI, AppContainer],
    mock_processor: Mock,
    mock_classifier: Mock,
    mock_fetcher: Mock,
) -> None:
    """Return 404 when fetcher raises after processor miss."""
    app, container = test_app
    mock_processor.get_paper_by_id.return_value = None
    mock_fetcher.extract_paper_by_name_or_id.side_effect = Exception("boom")

    with override_providers(
        (container.processor, mock_processor),
        (container.classifier, mock_classifier),
        (container.arxiv_fetcher, mock_fetcher),
    ):
        client = TestClient(app)
        response = client.post(
            "/processor/classify-paper",
            json={"paper_id": "1234.5678", "classifier_system_prompt": "Prompt"},
        )

    assert response.status_code == 404


def test_classify_paper_fetcher_returns_none(
    test_app: tuple[FastAPI, AppContainer],
    mock_processor: Mock,
    mock_classifier: Mock,
    mock_fetcher: Mock,
) -> None:
    """Return 404 when fetcher returns no paper."""
    app, container = test_app
    mock_processor.get_paper_by_id.return_value = None
    mock_fetcher.extract_paper_by_name_or_id.return_value = None

    with override_providers(
        (container.processor, mock_processor),
        (container.classifier, mock_classifier),
        (container.arxiv_fetcher, mock_fetcher),
    ):
        client = TestClient(app)
        response = client.post(
            "/processor/classify-paper",
            json={"paper_id": "1234.5678", "classifier_system_prompt": "Prompt"},
        )

    assert response.status_code == 404


def test_classify_paper_invalid_body(
    test_app: tuple[FastAPI, AppContainer],
    mock_processor: Mock,
    mock_classifier: Mock,
    mock_fetcher: Mock,
) -> None:
    """Return 422 when request payload is invalid."""
    app, container = test_app

    with override_providers(
        (container.processor, mock_processor),
        (container.classifier, mock_classifier),
        (container.arxiv_fetcher, mock_fetcher),
    ):
        client = TestClient(app)
        response = client.post("/processor/classify-paper", json={"paper_id": "1234.5678"})

    assert response.status_code == 422
