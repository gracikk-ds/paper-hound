"""Download a single PDF from a URL to the specified path."""

import os
from pathlib import Path

import requests


def download_pdf(pdf_url: str, pdf_path: Path) -> None:
    """Download a single PDF from a URL to the specified path.

    Args:
        pdf_url (str): The URL of the PDF to download.
        pdf_path (Path): The local file path to save the downloaded PDF.
    """
    file_dir = pdf_path.parent
    os.makedirs(file_dir, exist_ok=True)
    response = requests.get(pdf_url, stream=True, timeout=60)
    response.raise_for_status()
    with open(pdf_path, "wb") as pdf_file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                pdf_file.write(chunk)
