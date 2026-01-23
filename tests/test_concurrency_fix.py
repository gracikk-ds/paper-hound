"""Tests for concurrency bug fix - Factory pattern for isolated instances."""
# ruff: noqa: S101

from unittest.mock import Mock

import pytest

from src.containers.containers import AppContainer, init_app_container
from src.settings import settings


@pytest.fixture
def mock_vector_store() -> Mock:
    """Create a mock QdrantVectorStore."""
    return Mock()


@pytest.fixture
def mock_processing_cache() -> Mock:
    """Create a mock ProcessingCacheStore."""
    return Mock()


@pytest.fixture
def test_container(mock_vector_store: Mock, mock_processing_cache: Mock) -> AppContainer:
    """Create a test container with mocked dependencies."""
    container = init_app_container([], settings)
    # Override Qdrant-dependent services to avoid connection attempts
    container.vector_store.override(mock_vector_store)
    container.processing_cache.override(mock_processing_cache)
    return container


def test_workflow_instances_are_isolated(test_container: AppContainer) -> None:
    """Verify that multiple workflow() calls return different instances."""
    container = test_container

    workflow1 = container.workflow()
    workflow2 = container.workflow()

    # Each call should create a new instance
    assert workflow1 is not workflow2, "Workflow instances should be different"


def test_summarizer_instances_are_isolated(test_container: AppContainer) -> None:
    """Verify that summarizer instances are isolated between workflows."""
    container = test_container

    workflow1 = container.workflow()
    workflow2 = container.workflow()

    # Summarizer instances should be different
    assert workflow1.summarizer is not workflow2.summarizer, "Summarizer instances should be different"


def test_llm_client_instances_are_isolated(test_container: AppContainer) -> None:
    """Verify that LLM client instances are isolated between workflows."""
    container = test_container

    workflow1 = container.workflow()
    workflow2 = container.workflow()

    # LLM client instances should be different
    assert workflow1.summarizer.llm_client is not workflow2.summarizer.llm_client, (
        "LLM client instances should be different"
    )


def test_file_uris_are_isolated_between_instances(test_container: AppContainer) -> None:
    """Verify that file_uris lists are separate for different LLM client instances.

    This is the critical test that verifies the concurrency bug fix.
    """
    container = test_container

    workflow1 = container.workflow()
    workflow2 = container.workflow()

    # Simulate concurrent PDF attachment
    workflow1.summarizer.llm_client.attach_pdf("gs://bucket/pdf1.pdf")
    workflow2.summarizer.llm_client.attach_pdf("gs://bucket/pdf2.pdf")

    # Each instance should have its own file_uris list
    assert workflow1.summarizer.llm_client.file_uris == [
        "gs://bucket/pdf1.pdf",
    ], "Workflow1 should only have pdf1"
    assert workflow2.summarizer.llm_client.file_uris == [
        "gs://bucket/pdf2.pdf",
    ], "Workflow2 should only have pdf2"


def test_classifier_instances_are_isolated(test_container: AppContainer) -> None:
    """Verify that classifier instances are isolated between workflows."""
    container = test_container

    workflow1 = container.workflow()
    workflow2 = container.workflow()

    # Classifier instances should be different
    assert workflow1.classifier is not workflow2.classifier, "Classifier instances should be different"


def test_classifier_llm_client_instances_are_isolated(test_container: AppContainer) -> None:
    """Verify that classifier LLM client instances are isolated."""
    container = test_container

    workflow1 = container.workflow()
    workflow2 = container.workflow()

    # Classifier LLM client instances should be different
    assert workflow1.classifier.llm_client is not workflow2.classifier.llm_client, (
        "Classifier LLM client instances should be different"
    )


def test_singleton_services_remain_shared(test_container: AppContainer) -> None:
    """Verify that singleton services like processor are still shared.

    This ensures we didn't break thread-safe singletons.
    """
    container = test_container

    workflow1 = container.workflow()
    workflow2 = container.workflow()

    # Processor should be the same instance (singleton)
    assert workflow1.processor is workflow2.processor, "Processor should be shared (singleton)"

    # Vector store should be the same instance (singleton)
    assert workflow1.processor.vector_store is workflow2.processor.vector_store, (
        "Vector store should be shared (singleton)"
    )


def test_direct_container_calls_create_new_instances(test_container: AppContainer) -> None:
    """Verify that direct container calls also create new instances."""
    container = test_container

    # Direct calls to container
    summarizer1 = container.summarizer()
    summarizer2 = container.summarizer()

    assert summarizer1 is not summarizer2, "Direct summarizer calls should create new instances"
    assert summarizer1.llm_client is not summarizer2.llm_client, "LLM clients should be different"


def test_inference_price_tracking_isolated(test_container: AppContainer) -> None:
    """Verify that inference price tracking is isolated between instances."""
    container = test_container

    workflow1 = container.workflow()
    workflow2 = container.workflow()

    # Set different prices
    workflow1.summarizer.inference_price = 1.5
    workflow2.summarizer.inference_price = 2.5

    # Each instance should maintain its own price
    assert workflow1.summarizer.inference_price == 1.5, "Workflow1 price should be isolated"  # noqa: PLR2004
    assert workflow2.summarizer.inference_price == 2.5, "Workflow2 price should be isolated"  # noqa: PLR2004
