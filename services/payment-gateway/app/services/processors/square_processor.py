"""
=============================================================================
FILE: services/processors/square_processor.py
PURPOSE: Square payment processor implementation
=============================================================================
"""

from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import uuid4

import structlog

from app.services.processors.base import (
    BasePaymentProcessor,
    ProcessorResult,
    TokenizeResult,
    RefundResult,
    SubscriptionResult,
)

logger = structlog.get_logger()


class SquareProcessor(BasePaymentProcessor):
    """Square payment processor implementation."""

    processor_name = "square"

    def __init__(
        self,
        api_key: str,
        location_id: str,
        environment: str = "sandbox",
        **kwargs
    ):
        super().__init__(api_key, **kwargs)
        self.location_id = location_id
        self.environment = environment
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from square.client import Client
            self._client = Client(
                access_token=self.api_key,
                environment=self.environment,
            )
        return self._client

    def _convert_amount(self, amount: Decimal) -> int:
        """Convert decimal amount to cents."""
        return int(amount * 100)

    async def charge(
        self,
        amount: Decimal,
        currency: str,
        payment_method_token: str,
        customer_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> ProcessorResult:
        try:
            body = {
                "source_id": payment_method_token,
                "idempotency_key": idempotency_key or str(uuid4()),
                "amount_money": {
                    "amount": self._convert_amount(amount),
                    "currency": currency.upper(),
                },
                "location_id": self.location_id,
                "autocomplete": True,
            }

            if customer_id:
                body["customer_id"] = customer_id
            if description:
                body["note"] = description
            if metadata:
                body["reference_id"] = metadata.get("reference_id", "")

            result = self.client.payments.create_payment(body=body)

            if result.is_success():
                payment = result.body.get("payment", {})
                return ProcessorResult(
                    success=payment.get("status") == "COMPLETED",
                    transaction_id=payment.get("id"),
                    receipt_url=payment.get("receipt_url"),
                    raw_response=result.body,
                )
            else:
                errors = result.errors
                error = errors[0] if errors else {}
                return ProcessorResult(
                    success=False,
                    error_code=error.get("code", "unknown"),
                    error_message=error.get("detail", str(errors)),
                )

        except Exception as e:
            logger.error("square_charge_error", error=str(e))
            return ProcessorResult(
                success=False,
                error_code="exception",
                error_message=str(e),
            )

    async def authorize(
        self,
        amount: Decimal,
        currency: str,
        payment_method_token: str,
        customer_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> ProcessorResult:
        try:
            body = {
                "source_id": payment_method_token,
                "idempotency_key": idempotency_key or str(uuid4()),
                "amount_money": {
                    "amount": self._convert_amount(amount),
                    "currency": currency.upper(),
                },
                "location_id": self.location_id,
                "autocomplete": False,  # Don't auto-complete for auth
            }

            if customer_id:
                body["customer_id"] = customer_id
            if description:
                body["note"] = description

            result = self.client.payments.create_payment(body=body)

            if result.is_success():
                payment = result.body.get("payment", {})
                return ProcessorResult(
                    success=payment.get("status") == "APPROVED",
                    transaction_id=payment.get("id"),
                    raw_response=result.body,
                )
            else:
                errors = result.errors
                error = errors[0] if errors else {}
                return ProcessorResult(
                    success=False,
                    error_code=error.get("code", "unknown"),
                    error_message=error.get("detail", str(errors)),
                )

        except Exception as e:
            logger.error("square_authorize_error", error=str(e))
            return ProcessorResult(
                success=False,
                error_code="exception",
                error_message=str(e),
            )

    async def capture(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
    ) -> ProcessorResult:
        try:
            body = {}
            if amount:
                body["amount_money"] = {
                    "amount": self._convert_amount(amount),
                    "currency": "USD",
                }

            result = self.client.payments.complete_payment(
                payment_id=transaction_id,
                body=body,
            )

            if result.is_success():
                payment = result.body.get("payment", {})
                return ProcessorResult(
                    success=payment.get("status") == "COMPLETED",
                    transaction_id=payment.get("id"),
                    raw_response=result.body,
                )
            else:
                errors = result.errors
                error = errors[0] if errors else {}
                return ProcessorResult(
                    success=False,
                    error_code=error.get("code", "unknown"),
                    error_message=error.get("detail", str(errors)),
                )

        except Exception as e:
            logger.error("square_capture_error", error=str(e))
            return ProcessorResult(
                success=False,
                error_code="exception",
                error_message=str(e),
            )

    async def void(self, transaction_id: str) -> ProcessorResult:
        try:
            result = self.client.payments.cancel_payment(payment_id=transaction_id)

            if result.is_success():
                payment = result.body.get("payment", {})
                return ProcessorResult(
                    success=payment.get("status") == "CANCELED",
                    transaction_id=payment.get("id"),
                    raw_response=result.body,
                )
            else:
                errors = result.errors
                error = errors[0] if errors else {}
                return ProcessorResult(
                    success=False,
                    error_code=error.get("code", "unknown"),
                    error_message=error.get("detail", str(errors)),
                )

        except Exception as e:
            logger.error("square_void_error", error=str(e))
            return ProcessorResult(
                success=False,
                error_code="exception",
                error_message=str(e),
            )

    async def refund(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None,
    ) -> RefundResult:
        try:
            # First get the payment to determine amount if not provided
            payment_result = self.client.payments.get_payment(payment_id=transaction_id)

            if not payment_result.is_success():
                return RefundResult(
                    success=False,
                    error_code="payment_not_found",
                    error_message="Could not retrieve original payment",
                )

            payment = payment_result.body.get("payment", {})
            refund_amount = amount or Decimal(
                payment.get("amount_money", {}).get("amount", 0)
            ) / 100

            body = {
                "idempotency_key": str(uuid4()),
                "payment_id": transaction_id,
                "amount_money": {
                    "amount": self._convert_amount(refund_amount),
                    "currency": payment.get("amount_money", {}).get("currency", "USD"),
                },
            }

            if reason:
                body["reason"] = reason

            result = self.client.refunds.refund_payment(body=body)

            if result.is_success():
                refund = result.body.get("refund", {})
                return RefundResult(
                    success=refund.get("status") in ["COMPLETED", "PENDING"],
                    refund_id=refund.get("id"),
                    raw_response=result.body,
                )
            else:
                errors = result.errors
                error = errors[0] if errors else {}
                return RefundResult(
                    success=False,
                    error_code=error.get("code", "unknown"),
                    error_message=error.get("detail", str(errors)),
                )

        except Exception as e:
            logger.error("square_refund_error", error=str(e))
            return RefundResult(
                success=False,
                error_code="exception",
                error_message=str(e),
            )

    async def tokenize_card(
        self,
        card_token: str,
        customer_id: Optional[str] = None,
    ) -> TokenizeResult:
        try:
            if not customer_id:
                return TokenizeResult(
                    success=False,
                    error_code="customer_required",
                    error_message="Square requires a customer ID to store cards",
                )

            body = {
                "idempotency_key": str(uuid4()),
                "source_id": card_token,
                "card": {
                    "customer_id": customer_id,
                },
            }

            result = self.client.cards.create_card(body=body)

            if result.is_success():
                card = result.body.get("card", {})
                return TokenizeResult(
                    success=True,
                    token=card.get("id"),
                    customer_id=customer_id,
                    card_brand=card.get("card_brand"),
                    card_last_four=card.get("last_4"),
                    card_exp_month=card.get("exp_month"),
                    card_exp_year=card.get("exp_year"),
                    card_fingerprint=card.get("fingerprint"),
                )
            else:
                errors = result.errors
                error = errors[0] if errors else {}
                return TokenizeResult(
                    success=False,
                    error_code=error.get("code", "unknown"),
                    error_message=error.get("detail", str(errors)),
                )

        except Exception as e:
            logger.error("square_tokenize_error", error=str(e))
            return TokenizeResult(
                success=False,
                error_code="exception",
                error_message=str(e),
            )

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = {
            "idempotency_key": str(uuid4()),
            "email_address": email,
        }

        if name:
            parts = name.split(" ", 1)
            body["given_name"] = parts[0]
            if len(parts) > 1:
                body["family_name"] = parts[1]

        if metadata:
            body["reference_id"] = metadata.get("reference_id", "")
            body["note"] = metadata.get("note", "")

        result = self.client.customers.create_customer(body=body)

        if result.is_success():
            customer = result.body.get("customer", {})
            return {
                "id": customer.get("id"),
                "email": customer.get("email_address"),
            }
        else:
            raise Exception(f"Failed to create customer: {result.errors}")

    async def create_subscription(
        self,
        customer_id: str,
        price_amount: Decimal,
        currency: str,
        interval: str,
        payment_method_token: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SubscriptionResult:
        try:
            # Square requires a catalog plan, create one
            plan_body = {
                "idempotency_key": str(uuid4()),
                "object": {
                    "type": "SUBSCRIPTION_PLAN",
                    "id": f"#plan_{uuid4().hex[:8]}",
                    "subscription_plan_data": {
                        "name": f"Subscription - {interval}",
                        "phases": [
                            {
                                "cadence": self._map_interval(interval),
                                "recurring_price_money": {
                                    "amount": self._convert_amount(price_amount),
                                    "currency": currency.upper(),
                                },
                            }
                        ],
                    },
                },
            }

            plan_result = self.client.catalog.upsert_catalog_object(body=plan_body)

            if not plan_result.is_success():
                return SubscriptionResult(
                    success=False,
                    error_code="plan_creation_failed",
                    error_message=str(plan_result.errors),
                )

            plan_id = plan_result.body.get("catalog_object", {}).get("id")

            # Create subscription
            sub_body = {
                "idempotency_key": str(uuid4()),
                "location_id": self.location_id,
                "customer_id": customer_id,
                "plan_id": plan_id,
                "card_id": payment_method_token,
            }

            result = self.client.subscriptions.create_subscription(body=sub_body)

            if result.is_success():
                sub = result.body.get("subscription", {})
                return SubscriptionResult(
                    success=True,
                    subscription_id=sub.get("id"),
                    customer_id=customer_id,
                    status=sub.get("status", "").lower(),
                    current_period_start=sub.get("start_date"),
                    current_period_end=sub.get("charged_through_date"),
                )
            else:
                errors = result.errors
                error = errors[0] if errors else {}
                return SubscriptionResult(
                    success=False,
                    error_code=error.get("code", "unknown"),
                    error_message=error.get("detail", str(errors)),
                )

        except Exception as e:
            logger.error("square_subscription_error", error=str(e))
            return SubscriptionResult(
                success=False,
                error_code="exception",
                error_message=str(e),
            )

    def _map_interval(self, interval: str) -> str:
        """Map billing interval to Square cadence."""
        mapping = {
            "daily": "DAILY",
            "weekly": "WEEKLY",
            "monthly": "MONTHLY",
            "quarterly": "EVERY_THREE_MONTHS",
            "yearly": "ANNUAL",
            "annual": "ANNUAL",
        }
        return mapping.get(interval.lower(), "MONTHLY")

    async def cancel_subscription(self, subscription_id: str) -> SubscriptionResult:
        try:
            result = self.client.subscriptions.cancel_subscription(
                subscription_id=subscription_id
            )

            if result.is_success():
                sub = result.body.get("subscription", {})
                return SubscriptionResult(
                    success=True,
                    subscription_id=sub.get("id"),
                    status="canceled",
                )
            else:
                errors = result.errors
                error = errors[0] if errors else {}
                return SubscriptionResult(
                    success=False,
                    error_code=error.get("code", "unknown"),
                    error_message=error.get("detail", str(errors)),
                )

        except Exception as e:
            logger.error("square_cancel_subscription_error", error=str(e))
            return SubscriptionResult(
                success=False,
                error_code="exception",
                error_message=str(e),
            )

    async def pause_subscription(self, subscription_id: str) -> SubscriptionResult:
        try:
            result = self.client.subscriptions.pause_subscription(
                subscription_id=subscription_id,
                body={},
            )

            if result.is_success():
                sub = result.body.get("subscription", {})
                return SubscriptionResult(
                    success=True,
                    subscription_id=sub.get("id"),
                    status="paused",
                )
            else:
                errors = result.errors
                error = errors[0] if errors else {}
                return SubscriptionResult(
                    success=False,
                    error_code=error.get("code", "unknown"),
                    error_message=error.get("detail", str(errors)),
                )

        except Exception as e:
            logger.error("square_pause_subscription_error", error=str(e))
            return SubscriptionResult(
                success=False,
                error_code="exception",
                error_message=str(e),
            )

    async def resume_subscription(self, subscription_id: str) -> SubscriptionResult:
        try:
            result = self.client.subscriptions.resume_subscription(
                subscription_id=subscription_id,
                body={},
            )

            if result.is_success():
                sub = result.body.get("subscription", {})
                return SubscriptionResult(
                    success=True,
                    subscription_id=sub.get("id"),
                    status=sub.get("status", "").lower(),
                )
            else:
                errors = result.errors
                error = errors[0] if errors else {}
                return SubscriptionResult(
                    success=False,
                    error_code=error.get("code", "unknown"),
                    error_message=error.get("detail", str(errors)),
                )

        except Exception as e:
            logger.error("square_resume_subscription_error", error=str(e))
            return SubscriptionResult(
                success=False,
                error_code="exception",
                error_message=str(e),
            )

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        try:
            from square.utilities.webhooks_helper import is_valid_webhook_event_signature

            return is_valid_webhook_event_signature(
                request_body=payload.decode(),
                signature_header=signature,
                signature_key=self.config.get("webhook_signature_key", ""),
                notification_url=self.config.get("webhook_url", ""),
            )
        except Exception:
            return False
