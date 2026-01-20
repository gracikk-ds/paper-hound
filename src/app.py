"""App entrypoints."""

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from loguru import logger
from starlette.middleware import Middleware
from starlette_context.middleware import ContextMiddleware
from starlette_context.plugins.correlation_id import CorrelationIdPlugin

from src.containers.containers import init_app_container
from src.handlers.exception_handlers import handle_unexpected_exception
from src.metrics.asgi_metrics import metrics_endpoint
from src.middleware.metrics import PrometheusMiddleware
from src.middleware.process_time import ProcessTimeMiddleware
from src.routes import (
    ai_endpoint,
    health_endpoints,  # noqa: F401
    processor_endpoints,
    workflow_endpoints,
)
from src.routes.routers import processor_router, status_check_bp, workflow_router
from src.service.workflow import WorkflowService
from src.settings import settings
from telegram_bot.bot import create_bot_application, run_bot, stop_bot
from telegram_bot.notifications import run_subscription_notifications


async def run_scheduled_workflow_with_notifications(
    workflow_service: WorkflowService,
    bot_token: str,
) -> None:
    """Run the scheduled workflow and then send notifications.

    Args:
        workflow_service: The workflow service instance.
        bot_token: Telegram bot token.
    """
    # Run the workflow and get processed papers by category
    processed_by_category = await workflow_service.run_scheduled_job()

    # Then send notifications to subscribers about processed papers
    try:
        notifications_sent = await run_subscription_notifications(
            bot_token=bot_token,
            processed_by_category=processed_by_category,
        )
        logger.info(f"Sent {notifications_sent} subscription notifications after workflow.")
    except Exception:
        logger.exception("Error sending subscription notifications")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for the application."""
    container = app.container  # type: ignore

    # Initialize Telegram bot
    bot_application = None
    bot_task = None
    if settings.telegram_token:
        admin_ids = {settings.telegram_chat_id} if settings.telegram_chat_id else set()
        bot_application = create_bot_application(
            token=settings.telegram_token,
            container=container,
            admin_user_ids=admin_ids,
        )
        bot_task = asyncio.create_task(run_bot(bot_application))
        logger.info("Telegram bot started.")

    # Start the scheduler with explicit timezone
    scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    workflow_service = container.workflow()

    # Schedule the daily job at 06:00 with notifications
    scheduler.add_job(
        run_scheduled_workflow_with_notifications,
        "cron",
        hour=6,
        minute=0,
        id="daily_workflow",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        args=[workflow_service, settings.telegram_token],
    )
    scheduler.start()
    next_run = scheduler.get_job("daily_workflow").next_run_time
    logger.info(f"Scheduler started with timezone {settings.scheduler_timezone}. Next run: {next_run}")

    yield

    # Cleanup
    scheduler.shutdown()
    if bot_application and bot_task:
        bot_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await bot_task
        await stop_bot(bot_application)
        logger.info("Telegram bot stopped.")


def create_app() -> FastAPI:
    """Create a FastAPI instance with configured routes and middleware.

    Returns:
        FastAPI: An instance of the FastAPI application.
    """
    modules_to_inject = [
        processor_endpoints,
        ai_endpoint,
        workflow_endpoints,
    ]
    container = init_app_container(modules_to_inject, settings)

    middleware = [
        Middleware(ContextMiddleware, plugins=(CorrelationIdPlugin(),)),
        Middleware(ProcessTimeMiddleware),
        Middleware(PrometheusMiddleware, filter_unhandled_paths=True),
    ]

    app: FastAPI = FastAPI(
        title=settings.api_name,
        version=settings.api_version,
        middleware=middleware,
        description="Paper Hound API.",
        lifespan=lifespan,
    )

    # Attach container to app for access in lifespan
    app.container = container  # type: ignore

    # Register the exception handler for catching unexpected errors
    app.add_exception_handler(Exception, handle_unexpected_exception)

    app.include_router(status_check_bp, prefix="/health", tags=["status_check"])
    app.include_router(processor_router, prefix="/processor", tags=["processor"])
    app.include_router(workflow_router, prefix="/workflow", tags=["workflow"])
    app.add_route("/metrics", metrics_endpoint)
    return app
