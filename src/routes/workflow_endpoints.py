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
    """Run the daily workflow manually.

    Args:
        background_tasks (BackgroundTasks): Background tasks.
        request (WorkflowRunRequest): Request model.
        workflow (WorkflowService): Workflow service.

    Returns:
        dict[str, str]: Status message.
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
