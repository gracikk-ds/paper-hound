"""Command handler implementations for Telegram bot."""

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from loguru import logger
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.service.notion_db.extract_page_content import NotionPageExtractor
from src.settings import settings as api_settings
from telegram_bot.bot import bot_context
from telegram_bot.formatters import (
    _escape_markdown,
    format_paper_detailed,
    format_search_results,
    format_similar_results,
    format_stats,
)
from telegram_bot.keyboards import build_paper_actions_keyboard, build_paper_list_keyboard
from telegram_bot.subscriptions import get_subscription_store

# Default search parameters
DEFAULT_TOP_K = 5
DEFAULT_THRESHOLD = 0.65
DEFAULT_CATEGORY = "AdHoc Research"


@dataclass
class SearchParams:
    """Parsed search parameters from user input."""

    query: str
    top_k: int = DEFAULT_TOP_K
    threshold: float = DEFAULT_THRESHOLD
    start_date_str: str | None = None
    end_date_str: str | None = None


def parse_search_params(args: list[str], default_k: int = DEFAULT_TOP_K) -> SearchParams:
    """Parse search arguments extracting optional parameters.

    Supports the following options in any order:
        k:N         - Number of results
        t:N         - Similarity threshold (0-1)
        from:DATE   - Start date (YYYY-MM-DD)
        to:DATE     - End date (YYYY-MM-DD)

    Args:
        args: List of arguments from the command.
        default_k: Default number of results.

    Returns:
        SearchParams with parsed values.

    Examples:
        >>> parse_search_params(["neural", "networks", "k:10", "t:0.5"])
        SearchParams(query="neural networks", top_k=10, threshold=0.5, ...)
    """
    query_parts: list[str] = []
    top_k = default_k
    threshold = DEFAULT_THRESHOLD
    start_date_str: str | None = None
    end_date_str: str | None = None

    # Patterns for parameter extraction
    param_patterns = {
        "k": re.compile(r"^k:(\d+)$"),
        "t": re.compile(r"^t:([0-9.]+)$"),
        "from": re.compile(r"^from:(\d{4}-\d{2}-\d{2})$"),
        "to": re.compile(r"^to:(\d{4}-\d{2}-\d{2})$"),
    }

    for arg in args:
        matched = False
        for param_name, pattern in param_patterns.items():
            match = pattern.match(arg)
            if match:
                matched = True
                value = match.group(1)
                if param_name == "k":
                    top_k = max(1, min(int(value), 50))  # Clamp between 1-50
                elif param_name == "t":
                    threshold = max(0.0, min(float(value), 1.0))  # Clamp between 0-1
                elif param_name == "from":
                    start_date_str = value
                elif param_name == "to":
                    end_date_str = value
                break

        if not matched:
            query_parts.append(arg)

    return SearchParams(
        query=" ".join(query_parts),
        top_k=top_k,
        threshold=threshold,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
    )


@dataclass
class SummarizeParams:
    """Parsed summarize parameters from user input."""

    paper_id: str
    category: str = DEFAULT_CATEGORY


def normalize_paper_id(paper_id: str) -> str:
    """Normalize a paper identifier or arXiv URL.

    Handles various input formats:
        - Plain ID: "2301.07041"
        - With version: "2301.07041v2"
        - arXiv abs URL: "https://arxiv.org/abs/2301.07041"
        - arXiv PDF URL: "https://arxiv.org/pdf/2301.07041.pdf"
        - alphaxiv URL: "https://alphaxiv.org/abs/2301.07041"

    Args:
        paper_id: Raw paper ID or URL.

    Returns:
        Normalized paper ID string (without version suffix).
    """
    cleaned = paper_id.strip()

    # Handle URLs
    if cleaned.startswith(("http://", "https://")):
        parsed = urlparse(cleaned)
        if parsed.netloc.endswith(("arxiv.org", "alphaxiv.org")):
            path = parsed.path.strip("/")
            if path.startswith(("abs/", "pdf/")):
                cleaned = path.split("/", 1)[1].replace(".pdf", "")

    # Strip version suffix (e.g., "2301.07041v2" -> "2301.07041")
    match = re.match(r"^(\d{4}\.\d{5})(?:v\d+)?$", cleaned)
    return match.group(1) if match else cleaned


