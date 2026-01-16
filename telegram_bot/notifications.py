"""Notification service for sending updates to subscribers."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from loguru import logger
from telegram import Bot
from telegram.constants import ParseMode

from telegram_bot.formatters import _escape_markdown
from telegram_bot.keyboards import build_notification_keyboard
from telegram_bot.subscriptions import Subscription, get_subscription_store

if TYPE_CHECKING:
    from src.service.processor import PapersProcessor
    from src.service.vector_db.processing_cache import ProcessingCacheStore


MAX_TITLE_LENGTH: int = 100


class NotificationService:
    """Service for sending subscription notifications via Telegram."""

    def __init__(
        self,
        bot_token: str,
        processor: "PapersProcessor",
        processing_cache: "ProcessingCacheStore",
        look_back_days: int = 3,
    ) -> None:
        """Initialize the notification service.

        Args:
            bot_token: Telegram bot token.
            processor: Papers processor for searching papers.
            processing_cache: Processing cache for getting Notion URLs.
            look_back_days: Number of days to look back for new papers.
        """
        self.bot = Bot(token=bot_token)
        self.processor = processor
        self.processing_cache = processing_cache
        self.look_back_days = look_back_days

    async def send_subscription_notifications(self) -> int:
        """Send notifications for all active subscriptions.

        Returns:
            Number of notifications sent.
        """
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
        today = datetime.now().date()  # noqa: DTZ005
        start_date = today - timedelta(days=self.look_back_days)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = today.strftime("%Y-%m-%d")

        for chat_subscriptions in subscriptions_by_chat.values():
            for subscription in chat_subscriptions:
                try:
                    sent = await self._process_subscription(
                        subscription,
                        start_date_str,
                        end_date_str,
                    )
                    if sent:
                        notifications_sent += 1
                        store.update_last_notified(subscription.id)
                except Exception as exp:  # noqa: BLE001
                    logger.error(f"Error processing subscription {subscription.id}: {exp}")

        logger.info(f"Sent {notifications_sent} subscription notifications.")
        return notifications_sent

    async def _process_subscription(
        self,
        subscription: Subscription,
        start_date_str: str,
        end_date_str: str,
    ) -> bool:
        """Process a single subscription and send notification if there are new papers.

        Args:
            subscription: The subscription to process.
            start_date_str: Start date for paper search.
            end_date_str: End date for paper search.

        Returns:
            True if notification was sent, False otherwise.
        """
        # Search for papers matching the subscription query
        loop = asyncio.get_running_loop()
        papers = await loop.run_in_executor(
            None,
            lambda: self.processor.search_papers(
                query=subscription.query,
                k=5,
                threshold=subscription.threshold,
                start_date_str=start_date_str,
                end_date_str=end_date_str,
            ),
        )

        if not papers:
            return False

        # Filter papers that were already notified (based on last_notified_at)
        if subscription.last_notified_at:
            filtered_papers = []
            for p in papers:
                try:
                    paper_date = datetime.fromisoformat(p.published_date)
                    if paper_date > subscription.last_notified_at:
                        filtered_papers.append(p)
                except (ValueError, TypeError):
                    # Skip papers with invalid/missing dates rather than failing the batch
                    logger.warning(f"Invalid published_date for paper {p.paper_id}: {p.published_date}")
                    continue
            papers = filtered_papers

        if not papers:
            return False

        # Get Notion URLs from processing cache
        papers_with_urls = []
        for paper in papers:
            notion_url = await self._get_notion_url(paper.paper_id)
            papers_with_urls.append((paper, notion_url))

        # Send notification
        await self._send_notification(subscription, papers_with_urls)
        return True

    async def _get_notion_url(self, paper_id: str) -> str | None:
        """Get Notion URL for a paper from the processing cache.

        Args:
            paper_id: The paper ID.

        Returns:
            Notion URL or None if not found.
        """
        try:
            # Try to find summarizer results for this paper in any category
            loop = asyncio.get_running_loop()
            # The cache key format includes paper_id, so we search by prefix
            # This is a simplified approach - in production you'd want a more efficient lookup
            results = await loop.run_in_executor(
                None,
                lambda: self.processing_cache.get_summarizer_results([f"{paper_id}_"]),
            )
            for result in results.values():
                if result and result.status == "success" and result.notion_page_url:
                    return result.notion_page_url
        except Exception as exp:  # noqa: BLE001
            logger.debug(f"Could not get Notion URL for {paper_id}: {exp}")
        return None

    async def _send_notification(
        self,
        subscription: Subscription,
        papers_with_urls: list[tuple],
    ) -> None:
        """Send a notification message for new papers.

        Args:
            subscription: The subscription.
            papers_with_urls: List of (paper, notion_url) tuples.
        """
        header = f"*New papers matching your subscription:*\n_{_escape_markdown(subscription.query)}_\n\n"

        messages = [header]
        for i, (paper, notion_url) in enumerate(papers_with_urls, 1):
            title = _escape_markdown(paper.title)
            if len(title) > MAX_TITLE_LENGTH:
                title = title[:MAX_TITLE_LENGTH] + "\\.\\.\\."

            paper_text = f"{i}\\. *{title}*"
            messages.append(paper_text)

            # Send each paper with its own keyboard
            keyboard = build_notification_keyboard(paper, notion_url)
            try:
                await self.bot.send_message(
                    chat_id=subscription.chat_id,
                    text=header + paper_text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=keyboard,
                )
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
            except Exception as exp:  # noqa: BLE001
                logger.error(f"Error sending notification to {subscription.chat_id}: {exp}")


async def run_subscription_notifications(
    bot_token: str,
    processor: "PapersProcessor",
    processing_cache: "ProcessingCacheStore",
    look_back_days: int = 3,
) -> int:
    """Run subscription notifications.

    Args:
        bot_token: Telegram bot token.
        processor: Papers processor.
        processing_cache: Processing cache.
        look_back_days: Number of days to look back.

    Returns:
        Number of notifications sent.
    """
    service = NotificationService(
        bot_token=bot_token,
        processor=processor,
        processing_cache=processing_cache,
        look_back_days=look_back_days,
    )
    return await service.send_subscription_notifications()
