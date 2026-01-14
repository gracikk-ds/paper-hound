"""Qdrant vector store wrapper and collection setup."""

import itertools
import uuid
from collections.abc import Iterable
from datetime import date, datetime

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from src.utils.schemas import Paper, QdrantConnectionConfig


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

            # Ensure payload index for efficient sorting by date
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name="published_date_ts",
                field_schema=qmodels.PayloadSchemaType.FLOAT,
                wait=True,
            )
        except UnexpectedResponse as exp:
            logger.error(f"An API error occurred while ensuring collection '{self.collection}': {exp}")
            raise
        except Exception as exp:
            logger.error(f"An unexpected error occurred: {exp}")
            raise

    def find_start_end_dates(self) -> tuple[str | None, str | None]:
        """Find the start and end dates of the collection efficiently.

        This method leverages server-side sorting to find the minimum and maximum 'published_date' without fetching
        all records. For best performance, ensure a payload index exists on the 'published_date' field.

        Returns:
            tuple[str | None, str | None]:
                - A tuple containing the start (min) and end (max) dates,
                - None, None if the collection is empty or no points have dates.
        """
        self.ensure_collection()

        if self.count() == 0:
            logger.info(f"Collection '{self.collection}' appears to be empty.")
            return None, None

        try:
            # Query for the earliest date (ascending order, limit 1)
            min_date_points, _ = self.client.scroll(
                collection_name=self.collection,
                order_by=qmodels.OrderBy(key="published_date_ts", direction=qmodels.Direction.ASC),
                limit=1,
                with_payload=["published_date_ts", "published_date"],  # Fetch only the required field
            )
            # Query for the latest date (descending order, limit 1)
            max_date_points, _ = self.client.scroll(
                collection_name=self.collection,
                order_by=qmodels.OrderBy(key="published_date_ts", direction=qmodels.Direction.DESC),
                limit=1,
                with_payload=["published_date_ts", "published_date"],
            )
        except UnexpectedResponse as exp:
            logger.error(
                f"Failed to query dates. Ensure the 'published_date' field exists on all points. Error: {exp}",
            )
            return None, None
        except Exception as exp:
            logger.error(f"An unexpected error occurred while finding dates: {exp}")
            raise

        if not min_date_points or not max_date_points:
            logger.warning(
                f"Collection '{self.collection}' appears to be empty or lacks 'published_date' payloads.",
            )
            return None, None

        start_date = min_date_points[0].payload.get("published_date")
        end_date = max_date_points[0].payload.get("published_date")

        if start_date and end_date:
            return start_date, end_date

        logger.warning("Could not retrieve a valid start or end date from the collection.")
        return None, None

    def upsert(
        self,
        ids: Iterable[str],
        vectors: Iterable[list[float]],
        payloads: Iterable[Paper],
        batch_size: int = 256,
    ) -> None:
        """Upserts points into Qdrant in memory-efficient batches from iterators.

        Args:
            ids (Iterable[str]): An iterator of point IDs.
            vectors (Iterable[list[float]]): An iterator of vectors.
            payloads (Iterable[Paper]): An iterator of payloads.
            batch_size (int): The number of points to send in each batch.
        """
        self.ensure_collection()
        uuid_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, id_val)) for id_val in ids]

        existing_ids = set()
        # Check for existing points to avoid re-upserting
        check_batch_size = 1000
        for i in range(0, len(uuid_ids), check_batch_size):
            chunk = uuid_ids[i : i + check_batch_size]
            try:
                results = self.client.retrieve(
                    collection_name=self.collection,
                    ids=chunk,
                    with_payload=False,
                    with_vectors=False,
                )
                existing_ids.update(point.id for point in results)
            except Exception as exp:
                logger.error(f"Failed to check existing points: {exp}")
                raise

        if existing_ids:
            logger.info(f"Skipping {len(existing_ids)} existing points.")

        points_iter = (
            qmodels.PointStruct(id=uuid_id, vector=vec, payload=pay.model_dump())
            for uuid_id, vec, pay in zip(uuid_ids, vectors, payloads, strict=True)
            if uuid_id not in existing_ids
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
        threshold: float = 0.65,
        q_filter: qmodels.Filter | None = None,
    ) -> list[qmodels.ScoredPoint]:
        """Searches for similar vectors.

        Args:
            query_vector (list[float]): The vector to search for.
            limit (int): The maximum number of results to return.
            threshold (float): The threshold for the similarity score.
            q_filter (qmodels.Filter | None): A filter to apply to the search.

        Returns:
            A list of scored points, or an empty list if an error occurs.
        """
        self.ensure_collection()
        try:
            return self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=q_filter,
                score_threshold=threshold,
            )
        except Exception as exp:  # noqa: BLE001
            logger.error(f"An error occurred during search: {exp}")
            return []

    def retrieve(self, ids: list[str] | str) -> list[qmodels.Record] | qmodels.Record:
        """Retrieve points from the vector store by their IDs.

        Args:
            ids (list[str] | str): The ID or IDs of the points to retrieve.

        Returns:
            list[qmodels.Record] | qmodels.Record: A list of records or a single record.
        """
        self.ensure_collection()
        is_single_id = isinstance(ids, str)
        point_ids: list[str] = [ids] if is_single_id else ids  # type: ignore
        point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, id_val)) for id_val in point_ids]

        try:
            # Fetch records with full data (payload and vector).
            records = self.client.retrieve(
                collection_name=self.collection,
                ids=point_ids,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exp:  # noqa: BLE001
            logger.error(f"An error occurred during retrieval for IDs {ids}: {exp}")
            return []
        if is_single_id:
            return records[0] if records else []
        return records

    def delete(self, ids: list[str] | str) -> None:
        """Delete one or more points from the vector store by their IDs.

        Args:
            ids (list[str] | str): The ID or IDs of the points to delete.
        """
        self.ensure_collection()

        point_ids: list[str] = [ids] if isinstance(ids, str) else ids
        point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, id_val)) for id_val in point_ids]

        if not point_ids:
            logger.warning("Delete operation called with no IDs.")
            return

        try:
            logger.info(f"Deleting {len(point_ids)} points from '{self.collection}'.")
            self.client.delete(
                collection_name=self.collection,
                points_selector=qmodels.PointIdsList(points=point_ids),  # type: ignore
                wait=True,  # Wait for the operation to complete.
            )
            logger.info(f"Successfully deleted points: {point_ids}")
        except Exception as exp:  # noqa: BLE001
            logger.error(f"Failed to delete points with IDs {point_ids}: {exp}")

    def count(self) -> int:
        """Count the total number of points in the collection.

        Returns:
            int: The number of points in the collection. Returns 0 on error.
        """
        self.ensure_collection()
        try:
            count_result = self.client.count(
                collection_name=self.collection,
                exact=True,  # Get the exact count.
            )
        except Exception as exp:  # noqa: BLE001
            logger.error(f"Failed to count points in collection '{self.collection}': {exp}")
            return 0
        return count_result.count

    def get_vector(self, ids: str | list[str]) -> list[float] | list[list[float]]:
        """Get the vector(s) for the given point ID(s).

        Args:
            ids (str | list[str]): The ID or list of IDs of the points.

        Returns:
            list[float] | list[list[float]]: A single vector or a list of vectors.
        """
        self.ensure_collection()
        is_single_id = isinstance(ids, str)
        point_ids: list[str] = [ids] if is_single_id else ids  # type: ignore
        point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, id_val)) for id_val in point_ids]

        try:
            # Retrieve points with vectors but without payloads for efficiency.
            records = self.client.retrieve(
                collection_name=self.collection,
                ids=point_ids,
                with_payload=False,
                with_vectors=True,
            )
        except Exception as exp:  # noqa: BLE001
            logger.error(f"An error occurred while getting vectors for IDs {ids}: {exp}")
            return []

        # The vector can be None if it's not stored for a point
        vectors: list[list[float]] = [rec.vector for rec in records if rec.vector is not None]  # type: ignore

        if not vectors:
            logger.warning(f"No vectors found for any ID in: {point_ids}")
            return []

        return vectors[0] if is_single_id else vectors
