"""Processor endpoints."""

from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Form, HTTPException

from src.containers.containers import AppContainer
from src.routes.routers import processor_router
from src.service.processor import PapersProcessor
from src.utils.schemas import Paper

ProcessorResponseModel = list[Paper]


@processor_router.post("/insert-papers", response_model=None)
@inject
def insert_papers(
    start_date_str: str = Form(...),
    end_date_str: str = Form(...),
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> None:
    """Insert papers endpoint.

    Args:
        start_date_str (str): start date.
        end_date_str (str): end date.
        processor (PapersProcessor): service for processor.
    """
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()  # noqa: DTZ007
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()  # noqa: DTZ007
    processor.insert_papers(start_date, end_date)


@processor_router.post("/search-papers", response_model=ProcessorResponseModel)
@inject
def search_papers(  # noqa: PLR0913
    query: str = Form(...),
    top_k: int = Form(10),
    threshold: float = Form(0.65),
    start_date_str: str | None = Form(None),
    end_date_str: str | None = Form(None),
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> ProcessorResponseModel:
    """Search papers endpoint.

    Args:
        query (str): query.
        top_k (int): top k.
        threshold (float): threshold.
        start_date_str (str | None): start date.
        end_date_str (str | None): end date.
        processor (PapersProcessor): service for processor.
    """
    return processor.search_papers(query, top_k, threshold, start_date_str, end_date_str)


@processor_router.get("/get-paper-by-id", response_model=Paper)
@inject
def get_paper_by_id(
    paper_id: str = Form(...),
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> Paper:
    """Get paper by id endpoint.

    Args:
        paper_id (str): paper id.
        processor (PapersProcessor): service for processor.
    """
    paper = processor.get_paper_by_id(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@processor_router.post("/find-similar-papers", response_model=ProcessorResponseModel)
@inject
def find_similar_papers(  # noqa: PLR0913
    paper_id: str = Form(...),
    top_k: int = Form(5),
    threshold: float = Form(0.65),
    start_date_str: str | None = Form(None),
    end_date_str: str | None = Form(None),
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> ProcessorResponseModel:
    """Find similar papers endpoint.

    Args:
        paper_id (str): paper id.
        top_k (int): top k.
        threshold (float): threshold.
        start_date_str (str | None): start date.
        end_date_str (str | None): end date.
        processor (PapersProcessor): service for processor.
    """
    return processor.find_similar_papers(paper_id, top_k, threshold, start_date_str, end_date_str)


@processor_router.post("/delete-papers", response_model=None)
@inject
def delete_papers(
    paper_ids: list[str] = Form(...),  # noqa: B008
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> None:
    """Delete papers endpoint.

    Args:
        paper_ids (list[str]): list of paper ids.
        processor (PapersProcessor): service for processor.
    """
    processor.delete_papers(paper_ids)


@processor_router.get("/count-papers", response_model=int)
@inject
def count_papers(
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> int:
    """Count papers endpoint.

    Args:
        processor (PapersProcessor): service for processor.
    """
    return processor.count_papers()
