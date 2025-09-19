"""Containers for injection."""

import sys
from typing import Any

import loguru
from dependency_injector import containers, providers
from loguru import logger

from src.logger.log import DevelopFormatter
from src.service.embedder import EmbeddingService
from src.service.processor import PapersProcessor
from src.service.vector_storage import QdrantVectorStore
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

    vector_store: providers.Singleton[QdrantVectorStore] = providers.Singleton(
        QdrantVectorStore,
        collection=config.vector_store_collection,
        vector_size=config.vector_store_vector_size,
        distance=config.vector_store_distance,
    )

    embedding_service: providers.Singleton[EmbeddingService] = providers.Singleton(
        EmbeddingService,
        model_name=config.embedding_service_model_name,
        device=config.embedding_service_device,
        batch_size=config.embedding_service_batch_size,
    )

    processor: providers.Singleton[PapersProcessor] = providers.Singleton(
        PapersProcessor,
        vector_store=vector_store,
        embedding_service=embedding_service,
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
