"""Handlers package for the telegram bot."""

from telegram_bot.handlers.callback_handlers import handle_callback_query
from telegram_bot.handlers.main_handlers import handle_paper, handle_search, handle_similar, handle_summarize
from telegram_bot.handlers.storage_handlers import handle_insert, handle_stats
from telegram_bot.handlers.subscription_handlers import (
    handle_subscribe,
    handle_subscriptions,
    handle_topics,
    handle_unsubscribe,
)
from telegram_bot.handlers.welcome_handlers import handle_help, handle_start

__all__ = [
    "handle_callback_query",
    "handle_help",
    "handle_insert",
    "handle_paper",
    "handle_search",
    "handle_similar",
    "handle_start",
    "handle_stats",
    "handle_subscribe",
    "handle_subscriptions",
    "handle_summarize",
    "handle_topics",
    "handle_unsubscribe",
]
