"""Deposit and payment integration service."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ErrorCode, ServiceError
from app.models.reservation import DepositStatus, Reservation

logger = structlog.get_logger()
settings = get_settings()


class DepositService:
    """Manages deposit collection and refunds via the payment service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._payment_service_url = getattr(settings, "PAYMENT_SERVICE_URL", "http://localhost:8007")

    async def collect_deposit(
        self,
        reservation_id: UUID,
        amount: Decimal,
        customer_id: UUID,
        payment_method_id: Optional[str] = None,
    ) -> dict:
        """Collect deposit for a reservation via the payment service."""
        result = await self.db.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        )
        reservation = result.scalar_one_or_none()
        if not reservation:
            raise ServiceError(
                ErrorCode.RESERVATION_NOT_FOUND,
                "Reservation not found",
                status_code=404,
            )

        if reservation.deposit_status == DepositStatus.COLLECTED.value:
            return {
                "status": "already_collected",
                "reservation_id": str(reservation_id),
                "transaction_id": reservation.deposit_transaction_id,
            }

        # Call payment service
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._payment_service_url}/api/v1/payments",
                    json={
                        "customer_id": str(customer_id),
                        "amount": str(amount),
                        "currency": "USD",
                        "description": f"Deposit for reservation {reservation.confirmation_code}",
                        "metadata": {
                            "reservation_id": str(reservation_id),
                            "confirmation_code": reservation.confirmation_code,
                            "type": "reservation_deposit",
                        },
                        "payment_method_id": payment_method_id,
                    },
                )
                if response.status_code in (200, 201):
                    payment_data = response.json()
                    transaction_id = payment_data.get("transaction_id", payment_data.get("id", ""))

                    reservation.deposit_status = DepositStatus.COLLECTED.value
                    reservation.deposit_paid = True
                    reservation.deposit_transaction_id = str(transaction_id)
                    reservation.deposit_paid_at = datetime.now(timezone.utc)
                    await self.db.commit()

                    logger.info(
                        "deposit_collected",
                        reservation_id=str(reservation_id),
                        amount=str(amount),
                        transaction_id=str(transaction_id),
                    )
                    return {
                        "status": "collected",
                        "reservation_id": str(reservation_id),
                        "transaction_id": str(transaction_id),
                        "amount": str(amount),
                    }
                else:
                    logger.error(
                        "deposit_collection_failed",
                        reservation_id=str(reservation_id),
                        status=response.status_code,
                        body=response.text,
                    )
                    reservation.deposit_status = DepositStatus.PENDING.value
                    await self.db.commit()
                    raise ServiceError(
                        ErrorCode.DEPOSIT_COLLECTION_FAILED,
                        "Failed to collect deposit from payment service.",
                        status_code=502,
                        details={"payment_status": response.status_code},
                    )
        except httpx.RequestError as e:
            logger.error("deposit_payment_service_unreachable", error=str(e))
            raise ServiceError(
                ErrorCode.DEPOSIT_COLLECTION_FAILED,
                "Payment service is unavailable. Deposit not collected.",
                status_code=503,
            )

    async def refund_deposit(
        self, reservation_id: UUID, reason: str = "cancellation"
    ) -> dict:
        """Refund a collected deposit."""
        result = await self.db.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        )
        reservation = result.scalar_one_or_none()
        if not reservation:
            raise ServiceError(
                ErrorCode.RESERVATION_NOT_FOUND,
                "Reservation not found",
                status_code=404,
            )

        if reservation.deposit_status != DepositStatus.COLLECTED.value:
            return {
                "status": "no_deposit_to_refund",
                "reservation_id": str(reservation_id),
            }

        if not reservation.deposit_transaction_id:
            return {
                "status": "no_transaction_id",
                "reservation_id": str(reservation_id),
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._payment_service_url}/api/v1/payments/{reservation.deposit_transaction_id}/refund",
                    json={
                        "amount": str(reservation.deposit_amount),
                        "reason": reason,
                        "metadata": {
                            "reservation_id": str(reservation_id),
                            "confirmation_code": reservation.confirmation_code,
                            "type": "deposit_refund",
                        },
                    },
                )
                if response.status_code in (200, 201):
                    reservation.deposit_status = DepositStatus.REFUNDED.value
                    reservation.deposit_refunded_at = datetime.now(timezone.utc)
                    await self.db.commit()
                    logger.info(
                        "deposit_refunded",
                        reservation_id=str(reservation_id),
                        amount=str(reservation.deposit_amount),
                    )
                    return {
                        "status": "refunded",
                        "reservation_id": str(reservation_id),
                        "amount": str(reservation.deposit_amount),
                    }
                else:
                    logger.error(
                        "deposit_refund_failed",
                        reservation_id=str(reservation_id),
                        status=response.status_code,
                    )
                    raise ServiceError(
                        ErrorCode.REFUND_FAILED,
                        "Failed to process deposit refund.",
                        status_code=502,
                    )
        except httpx.RequestError as e:
            logger.error("refund_payment_service_unreachable", error=str(e))
            raise ServiceError(
                ErrorCode.REFUND_FAILED,
                "Payment service is unavailable. Refund not processed.",
                status_code=503,
            )

    async def forfeit_deposit(self, reservation_id: UUID) -> dict:
        """Forfeit deposit (e.g., for no-shows)."""
        result = await self.db.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        )
        reservation = result.scalar_one_or_none()
        if not reservation:
            raise ServiceError(
                ErrorCode.RESERVATION_NOT_FOUND,
                "Reservation not found",
                status_code=404,
            )

        reservation.deposit_status = DepositStatus.FORFEITED.value
        await self.db.commit()
        logger.info(
            "deposit_forfeited",
            reservation_id=str(reservation_id),
            amount=str(reservation.deposit_amount),
        )
        return {
            "status": "forfeited",
            "reservation_id": str(reservation_id),
            "amount": str(reservation.deposit_amount),
        }
