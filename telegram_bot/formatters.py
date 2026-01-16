"""Message formatting utilities for Telegram bot."""

from src.utils.schemas import Paper

MAX_AUTHORS_TO_DISPLAY: int = 3
MAX_ABSTRACT_LENGTH: int = 800


def format_paper_short(paper: Paper, index: int | None = None) -> str:
    """Format a paper for display in search results.

    Args:
        paper: The paper to format.
        index: Optional index number for numbered lists.

    Returns:
        Formatted paper string with title, authors, and date.
    """
    prefix = f"{index}\\. " if index is not None else ""
    authors = ", ".join(paper.authors[:MAX_AUTHORS_TO_DISPLAY])
    if len(paper.authors) > MAX_AUTHORS_TO_DISPLAY:
        authors += " et al."

    published_date = _escape_markdown(paper.published_date[:10])
    return (
        f"{prefix}*{_escape_markdown(paper.title)}*\n"
        f"_{_escape_markdown(authors)}_\n"
        f"Published: {published_date} \\| Category: `{paper.primary_category}`"
    )


def format_paper_detailed(paper: Paper) -> str:
    """Format a paper with full details including abstract.

    Args:
        paper: The paper to format.

    Returns:
        Formatted paper string with all details.
    """
    authors = ", ".join(paper.authors[:MAX_AUTHORS_TO_DISPLAY])
    if len(paper.authors) > MAX_AUTHORS_TO_DISPLAY:
        authors += f" et al. ({len(paper.authors)} authors)"

    # Truncate abstract if too long
    abstract = paper.summary
    if len(abstract) > MAX_ABSTRACT_LENGTH:
        abstract = abstract[:MAX_ABSTRACT_LENGTH] + "..."

    published_date = _escape_markdown(paper.published_date[:10])
    updated_date = _escape_markdown(paper.updated_date[:10])
    return (
        f"*{_escape_markdown(paper.title)}*\n\n"
        f"*Authors:* {_escape_markdown(authors)}\n"
        f"*Published:* {published_date}\n"
        f"*Updated:* {updated_date}\n"
        f"*Category:* `{paper.primary_category}`\n"
        f"*arXiv ID:* `{paper.paper_id}`\n\n"
        f"*Abstract:*\n{_escape_markdown(abstract)}"
    )


def format_search_results(papers: list[Paper], query: str) -> str:
    """Format search results for display.

    Args:
        papers: List of papers from search.
        query: The search query used.

    Returns:
        Formatted search results message.
    """
    if not papers:
        return f"No papers found for query: _{_escape_markdown(query)}_"

    header = f"Found {len(papers)} paper\\(s\\) for: _{_escape_markdown(query)}_\n\n"
    paper_lines = [format_paper_short(p, i + 1) for i, p in enumerate(papers)]
    return header + "\n\n".join(paper_lines)


def format_similar_results(papers: list[Paper], source_paper_id: str) -> str:
    """Format similar papers results.

    Args:
        papers: List of similar papers.
        source_paper_id: The paper ID used as reference.

    Returns:
        Formatted similar papers message.
    """
    if not papers:
        return f"No similar papers found for: `{source_paper_id}`"

    header = f"Papers similar to `{source_paper_id}`:\n\n"
    paper_lines = [format_paper_short(p, i + 1) for i, p in enumerate(papers)]
    return header + "\n\n".join(paper_lines)


def format_stats(paper_count: int) -> str:
    """Format database statistics.

    Args:
        paper_count: Total number of papers in database.

    Returns:
        Formatted stats message.
    """
    return f"*Database Statistics*\n\nTotal papers indexed: `{paper_count}`"


def format_subscription_notification(
    query: str,
    papers: list[tuple[Paper, str | None]],
) -> str:
    """Format notification for new papers matching subscription.

    Args:
        query: The subscription query.
        papers: List of tuples (paper, notion_url).

    Returns:
        Formatted notification message.
    """
    header = f"*New papers matching your subscription:*\n_{_escape_markdown(query)}_\n\n"
    lines = []
    for i, (paper, notion_url) in enumerate(papers, 1):
        line = f"{i}\\. *{_escape_markdown(paper.title)}*"
        if notion_url:
            line += f"\n   [View Summary on Notion]({_escape_url(notion_url)})"
        lines.append(line)
    return header + "\n\n".join(lines)


def _escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2.

    Args:
        text: Text to escape.

    Returns:
        Escaped text safe for MarkdownV2.
    """
    # Backslash must be escaped first to avoid double-escaping
    text = text.replace("\\", "\\\\")
    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


def _escape_url(url: str) -> str:
    """Escape special characters in URLs for Telegram MarkdownV2 links.

    Args:
        url: URL to escape.

    Returns:
        Escaped URL safe for MarkdownV2 link syntax.
    """
    url = url.replace("\\", "\\\\")
    return url.replace(")", "\\)")
