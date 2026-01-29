# POS Integration Service - Testing Guide

## Running Tests

Run the full test suite:

```bash
cd services/pos
poetry run pytest
```

Run tests with coverage reporting:

```bash
poetry run pytest --cov=app --cov-report=term-missing
```

Run tests with verbose output:

```bash
poetry run pytest -v
```

Run a specific test file:

```bash
poetry run pytest tests/test_services/test_transaction_service.py
```

Run a specific test by name:

```bash
poetry run pytest -k "test_create_transaction"
```

## Test Structure

```
tests/
  conftest.py                          # Shared fixtures, async DB session, test client
  test_services/
    test_transaction_service.py        # Transaction CRUD and lifecycle tests
    test_payment_service.py            # Payment processing and multi-tender tests
    test_receipt_service.py            # Receipt generation and delivery tests
    test_refund_service.py             # Refund workflow and approval tests
    test_cash_drawer_service.py        # Cash drawer session and event tests
    test_tax_service.py                # Tax rate calculation tests
    test_reconciliation_service.py     # Daily reconciliation tests
    test_integration_service.py        # External POS sync tests
    test_discount_service.py           # Discount engine and rule application tests
    test_shift_service.py              # Shift management and break tracking tests
    test_tip_service.py                # Tip pooling and distribution tests
    test_currency_service.py           # Multi-currency conversion tests
    test_reporting_service.py          # Reporting and analytics tests
    test_fraud_detection_service.py    # Fraud detection and alerting tests
    test_audit_service.py              # Audit logging tests
    test_receipt_template_service.py   # Receipt template management tests
    test_stripe_processor.py           # Stripe payment processor tests
  test_api/
    test_transaction_endpoints.py      # Transaction API endpoint tests
    test_payment_endpoints.py          # Payment API endpoint tests
    test_receipt_endpoints.py          # Receipt API endpoint tests
    test_refund_endpoints.py           # Refund API endpoint tests
    test_cash_drawer_endpoints.py      # Cash drawer API endpoint tests
    test_tax_rate_endpoints.py         # Tax rate API endpoint tests
    test_reconciliation_endpoints.py   # Reconciliation API endpoint tests
    test_integration_endpoints.py      # Integration API endpoint tests
    test_discount_endpoints.py         # Discount API endpoint tests
    test_shift_endpoints.py            # Shift API endpoint tests
    test_tip_pool_endpoints.py         # Tip pool API endpoint tests
    test_currency_endpoints.py         # Currency API endpoint tests
    test_report_endpoints.py           # Reports API endpoint tests
    test_fraud_alert_endpoints.py      # Fraud alert API endpoint tests
    test_audit_log_endpoints.py        # Audit log API endpoint tests
    test_receipt_template_endpoints.py # Receipt template API endpoint tests
    test_webhook_endpoints.py          # Webhook receiver endpoint tests
```

### conftest.py

The `conftest.py` file provides shared fixtures used across all tests:

- `db_session` - Async SQLAlchemy session with automatic rollback
- `test_client` - FastAPI `AsyncClient` for endpoint testing
- `sample_transaction` - Pre-built transaction fixture
- `sample_payment` - Pre-built payment fixture
- `sample_drawer` - Pre-built cash drawer session fixture
- `sample_discount` - Pre-built discount rule fixture
- `sample_shift` - Pre-built shift fixture
- `sample_tip_pool` - Pre-built tip pool fixture
- `sample_currency` - Pre-built currency fixture
- `sample_receipt_template` - Pre-built receipt template fixture
- `sample_fraud_alert` - Pre-built fraud alert fixture
- `sample_audit_log` - Pre-built audit log fixture

## Testing Patterns

### AsyncMock for Async Service Methods

All service layer methods are async. Use `AsyncMock` to mock them in tests:

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_create_transaction(db_session):
    mock_event_publisher = AsyncMock()
    with patch("app.services.event_publisher.publish", mock_event_publisher):
        service = TransactionService(db_session)
        transaction = await service.create(
            venue_id="venue-001",
            terminal_id="terminal-01",
            items=[
                {"product_id": "prod-001", "name": "Lane Rental", "quantity": 1, "unit_price": 35.00},
                {"product_id": "prod-002", "name": "Shoe Rental", "quantity": 2, "unit_price": 5.50},
            ]
        )
        assert transaction.status == "open"
        assert transaction.subtotal == 46.00
        mock_event_publisher.assert_called_once()
```

### MagicMock for Synchronous Dependencies

Use `MagicMock` for synchronous helpers and utilities:

```python
from unittest.mock import MagicMock

def test_tax_calculation():
    mock_cache = MagicMock()
    mock_cache.get.return_value = {"rate": 0.075, "jurisdiction": "FL"}

    tax_service = TaxService(cache=mock_cache)
    result = tax_service.calculate(subtotal=100.00, category="food_beverage")

    assert result.tax_amount == 7.50
    assert result.rate == 0.075
```

## Manual Testing

The following curl examples walk through the key operational flows. All examples assume the service is running at `http://localhost:8014`.

