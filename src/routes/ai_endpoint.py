"""Ai endpoints."""

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException
from loguru import logger

from src.containers.containers import AppContainer
from src.routes.routers import processor_router
from src.service.ai_researcher.classifier import Classifier
from src.service.arxiv.arxiv_fetcher import ArxivFetcher
from src.service.notion_db.extract_page_content import NotionPageExtractor
from src.service.processor import PapersProcessor
from src.service.workflow import WorkflowService
from src.settings import settings as api_settings
from src.utils.schemas import ClassifyRequest, SummarizeRequest


@processor_router.post("/summarize-paper", response_model=str)
@inject
def summarize_paper(
    request: SummarizeRequest,
    workflow: WorkflowService = Depends(Provide[AppContainer.workflow]),  # noqa: B008
    notion_settings_extractor: NotionPageExtractor = Depends(Provide[AppContainer.notion_settings_extractor]),  # noqa: B008
) -> str:
    """Generate an AI-powered summary of an arXiv paper and publish it to Notion.

    Fetches the specified arXiv paper, generates a detailed summary using the provided
    (or auto-resolved) summarizer prompt, and creates a new page in Notion with the
    formatted summary.

    Args:
        request: The summarization request containing:
            - paper_id (str): The arXiv paper ID (e.g., "2301.07041") or full URL.
            - summarizer_prompt (str, optional): Custom prompt for the summarizer.
                If not provided, automatically resolved from Notion settings based on category.
            - category (str): The research category for prompt lookup and Notion organization.
                Defaults to "AdHoc Research".
        workflow: Injected workflow service for summary generation and upload.
        notion_settings_extractor: Injected extractor for resolving prompts from Notion.

    Returns:
        The URL of the newly created Notion page containing the paper summary.

    Raises:
        HTTPException: 404 if no summarizer prompt found for the specified category.
        HTTPException: 500 if summary generation or Notion upload fails.
    """
    database_id = api_settings.notion_command_database_id
    if request.category and request.summarizer_prompt is None:
        for page_id in notion_settings_extractor.query_database(database_id):
            settings = notion_settings_extractor.extract_settings_from_page(page_id)
            if settings is None:
                continue
            if settings["Page Name"] == request.category:
                request.summarizer_prompt = settings.get("Summarizer Prompt", None)
                break

    if request.summarizer_prompt is None:
        raise HTTPException(status_code=404, detail="Failed to find summarizer prompt for category")

    result = workflow.prepare_paper_summary_and_upload(
        paper_id=request.paper_id,
        summarizer_prompt=request.summarizer_prompt,
        category=request.category or "AdHoc Research",
    )
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
            - paper_id (str): The arXiv paper ID (e.g., "2301.07041") or full URL.
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
    paper = processor.get_paper_by_id(request.paper_id)
    if paper is None:
        try:
            paper = arxiv_fetcher.extract_paper_by_name_or_id(request.paper_id)
        except Exception as exp:
            logger.error(f"Error fetching paper {request.paper_id}: {exp}")
            raise HTTPException(status_code=404, detail="Paper not found") from exp

    if paper is None:
        logger.error(f"Error extracting paper: {request.paper_id}")
        raise HTTPException(status_code=404, detail="Paper not found")

    return classifier.classify(
        title=paper.title,
        summary=paper.summary,
        system_prompt=request.classifier_system_prompt,
    )
