"""Exception handlers."""

import traceback
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


async def handle_unexpected_exception(request: Request, exception: Exception, **_: Any) -> JSONResponse:  # noqa: ARG001
    """Handle unexpected exceptions.

    Args:
        request (Request): The request object.
        exception (Exception): The exception object.

    Returns:
        JSONResponse: The JSON response.
    """
    return JSONResponse(
        content={
            "error": "error.unexpected",
            "detail": {
                "exception": {
                    "class": str(exception.__class__),
                    "traceback": "".join(traceback.TracebackException.from_exception(exception).format()),
                },
            },
        },
        status_code=500,
    )
