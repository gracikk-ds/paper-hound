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
    """Fetch and store arXiv papers published within a date range.

    Queries the arXiv API for papers published between the specified dates,
    generates embeddings, and stores them in the vector database for later search.

    Args:
        request: The date range request containing:
            - start_date_str (str): Start date in YYYY-MM-DD format (inclusive).
            - end_date_str (str): End date in YYYY-MM-DD format (inclusive).
        processor: Injected processor service for paper ingestion.

    Raises:
        HTTPException: 400 if date format is invalid (expected YYYY-MM-DD).
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
    """Search for papers using semantic similarity.

    Performs a vector similarity search against stored paper embeddings to find
    papers that semantically match the query text.

    Args:
        request: The search request containing:
            - query (str): Natural language search query.
            - top_k (int): Maximum number of results to return. Defaults to 10.
            - threshold (float): Minimum similarity score (0-1). Defaults to 0.65.
            - start_date_str (str, optional): Filter results from this date (YYYY-MM-DD).
            - end_date_str (str, optional): Filter results until this date (YYYY-MM-DD).
        processor: Injected processor service for paper search.

    Returns:
        List of Paper objects matching the search criteria, ordered by relevance.
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
    """Retrieve a specific paper by its arXiv ID.

    Fetches complete paper metadata from the local vector database.

    Args:
        paper_id: The arXiv paper ID (e.g., "2301.07041").
        processor: Injected processor service for paper retrieval.

    Returns:
        Paper object containing title, authors, abstract, dates, and PDF URL.

    Raises:
        HTTPException: 404 if paper is not found in the database.
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
    """Find papers similar to a given paper.

    Uses the embedding of the specified paper to find other papers with similar
    content via vector similarity search.

    Args:
        request: The similarity search request containing:
            - paper_id (str): The arXiv ID of the reference paper.
            - top_k (int): Maximum number of similar papers to return. Defaults to 5.
            - threshold (float): Minimum similarity score (0-1). Defaults to 0.65.
            - start_date_str (str, optional): Filter results from this date (YYYY-MM-DD).
            - end_date_str (str, optional): Filter results until this date (YYYY-MM-DD).
        processor: Injected processor service for similarity search.

    Returns:
        List of Paper objects similar to the reference paper, ordered by similarity.
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
    """Delete papers from the vector database.

    Permanently removes the specified papers and their embeddings from storage.

    Args:
        request: The deletion request containing:
            - paper_ids (list[str]): List of arXiv paper IDs to delete.
        processor: Injected processor service for paper deletion.
    """
    processor.delete_papers(request.paper_ids)


@processor_router.get("/count-papers", response_model=int)
@inject
def count_papers(
    processor: PapersProcessor = Depends(Provide[AppContainer.processor]),  # noqa: B008
) -> int:
    """Get the total number of papers in the database.

    Returns the count of all papers currently stored in the vector database.

    Args:
        processor: Injected processor service for database operations.

    Returns:
        Total number of papers stored in the database.
    """
    return processor.count_papers()
