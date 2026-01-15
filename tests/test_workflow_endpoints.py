"""API-level tests for workflow endpoints."""
# ruff: noqa: S101, PLR2004

import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.containers.containers import AppContainer, init_app_container
from src.routes import workflow_endpoints
from src.routes.routers import workflow_router
from src.settings import settings
from tests.conftest import override_providers


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_app() -> tuple[FastAPI, AppContainer]:
    """Create a minimal FastAPI app for workflow endpoint tests."""
    app = FastAPI()
    container = init_app_container([workflow_endpoints], settings)
    app.container = container  # type: ignore[attr-defined]
    app.include_router(workflow_router, prefix="/workflow")
    return app, container


# =============================================================================
# Happy Path Tests
# =============================================================================


def test_run_workflow_success_default_request(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Return 202 with acceptance message for default request."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post("/workflow/run", json={})

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message": "Workflow started in background.",
    }


def test_run_workflow_background_task_scheduled(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
    fixed_dates: dict[str, datetime.date],
) -> None:
    """Verify background task is scheduled with correct default parameters."""
    app, container = test_app

    with (
        override_providers((container.workflow, mock_workflow)),
        patch("src.routes.workflow_endpoints.datetime") as mock_datetime,
    ):
        mock_datetime.date.today.return_value = fixed_dates["today"]
        mock_datetime.timedelta = datetime.timedelta
        mock_datetime.datetime = datetime.datetime

        client = TestClient(app)
        response = client.post("/workflow/run", json={})

    assert response.status_code == 202
    mock_workflow.run_workflow.assert_called_once_with(
        start_date=fixed_dates["yesterday"],
        end_date=fixed_dates["today"],
        skip_ingestion=False,
        use_classifier=True,
        top_k=10,
        category=None,
    )


# =============================================================================
# Date Handling Tests
# =============================================================================


def test_run_workflow_with_custom_dates(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Valid custom start and end dates are parsed correctly."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={
                "start_date_str": "2025-01-01",
                "end_date_str": "2025-01-15",
            },
        )

    assert response.status_code == 202
    mock_workflow.run_workflow.assert_called_once()
    call_kwargs = mock_workflow.run_workflow.call_args.kwargs
    assert call_kwargs["start_date"] == datetime.date(2025, 1, 1)
    assert call_kwargs["end_date"] == datetime.date(2025, 1, 15)


def test_run_workflow_only_start_date_provided(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
    fixed_dates: dict[str, datetime.date],
) -> None:
    """Only start_date_str provided uses today() for end date."""
    app, container = test_app

    with (
        override_providers((container.workflow, mock_workflow)),
        patch("src.routes.workflow_endpoints.datetime") as mock_datetime,
    ):
        mock_datetime.date.today.return_value = fixed_dates["today"]
        mock_datetime.timedelta = datetime.timedelta
        mock_datetime.datetime = datetime.datetime

        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"start_date_str": "2025-06-01"},
        )

    assert response.status_code == 202
    call_kwargs = mock_workflow.run_workflow.call_args.kwargs
    assert call_kwargs["start_date"] == datetime.date(2025, 6, 1)
    assert call_kwargs["end_date"] == fixed_dates["today"]


def test_run_workflow_only_end_date_provided(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
    fixed_dates: dict[str, datetime.date],
) -> None:
    """Only end_date_str provided uses yesterday() for start date."""
    app, container = test_app

    with (
        override_providers((container.workflow, mock_workflow)),
        patch("src.routes.workflow_endpoints.datetime") as mock_datetime,
    ):
        mock_datetime.date.today.return_value = fixed_dates["today"]
        mock_datetime.timedelta = datetime.timedelta
        mock_datetime.datetime = datetime.datetime

        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"end_date_str": "2025-06-20"},
        )

    assert response.status_code == 202
    call_kwargs = mock_workflow.run_workflow.call_args.kwargs
    assert call_kwargs["start_date"] == fixed_dates["yesterday"]
    assert call_kwargs["end_date"] == datetime.date(2025, 6, 20)


