"""App entrypoints."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from starlette.middleware import Middleware
from starlette_context.middleware import ContextMiddleware
from starlette_context.plugins.correlation_id import CorrelationIdPlugin

from src.containers.containers import init_app_container
from src.handlers.exception_handlers import handle_unexpected_exception
from src.metrics.asgi_metrics import metrics_endpoint
from src.middleware.metrics import PrometheusMiddleware
from src.middleware.process_time import ProcessTimeMiddleware
from src.routes import ai_endpoint, health_endpoints, processor_endpoints, workflow_endpoints  # noqa: F401
from src.routes.routers import processor_router, status_check_bp, storage_router, workflow_router
from src.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for the application."""
    # Start the scheduler
    scheduler = AsyncIOScheduler()
    workflow_service = app.container.workflow()  # type: ignore

    # Schedule the daily job at 08:00
    scheduler.add_job(workflow_service.run_scheduled_job, "cron", hour=6, minute=0)
    scheduler.start()

    # Run the job immediately on startup to debug the workflow
    app.state.startup_job = asyncio.create_task(workflow_service.run_scheduled_job())

    yield

    scheduler.shutdown()


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
    app.include_router(storage_router, prefix="/storage", tags=["storage"])
    app.include_router(processor_router, prefix="/processor", tags=["processor"])
    app.include_router(workflow_router, prefix="/workflow", tags=["workflow"])
    app.add_route("/metrics", metrics_endpoint)
    return app
