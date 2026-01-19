"""Call the workflow endpoint."""

import sys

import click
import requests
from requests.exceptions import RequestException


@click.command()
@click.option("--url", default="http://0.0.0.0:8001", help="Base URL of the API")
@click.option("--start-date", help="Start date for workflow (YYYY-MM-DD)")
@click.option("--end-date", help="End date for workflow (YYYY-MM-DD)")
@click.option("--skip-ingestion", is_flag=True, help="Skip ingestion of new papers")
@click.option("--use-classifier", default=True, help="Use classifier to filter papers")
@click.option("--top-k", type=int, default=5, help="Number of top papers to process")
@click.option("--category", default=None, help="Category to process")
@click.option("--timeout", default=600, help="Request timeout in seconds")
def main(  # noqa: PLR0913
    url: str,
    start_date: str | None,
    end_date: str | None,
    top_k: int,
    category: str | None,
    timeout: int,
    *,
    skip_ingestion: bool,
    use_classifier: bool,
) -> None:
    """Call the workflow run endpoint."""
    endpoint = f"{url.rstrip('/')}/workflow/run"
    data: dict[str, str] = {}
    if start_date:
        data["start_date_str"] = start_date
    if end_date:
        data["end_date_str"] = end_date
    data["skip_ingestion"] = skip_ingestion
    data["use_classifier"] = use_classifier
    data["top_k"] = top_k
    data["category"] = category

    click.echo(f"Calling endpoint: {endpoint}")
    if start_date:
        click.echo(f"Start date: {start_date}")
    if end_date:
        click.echo(f"End date: {end_date}")

    try:
        response = requests.post(endpoint, json=data, timeout=timeout)
        response.raise_for_status()
        click.echo(f"Status Code: {response.status_code}")
        click.echo(f"Response: {response.json()}")
    except RequestException as e:
        click.echo(f"Error calling endpoint: {e}", err=True)
        if hasattr(e, "response") and e.response is not None:
            click.echo(f"Server response: {e.response.text}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
