"""
=============================================================================
FILE: services/fraud_service.py
PURPOSE: Fraud detection and prevention service
=============================================================================
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.payment import (
    FraudDetectionRule,
    FraudAlert,
    PaymentTransaction,
    TransactionStatus,
    FraudRuleType,
    RiskLevel,
    FraudAlertStatus,
    RecommendedAction,
)
from app.schemas.payment import (
    FraudRuleCreate,
    FraudRuleUpdate,
    FraudRuleResponse,
    FraudAlertResponse,
    FraudAlertReview,
    FraudAlertListResponse,
    FraudCheckResult,
    ChargeRequest,
    PaginationParams,
)

logger = structlog.get_logger()


class FraudService:
    """Service for fraud detection and rule management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_transaction(
        self,
        transaction: PaymentTransaction,
        request: ChargeRequest,
    ) -> FraudCheckResult:
        """Run fraud checks on a transaction."""
        triggered_rules: List[str] = []
        rule_details: Dict[str, Any] = {}
        total_score = Decimal("0")

        # Get applicable rules (global + venue-specific)
        rules = await self._get_active_rules(transaction.venue_id)

        for rule in rules:
            is_triggered, details = await self._evaluate_rule(rule, transaction, request)
            if is_triggered:
                triggered_rules.append(rule.rule_name)
                rule_details[rule.rule_name] = details
                total_score += rule.risk_score_impact

        # Calculate risk level
        risk_level = self._calculate_risk_level(total_score)
        recommended_action = self._get_recommended_action(risk_level)
        passed = risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]

        # Create fraud alert if high/critical
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            alert = FraudAlert(
                id=uuid4(),
                payment_id=transaction.id,
                alert_type="automated_detection",
                fraud_score=total_score,
                risk_level=risk_level,
                triggered_rules=triggered_rules,
                rule_details=rule_details,
                recommended_action=recommended_action,
                status=FraudAlertStatus.PENDING,
            )
            self.db.add(alert)

            logger.warning(
                "fraud_alert_created",
                payment_id=str(transaction.id),
                fraud_score=float(total_score),
                risk_level=risk_level.value,
            )

        return FraudCheckResult(
            passed=passed,
            fraud_score=total_score,
            risk_level=risk_level,
            triggered_rules=triggered_rules,
            recommended_action=recommended_action,
            details=rule_details,
        )

    async def _get_active_rules(self, venue_id: UUID) -> List[FraudDetectionRule]:
        """Get active fraud rules for a venue."""
        query = (
            select(FraudDetectionRule)
            .where(
                FraudDetectionRule.is_active == True,
                (FraudDetectionRule.venue_id == venue_id) | (FraudDetectionRule.venue_id.is_(None))
            )
            .order_by(FraudDetectionRule.priority)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _evaluate_rule(
        self,
        rule: FraudDetectionRule,
        transaction: PaymentTransaction,
        request: ChargeRequest,
    ) -> tuple[bool, Dict[str, Any]]:
        """Evaluate a single fraud rule."""
        conditions = rule.rule_conditions
        details: Dict[str, Any] = {}

        if rule.rule_type == FraudRuleType.VELOCITY:
            return await self._check_velocity(conditions, transaction, details)
        elif rule.rule_type == FraudRuleType.AMOUNT_THRESHOLD:
            return self._check_amount_threshold(conditions, transaction, details)
        elif rule.rule_type == FraudRuleType.GEO_LOCATION:
            return await self._check_geo_location(conditions, request, details)
        elif rule.rule_type == FraudRuleType.CARD_BIN:
            return await self._check_card_bin(conditions, transaction, details)
        elif rule.rule_type == FraudRuleType.DEVICE_FINGERPRINT:
            return await self._check_device_fingerprint(conditions, request, details)
        elif rule.rule_type == FraudRuleType.IP_ADDRESS:
            return await self._check_ip_address(conditions, request, details)
        elif rule.rule_type == FraudRuleType.CUSTOM:
            return self._check_custom_rule(conditions, transaction, request, details)

        return False, details

    async def _check_velocity(
        self,
        conditions: Dict[str, Any],
        transaction: PaymentTransaction,
        details: Dict[str, Any],
    ) -> tuple[bool, Dict[str, Any]]:
        """Check velocity-based fraud rules."""
        time_window = conditions.get("time_window_minutes", 60)
        max_transactions = conditions.get("max_transactions", 10)
        max_amount = Decimal(str(conditions.get("max_amount", 10000)))

        since = datetime.utcnow() - timedelta(minutes=time_window)

        # Count recent transactions
        if transaction.customer_id:
            count_query = select(func.count()).select_from(PaymentTransaction).where(
                and_(
                    PaymentTransaction.customer_id == transaction.customer_id,
                    PaymentTransaction.created_at >= since,
                    PaymentTransaction.status.in_([
                        TransactionStatus.COMPLETED,
                        TransactionStatus.PENDING,
                    ]),
                )
            )
            result = await self.db.execute(count_query)
            transaction_count = result.scalar() or 0

            # Sum recent amounts
            sum_query = select(func.sum(PaymentTransaction.amount)).where(
                and_(
                    PaymentTransaction.customer_id == transaction.customer_id,
                    PaymentTransaction.created_at >= since,
                    PaymentTransaction.status.in_([
                        TransactionStatus.COMPLETED,
                        TransactionStatus.PENDING,
                    ]),
                )
            )
            result = await self.db.execute(sum_query)
            total_amount = result.scalar() or Decimal("0")

            details["transaction_count"] = transaction_count
            details["total_amount"] = float(total_amount)
            details["time_window_minutes"] = time_window

            if transaction_count >= max_transactions:
                details["reason"] = f"Exceeded max transactions ({max_transactions}) in {time_window} minutes"
                return True, details

            if total_amount + transaction.amount > max_amount:
                details["reason"] = f"Exceeded max amount (${max_amount}) in {time_window} minutes"
                return True, details

        return False, details

    def _check_amount_threshold(
        self,
        conditions: Dict[str, Any],
        transaction: PaymentTransaction,
        details: Dict[str, Any],
    ) -> tuple[bool, Dict[str, Any]]:
        """Check amount-based fraud rules."""
        min_amount = Decimal(str(conditions.get("min_amount", 0)))
        max_amount = Decimal(str(conditions.get("max_amount", float("inf"))))

        details["amount"] = float(transaction.amount)

        if transaction.amount < min_amount:
            details["reason"] = f"Amount below minimum threshold (${min_amount})"
            return True, details

        if max_amount and transaction.amount > max_amount:
            details["reason"] = f"Amount exceeds maximum threshold (${max_amount})"
            return True, details

        return False, details

    async def _check_geo_location(
        self,
        conditions: Dict[str, Any],
        request: ChargeRequest,
        details: Dict[str, Any],
    ) -> tuple[bool, Dict[str, Any]]:
        """Check geo-location based fraud rules."""
        blocked_countries = conditions.get("blocked_countries", [])
        allowed_countries = conditions.get("allowed_countries", [])

        if not request.ip_address:
            return False, details

        # In production, use a GeoIP service
        # For now, we'll use a placeholder
        country = await self._get_country_from_ip(request.ip_address)
        details["detected_country"] = country
        details["ip_address"] = request.ip_address

        if blocked_countries and country in blocked_countries:
            details["reason"] = f"Transaction from blocked country: {country}"
            return True, details

        if allowed_countries and country not in allowed_countries:
            details["reason"] = f"Transaction from non-allowed country: {country}"
            return True, details

        return False, details

    async def _get_country_from_ip(self, ip_address: str) -> str:
        """Get country from IP address. Placeholder for GeoIP service."""
        # In production, integrate with MaxMind or similar
        return "US"

    async def _check_card_bin(
        self,
        conditions: Dict[str, Any],
        transaction: PaymentTransaction,
        details: Dict[str, Any],
    ) -> tuple[bool, Dict[str, Any]]:
        """Check card BIN-based fraud rules."""
        blocked_bins = conditions.get("blocked_bins", [])
        high_risk_bins = conditions.get("high_risk_bins", [])

        # Would need to get card BIN from payment method
        # Placeholder implementation
        return False, details

    async def _check_device_fingerprint(
        self,
        conditions: Dict[str, Any],
        request: ChargeRequest,
        details: Dict[str, Any],
    ) -> tuple[bool, Dict[str, Any]]:
        """Check device fingerprint fraud rules."""
        if not request.device_fingerprint:
            if conditions.get("require_fingerprint", False):
                details["reason"] = "Device fingerprint required but not provided"
                return True, details
            return False, details

        # Check if fingerprint is associated with previous fraud
        query = select(func.count()).select_from(PaymentTransaction).where(
            and_(
                PaymentTransaction.device_fingerprint == request.device_fingerprint,
                PaymentTransaction.status == TransactionStatus.FRAUD_BLOCKED,
            )
        )
        result = await self.db.execute(query)
        fraud_count = result.scalar() or 0

        if fraud_count > 0:
            details["reason"] = f"Device fingerprint associated with {fraud_count} previous fraud attempts"
            details["fraud_count"] = fraud_count
            return True, details

        return False, details

    async def _check_ip_address(
        self,
        conditions: Dict[str, Any],
        request: ChargeRequest,
        details: Dict[str, Any],
    ) -> tuple[bool, Dict[str, Any]]:
        """Check IP address fraud rules."""
        blocked_ips = conditions.get("blocked_ips", [])
        blocked_ranges = conditions.get("blocked_ranges", [])

        if not request.ip_address:
            return False, details

        if request.ip_address in blocked_ips:
            details["reason"] = f"IP address {request.ip_address} is blocked"
            return True, details

        # Check previous fraud from this IP
        query = select(func.count()).select_from(PaymentTransaction).where(
            and_(
                PaymentTransaction.ip_address == request.ip_address,
                PaymentTransaction.status == TransactionStatus.FRAUD_BLOCKED,
            )
        )
        result = await self.db.execute(query)
        fraud_count = result.scalar() or 0

        if fraud_count >= conditions.get("max_fraud_attempts", 3):
            details["reason"] = f"IP address associated with {fraud_count} previous fraud attempts"
            return True, details

        return False, details

    def _check_custom_rule(
        self,
        conditions: Dict[str, Any],
        transaction: PaymentTransaction,
        request: ChargeRequest,
        details: Dict[str, Any],
    ) -> tuple[bool, Dict[str, Any]]:
        """Check custom fraud rules."""
        # Custom rules can be implemented based on conditions
        return False, details

    def _calculate_risk_level(self, score: Decimal) -> RiskLevel:
        """Calculate risk level from fraud score."""
        if score >= settings.fraud_score_critical_threshold:
            return RiskLevel.CRITICAL
        elif score >= settings.fraud_score_high_threshold:
            return RiskLevel.HIGH
        elif score >= settings.fraud_score_medium_threshold:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _get_recommended_action(self, risk_level: RiskLevel) -> RecommendedAction:
        """Get recommended action based on risk level."""
        if risk_level == RiskLevel.CRITICAL:
            return RecommendedAction.BLOCK
        elif risk_level == RiskLevel.HIGH:
            return RecommendedAction.MANUAL_REVIEW
        elif risk_level == RiskLevel.MEDIUM:
            return RecommendedAction.FLAG
        else:
            return RecommendedAction.ALLOW

    async def create_rule(self, data: FraudRuleCreate) -> FraudRuleResponse:
        """Create a new fraud detection rule."""
        rule = FraudDetectionRule(
            id=uuid4(),
            venue_id=data.venue_id,
            rule_name=data.rule_name,
            rule_type=data.rule_type,
            rule_conditions=data.rule_conditions,
            risk_score_impact=data.risk_score_impact,
            description=data.description,
            priority=data.priority,
            is_active=True,
        )
        self.db.add(rule)
        await self.db.flush()
        return FraudRuleResponse.model_validate(rule)

    async def update_rule(self, rule_id: UUID, data: FraudRuleUpdate) -> FraudRuleResponse:
        """Update a fraud detection rule."""
        result = await self.db.execute(
            select(FraudDetectionRule).where(FraudDetectionRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if not rule:
            raise ValueError(f"Rule {rule_id} not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)

        await self.db.flush()
        return FraudRuleResponse.model_validate(rule)

    async def delete_rule(self, rule_id: UUID) -> None:
        """Delete a fraud detection rule."""
        result = await self.db.execute(
            select(FraudDetectionRule).where(FraudDetectionRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if rule:
            await self.db.delete(rule)
            await self.db.flush()

    async def list_rules(
        self,
        venue_id: Optional[UUID] = None,
        include_global: bool = True,
    ) -> List[FraudRuleResponse]:
        """List fraud detection rules."""
        conditions = []
        if venue_id:
            if include_global:
                conditions.append(
                    (FraudDetectionRule.venue_id == venue_id) |
                    (FraudDetectionRule.venue_id.is_(None))
                )
            else:
                conditions.append(FraudDetectionRule.venue_id == venue_id)
        elif not include_global:
            conditions.append(FraudDetectionRule.venue_id.isnot(None))

        query = select(FraudDetectionRule).order_by(FraudDetectionRule.priority)
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.db.execute(query)
        rules = result.scalars().all()
        return [FraudRuleResponse.model_validate(r) for r in rules]

    async def review_alert(
        self,
        alert_id: UUID,
        review: FraudAlertReview,
        reviewer_id: UUID,
    ) -> FraudAlertResponse:
        """Review a fraud alert."""
        result = await self.db.execute(
            select(FraudAlert).where(FraudAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = review.action
        alert.reviewed_by = reviewer_id
        alert.review_notes = review.notes
        alert.reviewed_at = datetime.utcnow()

        await self.db.flush()
        return FraudAlertResponse.model_validate(alert)

    async def list_alerts(
        self,
        venue_id: Optional[UUID] = None,
        status: Optional[FraudAlertStatus] = None,
        params: PaginationParams = PaginationParams(),
    ) -> FraudAlertListResponse:
        """List fraud alerts."""
        query = select(FraudAlert).join(PaymentTransaction)

        if venue_id:
            query = query.where(PaymentTransaction.venue_id == venue_id)
        if status:
            query = query.where(FraudAlert.status == status)

        # Get count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        query = query.order_by(FraudAlert.created_at.desc())
        offset = (params.page - 1) * params.page_size
        query = query.offset(offset).limit(params.page_size)

        result = await self.db.execute(query)
        alerts = result.scalars().all()

        return FraudAlertListResponse(
            alerts=[FraudAlertResponse.model_validate(a) for a in alerts],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )
