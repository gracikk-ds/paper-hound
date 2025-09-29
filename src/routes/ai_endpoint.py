"""Ai endpoints."""

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Form

from src.ai_researcher.classifier import Classifier
from src.ai_researcher.gemini_researcher import GeminiApiClient
from src.containers.containers import AppContainer
from src.routes.routers import processor_router
from src.utils.schemas import Paper

ProcessorResponseModel = list[Paper]


@processor_router.post("/summarize-paper", response_model=None)
@inject
async def summarize_paper(
    paper: Paper = Form(...),  # noqa: B008
    summarizer: GeminiApiClient = Depends(Provide[AppContainer.summarizer]),  # noqa: B008
) -> None:
    """Summarize paper endpoint.

    Args:
        paper (Paper): the paper to summarize.
        summarizer (GeminiApiClient): summarizer.
    """
    raise NotImplementedError("Not implemented")


@processor_router.post("/classify-paper", response_model=None)
@inject
async def classify_paper(
    paper: Paper = Form(...),  # noqa: B008
    classifier_system_prompt: str = Form(...),
    classifier: Classifier = Depends(Provide[AppContainer.classifier]),  # noqa: B008
) -> None:
    """Classify paper endpoint.

    Args:
        paper (Paper): the paper to classify.
        classifier_system_prompt (str): the system prompt to use for the classifier.
        classifier (Classifier): classifier.
    """
    classifier.classify(
        title=paper.title,
        summary=paper.summary,
        full_date=paper.published_date,
        system_prompt=classifier_system_prompt,
    )
