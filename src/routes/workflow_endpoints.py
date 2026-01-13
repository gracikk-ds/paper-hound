"""Workflow endpoints."""

import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Form

from src.containers.containers import AppContainer
from src.routes.routers import workflow_router
from src.service.workflow import WorkflowService


@workflow_router.post("/run", response_model=None)
@inject
def run_workflow(
    date_str: str | None = Form(None),
    workflow: WorkflowService = Depends(Provide[AppContainer.workflow]),  # noqa: B008
) -> dict[str, str]:
    """Run the daily workflow manually.

    Args:
        date_str (str | None): Date to run the workflow for (YYYY-MM-DD). Defaults to yesterday if None.
        workflow (WorkflowService): Workflow service.

    Returns:
        dict[str, str]: Status message.
    """
    date_obj = None
    if date_str:
        try:
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
        except ValueError:
            return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD."}

    try:
        workflow.process_daily_cycle(date=date_obj)
        return {"status": "success", "message": "Workflow completed successfully."}  # noqa: TRY300
    except Exception as exp:  # noqa: BLE001
        return {"status": "error", "message": f"Workflow failed: {exp}"}
