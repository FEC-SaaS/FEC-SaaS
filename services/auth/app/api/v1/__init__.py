from fastapi import APIRouter

from app.api.v1 import auth, family, loyalty, parental, roles, social, users

api_router = APIRouter()

# Core auth endpoints
api_router.include_router(auth.router)
api_router.include_router(social.router)

# Admin endpoints
api_router.include_router(users.router)
api_router.include_router(roles.router)

# Industry-leading feature endpoints
api_router.include_router(family.router)
api_router.include_router(parental.router)
api_router.include_router(loyalty.router)

