"""Initialize all the routers for the API."""

from fastapi import APIRouter

processor_router = APIRouter(tags=["processor"])
status_check_bp = APIRouter(tags=["status_check"])
workflow_router = APIRouter(tags=["workflow"])
