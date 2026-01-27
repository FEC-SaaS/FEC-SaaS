"""
=============================================================================
FILE: services/processors/stripe_processor.py
PURPOSE: Stripe payment processor implementation
=============================================================================
"""

from decimal import Decimal
from typing import Any, Dict, Optional

import structlog

from app.services.processors.base import (
    BasePaymentProcessor,
    ProcessorResult,
    TokenizeResult,
    RefundResult,
    SubscriptionResult,
)

logger = structlog.get_logger()


class StripeProcessor(BasePaymentProcessor):
    """Stripe payment processor implementation."""
    
    processor_name = "stripe"
    
    def __init__(self, api_key: str, webhook_secret: Optional[str] = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.webhook_secret = webhook_secret
        self._stripe = None
    
    @property
    def stripe(self):
        if self._stripe is None:
            import stripe
            stripe.api_key = self.api_key
            self._stripe = stripe
        return self._stripe
    
    async def charge(
        self, amount: Decimal, currency: str, payment_method_token: str,
        customer_id: Optional[str] = None, description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None, idempotency_key: Optional[str] = None,
    ) -> ProcessorResult:
        try:
            params = {
                "amount": int(amount * 100),
                "currency": currency.lower(),
                "payment_method": payment_method_token,
                "confirm": True,
                "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
            }
            if customer_id: params["customer"] = customer_id
            if description: params["description"] = description
            if metadata: params["metadata"] = metadata
            
            idempotency = {"idempotency_key": idempotency_key} if idempotency_key else {}
            intent = self.stripe.PaymentIntent.create(**params, **idempotency)
            
            return ProcessorResult(
                success=intent.status == "succeeded",
                transaction_id=intent.id,
                raw_response=dict(intent),
            )
        except self.stripe.error.CardError as e:
            return ProcessorResult(success=False, error_code=e.code, error_message=str(e.user_message), decline_code=e.decline_code)
        except self.stripe.error.StripeError as e:
            return ProcessorResult(success=False, error_code=getattr(e, "code", "unknown"), error_message=str(e))

    async def authorize(
        self, amount: Decimal, currency: str, payment_method_token: str,
        customer_id: Optional[str] = None, description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None, idempotency_key: Optional[str] = None,
    ) -> ProcessorResult:
        try:
            params = {
                "amount": int(amount * 100), "currency": currency.lower(),
                "payment_method": payment_method_token, "capture_method": "manual", "confirm": True,
            }
            if customer_id: params["customer"] = customer_id
            if description: params["description"] = description
            if metadata: params["metadata"] = metadata
            idempotency = {"idempotency_key": idempotency_key} if idempotency_key else {}
            intent = self.stripe.PaymentIntent.create(**params, **idempotency)
            return ProcessorResult(success=intent.status == "requires_capture", transaction_id=intent.id, raw_response=dict(intent))
        except self.stripe.error.StripeError as e:
            return ProcessorResult(success=False, error_code=getattr(e, "code", "unknown"), error_message=str(e))

    async def capture(self, transaction_id: str, amount: Optional[Decimal] = None) -> ProcessorResult:
        try:
            params = {"amount_to_capture": int(amount * 100)} if amount else {}
            intent = self.stripe.PaymentIntent.capture(transaction_id, **params)
            return ProcessorResult(success=intent.status == "succeeded", transaction_id=intent.id, raw_response=dict(intent))
        except self.stripe.error.StripeError as e:
            return ProcessorResult(success=False, error_code=getattr(e, "code", "unknown"), error_message=str(e))

    async def void(self, transaction_id: str) -> ProcessorResult:
        try:
            intent = self.stripe.PaymentIntent.cancel(transaction_id)
            return ProcessorResult(success=intent.status == "canceled", transaction_id=intent.id, raw_response=dict(intent))
        except self.stripe.error.StripeError as e:
            return ProcessorResult(success=False, error_code=getattr(e, "code", "unknown"), error_message=str(e))

    async def refund(self, transaction_id: str, amount: Optional[Decimal] = None, reason: Optional[str] = None) -> RefundResult:
        try:
            params = {"payment_intent": transaction_id}
            if amount: params["amount"] = int(amount * 100)
            if reason: params["reason"] = reason
            refund = self.stripe.Refund.create(**params)
            return RefundResult(success=refund.status == "succeeded", refund_id=refund.id, raw_response=dict(refund))
        except self.stripe.error.StripeError as e:
            return RefundResult(success=False, error_code=getattr(e, "code", "unknown"), error_message=str(e))

    async def tokenize_card(self, card_token: str, customer_id: Optional[str] = None) -> TokenizeResult:
        try:
            pm = self.stripe.PaymentMethod.retrieve(card_token)
            if customer_id: self.stripe.PaymentMethod.attach(card_token, customer=customer_id)
            card = pm.get("card", {})
            return TokenizeResult(
                success=True, token=pm.id, customer_id=customer_id, card_brand=card.get("brand"),
                card_last_four=card.get("last4"), card_exp_month=card.get("exp_month"),
                card_exp_year=card.get("exp_year"), card_fingerprint=card.get("fingerprint"),
            )
        except self.stripe.error.StripeError as e:
            return TokenizeResult(success=False, error_code=getattr(e, "code", "unknown"), error_message=str(e))

    async def create_customer(self, email: str, name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = {"email": email}
        if name: params["name"] = name
        if metadata: params["metadata"] = metadata
        customer = self.stripe.Customer.create(**params)
        return {"id": customer.id, "email": customer.email}

    async def create_subscription(
        self, customer_id: str, price_amount: Decimal, currency: str, interval: str,
        payment_method_token: str, metadata: Optional[Dict[str, Any]] = None,
    ) -> SubscriptionResult:
        try:
            self.stripe.PaymentMethod.attach(payment_method_token, customer=customer_id)
            self.stripe.Customer.modify(customer_id, invoice_settings={"default_payment_method": payment_method_token})
            price = self.stripe.Price.create(
                unit_amount=int(price_amount * 100), currency=currency.lower(),
                recurring={"interval": interval}, product_data={"name": f"Subscription - {interval}"},
            )
            sub = self.stripe.Subscription.create(customer=customer_id, items=[{"price": price.id}], metadata=metadata or {})
            return SubscriptionResult(
                success=True, subscription_id=sub.id, customer_id=customer_id, status=sub.status,
                current_period_start=str(sub.current_period_start), current_period_end=str(sub.current_period_end),
            )
        except self.stripe.error.StripeError as e:
            return SubscriptionResult(success=False, error_code=getattr(e, "code", "unknown"), error_message=str(e))

    async def cancel_subscription(self, subscription_id: str) -> SubscriptionResult:
        try:
            sub = self.stripe.Subscription.delete(subscription_id)
            return SubscriptionResult(success=True, subscription_id=sub.id, status=sub.status)
        except self.stripe.error.StripeError as e:
            return SubscriptionResult(success=False, error_message=str(e))

    async def pause_subscription(self, subscription_id: str) -> SubscriptionResult:
        try:
            sub = self.stripe.Subscription.modify(subscription_id, pause_collection={"behavior": "void"})
            return SubscriptionResult(success=True, subscription_id=sub.id, status="paused")
        except self.stripe.error.StripeError as e:
            return SubscriptionResult(success=False, error_message=str(e))

    async def resume_subscription(self, subscription_id: str) -> SubscriptionResult:
        try:
            sub = self.stripe.Subscription.modify(subscription_id, pause_collection="")
            return SubscriptionResult(success=True, subscription_id=sub.id, status=sub.status)
        except self.stripe.error.StripeError as e:
            return SubscriptionResult(success=False, error_message=str(e))

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        try:
            self.stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
            return True
        except Exception:
            return False
