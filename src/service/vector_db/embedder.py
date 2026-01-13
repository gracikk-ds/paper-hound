"""Embedding service using Google Vertex AI."""

import json
import os

from google import genai
from google.genai.types import EmbedContentResponse
from loguru import logger

MODEL_PRICE: dict[str, float] = {
    "gemini-embedding-001": 0.15,
}
MILLION_TOKENS: int = 1000000


class EmbeddingService:
    """Wrapper over Google Vertex AI for embeddings."""

    location: str = "us-central1"  # Using us-central1 as default location

    def __init__(self, model_name: str = "gemini-embedding-001", batch_size: int = 250) -> None:
        """Initialize the embedding service.

        Args:
            model_name (str): The name of the model to use for embedding.
            batch_size (int): The batch size to use for embedding.
        """
        self.batch_size = batch_size
        self.model_name = model_name
        self._load_project_id_from_creds()
        # Initialize the gemini client
        self.client = genai.Client(vertexai=True, location=self.location, project=self.project)
        logger.info(f"Initialized embedding service with model {model_name}")
        self.price_per_million_tokens = MODEL_PRICE[model_name]
        self.inference_price = 0.0
        self.total_inference_price = 0.0

    def _load_project_id_from_creds(self) -> None:
        """Load the project id from the credentials.

        Raises:
            ValueError: If the project id cannot be loaded.
        """
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path is None:
            msg = "GOOGLE_APPLICATION_CREDENTIALS is not set"
            raise ValueError(msg)
        with open(creds_path) as creds_file:
            creds = json.load(creds_file)
        self.project = creds["project_id"]

    def calculate_inference_price(self, response: EmbedContentResponse) -> float:
        """Calculate the inference price for a given model.

        Args:
            response (EmbedContentResponse): The response from the embedding service.

        Returns:
            float: The inference price.
        """
        input_token_count = getattr(response.metadata, "billable_character_count", 0) or 0
        return self.price_per_million_tokens * input_token_count / MILLION_TOKENS

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text.

        Args:
            text (str): The text to embed.

        Returns:
            list[float]: The embedding vector as a Python list of floats.
        """
        response = self.client.models.embed_content(model=self.model_name, contents=text)
        self.inference_price = self.calculate_inference_price(response)
        self.total_inference_price += self.inference_price
        if not response.embeddings:
            return []
        return response.embeddings[0].values

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts.

        Args:
            texts (list[str]): The texts to embed.

        Returns:
            list[list[float]]: The embedding vectors as a list of list of floats.
        """
        all_embeddings = []

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            response = self.client.models.embed_content(model=self.model_name, contents=batch)
            self.inference_price = self.calculate_inference_price(response)
            self.total_inference_price += self.inference_price
            if response.embeddings:
                all_embeddings.extend(embedding.values for embedding in response.embeddings)

        return all_embeddings
