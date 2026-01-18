"""Processing cache stored in Qdrant.

This module provides a small, persistent cache to avoid repeating expensive
LLM calls (classifier/summarizer) across repeated workflow runs.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels

from src.utils.schemas import QdrantConnectionConfig

Stage = Literal["classifier", "summarizer"]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def stable_hash(value: str) -> str:
    """Stable SHA256 hex digest for prompts/model identifiers."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_cache_key(*, paper_id: str, category_key: str, stage: Stage, model_name: str, prompt_hash: str) -> str:
    """Return a stable cache key for a processing result."""
    payload = {
        "category_key": category_key,
        "model_name": model_name,
        "paper_id": paper_id,
        "prompt_hash": prompt_hash,
        "stage": stage,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def make_summarizer_cache_key(paper_id: str) -> str:
    """Return a stable cache key for a summarizer result based only on paper_id.

    This simplified key ensures that a paper is only summarized once,
    regardless of category, model, or prompt changes.
    """
    payload = {"paper_id": paper_id, "stage": "summarizer"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _qdrant_point_id(cache_key: str) -> str:
    """Create a deterministic Qdrant point id from a cache key."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, cache_key))


@dataclass(frozen=True)
class CachedSummarizerResult:
    """A dataclass for summarizer result caching."""

    status: Literal["success", "failed"]
    notion_page_url: str | None = None


class ProcessingCacheStore:
    """A small Qdrant-backed KV store for workflow processing results."""

    def __init__(
        self,
        *,
        collection: str = "arxiv_processing_cache",
        config: QdrantConnectionConfig | None = None,
    ) -> None:
        """Initialize the ProcessingCacheStore.

        Args:
            collection (str): The name of the collection to use for caching.
            config (QdrantConnectionConfig | None): The connection configuration for Qdrant.

        Raises:
            ConnectionError: If the connection to Qdrant fails.
        """
        self.collection = collection
        if config is None:
            config = QdrantConnectionConfig()

        try:
            self.client = QdrantClient(
                host=config.host,
                port=config.port,
                api_key=config.api_key,
                timeout=20,
            )
            self.client.get_collections()
            logger.info(f"Successfully connected to Qdrant for processing cache at {config.host}:{config.port}")
        except Exception as exp:
            logger.error(f"Failed to connect to Qdrant for processing cache: {exp}")
            msg = "Could not connect to Qdrant server for processing cache."
            raise ConnectionError(msg) from exp

    def ensure_collection(self) -> None:
        """Ensure the cache collection exists."""
        try:
            collections_response = self.client.get_collections()
            existing = {c.name for c in collections_response.collections}
            if self.collection in existing:
                return

            logger.info(f"Creating processing cache collection '{self.collection}'.")
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(size=1, distance=qmodels.Distance.COSINE),
            )
        except Exception as exp:
            logger.error(f"Failed to ensure processing cache collection '{self.collection}': {exp}")
            raise

    def get_classifier_results(self, cache_keys: list[str]) -> dict[str, bool]:
        """Batch fetch classifier results for given cache keys.

        Returns a map: cache_key -> is_relevant
        """
        self.ensure_collection()
        if not cache_keys:
            return {}

        ids = [_qdrant_point_id(k) for k in cache_keys]
        try:
            records = self.client.retrieve(
                collection_name=self.collection,
                ids=ids,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exp:
            logger.error(f"Failed to retrieve classifier cache records: {exp}")
            return {}

        out: dict[str, bool] = {}
        for rec in records:
            payload = rec.payload or {}
            if payload.get("stage") != "classifier":
                continue
            cache_key = payload.get("cache_key")
            is_relevant = payload.get("is_relevant")
            if isinstance(cache_key, str) and isinstance(is_relevant, bool):
                out[cache_key] = is_relevant
        return out

    def put_classifier_result(  # noqa: PLR0913
        self,
        *,
        cache_key: str,
        paper_id: str,
        category_key: str,
        model_name: str,
        prompt_hash: str,
        is_relevant: bool,
    ) -> None:
        """Upsert a classifier result."""
        self.ensure_collection()
        point_id = _qdrant_point_id(cache_key)
        payload: dict[str, Any] = {
            "cache_key": cache_key,
            "paper_id": paper_id,
            "category_key": category_key,
            "stage": "classifier",
            "model_name": model_name,
            "prompt_hash": prompt_hash,
            "is_relevant": is_relevant,
            "updated_at": _utc_now_iso(),
        }
        point = qmodels.PointStruct(id=point_id, vector=[0.0], payload=payload)
        try:
            self.client.upsert(collection_name=self.collection, points=[point], wait=True)
        except Exception as exp:
            logger.error(f"Failed to upsert classifier cache record: {exp}")

    def get_summarizer_results(self, cache_keys: list[str]) -> dict[str, CachedSummarizerResult]:
        """Batch fetch summarizer results for given cache keys.

        Returns a map: cache_key -> CachedSummarizerResult
        """
        self.ensure_collection()
        if not cache_keys:
            return {}

        ids = [_qdrant_point_id(k) for k in cache_keys]
        try:
            records = self.client.retrieve(
                collection_name=self.collection,
                ids=ids,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exp:
            logger.error(f"Failed to retrieve summarizer cache records: {exp}")
            return {}

        out: dict[str, CachedSummarizerResult] = {}
        for rec in records:
            payload = rec.payload or {}
            if payload.get("stage") != "summarizer":
                continue
            cache_key = payload.get("cache_key")
            status = payload.get("status")
            notion_page_url = payload.get("notion_page_url")
            if not isinstance(cache_key, str) or status not in ("success", "failed"):
                continue
            out[cache_key] = CachedSummarizerResult(
                status=status if isinstance(status, str) else "failed",
                notion_page_url=notion_page_url if isinstance(notion_page_url, str) else None,
            )
        return out

    def put_summarizer_result(  # noqa: PLR0913
        self,
        *,
        cache_key: str,
        paper_id: str,
        category_key: str,
        model_name: str,
        prompt_hash: str,
        status: Literal["success", "failed"],
        notion_page_url: str | None = None,
    ) -> None:
        """Upsert a summarizer result."""
        self.ensure_collection()
        point_id = _qdrant_point_id(cache_key)
        payload: dict[str, Any] = {
            "cache_key": cache_key,
            "paper_id": paper_id,
            "category_key": category_key,
            "stage": "summarizer",
            "model_name": model_name,
            "prompt_hash": prompt_hash,
            "status": status,
            "notion_page_url": notion_page_url,
            "updated_at": _utc_now_iso(),
        }
        point = qmodels.PointStruct(id=point_id, vector=[0.0], payload=payload)
        try:
            self.client.upsert(collection_name=self.collection, points=[point], wait=True)
        except Exception as exp:
            logger.error(f"Failed to upsert summarizer cache record: {exp}")

    def get_summarizer_result_by_paper_id(self, paper_id: str) -> CachedSummarizerResult | None:
        """Fetch summarizer result for a paper using only paper_id.

        Args:
            paper_id: The paper ID to look up.

        Returns:
            CachedSummarizerResult if found and valid, otherwise None.
        """
        cache_key = make_summarizer_cache_key(paper_id)
        results = self.get_summarizer_results([cache_key])
        return results.get(cache_key)

    def put_summarizer_result_by_paper_id(
        self,
        *,
        paper_id: str,
        status: Literal["success", "failed"],
        notion_page_url: str | None = None,
    ) -> None:
        """Upsert a summarizer result using only paper_id as the cache key.

        Args:
            paper_id: The paper ID.
            status: The result status ("success" or "failed").
            notion_page_url: The Notion page URL if successful.
        """
        self.ensure_collection()
        cache_key = make_summarizer_cache_key(paper_id)
        point_id = _qdrant_point_id(cache_key)
        payload: dict[str, Any] = {
            "cache_key": cache_key,
            "paper_id": paper_id,
            "stage": "summarizer",
            "status": status,
            "notion_page_url": notion_page_url,
            "updated_at": _utc_now_iso(),
        }
        point = qmodels.PointStruct(id=point_id, vector=[0.0], payload=payload)
        try:
            self.client.upsert(collection_name=self.collection, points=[point], wait=True)
        except Exception as exp:
            logger.error(f"Failed to upsert summarizer cache record: {exp}")
