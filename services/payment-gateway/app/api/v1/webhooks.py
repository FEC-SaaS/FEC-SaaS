"""
=============================================================================
FILE: api/v1/webhooks.py
PURPOSE: Payment processor webhook handlers
=============================================================================
"""

from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.models.payment import (
    PaymentTransaction,
    VenuePaymentConfig,
    PaymentProcessor,
    ProcessorType,
    TransactionStatus,
    DisputeType,
)
from app.services import DisputeService, EventPublisher, EventType
from app.services.processors import StripeProcessor, SquareProcessor

logger = structlog.get_logger()
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/stripe/{venue_id}",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook handler",
)
async def handle_stripe_webhook(
    venue_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle incoming Stripe webhooks."""
    body = await request.body()
    signature = request.headers.get("stripe-signature", "")

    # Get venue config to verify webhook
    config = await _get_venue_config(db, venue_id, ProcessorType.STRIPE)
    if not config:
        logger.warning("stripe_webhook_no_config", venue_id=str(venue_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not configured")

    # Verify webhook signature
    api_credentials = config.api_credentials or {}
    processor = StripeProcessor(
        api_key=api_credentials.get("api_key", ""),
        webhook_secret=api_credentials.get("webhook_secret", ""),
    )

    if not await processor.verify_webhook(body, signature):
        logger.warning("stripe_webhook_invalid_signature", venue_id=str(venue_id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    # Parse event
    import json
    event = json.loads(body)
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    logger.info("stripe_webhook_received", event_type=event_type, venue_id=str(venue_id))

    # Handle different event types
    event_pub = EventPublisher()

    if event_type == "payment_intent.succeeded":
        await _handle_payment_succeeded(db, data, venue_id, event_pub)
    elif event_type == "payment_intent.payment_failed":
        await _handle_payment_failed(db, data, venue_id, event_pub)
    elif event_type == "charge.dispute.created":
        await _handle_dispute_created(db, data, venue_id, event_pub)
    elif event_type == "charge.dispute.updated":
        await _handle_dispute_updated(db, data, event_pub)
    elif event_type == "charge.dispute.closed":
        await _handle_dispute_closed(db, data, event_pub)
    elif event_type.startswith("invoice."):
        await _handle_invoice_event(db, event_type, data, venue_id, event_pub)
    elif event_type.startswith("customer.subscription."):
        await _handle_subscription_event(db, event_type, data, venue_id, event_pub)

    return {"status": "ok"}


@router.post(
    "/square/{venue_id}",
    status_code=status.HTTP_200_OK,
    summary="Square webhook handler",
)
async def handle_square_webhook(
    venue_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle incoming Square webhooks."""
    body = await request.body()
    signature = request.headers.get("x-square-signature", "")

    # Get venue config
    config = await _get_venue_config(db, venue_id, ProcessorType.SQUARE)
    if not config:
        logger.warning("square_webhook_no_config", venue_id=str(venue_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not configured")

    # Verify webhook signature
    api_credentials = config.api_credentials or {}
    processor = SquareProcessor(
        api_key=api_credentials.get("api_key", ""),
        location_id=api_credentials.get("location_id", ""),
        webhook_signature_key=api_credentials.get("webhook_signature_key", ""),
        webhook_url=api_credentials.get("webhook_url", ""),
    )

    if not await processor.verify_webhook(body, signature):
        logger.warning("square_webhook_invalid_signature", venue_id=str(venue_id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    # Parse event
    import json
    event = json.loads(body)
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    logger.info("square_webhook_received", event_type=event_type, venue_id=str(venue_id))

    event_pub = EventPublisher()

    if event_type == "payment.completed":
        await _handle_payment_succeeded(db, data, venue_id, event_pub, processor_type="square")
    elif event_type == "payment.failed":
        await _handle_payment_failed(db, data, venue_id, event_pub, processor_type="square")
    elif event_type == "dispute.created":
        await _handle_square_dispute_created(db, data, venue_id, event_pub)

    return {"status": "ok"}


async def _get_venue_config(
    db: AsyncSession,
    venue_id: UUID,
    processor_type: ProcessorType,
) -> VenuePaymentConfig:
    """Get venue payment config for a processor type."""
    result = await db.execute(
        select(VenuePaymentConfig)
        .join(PaymentProcessor)
        .where(
            VenuePaymentConfig.venue_id == venue_id,
            PaymentProcessor.processor_type == processor_type,
            VenuePaymentConfig.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def _handle_payment_succeeded(
    db: AsyncSession,
    data: dict,
    venue_id: UUID,
    event_pub: EventPublisher,
    processor_type: str = "stripe",
):
    """Handle payment succeeded webhook."""
    if processor_type == "stripe":
        processor_tx_id = data.get("id")
    else:
        processor_tx_id = data.get("payment", {}).get("id")

    result = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.processor_transaction_id == processor_tx_id
        )
    )
    transaction = result.scalar_one_or_none()

    if transaction and transaction.status == TransactionStatus.PENDING:
        transaction.status = TransactionStatus.COMPLETED

        await event_pub.publish_payment_completed(
            transaction_id=transaction.id,
            venue_id=venue_id,
            customer_id=transaction.customer_id,
            amount=transaction.amount,
            currency=transaction.currency,
        )


async def _handle_payment_failed(
    db: AsyncSession,
    data: dict,
    venue_id: UUID,
    event_pub: EventPublisher,
    processor_type: str = "stripe",
):
    """Handle payment failed webhook."""
    if processor_type == "stripe":
        processor_tx_id = data.get("id")
        error_code = data.get("last_payment_error", {}).get("code")
        error_message = data.get("last_payment_error", {}).get("message")
    else:
        processor_tx_id = data.get("payment", {}).get("id")
        error_code = "failed"
        error_message = "Payment failed"

    result = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.processor_transaction_id == processor_tx_id
        )
    )
    transaction = result.scalar_one_or_none()

    if transaction and transaction.status == TransactionStatus.PENDING:
        transaction.status = TransactionStatus.FAILED
        transaction.error_code = error_code
        transaction.error_message = error_message

        await event_pub.publish_payment_failed(
            transaction_id=transaction.id,
            venue_id=venue_id,
            customer_id=transaction.customer_id,
            amount=transaction.amount,
            error_code=error_code,
            error_message=error_message,
        )


async def _handle_dispute_created(
    db: AsyncSession,
    data: dict,
    venue_id: UUID,
    event_pub: EventPublisher,
):
    """Handle Stripe dispute created webhook."""
    payment_intent_id = data.get("payment_intent")

    result = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.processor_transaction_id == payment_intent_id
        )
    )
    transaction = result.scalar_one_or_none()

    if transaction:
        dispute_service = DisputeService(db)

        # Map Stripe reason to dispute type
        reason = data.get("reason", "")
        dispute_type = _map_stripe_dispute_reason(reason)

        await dispute_service.create_dispute_from_webhook(
            payment_id=transaction.id,
            dispute_type=dispute_type,
            dispute_amount=Decimal(data.get("amount", 0)) / 100,
            processor_dispute_id=data.get("id"),
            dispute_reason=reason,
            dispute_reason_code=data.get("reason"),
        )

        await event_pub.publish_dispute_created(
            dispute_id=UUID(data.get("id")),
            transaction_id=transaction.id,
            venue_id=venue_id,
            dispute_amount=Decimal(data.get("amount", 0)) / 100,
            dispute_type=dispute_type.value,
        )


async def _handle_dispute_updated(db: AsyncSession, data: dict, event_pub: EventPublisher):
    """Handle Stripe dispute updated webhook."""
    dispute_service = DisputeService(db)
    # Status mapping would be implemented here
    pass


async def _handle_dispute_closed(db: AsyncSession, data: dict, event_pub: EventPublisher):
    """Handle Stripe dispute closed webhook."""
    dispute_service = DisputeService(db)

    status_mapping = {
        "won": "won",
        "lost": "lost",
        "warning_closed": "closed",
    }

    from app.models.payment import DisputeStatus

    status_str = data.get("status", "")
    if status_str in status_mapping:
        status = DisputeStatus(status_mapping[status_str])
        await dispute_service.update_dispute_status(
            processor_dispute_id=data.get("id"),
            status=status,
        )


async def _handle_invoice_event(
    db: AsyncSession,
    event_type: str,
    data: dict,
    venue_id: UUID,
    event_pub: EventPublisher,
):
    """Handle Stripe invoice events."""
    # Handle subscription invoice events
    if event_type == "invoice.payment_failed":
        subscription_id = data.get("subscription")
        if subscription_id:
            await event_pub.publish(
                EventType.SUBSCRIPTION_PAYMENT_FAILED,
                payload={
                    "processor_subscription_id": subscription_id,
                    "invoice_id": data.get("id"),
                },
                venue_id=venue_id,
            )


async def _handle_subscription_event(
    db: AsyncSession,
    event_type: str,
    data: dict,
    venue_id: UUID,
    event_pub: EventPublisher,
):
    """Handle Stripe subscription events."""
    # These are handled by the subscription service
    pass


async def _handle_square_dispute_created(
    db: AsyncSession,
    data: dict,
    venue_id: UUID,
    event_pub: EventPublisher,
):
    """Handle Square dispute created webhook."""
    dispute = data.get("dispute", {})
    payment_id = dispute.get("disputed_payment", {}).get("payment_id")

    result = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.processor_transaction_id == payment_id
        )
    )
    transaction = result.scalar_one_or_none()

    if transaction:
        dispute_service = DisputeService(db)

        await dispute_service.create_dispute_from_webhook(
            payment_id=transaction.id,
            dispute_type=DisputeType.CHARGEBACK,
            dispute_amount=Decimal(dispute.get("amount_money", {}).get("amount", 0)) / 100,
            processor_dispute_id=dispute.get("id"),
            dispute_reason=dispute.get("reason"),
        )


def _map_stripe_dispute_reason(reason: str) -> DisputeType:
    """Map Stripe dispute reason to DisputeType."""
    mapping = {
        "fraudulent": DisputeType.FRAUD,
        "duplicate": DisputeType.DUPLICATE,
        "subscription_canceled": DisputeType.SUBSCRIPTION_CANCELED,
        "product_unacceptable": DisputeType.PRODUCT_UNACCEPTABLE,
        "product_not_received": DisputeType.PRODUCT_NOT_RECEIVED,
        "unrecognized": DisputeType.FRAUD,
        "credit_not_processed": DisputeType.CREDIT_NOT_PROCESSED,
        "general": DisputeType.GENERAL,
    }
    return mapping.get(reason, DisputeType.CHARGEBACK)
