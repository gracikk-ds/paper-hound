"""Summarizer for research papers."""

from pathlib import Path
from typing import Literal

from loguru import logger

from src.service.ai_researcher.gemini_client import GeminiApiClient
from src.utils.schemas import Paper


class Summarizer:
    """Summarizer for research papers."""

    def __init__(self, llm_client: GeminiApiClient, path_to_prompt: str, tmp_storage_dir: str) -> None:
        """Initialize the summarizer.

        Args:
            llm_client (GeminiApiClient): The Gemini API client.
            path_to_prompt (str): The path to the prompt file.
            tmp_storage_dir (str): The path to the temporary storage directory.
        """
        self.total_price: float = 0.0
        self.inference_price: float = 0.0
        self.llm_client = llm_client
        self.tmp_storage_dir = tmp_storage_dir
        with open(path_to_prompt, encoding="utf-8") as file:
            self.default_prompt = file.read()

    def summarize(
        self,
        paper: Paper,
        pdf_path: Path,
        model_name: str | None = None,
        thinking_level: Literal["LOW", "MEDIUM", "HIGH"] | None = None,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        """Summarize a research paper.

        Args:
            paper (Paper): The paper to summarize.
            pdf_path (Path): The path to the PDF file.
            model_name (str | None): Optional model name to override the default.
            thinking_level (Literal["LOW", "MEDIUM", "HIGH"] | None): Optional thinking level to override.

        Returns:
            tuple[str | None, str | None, str | None, str | None]: The summary text, path to markdown file,
                model name used, and thinking level used.
        """
        response_text = self.llm_client(
            self.default_prompt,
            pdf_local_path=str(pdf_path),
            model_name=model_name,
            thinking_level=thinking_level,
        )
        self.inference_price = self.llm_client.inference_price
        self.total_price += self.inference_price
        logger.info(f"Summarizer inference price: {self.llm_client.inference_price}")

        if response_text is None:
            return None, None, None, None

        file_name = f"{paper.title.replace(' ', '_').lower()}_summary.md"
        md_path = Path(self.tmp_storage_dir) / file_name
        md_path.parent.mkdir(parents=True, exist_ok=True)

        with open(md_path, mode="w", encoding="utf-8") as file:
            file.write(response_text)

        return response_text, str(md_path), self.llm_client.last_used_model, self.llm_client.last_thinking_level
