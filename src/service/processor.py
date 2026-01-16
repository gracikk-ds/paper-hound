"""Processor module for managing paper operations within the system.

This module provides the `PapersProcessor` class, which acts as a central coordinator for:
- Fetching papers from arXiv day-by-day.
- Generating embeddings for paper summaries using `EmbeddingService`.
- Storing and retrieving papers in the `QdrantVectorStore`.
- Searching for papers using semantic similarity and metadata filtering (e.g., date ranges).
- Finding similar papers based on existing entries.
- Managing paper lifecycle (insertion, deletion, counting).
"""

from datetime import date, datetime, timedelta

from loguru import logger
from qdrant_client import models as qmodels

from src.service.arxiv.arxiv_fetcher import fetch_papers_day_by_day
from src.service.vector_db.embedder import EmbeddingService
from src.service.vector_db.vector_storage import QdrantVectorStore
from src.utils.schemas import Paper


class PapersProcessor:
    """Papers processor class for processing papers."""

    def __init__(self, vector_store: QdrantVectorStore, embedding_service: EmbeddingService) -> None:
        """Initialize the papers processor.

        Args:
            vector_store (QdrantVectorStore): The vector store to insert the papers into.
            embedding_service (EmbeddingService): The embedding service to use.
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service

    def insert_papers(self, start_date: date, end_date: date) -> float:
        """Insert the papers into the vector store.

        Args:
            start_date (date): The start date to process.
            end_date (date): The end date to process.

        Returns:
            float: The costs of the embedding service.
        """
        collection_start_date_str, collection_end_date_str = self.vector_store.find_start_end_dates()

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        embedder_costs = 0.0
        current_embedding_model = self.embedding_service.model_name
        for papers in fetch_papers_day_by_day(
            start_date_str,
            end_date_str,
            collection_start_date_str,
            collection_end_date_str,
        ):
            paper_ids = [paper.paper_id for paper in papers]

            # Pre-check Qdrant: if the point exists and embedding_model matches, skip embedding.
            existing_models_by_id = self.vector_store.get_points_embedding_model(paper_ids)

            papers_to_embed: list[Paper] = [
                paper for paper in papers if existing_models_by_id.get(paper.paper_id) != current_embedding_model
            ]

            if not papers_to_embed:
                logger.info(
                    f"Embedding skipped for day batch: fetched={len(papers)}, skipped_same_model={len(papers)}",
                )
                continue

            new_count = sum(1 for p in papers_to_embed if p.paper_id not in existing_models_by_id)
            reembed_count = len(papers_to_embed) - new_count
            skipped_count = len(papers) - len(papers_to_embed)
            logger.info(
                "Embedding precheck stats "
                f"[model={current_embedding_model}]: fetched={len(papers)}, "
                f"to_embed={len(papers_to_embed)}, skipped_same_model={skipped_count}, "
                f"new={new_count}, reembed_model_change={reembed_count}",
            )

            # Embed only the needed subset.
            ids_to_embed = [paper.paper_id for paper in papers_to_embed]
            summary_list = [paper.summary for paper in papers_to_embed]

            before_total = self.embedding_service.total_inference_price
            summary_embeddings = self.embedding_service.embed_batch(summary_list)
            embedder_costs += self.embedding_service.total_inference_price - before_total

            # Overwrite existing points when model changed; insert new ones otherwise.
            self.vector_store.upsert(
                ids_to_embed,
                summary_embeddings,
                papers_to_embed,
                skip_existing=False,
                embedding_model=current_embedding_model,
            )
        return embedder_costs

    def search_papers(
        self,
        query: str,
        k: int = 10,
        threshold: float = 0.65,
        start_date_str: str | None = None,
        end_date_str: str | None = None,
    ) -> list[Paper]:
        """Search the papers in the vector store.

        Args:
            query (str): The query to search for.
            k (int): The number of papers to return per each day.
            threshold (float): The threshold for the similarity score.
            start_date_str (str | None): The start date to search for (YYYY-MM-DD).
            end_date_str (str | None): The end date to search for (YYYY-MM-DD).
        """
        query_embedding = self.embedding_service.embed_text(query)

        # get only papers inside the date range
        filter_conditions = []
        start_dt = None
        end_dt = None

        # Add a lower-bound date condition if a start date is provided
        if start_date_str:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")  # noqa: DTZ007
            start_timestamp = start_dt.timestamp()
            filter_conditions.append(
                qmodels.FieldCondition(
                    key="published_date_ts",
                    range=qmodels.Range(gte=start_timestamp),
                ),
            )

        if end_date_str:
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")  # noqa: DTZ007
            # To include the entire end day, filter for less than the start of the next day
            next_day_dt = end_dt + timedelta(days=1) - timedelta(seconds=1)
            next_day_timestamp = next_day_dt.timestamp()
            filter_conditions.append(
                qmodels.FieldCondition(
                    key="published_date_ts",
                    range=qmodels.Range(lt=next_day_timestamp),  # Use 'lt' (less than)
                ),
            )

        # Calculate total k based on date range (k is per day)
        if start_dt and end_dt:
            num_days = max(1, (end_dt - start_dt).days + 1)
            total_k = k * num_days
        else:
            total_k = k

        # Only create a Filter object if there are conditions to apply
        final_filter = qmodels.Filter(must=filter_conditions) if filter_conditions else None

        results = self.vector_store.search(query_embedding, total_k, threshold, final_filter)
        if results:
            return [Paper(**result.payload) for result in results]  # type: ignore
        return []

    def get_paper_by_id(self, paper_id: str) -> Paper | None:
        """Retrieves a single paper from the vector store by its unique ID."""
        results = self.vector_store.retrieve([paper_id])
        if results:
            return Paper(**results[0].payload)  # type: ignore[missing-argument]
        return None

    def find_similar_papers(
        self,
        paper_id: str,
        k: int = 5,
        threshold: float = 0.65,
        start_date_str: str | None = None,
        end_date_str: str | None = None,
    ) -> list[Paper]:
        """Finds papers with summaries similar to a given paper's summary.

        Args:
            paper_id (str): The ID of the paper to find similar papers for.
            k (int): The number of papers to return.
            threshold (float): The threshold for the similarity score.
            start_date_str (str | None): The start date to search for (YYYY-MM-DD).
            end_date_str (str | None): The end date to search for (YYYY-MM-DD).
        """
        source_vector = self.vector_store.get_vector(paper_id)
        if not source_vector:
            return []

        # Date filtering logic similar to search_papers
        must_conditions = []
        if start_date_str:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")  # noqa: DTZ007
            start_timestamp = start_dt.timestamp()
            must_conditions.append(
                qmodels.FieldCondition(
                    key="published_date_ts",
                    range=qmodels.Range(gte=start_timestamp),
                ),
            )

        if end_date_str:
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")  # noqa: DTZ007
            next_day_dt = end_dt + timedelta(days=1) - timedelta(seconds=1)
            next_day_timestamp = next_day_dt.timestamp()
            must_conditions.append(
                qmodels.FieldCondition(
                    key="published_date_ts",
                    range=qmodels.Range(lt=next_day_timestamp),
                ),
            )

        # Combine date filters with exclusion of the source paper
        search_filter = qmodels.Filter(
            must=must_conditions if must_conditions else None,
            must_not=[
                qmodels.FieldCondition(key="paper_id", match=qmodels.MatchValue(value=paper_id)),
            ],
        )

        results = self.vector_store.search(
            query_vector=source_vector,  # type: ignore
            limit=k,
            threshold=threshold,
            q_filter=search_filter,
        )
        if results:
            return [Paper(**result.payload) for result in results]  # type: ignore
        return []

    def delete_papers(self, paper_ids: list[str]) -> None:
        """Deletes one or more papers from the vector store."""
        if not paper_ids:
            return
        self.vector_store.delete(paper_ids)

    def count_papers(self) -> int:
        """Returns the total number of papers in the vector store."""
        return self.vector_store.count()
