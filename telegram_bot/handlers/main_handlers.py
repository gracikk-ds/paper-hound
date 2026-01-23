"""Command handler implementations for Telegram bot."""

import asyncio

from loguru import logger
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from telegram_bot.context import bot_context
from telegram_bot.formatters import (
    _escape_markdown,
    format_paper_detailed,
    format_paper_short,
    format_search_results,
    format_similar_results,
)
from telegram_bot.handlers.handlers_utils import parse_search_params, parse_summarize_params, validate_summarize_params
from telegram_bot.handlers.schemas import SearchParams
from telegram_bot.keyboards import (
    build_paper_actions_keyboard,
    build_paper_list_keyboard,
    build_summary_result_keyboard,
)


async def handle_paper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /paper command.

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text("Usage: /paper <paper_id>\nExample: /paper 2601.02242")
        return

    paper_id = context.args[0].strip()
    await update.message.reply_text(f"Fetching paper `{paper_id}`\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        processor = bot_context.container.processor()
        arxiv_fetcher = bot_context.container.arxiv_fetcher()
        loop = asyncio.get_running_loop()

        # Fetch from storage or arXiv (stores if fetched from arXiv)
        paper = await loop.run_in_executor(
            None,
            lambda: processor.fetch_and_store_paper(paper_id, arxiv_fetcher),
        )

        if paper is None:
            await update.message.reply_text(f"Paper not found: {paper_id}")
            return

        message = format_paper_detailed(paper)
        keyboard = build_paper_actions_keyboard(paper)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)
    except Exception as exp:
        logger.error(f"Error fetching paper: {exp}")
        await update.message.reply_text("An error occurred while fetching the paper. Please try again.")


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /search command.

    Supports optional parameters:
        k:N         - Number of results (default: 5)
        t:N         - Similarity threshold 0-1 (default: 0.65)
        from:DATE   - Start date (YYYY-MM-DD)
        to:DATE     - End date (YYYY-MM-DD)

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /search <query> [options]\n\n"
            "Options:\n"
            "  k:N - Number of results (default: 5)\n"
            "  t:N - Threshold 0-1 (default: 0.65)\n"
            "  from:DATE - Start date (YYYY-MM-DD)\n"
            "  to:DATE - End date (YYYY-MM-DD)\n\n"
            "Example: /search neural radiance fields k:10 t:0.5",
        )
        return

    params = parse_search_params(context.args)

    if not params.query:
        await update.message.reply_text("Please provide a search query.")
        return

    escaped_query = _escape_markdown(params.query)
    await update.message.reply_text(f"Searching for: _{escaped_query}_\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        processor = bot_context.container.processor()
        loop = asyncio.get_running_loop()
        papers = await loop.run_in_executor(
            None,
            lambda: processor.search_papers(
                query=params.query,
                k=params.top_k,
                threshold=params.threshold,
                start_date_str=params.start_date_str,
                end_date_str=params.end_date_str,
            ),
        )

        if not papers:
            await update.message.reply_text(f"No papers found for: {params.query}")
            return

        # Store papers in context for callback handling
        context.user_data["last_search_papers"] = {p.paper_id: p for p in papers}

        message = format_search_results(papers, params.query)
        keyboard = build_paper_list_keyboard(papers)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)
    except Exception as exp:
        logger.error(f"Error in search: {exp}")
        await update.message.reply_text("An error occurred while searching. Please try again.")


