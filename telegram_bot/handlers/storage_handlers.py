"""Storage handler implementations for Telegram bot."""

import asyncio
from datetime import datetime

from loguru import logger
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from telegram_bot.context import bot_context
from telegram_bot.formatters import format_stats


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
        embedder_costs = await loop.run_in_executor(
            None,
            lambda: processor.insert_papers(start_date, end_date),
        )
        await status_msg.edit_text(
            f"Successfully inserted papers from {start_date_str} to {end_date_str}.\n"
            f"Embedder costs: ${embedder_costs:.4f}",
        )
    except Exception as exp:
        logger.error(f"Error inserting papers: {exp}")
        await status_msg.edit_text("An error occurred while inserting papers. Please try again.")


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: ARG001
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
