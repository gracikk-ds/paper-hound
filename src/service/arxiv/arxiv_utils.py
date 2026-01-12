"""arXiv utilities."""

import re
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

from src.utils.schemas import Paper

ARXIV_ID_REGEX = re.compile(
    r"""
        ^
        (
            (?:\d{4}\.\d{4,5})(?:v\d+)?  # New style IDs, e.g. 2401.01234v2
            |
            (?:[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?  # Legacy IDs, e.g. cs/0501001
        )
        $
        """,
    re.IGNORECASE | re.VERBOSE,
)


def safe_get_text(element: ET.Element, tag: str, default: str = "") -> str:
    """Get the text of an element, or return a default value if the element is not found.

    Args:
        element (ET.Element): The element to get the text from.
        tag (str): The tag of the element to get the text from.
        default (str): The default value to return if the element is not found.

    Returns:
        str: Text contained in the requested tag or the provided default.
    """
    found_element = element.find(tag)
    return found_element.text if found_element is not None else default  # type: ignore


def count_inclusive_days(start_date_obj: datetime, end_date_obj: datetime) -> int:
    """Return the inclusive number of days between two datetimes.

    Args:
        start_date_obj (datetime): Start of the interval.
        end_date_obj (datetime): End of the interval.

    Returns:
        int: Total number of days, including both bounds.
    """
    return (end_date_obj - start_date_obj).days + 1


def iter_daily_ranges(
    start_date_obj: datetime,
    end_date_obj: datetime,
) -> Iterator[tuple[datetime, datetime]]:
    """Yield (start, end) datetimes that cover each day in the interval.

    Args:
        start_date_obj (datetime): Inclusive lower bound of the period.
        end_date_obj (datetime): Inclusive upper bound of the period.

    Yields:
        Iterator[tuple[datetime, datetime]]: Tuples describing one day's time span.
    """
    current_start = start_date_obj
    while current_start <= end_date_obj:
        current_end = min(end_date_obj, current_start + timedelta(days=1) - timedelta(seconds=1))
        yield current_start, current_end
        current_start += timedelta(days=1)


def should_skip_collection_window(
    window_start: datetime,
    window_end: datetime,
    collection_start: datetime | None,
    collection_end: datetime | None,
) -> bool:
    """Return whether a window is fully inside the collection exclusion window.

    Args:
        window_start (datetime): Start of the currently processed window.
        window_end (datetime): End of the currently processed window.
        collection_start (datetime | None): Start of the exclusion window.
        collection_end (datetime | None): End of the exclusion window.

    Returns:
        bool: True if the window should be skipped, False otherwise.
    """
    if collection_start is None or collection_end is None:
        return False
    return collection_start <= window_start and window_end <= collection_end


def get_base_paper_id(paper_id: str) -> str:
    """Return the base arXiv identifier (without version suffix).

    Args:
        paper_id (str): The arXiv identifier, possibly with a version suffix.

    Returns:
        str: The identifier stripped of any version suffix.
    """
    return paper_id.split("v", 1)[0]


def deduplicate_papers_by_base_id(papers: Iterable[Paper]) -> list[Paper]:
    """Return papers with the latest version for each base arXiv id.

    Args:
        papers (Iterable[Paper]): Papers potentially containing multiple versions.

    Returns:
        list[Paper]: One paper per base id, keeping the last occurrence.
    """
    unique_by_id: dict[str, Paper] = {}
    for paper in papers:
        base_id = get_base_paper_id(paper.paper_id)
        unique_by_id[base_id] = paper
    return list(unique_by_id.values())
