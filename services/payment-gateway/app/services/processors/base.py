"""
=============================================================================
FILE: services/processors/base.py
PURPOSE: Base payment processor interface
=============================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID


@dataclass
class ProcessorResult:
    """Result from payment processor operation."""
    success: bool
    transaction_id: Optional[str] = None
    authorization_code: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    decline_code: Optional[str] = None
    receipt_url: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    processor_fee: Optional[Decimal] = None


@dataclass
class TokenizeResult:
    """Result from payment method tokenization."""
    success: bool
    token: Optional[str] = None
    customer_id: Optional[str] = None
    card_brand: Optional[str] = None
    card_last_four: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None
    card_fingerprint: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RefundResult:
    """Result from refund operation."""
    success: bool
    refund_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class SubscriptionResult:
    """Result from subscription operation."""
    success: bool
    subscription_id: Optional[str] = None
    customer_id: Optional[str] = None
    status: Optional[str] = None
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class BasePaymentProcessor(ABC):
    """Abstract base class for payment processors."""
    
    processor_name: str = "base"
    
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.config = kwargs
    
    @abstractmethod
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
        """Process a payment charge."""
        pass
    
    @abstractmethod
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
        """Authorize a payment (capture later)."""
        pass
    
    @abstractmethod
    async def capture(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
    ) -> ProcessorResult:
        """Capture an authorized payment."""
        pass
    
    @abstractmethod
    async def void(
        self,
        transaction_id: str,
    ) -> ProcessorResult:
        """Void a payment."""
        pass
    
    @abstractmethod
    async def refund(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None,
    ) -> RefundResult:
        """Refund a payment."""
        pass
    
    @abstractmethod
    async def tokenize_card(
        self,
        card_token: str,
        customer_id: Optional[str] = None,
    ) -> TokenizeResult:
        """Tokenize a card for future use."""
        pass
    
    @abstractmethod
    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a customer in the processor."""
        pass
    
    @abstractmethod
    async def create_subscription(
        self,
        customer_id: str,
        price_amount: Decimal,
        currency: str,
        interval: str,
        payment_method_token: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SubscriptionResult:
        """Create a subscription."""
        pass
    
    @abstractmethod
    async def cancel_subscription(
        self,
        subscription_id: str,
    ) -> SubscriptionResult:
        """Cancel a subscription."""
        pass
    
    @abstractmethod
    async def pause_subscription(
        self,
        subscription_id: str,
    ) -> SubscriptionResult:
        """Pause a subscription."""
        pass
    
    @abstractmethod
    async def resume_subscription(
        self,
        subscription_id: str,
    ) -> SubscriptionResult:
        """Resume a paused subscription."""
        pass
    
    @abstractmethod
    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify webhook signature."""
        pass
