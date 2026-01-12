"""arXiv paper fetcher."""

import re
import time
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from urllib import error, parse, request
from xml.etree import ElementTree as ET

from dateutil import parser  # type: ignore
from loguru import logger
from tqdm import tqdm  # type: ignore

from src.service.arxiv.arxiv_utils import (
    ARXIV_ID_REGEX,
    count_inclusive_days,
    deduplicate_papers_by_base_id,
    get_base_paper_id,
    iter_daily_ranges,
    safe_get_text,
    should_skip_collection_window,
)
from src.utils.schemas import Paper


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
            categories (list[str]): arXiv categories to search in.
            start_date (datetime): Start date for filtering papers.
            end_date (datetime): End date for filtering papers.

        Returns:
            str: The constructed arXiv query string.
        """
        category_clauses = [f"cat:{cat}" for cat in categories]
        query = f"({' OR '.join(category_clauses)})"
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
            with request.urlopen(url) as response:  # noqa: S310
                response_data = response.read().decode("utf-8")
        except error.HTTPError as exp:
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

    @classmethod
    def _extract_arxiv_id(cls, value: str) -> str | None:
        """Return a normalized arXiv ID if the provided value looks like one.

        Args:
            value (str): Any string potentially containing an arXiv identifier.

        Returns:
            str | None: A normalized identifier or None when the input is invalid.
        """
        normalized = value.strip()
        if not normalized:
            return None
        normalized = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", normalized, flags=re.IGNORECASE)
        normalized = normalized.removeprefix("arXiv:")
        normalized = normalized.rstrip("/")
        normalized = normalized.split("?")[0]
        normalized = normalized.removesuffix(".pdf")
        if ARXIV_ID_REGEX.match(normalized):
            return normalized
        return None

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
            url = self.base_url + parse.urlencode(query_params)
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

    def extract_paper_by_name_or_id(self, name_or_id: str) -> Paper:
        """Extract a paper by name or ID.

        Args:
            name_or_id (str): The name or ID of the paper.

        Returns:
            Paper: The paper.
        """
        cleaned_value = name_or_id.strip()
        arxiv_id = self._extract_arxiv_id(cleaned_value)
        if arxiv_id is not None:
            logger.info(f"Fetching paper by arXiv id: {arxiv_id}")
            query_params = {"id_list": arxiv_id}
        else:
            if not cleaned_value:
                msg = "Paper title is empty."
                raise ValueError(msg)
            logger.info(f"Fetching paper by title: {cleaned_value}")
            query_params = {
                "search_query": f'ti:"{cleaned_value}"',
                "start": "0",
                "max_results": "1",
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
        url = self.base_url + parse.urlencode(query_params)
        entities = self._extract_entities(url)
        if not entities:
            search_target = f"arXiv id '{arxiv_id}'" if arxiv_id else f"title '{cleaned_value}'"
            msg = f"No papers found for {search_target}."
            raise ValueError(msg)
        return self.parse_papers_info(entities)[0]


def fetch_papers_in_chunks(
    start_date_str: str,
    end_date_str: str,
    collection_start_date_str: str | None = None,
    collection_end_date_str: str | None = None,
    categories: list[str] | None = None,
) -> list[Paper]:
    """Fetches papers by breaking the date range into daily chunks to avoid API limitations.

    Args:
        start_date_str (str): Start date (YYYY-MM-DD) for filtering papers.
        end_date_str (str): End date (YYYY-MM-DD) for filtering papers.
        collection_start_date_str (str | None): Start date (YYYY-MM-DD) for filtering papers in the collection.
        collection_end_date_str (str | None): End date (YYYY-MM-DD) for filtering papers in the collection.
        categories (list[str] | None): List of arXiv categories to search in.

    Returns:
        list[Paper]: The list of papers.
    """
    fetcher = ArxivFetcher(page_size=500)
    if categories is None:
        categories = list(fetcher.predefined_categories)

    start_date_obj, end_date_obj = fetcher.check_start_end_dates_diff(start_date_str, end_date_str)
    collection_start_date_obj: datetime | None = None
    collection_end_date_obj: datetime | None = None
    if collection_start_date_str is not None and collection_end_date_str is not None:
        collection_start_date_obj, collection_end_date_obj = fetcher.check_start_end_dates_diff(
            collection_start_date_str,
            collection_end_date_str,
        )

    total_days = count_inclusive_days(start_date_obj, end_date_obj)
    all_papers: list[Paper] = []
    for current_start, current_end in tqdm(
        iter_daily_ranges(start_date_obj, end_date_obj),
        desc="Fetching papers day by day",
        total=total_days,
    ):
        if should_skip_collection_window(
            current_start,
            current_end,
            collection_start_date_obj,
            collection_end_date_obj,
        ):
            continue

        papers_for_day = fetcher.fetch_papers_for_period(
            start_date_obj=current_start,
            end_date_obj=current_end,
            categories=categories,
        )
        all_papers.extend(papers_for_day)

    return deduplicate_papers_by_base_id(all_papers)


def fetch_papers_day_by_day(
    start_date_str: str,
    end_date_str: str,
    collection_start_date_str: str | None = None,
    collection_end_date_str: str | None = None,
    categories: list[str] | None = None,
) -> Iterator[list[Paper]]:
    """Fetch papers as an iterator, yielding a list (batch) of all unique papers for each day.

    Args:
        start_date_str (str): Start date (YYYY-MM-DD) for filtering papers.
        end_date_str (str): End date (YYYY-MM-DD) for filtering papers.
        collection_start_date_str (str | None): Start date (YYYY-MM-DD) for filtering papers in the collection.
        collection_end_date_str (str | None): End date (YYYY-MM-DD) for filtering papers in the collection.
        categories (list[str] | None): List of arXiv categories to search in.

    Yields:
        Iterator[list[Paper]]: A list of unique Paper objects published on a given day.
    """
    fetcher = ArxivFetcher(page_size=200)
    if categories is None:
        categories = list(fetcher.predefined_categories)

    start_date_obj, end_date_obj = fetcher.check_start_end_dates_diff(start_date_str, end_date_str)
    collection_start_date_obj: datetime | None = None
    collection_end_date_obj: datetime | None = None
    if collection_start_date_str is not None and collection_end_date_str is not None:
        collection_start_date_obj, collection_end_date_obj = fetcher.check_start_end_dates_diff(
            collection_start_date_str,
            collection_end_date_str,
        )

    total_days = count_inclusive_days(start_date_obj, end_date_obj)
    for current_start, current_end in tqdm(
        iter_daily_ranges(start_date_obj, end_date_obj),
        desc="Fetching paper chunks by day",
        total=total_days,
    ):
        if should_skip_collection_window(
            current_start,
            current_end,
            collection_start_date_obj,
            collection_end_date_obj,
        ):
            continue

        papers_for_day = fetcher.fetch_papers_for_period(
            start_date_obj=current_start,
            end_date_obj=current_end,
            categories=categories,
        )

        unique_papers_for_day = []
        for paper in papers_for_day:
            base_id = get_base_paper_id(paper.paper_id)
            if base_id not in fetcher.seen_paper_ids:
                fetcher.seen_paper_ids.add(base_id)
                unique_papers_for_day.append(paper)

        if unique_papers_for_day:
            yield unique_papers_for_day
