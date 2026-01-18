"""Subscription handler implementations for Telegram bot."""

import asyncio

from loguru import logger
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from telegram_bot.context import bot_context
from telegram_bot.formatters import _escape_markdown
from telegram_bot.handlers.handlers_utils import get_available_topics
from telegram_bot.keyboards import build_topic_selection_keyboard, build_unsubscribe_selection_keyboard
from telegram_bot.subscriptions import get_subscription_store


async def handle_topics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: ARG001
    """Handle the /topics command.

    Shows all available topics from Notion database.

    Args:
        update: The update object.
        context: The callback context.
    """
    await update.message.reply_text("Fetching available topics\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)
    try:
        notion_extractor = bot_context.container.notion_settings_extractor()
        loop = asyncio.get_running_loop()
        available_topics = await loop.run_in_executor(None, lambda: get_available_topics(notion_extractor))
    except Exception as exp:
        logger.error(f"Error fetching available topics: {exp}")
        await update.message.reply_text("An error occurred while fetching available topics.")
        return

    if not available_topics:
        await update.message.reply_text("No topics available at the moment.")
        return

    lines = ["*Available Topics:*"]
    lines.extend(f"{idx + 1}\\. {_escape_markdown(topic)}" for idx, topic in enumerate(available_topics))

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


async def handle_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /subscribe command.

    Shows available topics (excluding already subscribed) and allows subscribing.

    Args:
        update: The update object.
        context: The callback context.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    try:
        notion_extractor = bot_context.container.notion_settings_extractor()
        loop = asyncio.get_running_loop()
        available_topics = await loop.run_in_executor(
            None,
            lambda: get_available_topics(notion_extractor),
        )
    except Exception as exp:
        logger.error(f"Error fetching available topics: {exp}")
        await update.message.reply_text("An error occurred while fetching available topics.")
        return

    if not available_topics:
        await update.message.reply_text("No topics available for subscription at the moment.")
        return

    # Get user's current subscriptions to filter them out
    store = get_subscription_store()
    user_subscriptions = store.get_user_subscriptions(user_id)
    subscribed_topics = {sub.query for sub in user_subscriptions}

    # Filter out already subscribed topics
    unsubscribed_topics = [t for t in available_topics if t not in subscribed_topics]

    # If no arguments, show available topics as buttons
    if not context.args:
        if not unsubscribed_topics:
            await update.message.reply_text(
                "You are already subscribed to all available topics\\!\n\n"
                "Use /subscriptions to view your subscriptions\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        keyboard = build_topic_selection_keyboard(unsubscribed_topics)
        await update.message.reply_text(
            "*Available Topics:*\n\nSelect a topic to subscribe:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )
        return

    # Validate topic against available topics
    topic = " ".join(context.args)
    if topic not in available_topics:
        keyboard = build_topic_selection_keyboard(unsubscribed_topics) if unsubscribed_topics else None
        await update.message.reply_text(
            f"Topic *{_escape_markdown(topic)}* is not available\\.\n\nUse /topics to see all available topics\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )
        return

    # Check if already subscribed
    if topic in subscribed_topics:
        await update.message.reply_text(
            f"You are already subscribed to *{_escape_markdown(topic)}*\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    try:
        store.add_subscription(user_id, chat_id, topic)
        count = store.count_user_subscriptions(user_id)

        await update.message.reply_text(
            f"Subscribed to: *{_escape_markdown(topic)}*\n\n"
            f"You'll receive updates when new papers match this topic\\.\n"
            f"Current subscriptions: {count}",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as exp:
        logger.error(f"Error subscribing: {exp}")
        await update.message.reply_text("An error occurred. Please try again.")


async def handle_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: ARG001
    """Handle the /unsubscribe command.

    Shows user's active subscriptions and allows unsubscribing via buttons.

    Args:
        update: The update object.
        context: The callback context.
    """
    user_id = update.effective_user.id
    store = get_subscription_store()
    subscriptions = store.get_user_subscriptions(user_id)

    if not subscriptions:
        await update.message.reply_text(
            "You have no active subscriptions\\.\n\nUse `/subscribe` to create one\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    keyboard = build_unsubscribe_selection_keyboard(subscriptions)
    await update.message.reply_text(
        "*Your Subscriptions:*\n\nSelect a subscription to remove:",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=keyboard,
    )


async def handle_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: ARG001
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
            "You have no active subscriptions\\.\n\nUse `/subscribe` to create one\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = ["*Your Subscriptions:*\n"]
    for idx, sub in enumerate(subscriptions):
        created = sub.created_at.strftime("%Y\\-%m\\-%d")
        lines.append(f"• \\#{idx + 1}: _{_escape_markdown(sub.query)}_ \\(since {created}\\)")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)
