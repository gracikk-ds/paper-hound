"""Health endpoints."""

from fastapi import Request, Response

from src.routes.routers import status_check_bp

AWESOME_RESPONSE: int = 200


@status_check_bp.get("/ping")
async def ping() -> str:
    """Just a ping pong handle.

    Returns:
        str: A message indicating successful response.
    """
    return "🏓 pong!"


@status_check_bp.get("/health_checker")
async def health_checker() -> Response:
    """Endpoint is used to check if this service responding.

    Returns:
        Response: An HTTP response indicating the health status.
    """
    return Response(status_code=AWESOME_RESPONSE)


@status_check_bp.get("/url_list")
def get_all_urls(request: Request) -> list[dict[str, str]]:
    """Get all the routes from the app.

    Args:
        request (Request): The request object.

    Returns:
        List[Dict[str, str]]: A list of dictionaries containing the path and name of each route.
    """
    return [{"path": route.path, "name": route.name} for route in request.app.routes]
