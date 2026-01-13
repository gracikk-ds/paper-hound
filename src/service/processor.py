"""Processor class for processing papers."""

from datetime import date, datetime, timedelta

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

    def insert_papers(self, start_date: date, end_date: date) -> tuple[str, float]:
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
        earliest_date = end_date
        for papers in fetch_papers_day_by_day(
            start_date_str,
            end_date_str,
            collection_start_date_str,
            collection_end_date_str,
        ):
            # embed the summaries
            paper_ids = [paper.paper_id for paper in papers]
            summary_list = [paper.summary for paper in papers]
            summary_embeddings = self.embedding_service.embed_batch(summary_list)
            embedder_costs += self.embedding_service.inference_price
            earliest_paper_date = self.vector_store.upsert(paper_ids, summary_embeddings, papers)
            if earliest_paper_date:
                earliest_date = min(earliest_date, earliest_paper_date)
        return earliest_date.strftime("%Y-%m-%d"), embedder_costs

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
            k (int): The number of papers to return.
            threshold (float): The threshold for the similarity score.
            start_date_str (str | None): The start date to search for (YYYY-MM-DD).
            end_date_str (str | None): The end date to search for (YYYY-MM-DD).
        """
        query_embedding = self.embedding_service.embed_text(query)

        # get only papers inside the date range
        filter_conditions = []
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

        # Only create a Filter object if there are conditions to apply
        final_filter = qmodels.Filter(must=filter_conditions) if filter_conditions else None

        results = self.vector_store.search(query_embedding, k, threshold, final_filter)
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
