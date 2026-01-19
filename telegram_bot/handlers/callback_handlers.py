"""Callback handler implementations for Telegram bot."""

import asyncio

from loguru import logger
from telegram import ChatMember, Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from telegram_bot.context import bot_context
from telegram_bot.formatters import _escape_markdown, format_paper_detailed, format_paper_short, format_similar_results
from telegram_bot.handlers.defaults import DEFAULT_CATEGORY
from telegram_bot.handlers.handlers_utils import normalize_paper_id
from telegram_bot.keyboards import (
    build_paper_actions_keyboard,
    build_paper_list_keyboard,
    build_summary_result_keyboard,
)
from telegram_bot.subscriptions import get_subscription_store


async def _is_callback_user_group_admin(update: Update) -> bool:
    """Check if the callback query user is an admin of the group chat.

    Args:
        update: The update object.

    Returns:
        True if user is admin/creator, False otherwise.
    """
    query = update.callback_query
    chat = query.message.chat
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


async def handle_callback_query(  # noqa: PLR0912,PLR0915,PLR0911
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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
            arxiv_fetcher = bot_context.container.arxiv_fetcher()
            loop = asyncio.get_running_loop()
            # Fetch from storage or arXiv (stores if fetched from arXiv)
            paper = await loop.run_in_executor(
                None,
                lambda: processor.fetch_and_store_paper(paper_id, arxiv_fetcher),
            )

        if paper:
            message = format_paper_detailed(paper)
            keyboard = build_paper_actions_keyboard(paper)
            await query.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard,
            )
        else:
            await query.message.reply_text(f"Paper not found: {paper_id}.")

    elif action == "summarize":
        paper_id = normalize_paper_id(value)
        category = DEFAULT_CATEGORY
        escaped_id = _escape_markdown(paper_id)

        status_msg = await query.message.reply_text(
            f"Generating summary for `{escaped_id}`\\.\\.\\. This may take a few minutes\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        try:
            workflow = bot_context.container.workflow()
            processor = bot_context.container.processor()
            arxiv_fetcher = bot_context.container.arxiv_fetcher()
            loop = asyncio.get_running_loop()

            notion_url = await loop.run_in_executor(
                None,
                lambda: workflow.prepare_paper_summary_and_upload(paper_id=paper_id, category=category),
            )
            costs = workflow.summarizer.inference_price
            costs_str = f"{costs:.3f}".replace(".", "\\.")

            if notion_url:
                # Fetch paper info to enrich the summary message
                paper = await loop.run_in_executor(
                    None,
                    lambda: processor.fetch_and_store_paper(paper_id, arxiv_fetcher),
                )

                keyboard = build_summary_result_keyboard(paper_id, notion_url)

                if paper:
                    paper_info = format_paper_short(paper)
                    await status_msg.edit_text(
                        f"\\(づ｡◕‿‿◕｡\\)づ  ✨  *Paper summary created\\!*  ✨\n\n"
                        f"{paper_info}\n\n"
                        f"*Summarizer costs*: ${costs_str}",
                        parse_mode=ParseMode.MARKDOWN_V2,
                        reply_markup=keyboard,
                    )
                else:
                    await status_msg.edit_text(
                        f"\\(づ｡◕‿‿◕｡\\)づ  ✨  *Paper summary created\\!*  ✨\n\n*Summarizer costs*: ${costs_str}",
                        parse_mode=ParseMode.MARKDOWN_V2,
                        reply_markup=keyboard,
                    )
            else:
                await status_msg.edit_text("Failed to generate summary.")
        except Exception as exp:
            logger.error(f"Error summarizing paper: {exp}")
            await status_msg.edit_text("An error occurred while generating the summary.")

    elif action == "similar":
        paper_id = value
        await query.message.reply_text(
            f"Finding papers similar to `{paper_id}`\\.\\.\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        try:
            processor = bot_context.container.processor()
            arxiv_fetcher = bot_context.container.arxiv_fetcher()
            loop = asyncio.get_running_loop()

            # Ensure paper is in storage (fetch and store if needed)
            source_paper = await loop.run_in_executor(
                None,
                lambda: processor.fetch_and_store_paper(paper_id, arxiv_fetcher),
            )

            if source_paper is None:
                await query.message.reply_text(f"Paper not found: {paper_id}.")
                return

            papers = await loop.run_in_executor(
                None,
                lambda: processor.find_similar_papers(paper_id=source_paper.paper_id, k=5, threshold=0.5),
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
                await query.message.reply_text(f"No similar papers found for: {paper_id}.")
        except Exception as exp:
            logger.error(f"Error finding similar papers: {exp}")
            await query.message.reply_text("An error occurred.")

    elif action == "sub":
        # Subscribe to a topic from inline keyboard
        topic = value
        user_id = update.effective_user.id
        chat_id = query.message.chat_id

        # Validate topic is allowed (not AdHoc Research)
        if topic == "AdHoc Research":
            await query.message.reply_text("This topic is not available for subscription.")
            return

        try:
            store = get_subscription_store()

            # Check if already subscribed
            user_subscriptions = store.get_user_subscriptions(user_id)
            subscribed_topics = {sub.query for sub in user_subscriptions}
            if topic in subscribed_topics:
                await query.message.edit_text(
                    f"You are already subscribed to *{_escape_markdown(topic)}*\\.",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                return

            store.add_subscription(user_id, chat_id, topic)
            count = store.count_user_subscriptions(user_id)

            await query.message.edit_text(
                f"Subscribed to: *{_escape_markdown(topic)}*\n\n"
                f"You'll receive updates when new papers match this topic\\.\n"
                f"Current subscriptions: {count}",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as exp:
            logger.error(f"Error subscribing via callback: {exp}")
            await query.message.reply_text("An error occurred. Please try again.")

    elif action == "unsub":
        try:
            subscription_id = int(value)
        except ValueError:
            await query.message.reply_text("Invalid subscription ID.")
            return

        user_id = update.effective_user.id
        store = get_subscription_store()

        if store.deactivate_subscription(subscription_id, user_id):
            await query.message.edit_text("Subscription deactivated.")
        else:
            await query.message.reply_text("Subscription not found or already inactive.")

    elif action == "gsub":
        # Subscribe group to a topic from inline keyboard
        topic = value
        user_id = update.effective_user.id
        chat_id = query.message.chat_id

        # Check if user is admin
        if not await _is_callback_user_group_admin(update):
            await query.answer("Only group administrators can manage group subscriptions.", show_alert=True)
            return

        # Validate topic is allowed (not AdHoc Research)
        if topic == "AdHoc Research":
            await query.message.reply_text("This topic is not available for subscription.")
            return

        try:
            store = get_subscription_store()

            # Check if already subscribed
            group_subscriptions = store.get_chat_subscriptions(chat_id)
            subscribed_topics = {sub.query for sub in group_subscriptions}
            if topic in subscribed_topics:
                await query.message.edit_text(
                    f"This group is already subscribed to *{_escape_markdown(topic)}*\\.",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                return

            store.add_subscription(user_id, chat_id, topic, is_group=True)
            count = store.count_chat_subscriptions(chat_id)

            await query.message.edit_text(
                f"Group subscribed to: *{_escape_markdown(topic)}*\n\n"
                f"Everyone in this group will receive updates when new papers match this topic\\.\n"
                f"Current group subscriptions: {count}",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as exp:
            logger.error(f"Error subscribing group via callback: {exp}")
            await query.message.reply_text("An error occurred. Please try again.")

    elif action == "gunsub":
        # Unsubscribe group from a topic
        try:
            subscription_id = int(value)
        except ValueError:
            await query.message.reply_text("Invalid subscription ID.")
            return

        chat_id = query.message.chat_id

        # Check if user is admin
        if not await _is_callback_user_group_admin(update):
            await query.answer("Only group administrators can manage group subscriptions.", show_alert=True)
            return

        store = get_subscription_store()

        if store.deactivate_chat_subscription(subscription_id, chat_id):
            await query.message.edit_text("Group subscription deactivated.")
        else:
            await query.message.reply_text("Subscription not found or already inactive.")
