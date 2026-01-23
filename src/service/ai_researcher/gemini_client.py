"""Gemini Api Client."""

import json
import os
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.cloud import aiplatform
from google.genai.types import (
    Content,
    FileData,
    GenerateContentConfig,
    GenerateContentResponse,
    HttpOptions,
    Part,
    ThinkingConfig,
    ThinkingLevel,
)
from loguru import logger

from src.service.ai_researcher.google_bucket import GoogleBucket
from src.utils.price_caculation import calculate_inference_price

load_dotenv()


class GeminiApiClient:
    """Gemini Api Client class."""

    prediction_timeout: int = 120
    location: str = "global"

    def __init__(
        self,
        model_name: str = "gemini-3-flash-preview",
        system_prompt: str | None = None,
        temperature: float = 0.0,
        thinking_level: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM",
        *,
        verbose: bool = False,
    ) -> None:
        """Initialize GeminiClient with Vertex AI connection, model, and defaults.

        Args:
            model_name: The model to use.
            system_prompt: The system prompt to use.
            temperature: The temperature to use.
            thinking_level: The thinking level to use.
            verbose: Whether to log the prompt to Gemini.
        """
        # Initialize aiplatform
        self._load_project_id_from_creds()
        self.model_name = model_name
        aiplatform.init(project=self.project, location=self.location)
        logger.info("aiplatform has been initialized.")

        # Initialize the gemini client
        self.client = genai.Client(
            vertexai=True,
            project=self.project,
            location=self.location,
            http_options=HttpOptions(timeout=self.prediction_timeout * 1000),
        )
        logger.info("gemini client has been initialized.")

        # Initialize the bucket
        self.bucket = GoogleBucket(bucket_prefix="pdfs")
        logger.info("google bucket has been initialized.")

        # Set the attributes
        self.temperature = temperature
        self.thinking_level = ThinkingLevel(thinking_level.upper())
        self._system_prompt = system_prompt
        self.file_uris: list[str] = []
        self.total_inference_price: float = 0.0
        self.total_requests: int = 0
        self.inference_price: float = 0.0
        self.verbose = verbose
        self.last_used_model: str | None = None
        self.last_thinking_level: str | None = None

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

    @property
    def system_prompt(self) -> str:
        """Get the system prompt.

        Returns:
            The system prompt.
        """
        if self._system_prompt is None:
            return "You are a helpful senior research assistant."
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, prompt: str) -> None:
        """Set or update the system prompt.

        Args:
            prompt (str): The system prompt to use.

        Raises:
            ValueError: If the system prompt is not a string.
        """
        if not isinstance(prompt, str):
            msg = "`system_prompt` must be a string."
            raise ValueError(msg)  # noqa: TRY004
        self._system_prompt = prompt

    def calculate_stats(self, response: GenerateContentResponse, effective_model: str | None = None) -> None:
        """Calculate the stats for the response.

        Args:
            response (GenerateContentResponse): The response from Gemini.
            effective_model (str | None): The model used for this request (for accurate pricing).
        """
        # Calculate the stats
        prompt_token_count = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        candidates_token_count = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
        thoughts_token_count = getattr(response.usage_metadata, "thoughts_token_count", 0) or 0
        cached_content_token_count = getattr(response.usage_metadata, "cached_content_token_count", 0) or 0

        model_for_pricing = effective_model if effective_model is not None else self.model_name
        self.inference_price = calculate_inference_price(
            model_name=model_for_pricing,
            total_input_token_count=prompt_token_count,
            cached_content_token_count=cached_content_token_count,
            total_output_token_count=candidates_token_count + thoughts_token_count,
        )

        self.total_requests += 1
        self.total_inference_price += self.inference_price

    def attach_pdf(self, gcs_uri: str) -> None:
        """Attach a PDF (or text file) for native processing.

        Args:
            gcs_uri (str): The URI of the PDF file to attach.
        """
        self.file_uris.append(gcs_uri)

    def clear_pdfs(self) -> None:
        """Clear all attached document URIs."""
        self.file_uris = []

    def ask(
        self,
        user_prompt: str,
        model_name: str | None = None,
        thinking_level: Literal["LOW", "MEDIUM", "HIGH"] | None = None,
    ) -> GenerateContentResponse:
        """Send a prompt to Gemini, with optional system, PDF, and image inputs.

        Args:
            user_prompt (str): The user prompt to send to Gemini.
            model_name (str | None): Optional model name to override the default.
            thinking_level (Literal["LOW", "MEDIUM", "HIGH"] | None): Optional thinking level to override.

        Returns:
            GenerateContentResponse: The generated content response.
        """
        contents: list[Content] = []

        # System instruction
        contents.append(Content(role="model", parts=[Part(text=self.system_prompt)]))

        # Attached PDF files if any
        for uri in self.file_uris:
            contents.append(  # noqa: PERF401
                Content(
                    role="user",
                    parts=[Part(file_data=FileData(file_uri=uri, mime_type="application/pdf"))],
                ),
            )

        # User message
        contents.append(Content(role="user", parts=[Part(text=user_prompt)]))

        # Determine effective model and thinking level
        effective_model = model_name if model_name is not None else self.model_name
        effective_thinking = (
            ThinkingLevel(thinking_level.upper()) if thinking_level is not None else self.thinking_level
        )

        # Track the last used model and thinking level
        self.last_used_model = effective_model
        self.last_thinking_level = thinking_level.upper() if thinking_level is not None else self.thinking_level.name

        # Generate the content
        response = self.client.models.generate_content(
            model=effective_model,
            contents=contents,  # type: ignore
            config=GenerateContentConfig(
                temperature=self.temperature,
                thinking_config=ThinkingConfig(thinking_level=effective_thinking),
            ),
        )
        self.calculate_stats(response, effective_model)
        return response

    def __call__(
        self,
        user_prompt: str,
        pdf_local_path: str | None = None,
        model_name: str | None = None,
        thinking_level: Literal["LOW", "MEDIUM", "HIGH"] | None = None,
    ) -> str | None:
        """Send a prompt to Gemini, with optional system, PDF, and image inputs.

        Args:
            user_prompt (str): The user prompt to send to Gemini.
            pdf_local_path (Optional[str]): The local path to the PDF file to attach.
            model_name (str | None): Optional model name to override the default.
            thinking_level (Literal["LOW", "MEDIUM", "HIGH"] | None): Optional thinking level to override.

        Returns:
            str | None: The generated text response.
        """
        # Attach the PDF file if provided
        if pdf_local_path is not None:
            pdf_uri = self.bucket.upload_file(pdf_local_path)
            self.attach_pdf(pdf_uri)

        # Send the prompt to Gemini
        response = self.ask(user_prompt, model_name=model_name, thinking_level=thinking_level)

        # Remove the PDF file from the bucket
        if pdf_local_path is not None:
            self.clear_pdfs()
            self.bucket.remove_file(pdf_uri)

        return response.text
