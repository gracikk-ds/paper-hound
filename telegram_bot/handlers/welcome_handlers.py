"""Welcome handler implementations for Telegram bot."""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from telegram_bot.handlers.help_texts import get_command_help

HELP_TEXT = """
*ArXiv Paper Hound Bot*

*Discovery Commands:*
/search \\<query\\> \\[options\\] \\- Semantic search for papers
/similar \\<paper\\_id\\> \\[options\\] \\- Find similar papers
*Search/Similar Options:*
• `k:N` \\- Number of results \\(default: 5\\)
• `t:N` \\- Similarity threshold 0\\-1 \\(default: 0\\.65\\)
• `from:DATE` \\- Start date \\(YYYY\\-MM\\-DD\\)
• `to:DATE` \\- End date \\(YYYY\\-MM\\-DD\\)

/paper \\<paper\\_id\\> \\- Get paper details by arXiv ID

/summarize \\<paper\\_id\\> \\[cat:Category\\] \\[model:Model\\] \\[think:LEVEL\\] \\- Generate AI summary
Accepts arXiv URLs or plain IDs
*Summarize Options:*
• `cat:Name` \\- Research category \\(default: AdHoc Research\\)
• `model:Name` \\- Model name \\(default: gemini-2\\.5\\-pro\\)
• `think:LEVEL` \\- Thinking level \\(default: LOW\\)

*Personal Subscription Commands:*
/topics \\- Show all available topics
/subscribe \\- Subscribe to a topic \\(shows unsubscribed topics\\)
/unsubscribe \\- Remove a subscription \\(shows your subscriptions\\)
/subscriptions \\- List your active subscriptions

*Group Subscription Commands \\(admins only\\):*
/groupsubscribe \\- Subscribe the group to a topic
/groupunsubscribe \\- Remove a group subscription
/groupsubscriptions \\- List group's active subscriptions

*Other Commands:*
/stats \\- Database statistics
/insert \\<start\\_date\\> \\<end\\_date\\> \\- Insert papers \\(admin only\\)
/help \\- Show this message

*Examples:*
`/search transformer architectures for vision`
`/search diffusion models k:10 t:0.5`
`/search attention from:2025\\-01\\-01 to:2025\\-01\\-15`
`/paper 2601.02242`
`/summarize 2601.02242 cat:Image Editing`
`/summarize https://arxiv.org/abs/2601.02242`
"""

WELCOME_TEXT = """
*Welcome to ArXiv Paper Hound\\!*

I help you discover, save, and summarize research papers from arXiv\\.

*Quick Start:*
• Search papers: `/search <your query>`
• Get paper details: `/paper <arxiv_id>`
• Summarize paper using Gemini Model: `/summarize <arxiv_id>`

Type /help for all available commands\\.
"""


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: ARG001
    """Handle the /start command.

    Args:
        update: The update object.
        context: The callback context.
    """
    await update.message.reply_text(WELCOME_TEXT, parse_mode=ParseMode.MARKDOWN_V2)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command.

    Supports:
        /help - Show all commands
        /help <command> - Show help for specific command

    Args:
        update: The update object.
        context: The callback context.
    """
    command = context.args[0] if context.args else None
    help_text = get_command_help(command)
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)
