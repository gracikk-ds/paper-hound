"""AI-powered endpoints for arXiv paper processing.

This module provides FastAPI endpoints for summarizing and classifying arXiv papers
using AI models. It integrates with Notion for publishing summaries and supports
custom classification prompts.

Endpoints:
    POST /summarize-paper: Generate an AI-powered summary of an arXiv paper and publish it to Notion.
    POST /classify-paper: Classify an arXiv paper based on a custom classification prompt.
"""

import re
from urllib.parse import urlparse

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException
from loguru import logger

from src.containers.containers import AppContainer
from src.routes.routers import processor_router
from src.service.ai_researcher.classifier import Classifier
from src.service.arxiv.arxiv_fetcher import ArxivFetcher
from src.service.processor import PapersProcessor
from src.service.workflow import WorkflowService
from src.utils.schemas import ClassifyRequest, SummarizeRequest


def _normalize_category(category: str | None) -> str:
    """Normalize the category value.

    Args:
        category: Raw category from the request.

    Returns:
        Normalized category name, defaulting to "AdHoc Research".
    """
    if category is None:
        return "AdHoc Research"
    normalized = category.strip()
    return normalized or "AdHoc Research"


def _normalize_paper_id(paper_id: str) -> str:
    """Normalize a paper identifier or arXiv URL.

    Args:
        paper_id: Raw paper ID or URL.

    Returns:
        Normalized paper ID string.
    """
    cleaned = paper_id.strip()
    if cleaned.startswith(("http://", "https://")):
        parsed = urlparse(cleaned)
        if parsed.netloc.endswith(("arxiv.org", "alphaxiv.org")):
            path = parsed.path.strip("/")
            if path.startswith(("abs/", "pdf/")):
                cleaned = path.split("/", 1)[1].replace(".pdf", "")

    match = re.match(r"^(\d{4}\.\d{5})(?:v\d+)?$", cleaned)
    return match.group(1) if match else cleaned


@processor_router.post("/summarize-paper", response_model=str)
@inject
def summarize_paper(
    request: SummarizeRequest,
    workflow: WorkflowService = Depends(Provide[AppContainer.workflow]),  # noqa: B008
) -> str:
    """Generate an AI-powered summary of an arXiv paper and publish it to Notion.

    Fetches the specified arXiv paper, generates a detailed summary using the default
    summarizer prompt, and creates a new page in Notion with the formatted summary.

    Args:
        request: The summarization request containing:
            - paper_id (str): The arXiv paper ID (e.g., "2601.02242") or full URL.
            - category (str): The research category for Notion organization. Defaults to "AdHoc Research".
            - model_name (str | None): Optional model name to override the default.
            - thinking_level (Literal["LOW", "MEDIUM", "HIGH"] | None): Optional thinking level.
        workflow: Injected workflow service for summary generation and upload.

    Returns:
        The URL of the newly created Notion page containing the paper summary.

    Raises:
        HTTPException: 500 if summary generation or Notion upload fails.
    """
    category = _normalize_category(request.category)

    try:
        result = workflow.prepare_paper_summary_and_upload(
            paper_id=request.paper_id,
            category=category,
            model_name=request.model_name,
            thinking_level=request.thinking_level,
        )
    except Exception as exp:
        logger.error(f"Error generating summary for {request.paper_id}: {exp}")
        raise HTTPException(status_code=500, detail="Failed to summarize paper") from exp
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to summarize paper")
    return result


@processor_router.post("/classify-paper", response_model=bool)
@inject
def classify_paper(
    request: ClassifyRequest,
    arxiv_fetcher: ArxivFetcher = Depends(Provide[AppContainer.arxiv_fetcher]),  # noqa: B008
    classifier: Classifier = Depends(Provide[AppContainer.classifier]),  # noqa: B008
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> bool:
    """Classify an arXiv paper based on a custom classification prompt.

    Evaluates whether a paper matches specific criteria defined in your classification
    prompt. First attempts to retrieve the paper from the local database; if not found,
    fetches directly from arXiv.

    Args:
        request: The classification request containing:
            - paper_id (str): The arXiv paper ID (e.g., "2601.02242") or full URL.
            - classifier_system_prompt (str): The system prompt defining classification
                criteria. The classifier analyzes the paper's title and abstract against
                this prompt to determine relevance.
        arxiv_fetcher: Injected fetcher for retrieving papers from arXiv.
        classifier: Injected classifier service for paper evaluation.
        processor: Injected processor for local database paper lookup.

    Returns:
        True if the paper matches the classification criteria, False otherwise.

    Raises:
        HTTPException: 404 if paper not found in local database and arXiv fetch fails.

    Example:
        Use cases include filtering papers by research domain (e.g., "Is this paper
        about generative image editing?"), identifying methodology types, or topic
        screening for literature reviews.
    """
    normalized_paper_id = _normalize_paper_id(request.paper_id)
    paper = processor.get_paper_by_id(normalized_paper_id)
    if paper is None:
        try:
            paper = arxiv_fetcher.extract_paper_by_name_or_id(normalized_paper_id)
        except Exception as exp:
            logger.error(f"Error fetching paper {request.paper_id}: {exp}")
            raise HTTPException(status_code=404, detail="Paper not found") from exp

    if paper is None:
        logger.error(f"Error extracting paper: {request.paper_id}")
        raise HTTPException(status_code=404, detail="Paper not found")

    try:
        return classifier.classify(
            title=paper.title,
            summary=paper.summary,
            system_prompt=request.classifier_system_prompt,
        )
    except Exception as exp:
        logger.error(f"Error classifying paper {request.paper_id}: {exp}")
        raise HTTPException(status_code=500, detail="Failed to classify paper") from exp
