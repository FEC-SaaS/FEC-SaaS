"""
=============================================================================
FILE: __init__.py (API v1 router)
PURPOSE: Aggregates all API v1 endpoint routers into a single router
=============================================================================

This module combines all API endpoint routers for version 1 of the API.
Each router handles a specific domain of functionality.

INCLUDED ROUTERS:
- auth: Core authentication (login, register, tokens, password reset)
- social: Social OAuth (Google, Facebook, Apple Sign-In)
- mfa: Multi-Factor Authentication (TOTP, backup codes)
- users: User management (admin endpoints)
- roles: Role and permission management
- family: Family account linking
- parental: Parental controls
- loyalty: Loyalty program features

=============================================================================
"""

from fastapi import APIRouter

from app.api.v1 import auth, family, loyalty, mfa, parental, roles, social, users

api_router = APIRouter()

# Core auth endpoints
api_router.include_router(auth.router)
api_router.include_router(social.router)
api_router.include_router(mfa.router)

# Admin endpoints
api_router.include_router(users.router)
api_router.include_router(roles.router)

# Industry-leading feature endpoints
api_router.include_router(family.router)
api_router.include_router(parental.router)
api_router.include_router(loyalty.router)

