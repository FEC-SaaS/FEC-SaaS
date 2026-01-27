"""
Unit tests for Payment Service.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.payment import (
    TransactionType,
    TransactionStatus,
    ProcessorType,
)
from app.schemas.payment import ChargeRequest, AuthorizeRequest
from app.services.payment_service import PaymentService
from app.services.processors import ProcessorResult


class TestPaymentService:
    """Tests for PaymentService class."""

    @pytest.mark.asyncio
    async def test_charge_success(self, db_session, mock_stripe_processor):
        """Test successful payment charge."""
        service = PaymentService(db_session)
        venue_id = uuid4()
        customer_id = uuid4()

        # Mock get_processor to return our mock
        with patch.object(service, 'get_processor', new_callable=AsyncMock) as mock_get_proc:
            mock_config = MagicMock()
            mock_config.id = uuid4()
            mock_get_proc.return_value = (mock_stripe_processor, mock_config)

            # Mock fraud service
            with patch.object(service.fraud_service, 'check_transaction', new_callable=AsyncMock) as mock_fraud:
                mock_fraud.return_value = MagicMock(
                    passed=True,
                    fraud_score=Decimal("10.0"),
                    risk_level="low",
                    triggered_rules=[],
                    recommended_action="allow",
                )

                request = ChargeRequest(
                    venue_id=venue_id,
                    customer_id=customer_id,
                    amount=Decimal("99.99"),
                    currency="USD",
                    token="pm_test_123",
                )

                # Mock _get_payment_token
                with patch.object(service, '_get_payment_token', new_callable=AsyncMock) as mock_token:
                    mock_token.return_value = "pm_test_123"

                    result = await service.charge(request)

                    assert result.status == TransactionStatus.COMPLETED
                    assert result.amount == Decimal("99.99")
                    mock_stripe_processor.charge.assert_called_once()

    @pytest.mark.asyncio
    async def test_charge_fraud_blocked(self, db_session, mock_stripe_processor):
        """Test payment blocked by fraud detection."""
        service = PaymentService(db_session)
        venue_id = uuid4()

        with patch.object(service, 'get_processor', new_callable=AsyncMock) as mock_get_proc:
            mock_config = MagicMock()
            mock_config.id = uuid4()
            mock_get_proc.return_value = (mock_stripe_processor, mock_config)

            # Mock fraud check to fail
            with patch.object(service.fraud_service, 'check_transaction', new_callable=AsyncMock) as mock_fraud:
                mock_fraud.return_value = MagicMock(
                    passed=False,
                    fraud_score=Decimal("90.0"),
                    risk_level="critical",
                    triggered_rules=["velocity_limit"],
                    recommended_action="block",
                )

                request = ChargeRequest(
                    venue_id=venue_id,
                    amount=Decimal("99.99"),
                    currency="USD",
                    token="pm_test_123",
                )

                with patch.object(service, '_get_payment_token', new_callable=AsyncMock) as mock_token:
                    mock_token.return_value = "pm_test_123"

                    result = await service.charge(request)

                    assert result.status == TransactionStatus.FRAUD_BLOCKED
                    assert result.error_code == "fraud_blocked"
                    # Processor should not be called
                    mock_stripe_processor.charge.assert_not_called()

    @pytest.mark.asyncio
    async def test_charge_processor_failure(self, db_session):
        """Test payment with processor failure."""
        service = PaymentService(db_session)
        venue_id = uuid4()

        # Create failing processor
        failing_processor = MagicMock()
        failing_processor.charge = AsyncMock(return_value=ProcessorResult(
            success=False,
            error_code="card_declined",
            error_message="Your card was declined",
            decline_code="insufficient_funds",
        ))

        with patch.object(service, 'get_processor', new_callable=AsyncMock) as mock_get_proc:
            mock_config = MagicMock()
            mock_config.id = uuid4()
            mock_get_proc.return_value = (failing_processor, mock_config)

            with patch.object(service.fraud_service, 'check_transaction', new_callable=AsyncMock) as mock_fraud:
                mock_fraud.return_value = MagicMock(
                    passed=True,
                    fraud_score=Decimal("5.0"),
                    risk_level="low",
                    triggered_rules=[],
                    recommended_action="allow",
                )

                request = ChargeRequest(
                    venue_id=venue_id,
                    amount=Decimal("99.99"),
                    currency="USD",
                    token="pm_test_123",
                )

                with patch.object(service, '_get_payment_token', new_callable=AsyncMock) as mock_token:
                    mock_token.return_value = "pm_test_123"

                    result = await service.charge(request)

                    assert result.status == TransactionStatus.DECLINED
                    assert result.error_code == "card_declined"
                    assert result.error_message == "Your card was declined"

    @pytest.mark.asyncio
    async def test_authorize_success(self, db_session, mock_stripe_processor):
        """Test successful payment authorization."""
        service = PaymentService(db_session)
        venue_id = uuid4()

        with patch.object(service, 'get_processor', new_callable=AsyncMock) as mock_get_proc:
            mock_config = MagicMock()
            mock_config.id = uuid4()
            mock_get_proc.return_value = (mock_stripe_processor, mock_config)

            request = AuthorizeRequest(
                venue_id=venue_id,
                amount=Decimal("150.00"),
                currency="USD",
                token="pm_test_123",
            )

            with patch.object(service, '_get_payment_token', new_callable=AsyncMock) as mock_token:
                mock_token.return_value = "pm_test_123"

                result = await service.authorize(request)

                assert result.status == TransactionStatus.AUTHORIZED
                assert result.transaction_type == TransactionType.AUTHORIZATION
                mock_stripe_processor.authorize.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_payment_method_raises_error(self, db_session):
        """Test that missing payment method raises error."""
        service = PaymentService(db_session)
        venue_id = uuid4()

        request = ChargeRequest(
            venue_id=venue_id,
            amount=Decimal("99.99"),
            currency="USD",
            # No token or payment_method_id
        )

        with pytest.raises(ValueError, match="No payment method provided"):
            await service._get_payment_token(request)


class TestPaymentAmountValidation:
    """Tests for payment amount validation."""

    def test_amount_must_be_positive(self):
        """Test that amount must be greater than 0."""
        with pytest.raises(ValueError):
            ChargeRequest(
                venue_id=uuid4(),
                amount=Decimal("0"),
                currency="USD",
                token="pm_test",
            )

    def test_amount_cannot_be_negative(self):
        """Test that negative amounts are rejected."""
        with pytest.raises(ValueError):
            ChargeRequest(
                venue_id=uuid4(),
                amount=Decimal("-10.00"),
                currency="USD",
                token="pm_test",
            )

    def test_valid_amount_accepted(self):
        """Test that valid amounts are accepted."""
        request = ChargeRequest(
            venue_id=uuid4(),
            amount=Decimal("99.99"),
            currency="USD",
            token="pm_test",
        )
        assert request.amount == Decimal("99.99")


class TestCurrencyValidation:
    """Tests for currency validation."""

    def test_currency_must_be_3_chars(self):
        """Test that currency must be exactly 3 characters."""
        with pytest.raises(ValueError):
            ChargeRequest(
                venue_id=uuid4(),
                amount=Decimal("10.00"),
                currency="US",  # Too short
                token="pm_test",
            )

    def test_valid_currency_accepted(self):
        """Test that valid currencies are accepted."""
        for currency in ["USD", "EUR", "GBP", "CAD"]:
            request = ChargeRequest(
                venue_id=uuid4(),
                amount=Decimal("10.00"),
                currency=currency,
                token="pm_test",
            )
            assert request.currency == currency
