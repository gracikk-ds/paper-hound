"""Embedding service using sentence-transformers."""

import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """Thin wrapper over SentenceTransformer for deterministic embeddings."""

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-4B") -> None:
        """Initialize the embedding service.

        Args:
            model_name (str): The name of the model to use for embedding.
        """
        self.model = SentenceTransformer(model_name)

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
        vectors = self.model.encode(list(texts), normalize_embeddings=True)
        if isinstance(vectors, np.ndarray):
            return vectors.astype(float).tolist()
        return [[float(v) for v in vec] for vec in vectors]  # type: ignore
