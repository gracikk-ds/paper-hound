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
    date_obj = None
    if request.date_str:
        try:
            date_obj = datetime.datetime.strptime(request.date_str, "%Y-%m-%d").date()  # noqa: DTZ007
        except ValueError as err:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD.",
            ) from err

    background_tasks.add_task(workflow.process_daily_cycle, date=date_obj)
    return {"status": "accepted", "message": "Workflow started in background."}
