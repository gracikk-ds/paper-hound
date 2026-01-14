"""Download a single PDF from a URL to the specified path."""

import os
from pathlib import Path

import requests
from loguru import logger

from src.utils.images_utils import extract_images
from src.utils.schemas import Paper


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


def load_pdf_and_images(paper: Paper) -> tuple[Path | None, Path | None]:
    """Load the PDF and images for the paper.

    Args:
        paper (Paper): the paper to load.

    Returns:
        tuple[Path, Path]: the path to the PDF and the path to the images.
    """
    file_name = f"{paper.title.replace(' ', '_').lower()}.pdf"
    tmp_pdf_path = Path("tmp_storage/tmp_pdfs") / file_name
    tmp_images_path = Path("tmp_storage/tmp_images") / file_name
    try:
        download_pdf(paper.pdf_url, tmp_pdf_path)
        extract_images(str(tmp_pdf_path), str(tmp_images_path))
    except Exception as exp:  # noqa: BLE001
        logger.error(f"Error loading PDF and images for paper: {paper.title}: {exp}")
        return None, None
    return tmp_pdf_path, tmp_images_path
