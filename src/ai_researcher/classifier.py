"""Classifier for research papers."""

import os

from loguru import logger

from src.ai_researcher.gemini_researcher import GeminiApiClient


class Classifier:
    """Classifier for research papers."""

    def __init__(
        self,
        path_to_prompt: str,
        skipped_file_path: str = "data/skipped/skipped_papers_by_classifier.txt",
    ) -> None:
        """Initialize the classifier.

        Args:
            path_to_prompt (str): The path to the prompt file.
            skipped_file_path (str): The path to the file to save the skipped papers to.
        """
        self.gemini_researcher = GeminiApiClient(model_name="gemini-2.5-pro")
        with open(path_to_prompt) as file:
            system_prompt = file.read()
        self.gemini_researcher.system_prompt = system_prompt
        self.skipped_file_path = skipped_file_path

    @property
    def system_prompt(self) -> str:
        """Get the system prompt.

        Returns:
            str: The system prompt.
        """
        return self.gemini_researcher.system_prompt

    @system_prompt.setter
    def system_prompt(self, prompt: str) -> None:
        """Set the system prompt.

        Args:
            prompt (str): The system prompt to use.
        """
        self.gemini_researcher.system_prompt = prompt

    def classify(
        self,
        title: str,
        summary: str,
        full_date: str,
        system_prompt: str | None = None,
    ) -> tuple[bool, str | None]:
        """Classify a research paper.

        Args:
            title (str): The title of the research paper.
            summary (str): The summary of the research paper.
            full_date (str): The full date of the research paper.
            system_prompt (str | None): The system prompt to use.

        Returns:
            Tuple[bool, Optional[str]]: Whether the paper is about generative image editing.
        """
        if system_prompt is not None:
            self.system_prompt = system_prompt

        prompt = f"Title: {title}\nSummary: {summary}"
        if self.gemini_researcher.ask(prompt).lower() == "yes":
            return False, None
        logger.info(f"Skipping paper {title} because it is not about generative image editing")
        skipped_dir = os.path.dirname(self.skipped_file_path)
        os.makedirs(skipped_dir, exist_ok=True)
        skipped_file_name = os.path.basename(self.skipped_file_path).split(".")[0]
        path_to_save = os.path.join(skipped_dir, f"{skipped_file_name}_{full_date}.txt")
        with open(path_to_save, "a") as file:
            file.write(f"{title}\n")
        return True, path_to_save
