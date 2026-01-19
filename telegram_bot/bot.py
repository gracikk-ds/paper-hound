"""Telegram bot initialization and main entry point."""

import asyncio
from typing import TYPE_CHECKING

from loguru import logger
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from telegram_bot.context import bot_context

if TYPE_CHECKING:
    from src.containers.containers import AppContainer

from telegram_bot.handlers import (
    handle_callback_query,
    handle_group_subscribe,
    handle_group_subscriptions,
    handle_group_unsubscribe,
    handle_help,
    handle_insert,
    handle_paper,
    handle_search,
    handle_similar,
    handle_start,
    handle_stats,
    handle_subscribe,
    handle_subscriptions,
    handle_summarize,
    handle_topics,
    handle_unsubscribe,
)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the bot.

    Args:
        update: The update that caused the error.
        context: The callback context.
    """
    logger.error(f"Exception while handling an update: {context.error}")
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "An error occurred while processing your request. Please try again later.",
        )


def create_bot_application(
    token: str,
    container: "AppContainer",
    admin_user_ids: set[int] | None = None,
) -> Application:
    """Create and configure the Telegram bot application.

    Args:
        token: Telegram bot token.
        container: The dependency injection container.
        admin_user_ids: Set of user IDs allowed to use admin commands.

    Returns:
        Configured Application instance.
    """
    # Store container in context for handlers to access
    bot_context.container = container
    bot_context.admin_user_ids = admin_user_ids or set()

    # Build application
    application = Application.builder().token(token).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("search", handle_search))
    application.add_handler(CommandHandler("paper", handle_paper))
    application.add_handler(CommandHandler("similar", handle_similar))
    application.add_handler(CommandHandler("summarize", handle_summarize))
    application.add_handler(CommandHandler("insert", handle_insert))
    application.add_handler(CommandHandler("topics", handle_topics))
    application.add_handler(CommandHandler("subscribe", handle_subscribe))
    application.add_handler(CommandHandler("unsubscribe", handle_unsubscribe))
    application.add_handler(CommandHandler("subscriptions", handle_subscriptions))
    application.add_handler(CommandHandler("stats", handle_stats))

    # Group subscription handlers
    application.add_handler(CommandHandler("groupsubscribe", handle_group_subscribe))
    application.add_handler(CommandHandler("groupunsubscribe", handle_group_unsubscribe))
    application.add_handler(CommandHandler("groupsubscriptions", handle_group_subscriptions))

    # Register callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Register error handler
    application.add_error_handler(error_handler)

    logger.info("Telegram bot application created and configured.")
    return application


async def run_bot(application: Application) -> None:
    """Run the bot using polling.

    Args:
        application: The configured Application instance.
    """
    logger.info("Starting Telegram bot polling...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    # Keep running until stopped
    try:
        while True:  # noqa: ASYNC110
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Bot polling cancelled.")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


async def stop_bot(application: Application) -> None:
    """Stop the bot gracefully.

    Args:
        application: The Application instance to stop.
    """
    logger.info("Stopping Telegram bot...")
    if application.updater and application.updater.running:
        await application.updater.stop()
    if application.running:
        await application.stop()
        await application.shutdown()
