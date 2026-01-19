"""Subscription handler implementations for Telegram bot."""

import asyncio

from loguru import logger
from telegram import ChatMember, Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from telegram_bot.context import bot_context
from telegram_bot.formatters import _escape_markdown
from telegram_bot.handlers.handlers_utils import get_available_topics
from telegram_bot.keyboards import (
    build_group_topic_selection_keyboard,
    build_group_unsubscribe_selection_keyboard,
    build_topic_selection_keyboard,
    build_unsubscribe_selection_keyboard,
)
from telegram_bot.subscriptions import get_subscription_store


async def is_user_group_admin(update: Update) -> bool:
    """Check if the user is an admin or creator of the group chat.

    Args:
        update: The update object.

    Returns:
        True if user is admin/creator, False otherwise.
    """
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == ChatType.PRIVATE:
        return False

    try:
        member = await chat.get_member(user.id)
    except Exception as exp:
        logger.error(f"Error checking admin status: {exp}")
        return False
    else:
        return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)


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


# =============================================================================
# Group Subscription Handlers
# =============================================================================


async def handle_group_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: PLR0911
    """Handle the /groupsubscribe command.

    Subscribe a group chat to a topic. Only group admins can use this command.

    Args:
        update: The update object.
        context: The callback context.
    """
    chat = update.effective_chat
    user_id = update.effective_user.id
    chat_id = chat.id

    # Check if in a group chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "This command can only be used in group chats\\.\n\nUse `/subscribe` for personal subscriptions\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Check if user is admin
    if not await is_user_group_admin(update):
        await update.message.reply_text(
            "Only group administrators can manage group subscriptions\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

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

    # Get group's current subscriptions to filter them out
    store = get_subscription_store()
    group_subscriptions = store.get_chat_subscriptions(chat_id)
    subscribed_topics = {sub.query for sub in group_subscriptions}

    # Filter out already subscribed topics
    unsubscribed_topics = [t for t in available_topics if t not in subscribed_topics]

    # If no arguments, show available topics as buttons
    if not context.args:
        if not unsubscribed_topics:
            await update.message.reply_text(
                "This group is already subscribed to all available topics\\!\n\n"
                "Use /groupsubscriptions to view group subscriptions\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        keyboard = build_group_topic_selection_keyboard(unsubscribed_topics)
        await update.message.reply_text(
            "*Available Topics:*\n\nSelect a topic to subscribe this group:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )
        return

    # Validate topic against available topics
    topic = " ".join(context.args)
    if topic not in available_topics:
        keyboard = build_group_topic_selection_keyboard(unsubscribed_topics) if unsubscribed_topics else None
        await update.message.reply_text(
            f"Topic *{_escape_markdown(topic)}* is not available\\.\n\nUse /topics to see all available topics\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )
        return

    # Check if already subscribed
    if topic in subscribed_topics:
        await update.message.reply_text(
            f"This group is already subscribed to *{_escape_markdown(topic)}*\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    try:
        store.add_subscription(user_id, chat_id, topic, is_group=True)
        count = store.count_chat_subscriptions(chat_id)

        await update.message.reply_text(
            f"Group subscribed to: *{_escape_markdown(topic)}*\n\n"
            f"Everyone in this group will receive updates when new papers match this topic\\.\n"
            f"Current group subscriptions: {count}",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as exp:
        logger.error(f"Error subscribing group: {exp}")
        await update.message.reply_text("An error occurred. Please try again.")


async def handle_group_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: ARG001
    """Handle the /groupunsubscribe command.

    Shows group's active subscriptions and allows unsubscribing via buttons.
    Only group admins can use this command.

    Args:
        update: The update object.
        context: The callback context.
    """
    chat = update.effective_chat
    chat_id = chat.id

    # Check if in a group chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "This command can only be used in group chats\\.\n\nUse `/unsubscribe` for personal subscriptions\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Check if user is admin
    if not await is_user_group_admin(update):
        await update.message.reply_text(
            "Only group administrators can manage group subscriptions\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    store = get_subscription_store()
    subscriptions = store.get_chat_subscriptions(chat_id)

    if not subscriptions:
        await update.message.reply_text(
            "This group has no active subscriptions\\.\n\nUse `/groupsubscribe` to create one\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    keyboard = build_group_unsubscribe_selection_keyboard(subscriptions)
    await update.message.reply_text(
        "*Group Subscriptions:*\n\nSelect a subscription to remove:",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=keyboard,
    )


async def handle_group_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: ARG001
    """Handle the /groupsubscriptions command.

    Shows all active subscriptions for the group. Any member can view.

    Args:
        update: The update object.
        context: The callback context.
    """
    chat = update.effective_chat
    chat_id = chat.id

    # Check if in a group chat
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "This command can only be used in group chats\\.\n\n"
            "Use `/subscriptions` to view your personal subscriptions\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    store = get_subscription_store()
    subscriptions = store.get_chat_subscriptions(chat_id)

    if not subscriptions:
        await update.message.reply_text(
            "This group has no active subscriptions\\.\n\nAdmins can use `/groupsubscribe` to create one\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = ["*Group Subscriptions:*\n"]
    for idx, sub in enumerate(subscriptions):
        created = sub.created_at.strftime("%Y\\-%m\\-%d")
        lines.append(f"• \\#{idx + 1}: _{_escape_markdown(sub.query)}_ \\(since {created}\\)")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)
