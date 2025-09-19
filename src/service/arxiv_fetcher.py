"""arXiv paper fetcher."""

import time
import urllib.request
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from dateutil import parser  # type: ignore
from loguru import logger
from tqdm import tqdm  # type: ignore

from src.utils.schemas import Paper


def safe_get_text(element: ET.Element, tag: str, default: str = "") -> str:
    """Get the text of an element, or return a default value if the element is not found.

    Args:
        element (ET.Element): The element to get the text from.
        tag (str): The tag of the element to get the text from.
        default (str): The default value to return if the element is not found.
    """
    found_element = element.find(tag)
    return found_element.text if found_element is not None else default  # type: ignore


class ArxivFetcher:
    """Class to fetch and filter arXiv papers based on keywords, categories, and date range."""

    predefined_categories: tuple[str, str, str] = ("cs.CV", "cs.LG", "cs.AI")
    base_url: str = "http://export.arxiv.org/api/query?"
    atom_namespace = "{http://www.w3.org/2005/Atom}"

    def __init__(self, page_size: int = 50) -> None:
        """Initialize the ArxivFetcher with search parameters.

        Args:
            page_size (int): Number of results per page for the arXiv client.
        """
        self.page_size = page_size
        self.seen_paper_ids: set[str] = set()

    def _build_arxiv_query(
        self,
        categories: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> str:
        """Build a boolean query string that conforms to the arXiv API grammar.

        Args:
            keywords (List[str]): List of keywords to search for.
            categories (List[str]): List of arXiv categories to search in.
            start_date (datetime): Start date for filtering papers.
            end_date (datetime): End date for filtering papers.

        Returns:
            str: The constructed arXiv query string.
        """
        category_clauses = [f"cat:{cat}" for cat in categories]
        query = f"({' OR '.join(category_clauses)})"
        end_date = end_date + timedelta(days=1) - timedelta(seconds=1)
        start = start_date.strftime("%Y%m%d%H%M%S")
        end = end_date.strftime("%Y%m%d%H%M%S")
        date_clause = f" AND submittedDate:[{start} TO {end}]"
        return f"{query}{date_clause}"

    def check_start_end_dates_diff(self, start_date: str, end_date: str) -> tuple[datetime, datetime]:
        """Check if the start and end dates are valid.

        Args:
            start_date (str): Start date (YYYY-MM-DD) for filtering papers.
            end_date (str): End date (YYYY-MM-DD) for filtering papers.

        Raises:
            ValueError: The start date is after the end date.

        Returns:
            tuple[datetime, datetime]: The start and end dates as datetime objects.
        """
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").astimezone(timezone.utc)
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").astimezone(timezone.utc)
        if start_date_obj > end_date_obj:
            msg = "Start date must be before end date."
            raise ValueError(msg)
        return start_date_obj, end_date_obj

    def _get_main_authors(
        self,
        authors: list[str],
    ) -> list[str]:
        """Get the main authors from the list of authors.

        Args:
            authors (list[str]): The list of authors names.

        Returns:
            list[str]: The list of authors names.
        """
        if len(authors) > 1:
            return [authors[0], authors[-1]]
        return authors

    def _extract_entities(self, url: str) -> list[ET.Element]:
        """Extract entities from the XML response.

        Args:
            url (str): The URL to extract entities from.

        Returns:
            list[ET.Element]: The list of entities.
        """
        try:
            # Make the API request
            with urllib.request.urlopen(url) as response:  # noqa: S310
                response_data = response.read().decode("utf-8")
        except urllib.error.HTTPError as exp:
            logger.error(f"HTTP Error: {exp.code} {exp.reason} for URL: {url}")
            return []

        # Parse the XML response (Atom feed)
        root = ET.fromstring(response_data)  # noqa: S314
        return root.findall(f"{self.atom_namespace}entry")

    def parse_papers_info(self, entities: list[ET.Element]) -> list[Paper]:
        """Parse the papers information from the XML response.

        Args:
            entities (list[ET.Element]): The list of entities.

        Returns:
            list[Paper]: The list of papers.
        """
        papers: list[Paper] = []
        for entry in entities:
            # Extract metadata for each paper
            paper_id = safe_get_text(entry, f"{self.atom_namespace}id").split("/abs/")[-1]
            title = safe_get_text(entry, f"{self.atom_namespace}title").strip().replace("\n", " ")
            summary = safe_get_text(entry, f"{self.atom_namespace}summary").strip().replace("\n", " ")
            published = safe_get_text(entry, f"{self.atom_namespace}published")
            published_date_ts = parser.isoparse(published).timestamp()
            updated = safe_get_text(entry, f"{self.atom_namespace}updated")
            updated_date_ts = parser.isoparse(updated).timestamp()

            authors = [
                safe_get_text(author, f"{self.atom_namespace}name")
                for author in entry.findall(f"{self.atom_namespace}author")
            ]
            authors = self._get_main_authors(authors)

            pdf_link = ""
            for link in entry.findall(f"{self.atom_namespace}link"):
                if link.get("title") == "pdf":
                    pdf_link = link.get("href", "")
                    break

            primary_category = entry.find("{http://arxiv.org/schemas/atom}primary_category")
            primary_category_str = primary_category.get("term", "") if primary_category is not None else ""

            papers.append(
                Paper(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    summary=summary,
                    published_date=published,
                    published_date_ts=published_date_ts,
                    updated_date=updated,
                    updated_date_ts=updated_date_ts,
                    pdf_url=pdf_link,
                    primary_category=primary_category_str,
                ),
            )
        return papers

    def fetch_papers_for_period(
        self,
        start_date_obj: datetime,
        end_date_obj: datetime,
        categories: list[str],
    ) -> list[Paper]:
        """Fetch papers for a specific and short period.

        Args:
            start_date_obj (datetime): Start date for filtering papers.
            end_date_obj (datetime): End date for filtering papers.
            categories (list[str]): List of arXiv categories to search in.

        Returns:
            list[Paper]: The list of papers.

        Raises:
            ValueError: The start date is after the end date.
            HTTPError: The HTTP error occurred while fetching the papers.
            Exception: The exception occurred while fetching the papers.
        """
        search_query = self._build_arxiv_query(categories, start_date_obj, end_date_obj)
        logger.info(f"Querying for date range: {start_date_obj.date()} to {end_date_obj.date()}")

        if end_date_obj - start_date_obj > timedelta(days=3):
            logger.warning("Fetching papers for a period longer than 3 days. API output may be incomplete.")

        papers = []
        start_index = 0
        while True:
            query_params = {
                "search_query": search_query,
                "start": start_index,
                "max_results": self.page_size,
                "sortBy": "submittedDate",
                "sortOrder": "ascending",
            }
            url = self.base_url + urllib.parse.urlencode(query_params)  # type: ignore
            entities = self._extract_entities(url)
            if not entities:
                break

            papers.extend(self.parse_papers_info(entities))
            start_index += len(entities)

            # If we received less papers than requested, this is the last page
            if len(entities) < self.page_size:
                break

            # Be polite to the API
            time.sleep(3)
        return papers


def fetch_papers_in_chunks(
    start_date_str: str,
    end_date_str: str,
    categories: list[str] | None = None,
) -> list[Paper]:
    """Fetches papers by breaking the date range into daily chunks to avoid API limitations."""
    fetcher = ArxivFetcher(page_size=500)
    if categories is None:
        categories = list(fetcher.predefined_categories)

    start_date_obj, end_date_obj = fetcher.check_start_end_dates_diff(start_date_str, end_date_str)

    all_papers = []
    total_days = (end_date_obj - start_date_obj).days + 1

    # Iterate over days
    for day_offset in tqdm(range(total_days), desc="Fetching papers day by day"):
        current_date = start_date_obj + timedelta(days=day_offset)

        # Request papers for one day
        papers_for_day = fetcher.fetch_papers_for_period(
            start_date_obj=current_date,
            end_date_obj=current_date,
            categories=categories,
        )

        if papers_for_day:
            all_papers.extend(papers_for_day)

        # Small pause between requests for different days, to be polite to the API
        if day_offset < total_days - 1:
            time.sleep(3)

    # Remove duplicates that may have appeared due to versioning of papers
    unique_papers = {paper.paper_id.split("v")[0]: paper for paper in all_papers}.values()
    return list(unique_papers)


def fetch_papers_day_by_day(
    start_date_str: str,
    end_date_str: str,
    categories: list[str] | None = None,
) -> Iterator[list[Paper]]:
    """Fetch papers as an iterator, yielding a list (batch) of all unique papers for each day.

    Yields:
        Iterator[list[Paper]]: A list of unique Paper objects published on a given day.
    """
    fetcher = ArxivFetcher(page_size=200)
    if categories is None:
        categories = list(fetcher.predefined_categories)

    start_date_obj, end_date_obj = fetcher.check_start_end_dates_diff(start_date_str, end_date_str)

    total_days = (end_date_obj - start_date_obj).days + 1

    for day_offset in tqdm(range(total_days), desc="Fetching paper chunks by day"):
        current_date = start_date_obj + timedelta(days=day_offset)

        papers_for_day = fetcher.fetch_papers_for_period(
            start_date_obj=current_date,
            end_date_obj=current_date,
            categories=categories,
        )

        # Filter out any papers we might have already seen
        unique_papers_for_day = []
        for paper in papers_for_day:
            base_id = paper.paper_id.split("v")[0]
            if base_id not in fetcher.seen_paper_ids:
                fetcher.seen_paper_ids.add(base_id)
                unique_papers_for_day.append(paper)

        # Only yield if we found new, unique papers for this day
        if unique_papers_for_day:
            yield unique_papers_for_day

        if day_offset < total_days - 1:
            time.sleep(3)
