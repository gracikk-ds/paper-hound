"""Upload a Markdown file to a Notion database page."""

import os
import re
from datetime import date
from typing import Any

import requests
from loguru import logger

from src.service.notion_db.s3_loader import S3Uploader
from src.service.notion_db.utils import resolve_image_path
from src.settings import settings


class EmptyMarkdownTitleError(ValueError):
    """Raised when the paper title cannot be parsed from the markdown input."""

    def __init__(self) -> None:
        """Initialize the exception with a helpful default message."""
        super().__init__('Empty title parsed from markdown. Expected the first paper title line to start with "## ".')


class MarkdownToNotionUploader:
    """Read a Markdown file and upload its content as blocks to a Notion database page.

    Attributes:
        api_token (str): Notion API token.
        database_id (str): Notion database ID.
        base_url (str): Notion API base URL.
        headers (dict): Notion API headers.
    """

    def __init__(self, database_id: str = "228f6f75bb0b80babf73d46a6254a459") -> None:
        """Initialize the uploader with the provided database ID.

        Args:
            database_id (str): Notion database ID. Default is "228f6f75bb0b80babf73d46a6254a459"
        """
        self.api_token = settings.notion_token
        self.database_id = database_id
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        self.bucket = S3Uploader()

    def find_paper_page_url(self, arxiv_url: str, category: str | None = None) -> str | None:
        """Find an existing Notion page URL for a paper by its ArXiv (AlphaXiv) URL/id.

        Args:
            arxiv_url: Either a raw arXiv id (e.g. "2601.02242") or the full URL value
                that is stored in the Notion "Arxiv" URL property.
            category (str | None): The category of the paper to filter by.

        Returns:
            The Notion page URL if found, otherwise None.
        """
        url = f"{self.base_url}/databases/{self.database_id}/query"
        expected_url = (
            arxiv_url if arxiv_url.startswith(("http://", "https://")) else f"https://www.alphaxiv.org/abs/{arxiv_url}"
        )
        arxiv_filter: dict[str, Any] = {
            "property": "Arxiv",
            "url": {"equals": expected_url},
        }

        # If category is provided, ensure we only match pages with the same Category value.
        if category is not None:
            payload: dict[str, Any] = {
                "filter": {
                    "and": [
                        arxiv_filter,
                        {"property": "Category", "multi_select": {"contains": category}},
                    ],
                },
            }
        else:
            payload = {"filter": arxiv_filter}
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", []) or []
            if not results:
                return None
            # Notion returns the page URL at the top level.
            page_url = results[0].get("url")
            return page_url if isinstance(page_url, str) and page_url else None
        except Exception as exp:
            logger.error(f"Error checking if paper exists: {exp}")
            return None

    def find_paper_page(self, arxiv_url: str) -> dict[str, Any] | None:
        """Find an existing Notion page for a paper by its ArXiv URL/id.

        Args:
            arxiv_url: Either a raw arXiv id (e.g. "2601.02242") or the full URL value
                that is stored in the Notion "Arxiv" URL property.

        Returns:
            A dict with 'page_id', 'page_url', and 'categories' (list of str) if found,
            otherwise None.
        """
        url = f"{self.base_url}/databases/{self.database_id}/query"
        expected_url = (
            arxiv_url if arxiv_url.startswith(("http://", "https://")) else f"https://www.alphaxiv.org/abs/{arxiv_url}"
        )
        payload: dict[str, Any] = {
            "filter": {
                "property": "Arxiv",
                "url": {"equals": expected_url},
            },
        }
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", []) or []
            if not results:
                return None

            page = results[0]
            page_id = page.get("id")
            page_url = page.get("url")

            # Extract existing categories from multi_select property
            categories: list[str] = []
            props = page.get("properties", {})
            category_prop = props.get("Category", {})
            if category_prop.get("type") == "multi_select":
                for item in category_prop.get("multi_select", []):
                    name = item.get("name")
                    if name:
                        categories.append(name)
        except Exception as exp:
            logger.error(f"Error finding paper page: {exp}")
            return None
        else:
            return {
                "page_id": page_id,
                "page_url": page_url,
                "categories": categories,
            }

    def add_category_to_page(self, page_id: str, category: str) -> bool:
        """Add a category to an existing Notion page's multi_select Category property.

        Args:
            page_id: The Notion page ID.
            category: The category name to add.

        Returns:
            True if successful, False otherwise.
        """
        # First, fetch current categories
        url = f"{self.base_url}/pages/{page_id}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            page = response.json()

            # Extract existing categories
            existing_categories: list[str] = []
            props = page.get("properties", {})
            category_prop = props.get("Category", {})
            if category_prop.get("type") == "multi_select":
                for item in category_prop.get("multi_select", []):
                    name = item.get("name")
                    if name:
                        existing_categories.append(name)

            # Check if category already exists
            if category in existing_categories:
                logger.info(f"Category '{category}' already exists on page {page_id}")
                return True

            # Add new category to the list
            existing_categories.append(category)

            # Update the page with new categories
            update_payload: dict[str, Any] = {
                "properties": {
                    "Category": {"multi_select": [{"name": cat} for cat in existing_categories]},
                },
            }
            update_response = requests.patch(url, headers=self.headers, json=update_payload, timeout=30)
            update_response.raise_for_status()
            logger.info(f"Added category '{category}' to page {page_id}")
        except Exception as exp:
            logger.error(f"Error adding category to page {page_id}: {exp}")
            return False
        else:
            return True

    def _parse_rich_text(self, line: str) -> list[dict[str, Any]]:
        """Parse a line for **bold** markdown and return Notion rich_text objects.

        Args:
            line (str): Line of text to parse.

        Returns:
            List[Dict[str, Any]]: List of Notion rich_text objects.
        """
        segments = []
        pattern = r"\*\*(.+?)\*\*"
        last_end = 0

        for match in re.finditer(pattern, line):
            # Add normal text before the bold
            if match.start() > last_end:
                text = line[last_end : match.start()]
                if text:
                    segments.append(
                        {
                            "type": "text",
                            "text": {"content": text},
                        },
                    )
            # Add bold text
            bold_text = match.group(1)
            segments.append(
                {
                    "type": "text",
                    "text": {"content": bold_text},
                    "annotations": {
                        "bold": True,
                        "italic": False,
                        "strikethrough": False,
                        "underline": False,
                        "code": False,
                        "color": "default",
                    },
                },
            )
            last_end = match.end()

        # Add the rest of the text after the last match
        if last_end < len(line):
            text = line[last_end:]
            if text:
                segments.append({"type": "text", "text": {"content": text}})
        # If nothing matched, just return the line as normal text
        if not segments:
            segments.append({"type": "text", "text": {"content": line}})
        return segments

    def _parse_heading(self, line: str, blocks: list[dict[str, Any]]) -> bool:
        """Parse a heading and add it to the list of blocks.

        Args:
            line (str): Line of text to parse.
            blocks (List[Dict[str, Any]]): List of Notion blocks.

        Returns:
            bool: True if the line is a heading, False otherwise.
        """
        if line.startswith("# "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]},
                },
            )
            return True
        if line.startswith("## "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:]}}]},
                },
            )
            return True
        if line.startswith("### "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:]}}]},
                },
            )
            return True
        return False

    def _remove_meta_lines(self, line: str, *, lines_to_remove: bool) -> tuple[bool, bool]:
        """Check whether the line is a meta line.

        Args:
            line (str): Line of text to parse.
            lines_to_remove (bool): True if we in the meta lines block, False otherwise.

        Returns:
            tuple[bool, bool]: Should we skip the line, and whether we are in the meta lines block.
        """
        if line.startswith("---") and lines_to_remove:  # end of meta lines block
            lines_to_remove = False
            return True, lines_to_remove  # skip the line and end the meta lines block

        if line.startswith("---"):  # start of meta lines block
            lines_to_remove = True
            return True, lines_to_remove  # skip the line and start the meta lines block

        if lines_to_remove:
            return True, lines_to_remove  # skip the line and continue

        return False, lines_to_remove  # don't skip the line and continue

    def _upload_image(self, local_path: str, blocks: list[dict[str, Any]]) -> None:
        """Upload an image to S3 and add it to the blocks.

        Args:
            local_path (str): Path to the image.
            blocks (list[dict[str, Any]]): List of Notion blocks.
        """
        s3_key = os.path.join(*os.path.normpath(local_path).split(os.sep)[-2:])  # noqa: PTH206
        public_url = self.bucket.upload_file(local_path, s3_key)
        blocks.append(
            {
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {"url": public_url},
                },
            },
        )

    def markdown_to_blocks(
        self,
        markdown: str,
    ) -> tuple[list[dict[str, Any]], str, str, str, list[str]]:
        """Convert basic Markdown text to Notion blocks. Support headings, paragraphs, bullet points.

        Args:
            markdown (str): Markdown text to convert.

        Returns:
            List[Dict[str, Any]]: List of Notion blocks.
            str: ArXiv URL.
            str: Published date.
            str: Title.
            list[str]: Authors.
        """
        lines = markdown.splitlines()
        blocks: list[dict[str, Any]] = []
        lines_to_remove = False
        first_heading = True
        title = ""
        arxiv_url = ""
        published_date = "2022-01-01"
        authors = []

        for line in lines:
            line = line.rstrip()  # noqa: PLW2901

            # Check if the line is a meta line
            skip_line, lines_to_remove = self._remove_meta_lines(line, lines_to_remove=lines_to_remove)
            if skip_line:
                continue

            if first_heading and line.startswith("## "):
                first_heading = False
                title = line[3:]
                continue

            if line.startswith("**ArXiv URL:**"):
                arxiv_url = line.split("**ArXiv URL:**")[1].strip()
                continue

            if line.startswith("**Published Date:**"):
                published_date = line.split("**Published Date:**")[1].strip()
                continue

            if line.startswith("**Authors:**"):
                try:
                    authors = eval(line.split("**Authors:**")[1].strip())  # noqa: S307
                except Exception as exp:
                    logger.warning(f"Error parsing authors: {exp}")
                    authors = []
                continue

            # Parse images
            local_path = resolve_image_path(line)
            if local_path:
                self._upload_image(local_path, blocks)
                continue

            # Parse headings
            if self._parse_heading(line, blocks):
                continue

            # Parse bullet points
            if line.startswith(("- ", "* ")):
                # Bullet list item
                blocks.append(
                    {
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": self._parse_rich_text(line[2:])},
                    },
                )
            elif line == "":
                continue
            else:
                # Parse paragraphs
                blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": self._parse_rich_text(line)},
                    },
                )
        return blocks, arxiv_url, published_date, title, authors

    def upload_markdown_file(self, file_path: str, category: str = "Image Editing") -> str:
        """Read the markdown file, convert to Notion blocks, and upload as a new page.

        Args:
            file_path (str): Path to the markdown file.
            category (str): Category of the paper.

        Returns:
            str: URL of the created Notion page.
        """
        with open(file_path, encoding="utf-8") as file:
            markdown = file.read()

        blocks, arxiv_url, published_date, title, authors = self.markdown_to_blocks(markdown)

        # Notion is strict about property payloads:
        # - Title content cannot be empty
        # - URL must be a valid URL (empty string often fails validation)
        # - Date must be ISO format (YYYY-MM-DD)
        title = (title or "").strip()
        if not title:
            raise EmptyMarkdownTitleError

        properties: dict[str, Any] = {
            "Category": {"multi_select": [{"name": category}]},
            "Status": {"select": {"name": "Inbox"}},
        }

        arxiv_url = (arxiv_url or "").strip()
        if arxiv_url:
            # Normalize plain arXiv ids into the URL format used in this DB.
            if not arxiv_url.startswith(("http://", "https://")):
                arxiv_url = f"https://www.alphaxiv.org/abs/{arxiv_url}"
            properties["Arxiv"] = {"url": arxiv_url}

        published_date = (published_date or "").strip()
        if published_date:
            try:
                # Validates YYYY-MM-DD; raises ValueError if invalid.
                date.fromisoformat(published_date.split("T")[0])
                properties["Published"] = {"date": {"start": published_date}}
            except ValueError:
                logger.warning(f"Skipping invalid Published date (expected YYYY-MM-DD): {published_date!r}")

        cleaned_authors: list[str] = []
        for author in authors or []:
            if isinstance(author, str):
                a = author.strip()
                if a:
                    cleaned_authors.append(a[:100])
        if cleaned_authors:
            properties["Authors"] = {"multi_select": [{"name": author} for author in cleaned_authors]}

        data = {
            "parent": {"database_id": self.database_id},
            "properties": {"Paper name": {"title": [{"text": {"content": title}}]}, **properties},
            "children": blocks,
        }
        url = f"{self.base_url}/pages"

        response = requests.post(url, headers=self.headers, json=data, timeout=60)
        if not response.ok:
            # Notion includes the actual validation error details in the response body; log them for debugging.
            logger.error(
                "Notion create page failed "
                f"(status={response.status_code}, url={url}, body={response.text}, payload={data})",
            )
        response.raise_for_status()
        page = response.json()
        return page.get("url", "")
