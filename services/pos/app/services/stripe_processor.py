"""Stripe payment processor integration for the POS service.

This module provides a StripeProcessor class that handles real card payments
via the Stripe SDK, including payment processing, refunds, and payment intents.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

import stripe
import structlog
from stripe.error import (
    AuthenticationError,
    CardError,
    InvalidRequestError,
    RateLimitError,
    StripeError,
)

from app.config import get_settings

logger = structlog.get_logger()


@dataclass
class ProcessorResult:
    """Result from a payment processor operation.

    Attributes:
        success: Whether the operation completed successfully.
        transaction_id: The processor's unique transaction identifier (e.g., Stripe charge ID).
        error_message: Human-readable error message if the operation failed.
        raw_response: The complete raw response from the processor for debugging/logging.
    """

    success: bool
    transaction_id: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class PaymentIntent:
    """Represents a Stripe PaymentIntent.

    Attributes:
        id: The PaymentIntent ID (e.g., pi_xxx).
        client_secret: Secret used by the client to confirm the payment.
        status: Current status of the PaymentIntent.
        amount: Amount in the smallest currency unit (e.g., cents for USD).
        currency: Three-letter ISO currency code.
        raw_response: The complete raw response from Stripe.
    """

    id: str
    client_secret: str
    status: str
    amount: int
    currency: str
    raw_response: Optional[Dict[str, Any]] = None


class StripeProcessor:
    """Handles payment processing via the Stripe SDK.

    This class provides methods for processing card payments, refunds,
    and managing Stripe PaymentIntents for the POS service.

    Attributes:
        api_key: The Stripe secret API key.
        webhook_secret: The Stripe webhook signing secret.
        api_version: The Stripe API version to use.

    Example:
        >>> processor = StripeProcessor()
        >>> result = await processor.process_payment(
        ...     amount=Decimal("49.99"),
        ...     currency="usd",
        ...     card_token="tok_visa",
        ...     metadata={"order_id": "12345"}
        ... )
        >>> if result.success:
        ...     print(f"Payment successful: {result.transaction_id}")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        api_version: Optional[str] = None,
    ) -> None:
        """Initialize the Stripe processor.

        Args:
            api_key: Stripe secret API key. Defaults to settings.STRIPE_SECRET_KEY.
            webhook_secret: Stripe webhook secret. Defaults to settings.STRIPE_WEBHOOK_SECRET.
            api_version: Stripe API version. Defaults to settings.STRIPE_API_VERSION.
        """
        settings = get_settings()
        self.api_key = api_key or settings.STRIPE_SECRET_KEY
        self.webhook_secret = webhook_secret or settings.STRIPE_WEBHOOK_SECRET
        self.api_version = api_version or settings.STRIPE_API_VERSION

        # Configure the Stripe library
        stripe.api_key = self.api_key
        stripe.api_version = self.api_version

        logger.info(
            "stripe_processor_initialized",
            api_version=self.api_version,
            has_api_key=bool(self.api_key),
            has_webhook_secret=bool(self.webhook_secret),
        )

    def _convert_amount_to_cents(self, amount: Decimal, currency: str) -> int:
        """Convert a decimal amount to the smallest currency unit.

        For most currencies, this multiplies by 100 to convert to cents.
        Zero-decimal currencies (like JPY) are not multiplied.

        Args:
            amount: The amount as a Decimal.
            currency: Three-letter ISO currency code.

        Returns:
            Amount in the smallest currency unit (integer).
        """
        # Zero-decimal currencies that don't need multiplication
        zero_decimal_currencies = {
            "bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga",
            "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf",
        }

        if currency.lower() in zero_decimal_currencies:
            return int(amount)
        return int(amount * 100)

    def _convert_cents_to_amount(self, cents: int, currency: str) -> Decimal:
        """Convert cents back to a decimal amount.

        Args:
            cents: Amount in the smallest currency unit.
            currency: Three-letter ISO currency code.

        Returns:
            Amount as a Decimal.
        """
        zero_decimal_currencies = {
            "bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga",
            "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf",
        }

        if currency.lower() in zero_decimal_currencies:
            return Decimal(str(cents))
        return Decimal(str(cents)) / 100

    async def process_payment(
        self,
        amount: Decimal,
        currency: str,
        card_token: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessorResult:
        """Process a card payment via Stripe.

        Creates a charge using the provided card token (from Stripe.js or Elements).

        Args:
            amount: The payment amount (e.g., Decimal("49.99")).
            currency: Three-letter ISO currency code (e.g., "usd").
            card_token: Stripe token representing the card (e.g., "tok_visa").
            metadata: Optional dictionary of metadata to attach to the charge.

        Returns:
            ProcessorResult with success status, transaction ID, and any error details.

        Example:
            >>> result = await processor.process_payment(
            ...     amount=Decimal("25.00"),
            ...     currency="usd",
            ...     card_token="tok_visa",
            ...     metadata={"customer_id": "cust_123", "venue_id": "venue_456"}
            ... )
        """
        logger.info(
            "stripe_process_payment_start",
            amount=str(amount),
            currency=currency,
            has_metadata=bool(metadata),
        )

        try:
            amount_cents = self._convert_amount_to_cents(amount, currency)

            # Create the charge
            # Note: stripe.Charge.create is synchronous, but we're in an async context
            # For true async, consider using stripe-async or running in executor
            charge = stripe.Charge.create(
                amount=amount_cents,
                currency=currency.lower(),
                source=card_token,
                metadata=metadata or {},
                capture=True,  # Immediately capture the charge
            )

            logger.info(
                "stripe_charge_created",
                charge_id=charge.id,
                amount_cents=amount_cents,
                status=charge.status,
            )

            return ProcessorResult(
                success=charge.status == "succeeded",
                transaction_id=charge.id,
                error_message=None if charge.status == "succeeded" else f"Charge status: {charge.status}",
                raw_response=dict(charge),
            )

        except CardError as e:
            # Card was declined or had an error
            logger.warning(
                "stripe_card_error",
                error_code=e.code,
                error_message=str(e.user_message),
                decline_code=getattr(e, "decline_code", None),
            )
            return ProcessorResult(
                success=False,
                transaction_id=None,
                error_message=e.user_message or str(e),
                raw_response={"error": {"code": e.code, "message": str(e)}},
            )

        except InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            logger.error(
                "stripe_invalid_request",
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=None,
                error_message=f"Invalid request: {e}",
                raw_response={"error": {"type": "invalid_request", "message": str(e)}},
            )

        except AuthenticationError as e:
            # Authentication with Stripe's API failed
            logger.error(
                "stripe_authentication_error",
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=None,
                error_message="Payment processor authentication failed",
                raw_response={"error": {"type": "authentication_error", "message": str(e)}},
            )

        except RateLimitError as e:
            # Too many requests to Stripe's API
            logger.warning(
                "stripe_rate_limit_error",
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=None,
                error_message="Payment processor is temporarily unavailable. Please try again.",
                raw_response={"error": {"type": "rate_limit_error", "message": str(e)}},
            )

        except StripeError as e:
            # Generic Stripe error
            logger.error(
                "stripe_generic_error",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=None,
                error_message=f"Payment processing error: {e}",
                raw_response={"error": {"type": "stripe_error", "message": str(e)}},
            )

        except Exception as e:
            # Unexpected error
            logger.exception(
                "stripe_unexpected_error",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=None,
                error_message="An unexpected error occurred during payment processing",
                raw_response={"error": {"type": "unexpected_error", "message": str(e)}},
            )

    async def refund_payment(
        self,
        processor_transaction_id: str,
        amount: Optional[Decimal] = None,
    ) -> ProcessorResult:
        """Refund a previously processed payment.

        Creates a refund for the specified charge. Supports both full and partial refunds.

        Args:
            processor_transaction_id: The Stripe charge ID (e.g., "ch_xxx").
            amount: Optional amount to refund. If None, refunds the full charge amount.

        Returns:
            ProcessorResult with success status and refund details.

        Example:
            >>> # Full refund
            >>> result = await processor.refund_payment("ch_1234567890")
            >>>
            >>> # Partial refund of $10.00
            >>> result = await processor.refund_payment(
            ...     "ch_1234567890",
            ...     amount=Decimal("10.00")
            ... )
        """
        logger.info(
            "stripe_refund_start",
            charge_id=processor_transaction_id,
            amount=str(amount) if amount else "full",
        )

        try:
            # Build refund parameters
            refund_params: Dict[str, Any] = {
                "charge": processor_transaction_id,
            }

            # If amount specified, get the charge to determine currency
            if amount is not None:
                charge = stripe.Charge.retrieve(processor_transaction_id)
                amount_cents = self._convert_amount_to_cents(amount, charge.currency)
                refund_params["amount"] = amount_cents

            refund = stripe.Refund.create(**refund_params)

            logger.info(
                "stripe_refund_created",
                refund_id=refund.id,
                charge_id=processor_transaction_id,
                status=refund.status,
                amount=refund.amount,
            )

            return ProcessorResult(
                success=refund.status in ("succeeded", "pending"),
                transaction_id=refund.id,
                error_message=None if refund.status in ("succeeded", "pending") else f"Refund status: {refund.status}",
                raw_response=dict(refund),
            )

        except InvalidRequestError as e:
            logger.error(
                "stripe_refund_invalid_request",
                charge_id=processor_transaction_id,
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=None,
                error_message=f"Invalid refund request: {e}",
                raw_response={"error": {"type": "invalid_request", "message": str(e)}},
            )

        except StripeError as e:
            logger.error(
                "stripe_refund_error",
                charge_id=processor_transaction_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=None,
                error_message=f"Refund processing error: {e}",
                raw_response={"error": {"type": "stripe_error", "message": str(e)}},
            )

        except Exception as e:
            logger.exception(
                "stripe_refund_unexpected_error",
                charge_id=processor_transaction_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=None,
                error_message="An unexpected error occurred during refund processing",
                raw_response={"error": {"type": "unexpected_error", "message": str(e)}},
            )

    async def get_payment_details(
        self,
        processor_transaction_id: str,
    ) -> Dict[str, Any]:
        """Retrieve detailed information about a processed payment.

        Fetches the charge details from Stripe, including card information,
        billing details, and transaction metadata.

        Args:
            processor_transaction_id: The Stripe charge ID (e.g., "ch_xxx").

        Returns:
            Dictionary containing payment details with the following structure:
            {
                "id": "ch_xxx",
                "amount": Decimal("49.99"),
                "currency": "usd",
                "status": "succeeded",
                "payment_method": {
                    "type": "card",
                    "brand": "visa",
                    "last4": "4242",
                    "exp_month": 12,
                    "exp_year": 2025
                },
                "billing_details": {...},
                "metadata": {...},
                "created": datetime,
                "refunded": bool,
                "refund_amount": Decimal,
                "raw": {...}
            }

        Raises:
            StripeError: If the charge cannot be retrieved.

        Example:
            >>> details = await processor.get_payment_details("ch_1234567890")
            >>> print(f"Card: {details['payment_method']['brand']} ending in {details['payment_method']['last4']}")
        """
        logger.info(
            "stripe_get_payment_details",
            charge_id=processor_transaction_id,
        )

        try:
            charge = stripe.Charge.retrieve(
                processor_transaction_id,
                expand=["payment_method", "balance_transaction"],
            )

            # Extract payment method details
            payment_method_details: Dict[str, Any] = {}
            if charge.payment_method_details:
                pm_details = charge.payment_method_details
                payment_method_details["type"] = pm_details.type

                if pm_details.type == "card" and pm_details.card:
                    card = pm_details.card
                    payment_method_details.update({
                        "brand": card.brand,
                        "last4": card.last4,
                        "exp_month": card.exp_month,
                        "exp_year": card.exp_year,
                        "funding": card.funding,
                        "country": card.country,
                    })

            # Build the response
            result: Dict[str, Any] = {
                "id": charge.id,
                "amount": self._convert_cents_to_amount(charge.amount, charge.currency),
                "currency": charge.currency,
                "status": charge.status,
                "payment_method": payment_method_details,
                "billing_details": dict(charge.billing_details) if charge.billing_details else {},
                "metadata": dict(charge.metadata) if charge.metadata else {},
                "created": charge.created,
                "refunded": charge.refunded,
                "refund_amount": self._convert_cents_to_amount(
                    charge.amount_refunded, charge.currency
                ) if charge.amount_refunded else Decimal("0"),
                "receipt_url": charge.receipt_url,
                "description": charge.description,
                "raw": dict(charge),
            }

            logger.info(
                "stripe_payment_details_retrieved",
                charge_id=processor_transaction_id,
                status=charge.status,
            )

            return result

        except InvalidRequestError as e:
            logger.error(
                "stripe_get_details_invalid_request",
                charge_id=processor_transaction_id,
                error_message=str(e),
            )
            raise

        except StripeError as e:
            logger.error(
                "stripe_get_details_error",
                charge_id=processor_transaction_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def create_payment_intent(
        self,
        amount: Decimal,
        currency: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentIntent:
        """Create a Stripe PaymentIntent for client-side confirmation.

        PaymentIntents are used for the modern Stripe payment flow where
        the payment is confirmed on the client side using Stripe.js.

        Args:
            amount: The payment amount (e.g., Decimal("49.99")).
            currency: Three-letter ISO currency code (e.g., "usd").
            metadata: Optional dictionary of metadata to attach to the PaymentIntent.

        Returns:
            PaymentIntent object with ID, client_secret, and status.

        Raises:
            StripeError: If the PaymentIntent cannot be created.

        Example:
            >>> intent = await processor.create_payment_intent(
            ...     amount=Decimal("99.99"),
            ...     currency="usd",
            ...     metadata={"order_id": "order_123"}
            ... )
            >>> # Send intent.client_secret to the client for confirmation
        """
        logger.info(
            "stripe_create_payment_intent_start",
            amount=str(amount),
            currency=currency,
            has_metadata=bool(metadata),
        )

        try:
            amount_cents = self._convert_amount_to_cents(amount, currency)

            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )

            logger.info(
                "stripe_payment_intent_created",
                payment_intent_id=intent.id,
                status=intent.status,
                amount_cents=amount_cents,
            )

            return PaymentIntent(
                id=intent.id,
                client_secret=intent.client_secret,
                status=intent.status,
                amount=intent.amount,
                currency=intent.currency,
                raw_response=dict(intent),
            )

        except InvalidRequestError as e:
            logger.error(
                "stripe_create_intent_invalid_request",
                error_message=str(e),
            )
            raise

        except StripeError as e:
            logger.error(
                "stripe_create_intent_error",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def confirm_payment_intent(
        self,
        payment_intent_id: str,
        payment_method_id: str,
    ) -> ProcessorResult:
        """Confirm a PaymentIntent with a payment method.

        This is typically called server-side when the client cannot confirm
        the payment directly, or for additional server-side validation.

        Args:
            payment_intent_id: The PaymentIntent ID (e.g., "pi_xxx").
            payment_method_id: The PaymentMethod ID (e.g., "pm_xxx").

        Returns:
            ProcessorResult with success status and transaction details.

        Example:
            >>> result = await processor.confirm_payment_intent(
            ...     payment_intent_id="pi_1234567890",
            ...     payment_method_id="pm_card_visa"
            ... )
        """
        logger.info(
            "stripe_confirm_payment_intent_start",
            payment_intent_id=payment_intent_id,
            payment_method_id=payment_method_id,
        )

        try:
            intent = stripe.PaymentIntent.confirm(
                payment_intent_id,
                payment_method=payment_method_id,
            )

            logger.info(
                "stripe_payment_intent_confirmed",
                payment_intent_id=intent.id,
                status=intent.status,
            )

            success = intent.status in ("succeeded", "requires_capture")
            error_message = None

            if intent.status == "requires_action":
                error_message = "Payment requires additional authentication"
            elif intent.status not in ("succeeded", "requires_capture"):
                error_message = f"Payment intent status: {intent.status}"

            return ProcessorResult(
                success=success,
                transaction_id=intent.id,
                error_message=error_message,
                raw_response=dict(intent),
            )

        except CardError as e:
            logger.warning(
                "stripe_confirm_card_error",
                payment_intent_id=payment_intent_id,
                error_code=e.code,
                error_message=str(e.user_message),
            )
            return ProcessorResult(
                success=False,
                transaction_id=payment_intent_id,
                error_message=e.user_message or str(e),
                raw_response={"error": {"code": e.code, "message": str(e)}},
            )

        except InvalidRequestError as e:
            logger.error(
                "stripe_confirm_invalid_request",
                payment_intent_id=payment_intent_id,
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=payment_intent_id,
                error_message=f"Invalid request: {e}",
                raw_response={"error": {"type": "invalid_request", "message": str(e)}},
            )

        except StripeError as e:
            logger.error(
                "stripe_confirm_error",
                payment_intent_id=payment_intent_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=payment_intent_id,
                error_message=f"Payment confirmation error: {e}",
                raw_response={"error": {"type": "stripe_error", "message": str(e)}},
            )

        except Exception as e:
            logger.exception(
                "stripe_confirm_unexpected_error",
                payment_intent_id=payment_intent_id,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            return ProcessorResult(
                success=False,
                transaction_id=payment_intent_id,
                error_message="An unexpected error occurred during payment confirmation",
                raw_response={"error": {"type": "unexpected_error", "message": str(e)}},
            )

    async def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> Dict[str, Any]:
        """Verify and parse a Stripe webhook event.

        Validates that the webhook payload came from Stripe using the
        webhook signing secret.

        Args:
            payload: The raw request body as bytes.
            signature: The Stripe-Signature header value.

        Returns:
            The parsed webhook event as a dictionary.

        Raises:
            ValueError: If the signature is invalid or verification fails.

        Example:
            >>> event = await processor.verify_webhook_signature(
            ...     payload=request.body,
            ...     signature=request.headers["Stripe-Signature"]
            ... )
            >>> if event["type"] == "payment_intent.succeeded":
            ...     handle_successful_payment(event["data"]["object"])
        """
        logger.info("stripe_verify_webhook_start")

        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self.webhook_secret,
            )

            logger.info(
                "stripe_webhook_verified",
                event_type=event.type,
                event_id=event.id,
            )

            return dict(event)

        except stripe.error.SignatureVerificationError as e:
            logger.warning(
                "stripe_webhook_signature_invalid",
                error_message=str(e),
            )
            raise ValueError(f"Invalid webhook signature: {e}")

        except Exception as e:
            logger.error(
                "stripe_webhook_verification_error",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise ValueError(f"Webhook verification failed: {e}")
