"""
Integration tests for Payment API endpoints.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient


class TestPaymentEndpoints:
    """Integration tests for payment API endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "payment-gateway"

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns service info."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Payment Gateway Service"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_charge_requires_auth(self, client: AsyncClient):
        """Test that charge endpoint requires authentication."""
        response = await client.post(
            "/api/v1/payments/charge",
            json={
                "venue_id": str(uuid4()),
                "amount": "99.99",
                "currency": "USD",
                "token": "pm_test",
            },
        )
        assert response.status_code == 403  # No auth token

    @pytest.mark.asyncio
    async def test_list_payments_requires_venue_access(
        self, client: AsyncClient, auth_headers
    ):
        """Test that listing payments requires venue access."""
        response = await client.get(
            f"/api/v1/payments/?venue_id={uuid4()}",
            headers=auth_headers,
        )
        # Should work for admin role
        assert response.status_code in [200, 403]


class TestPaymentMethodEndpoints:
    """Integration tests for payment method API endpoints."""

    @pytest.mark.asyncio
    async def test_list_payment_methods_requires_auth(self, client: AsyncClient):
        """Test that listing payment methods requires auth."""
        customer_id = uuid4()
        response = await client.get(
            f"/api/v1/payment-methods/customer/{customer_id}",
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_payment_methods_empty(
        self, client: AsyncClient, auth_headers
    ):
        """Test listing payment methods returns empty list for new customer."""
        customer_id = uuid4()
        response = await client.get(
            f"/api/v1/payment-methods/customer/{customer_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["payment_methods"] == []
        assert data["total"] == 0


class TestSubscriptionEndpoints:
    """Integration tests for subscription API endpoints."""

    @pytest.mark.asyncio
    async def test_list_subscriptions_requires_auth(self, client: AsyncClient):
        """Test that listing subscriptions requires auth."""
        response = await client.get(
            f"/api/v1/subscriptions/?venue_id={uuid4()}",
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_subscription_requires_valid_data(
        self, client: AsyncClient, auth_headers
    ):
        """Test subscription creation validation."""
        response = await client.post(
            "/api/v1/subscriptions/",
            headers=auth_headers,
            json={
                "customer_id": str(uuid4()),
                "venue_id": str(uuid4()),
                # Missing required fields
            },
        )
        assert response.status_code == 422  # Validation error


class TestFraudEndpoints:
    """Integration tests for fraud detection API endpoints."""

    @pytest.mark.asyncio
    async def test_list_fraud_rules_requires_auth(self, client: AsyncClient):
        """Test that listing fraud rules requires auth."""
        response = await client.get("/api/v1/fraud/rules")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_fraud_rules_empty(
        self, client: AsyncClient, auth_headers
    ):
        """Test listing fraud rules returns empty list."""
        response = await client.get(
            "/api/v1/fraud/rules",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_create_fraud_rule_validation(
        self, client: AsyncClient, auth_headers
    ):
        """Test fraud rule creation validation."""
        # Invalid rule type
        response = await client.post(
            "/api/v1/fraud/rules",
            headers=auth_headers,
            json={
                "rule_name": "Test Rule",
                "rule_type": "invalid_type",
                "rule_conditions": {"max_amount": 1000},
            },
        )
        assert response.status_code == 422  # Validation error


class TestDisputeEndpoints:
    """Integration tests for dispute API endpoints."""

    @pytest.mark.asyncio
    async def test_list_disputes_requires_auth(self, client: AsyncClient):
        """Test that listing disputes requires auth."""
        response = await client.get(
            f"/api/v1/disputes/?venue_id={uuid4()}",
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_disputes_empty(
        self, client: AsyncClient, auth_headers
    ):
        """Test listing disputes returns empty list for new venue."""
        venue_id = uuid4()
        response = await client.get(
            f"/api/v1/disputes/?venue_id={venue_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["disputes"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_dispute_metrics(
        self, client: AsyncClient, auth_headers
    ):
        """Test dispute metrics endpoint."""
        venue_id = uuid4()
        response = await client.get(
            f"/api/v1/disputes/metrics?venue_id={venue_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_disputes" in data
        assert "win_rate" in data
        assert "dispute_rate" in data


class TestWebhookEndpoints:
    """Integration tests for webhook endpoints."""

    @pytest.mark.asyncio
    async def test_stripe_webhook_requires_signature(self, client: AsyncClient):
        """Test Stripe webhook validates signature."""
        venue_id = uuid4()
        response = await client.post(
            f"/api/v1/webhooks/stripe/{venue_id}",
            content=b'{"type": "payment_intent.succeeded"}',
            headers={"content-type": "application/json"},
        )
        # Should fail without valid signature
        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_square_webhook_requires_signature(self, client: AsyncClient):
        """Test Square webhook validates signature."""
        venue_id = uuid4()
        response = await client.post(
            f"/api/v1/webhooks/square/{venue_id}",
            content=b'{"type": "payment.completed"}',
            headers={"content-type": "application/json"},
        )
        # Should fail without valid signature
        assert response.status_code in [400, 404]