def parse_summarize_params(args: list[str]) -> SummarizeParams:
    """Parse summarize arguments extracting optional parameters.

    Supports the following options:
        cat:CategoryName - Research category (default: AdHoc Research)

    Args:
        args: List of arguments from the command.

    Returns:
        SummarizeParams with parsed values.

    Examples:
        >>> parse_summarize_params(["2301.07041"])
        SummarizeParams(paper_id="2301.07041", category="AdHoc Research")

        >>> parse_summarize_params(["2301.07041", "cat:Image Editing"])
        SummarizeParams(paper_id="2301.07041", category="Image Editing")
    """
    paper_id = ""
    category = DEFAULT_CATEGORY
    category_pattern = re.compile(r"^cat:(.+)$")

    for arg in args:
        cat_match = category_pattern.match(arg)
        if cat_match:
            category = cat_match.group(1).strip()
        elif not paper_id:
            # First non-option argument is the paper_id
            paper_id = normalize_paper_id(arg)

    return SummarizeParams(paper_id=paper_id, category=category)


def _resolve_summarizer_prompt(notion_extractor: NotionPageExtractor, category: str) -> str | None:
    """Resolve the summarizer prompt from Notion settings based on category.

    Args:
        notion_extractor: The Notion page extractor instance.
        category: The research category to look up.

    Returns:
        The summarizer prompt string if found, None otherwise.
    """
    database_id = api_settings.notion_command_database_id
    if not database_id:
        return None

    try:
        for page_id in notion_extractor.query_database(database_id):
            page_settings = notion_extractor.extract_settings_from_page(page_id)
            if page_settings is None:
                continue
            if page_settings.get("Page Name", "").strip() == category:
                return page_settings.get("Summarizer Prompt", None)
    except Exception:
        logger.exception("Error resolving summarizer prompt")

    return None


HELP_TEXT = """
*ArXiv Paper Hound Bot*

*Discovery Commands:*
/search <query> \\[options\\] \\- Semantic search for papers
/paper <paper\\_id> \\- Get paper details by arXiv ID
/similar <paper\\_id> \\[options\\] \\- Find similar papers
/summarize <paper\\_id> \\[cat:Category\\] \\- Generate AI summary

*Search/Similar Options:*
• `k:N` \\- Number of results \\(default: 5\\)
• `t:N` \\- Similarity threshold 0\\-1 \\(default: 0\\.65\\)
• `from:DATE` \\- Start date \\(YYYY\\-MM\\-DD\\)
• `to:DATE` \\- End date \\(YYYY\\-MM\\-DD\\)

*Summarize Options:*
• `cat:Name` \\- Research category \\(default: AdHoc Research\\)
• Accepts arXiv URLs or plain IDs

*Subscription Commands:*
/subscribe <topic> \\- Subscribe to a topic for daily updates
/unsubscribe <id> \\- Remove a subscription
/subscriptions \\- List your active subscriptions

*Other Commands:*
/stats \\- Database statistics
/insert <start\\_date> <end\\_date> \\- Insert papers \\(admin only\\)
/help \\- Show this message

*Examples:*
`/search transformer architectures for vision`
`/search diffusion models k:10 t:0.5`
`/search attention from:2025\\-01\\-01 to:2025\\-01\\-15`
`/paper 2301.07041`
`/summarize 2301.07041 cat:Image Editing`
`/summarize https://arxiv.org/abs/2301.07041`
`/subscribe diffusion models`
"""

