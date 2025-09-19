"""Exception handlers."""

import traceback
from typing import Any

from fastapi.responses import JSONResponse


async def handle_unexpected_exception(*, exception: Exception, **_: Any) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
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
