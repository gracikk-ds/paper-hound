"""Ai endpoints."""

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Form, HTTPException
from loguru import logger

from src.containers.containers import AppContainer
from src.routes.routers import processor_router
from src.service.ai_researcher.classifier import Classifier
from src.service.arxiv.arxiv_fetcher import ArxivFetcher
from src.service.processor import PapersProcessor
from src.service.workflow import WorkflowService
from src.utils.schemas import Paper

ProcessorResponseModel = list[Paper]


@processor_router.post("/summarize-paper", response_model=None)
@inject
def summarize_paper(
    paper_id: str = Form(...),
    summarizer_prompt: str | None = Form(None),
    category: str = Form("AdHoc Research"),
    workflow: WorkflowService = Depends(Provide[AppContainer.workflow]),  # noqa: B008
) -> str | None:
    """Summarize paper endpoint.

    Args:
        paper_id (str): the ID of the paper to summarize.
        summarizer_prompt (str | None): the prompt to use for the summarizer.
        category (str): the category of the paper.
        workflow (WorkflowService): Workflow service.

    Returns:
        str | None: the URL of the created Notion page, None if an error occurred.
    """
    # TODO: Ensure that the paper is not already summarized.
    result = workflow.process_paper_summary_and_upload(
        paper_id=paper_id,
        summarizer_prompt=summarizer_prompt,
        category=category,
    )
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to summarize paper")
    return result


@processor_router.post("/classify-paper", response_model=None)
@inject
def classify_paper(
    paper_id: str = Form(...),
    classifier_system_prompt: str | None = Form(None),
    arxiv_fetcher: ArxivFetcher = Depends(Provide[AppContainer.arxiv_fetcher]),  # noqa: B008
    classifier: Classifier = Depends(Provide[AppContainer.classifier]),  # noqa: B008
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> bool | None:
    """Classify paper endpoint.

    Args:
        paper_id (str): the ID of the paper to classify.
        classifier_system_prompt (str): the system prompt to use for the classifier.
        arxiv_fetcher (ArxivFetcher): arxiv fetcher.
        classifier (Classifier): classifier.
        processor (PapersProcessor): processor.

    Returns:
        bool | None: True if the paper is about generative image editing, False otherwise, None if an error occurred.
    """
    paper = processor.get_paper_by_id(paper_id)
    if paper is None:
        try:
            paper = arxiv_fetcher.extract_paper_by_name_or_id(paper_id)
        except Exception as exp:  # noqa: BLE001
            logger.error(f"Error fetching paper {paper_id}: {exp}")
            raise HTTPException(status_code=404, detail="Paper not found") from exp

    if paper is None:
        logger.error(f"Error extracting paper: {paper_id}")
        raise HTTPException(status_code=404, detail="Paper not found")

    return classifier.classify(title=paper.title, summary=paper.summary, system_prompt=classifier_system_prompt)
