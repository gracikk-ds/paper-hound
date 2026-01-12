"""Ai endpoints."""

import os
from pathlib import Path

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Form
from loguru import logger

from src.containers.containers import AppContainer
from src.routes.routers import processor_router
from src.service.ai_researcher.classifier import Classifier
from src.service.ai_researcher.summarizer import Summarizer
from src.service.arxiv.arxiv_fetcher import ArxivFetcher
from src.service.notion_db.add_content_to_page import MarkdownToNotionUploader
from src.utils.images_utils import add_images_to_md, extract_images
from src.utils.load_utils import download_pdf
from src.utils.schemas import Paper

ProcessorResponseModel = list[Paper]


def load_pdf_and_images(paper: Paper) -> tuple[Path | None, Path | None]:
    """Load the PDF and images for the paper.

    Args:
        paper (Paper): the paper to load.

    Returns:
        tuple[Path, Path]: the path to the PDF and the path to the images.
    """
    file_name = f"{paper.title.replace(' ', '_').lower()}.pdf"
    tmp_pdf_path = Path("tmp_pdfs") / file_name
    tmp_images_path = Path("tmp_images") / file_name
    try:
        download_pdf(paper.pdf_url, tmp_pdf_path)
        extract_images(str(tmp_pdf_path), str(tmp_images_path))
    except Exception as exp:  # noqa: BLE001
        logger.error(f"Error loading PDF and images for paper: {paper.title}: {exp}")
        return None, None
    return tmp_pdf_path, tmp_images_path


@processor_router.post("/summarize-paper", response_model=None)
@inject
async def summarize_paper(
    paper_name_or_id: str = Form(...),
    summarizer_prompt: str | None = Form(None),
    notion_uploader: MarkdownToNotionUploader = Depends(Provide[AppContainer.notion_uploader]),  # noqa: B008
    arxiv_fetcher: ArxivFetcher = Depends(Provide[AppContainer.arxiv_fetcher]),  # noqa: B008
    summarizer: Summarizer = Depends(Provide[AppContainer.summarizer]),  # noqa: B008
) -> str | None:
    """Summarize paper endpoint.

    Args:
        paper_name_or_id (str): the name or ID of the paper to summarize.
        summarizer_prompt (str | None): the prompt to use for the summarizer.
        notion_uploader (MarkdownToNotionUploader): Class to upload markdown files to Notion.
        arxiv_fetcher (ArxivFetcher): Class to fetch and filter arXiv papers.
        summarizer (Summarizer): Class to summarize papers.

    Returns:
        str | None: the URL of the created Notion page, None if an error occurred.
    """
    # Extract paper information
    paper = arxiv_fetcher.extract_paper_by_name_or_id(paper_name_or_id)
    tmp_pdf_path, tmp_images_path = load_pdf_and_images(paper)
    if tmp_pdf_path is None or tmp_images_path is None:
        return None

    # Summarize paper
    _, md_path = summarizer.summarize(paper, tmp_pdf_path, summarizer_prompt)
    if md_path is None:
        logger.error(f"Error summarizing paper: {paper.title}")
        return None
    add_images_to_md(md_path, str(tmp_images_path), paper.model_dump())

    # Upload summary to notion
    notion_page_url = notion_uploader.upload_markdown_file(md_path, category="AdHoc Research")

    # Clean up
    tmp_pdf_path.unlink()
    tmp_images_path.unlink()
    os.remove(md_path)  # noqa: PTH107
    return notion_page_url


@processor_router.post("/classify-paper", response_model=None)
@inject
async def classify_paper(
    paper_name_or_id: str = Form(...),
    classifier_system_prompt: str | None = Form(None),
    arxiv_fetcher: ArxivFetcher = Depends(Provide[AppContainer.arxiv_fetcher]),  # noqa: B008
    classifier: Classifier = Depends(Provide[AppContainer.classifier]),  # noqa: B008
) -> bool | None:
    """Classify paper endpoint.

    Args:
        paper_name_or_id (str): the name or ID of the paper to classify.
        classifier_system_prompt (str): the system prompt to use for the classifier.
        arxiv_fetcher (ArxivFetcher): arxiv fetcher.
        classifier (Classifier): classifier.

    Returns:
        bool | None: True if the paper is about generative image editing, False otherwise, None if an error occurred.
    """
    try:
        paper = arxiv_fetcher.extract_paper_by_name_or_id(paper_name_or_id)
    except ValueError as exp:
        logger.error(f"Error extracting paper: {exp}")
        return None
    return classifier.classify(title=paper.title, summary=paper.summary, system_prompt=classifier_system_prompt)
