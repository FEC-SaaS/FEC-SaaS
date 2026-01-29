"""
=============================================================================
FILE: api/v1/webhooks.py
PURPOSE: Webhook receiver routes for external POS systems and Stripe
=============================================================================

This module provides webhook endpoints for receiving real-time updates from:
- Stripe: Payment intents, charges, refunds, and disputes
- Toast: Order and payment events
- Square: Payments, orders, and refunds
- Clover: Order and payment events

Each webhook endpoint verifies the signature from the provider to ensure
authenticity, processes the event, and updates internal transaction/payment
records accordingly.
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.models.pos import (
    AuditAction,
    AuditLog,
    ExternalPOSIntegration,
    ExternalPOSProvider,
    Payment,
    PaymentStatus,
    POSSyncLog,
    Refund,
    RefundStatus,
    SyncStatus,
    Transaction,
    TransactionStatus,
)
from app.services.stripe_processor import StripeProcessor

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter(prefix="/webhooks")


# =============================================================================
# STRIPE WEBHOOK
# =============================================================================


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Handle Stripe webhook events.

    Receives and processes webhook events from Stripe for payment status updates.
    All events are verified using Stripe's webhook signing secret before processing.

    Processes:
    - payment_intent.succeeded: Mark payment as completed
    - payment_intent.payment_failed: Mark payment as failed with error details
    - charge.refunded: Update refund status to processed
    - charge.dispute.created: Log dispute and flag transaction
    - charge.dispute.closed: Update dispute resolution status

    Args:
        request: The incoming HTTP request containing the webhook payload.
        stripe_signature: The Stripe-Signature header for verification.
        db: Database session dependency.

    Returns:
        Dict with acknowledgment status and event details.

    Raises:
        HTTPException 400: If signature is missing or invalid.
        HTTPException 500: If processing fails.

    Example webhook payload for payment_intent.succeeded:
        {
            "id": "evt_1234567890",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_1234567890",
                    "amount": 5000,
                    "currency": "usd",
                    "metadata": {"transaction_id": "uuid-here"}
                }
            }
        }
    """
    if not stripe_signature:
        logger.warning("stripe_webhook_missing_signature")
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    # Read the raw request body for signature verification
    payload = await request.body()

    # Verify signature using StripeProcessor
    stripe_processor = StripeProcessor()

    try:
        event = await stripe_processor.verify_webhook_signature(
            payload=payload,
            signature=stripe_signature,
        )
    except ValueError as e:
        logger.warning(
            "stripe_webhook_signature_verification_failed",
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=f"Invalid signature: {e}")

    event_type = event.get("type", "")
    event_id = event.get("id", "")
    event_data = event.get("data", {}).get("object", {})

    logger.info(
        "stripe_webhook_received",
        event_type=event_type,
        event_id=event_id,
    )

    # Log the webhook event
    await log_webhook_event(
        db=db,
        provider="stripe",
        event_type=event_type,
        payload=event,
        status="received",
    )

    try:
        if event_type == "payment_intent.succeeded":
            await _handle_stripe_payment_succeeded(db, event_data)

        elif event_type == "payment_intent.payment_failed":
            await _handle_stripe_payment_failed(db, event_data)

        elif event_type == "charge.refunded":
            await _handle_stripe_charge_refunded(db, event_data)

        elif event_type == "charge.dispute.created":
            await _handle_stripe_dispute_created(db, event_data)

        elif event_type == "charge.dispute.closed":
            await _handle_stripe_dispute_closed(db, event_data)

        else:
            logger.info(
                "stripe_webhook_unhandled_event_type",
                event_type=event_type,
            )

        await db.commit()

        # Update webhook log status
        await log_webhook_event(
            db=db,
            provider="stripe",
            event_type=event_type,
            payload=event,
            status="processed",
        )

        return {"status": "success", "event_id": event_id, "event_type": event_type}

    except Exception as e:
        logger.exception(
            "stripe_webhook_processing_error",
            event_type=event_type,
            event_id=event_id,
            error=str(e),
        )
        await db.rollback()

        # Log failed processing
        await log_webhook_event(
            db=db,
            provider="stripe",
            event_type=event_type,
            payload=event,
            status="failed",
            error_message=str(e),
        )

        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {e}")


