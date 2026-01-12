"""Gemini Api Client."""

import json
import os

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
)
from loguru import logger

from src.service.ai_researcher.google_bucket import GoogleBucket
from src.utils.price_caculation import calculate_inference_price

load_dotenv()


class GeminiApiClient:
    """Gemini Api Client class."""

    prediction_timeout: int = 120
    location: str = "us-central1"

    def __init__(
        self,
        model_name: str = "gemini-2.5-pro",
        system_prompt: str | None = None,
        temperature: float = 0.3,
        thinking_budget: int | None = None,
        *,
        verbose: bool = False,
    ) -> None:
        """Initialize GeminiClient with Vertex AI connection, model, and defaults.

        Args:
            model_name: The model to use.
            system_prompt: The system prompt to use.
            temperature: The temperature to use.
            thinking_budget: The thinking budget to use.
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
        self.thinking_budget = thinking_budget if thinking_budget is not None else -1
        self._system_prompt = system_prompt
        self.file_uris: list[str] = []
        self.total_inference_price: float = 0.0
        self.total_requests: int = 0
        self.verbose = verbose

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

    def calculate_stats(self, response: GenerateContentResponse) -> None:
        """Calculate the stats for the response.

        Args:
            response (GenerateContentResponse): The response from Gemini.
        """
        # Calculate the stats
        prompt_token_count = getattr(response.usage_metadata, "prompt_token_count", 0)
        candidates_token_count = getattr(response.usage_metadata, "candidates_token_count", 0)
        thoughts_token_count = getattr(response.usage_metadata, "thoughts_token_count", 0)

        inference_price = calculate_inference_price(
            model_name=self.model_name,
            total_input_token_count=prompt_token_count,
            total_output_token_count=candidates_token_count + thoughts_token_count,
        )

        self.total_requests += 1
        self.total_inference_price += inference_price

    def attach_pdf(self, gcs_uri: str) -> None:
        """Attach a PDF (or text file) for native processing.

        Args:
            gcs_uri (str): The URI of the PDF file to attach.
        """
        self.file_uris.append(gcs_uri)

    def clear_pdfs(self) -> None:
        """Clear all attached document URIs."""
        self.file_uris = []

    def ask(self, user_prompt: str, thinking_budget: int | None = None) -> GenerateContentResponse:
        """Send a prompt to Gemini, with optional system, PDF, and image inputs.

        Args:
            user_prompt (str): The user prompt to send to Gemini.
            thinking_budget (Optional[int]): The thinking budget to use.

        Returns:
            GenerateContentResponse: The generated content response.
        """
        if thinking_budget is None:
            thinking_budget = self.thinking_budget

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

        # Generate the content
        return self.client.models.generate_content(
            model=self.model_name,
            contents=contents,  # type: ignore
            config=GenerateContentConfig(
                temperature=self.temperature,
                thinking_config=ThinkingConfig(thinking_budget=thinking_budget),
            ),
        )

    def __call__(self, user_prompt: str, pdf_local_path: str | None = None) -> str | None:
        """Send a prompt to Gemini, with optional system, PDF, and image inputs.

        Args:
            user_prompt (str): The user prompt to send to Gemini.
            pdf_local_path (Optional[str]): The local path to the PDF file to attach.

        Returns:
            str | None: The generated text response.
        """
        # Attach the PDF file if provided
        if pdf_local_path is not None:
            pdf_uri = self.bucket.upload_file(pdf_local_path)
            self.attach_pdf(pdf_uri)

        # Send the prompt to Gemini
        response = self.ask(user_prompt)
        self.calculate_stats(response)

        # Remove the PDF file from the bucket
        if pdf_local_path is not None:
            self.clear_pdfs()
            self.bucket.remove_file(pdf_uri)

        return response.text
