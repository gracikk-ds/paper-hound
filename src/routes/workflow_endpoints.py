"""Workflow endpoints."""

import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import BackgroundTasks, Depends, HTTPException

from src.containers.containers import AppContainer
from src.routes.routers import workflow_router
from src.service.workflow import WorkflowService
from src.utils.schemas import WorkflowRunRequest


@workflow_router.post("/run", status_code=202)
@inject
def run_workflow(
    background_tasks: BackgroundTasks,
    request: WorkflowRunRequest,
    workflow: WorkflowService = Depends(Provide[AppContainer.workflow]),  # noqa: B008
) -> dict[str, str]:
    """Trigger the paper discovery and summarization workflow.

    Starts a background workflow that fetches new papers from arXiv, optionally
    classifies them, and generates summaries for relevant papers. The workflow
    runs asynchronously and returns immediately with acceptance status.

    Args:
        background_tasks: FastAPI background task manager.
        request: The workflow configuration containing:
            - start_date_str (str, optional): Start of date range (YYYY-MM-DD).
                Defaults to yesterday.
            - end_date_str (str, optional): End of date range (YYYY-MM-DD).
                Defaults to today.
            - skip_ingestion (bool): Skip fetching new papers if True. Defaults to False.
            - use_classifier (bool): Filter papers using AI classifier. Defaults to True.
            - top_k (int): Number of top papers to process. Defaults to 10.
            - category (str, optional): Research category for prompt selection.
        workflow: Injected workflow service for orchestrating the pipeline.

    Returns:
        Status dict with "status": "accepted" and confirmation message.

    Raises:
        HTTPException: 400 if date format is invalid (expected YYYY-MM-DD).
    """
    try:
        if request.start_date_str:
            start_date = datetime.datetime.strptime(request.start_date_str, "%Y-%m-%d").date()  # noqa: DTZ007
        else:
            start_date = datetime.date.today() - datetime.timedelta(days=1)  # noqa: DTZ011

        if request.end_date_str:
            end_date = datetime.datetime.strptime(request.end_date_str, "%Y-%m-%d").date()  # noqa: DTZ007
        else:
            end_date = datetime.date.today()  # noqa: DTZ011

    except ValueError as err:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD.",
        ) from err

    background_tasks.add_task(
        workflow.run_workflow,
        start_date=start_date,
        end_date=end_date,
        skip_ingestion=request.skip_ingestion,
        use_classifier=request.use_classifier,
        top_k=request.top_k,
        category=request.category,
    )
    return {"status": "accepted", "message": "Workflow started in background."}
