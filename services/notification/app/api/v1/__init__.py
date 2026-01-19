"""API v1 routes."""
from fastapi import APIRouter

from app.api.v1 import notifications, templates, webhooks

api_router = APIRouter()
api_router.include_router(notifications.router)
api_router.include_router(templates.router)
api_router.include_router(webhooks.router)
