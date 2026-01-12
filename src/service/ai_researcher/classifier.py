"""Classifier for research papers."""

from src.ai_researcher.gemini_researcher import GeminiApiClient


class Classifier:
    """Classifier for research papers."""

    def __init__(self, llm_client: GeminiApiClient, path_to_prompt: str) -> None:
        """Initialize the classifier.

        Args:
            llm_client (GeminiApiClient): The Gemini API client.
            path_to_prompt (str): The path to the prompt file.
        """
        self.gemini_researcher = llm_client
        with open(path_to_prompt) as file:
            system_prompt = file.read()
        self.gemini_researcher.system_prompt = system_prompt

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
        return self.gemini_researcher.ask(prompt).lower() == "yes"
