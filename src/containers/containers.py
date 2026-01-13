"""Containers for injection."""

import sys
from typing import Any

import loguru
from dependency_injector import containers, providers
from loguru import logger

from src.logger.log import DevelopFormatter
from src.service.ai_researcher.classifier import Classifier
from src.service.ai_researcher.gemini_client import GeminiApiClient
from src.service.ai_researcher.summarizer import Summarizer
from src.service.arxiv.arxiv_fetcher import ArxivFetcher
from src.service.notion_db.add_content_to_page import MarkdownToNotionUploader
from src.service.notion_db.extract_page_content import NotionPageExtractor
from src.service.processor import PapersProcessor
from src.service.vector_db.embedder import EmbeddingService
from src.service.vector_db.vector_storage import QdrantVectorStore
from src.service.workflow import WorkflowService
from src.settings import Settings


class LoggerInitializer:
    """Class to handle the initialization and closing of logger."""

    def __init__(self) -> None:
        """Initialize the logger initializer."""
        self.develop_fmt = DevelopFormatter("paper-hound-api")

    def init_logger(self) -> "loguru.Logger":
        """Initialize and configure the logger.

        Returns:
            loguru.Logger: The configured logger.
        """
        logger.remove()
        logger.add(sys.stderr, format=self.develop_fmt)  # type: ignore
        return logger

    def close_logger(self, my_logger: "loguru.Logger"):  # noqa: ANN201
        """Close and clean up the logger.

        Args:
            my_logger (loguru.Logger): The logger to be closed.
        """
        my_logger.remove()


class AppContainer(containers.DeclarativeContainer):
    """Dependency injection container for managing application components.

    Args:
        containers.DeclarativeContainer: The base class for the dependency injection container.
    """

    # Get the configuration
    config = providers.Configuration()

    # Vector database entities
    vector_store: providers.Singleton[QdrantVectorStore] = providers.Singleton(
        QdrantVectorStore,
        collection=config.vector_store_collection,
        vector_size=config.vector_store_vector_size,
        distance=config.vector_store_distance,
    )

    embedding_service: providers.Singleton[EmbeddingService] = providers.Singleton(
        EmbeddingService,
        model_name=config.embedding_service_model_name,
        batch_size=config.embedding_service_batch_size,
    )

    processor: providers.Singleton[PapersProcessor] = providers.Singleton(
        PapersProcessor,
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    # Arxiv entities
    arxiv_fetcher: providers.Singleton[ArxivFetcher] = providers.Singleton(ArxivFetcher)

    # Notion entities
    notion_uploader: providers.Singleton[MarkdownToNotionUploader] = providers.Singleton(
        MarkdownToNotionUploader,
        database_id=config.notion_database_id,
    )
    # LLM entities
    llm_client: providers.Singleton[GeminiApiClient] = providers.Singleton(
        GeminiApiClient,
        model_name=config.gemini_model_name,
    )

    classifier: providers.Singleton[Classifier] = providers.Singleton(
        Classifier,
        llm_client=llm_client,
        path_to_prompt=config.classifier_path_to_prompt,
    )

    summarizer: providers.Singleton[Summarizer] = providers.Singleton(
        Summarizer,
        llm_client=llm_client,
        path_to_prompt=config.summarizer_path_to_prompt,
    )

    notion_settings_extractor: providers.Singleton[NotionPageExtractor] = providers.Singleton(NotionPageExtractor)

    workflow: providers.Singleton[WorkflowService] = providers.Singleton(
        WorkflowService,
        processor=processor,
        classifier=classifier,
        summarizer=summarizer,
        arxiv_fetcher=arxiv_fetcher,
        notion_uploader=notion_uploader,
        notion_settings_extractor=notion_settings_extractor,
        notion_settings_db_ids=config.notion_settings_db_ids,
    )

    # Singleton and Callable provider for the Logger resource.
    logger_initializer: providers.Singleton[LoggerInitializer] = providers.Singleton(LoggerInitializer)
    logger = providers.Callable(logger_initializer().init_logger)


def init_app_container(modules_to_wire: list[Any], config: Settings) -> AppContainer:
    """Initialize the app container.

    Args:
        modules_to_wire (list[Any]): The modules to wire.
        config (Settings): The configuration.

    Returns:
        AppContainer: The container.
    """
    container = AppContainer()
    json_config = config.model_dump(mode="json")
    container.config.from_dict(json_config)
    container.wire(modules_to_wire)
    container.logger()
    return container
