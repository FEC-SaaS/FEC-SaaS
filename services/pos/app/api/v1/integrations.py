"""External POS integration API routes for the POS service."""

import math
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.pos import ExternalPOSIntegration, POSSyncLog
from app.schemas.pos import (
    IntegrationCreate,
    IntegrationResponse,
    IntegrationUpdate,
    PaginatedResponse,
    SyncLogResponse,
)
from app.services.event_publisher import event_publisher

router = APIRouter()
settings = get_settings()


# ---------------------------------------------------------------------------
# Inline integration service
# ---------------------------------------------------------------------------
class _IntegrationService:
    """Lightweight service for external POS integration management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_integrations(self, venue_id: UUID) -> List[ExternalPOSIntegration]:
        result = await self.db.execute(
            select(ExternalPOSIntegration)
            .where(ExternalPOSIntegration.venue_id == venue_id)
            .order_by(ExternalPOSIntegration.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_integration(
        self, venue_id: UUID, data: IntegrationCreate
    ) -> ExternalPOSIntegration:
        integration = ExternalPOSIntegration(
            venue_id=venue_id,
            provider=data.provider.value if hasattr(data.provider, "value") else data.provider,
            provider_name=data.provider_name,
            api_key_encrypted=data.api_key,
            api_secret_encrypted=data.api_secret,
            location_id=data.location_id,
            webhook_url=data.webhook_url,
            sync_frequency_minutes=data.sync_frequency_minutes,
            config=data.config,
        )
        self.db.add(integration)
        await self.db.commit()
        await self.db.refresh(integration)
        return integration

    async def get_integration(self, integration_id: UUID) -> ExternalPOSIntegration | None:
        result = await self.db.execute(
            select(ExternalPOSIntegration)
            .where(ExternalPOSIntegration.id == integration_id)
        )
        return result.scalar_one_or_none()

    async def update_integration(
        self, integration_id: UUID, data: IntegrationUpdate
    ) -> ExternalPOSIntegration | None:
        integration = await self.get_integration(integration_id)
        if not integration:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(integration, field, value)
        await self.db.commit()
        await self.db.refresh(integration)
        return integration

    async def trigger_sync(self, integration_id: UUID) -> POSSyncLog | None:
        integration = await self.get_integration(integration_id)
        if not integration:
            return None
        sync_log = POSSyncLog(
            integration_id=integration.id,
            venue_id=integration.venue_id,
            sync_type="manual",
            status="in_progress",
            records_synced=0,
            records_failed=0,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(sync_log)
        await self.db.commit()
        await self.db.refresh(sync_log)
        return sync_log

    async def get_sync_logs(
        self, integration_id: UUID, page: int, page_size: int
    ) -> tuple[list[POSSyncLog], int]:
        base = select(POSSyncLog).where(POSSyncLog.integration_id == integration_id)

        # Count
        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        # Items
        result = await self.db.execute(
            base.order_by(desc(POSSyncLog.started_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total


def _get_service(db: AsyncSession = Depends(get_db)) -> _IntegrationService:
    return _IntegrationService(db)


# ---------------------------------------------------------------------------
# GET /pos/integrations — list integrations
# ---------------------------------------------------------------------------
@router.get(
    "/pos/integrations",
    response_model=List[IntegrationResponse],
    summary="List external POS integrations",
)
async def list_integrations(
    venue_id: UUID = Query(..., description="Venue to list integrations for"),
    service: _IntegrationService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> List[IntegrationResponse]:
    """Return all external POS integrations for a venue."""
    integrations = await service.list_integrations(venue_id)
    return [IntegrationResponse.model_validate(i) for i in integrations]


# ---------------------------------------------------------------------------
# POST /pos/integrations — create an integration
# ---------------------------------------------------------------------------
@router.post(
    "/pos/integrations",
    response_model=IntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an external POS integration",
)
async def create_integration(
    body: IntegrationCreate,
    venue_id: UUID = Query(..., description="Venue to create the integration for"),
    service: _IntegrationService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> IntegrationResponse:
    """Create a new external POS integration for a venue."""
    integration = await service.create_integration(venue_id, body)
    return IntegrationResponse.model_validate(integration)


# ---------------------------------------------------------------------------
# PUT /pos/integrations/{integration_id} — update an integration
# ---------------------------------------------------------------------------
@router.put(
    "/pos/integrations/{integration_id}",
    response_model=IntegrationResponse,
    summary="Update an external POS integration",
)
async def update_integration(
    integration_id: UUID,
    body: IntegrationUpdate,
    service: _IntegrationService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> IntegrationResponse:
    """Update an existing external POS integration."""
    integration = await service.update_integration(integration_id, body)
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    return IntegrationResponse.model_validate(integration)


# ---------------------------------------------------------------------------
# POST /pos/integrations/{integration_id}/sync — trigger sync
# ---------------------------------------------------------------------------
@router.post(
    "/pos/integrations/{integration_id}/sync",
    response_model=SyncLogResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a sync for an integration",
)
async def trigger_sync(
    integration_id: UUID,
    service: _IntegrationService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> SyncLogResponse:
    """Trigger a manual sync for an external POS integration. Returns immediately with an in-progress sync log."""
    sync_log = await service.trigger_sync(integration_id)
    if not sync_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    return SyncLogResponse.model_validate(sync_log)


# ---------------------------------------------------------------------------
# GET /pos/integrations/{integration_id}/sync-log — get sync history
# ---------------------------------------------------------------------------
@router.get(
    "/pos/integrations/{integration_id}/sync-log",
    response_model=PaginatedResponse,
    summary="Get sync history for an integration",
)
async def get_sync_log(
    integration_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: _IntegrationService = Depends(_get_service),
    current_user: dict = Depends(get_current_user),
) -> PaginatedResponse:
    """Return paginated sync history for an external POS integration."""
    logs, total = await service.get_sync_logs(integration_id, page, page_size)
    return PaginatedResponse(
        items=[SyncLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