WELCOME_TEXT = """
*Welcome to ArXiv Paper Hound\\!*

I help you discover, save, and summarize research papers from arXiv\\.

*Quick Start:*
• Search papers: `/search <your query>`
• Get paper details: `/paper <arxiv_id>`
• Subscribe to topics: `/subscribe <topic>`

Type /help for all available commands\\.
"""


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command.

    Args:
        update: The update object.
        context: The callback context.
    """
    await update.message.reply_text(WELCOME_TEXT, parse_mode=ParseMode.MARKDOWN_V2)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command.

    Args:
        update: The update object.
        context: The callback context.
    """
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN_V2)


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /search command.

    Supports optional parameters:
        k:N         - Number of results (default: 5)
        t:N         - Similarity threshold 0-1 (default: 0.65)
        from:DATE   - Start date (YYYY-MM-DD)
        to:DATE     - End date (YYYY-MM-DD)

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /search <query> [options]\n\n"
            "Options:\n"
            "  k:N - Number of results (default: 5)\n"
            "  t:N - Threshold 0-1 (default: 0.65)\n"
            "  from:DATE - Start date (YYYY-MM-DD)\n"
            "  to:DATE - End date (YYYY-MM-DD)\n\n"
            "Example: /search neural radiance fields k:10 t:0.5",
        )
        return

    params = parse_search_params(context.args)

    if not params.query:
        await update.message.reply_text("Please provide a search query.")
        return

    escaped_query = _escape_markdown(params.query)
    await update.message.reply_text(f"Searching for: _{escaped_query}_...", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        processor = bot_context.container.processor()
        loop = asyncio.get_running_loop()
        papers = await loop.run_in_executor(
            None,
            lambda: processor.search_papers(
                query=params.query,
                k=params.top_k,
                threshold=params.threshold,
                start_date_str=params.start_date_str,
                end_date_str=params.end_date_str,
            ),
        )

        if not papers:
            await update.message.reply_text(f"No papers found for: {params.query}")
            return

        # Store papers in context for callback handling
        context.user_data["last_search_papers"] = {p.paper_id: p for p in papers}

        message = format_search_results(papers, params.query)
        keyboard = build_paper_list_keyboard(papers)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)
    except Exception as exp:
        logger.error(f"Error in search: {exp}")
        await update.message.reply_text("An error occurred while searching. Please try again.")


async def handle_paper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /paper command.

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text("Usage: /paper <paper_id>\nExample: /paper 2301.07041")
        return

    paper_id = context.args[0].strip()
    await update.message.reply_text(f"Fetching paper `{paper_id}`...", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        processor = bot_context.container.processor()
        loop = asyncio.get_running_loop()
        paper = await loop.run_in_executor(None, lambda: processor.get_paper_by_id(paper_id))

        if paper is None:
            # Try fetching from arXiv
            arxiv_fetcher = bot_context.container.arxiv_fetcher()
            paper = await loop.run_in_executor(
                None,
                lambda: arxiv_fetcher.extract_paper_by_name_or_id(paper_id),
            )

        if paper is None:
            await update.message.reply_text(f"Paper not found: {paper_id}")
            return

        message = format_paper_detailed(paper)
        keyboard = build_paper_actions_keyboard(paper)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)
    except Exception as exp:
        logger.error(f"Error fetching paper: {exp}")
        await update.message.reply_text("An error occurred while fetching the paper. Please try again.")


async def handle_similar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /similar command.

    Supports optional parameters:
        k:N         - Number of results (default: 5)
        t:N         - Similarity threshold 0-1 (default: 0.65)
        from:DATE   - Start date (YYYY-MM-DD)
        to:DATE     - End date (YYYY-MM-DD)

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /similar <paper_id> [options]\n\n"
            "Options:\n"
            "  k:N - Number of results (default: 5)\n"
            "  t:N - Threshold 0-1 (default: 0.65)\n"
            "  from:DATE - Start date (YYYY-MM-DD)\n"
            "  to:DATE - End date (YYYY-MM-DD)\n\n"
            "Example: /similar 2301.07041 k:10",
        )
        return

    # First arg is paper_id, rest are optional params
    paper_id = context.args[0].strip()
    params = parse_search_params(context.args[1:]) if len(context.args) > 1 else SearchParams(query="")

    escaped_id = _escape_markdown(paper_id)
    await update.message.reply_text(f"Finding papers similar to `{escaped_id}`...", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        processor = bot_context.container.processor()
        loop = asyncio.get_running_loop()
        papers = await loop.run_in_executor(
            None,
            lambda: processor.find_similar_papers(
                paper_id=paper_id,
                k=params.top_k,
                threshold=params.threshold,
                start_date_str=params.start_date_str,
                end_date_str=params.end_date_str,
            ),
        )

        if not papers:
            await update.message.reply_text(f"No similar papers found for: {paper_id}")
            return

        context.user_data["last_search_papers"] = {p.paper_id: p for p in papers}

        message = format_similar_results(papers, paper_id)
        keyboard = build_paper_list_keyboard(papers)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)
    except Exception as exp:
        logger.error(f"Error finding similar papers: {exp}")
        await update.message.reply_text("An error occurred. Please try again.")