async def handle_similar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /similar command.

    Supports optional parameters:
        k:N         - Number of results (default: 5)
        t:N         - Similarity threshold 0-1 (default: 0.65)
        from:DATE   - Start date (YYYY-MM-DD)
        to:DATE     - End date (YYYY-MM-DD)

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /similar <paper_id> [options]\n\n"
            "Options:\n"
            "  k:N - Number of results (default: 5)\n"
            "  t:N - Threshold 0-1 (default: 0.65)\n"
            "  from:DATE - Start date (YYYY-MM-DD)\n"
            "  to:DATE - End date (YYYY-MM-DD)\n\n"
            "Example: /similar 2601.02242 k:10",
        )
        return

    # First arg is paper_id, rest are optional params
    paper_id = context.args[0].strip()
    params = parse_search_params(context.args[1:]) if len(context.args) > 1 else SearchParams(query="")

    escaped_id = _escape_markdown(paper_id)
    await update.message.reply_text(
        f"Finding papers similar to `{escaped_id}`\\.\\.\\.",
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
            await update.message.reply_text(f"Paper not found: {paper_id}")
            return

        papers = await loop.run_in_executor(
            None,
            lambda: processor.find_similar_papers(
                paper_id=source_paper.paper_id,
                k=params.top_k,
                threshold=params.threshold,
                start_date_str=params.start_date_str,
                end_date_str=params.end_date_str,
            ),
        )

        if not papers:
            await update.message.reply_text(f"No similar papers found for: {paper_id}")
            return

        context.user_data["last_search_papers"] = {p.paper_id: p for p in papers}

        message = format_similar_results(papers, paper_id)
        keyboard = build_paper_list_keyboard(papers)
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)
    except Exception as exp:
        logger.error(f"Error finding similar papers: {exp}")
        await update.message.reply_text("An error occurred. Please try again.")


async def handle_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /summarize command.

    Supports optional parameters:
        cat:CategoryName - Research category (default: AdHoc Research)
        model:ModelName - Model name to use for summarization
        think:LEVEL - Thinking level (LOW, MEDIUM, HIGH)

    Accepts paper IDs or full arXiv/alphaxiv URLs.

    Args:
        update: The update object.
        context: The callback context.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: /summarize <paper_id|url> [options]\n\n"
            "Options:\n"
            "  cat:Name - Research category (default: AdHoc Research)\n"
            "  model:Name - Model name (e.g., gemini-3-pro-preview)\n"
            "  think:LEVEL - Thinking level (LOW, MEDIUM, HIGH)\n\n"
            "Examples:\n"
            "  /summarize 2601.02242\n"
            "  /summarize https://arxiv.org/abs/2601.02242\n"
            "  /summarize 2601.02242 cat:ML\n"
            "  /summarize 2601.02242 model:gemini-3-pro-preview think:HIGH",
        )
        return

    params = parse_summarize_params(context.args)

    if not params.paper_id:
        await update.message.reply_text("Please provide a paper ID or arXiv URL.")
        return

    # Validate model name and thinking level
    validation_error = validate_summarize_params(params)
    if validation_error:
        await update.message.reply_text(f"Invalid parameters:\n\n{validation_error}")
        return

    escaped_id = _escape_markdown(params.paper_id)
    escaped_cat = _escape_markdown(params.category)

    # Build status message with model/thinking info if specified
    status_parts = [f"Generating summary for `{escaped_id}` \\(category: {escaped_cat}\\)"]
    if params.model_name:
        escaped_model = _escape_markdown(params.model_name)
        status_parts.append(f"Model: {escaped_model}")
    if params.thinking_level:
        status_parts.append(f"Thinking: {params.thinking_level}")
    status_parts.append("This may take a few minutes\\.")

    status_msg = await update.message.reply_text(
        "\n".join(status_parts),
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        workflow = bot_context.container.workflow()
        processor = bot_context.container.processor()
        arxiv_fetcher = bot_context.container.arxiv_fetcher()
        loop = asyncio.get_running_loop()

        notion_url = await loop.run_in_executor(
            None,
            lambda: workflow.prepare_paper_summary_and_upload(
                paper_id=params.paper_id,
                category=params.category,
                model_name=params.model_name,
                thinking_level=params.thinking_level,
            ),
        )
        costs = workflow.summarizer.inference_price
        costs_str = f"{costs:.3f}".replace(".", "\\.")

        if notion_url:
            # Fetch paper info to enrich the summary message
            paper = await loop.run_in_executor(
                None,
                lambda: processor.fetch_and_store_paper(params.paper_id, arxiv_fetcher),
            )

            keyboard = build_summary_result_keyboard(params.paper_id, notion_url)

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
            await status_msg.edit_text("Failed to generate summary. Please try again.")
    except Exception as exp:
        logger.error(f"Error summarizing paper: {exp}")
        await status_msg.edit_text("An error occurred while generating the summary. Please try again.")
