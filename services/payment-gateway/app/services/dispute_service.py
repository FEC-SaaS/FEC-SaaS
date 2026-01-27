"""
=============================================================================
FILE: services/dispute_service.py
PURPOSE: Payment dispute management service
=============================================================================
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import (
    PaymentDispute,
    PaymentTransaction,
    TransactionStatus,
    DisputeType,
    DisputeStatus,
)
from app.schemas.payment import (
    DisputeResponse,
    DisputeEvidenceSubmit,
    DisputeListResponse,
    PaginationParams,
)

logger = structlog.get_logger()


class DisputeService:
    """Service for managing payment disputes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_dispute_from_webhook(
        self,
        payment_id: UUID,
        dispute_type: DisputeType,
        dispute_amount: Decimal,
        processor_dispute_id: str,
        dispute_reason: Optional[str] = None,
        dispute_reason_code: Optional[str] = None,
        evidence_due_date: Optional[date] = None,
    ) -> DisputeResponse:
        """Create a dispute from processor webhook."""
        # Get the transaction
        result = await self.db.execute(
            select(PaymentTransaction).where(PaymentTransaction.id == payment_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise ValueError(f"Transaction {payment_id} not found")

        # Create dispute record
        dispute = PaymentDispute(
            id=uuid4(),
            payment_id=payment_id,
            dispute_type=dispute_type,
            dispute_reason=dispute_reason,
            dispute_reason_code=dispute_reason_code,
            dispute_amount=dispute_amount,
            processor_dispute_id=processor_dispute_id,
            dispute_date=date.today(),
            response_due_date=evidence_due_date,
            evidence_due_date=evidence_due_date,
            status=DisputeStatus.OPEN,
        )

        # Update transaction status
        transaction.status = TransactionStatus.DISPUTED

        self.db.add(dispute)
        await self.db.flush()

        logger.warning(
            "dispute_created",
            dispute_id=str(dispute.id),
            payment_id=str(payment_id),
            dispute_type=dispute_type.value,
            amount=float(dispute_amount),
        )

        return DisputeResponse.model_validate(dispute)

    async def get_dispute(self, dispute_id: UUID) -> DisputeResponse:
        """Get a dispute by ID."""
        result = await self.db.execute(
            select(PaymentDispute).where(PaymentDispute.id == dispute_id)
        )
        dispute = result.scalar_one_or_none()
        if not dispute:
            raise ValueError(f"Dispute {dispute_id} not found")
        return DisputeResponse.model_validate(dispute)

    async def list_disputes(
        self,
        venue_id: UUID,
        status: Optional[DisputeStatus] = None,
        params: PaginationParams = PaginationParams(),
    ) -> DisputeListResponse:
        """List disputes for a venue."""
        query = (
            select(PaymentDispute)
            .join(PaymentTransaction)
            .where(PaymentTransaction.venue_id == venue_id)
        )

        if status:
            query = query.where(PaymentDispute.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        query = query.order_by(PaymentDispute.created_at.desc())
        offset = (params.page - 1) * params.page_size
        query = query.offset(offset).limit(params.page_size)

        result = await self.db.execute(query)
        disputes = result.scalars().all()

        return DisputeListResponse(
            disputes=[DisputeResponse.model_validate(d) for d in disputes],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )

    async def submit_evidence(
        self,
        dispute_id: UUID,
        data: DisputeEvidenceSubmit,
        user_id: Optional[UUID] = None,
    ) -> DisputeResponse:
        """Submit evidence for a dispute."""
        result = await self.db.execute(
            select(PaymentDispute).where(PaymentDispute.id == dispute_id)
        )
        dispute = result.scalar_one_or_none()
        if not dispute:
            raise ValueError(f"Dispute {dispute_id} not found")

        if dispute.status not in [DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW]:
            raise ValueError(f"Cannot submit evidence for dispute in status: {dispute.status.value}")

        # Add evidence to existing or create new
        evidence = dispute.evidence_submitted or {}
        evidence[data.evidence_type] = {
            "data": data.evidence_data,
            "notes": data.notes,
            "submitted_at": datetime.utcnow().isoformat(),
            "submitted_by": str(user_id) if user_id else None,
        }

        dispute.evidence_submitted = evidence
        dispute.status = DisputeStatus.UNDER_REVIEW
        dispute.updated_at = datetime.utcnow()

        await self.db.flush()

        logger.info(
            "dispute_evidence_submitted",
            dispute_id=str(dispute_id),
            evidence_type=data.evidence_type,
        )

        return DisputeResponse.model_validate(dispute)

    async def accept_dispute(
        self,
        dispute_id: UUID,
        notes: Optional[str] = None,
    ) -> DisputeResponse:
        """Accept a dispute (concede to customer)."""
        result = await self.db.execute(
            select(PaymentDispute).where(PaymentDispute.id == dispute_id)
        )
        dispute = result.scalar_one_or_none()
        if not dispute:
            raise ValueError(f"Dispute {dispute_id} not found")

        dispute.status = DisputeStatus.LOST
        dispute.resolution_date = date.today()
        dispute.resolution_notes = notes
        dispute.updated_at = datetime.utcnow()

        await self.db.flush()

        logger.info(
            "dispute_accepted",
            dispute_id=str(dispute_id),
        )

        return DisputeResponse.model_validate(dispute)

    async def update_dispute_status(
        self,
        processor_dispute_id: str,
        status: DisputeStatus,
        resolution_notes: Optional[str] = None,
    ) -> Optional[DisputeResponse]:
        """Update dispute status from processor webhook."""
        result = await self.db.execute(
            select(PaymentDispute).where(
                PaymentDispute.processor_dispute_id == processor_dispute_id
            )
        )
        dispute = result.scalar_one_or_none()
        if not dispute:
            logger.warning(
                "dispute_not_found_for_update",
                processor_dispute_id=processor_dispute_id,
            )
            return None

        dispute.status = status
        if status in [DisputeStatus.WON, DisputeStatus.LOST]:
            dispute.resolution_date = date.today()
        if resolution_notes:
            dispute.resolution_notes = resolution_notes
        dispute.updated_at = datetime.utcnow()

        # Update transaction status if won
        if status == DisputeStatus.WON:
            tx_result = await self.db.execute(
                select(PaymentTransaction).where(PaymentTransaction.id == dispute.payment_id)
            )
            transaction = tx_result.scalar_one_or_none()
            if transaction:
                transaction.status = TransactionStatus.COMPLETED

        await self.db.flush()

        logger.info(
            "dispute_status_updated",
            dispute_id=str(dispute.id),
            new_status=status.value,
        )

        return DisputeResponse.model_validate(dispute)

    async def get_dispute_metrics(
        self,
        venue_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get dispute metrics for a venue."""
        query = (
            select(PaymentDispute)
            .join(PaymentTransaction)
            .where(PaymentTransaction.venue_id == venue_id)
        )

        if start_date:
            query = query.where(PaymentDispute.dispute_date >= start_date)
        if end_date:
            query = query.where(PaymentDispute.dispute_date <= end_date)

        result = await self.db.execute(query)
        disputes = result.scalars().all()

        total_disputes = len(disputes)
        total_amount = sum(d.dispute_amount for d in disputes)

        won = sum(1 for d in disputes if d.status == DisputeStatus.WON)
        lost = sum(1 for d in disputes if d.status == DisputeStatus.LOST)
        pending = sum(1 for d in disputes if d.status in [DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW])

        # Get total transactions for dispute rate
        tx_count_query = select(func.count()).select_from(PaymentTransaction).where(
            PaymentTransaction.venue_id == venue_id,
            PaymentTransaction.status == TransactionStatus.COMPLETED,
        )
        if start_date:
            tx_count_query = tx_count_query.where(PaymentTransaction.created_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            tx_count_query = tx_count_query.where(PaymentTransaction.created_at <= datetime.combine(end_date, datetime.max.time()))

        tx_result = await self.db.execute(tx_count_query)
        total_transactions = tx_result.scalar() or 1

        return {
            "total_disputes": total_disputes,
            "total_amount": float(total_amount),
            "won": won,
            "lost": lost,
            "pending": pending,
            "win_rate": (won / (won + lost)) * 100 if (won + lost) > 0 else 0,
            "dispute_rate": (total_disputes / total_transactions) * 100,
        }
