"""POS Integration API v1 router."""

from fastapi import APIRouter

from app.api.v1.transactions import router as transactions_router
from app.api.v1.payments import router as payments_router
from app.api.v1.receipts import router as receipts_router
from app.api.v1.receipt_templates import router as receipt_templates_router
from app.api.v1.refunds import router as refunds_router
from app.api.v1.cash_drawers import router as cash_drawers_router
from app.api.v1.tax_rates import router as tax_rates_router
from app.api.v1.reconciliation import router as reconciliation_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.reports import router as reports_router
from app.api.v1.discounts import router as discounts_router
from app.api.v1.shifts import router as shifts_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.tip_pools import router as tip_pools_router
from app.api.v1.currencies import router as currencies_router
from app.api.v1.fraud_alerts import router as fraud_alerts_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(transactions_router, tags=["Transactions"])
api_router.include_router(payments_router, tags=["Payments"])
api_router.include_router(receipts_router, tags=["Receipts"])
api_router.include_router(receipt_templates_router, tags=["Receipt Templates"])
api_router.include_router(refunds_router, tags=["Refunds"])
api_router.include_router(cash_drawers_router, tags=["Cash Drawers"])
api_router.include_router(tax_rates_router, tags=["Tax Rates"])
api_router.include_router(reconciliation_router, tags=["Reconciliation"])
api_router.include_router(integrations_router, tags=["External Integrations"])
api_router.include_router(webhooks_router, tags=["Webhooks"])
api_router.include_router(reports_router, tags=["Reports & Analytics"])
api_router.include_router(discounts_router, tags=["Discounts"])
api_router.include_router(shifts_router, tags=["Shifts"])
api_router.include_router(audit_logs_router, tags=["Audit Logs"])
api_router.include_router(tip_pools_router, tags=["Tip Pools"])
api_router.include_router(currencies_router, tags=["Currencies"])
api_router.include_router(fraud_alerts_router, tags=["Fraud Alerts"])
