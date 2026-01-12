"""Classifier for research papers."""

from src.service.ai_researcher.gemini_client import GeminiApiClient


class Classifier:
    """Classifier for research papers."""

    def __init__(self, llm_client: GeminiApiClient, path_to_prompt: str) -> None:
        """Initialize the classifier.

        Args:
            llm_client (GeminiApiClient): The Gemini API client.
            path_to_prompt (str): The path to the prompt file.
        """
        self.llm_client = llm_client
        with open(path_to_prompt) as file:
            system_prompt = file.read()
        self.llm_client.system_prompt = system_prompt

    @property
    def system_prompt(self) -> str:
        """Get the system prompt.

        Returns:
            str: The system prompt.
        """
        return self.llm_client.system_prompt

    @system_prompt.setter
    def system_prompt(self, prompt: str) -> None:
        """Set the system prompt.

        Args:
            prompt (str): The system prompt to use.
        """
        self.llm_client.system_prompt = prompt

    def classify(
        self,
        title: str,
        summary: str,
        system_prompt: str | None = None,
    ) -> bool:
        """Classify a research paper.

        Args:
            title (str): The title of the research paper.
            summary (str): The summary of the research paper.
            full_date (str): The full date of the research paper.
            system_prompt (str | None): The system prompt to use.

        Returns:
            bool: True if the paper is about generative image editing, False otherwise.
        """
        if system_prompt is not None:
            self.system_prompt = system_prompt
        prompt = f"Title: {title}\nSummary: {summary}"
        response = self.llm_client.ask(prompt).text
        return response is not None and response.lower() == "yes"
