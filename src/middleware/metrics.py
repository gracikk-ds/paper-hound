"""Prometheus middleware."""

import time

from starlette.routing import Match
from starlette.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.metrics.asgi_metrics import EXCEPTIONS, REQUESTS, REQUESTS_IN_PROGRESS, REQUESTS_PROCESSING_TIME, RESPONSES


class PrometheusMiddleware:
    """Middleware to collect metrics for the API."""

    def __init__(self, app: ASGIApp, *, filter_unhandled_paths: bool = False) -> None:
        """Initialize the Prometheus middleware.

        Args:
            app: The ASGI app to wrap.
            filter_unhandled_paths: Whether to filter unhandled paths.
        """
        self.app = app
        self.filter_unhandled_paths = filter_unhandled_paths

    @staticmethod
    def get_path_template(scope: Scope) -> tuple[str, bool]:
        """Get the path template and whether it's handled.

        Args:
            scope: The ASGI scope.

        Returns:
            Tuple[str, bool]: The path template and whether it's handled.
        """
        for route in scope["app"].routes:
            match, _ = route.matches(scope)
            if match == Match.FULL:
                return route.path, True
        return scope["path"], False

    def _should_filter(self, *, is_handled_path: bool) -> bool:
        """Determine if the path should be filtered.

        Args:
            is_handled_path: Whether the path is handled.

        Returns:
            bool: Whether the path should be filtered.
        """
        return self.filter_unhandled_paths and not is_handled_path

    @staticmethod
    def _record_processing_time(method: str, path_template: str, start_time: float) -> None:
        """Record request processing time.

        Args:
            method: The HTTP method.
            path_template: The path template.
            start_time: The start time of the request.
        """
        duration = time.perf_counter() - start_time
        REQUESTS_PROCESSING_TIME.labels(method=method, path_template=path_template).observe(duration)

    @staticmethod
    def _finalize_request(method: str, path_template: str, status_code: int) -> None:
        """Finalize metrics for the request.

        Args:
            method: The HTTP method.
            path_template: The path template.
            status_code: The status code.
        """
        RESPONSES.labels(method=method, path_template=path_template, status_code=status_code).inc()
        REQUESTS_IN_PROGRESS.labels(method=method, path_template=path_template).dec()

    async def _process_request(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        method: str,
        path_template: str,
    ) -> None:
        """Process request and collect metrics.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive function.
            send: The ASGI send function.
            method: The HTTP method.
            path_template: The path template.

        Raises:
            BaseException: Any exception raised by the wrapped app.
        """
        status_code = HTTP_200_OK
        REQUESTS_IN_PROGRESS.labels(method=method, path_template=path_template).inc()
        REQUESTS.labels(method=method, path_template=path_template).inc()
        before_time = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except BaseException as exp:
            status_code = HTTP_500_INTERNAL_SERVER_ERROR
            EXCEPTIONS.labels(
                method=method,
                path_template=path_template,
                exception_type=type(exp).__name__,
            ).inc()
            raise
        else:
            self._record_processing_time(method, path_template, before_time)
        finally:
            self._finalize_request(method, path_template, status_code)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process the request and collect metrics.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive function.
            send: The ASGI send function.
        """
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path_template, is_handled_path = self.get_path_template(scope)

        if self._should_filter(is_handled_path=is_handled_path):
            await self.app(scope, receive, send)
            return

        await self._process_request(scope, receive, send, method, path_template)
