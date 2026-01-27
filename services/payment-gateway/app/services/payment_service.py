"""
=============================================================================
FILE: services/payment_service.py
PURPOSE: Core payment processing service
=============================================================================
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.payment import (
    PaymentProcessor,
    VenuePaymentConfig,
    CustomerPaymentMethod,
    PaymentTransaction,
    TransactionType,
    TransactionStatus,
    ProcessorType,
)
from app.schemas.payment import (
    ChargeRequest,
    AuthorizeRequest,
    CaptureRequest,
    PaymentResponse,
    PaymentDetailResponse,
    PaymentListResponse,
    PaginationParams,
)
from app.services.processors import (
    BasePaymentProcessor,
    StripeProcessor,
    SquareProcessor,
)
from app.services.fraud_service import FraudService
from app.core.encryption import decrypt_sensitive_data

logger = structlog.get_logger()


class PaymentService:
    """Service for processing payments."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.fraud_service = FraudService(db)
        self._processors: Dict[str, BasePaymentProcessor] = {}

    async def get_processor(self, venue_id: UUID) -> Tuple[BasePaymentProcessor, VenuePaymentConfig]:
        """Get the payment processor for a venue."""
        query = (
            select(VenuePaymentConfig)
            .join(PaymentProcessor)
            .where(
                VenuePaymentConfig.venue_id == venue_id,
                VenuePaymentConfig.is_active == True,
                VenuePaymentConfig.is_primary == True,
            )
            .options(selectinload(VenuePaymentConfig.processor))
        )
        result = await self.db.execute(query)
        config = result.scalar_one_or_none()

        if not config:
            raise ValueError(f"No active payment processor configured for venue {venue_id}")

        processor_key = f"{config.processor_id}_{venue_id}"

        if processor_key not in self._processors:
            api_credentials = config.api_credentials or {}
            decrypted_key = decrypt_sensitive_data(api_credentials.get("api_key", ""))

            if config.processor.processor_type == ProcessorType.STRIPE:
                self._processors[processor_key] = StripeProcessor(
                    api_key=decrypted_key,
                    webhook_secret=api_credentials.get("webhook_secret"),
                )
            elif config.processor.processor_type == ProcessorType.SQUARE:
                self._processors[processor_key] = SquareProcessor(
                    api_key=decrypted_key,
                    location_id=api_credentials.get("location_id", ""),
                    environment=api_credentials.get("environment", "sandbox"),
                )
            else:
                raise ValueError(f"Unsupported processor type: {config.processor.processor_type}")

        return self._processors[processor_key], config

    async def charge(
        self,
        request: ChargeRequest,
        user_id: Optional[UUID] = None,
    ) -> PaymentResponse:
        """Process a payment charge."""
        processor, config = await self.get_processor(request.venue_id)

        # Get payment method token
        payment_token = await self._get_payment_token(request)

        # Create transaction record
        transaction = PaymentTransaction(
            id=uuid4(),
            venue_id=request.venue_id,
            customer_id=request.customer_id,
            payment_method_id=request.payment_method_id,
            config_id=config.id,
            amount=request.amount,
            currency=request.currency,
            transaction_type=TransactionType.CHARGE,
            status=TransactionStatus.PENDING,
            description=request.description,
            order_id=request.order_id,
            invoice_id=request.invoice_id,
            extra_metadata=request.metadata,
            idempotency_key=request.idempotency_key,
            ip_address=request.ip_address,
            device_fingerprint=request.device_fingerprint,
            initiated_by=user_id,
        )

        # Run fraud check
        fraud_result = await self.fraud_service.check_transaction(transaction, request)
        transaction.fraud_score = fraud_result.fraud_score
        transaction.fraud_check_passed = fraud_result.passed

        if not fraud_result.passed:
            transaction.status = TransactionStatus.FRAUD_BLOCKED
            transaction.error_code = "fraud_blocked"
            transaction.error_message = f"Transaction blocked: {fraud_result.recommended_action.value}"
            self.db.add(transaction)
            await self.db.flush()
            return self._to_response(transaction)

        # Process payment
        result = await processor.charge(
            amount=request.amount,
            currency=request.currency,
            payment_method_token=payment_token,
            customer_id=str(request.customer_id) if request.customer_id else None,
            description=request.description,
            metadata=request.metadata,
            idempotency_key=request.idempotency_key,
        )

        # Update transaction
        if result.success:
            transaction.status = TransactionStatus.COMPLETED
            transaction.processor_transaction_id = result.transaction_id
            transaction.authorization_code = result.authorization_code
            transaction.receipt_url = result.receipt_url
            transaction.processor_fee = result.processor_fee
            if transaction.processor_fee:
                transaction.net_amount = transaction.amount - transaction.processor_fee
            transaction.processed_at = datetime.utcnow()
        else:
            transaction.status = TransactionStatus.FAILED
            if result.decline_code:
                transaction.status = TransactionStatus.DECLINED
            transaction.error_code = result.error_code
            transaction.error_message = result.error_message
            transaction.decline_code = result.decline_code

        transaction.raw_response = result.raw_response
        self.db.add(transaction)
        await self.db.flush()

        # Save payment method if requested
        if result.success and request.save_payment_method and request.token:
            await self._save_payment_method(request, processor, config)

        logger.info(
            "payment_processed",
            transaction_id=str(transaction.id),
            success=result.success,
            amount=float(request.amount),
        )

        return self._to_response(transaction)

    async def authorize(
        self,
        request: AuthorizeRequest,
        user_id: Optional[UUID] = None,
    ) -> PaymentResponse:
        """Authorize a payment for later capture."""
        processor, config = await self.get_processor(request.venue_id)
        payment_token = await self._get_payment_token(request)

        transaction = PaymentTransaction(
            id=uuid4(),
            venue_id=request.venue_id,
            customer_id=request.customer_id,
            payment_method_id=request.payment_method_id,
            config_id=config.id,
            amount=request.amount,
            currency=request.currency,
            transaction_type=TransactionType.AUTHORIZATION,
            status=TransactionStatus.PENDING,
            description=request.description,
            order_id=request.order_id,
            extra_metadata=request.metadata,
            idempotency_key=request.idempotency_key,
            initiated_by=user_id,
        )

        result = await processor.authorize(
            amount=request.amount,
            currency=request.currency,
            payment_method_token=payment_token,
            customer_id=str(request.customer_id) if request.customer_id else None,
            description=request.description,
            metadata=request.metadata,
            idempotency_key=request.idempotency_key,
        )

        if result.success:
            transaction.status = TransactionStatus.AUTHORIZED
            transaction.processor_transaction_id = result.transaction_id
            transaction.authorization_code = result.authorization_code
            transaction.authorized_at = datetime.utcnow()
        else:
            transaction.status = TransactionStatus.FAILED
            transaction.error_code = result.error_code
            transaction.error_message = result.error_message

        transaction.raw_response = result.raw_response
        self.db.add(transaction)
        await self.db.flush()

        return self._to_response(transaction)

    async def capture(
        self,
        transaction_id: UUID,
        request: CaptureRequest,
        user_id: Optional[UUID] = None,
    ) -> PaymentResponse:
        """Capture an authorized payment."""
        transaction = await self._get_transaction(transaction_id)

        if transaction.status != TransactionStatus.AUTHORIZED:
            raise ValueError(f"Transaction {transaction_id} is not in authorized state")

        processor, _ = await self.get_processor(transaction.venue_id)

        result = await processor.capture(
            transaction_id=transaction.processor_transaction_id,
            amount=request.amount,
        )

        if result.success:
            transaction.status = TransactionStatus.CAPTURED
            transaction.captured_amount = request.amount or transaction.amount
            transaction.captured_at = datetime.utcnow()
            transaction.transaction_type = TransactionType.CAPTURE
        else:
            transaction.error_code = result.error_code
            transaction.error_message = result.error_message

        transaction.raw_response = result.raw_response
        await self.db.flush()

        return self._to_response(transaction)

    async def void(
        self,
        transaction_id: UUID,
        reason: Optional[str] = None,
        user_id: Optional[UUID] = None,
    ) -> PaymentResponse:
        """Void a payment."""
        transaction = await self._get_transaction(transaction_id)

        if transaction.status not in [TransactionStatus.AUTHORIZED, TransactionStatus.PENDING]:
            raise ValueError(f"Transaction {transaction_id} cannot be voided")

        processor, _ = await self.get_processor(transaction.venue_id)

        result = await processor.void(transaction_id=transaction.processor_transaction_id)

        if result.success:
            transaction.status = TransactionStatus.VOIDED
            transaction.voided_at = datetime.utcnow()
            transaction.transaction_type = TransactionType.VOID
        else:
            transaction.error_code = result.error_code
            transaction.error_message = result.error_message

        transaction.raw_response = result.raw_response
        await self.db.flush()

        return self._to_response(transaction)

    async def get_transaction(self, transaction_id: UUID) -> PaymentDetailResponse:
        """Get transaction details including refunds and disputes."""
        query = (
            select(PaymentTransaction)
            .where(PaymentTransaction.id == transaction_id)
            .options(
                selectinload(PaymentTransaction.refunds),
                selectinload(PaymentTransaction.fraud_alerts),
                selectinload(PaymentTransaction.disputes),
            )
        )
        result = await self.db.execute(query)
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")

        return self._to_detail_response(transaction)

    async def list_transactions(
        self,
        venue_id: UUID,
        params: PaginationParams,
        customer_id: Optional[UUID] = None,
        status: Optional[TransactionStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> PaymentListResponse:
        """List transactions for a venue with filters."""
        query = select(PaymentTransaction).where(PaymentTransaction.venue_id == venue_id)

        if customer_id:
            query = query.where(PaymentTransaction.customer_id == customer_id)
        if status:
            query = query.where(PaymentTransaction.status == status)
        if start_date:
            query = query.where(PaymentTransaction.created_at >= start_date)
        if end_date:
            query = query.where(PaymentTransaction.created_at <= end_date)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply sorting and pagination
        if params.sort_order == "desc":
            query = query.order_by(getattr(PaymentTransaction, params.sort_by).desc())
        else:
            query = query.order_by(getattr(PaymentTransaction, params.sort_by).asc())

        offset = (params.page - 1) * params.page_size
        query = query.offset(offset).limit(params.page_size)

        result = await self.db.execute(query)
        transactions = result.scalars().all()

        return PaymentListResponse(
            payments=[self._to_response(t) for t in transactions],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )

    async def _get_transaction(self, transaction_id: UUID) -> PaymentTransaction:
        """Get a transaction by ID."""
        result = await self.db.execute(
            select(PaymentTransaction).where(PaymentTransaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")
        return transaction

    async def _get_payment_token(self, request: ChargeRequest) -> str:
        """Get payment method token from request."""
        if request.token:
            return request.token

        if request.payment_method_id:
            result = await self.db.execute(
                select(CustomerPaymentMethod).where(
                    CustomerPaymentMethod.id == request.payment_method_id,
                    CustomerPaymentMethod.is_active == True,
                )
            )
            payment_method = result.scalar_one_or_none()
            if payment_method:
                return decrypt_sensitive_data(payment_method.processor_token)

        raise ValueError("No payment method provided")

    async def _save_payment_method(
        self,
        request: ChargeRequest,
        processor: BasePaymentProcessor,
        config: VenuePaymentConfig,
    ) -> None:
        """Save payment method for future use."""
        if not request.customer_id:
            return

        result = await processor.tokenize_card(
            card_token=request.token,
            customer_id=str(request.customer_id),
        )

        if result.success:
            from app.services.payment_method_service import PaymentMethodService
            method_service = PaymentMethodService(self.db)
            await method_service.create_from_tokenize_result(
                customer_id=request.customer_id,
                venue_id=request.venue_id,
                result=result,
                billing_address=request.metadata.get("billing_address") if request.metadata else None,
            )

    def _to_response(self, transaction: PaymentTransaction) -> PaymentResponse:
        """Convert transaction to response schema."""
        return PaymentResponse(
            id=transaction.id,
            venue_id=transaction.venue_id,
            customer_id=transaction.customer_id,
            payment_method_id=transaction.payment_method_id,
            amount=transaction.amount,
            currency=transaction.currency,
            transaction_type=transaction.transaction_type,
            status=transaction.status,
            processor_transaction_id=transaction.processor_transaction_id,
            authorization_code=transaction.authorization_code,
            processor_fee=transaction.processor_fee,
            net_amount=transaction.net_amount,
            error_code=transaction.error_code,
            error_message=transaction.error_message,
            fraud_score=transaction.fraud_score,
            fraud_check_passed=transaction.fraud_check_passed,
            description=transaction.description,
            receipt_url=transaction.receipt_url,
            metadata=transaction.extra_metadata,
            processed_at=transaction.processed_at,
            created_at=transaction.created_at,
        )

    def _to_detail_response(self, transaction: PaymentTransaction) -> PaymentDetailResponse:
        """Convert transaction to detailed response schema."""
        from app.schemas.payment import RefundResponse, FraudAlertResponse, DisputeResponse

        return PaymentDetailResponse(
            id=transaction.id,
            venue_id=transaction.venue_id,
            customer_id=transaction.customer_id,
            payment_method_id=transaction.payment_method_id,
            amount=transaction.amount,
            currency=transaction.currency,
            transaction_type=transaction.transaction_type,
            status=transaction.status,
            processor_transaction_id=transaction.processor_transaction_id,
            authorization_code=transaction.authorization_code,
            processor_fee=transaction.processor_fee,
            net_amount=transaction.net_amount,
            error_code=transaction.error_code,
            error_message=transaction.error_message,
            fraud_score=transaction.fraud_score,
            fraud_check_passed=transaction.fraud_check_passed,
            description=transaction.description,
            receipt_url=transaction.receipt_url,
            metadata=transaction.extra_metadata,
            processed_at=transaction.processed_at,
            created_at=transaction.created_at,
            refunds=[RefundResponse.model_validate(r) for r in transaction.refunds],
            fraud_alerts=[FraudAlertResponse.model_validate(a) for a in transaction.fraud_alerts],
            disputes=[DisputeResponse.model_validate(d) for d in transaction.disputes],
        )
