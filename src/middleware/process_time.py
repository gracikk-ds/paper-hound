"""Middleware for processing time header."""

from collections.abc import Awaitable, Callable
from time import time

from fastapi import Request
from fastapi.responses import Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class ProcessTimeMiddleware(BaseHTTPMiddleware):
    """Middleware for processing time header."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Dispatch the middleware.

        Args:
            request (Request): The request object.
            call_next (Callable[[Request], Awaitable[Response]]): The next middleware or endpoint to call.

        Returns:
            Response: The response object.
        """
        start_time = time() * 1000  # time in millis
        response = await call_next(request)
        process_time = time() * 1000 - start_time
        response.headers["X-Process-Time"] = str(process_time)
        logger.info(f"Total request time: {process_time!s} ms")
        return response
