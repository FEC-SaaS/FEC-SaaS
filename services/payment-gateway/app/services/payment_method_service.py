"""
=============================================================================
FILE: services/payment_method_service.py
PURPOSE: Payment method management service
=============================================================================
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import (
    CustomerPaymentMethod,
    PaymentMethodType,
    CardBrand,
)
from app.schemas.payment import (
    PaymentMethodCreate,
    PaymentMethodUpdate,
    PaymentMethodResponse,
    PaymentMethodListResponse,
)
from app.services.processors import TokenizeResult
from app.core.encryption import encrypt_sensitive_data, decrypt_sensitive_data

logger = structlog.get_logger()


class PaymentMethodService:
    """Service for managing customer payment methods."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payment_method(
        self,
        data: PaymentMethodCreate,
        processor_customer_id: Optional[str] = None,
    ) -> PaymentMethodResponse:
        """Create a new payment method."""
        # Encrypt the token
        encrypted_token = encrypt_sensitive_data(data.token)

        # If set_as_default, unset other defaults
        if data.set_as_default:
            await self._unset_defaults(data.customer_id, data.venue_id)

        payment_method = CustomerPaymentMethod(
            id=uuid4(),
            customer_id=data.customer_id,
            venue_id=data.venue_id,
            payment_method_type=data.payment_method_type,
            processor_token=encrypted_token,
            processor_customer_id=processor_customer_id,
            card_brand=data.card_brand,
            card_last_four=data.card_last_four,
            card_exp_month=data.card_exp_month,
            card_exp_year=data.card_exp_year,
            billing_address=data.billing_address.model_dump() if data.billing_address else None,
            nickname=data.nickname,
            is_default=data.set_as_default,
            is_active=True,
        )

        self.db.add(payment_method)
        await self.db.flush()

        logger.info(
            "payment_method_created",
            payment_method_id=str(payment_method.id),
            customer_id=str(data.customer_id),
        )

        return PaymentMethodResponse.model_validate(payment_method)

    async def create_from_tokenize_result(
        self,
        customer_id: UUID,
        venue_id: UUID,
        result: TokenizeResult,
        billing_address: Optional[Dict[str, Any]] = None,
        nickname: Optional[str] = None,
        set_as_default: bool = False,
    ) -> PaymentMethodResponse:
        """Create payment method from processor tokenization result."""
        encrypted_token = encrypt_sensitive_data(result.token)

        if set_as_default:
            await self._unset_defaults(customer_id, venue_id)

        # Map card brand string to enum
        card_brand = None
        if result.card_brand:
            brand_mapping = {
                "visa": CardBrand.VISA,
                "mastercard": CardBrand.MASTERCARD,
                "amex": CardBrand.AMEX,
                "american_express": CardBrand.AMEX,
                "discover": CardBrand.DISCOVER,
                "diners": CardBrand.DINERS,
                "jcb": CardBrand.JCB,
                "unionpay": CardBrand.UNIONPAY,
            }
            card_brand = brand_mapping.get(result.card_brand.lower())

        payment_method = CustomerPaymentMethod(
            id=uuid4(),
            customer_id=customer_id,
            venue_id=venue_id,
            payment_method_type=PaymentMethodType.CARD,
            processor_token=encrypted_token,
            processor_customer_id=result.customer_id,
            card_brand=card_brand,
            card_last_four=result.card_last_four,
            card_exp_month=result.card_exp_month,
            card_exp_year=result.card_exp_year,
            card_fingerprint=result.card_fingerprint,
            billing_address=billing_address,
            nickname=nickname,
            is_default=set_as_default,
            is_active=True,
        )

        self.db.add(payment_method)
        await self.db.flush()

        return PaymentMethodResponse.model_validate(payment_method)

    async def update_payment_method(
        self,
        payment_method_id: UUID,
        data: PaymentMethodUpdate,
    ) -> PaymentMethodResponse:
        """Update a payment method."""
        payment_method = await self._get_payment_method(payment_method_id)

        if data.billing_address:
            payment_method.billing_address = data.billing_address.model_dump()

        if data.nickname is not None:
            payment_method.nickname = data.nickname

        if data.is_default is not None:
            if data.is_default:
                await self._unset_defaults(
                    payment_method.customer_id,
                    payment_method.venue_id,
                )
            payment_method.is_default = data.is_default

        payment_method.updated_at = datetime.utcnow()
        await self.db.flush()

        return PaymentMethodResponse.model_validate(payment_method)

    async def delete_payment_method(self, payment_method_id: UUID) -> None:
        """Soft delete a payment method."""
        payment_method = await self._get_payment_method(payment_method_id)
        payment_method.is_active = False
        payment_method.updated_at = datetime.utcnow()
        await self.db.flush()

        logger.info(
            "payment_method_deleted",
            payment_method_id=str(payment_method_id),
        )

    async def get_payment_method(self, payment_method_id: UUID) -> PaymentMethodResponse:
        """Get a payment method by ID."""
        payment_method = await self._get_payment_method(payment_method_id)
        return PaymentMethodResponse.model_validate(payment_method)

    async def list_payment_methods(
        self,
        customer_id: UUID,
        venue_id: Optional[UUID] = None,
        include_expired: bool = False,
    ) -> PaymentMethodListResponse:
        """List payment methods for a customer."""
        query = select(CustomerPaymentMethod).where(
            and_(
                CustomerPaymentMethod.customer_id == customer_id,
                CustomerPaymentMethod.is_active == True,
            )
        )

        if venue_id:
            query = query.where(CustomerPaymentMethod.venue_id == venue_id)

        if not include_expired:
            # Filter out expired cards
            current_year = datetime.utcnow().year
            current_month = datetime.utcnow().month
            query = query.where(
                (CustomerPaymentMethod.payment_method_type != PaymentMethodType.CARD) |
                (
                    (CustomerPaymentMethod.card_exp_year > current_year) |
                    (
                        (CustomerPaymentMethod.card_exp_year == current_year) &
                        (CustomerPaymentMethod.card_exp_month >= current_month)
                    )
                )
            )

        query = query.order_by(
            CustomerPaymentMethod.is_default.desc(),
            CustomerPaymentMethod.created_at.desc(),
        )

        result = await self.db.execute(query)
        payment_methods = result.scalars().all()

        return PaymentMethodListResponse(
            payment_methods=[PaymentMethodResponse.model_validate(pm) for pm in payment_methods],
            total=len(payment_methods),
        )

    async def get_default_payment_method(
        self,
        customer_id: UUID,
        venue_id: UUID,
    ) -> Optional[PaymentMethodResponse]:
        """Get the default payment method for a customer at a venue."""
        result = await self.db.execute(
            select(CustomerPaymentMethod).where(
                and_(
                    CustomerPaymentMethod.customer_id == customer_id,
                    CustomerPaymentMethod.venue_id == venue_id,
                    CustomerPaymentMethod.is_default == True,
                    CustomerPaymentMethod.is_active == True,
                )
            )
        )
        payment_method = result.scalar_one_or_none()

        if payment_method:
            return PaymentMethodResponse.model_validate(payment_method)

        # If no default, return the most recent active method
        result = await self.db.execute(
            select(CustomerPaymentMethod)
            .where(
                and_(
                    CustomerPaymentMethod.customer_id == customer_id,
                    CustomerPaymentMethod.venue_id == venue_id,
                    CustomerPaymentMethod.is_active == True,
                )
            )
            .order_by(CustomerPaymentMethod.created_at.desc())
            .limit(1)
        )
        payment_method = result.scalar_one_or_none()

        if payment_method:
            return PaymentMethodResponse.model_validate(payment_method)

        return None

    async def set_default(
        self,
        payment_method_id: UUID,
    ) -> PaymentMethodResponse:
        """Set a payment method as default."""
        payment_method = await self._get_payment_method(payment_method_id)

        await self._unset_defaults(
            payment_method.customer_id,
            payment_method.venue_id,
        )

        payment_method.is_default = True
        payment_method.updated_at = datetime.utcnow()
        await self.db.flush()

        return PaymentMethodResponse.model_validate(payment_method)

    async def _get_payment_method(self, payment_method_id: UUID) -> CustomerPaymentMethod:
        """Get payment method by ID."""
        result = await self.db.execute(
            select(CustomerPaymentMethod).where(
                CustomerPaymentMethod.id == payment_method_id
            )
        )
        payment_method = result.scalar_one_or_none()
        if not payment_method:
            raise ValueError(f"Payment method {payment_method_id} not found")
        return payment_method

    async def _unset_defaults(self, customer_id: UUID, venue_id: UUID) -> None:
        """Unset default flag for all payment methods of a customer at a venue."""
        result = await self.db.execute(
            select(CustomerPaymentMethod).where(
                and_(
                    CustomerPaymentMethod.customer_id == customer_id,
                    CustomerPaymentMethod.venue_id == venue_id,
                    CustomerPaymentMethod.is_default == True,
                )
            )
        )
        for pm in result.scalars().all():
            pm.is_default = False
