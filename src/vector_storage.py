"""Qdrant vector store wrapper and collection setup."""

import itertools
from collections.abc import Iterable
from typing import Any

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from src.settings import QdrantConnectionConfig


class QdrantVectorStore:
    """A wrapper around QdrantClient."""

    def __init__(
        self,
        collection: str = "arxiv_papers",
        vector_size: int = 2560,
        distance: qmodels.Distance = qmodels.Distance.COSINE,
        config: QdrantConnectionConfig | None = None,
    ) -> None:
        """Initializes the QdrantVectorStore.

        Args:
            collection (str): The name of the collection to manage. Default is "arxiv_papers".
            vector_size (int): The dimension of the vectors. Default is 2560.
            distance (qmodels.Distance): The distance metric for the vectors. Default is COSINE.
            config (QdrantConnectionConfig | None): Connection config. If None, loaded from env.

        Raises:
            ConnectionError: If the connection to Qdrant fails.
        """
        self.collection = collection
        self.vector_size = vector_size
        self.distance = distance

        if config is None:
            config = QdrantConnectionConfig()

        try:
            self.client = QdrantClient(
                host=config.host,
                port=config.port,
                api_key=config.api_key,
                timeout=20,
            )
            self.client.get_collections()  # Ping the server to check connection
            logger.info(f"Successfully connected to Qdrant at {config.host}:{config.port}")
        except Exception as exp:
            logger.error(f"Failed to connect to Qdrant: {exp}")
            msg = "Could not connect to Qdrant server."
            raise ConnectionError(msg) from exp

    def close(self) -> None:
        """Close the connection to Qdrant."""
        logger.info("Closing Qdrant client connection.")
        self.client.close()

    def ensure_collection(self, *, recreate: bool = False) -> None:
        """Create the collection if it does not exist.

        Args:
            *: positional only arguments
            recreate (bool): If True, deletes the collection if it exists and creates a new one. Default is False.

        Raises:
            UnexpectedResponse: If the API error occurs while ensuring the collection.
            Exception: If an unexpected error occurs.
        """
        try:
            collections_response = self.client.get_collections()
            existing = [c.name for c in collections_response.collections]

            if self.collection in existing and recreate:
                logger.warning(f"Recreating collection: '{self.collection}'")
                self.client.delete_collection(self.collection)
                existing.remove(self.collection)

            if self.collection not in existing:
                logger.info(f"Collection '{self.collection}' not found. Creating it.")
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=qmodels.VectorParams(size=self.vector_size, distance=self.distance),
                )
            else:
                logger.info(f"Collection '{self.collection}' already exists.")
        except UnexpectedResponse as exp:
            logger.error(f"An API error occurred while ensuring collection '{self.collection}': {exp}")
            raise
        except Exception as exp:
            logger.error(f"An unexpected error occurred: {exp}")
            raise

    def upsert(
        self,
        ids: Iterable[str],
        vectors: Iterable[list[float]],
        payloads: Iterable[dict[str, Any]],
        batch_size: int = 256,
    ) -> None:
        """Upserts points into Qdrant in memory-efficient batches from iterators.

        Args:
            ids (Iterable[str]): An iterator of point IDs.
            vectors (Iterable[list[float]]): An iterator of vectors.
            payloads (Iterable[dict[str, Any]]): An iterator of payloads.
            batch_size (int): The number of points to send in each batch.
        """
        points_iter = (
            qmodels.PointStruct(id=id_val, vector=vec, payload=pay)
            for id_val, vec, pay in zip(ids, vectors, payloads, strict=True)
        )

        batch_num = 0
        while True:
            batch = list(itertools.islice(points_iter, batch_size))
            if not batch:
                break

            batch_num += 1
            logger.info(f"Upserting batch {batch_num} with {len(batch)} points.")
            try:
                self.client.upsert(
                    collection_name=self.collection,
                    points=batch,
                    wait=True,
                )
            except Exception as exp:
                logger.error(f"Failed to upsert batch {batch_num}: {exp}")
                raise

    def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        q_filter: qmodels.Filter | None = None,
    ) -> list[qmodels.ScoredPoint]:
        """Searches for similar vectors.

        Args:
            query_vector (list[float]): The vector to search for.
            limit (int): The maximum number of results to return.
            q_filter (qmodels.Filter | None): A filter to apply to the search.

        Returns:
            A list of scored points, or an empty list if an error occurs.
        """
        try:
            return self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=q_filter,
            )
        except Exception as exp:  # noqa: BLE001
            logger.error(f"An error occurred during search: {exp}")
            return []