def test_run_workflow_both_dates_none_uses_defaults(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
    fixed_dates: dict[str, datetime.date],
) -> None:
    """Both dates as None uses yesterday/today defaults."""
    app, container = test_app

    with (
        override_providers((container.workflow, mock_workflow)),
        patch("src.routes.workflow_endpoints.datetime") as mock_datetime,
    ):
        mock_datetime.date.today.return_value = fixed_dates["today"]
        mock_datetime.timedelta = datetime.timedelta
        mock_datetime.datetime = datetime.datetime

        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"start_date_str": None, "end_date_str": None},
        )

    assert response.status_code == 202
    call_kwargs = mock_workflow.run_workflow.call_args.kwargs
    assert call_kwargs["start_date"] == fixed_dates["yesterday"]
    assert call_kwargs["end_date"] == fixed_dates["today"]


# =============================================================================
# Date Validation Error Tests (400)
# =============================================================================


def test_run_workflow_invalid_start_date_format(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Return 400 when start_date_str format is invalid."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"start_date_str": "not-a-date"},
        )

    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]
    mock_workflow.run_workflow.assert_not_called()


def test_run_workflow_invalid_end_date_format(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Return 400 when end_date_str format is invalid."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"end_date_str": "01-15-2025"},  # MM-DD-YYYY instead of YYYY-MM-DD
        )

    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]
    mock_workflow.run_workflow.assert_not_called()


def test_run_workflow_invalid_both_dates_format(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Return 400 when both date formats are invalid."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={
                "start_date_str": "invalid",
                "end_date_str": "also-invalid",
            },
        )

    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]
    mock_workflow.run_workflow.assert_not_called()


def test_run_workflow_invalid_date_with_extra_chars(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Return 400 for date with extra characters."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"start_date_str": "2025-01-01T00:00:00"},  # Has time component
        )

    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]


# =============================================================================
# Request Body Validation Tests (422)
# =============================================================================


def test_run_workflow_invalid_top_k_type(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Return 422 when top_k is not an integer."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"top_k": "not-an-int"},
        )

    assert response.status_code == 422


def test_run_workflow_invalid_skip_ingestion_type(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Return 422 when skip_ingestion is not a boolean."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"skip_ingestion": "not-a-bool"},
        )

    assert response.status_code == 422


def test_run_workflow_invalid_use_classifier_type(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Return 422 when use_classifier is not a boolean."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"use_classifier": "not-a-bool"},
        )

    assert response.status_code == 422


# =============================================================================
# Request Parameter Combination Tests
# =============================================================================


def test_run_workflow_skip_ingestion_true(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Verify skip_ingestion=True is passed to workflow."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"skip_ingestion": True},
        )

    assert response.status_code == 202
    call_kwargs = mock_workflow.run_workflow.call_args.kwargs
    assert call_kwargs["skip_ingestion"] is True


def test_run_workflow_use_classifier_false(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Verify use_classifier=False is passed to workflow."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"use_classifier": False},
        )

    assert response.status_code == 202
    call_kwargs = mock_workflow.run_workflow.call_args.kwargs
    assert call_kwargs["use_classifier"] is False


def test_run_workflow_custom_top_k(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Verify custom top_k value is passed to workflow."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"top_k": 25},
        )

    assert response.status_code == 202
    call_kwargs = mock_workflow.run_workflow.call_args.kwargs
    assert call_kwargs["top_k"] == 25


def test_run_workflow_custom_category(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Verify custom category is passed to workflow."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={"category": "Machine Learning"},
        )

    assert response.status_code == 202
    call_kwargs = mock_workflow.run_workflow.call_args.kwargs
    assert call_kwargs["category"] == "Machine Learning"


def test_run_workflow_all_parameters(
    test_app: tuple[FastAPI, AppContainer],
    mock_workflow: Mock,
) -> None:
    """Verify all parameters are correctly passed to workflow."""
    app, container = test_app

    with override_providers((container.workflow, mock_workflow)):
        client = TestClient(app)
        response = client.post(
            "/workflow/run",
            json={
                "start_date_str": "2025-03-01",
                "end_date_str": "2025-03-15",
                "skip_ingestion": True,
                "use_classifier": False,
                "top_k": 50,
                "category": "Physics",
            },
        )

    assert response.status_code == 202
    mock_workflow.run_workflow.assert_called_once_with(
        start_date=datetime.date(2025, 3, 1),
        end_date=datetime.date(2025, 3, 15),
        skip_ingestion=True,
        use_classifier=False,
        top_k=50,
        category="Physics",
    )
