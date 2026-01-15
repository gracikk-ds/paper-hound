"""Pytest configuration, environment setup, and shared fixtures.

This module sets required environment variables for settings initialization
and provides shared fixtures for all test modules.
"""

import datetime
import os
from collections.abc import Generator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from dependency_injector import providers


def _set_required_envs() -> None:
    """Set required environment variables for tests."""
    os.environ.setdefault("NOTION_TOKEN", "test-notion-token")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-aws-key")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
    os.environ.setdefault("ENDPOINT_URL", "https://example.com")
    os.environ.setdefault("S3_BUCKET", "test-bucket")
    os.environ.setdefault("TELEGRAM_TOKEN", "test-telegram-token")
    os.environ.setdefault("TELEGRAM_CHAT_ID", "123456")


_set_required_envs()


# =============================================================================
# Provider Override Helper
# =============================================================================


@contextmanager
def override_providers(*overrides: tuple[providers.Provider, object]) -> Generator[None, None, None]:
    """Temporarily override dependency-injector providers.

    Args:
        *overrides: Tuples of (provider, value) to inject.
    """
    try:
        for provider, value in overrides:
            provider.override(providers.Object(value))
        yield
    finally:
        for provider, _ in overrides:
            provider.reset_override()


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_workflow() -> Mock:
    """Create a mock WorkflowService."""
    return Mock()


@pytest.fixture
def mock_extractor() -> Mock:
    """Create a mock NotionPageExtractor."""
    return Mock()


@pytest.fixture
def mock_processor() -> Mock:
    """Create a mock PapersProcessor."""
    return Mock()


@pytest.fixture
def mock_classifier() -> Mock:
    """Create a mock Classifier."""
    return Mock()


@pytest.fixture
def mock_fetcher() -> Mock:
    """Create a mock ArxivFetcher."""
    return Mock()


@pytest.fixture
def sample_paper() -> SimpleNamespace:
    """Create a sample paper object."""
    return SimpleNamespace(title="Paper", summary="Summary")


@pytest.fixture
def fixed_dates() -> dict[str, datetime.date]:
    """Return fixed dates for deterministic testing."""
    return {
        "today": datetime.date(2025, 6, 15),
        "yesterday": datetime.date(2025, 6, 14),
    }
