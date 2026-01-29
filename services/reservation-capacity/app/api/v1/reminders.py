"""Reservation reminder API routes."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.reservation import ReminderCreate, ReminderResponse
from app.services.event_publisher import event_publisher
from app.services.reminder_service import ReminderService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> ReminderService:
    return ReminderService(db, event_publisher)


@router.get("/reservations/{reservation_id}/reminders", response_model=List[ReminderResponse])
async def list_reminders(
    reservation_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: ReminderService = Depends(_get_service),
):
    return await service.list_reminders(reservation_id)


@router.post(
    "/reservations/{reservation_id}/reminders",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_reminder(
    reservation_id: UUID,
    data: ReminderCreate = ...,
    current_user: dict = Depends(get_current_user),
    service: ReminderService = Depends(_get_service),
):
    return await service.schedule_reminder(reservation_id, data)


@router.post("/reservations/{reservation_id}/send-confirmation", response_model=ReminderResponse)
async def send_confirmation(
    reservation_id: UUID,
    current_user: dict = Depends(get_current_user),
    service: ReminderService = Depends(_get_service),
):
    result = await service.send_confirmation(reservation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return result
