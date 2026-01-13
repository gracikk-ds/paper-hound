"""Ai endpoints."""

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


@processor_router.post("/summarize-paper", response_model=str)
@inject
def summarize_paper(
    request: SummarizeRequest,
    workflow: WorkflowService = Depends(Provide[AppContainer.workflow]),  # noqa: B008
) -> str:
    """Summarize paper endpoint.

    Args:
        request (SummarizeRequest): Request model.
        workflow (WorkflowService): Workflow service.

    Returns:
        str: the URL of the created Notion page.
    """
    # TODO: Ensure that the paper is not already summarized.
    result = workflow.process_paper_summary_and_upload(
        paper_id=request.paper_id,
        summarizer_prompt=request.summarizer_prompt,
        category=request.category,
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
    """Classify paper endpoint.

    Args:
        request (ClassifyRequest): Request model.
        arxiv_fetcher (ArxivFetcher): arxiv fetcher.
        classifier (Classifier): classifier.
        processor (PapersProcessor): processor.

    Returns:
        bool: True if the paper is about generative image editing, False otherwise.
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
