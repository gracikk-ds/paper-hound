"""ASGI metrics."""

import os

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Gauge, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from src.metrics.default_buckets import DEFAULT_BUCKETS
from src.settings import settings

TASK = settings.api_name

REQUESTS = Counter(
    f"{TASK}_starlette_requests_total",
    "Total count of requests by method and path.",
    ["method", "path_template"],
)

RESPONSES = Counter(
    f"{TASK}_starlette_responses_total",
    "Total count of responses by method, path and status codes.",
    ["method", "path_template", "status_code"],
)

REQUESTS_PROCESSING_TIME = Histogram(
    f"{TASK}_starlette_requests_processing_time_seconds",
    "Histogram of requests processing time by path (in seconds)",
    ["method", "path_template"],
    buckets=DEFAULT_BUCKETS,
)

EXCEPTIONS = Counter(
    f"{TASK}_starlette_exceptions_total",
    "Total count of exceptions raised by path and exception type",
    ["method", "path_template", "exception_type"],
)

REQUESTS_IN_PROGRESS = Gauge(
    f"{TASK}_starlette_requests_in_progress",
    "Gauge of requests by method and path currently being processed",
    ["method", "path_template"],
)


def metrics_endpoint(request: Request) -> Response:  # noqa: ARG001
    """Get the metrics.

    Args:
        request: The request.

    Returns:
        Response: The metrics.
    """
    # This import MUST happen at runtime, after process boot and
    # after the env variable has been set up.
    import prometheus_client  # noqa: PLC0415
    from prometheus_client import multiprocess as prom_mp  # noqa: PLC0415

    if "prometheus_multiproc_dir" in os.environ:
        registry = prometheus_client.CollectorRegistry()
        prom_mp.MultiProcessCollector(registry)  # type: ignore
    else:
        registry = REGISTRY

    return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})
