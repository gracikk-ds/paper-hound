"""Processor endpoints."""

from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException

from src.containers.containers import AppContainer
from src.routes.routers import processor_router
from src.service.processor import PapersProcessor
from src.utils.schemas import DateRangeRequest, DeletePapersRequest, FindSimilarPapersRequest, Paper, PaperSearchRequest

ProcessorResponseModel = list[Paper]


@processor_router.post("/insert-papers", status_code=201)
@inject
def insert_papers(
    request: DateRangeRequest,
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> None:
    """Insert papers endpoint.

    Args:
        request (DateRangeRequest): request model.
        processor (PapersProcessor): service for processor.
    """
    try:
        start_date = datetime.strptime(request.start_date_str, "%Y-%m-%d").date()  # noqa: DTZ007
        end_date = datetime.strptime(request.end_date_str, "%Y-%m-%d").date()  # noqa: DTZ007
        processor.insert_papers(start_date, end_date)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD") from err


@processor_router.post("/search-papers", response_model=ProcessorResponseModel)
@inject
def search_papers(
    request: PaperSearchRequest,
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> ProcessorResponseModel:
    """Search papers endpoint.

    Args:
        request (PaperSearchRequest): request model.
        processor (PapersProcessor): service for processor.
    """
    return processor.search_papers(
        request.query,
        request.top_k,
        request.threshold,
        request.start_date_str,
        request.end_date_str,
    )


@processor_router.get("/papers/{paper_id}", response_model=Paper)
@inject
def get_paper_by_id(
    paper_id: str,
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
def find_similar_papers(
    request: FindSimilarPapersRequest,
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> ProcessorResponseModel:
    """Find similar papers endpoint.

    Args:
        request (FindSimilarPapersRequest): request model.
        processor (PapersProcessor): service for processor.
    """
    return processor.find_similar_papers(
        request.paper_id,
        request.top_k,
        request.threshold,
        request.start_date_str,
        request.end_date_str,
    )


@processor_router.post("/delete-papers", status_code=204)
@inject
def delete_papers(
    request: DeletePapersRequest,
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> None:
    """Delete papers endpoint.

    Args:
        request (DeletePapersRequest): request model.
        processor (PapersProcessor): service for processor.
    """
    processor.delete_papers(request.paper_ids)


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
