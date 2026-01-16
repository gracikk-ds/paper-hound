"""Command handler implementations for Telegram bot."""

import asyncio
from datetime import datetime

from loguru import logger
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

# Import will be resolved at runtime via bot_context
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

HELP_TEXT = """
*ArXiv Paper Hound Bot*

*Discovery Commands:*
/search <query> \\- Semantic search for papers
/paper <paper\\_id> \\- Get paper details by arXiv ID
/similar <paper\\_id> \\- Find similar papers
/summarize <paper\\_id> \\- Generate AI summary \\(may take a while\\)

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
`/paper 2301.07041`
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

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text("Usage: /search <query>\nExample: /search neural radiance fields")
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"Searching for: _{query}_...", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        processor = bot_context.container.processor()
        loop = asyncio.get_running_loop()
        papers = await loop.run_in_executor(
            None,
            lambda: processor.search_papers(query=query, k=5, threshold=0.5),
        )

        if not papers:
            await update.message.reply_text(f"No papers found for: {query}")
            return

        # Store papers in context for callback handling
        context.user_data["last_search_papers"] = {p.paper_id: p for p in papers}

        message = format_search_results(papers, query)
        keyboard = build_paper_list_keyboard(papers)
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )
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
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )
    except Exception as exp:
        logger.error(f"Error fetching paper: {exp}")
        await update.message.reply_text("An error occurred while fetching the paper. Please try again.")


async def handle_similar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /similar command.

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text("Usage: /similar <paper_id>\nExample: /similar 2301.07041")
        return

    paper_id = context.args[0].strip()
    await update.message.reply_text(f"Finding papers similar to `{paper_id}`...", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        processor = bot_context.container.processor()
        loop = asyncio.get_running_loop()
        papers = await loop.run_in_executor(
            None,
            lambda: processor.find_similar_papers(paper_id=paper_id, k=5, threshold=0.5),
        )

        if not papers:
            await update.message.reply_text(f"No similar papers found for: {paper_id}")
            return

        context.user_data["last_search_papers"] = {p.paper_id: p for p in papers}

        message = format_similar_results(papers, paper_id)
        keyboard = build_paper_list_keyboard(papers)
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )
    except Exception as exp:
        logger.error(f"Error finding similar papers: {exp}")
        await update.message.reply_text("An error occurred. Please try again.")


async def handle_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /summarize command.

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text("Usage: /summarize <paper_id>\nExample: /summarize 2301.07041")
        return

    paper_id = context.args[0].strip()
    status_msg = await update.message.reply_text(
        f"Generating summary for `{paper_id}`\\.\\.\\. This may take a few minutes\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        workflow = bot_context.container.workflow()
        loop = asyncio.get_running_loop()
        notion_url = await loop.run_in_executor(
            None,
            lambda: workflow.prepare_paper_summary_and_upload(paper_id=paper_id),
        )

        if notion_url:
            await status_msg.edit_text(
                f"Summary created\\!\n\n[View on Notion]({notion_url})",
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
        paper_id = value
        await query.message.reply_text(
            f"Generating summary for `{paper_id}`\\.\\.\\. This may take a few minutes\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        try:
            workflow = bot_context.container.workflow()
            loop = asyncio.get_running_loop()
            notion_url = await loop.run_in_executor(
                None,
                lambda: workflow.prepare_paper_summary_and_upload(paper_id=paper_id),
            )

            if notion_url:
                await query.message.reply_text(
                    f"Summary created\\!\n\n[View on Notion]({notion_url})",
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