async def handle_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /summarize command.

    Supports optional parameters:
        cat:CategoryName - Research category (default: AdHoc Research)

    Accepts paper IDs or full arXiv/alphaxiv URLs.

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /summarize <paper_id|url> [options]\n\n"
            "Options:\n"
            "  cat:Name - Research category (default: AdHoc Research)\n\n"
            "Examples:\n"
            "  /summarize 2301.07041\n"
            "  /summarize https://arxiv.org/abs/2301.07041\n"
            "  /summarize 2301.07041 cat:ML",
        )
        return

    params = parse_summarize_params(context.args)

    if not params.paper_id:
        await update.message.reply_text("Please provide a paper ID or arXiv URL.")
        return

    escaped_id = _escape_markdown(params.paper_id)
    escaped_cat = _escape_markdown(params.category)
    status_msg = await update.message.reply_text(
        f"Generating summary for `{escaped_id}` \\(category: {escaped_cat}\\)\\.\\.\\.\nThis may take a few minutes\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        # Resolve summarizer prompt from Notion settings based on category
        notion_extractor = bot_context.container.notion_settings_extractor()
        workflow = bot_context.container.workflow()
        loop = asyncio.get_running_loop()

        summarizer_prompt = await loop.run_in_executor(
            None,
            lambda: _resolve_summarizer_prompt(notion_extractor, params.category),
        )

        if summarizer_prompt is None:
            logger.warning(f"No prompt found for category '{params.category}', using default")

        notion_url = await loop.run_in_executor(
            None,
            lambda: workflow.prepare_paper_summary_and_upload(
                paper_id=params.paper_id,
                summarizer_prompt=summarizer_prompt,
                category=params.category,
            ),
        )

        if notion_url:
            await status_msg.edit_text(
                f"Summary created\\!\n\n[View on Notion]({_escape_markdown(notion_url)})",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            await status_msg.edit_text("Failed to generate summary. Please try again.")
    except Exception as exp:
        logger.error(f"Error summarizing paper: {exp}")
        await status_msg.edit_text("An error occurred while generating the summary. Please try again.")


async def handle_insert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /insert command (admin only).

    Args:
        update: The update object.
        context: The callback context.
    """
    user_id = update.effective_user.id
    # Fail-closed: if no admins configured, block everyone
    if not bot_context.admin_user_ids or user_id not in bot_context.admin_user_ids:
        await update.message.reply_text("This command is restricted to administrators.")
        return

    if len(context.args) != 2:  # noqa: PLR2004
        await update.message.reply_text(
            "Usage: /insert <start_date> <end_date>\nExample: /insert 2025-01-10 2025-01-16",
        )
        return

    start_date_str, end_date_str = context.args[0], context.args[1]

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()  # noqa: DTZ007
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()  # noqa: DTZ007
    except ValueError:
        await update.message.reply_text("Invalid date format. Use YYYY-MM-DD.")
        return

    status_msg = await update.message.reply_text(
        f"Inserting papers from {start_date_str} to {end_date_str}... This may take a while.",
    )

    try:
        processor = bot_context.container.processor()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: processor.insert_papers(start_date, end_date),
        )
        await status_msg.edit_text(f"Successfully inserted papers from {start_date_str} to {end_date_str}.")
    except Exception as exp:
        logger.error(f"Error inserting papers: {exp}")
        await status_msg.edit_text("An error occurred while inserting papers. Please try again.")


async def handle_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /subscribe command.

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /subscribe <topic>\nExample: /subscribe diffusion models",
        )
        return

    query = " ".join(context.args)
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    try:
        store = get_subscription_store()
        store.add_subscription(user_id, chat_id, query)
        count = store.count_user_subscriptions(user_id)

        await update.message.reply_text(
            f"Subscribed to: *{_escape_markdown(query)}*\n\n"
            f"You'll receive updates when new papers match this topic\\.\n"
            f"Current subscriptions: {count}",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as exp:
        logger.error(f"Error subscribing: {exp}")
        await update.message.reply_text("An error occurred. Please try again.")


async def handle_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /unsubscribe command.

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /unsubscribe <subscription_id>\nUse /subscriptions to see your subscription IDs.",
        )
        return

    try:
        subscription_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid subscription ID. Must be a number.")
        return

    user_id = update.effective_user.id
    store = get_subscription_store()

    if store.deactivate_subscription(subscription_id, user_id):
        await update.message.reply_text(f"Unsubscribed from subscription #{subscription_id}.")
    else:
        await update.message.reply_text("Subscription not found or already inactive.")


async def handle_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /subscriptions command.

    Args:
        update: The update object.
        context: The callback context.
    """
    user_id = update.effective_user.id
    store = get_subscription_store()
    subscriptions = store.get_user_subscriptions(user_id)

    if not subscriptions:
        await update.message.reply_text(
            "You have no active subscriptions\\.\n\nUse `/subscribe <topic>` to create one\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = ["*Your Subscriptions:*\n"]
    for sub in subscriptions:
        created = sub.created_at.strftime("%Y\\-%m\\-%d")
        lines.append(f"• \\#{sub.id}: _{_escape_markdown(sub.query)}_ \\(since {created}\\)")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /stats command.

    Args:
        update: The update object.
        context: The callback context.
    """
    try:
        processor = bot_context.container.processor()
        loop = asyncio.get_running_loop()
        count = await loop.run_in_executor(None, processor.count_papers)

        message = format_stats(count)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as exp:
        logger.error(f"Error getting stats: {exp}")
        await update.message.reply_text("An error occurred. Please try again.")


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: PLR0912,PLR0915
    """Handle inline button callbacks.

    Args:
        update: The update object.
        context: The callback context.
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data:
        return

    try:
        action, value = data.split(":", 1)
    except ValueError:
        return

    if action == "paper":
        # Show paper details
        paper_id = value
        papers = context.user_data.get("last_search_papers", {})
        paper = papers.get(paper_id)

        if paper is None:
            processor = bot_context.container.processor()
            loop = asyncio.get_running_loop()
            paper = await loop.run_in_executor(None, lambda: processor.get_paper_by_id(paper_id))

        if paper:
            message = format_paper_detailed(paper)
            keyboard = build_paper_actions_keyboard(paper)
            await query.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard,
            )
        else:
            await query.message.reply_text(f"Paper not found: {paper_id}")

    elif action == "summarize":
        paper_id = normalize_paper_id(value)
        category = DEFAULT_CATEGORY
        escaped_id = _escape_markdown(paper_id)

        await query.message.reply_text(
            f"Generating summary for `{escaped_id}`\\.\\.\\. This may take a few minutes\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        try:
            notion_extractor = bot_context.container.notion_settings_extractor()
            workflow = bot_context.container.workflow()
            loop = asyncio.get_running_loop()

            # Resolve prompt from Notion settings
            summarizer_prompt = await loop.run_in_executor(
                None,
                lambda: _resolve_summarizer_prompt(notion_extractor, category),
            )

            notion_url = await loop.run_in_executor(
                None,
                lambda: workflow.prepare_paper_summary_and_upload(
                    paper_id=paper_id,
                    summarizer_prompt=summarizer_prompt,
                    category=category,
                ),
            )

            if notion_url:
                await query.message.reply_text(
                    f"Summary created\\!\n\n[View on Notion]({_escape_markdown(notion_url)})",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            else:
                await query.message.reply_text("Failed to generate summary.")
        except Exception as exp:
            logger.error(f"Error summarizing paper: {exp}")
            await query.message.reply_text("An error occurred while generating the summary.")

    elif action == "similar":
        paper_id = value
        await query.message.reply_text(
            f"Finding papers similar to `{paper_id}`\\.\\.\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        try:
            processor = bot_context.container.processor()
            loop = asyncio.get_running_loop()
            papers = await loop.run_in_executor(
                None,
                lambda: processor.find_similar_papers(paper_id=paper_id, k=5, threshold=0.5),
            )

            if papers:
                context.user_data["last_search_papers"] = {p.paper_id: p for p in papers}
                message = format_similar_results(papers, paper_id)
                keyboard = build_paper_list_keyboard(papers)
                await query.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=keyboard,
                )
            else:
                await query.message.reply_text(f"No similar papers found for: {paper_id}")
        except Exception as exp:
            logger.error(f"Error finding similar papers: {exp}")
            await query.message.reply_text("An error occurred.")

    elif action == "unsub":
        try:
            subscription_id = int(value)
        except ValueError:
            await query.message.reply_text("Invalid subscription ID.")
            return

        user_id = update.effective_user.id
        store = get_subscription_store()

        if store.deactivate_subscription(subscription_id, user_id):
            await query.message.edit_text(f"Unsubscribed from subscription #{subscription_id}.")
        else:
            await query.message.reply_text("Subscription not found or already inactive.")
