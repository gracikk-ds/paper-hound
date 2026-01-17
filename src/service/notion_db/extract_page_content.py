"""Extract information from a Notion page using the Notion API.

Link to API page: https://www.notion.so/profile/integrations/internal/4332f261-a4c4-4579-8635-14617fae08bc
"""

from typing import Any

import requests

from src.settings import settings


class NotionPageExtractor:
    """Class to extract information from a Notion page using the Notion API.

    Attributes:
        api_token (str): Integration token for authenticating with the Notion API.
        base_url (str): Base URL for Notion API endpoints.
        headers (dict): Headers for the Notion API requests.

    Methods:
        get_page(page_id): Returns page properties as a dictionary.
        get_blocks(page_id): Returns a list of blocks (content) for a given page.
        extract_text_from_blocks(blocks): Extracts and concatenates text from blocks.
    """

    def __init__(self) -> None:
        """Initialize with the provided Notion integration token."""
        self.api_token = settings.notion_token
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    def get_page(self, page_id: str) -> dict[str, Any]:
        """Fetch the properties of a Notion page.

        Args:
            page_id (str): The ID of the Notion page.

        Returns:
            dict: Dictionary of page properties.
        """
        url = f"{self.base_url}/pages/{page_id}"
        response = requests.get(url, headers=self.headers, timeout=60)
        response.raise_for_status()
        return response.json()

    def get_blocks(self, page_id: str, page_size: int = 100) -> list[dict[str, Any]]:
        """Retrieve the content blocks of a Notion page.

        Args:
            page_id (str): The ID of the Notion page.
            page_size (int): Number of blocks to fetch per request (max 100).

        Returns:
            list: List of block objects.
        """
        blocks = []
        url = f"{self.base_url}/blocks/{page_id}/children?page_size={page_size}"
        while url:
            response = requests.get(url, headers=self.headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            blocks.extend(data.get("results", []))
            url = data.get("next_cursor")
            if url:
                url = f"{self.base_url}/blocks/{page_id}/children?start_cursor={url}&page_size={page_size}"
        return blocks

    def query_database(self, database_id: str) -> list[str]:
        """Query a database to retrieve its pages (items).

        Args:
            database_id (str): The ID of the Notion database.

        Returns:
            list: List of page IDs.
        """
        results = []
        url = f"{self.base_url}/databases/{database_id}/query"
        has_more = True
        start_cursor = None

        while has_more:
            payload = {}
            if start_cursor:
                payload["start_cursor"] = start_cursor

            response = requests.post(url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            results.extend(data.get("results", []))
            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

        return [page["id"] for page in results]

    @staticmethod
    def extract_text_from_block(block: dict[str, Any]) -> str:
        """Extract and concatenate plain text from Notion blocks.

        Args:
            block (dict[str, Any]): Notion block object.

        Returns:
            str: Concatenated text extracted from the blocks.
        """
        texts = []
        block_type = block.get("type")
        if block_type and block_type in block:
            rich_text = block[block_type].get("rich_text", [])
            for text in rich_text:
                plain_text = text.get("plain_text")
                if plain_text:
                    texts.append(plain_text)
        return "\n".join(texts)

    def extract_settings_from_page(self, page_id: str) -> dict[str, Any] | None:
        """Extract settings from a Notion page.

        Args:
            page_id (str): The ID of the Notion page.

        Returns:
            dict: Dictionary of settings.
        """
        blocks = self.get_blocks(page_id)
        settings = {"Query Prompt": None, "Classifier Prompt": None}
        current_setting = None
        for block in blocks:
            block_type = block.get("type")
            block_text = self.extract_text_from_block(block)
            if block_type == "heading_1" and block_text in settings:
                current_setting = block_text
                continue

            if current_setting is not None:
                settings[current_setting] = block_text
                current_setting = None

        if any(value is None for value in settings.values()):
            return None

        settings["Page Name"] = (
            self.get_page(page_id).get("properties", {}).get("Name", {}).get("title", [{}])[0].get("plain_text")
        )
        return settings
