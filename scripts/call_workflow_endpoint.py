"""Call the workflow endpoint."""

import sys

import click
import requests
from requests.exceptions import RequestException


@click.command()
@click.option("--url", default="http://localhost:8000", help="Base URL of the API")
@click.option("--date", help="Date to run workflow for (YYYY-MM-DD)")
@click.option("--timeout", default=600, help="Request timeout in seconds")
def main(url: str, date: str | None, timeout: int) -> None:
    """Call the workflow run endpoint."""
    endpoint = f"{url.rstrip('/')}/workflow/run"
    data = {}
    if date:
        data["date_str"] = date

    click.echo(f"Calling endpoint: {endpoint}")
    if date:
        click.echo(f"For date: {date}")

    try:
        response = requests.post(endpoint, data=data, timeout=timeout)
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
