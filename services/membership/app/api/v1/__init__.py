"""API v1 package."""

from fastapi import APIRouter

from app.api.v1.subscriptions import router as subscriptions_router
from app.api.v1.loyalty import router as loyalty_router
from app.api.v1.rewards import router as rewards_router
from app.api.v1.family import router as family_router
from app.api.v1.corporate import router as corporate_router
from app.api.v1.referrals import router as referrals_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.tiers import router as tiers_router

api_router = APIRouter()

api_router.include_router(subscriptions_router)
api_router.include_router(loyalty_router)
api_router.include_router(rewards_router)
api_router.include_router(family_router)
api_router.include_router(corporate_router)
api_router.include_router(referrals_router)
api_router.include_router(analytics_router)
api_router.include_router(tiers_router)