### Flow 1: Create Transaction, Process Payment, Generate Receipt

**Step 1: Create a transaction**

```bash
curl -X POST http://localhost:8014/api/v1/transactions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "venue_id": "venue-001",
    "terminal_id": "terminal-01",
    "customer_id": "cust-042",
    "items": [
      {
        "product_id": "prod-001",
        "name": "Lane Rental - 1 Hour",
        "quantity": 1,
        "unit_price": 35.00,
        "category": "bowling"
      },
      {
        "product_id": "prod-002",
        "name": "Shoe Rental",
        "quantity": 3,
        "unit_price": 5.50,
        "category": "bowling"
      },
      {
        "product_id": "prod-015",
        "name": "Nachos",
        "quantity": 1,
        "unit_price": 9.99,
        "category": "food_beverage"
      }
    ]
  }'
```

**Step 2: Process payment for the transaction**

```bash
curl -X POST http://localhost:8014/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "transaction_id": "<transaction_id_from_step_1>",
    "method": "credit_card",
    "amount": 65.24,
    "card_last_four": "4242",
    "card_brand": "visa"
  }'
```

**Step 3: Generate a receipt**

```bash
curl -X POST http://localhost:8014/api/v1/receipts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "transaction_id": "<transaction_id_from_step_1>",
    "format": "pdf",
    "delivery_method": "email",
    "recipient_email": "customer@example.com"
  }'
```

### Flow 2: Cash Drawer Lifecycle

**Step 1: Open a cash drawer**

```bash
curl -X POST http://localhost:8014/api/v1/cash-drawers/open \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "terminal_id": "terminal-01",
    "opening_balance": 200.00,
    "operator_id": "emp-007"
  }'
```

**Step 2: Record a cash drop**

```bash
curl -X POST http://localhost:8014/api/v1/cash-drawers/<drawer_id>/drop \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "amount": 500.00,
    "note": "Mid-shift safe drop"
  }'
```

**Step 3: Close the drawer**

```bash
curl -X POST http://localhost:8014/api/v1/cash-drawers/<drawer_id>/close \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "closing_count": 247.50,
    "note": "End of shift"
  }'
```

### Flow 3: Daily Reconciliation

**Step 1: Create a reconciliation report**

```bash
curl -X POST http://localhost:8014/api/v1/reconciliation \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "venue_id": "venue-001",
    "date": "2026-01-28",
    "prepared_by": "emp-003"
  }'
```

**Step 2: Complete the reconciliation**

```bash
curl -X POST http://localhost:8014/api/v1/reconciliation/<report_id>/complete \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "reviewed_by": "mgr-001",
    "notes": "All totals balanced within tolerance"
  }'
```

### Flow 4: Refund Workflow

**Step 1: Issue a refund request**

```bash
curl -X POST http://localhost:8014/api/v1/refunds \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "payment_id": "<payment_id>",
    "amount": 9.99,
    "reason": "Customer complaint - food quality",
    "requested_by": "emp-012"
  }'
```

**Step 2: Approve the refund**

```bash
curl -X POST http://localhost:8014/api/v1/refunds/<refund_id>/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "approved_by": "mgr-001",
    "notes": "Approved per customer satisfaction policy"
  }'
```

**Step 3: Process the refund**

```bash
curl -X POST http://localhost:8014/api/v1/refunds/<refund_id>/process \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>"
```

### Flow 5: Shift Management

**Step 1: Start a shift**

```bash
curl -X POST http://localhost:8014/api/v1/shifts/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "venue_id": "venue-001",
    "terminal_id": "terminal-01",
    "employee_id": "emp-007"
  }'
```

**Step 2: Start a break**

```bash
curl -X POST http://localhost:8014/api/v1/shifts/<shift_id>/break/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "break_type": "lunch"
  }'
```

**Step 3: End a break**

```bash
curl -X POST http://localhost:8014/api/v1/shifts/<shift_id>/break/end \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>"
```

**Step 4: End the shift**

```bash
curl -X POST http://localhost:8014/api/v1/shifts/<shift_id>/end \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "notes": "Busy evening shift"
  }'
```

### Flow 6: Discount Application

**Step 1: Create a discount rule**

```bash
curl -X POST http://localhost:8014/api/v1/discounts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "Happy Hour 20% Off",
    "discount_type": "percentage",
    "value": 20.00,
    "applies_to": "food_beverage",
    "start_time": "16:00:00",
    "end_time": "18:00:00",
    "active_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "venue_id": "venue-001"
  }'
```

**Step 2: Apply discount to a transaction**

```bash
curl -X POST http://localhost:8014/api/v1/discounts/<discount_id>/apply \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "transaction_id": "<transaction_id>"
  }'
```

### Flow 7: Tip Pool Distribution

**Step 1: Create a tip pool**

```bash
curl -X POST http://localhost:8014/api/v1/tip-pools \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "venue_id": "venue-001",
    "pool_date": "2026-01-28",
    "distribution_method": "hours_worked",
    "total_tips": 450.00
  }'
```

