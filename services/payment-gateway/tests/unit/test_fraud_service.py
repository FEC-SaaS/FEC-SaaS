"""
Unit tests for Fraud Service.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.models.payment import (
    FraudRuleType,
    RiskLevel,
    FraudAlertStatus,
    RecommendedAction,
)
from app.schemas.payment import FraudRuleCreate, ChargeRequest
from app.services.fraud_service import FraudService


class TestFraudService:
    """Tests for FraudService class."""

    @pytest.mark.asyncio
    async def test_low_risk_transaction_passes(self, db_session):
        """Test that low risk transactions pass fraud check."""
        service = FraudService(db_session)

        # Mock no rules to trigger
        with patch.object(service, '_get_active_rules', new_callable=AsyncMock) as mock_rules:
            mock_rules.return_value = []

            transaction = MagicMock()
            transaction.id = uuid4()
            transaction.venue_id = uuid4()
            transaction.customer_id = uuid4()
            transaction.amount = Decimal("50.00")

            request = ChargeRequest(
                venue_id=transaction.venue_id,
                amount=transaction.amount,
                currency="USD",
                token="pm_test",
            )

            result = await service.check_transaction(transaction, request)

            assert result.passed is True
            assert result.fraud_score == Decimal("0")
            assert result.risk_level == RiskLevel.LOW
            assert result.recommended_action == RecommendedAction.ALLOW

    @pytest.mark.asyncio
    async def test_high_risk_triggers_alert(self, db_session):
        """Test that high risk transactions trigger alerts."""
        service = FraudService(db_session)

        # Create mock rule that triggers
        mock_rule = MagicMock()
        mock_rule.id = uuid4()
        mock_rule.rule_name = "high_amount"
        mock_rule.rule_type = FraudRuleType.AMOUNT_THRESHOLD
        mock_rule.rule_conditions = {"max_amount": 100}
        mock_rule.risk_score_impact = 80  # High score

        with patch.object(service, '_get_active_rules', new_callable=AsyncMock) as mock_rules:
            mock_rules.return_value = [mock_rule]

            # Mock the amount threshold check to trigger
            with patch.object(service, '_check_amount_threshold') as mock_check:
                mock_check.return_value = (True, {"reason": "Amount exceeds threshold"})

                transaction = MagicMock()
                transaction.id = uuid4()
                transaction.venue_id = uuid4()
                transaction.amount = Decimal("500.00")

                request = ChargeRequest(
                    venue_id=transaction.venue_id,
                    amount=transaction.amount,
                    currency="USD",
                    token="pm_test",
                )

                result = await service.check_transaction(transaction, request)

                assert result.passed is False
                assert result.fraud_score >= Decimal("80")
                assert result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
                assert "high_amount" in result.triggered_rules

    @pytest.mark.asyncio
    async def test_velocity_check_blocks_rapid_transactions(self, db_session):
        """Test velocity check blocks rapid transactions."""
        service = FraudService(db_session)

        conditions = {
            "time_window_minutes": 60,
            "max_transactions": 5,
            "max_amount": 1000,
        }

        transaction = MagicMock()
        transaction.customer_id = uuid4()
        transaction.amount = Decimal("100.00")

        details = {}

        # Mock db query to return high transaction count
        with patch.object(db_session, 'execute', new_callable=AsyncMock) as mock_exec:
            # First call returns transaction count
            mock_result1 = MagicMock()
            mock_result1.scalar.return_value = 10  # Exceeds max of 5

            # Second call returns total amount
            mock_result2 = MagicMock()
            mock_result2.scalar.return_value = Decimal("500.00")

            mock_exec.side_effect = [mock_result1, mock_result2]

            triggered, result_details = await service._check_velocity(
                conditions, transaction, details
            )

            assert triggered is True
            assert "exceeded max transactions" in result_details.get("reason", "").lower()


class TestRiskLevelCalculation:
    """Tests for risk level calculation."""

    def test_low_score_is_low_risk(self, db_session):
        """Test that low scores result in low risk."""
        service = FraudService(db_session)

        assert service._calculate_risk_level(Decimal("10")) == RiskLevel.LOW
        assert service._calculate_risk_level(Decimal("0")) == RiskLevel.LOW

    def test_medium_score_is_medium_risk(self, db_session):
        """Test that medium scores result in medium risk."""
        service = FraudService(db_session)

        # Default threshold is 30 for medium
        assert service._calculate_risk_level(Decimal("35")) == RiskLevel.MEDIUM

    def test_high_score_is_high_risk(self, db_session):
        """Test that high scores result in high risk."""
        service = FraudService(db_session)

        # Default threshold is 60 for high
        assert service._calculate_risk_level(Decimal("65")) == RiskLevel.HIGH

    def test_critical_score_is_critical_risk(self, db_session):
        """Test that critical scores result in critical risk."""
        service = FraudService(db_session)

        # Default threshold is 80 for critical
        assert service._calculate_risk_level(Decimal("85")) == RiskLevel.CRITICAL


class TestRecommendedActions:
    """Tests for recommended action determination."""

    def test_low_risk_recommends_allow(self, db_session):
        """Test that low risk recommends allow."""
        service = FraudService(db_session)
        assert service._get_recommended_action(RiskLevel.LOW) == RecommendedAction.ALLOW

    def test_medium_risk_recommends_flag(self, db_session):
        """Test that medium risk recommends flag."""
        service = FraudService(db_session)
        assert service._get_recommended_action(RiskLevel.MEDIUM) == RecommendedAction.FLAG

    def test_high_risk_recommends_review(self, db_session):
        """Test that high risk recommends manual review."""
        service = FraudService(db_session)
        assert service._get_recommended_action(RiskLevel.HIGH) == RecommendedAction.MANUAL_REVIEW

    def test_critical_risk_recommends_block(self, db_session):
        """Test that critical risk recommends block."""
        service = FraudService(db_session)
        assert service._get_recommended_action(RiskLevel.CRITICAL) == RecommendedAction.BLOCK


class TestFraudRuleValidation:
    """Tests for fraud rule creation and validation."""

    def test_create_rule_requires_name(self):
        """Test that rule name is required."""
        with pytest.raises(ValueError):
            FraudRuleCreate(
                rule_name="",  # Empty name should fail
                rule_type=FraudRuleType.VELOCITY,
                rule_conditions={"max_transactions": 10},
            )

    def test_create_rule_requires_conditions(self):
        """Test that rule conditions are required."""
        with pytest.raises(ValueError):
            FraudRuleCreate(
                rule_name="Test Rule",
                rule_type=FraudRuleType.VELOCITY,
                rule_conditions={},  # Empty conditions
            )

    def test_valid_rule_creation(self):
        """Test valid rule creation."""
        rule = FraudRuleCreate(
            rule_name="Velocity Limit",
            rule_type=FraudRuleType.VELOCITY,
            rule_conditions={
                "time_window_minutes": 60,
                "max_transactions": 10,
                "max_amount": 5000,
            },
            risk_score_impact=25,
        )

        assert rule.rule_name == "Velocity Limit"
        assert rule.rule_type == FraudRuleType.VELOCITY
        assert rule.risk_score_impact == 25


class TestAmountThresholdCheck:
    """Tests for amount threshold fraud rule."""

    def test_amount_below_minimum_triggers(self, db_session):
        """Test that amount below minimum triggers rule."""
        service = FraudService(db_session)

        conditions = {"min_amount": 10}
        transaction = MagicMock()
        transaction.amount = Decimal("5.00")

        triggered, details = service._check_amount_threshold(conditions, transaction, {})

        assert triggered is True
        assert "below minimum" in details.get("reason", "").lower()

    def test_amount_above_maximum_triggers(self, db_session):
        """Test that amount above maximum triggers rule."""
        service = FraudService(db_session)

        conditions = {"max_amount": 1000}
        transaction = MagicMock()
        transaction.amount = Decimal("1500.00")

        triggered, details = service._check_amount_threshold(conditions, transaction, {})

        assert triggered is True
        assert "exceeds maximum" in details.get("reason", "").lower()

    def test_amount_within_range_passes(self, db_session):
        """Test that amount within range passes."""
        service = FraudService(db_session)

        conditions = {"min_amount": 10, "max_amount": 1000}
        transaction = MagicMock()
        transaction.amount = Decimal("500.00")

        triggered, details = service._check_amount_threshold(conditions, transaction, {})

        assert triggered is False