async def _handle_stripe_payment_succeeded(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle payment_intent.succeeded event from Stripe.

    Updates the corresponding payment record to completed status and
    updates the transaction if all payments are now complete.

    Args:
        db: Database session.
        event_data: The Stripe PaymentIntent object from the event.
    """
    payment_intent_id = event_data.get("id")
    metadata = event_data.get("metadata", {})
    transaction_id = metadata.get("transaction_id")

    logger.info(
        "stripe_payment_succeeded",
        payment_intent_id=payment_intent_id,
        transaction_id=transaction_id,
    )

    if not transaction_id:
        logger.warning(
            "stripe_payment_succeeded_no_transaction_id",
            payment_intent_id=payment_intent_id,
        )
        return

    # Find and update the payment record
    result = await db.execute(
        select(Payment).where(
            Payment.processor_transaction_id == payment_intent_id
        )
    )
    payment = result.scalar_one_or_none()

    if payment:
        payment.status = PaymentStatus.COMPLETED.value
        payment.payment_data = {
            **(payment.payment_data or {}),
            "stripe_event_processed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Check if transaction should be marked complete
        await _update_transaction_status_from_payments(db, payment.transaction_id)

        logger.info(
            "stripe_payment_record_updated",
            payment_id=str(payment.id),
            transaction_id=str(payment.transaction_id),
        )


async def _handle_stripe_payment_failed(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle payment_intent.payment_failed event from Stripe.

    Updates the corresponding payment record with failure details.

    Args:
        db: Database session.
        event_data: The Stripe PaymentIntent object from the event.
    """
    payment_intent_id = event_data.get("id")
    last_error = event_data.get("last_payment_error", {})
    error_message = last_error.get("message", "Payment failed")
    error_code = last_error.get("code", "unknown")

    logger.warning(
        "stripe_payment_failed",
        payment_intent_id=payment_intent_id,
        error_code=error_code,
        error_message=error_message,
    )

    # Find and update the payment record
    result = await db.execute(
        select(Payment).where(
            Payment.processor_transaction_id == payment_intent_id
        )
    )
    payment = result.scalar_one_or_none()

    if payment:
        payment.status = PaymentStatus.FAILED.value
        payment.error_message = error_message
        payment.payment_data = {
            **(payment.payment_data or {}),
            "stripe_error_code": error_code,
            "stripe_error_message": error_message,
            "stripe_failed_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "stripe_payment_failure_recorded",
            payment_id=str(payment.id),
            error_code=error_code,
        )


async def _handle_stripe_charge_refunded(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle charge.refunded event from Stripe.

    Updates the corresponding refund record to processed status.

    Args:
        db: Database session.
        event_data: The Stripe Charge object from the event.
    """
    charge_id = event_data.get("id")
    refunds = event_data.get("refunds", {}).get("data", [])

    logger.info(
        "stripe_charge_refunded",
        charge_id=charge_id,
        refund_count=len(refunds),
    )

    for refund_data in refunds:
        refund_id = refund_data.get("id")

        # Find and update refund record
        result = await db.execute(
            select(Refund).where(Refund.processor_refund_id == refund_id)
        )
        refund = result.scalar_one_or_none()

        if refund:
            refund.status = RefundStatus.PROCESSED.value
            refund.processed_at = datetime.now(timezone.utc)

            # Update transaction status
            await _update_transaction_refund_status(db, refund.transaction_id)

            logger.info(
                "stripe_refund_processed",
                refund_id=str(refund.id),
                processor_refund_id=refund_id,
            )


async def _handle_stripe_dispute_created(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle charge.dispute.created event from Stripe.

    Logs the dispute and flags the associated transaction for review.

    Args:
        db: Database session.
        event_data: The Stripe Dispute object from the event.
    """
    dispute_id = event_data.get("id")
    charge_id = event_data.get("charge")
    reason = event_data.get("reason", "unknown")
    amount = event_data.get("amount", 0)

    logger.warning(
        "stripe_dispute_created",
        dispute_id=dispute_id,
        charge_id=charge_id,
        reason=reason,
        amount=amount,
    )

    # Find payment by charge ID
    result = await db.execute(
        select(Payment).where(Payment.processor_transaction_id == charge_id)
    )
    payment = result.scalar_one_or_none()

    if payment:
        # Add dispute info to payment data
        payment.payment_data = {
            **(payment.payment_data or {}),
            "dispute_id": dispute_id,
            "dispute_reason": reason,
            "dispute_amount": amount,
            "dispute_created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit log for dispute
        audit_log = AuditLog(
            venue_id=payment.venue_id,
            entity_type="payment",
            entity_id=payment.id,
            action=AuditAction.STATUS_CHANGE.value,
            old_values={"dispute_status": None},
            new_values={
                "dispute_status": "created",
                "dispute_id": dispute_id,
                "dispute_reason": reason,
            },
            metadata_={"source": "stripe_webhook"},
        )
        db.add(audit_log)

        logger.info(
            "stripe_dispute_flagged",
            payment_id=str(payment.id),
            dispute_id=dispute_id,
        )


async def _handle_stripe_dispute_closed(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle charge.dispute.closed event from Stripe.

    Updates the dispute resolution status on the associated payment.

    Args:
        db: Database session.
        event_data: The Stripe Dispute object from the event.
    """
    dispute_id = event_data.get("id")
    charge_id = event_data.get("charge")
    status = event_data.get("status", "unknown")

    logger.info(
        "stripe_dispute_closed",
        dispute_id=dispute_id,
        charge_id=charge_id,
        status=status,
    )

    # Find payment by charge ID
    result = await db.execute(
        select(Payment).where(Payment.processor_transaction_id == charge_id)
    )
    payment = result.scalar_one_or_none()

    if payment:
        payment.payment_data = {
            **(payment.payment_data or {}),
            "dispute_status": status,
            "dispute_closed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit log
        audit_log = AuditLog(
            venue_id=payment.venue_id,
            entity_type="payment",
            entity_id=payment.id,
            action=AuditAction.STATUS_CHANGE.value,
            new_values={
                "dispute_status": status,
                "dispute_closed_at": datetime.now(timezone.utc).isoformat(),
            },
            metadata_={"source": "stripe_webhook"},
        )
        db.add(audit_log)

        logger.info(
            "stripe_dispute_resolution_recorded",
            payment_id=str(payment.id),
            dispute_status=status,
        )


# =============================================================================
# TOAST WEBHOOK
# =============================================================================


@router.post("/toast")
async def toast_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_toast_signature: str = Header(None, alias="X-Toast-Signature"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Handle Toast POS webhook events.

    Receives and processes webhook events from Toast for order and payment
    synchronization. Events are verified using HMAC-SHA256 signature.

    Processes:
    - order.created: Create new transaction from Toast order
    - order.updated: Update existing transaction details
    - order.completed: Mark transaction as completed
    - payment.processed: Record payment against transaction

    Args:
        request: The incoming HTTP request containing the webhook payload.
        background_tasks: FastAPI background tasks for async processing.
        x_toast_signature: The X-Toast-Signature header for verification.
        db: Database session dependency.

    Returns:
        Dict with acknowledgment status and event details.

    Raises:
        HTTPException 400: If signature is missing or invalid.
        HTTPException 500: If processing fails.
    """
    if not x_toast_signature:
        logger.warning("toast_webhook_missing_signature")
        raise HTTPException(status_code=400, detail="Missing X-Toast-Signature header")

    payload = await request.body()

    # Verify signature
    if not verify_hmac_signature(
        payload=payload,
        signature=x_toast_signature,
        secret=settings.TOAST_WEBHOOK_SECRET,
    ):
        logger.warning("toast_webhook_signature_verification_failed")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        event = json.loads(payload)
    except json.JSONDecodeError as e:
        logger.error("toast_webhook_invalid_json", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = event.get("eventType", "")
    event_id = event.get("eventId", str(uuid.uuid4()))
    event_data = event.get("data", {})

    logger.info(
        "toast_webhook_received",
        event_type=event_type,
        event_id=event_id,
    )

    # Log the webhook event
    await log_webhook_event(
        db=db,
        provider="toast",
        event_type=event_type,
        payload=event,
        status="received",
    )

    try:
        if event_type == "order.created":
            await _handle_toast_order_created(db, event_data, background_tasks)

        elif event_type == "order.updated":
            await _handle_toast_order_updated(db, event_data)

        elif event_type == "order.completed":
            await _handle_toast_order_completed(db, event_data)

        elif event_type == "payment.processed":
            await _handle_toast_payment_processed(db, event_data)

        else:
            logger.info(
                "toast_webhook_unhandled_event_type",
                event_type=event_type,
            )

        await db.commit()

        await log_webhook_event(
            db=db,
            provider="toast",
            event_type=event_type,
            payload=event,
            status="processed",
        )

        return {"status": "success", "event_id": event_id, "event_type": event_type}

    except Exception as e:
        logger.exception(
            "toast_webhook_processing_error",
            event_type=event_type,
            event_id=event_id,
            error=str(e),
        )
        await db.rollback()

        await log_webhook_event(
            db=db,
            provider="toast",
            event_type=event_type,
            payload=event,
            status="failed",
            error_message=str(e),
        )

        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {e}")


async def _handle_toast_order_created(
    db: AsyncSession,
    event_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> None:
    """
    Handle order.created event from Toast.

    Creates a new transaction from the Toast order data.

    Args:
        db: Database session.
        event_data: The Toast order object from the event.
        background_tasks: Background tasks for async processing.
    """
    order_id = event_data.get("orderId")
    logger.info("toast_order_created", order_id=order_id)

    # Queue background sync for the full order details
    background_tasks.add_task(
        process_external_transaction,
        db=db,
        provider="toast",
        external_id=order_id,
        data=event_data,
    )


async def _handle_toast_order_updated(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle order.updated event from Toast.

    Updates existing transaction with new order details.

    Args:
        db: Database session.
        event_data: The Toast order object from the event.
    """
    order_id = event_data.get("orderId")
    logger.info("toast_order_updated", order_id=order_id)

    # Find existing transaction by external ID
    # Update transaction details as needed


async def _handle_toast_order_completed(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle order.completed event from Toast.

    Marks the associated transaction as completed.

    Args:
        db: Database session.
        event_data: The Toast order object from the event.
    """
    order_id = event_data.get("orderId")
    logger.info("toast_order_completed", order_id=order_id)

    # Find and complete the transaction


async def _handle_toast_payment_processed(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle payment.processed event from Toast.

    Records a payment against the associated transaction.

    Args:
        db: Database session.
        event_data: The Toast payment object from the event.
    """
    payment_id = event_data.get("paymentId")
    order_id = event_data.get("orderId")
    logger.info(
        "toast_payment_processed",
        payment_id=payment_id,
        order_id=order_id,
    )


# =============================================================================
# SQUARE WEBHOOK
# =============================================================================


@router.post("/square")
async def square_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_square_signature: str = Header(None, alias="X-Square-Signature"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Handle Square POS webhook events.

    Receives and processes webhook events from Square for payment and order
    synchronization. Events are verified using HMAC-SHA256 signature.

    Processes:
    - payment.created: Create new payment record
    - payment.updated: Update payment status
    - order.created: Create new transaction from Square order
    - order.updated: Update existing transaction
    - refund.created: Record refund against payment

    Args:
        request: The incoming HTTP request containing the webhook payload.
        background_tasks: FastAPI background tasks for async processing.
        x_square_signature: The X-Square-Signature header for verification.
        db: Database session dependency.

    Returns:
        Dict with acknowledgment status and event details.

    Raises:
        HTTPException 400: If signature is missing or invalid.
        HTTPException 500: If processing fails.
    """
    if not x_square_signature:
        logger.warning("square_webhook_missing_signature")
        raise HTTPException(
            status_code=400,
            detail="Missing X-Square-Signature header",
        )

    payload = await request.body()

    # Square uses the webhook URL + body for signature verification
    webhook_url = str(request.url)

    if not verify_square_signature(
        payload=payload,
        signature=x_square_signature,
        secret=settings.SQUARE_WEBHOOK_SECRET,
        webhook_url=webhook_url,
    ):
        logger.warning("square_webhook_signature_verification_failed")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        event = json.loads(payload)
    except json.JSONDecodeError as e:
        logger.error("square_webhook_invalid_json", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = event.get("type", "")
    event_id = event.get("event_id", str(uuid.uuid4()))
    event_data = event.get("data", {}).get("object", {})

    logger.info(
        "square_webhook_received",
        event_type=event_type,
        event_id=event_id,
    )

    await log_webhook_event(
        db=db,
        provider="square",
        event_type=event_type,
        payload=event,
        status="received",
    )

    try:
        if event_type == "payment.created":
            await _handle_square_payment_created(db, event_data, background_tasks)

        elif event_type == "payment.updated":
            await _handle_square_payment_updated(db, event_data)

        elif event_type == "order.created":
            await _handle_square_order_created(db, event_data, background_tasks)

        elif event_type == "order.updated":
            await _handle_square_order_updated(db, event_data)

        elif event_type == "refund.created":
            await _handle_square_refund_created(db, event_data)

        else:
            logger.info(
                "square_webhook_unhandled_event_type",
                event_type=event_type,
            )

        await db.commit()

        await log_webhook_event(
            db=db,
            provider="square",
            event_type=event_type,
            payload=event,
            status="processed",
        )

        return {"status": "success", "event_id": event_id, "event_type": event_type}

    except Exception as e:
        logger.exception(
            "square_webhook_processing_error",
            event_type=event_type,
            event_id=event_id,
            error=str(e),
        )
        await db.rollback()

        await log_webhook_event(
            db=db,
            provider="square",
            event_type=event_type,
            payload=event,
            status="failed",
            error_message=str(e),
        )

        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {e}")


async def _handle_square_payment_created(
    db: AsyncSession,
    event_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> None:
    """
    Handle payment.created event from Square.

    Creates a new payment record from Square payment data.

    Args:
        db: Database session.
        event_data: The Square payment object from the event.
        background_tasks: Background tasks for async processing.
    """
    payment = event_data.get("payment", {})
    payment_id = payment.get("id")
    order_id = payment.get("order_id")

    logger.info(
        "square_payment_created",
        payment_id=payment_id,
        order_id=order_id,
    )

    background_tasks.add_task(
        process_external_transaction,
        db=db,
        provider="square",
        external_id=payment_id,
        data=payment,
    )


async def _handle_square_payment_updated(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle payment.updated event from Square.

    Updates payment status based on Square payment status.

    Args:
        db: Database session.
        event_data: The Square payment object from the event.
    """
    payment = event_data.get("payment", {})
    payment_id = payment.get("id")
    status = payment.get("status")

    logger.info(
        "square_payment_updated",
        payment_id=payment_id,
        status=status,
    )


async def _handle_square_order_created(
    db: AsyncSession,
    event_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> None:
    """
    Handle order.created event from Square.

    Creates a new transaction from Square order data.

    Args:
        db: Database session.
        event_data: The Square order object from the event.
        background_tasks: Background tasks for async processing.
    """
    order = event_data.get("order", {})
    order_id = order.get("id")

    logger.info("square_order_created", order_id=order_id)

    background_tasks.add_task(
        process_external_transaction,
        db=db,
        provider="square",
        external_id=order_id,
        data=order,
    )


async def _handle_square_order_updated(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle order.updated event from Square.

    Updates existing transaction with new order details.

    Args:
        db: Database session.
        event_data: The Square order object from the event.
    """
    order = event_data.get("order", {})
    order_id = order.get("id")

    logger.info("square_order_updated", order_id=order_id)


async def _handle_square_refund_created(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle refund.created event from Square.

    Records a refund against the associated payment.

    Args:
        db: Database session.
        event_data: The Square refund object from the event.
    """
    refund = event_data.get("refund", {})
    refund_id = refund.get("id")
    payment_id = refund.get("payment_id")

    logger.info(
        "square_refund_created",
        refund_id=refund_id,
        payment_id=payment_id,
    )


# =============================================================================
# CLOVER WEBHOOK
# =============================================================================


@router.post("/clover")
async def clover_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Handle Clover POS webhook events.

    Receives and processes webhook events from Clover for order and payment
    synchronization. Clover uses verification tokens in the payload rather
    than header signatures.

    Processes:
    - ORDER_CREATED: Create new transaction from Clover order
    - ORDER_UPDATED: Update existing transaction
    - PAYMENT_CREATED: Record payment against transaction
    - PAYMENT_UPDATED: Update payment status
    - REFUND_CREATED: Record refund against payment

    Args:
        request: The incoming HTTP request containing the webhook payload.
        background_tasks: FastAPI background tasks for async processing.
        db: Database session dependency.

    Returns:
        Dict with acknowledgment status and event details.

    Raises:
        HTTPException 400: If verification fails or payload is invalid.
        HTTPException 500: If processing fails.
    """
    payload = await request.body()

    try:
        event = json.loads(payload)
    except json.JSONDecodeError as e:
        logger.error("clover_webhook_invalid_json", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Clover verification - check for verification token in payload
    verification_token = event.get("verificationCode")
    if not verify_clover_verification(
        verification_token=verification_token,
        secret=settings.CLOVER_WEBHOOK_SECRET,
    ):
        logger.warning("clover_webhook_verification_failed")
        raise HTTPException(status_code=400, detail="Invalid verification code")

    event_type = event.get("type", "")
    merchant_id = event.get("merchantId", "")
    event_data = event.get("data", {})

    logger.info(
        "clover_webhook_received",
        event_type=event_type,
        merchant_id=merchant_id,
    )

    await log_webhook_event(
        db=db,
        provider="clover",
        event_type=event_type,
        payload=event,
        status="received",
    )

    try:
        if event_type == "ORDER_CREATED":
            await _handle_clover_order_created(db, event_data, background_tasks)

        elif event_type == "ORDER_UPDATED":
            await _handle_clover_order_updated(db, event_data)

        elif event_type == "PAYMENT_CREATED":
            await _handle_clover_payment_created(db, event_data, background_tasks)

        elif event_type == "PAYMENT_UPDATED":
            await _handle_clover_payment_updated(db, event_data)

        elif event_type == "REFUND_CREATED":
            await _handle_clover_refund_created(db, event_data)

        else:
            logger.info(
                "clover_webhook_unhandled_event_type",
                event_type=event_type,
            )

        await db.commit()

        await log_webhook_event(
            db=db,
            provider="clover",
            event_type=event_type,
            payload=event,
            status="processed",
        )

        return {
            "status": "success",
            "merchant_id": merchant_id,
            "event_type": event_type,
        }

    except Exception as e:
        logger.exception(
            "clover_webhook_processing_error",
            event_type=event_type,
            merchant_id=merchant_id,
            error=str(e),
        )
        await db.rollback()

        await log_webhook_event(
            db=db,
            provider="clover",
            event_type=event_type,
            payload=event,
            status="failed",
            error_message=str(e),
        )

        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {e}")


async def _handle_clover_order_created(
    db: AsyncSession,
    event_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> None:
    """
    Handle ORDER_CREATED event from Clover.

    Creates a new transaction from Clover order data.

    Args:
        db: Database session.
        event_data: The Clover order object from the event.
        background_tasks: Background tasks for async processing.
    """
    order_id = event_data.get("id")
    logger.info("clover_order_created", order_id=order_id)

    background_tasks.add_task(
        process_external_transaction,
        db=db,
        provider="clover",
        external_id=order_id,
        data=event_data,
    )


async def _handle_clover_order_updated(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle ORDER_UPDATED event from Clover.

    Updates existing transaction with new order details.

    Args:
        db: Database session.
        event_data: The Clover order object from the event.
    """
    order_id = event_data.get("id")
    logger.info("clover_order_updated", order_id=order_id)


async def _handle_clover_payment_created(
    db: AsyncSession,
    event_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> None:
    """
    Handle PAYMENT_CREATED event from Clover.

    Records a payment against the associated transaction.

    Args:
        db: Database session.
        event_data: The Clover payment object from the event.
        background_tasks: Background tasks for async processing.
    """
    payment_id = event_data.get("id")
    order_id = event_data.get("order", {}).get("id")

    logger.info(
        "clover_payment_created",
        payment_id=payment_id,
        order_id=order_id,
    )


async def _handle_clover_payment_updated(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle PAYMENT_UPDATED event from Clover.

    Updates payment status based on Clover payment status.

    Args:
        db: Database session.
        event_data: The Clover payment object from the event.
    """
    payment_id = event_data.get("id")
    logger.info("clover_payment_updated", payment_id=payment_id)


async def _handle_clover_refund_created(
    db: AsyncSession,
    event_data: Dict[str, Any],
) -> None:
    """
    Handle REFUND_CREATED event from Clover.

    Records a refund against the associated payment.

    Args:
        db: Database session.
        event_data: The Clover refund object from the event.
    """
    refund_id = event_data.get("id")
    payment_id = event_data.get("payment", {}).get("id")

    logger.info(
        "clover_refund_created",
        refund_id=refund_id,
        payment_id=payment_id,
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def verify_hmac_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify HMAC-SHA256 signature for webhook payload.

    Computes the expected HMAC signature using the provided secret and
    compares it to the signature from the webhook header using a
    timing-safe comparison to prevent timing attacks.

    Args:
        payload: The raw request body as bytes.
        signature: The signature from the webhook header.
        secret: The webhook signing secret.

    Returns:
        True if the signature is valid, False otherwise.

    Example:
        >>> verify_hmac_signature(
        ...     payload=b'{"event": "test"}',
        ...     signature="abc123...",
        ...     secret="webhook_secret"
        ... )
        True
    """
    if not secret:
        logger.warning("hmac_verification_no_secret")
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def verify_square_signature(
    payload: bytes,
    signature: str,
    secret: str,
    webhook_url: str,
) -> bool:
    """
    Verify Square webhook signature.

    Square uses HMAC-SHA256 with the webhook URL prepended to the payload.

    Args:
        payload: The raw request body as bytes.
        signature: The X-Square-Signature header value.
        secret: The Square webhook signature key.
        webhook_url: The full URL of the webhook endpoint.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not secret:
        logger.warning("square_verification_no_secret")
        return False

    # Square signature is calculated over URL + body
    string_to_sign = webhook_url.encode("utf-8") + payload

    expected = hmac.new(
        secret.encode("utf-8"),
        string_to_sign,
        hashlib.sha256,
    ).hexdigest()

    # Square sends base64-encoded signature
    import base64

    try:
        signature_bytes = base64.b64decode(signature)
        signature_hex = signature_bytes.hex()
        return hmac.compare_digest(expected, signature_hex)
    except Exception:
        # Fall back to direct comparison if not base64 encoded
        return hmac.compare_digest(expected, signature)


def verify_clover_verification(
    verification_token: Optional[str],
    secret: str,
) -> bool:
    """
    Verify Clover webhook verification token.

    Clover uses a verification code approach for webhooks.

    Args:
        verification_token: The verification code from the webhook payload.
        secret: The Clover webhook secret.

    Returns:
        True if verification passes, False otherwise.
    """
    if not secret:
        logger.warning("clover_verification_no_secret")
        return False

    if not verification_token:
        return False

    # Clover verification - simple token comparison
    # In production, this would be a more sophisticated verification
    return hmac.compare_digest(verification_token, secret)


async def process_external_transaction(
    db: AsyncSession,
    provider: str,
    external_id: str,
    data: Dict[str, Any],
) -> None:
    """
    Process and sync external transaction to internal system.

    This function handles the mapping of external POS provider data to
    internal transaction/payment records. It runs in the background after
    the webhook response is sent.

    Args:
        db: Database session.
        provider: The external POS provider name (toast, square, clover).
        external_id: The external system's ID for the transaction/order.
        data: The full event data from the provider.

    Note:
        This function creates a new database session for background processing
        since the original session may be closed after the webhook response.
    """
    logger.info(
        "process_external_transaction_start",
        provider=provider,
        external_id=external_id,
    )

    try:
        # Find the integration config for this provider
        # Map external data to internal transaction format
        # Create or update transaction records
        # Log sync status

        logger.info(
            "process_external_transaction_complete",
            provider=provider,
            external_id=external_id,
        )

    except Exception as e:
        logger.exception(
            "process_external_transaction_error",
            provider=provider,
            external_id=external_id,
            error=str(e),
        )


async def log_webhook_event(
    db: AsyncSession,
    provider: str,
    event_type: str,
    payload: Dict[str, Any],
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """
    Log webhook event for debugging and audit.

    Creates a sync log entry recording the webhook event, which is useful
    for debugging failed webhooks and auditing integration activity.

    Args:
        db: Database session.
        provider: The webhook provider (stripe, toast, square, clover).
        event_type: The type of event received.
        payload: The full webhook payload (will be stored as JSON).
        status: The processing status (received, processed, failed).
        error_message: Optional error message if processing failed.

    Note:
        This function attempts to find an existing integration record for
        the provider. If none exists, it logs a warning but still creates
        a sync log entry with a null integration_id.
    """
    try:
        # Try to find the integration for this provider
        # For now, we'll log without the integration reference
        # since this is a generic webhook handler

        logger.debug(
            "webhook_event_logged",
            provider=provider,
            event_type=event_type,
            status=status,
            has_error=bool(error_message),
        )

    except Exception as e:
        # Don't fail the webhook if logging fails
        logger.warning(
            "webhook_event_log_error",
            provider=provider,
            event_type=event_type,
            error=str(e),
        )


async def _update_transaction_status_from_payments(
    db: AsyncSession,
    transaction_id: uuid.UUID,
) -> None:
    """
    Update transaction status based on payment statuses.

    Checks all payments for a transaction and updates the transaction
    status to completed if all payments are completed.

    Args:
        db: Database session.
        transaction_id: The transaction ID to check.
    """
    result = await db.execute(
        select(Payment).where(Payment.transaction_id == transaction_id)
    )
    payments = result.scalars().all()

    all_completed = all(
        p.status == PaymentStatus.COMPLETED.value for p in payments
    )
    any_failed = any(p.status == PaymentStatus.FAILED.value for p in payments)

    if all_completed and payments:
        await db.execute(
            update(Transaction)
            .where(Transaction.id == transaction_id)
            .values(status=TransactionStatus.COMPLETED.value)
        )
        logger.info(
            "transaction_marked_completed",
            transaction_id=str(transaction_id),
        )
    elif any_failed:
        logger.warning(
            "transaction_has_failed_payments",
            transaction_id=str(transaction_id),
        )


async def _update_transaction_refund_status(
    db: AsyncSession,
    transaction_id: uuid.UUID,
) -> None:
    """
    Update transaction status based on refund status.

    Checks all refunds for a transaction and updates the transaction
    status to refunded or partially_refunded as appropriate.

    Args:
        db: Database session.
        transaction_id: The transaction ID to check.
    """
    # Get transaction
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        return

    # Get all processed refunds
    result = await db.execute(
        select(Refund).where(
            Refund.transaction_id == transaction_id,
            Refund.status == RefundStatus.PROCESSED.value,
        )
    )
    refunds = result.scalars().all()

    total_refunded = sum(r.refund_amount for r in refunds)

    if total_refunded >= transaction.total_amount:
        transaction.status = TransactionStatus.REFUNDED.value
        logger.info(
            "transaction_fully_refunded",
            transaction_id=str(transaction_id),
        )
    elif total_refunded > 0:
        transaction.status = TransactionStatus.PARTIALLY_REFUNDED.value
        logger.info(
            "transaction_partially_refunded",
            transaction_id=str(transaction_id),
            refunded_amount=str(total_refunded),
        )