**Step 2: Distribute tips**

```bash
curl -X POST http://localhost:8014/api/v1/tip-pools/<tip_pool_id>/distribute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "employees": [
      {"employee_id": "emp-007", "hours_worked": 8.0},
      {"employee_id": "emp-008", "hours_worked": 6.5},
      {"employee_id": "emp-009", "hours_worked": 7.0}
    ]
  }'
```

### Flow 8: Currency Conversion

**Step 1: Add a supported currency**

```bash
curl -X POST http://localhost:8014/api/v1/currencies \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "code": "EUR",
    "name": "Euro",
    "symbol": "€",
    "exchange_rate": 0.92,
    "decimal_places": 2
  }'
```

**Step 2: Convert currency**

```bash
curl -X POST http://localhost:8014/api/v1/currencies/convert \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "amount": 100.00,
    "from_currency": "USD",
    "to_currency": "EUR"
  }'
```

### Flow 9: Reporting

**Step 1: Get sales report**

```bash
curl -X GET "http://localhost:8014/api/v1/reports/sales?venue_id=venue-001&start_date=2026-01-01&end_date=2026-01-28" \
  -H "Authorization: Bearer <token>"
```

**Step 2: Get employee performance**

```bash
curl -X GET "http://localhost:8014/api/v1/reports/employee-performance?venue_id=venue-001&start_date=2026-01-01&end_date=2026-01-28" \
  -H "Authorization: Bearer <token>"
```

**Step 3: Get hourly sales breakdown**

```bash
curl -X GET "http://localhost:8014/api/v1/reports/hourly-sales?venue_id=venue-001&date=2026-01-28" \
  -H "Authorization: Bearer <token>"
```

### Flow 10: Fraud Alert Management

**Step 1: List fraud alerts**

```bash
curl -X GET "http://localhost:8014/api/v1/fraud-alerts?venue_id=venue-001&status=pending" \
  -H "Authorization: Bearer <token>"
```

**Step 2: Investigate an alert**

```bash
curl -X POST http://localhost:8014/api/v1/fraud-alerts/<alert_id>/investigate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "investigator_id": "mgr-001",
    "notes": "Reviewing transaction patterns"
  }'
```

**Step 3: Resolve a fraud alert**

```bash
curl -X POST http://localhost:8014/api/v1/fraud-alerts/<alert_id>/resolve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "resolution": "confirmed_fraud",
    "action_taken": "Voided transaction and blocked customer",
    "resolved_by": "mgr-001"
  }'
```

### Flow 11: Receipt Templates

**Step 1: Create a receipt template**

```bash
curl -X POST http://localhost:8014/api/v1/receipt-templates \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "Bowling Receipt",
    "template_type": "thermal",
    "venue_id": "venue-001",
    "header_text": "Welcome to Fun Bowl!",
    "footer_text": "Thank you for bowling with us!",
    "show_logo": true,
    "show_tax_breakdown": true,
    "template_body": "<template content>"
  }'
```

**Step 2: Preview a template**

```bash
curl -X POST http://localhost:8014/api/v1/receipt-templates/<template_id>/preview \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "sample_transaction_id": "<transaction_id>"
  }'
```

### Flow 12: Audit Logs

**Step 1: Query audit logs**

```bash
curl -X GET "http://localhost:8014/api/v1/audit-logs?venue_id=venue-001&action=transaction.created&start_date=2026-01-28T00:00:00Z&end_date=2026-01-28T23:59:59Z" \
  -H "Authorization: Bearer <token>"
```

**Step 2: Get specific audit log**

```bash
curl -X GET http://localhost:8014/api/v1/audit-logs/<audit_log_id> \
  -H "Authorization: Bearer <token>"
```

### Flow 13: Webhook Testing

**Test Stripe webhook (use Stripe CLI for local testing)**

```bash
# Forward webhooks to local server
stripe listen --forward-to localhost:8014/api/v1/webhooks/stripe

# Trigger a test event
stripe trigger payment_intent.succeeded
```

**Test Toast webhook**

```bash
curl -X POST http://localhost:8014/api/v1/webhooks/toast \
  -H "Content-Type: application/json" \
  -H "X-Toast-Signature: <signature>" \
  -d '{
    "eventType": "ORDER_COMPLETED",
    "orderId": "toast-order-123",
    "data": { ... }
  }'
```

**Test Square webhook**

```bash
curl -X POST http://localhost:8014/api/v1/webhooks/square \
  -H "Content-Type: application/json" \
  -H "X-Square-Signature: <signature>" \
  -d '{
    "type": "payment.completed",
    "data": { ... }
  }'
```

**Test Clover webhook**

```bash
curl -X POST http://localhost:8014/api/v1/webhooks/clover \
  -H "Content-Type: application/json" \
  -H "X-Clover-Signature: <signature>" \
  -d '{
    "type": "ORDER_CREATED",
    "data": { ... }
  }'
```
