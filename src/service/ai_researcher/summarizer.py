"""Summarizer for research papers."""

from pathlib import Path

from loguru import logger

from src.service.ai_researcher.gemini_client import GeminiApiClient
from src.utils.schemas import Paper


class Summarizer:
    """Summarizer for research papers."""

    def __init__(self, llm_client: GeminiApiClient, path_to_prompt: str) -> None:
        """Initialize the summarizer.

        Args:
            llm_client (GeminiApiClient): The Gemini API client.
            path_to_prompt (str): The path to the prompt file.
        """
        self.total_price: float = 0.0
        self.inference_price: float = 0.0
        self.llm_client = llm_client
        with open(path_to_prompt, encoding="utf-8") as file:
            self.default_prompt = file.read()

    def summarize(
        self,
        paper: Paper,
        pdf_path: Path,
        summarizer_prompt: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Summarize a research paper.

        Args:
            paper (Paper): The paper to summarize.
            pdf_path (Path): The path to the PDF file.
            summarizer_prompt (str | None): The prompt to use for the summarizer.

        Returns:
            tuple[str | None, str | None]: The summary text and the path to the markdown file.
        """
        prompt = summarizer_prompt if summarizer_prompt is not None else self.default_prompt

        response_text = self.llm_client(prompt, pdf_local_path=str(pdf_path))
        self.inference_price = self.llm_client.inference_price
        self.total_price += self.inference_price
        logger.info(f"Summarizer inference price: {self.llm_client.inference_price}")

        if response_text is None:
            return None, None

        file_name = f"{paper.title.replace(' ', '_').lower()}_summary.md"
        md_path = Path("tmp_storage/tmp_mds") / file_name
        md_path.parent.mkdir(parents=True, exist_ok=True)

        with open(md_path, mode="w", encoding="utf-8") as file:
            file.write(response_text)

        return response_text, str(md_path)
