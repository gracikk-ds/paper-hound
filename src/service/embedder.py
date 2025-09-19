"""Embedding service using sentence-transformers."""

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """Thin wrapper over SentenceTransformer for deterministic embeddings."""

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-4B", device: str = "cpu", batch_size: int = 32) -> None:
        """Initialize the embedding service.

        Args:
            model_name (str): The name of the model to use for embedding.
            device (str): The device to use for embedding.
            batch_size (int): The batch size to use for embedding.
        """
        self.batch_size = batch_size
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device=device)
        logger.info(f"Initialized embedding service with model {model_name} and device {device}")

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text.

        Args:
            text (str): The text to embed.

        Returns:
            list[float]: The embedding vector as a Python list of floats.
        """
        vector = self.model.encode(text, normalize_embeddings=True)
        if isinstance(vector, np.ndarray):
            return vector.astype(float).tolist()
        # Fallback in case model returns list-like
        return [float(v) for v in vector]  # type: ignore

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts.

        Args:
            texts (list[str]): The texts to embed.

        Returns:
            list[list[float]]: The embedding vectors as a list of list of floats.
        """
        vectors = self.model.encode(texts, normalize_embeddings=True, batch_size=self.batch_size)
        if isinstance(vectors, np.ndarray):
            return vectors.astype(float).tolist()
        return [[float(v) for v in vec] for vec in vectors]  # type: ignore
