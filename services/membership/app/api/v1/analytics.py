"""
=============================================================================
FILE: api/v1/analytics.py
PURPOSE: Membership analytics API endpoints
=============================================================================
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_venue_access
from app.models import (
    CustomerSubscription,
    SubscriptionPlan,
    SubscriptionInvoice,
    CustomerLoyaltyAccount,
    LoyaltyTransaction,
    RewardRedemption,
    ReferralReward,
    SubscriptionStatus,
    InvoiceStatus,
    ReferralStatus,
    LoyaltyTransactionType,
)
from app.schemas.membership import (
    MRRAnalytics,
    ChurnAnalytics,
    LTVAnalytics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# =============================================================================
# SUBSCRIPTION ANALYTICS
# =============================================================================


@router.get("/mrr", response_model=MRRAnalytics)
async def get_mrr_analytics(
    venue_id: UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get Monthly Recurring Revenue analytics."""
    await require_venue_access(current_user, venue_id, "admin")

    # Get all active subscriptions for the venue's plans
    result = await db.execute(
        select(CustomerSubscription, SubscriptionPlan)
        .join(SubscriptionPlan, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(
            and_(
                SubscriptionPlan.venue_id == venue_id,
                CustomerSubscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIAL,
                ]),
            )
        )
    )
    subscriptions = result.all()

    # Calculate current MRR
    current_mrr = Decimal("0")
    subscription_count = 0

    for sub, plan in subscriptions:
        monthly_value = _normalize_to_monthly(plan.price, plan.billing_interval.value)
        current_mrr += monthly_value
        subscription_count += 1

    # Calculate average revenue per subscription
    avg_revenue = current_mrr / subscription_count if subscription_count > 0 else Decimal("0")

    # Get new MRR (new subscriptions this month)
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(CustomerSubscription, SubscriptionPlan)
        .join(SubscriptionPlan, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(
            and_(
                SubscriptionPlan.venue_id == venue_id,
                CustomerSubscription.created_at >= month_start,
            )
        )
    )
    new_subs = result.all()
    new_mrr = sum(
        _normalize_to_monthly(plan.price, plan.billing_interval.value)
        for _, plan in new_subs
    )

    # Get churned MRR (cancelled this month)
    result = await db.execute(
        select(CustomerSubscription, SubscriptionPlan)
        .join(SubscriptionPlan, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(
            and_(
                SubscriptionPlan.venue_id == venue_id,
                CustomerSubscription.cancelled_at >= month_start,
            )
        )
    )
    churned_subs = result.all()
    churned_mrr = sum(
        _normalize_to_monthly(plan.price, plan.billing_interval.value)
        for _, plan in churned_subs
    )

    return {
        "current_mrr": float(current_mrr),
        "new_mrr": float(new_mrr),
        "churned_mrr": float(churned_mrr),
        "net_mrr_change": float(new_mrr - churned_mrr),
        "active_subscriptions": subscription_count,
        "average_revenue_per_subscription": float(avg_revenue),
        "period_start": month_start,
        "period_end": datetime.utcnow(),
    }


@router.get("/churn", response_model=ChurnAnalytics)
async def get_churn_analytics(
    venue_id: UUID,
    period_months: int = Query(default=12, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get churn rate analytics."""
    await require_venue_access(current_user, venue_id, "admin")

    period_start = datetime.utcnow() - timedelta(days=30 * period_months)

    # Get total subscriptions at period start (active before period start and not cancelled before period start)
    result = await db.execute(
        select(func.count(CustomerSubscription.id))
        .join(SubscriptionPlan, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(
            and_(
                SubscriptionPlan.venue_id == venue_id,
                CustomerSubscription.created_at < period_start,
                or_(
                    CustomerSubscription.cancelled_at.is_(None),
                    CustomerSubscription.cancelled_at >= period_start,
                ),
            )
        )
    )
    starting_count = result.scalar() or 0

    # Get churned subscriptions in period
    result = await db.execute(
        select(func.count(CustomerSubscription.id))
        .join(SubscriptionPlan, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(
            and_(
                SubscriptionPlan.venue_id == venue_id,
                CustomerSubscription.cancelled_at >= period_start,
                CustomerSubscription.cancelled_at <= datetime.utcnow(),
            )
        )
    )
    churned_count = result.scalar() or 0

    # Calculate churn rate
    churn_rate = (churned_count / starting_count * 100) if starting_count > 0 else 0

    # Get current active count
    result = await db.execute(
        select(func.count(CustomerSubscription.id))
        .join(SubscriptionPlan, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(
            and_(
                SubscriptionPlan.venue_id == venue_id,
                CustomerSubscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIAL,
                ]),
            )
        )
    )
    current_active = result.scalar() or 0

    # Calculate retention rate
    retention_rate = 100 - churn_rate

    return {
        "churn_rate": round(churn_rate, 2),
        "retention_rate": round(retention_rate, 2),
        "churned_subscriptions": churned_count,
        "starting_subscriptions": starting_count,
        "current_active_subscriptions": current_active,
        "period_months": period_months,
        "period_start": period_start,
        "period_end": datetime.utcnow(),
    }


@router.get("/ltv", response_model=LTVAnalytics)
async def get_ltv_analytics(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get Customer Lifetime Value analytics."""
    await require_venue_access(current_user, venue_id, "admin")

    # Get all invoices for the venue's subscriptions
    result = await db.execute(
        select(SubscriptionInvoice)
        .join(CustomerSubscription, SubscriptionInvoice.subscription_id == CustomerSubscription.id)
        .join(SubscriptionPlan, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(
            and_(
                SubscriptionPlan.venue_id == venue_id,
                SubscriptionInvoice.status == InvoiceStatus.PAID,
            )
        )
    )
    paid_invoices = list(result.scalars().all())

    total_revenue = sum(i.amount for i in paid_invoices)

    # Get unique customers
    result = await db.execute(
        select(func.count(func.distinct(CustomerSubscription.customer_id)))
        .join(SubscriptionPlan, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(SubscriptionPlan.venue_id == venue_id)
    )
    total_customers = result.scalar() or 0

    # Calculate average LTV
    avg_ltv = total_revenue / total_customers if total_customers > 0 else Decimal("0")

    # Get churn rate for projection
    result = await db.execute(
        select(func.count(CustomerSubscription.id))
        .join(SubscriptionPlan, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(
            and_(
                SubscriptionPlan.venue_id == venue_id,
                CustomerSubscription.cancelled_at.isnot(None),
            )
        )
    )
    churned = result.scalar() or 0

    result = await db.execute(
        select(func.count(CustomerSubscription.id))
        .join(SubscriptionPlan, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(SubscriptionPlan.venue_id == venue_id)
    )
    total_subs = result.scalar() or 0

    monthly_churn_rate = (churned / total_subs) if total_subs > 0 else 0.05  # Default 5%

    # Calculate projected LTV using formula: ARPU / Churn Rate
    result = await db.execute(
        select(func.avg(SubscriptionPlan.price))
        .join(CustomerSubscription, CustomerSubscription.plan_id == SubscriptionPlan.id)
        .where(
            and_(
                SubscriptionPlan.venue_id == venue_id,
                CustomerSubscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIAL,
                ]),
            )
        )
    )
    avg_price = result.scalar() or Decimal("0")

    projected_ltv = float(avg_price) / monthly_churn_rate if monthly_churn_rate > 0 else float(avg_price) * 24

    return {
        "average_ltv": float(avg_ltv),
        "projected_ltv": round(projected_ltv, 2),
        "total_revenue": float(total_revenue),
        "total_customers": total_customers,
        "monthly_churn_rate": round(monthly_churn_rate * 100, 2),
        "average_subscription_value": float(avg_price),
    }


# =============================================================================
# LOYALTY ANALYTICS
# =============================================================================


@router.get("/loyalty")
async def get_loyalty_analytics(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get loyalty program analytics."""
    await require_venue_access(current_user, venue_id, "admin")

    from app.models import LoyaltyProgram

    # Get program for venue
    result = await db.execute(
        select(LoyaltyProgram).where(
            and_(
                LoyaltyProgram.venue_id == venue_id,
                LoyaltyProgram.is_active == True,
            )
        )
    )
    program = result.scalar_one_or_none()
    if not program:
        return {"error": "No active loyalty program found"}

    # Get account stats
    result = await db.execute(
        select(
            func.count(CustomerLoyaltyAccount.id).label("total_accounts"),
            func.sum(CustomerLoyaltyAccount.points_balance).label("total_points"),
            func.sum(CustomerLoyaltyAccount.lifetime_points).label("lifetime_points"),
            func.avg(CustomerLoyaltyAccount.points_balance).label("avg_balance"),
        )
        .where(CustomerLoyaltyAccount.program_id == program.id)
    )
    account_stats = result.one()

    # Get transaction stats
    result = await db.execute(
        select(
            LoyaltyTransaction.transaction_type,
            func.count(LoyaltyTransaction.id).label("count"),
            func.sum(func.abs(LoyaltyTransaction.points)).label("total_points"),
        )
        .join(CustomerLoyaltyAccount, LoyaltyTransaction.account_id == CustomerLoyaltyAccount.id)
        .where(CustomerLoyaltyAccount.program_id == program.id)
        .group_by(LoyaltyTransaction.transaction_type)
    )
    transaction_breakdown = {
        row.transaction_type.value: {
            "count": row.count,
            "total_points": row.total_points or 0,
        }
        for row in result
    }

    # Get redemption rate
    earned = transaction_breakdown.get("earned", {}).get("total_points", 0)
    redeemed = transaction_breakdown.get("redeemed", {}).get("total_points", 0)
    redemption_rate = (redeemed / earned * 100) if earned > 0 else 0

    return {
        "program_id": program.id,
        "program_name": program.name,
        "total_members": account_stats.total_accounts or 0,
        "total_points_outstanding": account_stats.total_points or 0,
        "lifetime_points_issued": account_stats.lifetime_points or 0,
        "average_points_balance": float(account_stats.avg_balance or 0),
        "transaction_breakdown": transaction_breakdown,
        "redemption_rate": round(redemption_rate, 2),
    }


# =============================================================================
# REWARDS ANALYTICS
# =============================================================================


@router.get("/rewards")
async def get_rewards_analytics(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get rewards redemption analytics."""
    await require_venue_access(current_user, venue_id, "admin")

    from app.models import RewardsCatalog

    # Get redemption stats
    result = await db.execute(
        select(
            RewardRedemption.status,
            func.count(RewardRedemption.id).label("count"),
            func.sum(RewardRedemption.points_spent).label("total_points"),
            func.sum(RewardRedemption.monetary_value).label("total_value"),
        )
        .join(RewardsCatalog, RewardRedemption.reward_id == RewardsCatalog.id)
        .where(RewardsCatalog.venue_id == venue_id)
        .group_by(RewardRedemption.status)
    )

    status_breakdown = {}
    total_redemptions = 0
    total_points_spent = 0
    total_value_redeemed = Decimal("0")

    for row in result:
        status_breakdown[row.status.value] = {
            "count": row.count,
            "points_spent": row.total_points or 0,
            "monetary_value": float(row.total_value or 0),
        }
        total_redemptions += row.count
        total_points_spent += row.total_points or 0
        if row.total_value:
            total_value_redeemed += row.total_value

    # Get top rewards
    result = await db.execute(
        select(
            RewardsCatalog.name,
            func.count(RewardRedemption.id).label("redemption_count"),
        )
        .join(RewardRedemption, RewardRedemption.reward_id == RewardsCatalog.id)
        .where(RewardsCatalog.venue_id == venue_id)
        .group_by(RewardsCatalog.id, RewardsCatalog.name)
        .order_by(func.count(RewardRedemption.id).desc())
        .limit(10)
    )
    top_rewards = [
        {"name": row.name, "redemption_count": row.redemption_count}
        for row in result
    ]

    return {
        "total_redemptions": total_redemptions,
        "total_points_spent": total_points_spent,
        "total_value_redeemed": float(total_value_redeemed),
        "status_breakdown": status_breakdown,
        "top_rewards": top_rewards,
    }


# =============================================================================
# REFERRAL ANALYTICS
# =============================================================================


@router.get("/referrals")
async def get_referral_analytics(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get referral program analytics."""
    await require_venue_access(current_user, venue_id, "admin")

    # Get referral stats
    result = await db.execute(
        select(
            ReferralReward.status,
            func.count(ReferralReward.id).label("count"),
            func.sum(ReferralReward.referrer_reward_points).label("referrer_points"),
            func.sum(ReferralReward.referred_reward_points).label("referred_points"),
        )
        .where(ReferralReward.venue_id == venue_id)
        .group_by(ReferralReward.status)
    )

    status_breakdown = {}
    total_referrals = 0
    completed_referrals = 0
    total_points_issued = 0

    for row in result:
        status_breakdown[row.status.value] = {
            "count": row.count,
            "referrer_points": row.referrer_points or 0,
            "referred_points": row.referred_points or 0,
        }
        total_referrals += row.count
        if row.status == ReferralStatus.COMPLETED:
            completed_referrals = row.count
            total_points_issued = (row.referrer_points or 0) + (row.referred_points or 0)

    conversion_rate = (completed_referrals / total_referrals * 100) if total_referrals > 0 else 0

    return {
        "total_referrals": total_referrals,
        "completed_referrals": completed_referrals,
        "conversion_rate": round(conversion_rate, 2),
        "total_points_issued": total_points_issued,
        "status_breakdown": status_breakdown,
    }


# =============================================================================
# DASHBOARD SUMMARY
# =============================================================================


@router.get("/dashboard")
async def get_analytics_dashboard(
    venue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a summary dashboard of all membership analytics."""
    await require_venue_access(current_user, venue_id, "admin")

    # Get quick stats
    mrr_data = await get_mrr_analytics(venue_id, None, None, db, current_user)
    churn_data = await get_churn_analytics(venue_id, 12, db, current_user)
    ltv_data = await get_ltv_analytics(venue_id, db, current_user)

    return {
        "mrr": {
            "current": mrr_data["current_mrr"],
            "new": mrr_data["new_mrr"],
            "churned": mrr_data["churned_mrr"],
            "net_change": mrr_data["net_mrr_change"],
        },
        "subscriptions": {
            "active": mrr_data["active_subscriptions"],
            "avg_revenue": mrr_data["average_revenue_per_subscription"],
        },
        "churn": {
            "rate": churn_data["churn_rate"],
            "retention_rate": churn_data["retention_rate"],
        },
        "ltv": {
            "average": ltv_data["average_ltv"],
            "projected": ltv_data["projected_ltv"],
        },
        "generated_at": datetime.utcnow(),
    }


# =============================================================================
# HELPERS
# =============================================================================


def _normalize_to_monthly(price: Decimal, interval: str) -> Decimal:
    """Normalize a price to monthly equivalent."""
    multipliers = {
        "weekly": Decimal("4.33"),
        "monthly": Decimal("1"),
        "quarterly": Decimal("0.33"),
        "semi_annual": Decimal("0.167"),
        "annual": Decimal("0.083"),
    }
    return price * multipliers.get(interval, Decimal("1"))
