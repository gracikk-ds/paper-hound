"""Notification service for sending updates to subscribers."""

import asyncio
from collections import defaultdict
from datetime import datetime

from loguru import logger
from telegram import Bot
from telegram.constants import ParseMode

from src.utils.schemas import Paper
from telegram_bot.formatters import _escape_markdown, format_paper_short
from telegram_bot.keyboards import build_notification_keyboard
from telegram_bot.subscriptions import Subscription, get_subscription_store


class NotificationService:
    """Service for sending subscription notifications via Telegram."""

    def __init__(
        self,
        bot_token: str,
        processed_by_category: dict[str, list[tuple[Paper, str]]],
    ) -> None:
        """Initialize the notification service.

        Args:
            bot_token: Telegram bot token.
            processed_by_category: Mapping of category name to list of (paper, notion_url)
                tuples for papers processed in the current workflow run.
        """
        self.bot = Bot(token=bot_token)
        self.processed_by_category = processed_by_category

    async def send_subscription_notifications(self) -> int:
        """Send notifications for all active subscriptions.

        Returns:
            Number of notifications sent.
        """
        if not self.processed_by_category:
            logger.info("No processed papers to notify about.")
            return 0

        store = get_subscription_store()
        subscriptions = store.get_all_active_subscriptions()

        if not subscriptions:
            logger.info("No active subscriptions to process.")
            return 0

        # Group subscriptions by chat_id for batching
        subscriptions_by_chat: dict[int, list[Subscription]] = defaultdict(list)
        for sub in subscriptions:
            subscriptions_by_chat[sub.chat_id].append(sub)

        notifications_sent = 0

        for chat_subscriptions in subscriptions_by_chat.values():
            for subscription in chat_subscriptions:
                try:
                    sent = await self._process_subscription(subscription)
                    if sent:
                        notifications_sent += 1
                        store.update_last_notified(subscription.id)
                except Exception as exp:
                    logger.error(f"Error processing subscription {subscription.id}: {exp}")

        logger.info(f"Sent {notifications_sent} subscription notifications.")
        return notifications_sent

    async def _process_subscription(self, subscription: Subscription) -> bool:
        """Process a single subscription and send notification if there are new papers.

        The subscription.query field contains the category name that the user subscribed to.
        We look up processed papers for that category and send notifications.

        Args:
            subscription: The subscription to process.

        Returns:
            True if notification was sent, False otherwise.
        """
        # Get papers for this subscription's category
        category = subscription.query
        papers_with_urls = self.processed_by_category.get(category, [])

        if not papers_with_urls:
            return False

        # Filter papers that were already notified (based on last_notified_at)
        if subscription.last_notified_at:
            filtered_papers_with_urls = []
            for paper, notion_url in papers_with_urls:
                try:
                    paper_date = datetime.fromisoformat(paper.published_date)
                    if paper_date > subscription.last_notified_at:
                        filtered_papers_with_urls.append((paper, notion_url))
                except (ValueError, TypeError):
                    # Skip papers with invalid/missing dates rather than failing the batch
                    logger.warning(f"Invalid published_date for paper {paper.paper_id}: {paper.published_date}")
                    continue
            papers_with_urls = filtered_papers_with_urls

        if not papers_with_urls:
            return False

        # Send notification
        await self._send_notification(subscription, papers_with_urls)
        return True

    async def _send_notification(
        self,
        subscription: Subscription,
        papers_with_urls: list[tuple[Paper, str]],
    ) -> None:
        """Send a notification message for new papers.

        Args:
            subscription: The subscription.
            papers_with_urls: List of (paper, notion_url) tuples.
        """
        header = f"*New papers matching your subscription:*\n_{_escape_markdown(subscription.query)}_\n\n"

        try:
            await self.bot.send_message(
                chat_id=subscription.chat_id,
                text=header,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        except Exception as exp:
            logger.error(f"Error sending notification to {subscription.chat_id}: {exp}")

        for i, (paper, notion_url) in enumerate(papers_with_urls, 1):
            paper_text = format_paper_short(paper, index=i)

            # Send each paper with its own keyboard
            keyboard = build_notification_keyboard(paper, notion_url)
            try:
                await self.bot.send_message(
                    chat_id=subscription.chat_id,
                    text=paper_text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=keyboard,
                )
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
            except Exception as exp:
                logger.error(f"Error sending notification to {subscription.chat_id}: {exp}")


async def run_subscription_notifications(
    bot_token: str,
    processed_by_category: dict[str, list[tuple[Paper, str]]],
) -> int:
    """Run subscription notifications for processed papers.

    Args:
        bot_token: Telegram bot token.
        processed_by_category: Mapping of category name to list of (paper, notion_url)
            tuples for papers processed in the current workflow run.

    Returns:
        Number of notifications sent.
    """
    service = NotificationService(
        bot_token=bot_token,
        processed_by_category=processed_by_category,
    )
    return await service.send_subscription_notifications()
