"""Processor endpoints."""

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Form

from src.containers.containers import AppContainer
from src.routes.routers import processor_router
from src.service.processor import PapersProcessor
from src.utils.schemas import Paper

ProcessorResponseModel = list[Paper]


@processor_router.post("/insert-papers", response_model=None)
@inject
async def insert_papers(
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
    processor.insert_papers(start_date_str, end_date_str)


@processor_router.post("/search-papers", response_model=ProcessorResponseModel)
@inject
async def search_papers(
    query: str = Form(...),
    top_k: int = Form(10),
    start_date_str: str | None = Form(None),
    end_date_str: str | None = Form(None),
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> ProcessorResponseModel:
    """Search papers endpoint.

    Args:
        query (str): query.
        top_k (int): top k.
        start_date_str (str | None): start date.
        end_date_str (str | None): end date.
        processor (PapersProcessor): service for processor.
    """
    return processor.search_papers(query, top_k, start_date_str, end_date_str)


@processor_router.get("/get-paper-by-id", response_model=Paper | None)
@inject
async def get_paper_by_id(
    paper_id: str = Form(...),
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> Paper | None:
    """Get paper by id endpoint.

    Args:
        paper_id (str): paper id.
        processor (PapersProcessor): service for processor.
    """
    return processor.get_paper_by_id(paper_id)
