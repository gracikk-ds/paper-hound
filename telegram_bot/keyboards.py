"""Inline keyboard builders for Telegram bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.schemas import Paper

BUTTONS_PER_ROW: int = 5


def build_paper_actions_keyboard(paper: Paper) -> InlineKeyboardMarkup:
    """Build inline keyboard with actions for a paper.

    Args:
        paper: The paper to build actions for.

    Returns:
        InlineKeyboardMarkup with View PDF, Summarize, and Find Similar buttons.
    """
    buttons = [
        [
            InlineKeyboardButton("View PDF", url=paper.pdf_url),
            InlineKeyboardButton("Summarize", callback_data=f"summarize:{paper.paper_id}"),
        ],
        [
            InlineKeyboardButton("Find Similar", callback_data=f"similar:{paper.paper_id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def build_paper_list_keyboard(papers: list[Paper]) -> InlineKeyboardMarkup:
    """Build inline keyboard for selecting a paper from a list.

    Args:
        papers: List of papers to build selection buttons for.

    Returns:
        InlineKeyboardMarkup with numbered selection buttons.
    """
    buttons = []
    row = []
    for i, paper in enumerate(papers, 1):
        row.append(InlineKeyboardButton(str(i), callback_data=f"paper:{paper.paper_id}"))
        if len(row) == BUTTONS_PER_ROW:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def build_notification_keyboard(paper: Paper, notion_url: str | None = None) -> InlineKeyboardMarkup:
    """Build inline keyboard for subscription notification.

    Args:
        paper: The paper to build actions for.
        notion_url: Optional Notion page URL with the summary.

    Returns:
        InlineKeyboardMarkup with View PDF and optionally View Summary buttons.
    """
    buttons = [[InlineKeyboardButton("View PDF", url=paper.pdf_url)]]
    if notion_url:
        buttons[0].append(InlineKeyboardButton("View Summary", url=notion_url))
    return InlineKeyboardMarkup(buttons)


def build_subscription_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    """Build inline keyboard for subscription management.

    Args:
        subscription_id: The subscription ID for the unsubscribe button.

    Returns:
        InlineKeyboardMarkup with unsubscribe button.
    """
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Unsubscribe", callback_data=f"unsub:{subscription_id}")],
        ],
    )


def build_topic_selection_keyboard(topics: list[str]) -> InlineKeyboardMarkup:
    """Build inline keyboard for topic subscription selection.

    Args:
        topics: List of available topic names.

    Returns:
        InlineKeyboardMarkup with topic buttons (one per row).
    """
    buttons = [[InlineKeyboardButton(topic, callback_data=f"sub:{topic}")] for topic in topics]
    return InlineKeyboardMarkup(buttons)
