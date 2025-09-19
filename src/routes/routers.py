"""Initialize all the routers for the API."""

from fastapi import APIRouter

processor_router = APIRouter(tags=["processor"])
storage_router = APIRouter(tags=["storage"])
status_check_bp = APIRouter(tags=["status_check"])
