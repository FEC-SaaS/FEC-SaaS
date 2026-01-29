"""Restaurant API v1 router."""

from fastapi import APIRouter

from app.api.v1.tables import router as tables_router
from app.api.v1.reservations import router as reservations_router
from app.api.v1.menu import router as menu_router
from app.api.v1.orders import router as orders_router
from app.api.v1.kds import router as kds_router
from app.api.v1.bar import router as bar_router
from app.api.v1.waste import router as waste_router
from app.api.v1.digital_menu import router as digital_menu_router
from app.api.v1.tax_config import router as tax_config_router

api_router = APIRouter(prefix="/api/v1/restaurant")

api_router.include_router(tables_router, tags=["Tables & Sections"])
api_router.include_router(reservations_router, tags=["Reservations"])
api_router.include_router(menu_router, tags=["Menu"])
api_router.include_router(orders_router, tags=["Orders"])
api_router.include_router(kds_router, tags=["KDS"])
api_router.include_router(bar_router, tags=["Bar"])
api_router.include_router(waste_router, tags=["Waste"])
api_router.include_router(digital_menu_router, tags=["Digital Menu"])
api_router.include_router(tax_config_router, tags=["Tax Configuration"])
