"""Structured error responses with standardized error codes."""

from enum import Enum
from typing import Any, Optional

from fastapi import HTTPException, status


class ErrorCode(str, Enum):
    """Standardized error codes for the reservation & capacity service."""

    # ─── Reservation errors ──────────────────────────────────────────────
    RESERVATION_NOT_FOUND = "RESERVATION_NOT_FOUND"
    RESERVATION_ALREADY_CANCELLED = "RESERVATION_ALREADY_CANCELLED"
    RESERVATION_INVALID_STATUS_TRANSITION = "RESERVATION_INVALID_STATUS_TRANSITION"
    RESERVATION_PAST_DATE = "RESERVATION_PAST_DATE"
    RESERVATION_TOO_FAR_ADVANCE = "RESERVATION_TOO_FAR_ADVANCE"
    RESERVATION_INSUFFICIENT_ADVANCE = "RESERVATION_INSUFFICIENT_ADVANCE"
    RESERVATION_INVALID_TIME_RANGE = "RESERVATION_INVALID_TIME_RANGE"
    RESERVATION_PARTY_SIZE_EXCEEDED = "RESERVATION_PARTY_SIZE_EXCEEDED"
    RESERVATION_OUTSIDE_BUSINESS_HOURS = "RESERVATION_OUTSIDE_BUSINESS_HOURS"

    # ─── Capacity errors ─────────────────────────────────────────────────
    SLOT_UNAVAILABLE = "SLOT_UNAVAILABLE"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    CAPACITY_CONFIG_NOT_FOUND = "CAPACITY_CONFIG_NOT_FOUND"

    # ─── Hold errors ─────────────────────────────────────────────────────
    HOLD_EXPIRED = "HOLD_EXPIRED"
    HOLD_NOT_FOUND = "HOLD_NOT_FOUND"
    HOLD_ALREADY_RELEASED = "HOLD_ALREADY_RELEASED"

    # ─── Conflict errors ─────────────────────────────────────────────────
    DOUBLE_BOOKING_DETECTED = "DOUBLE_BOOKING_DETECTED"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"

    # ─── Idempotency ─────────────────────────────────────────────────────
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"

    # ─── Rate limiting ───────────────────────────────────────────────────
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # ─── Waitlist errors ─────────────────────────────────────────────────
    WAITLIST_ENTRY_NOT_FOUND = "WAITLIST_ENTRY_NOT_FOUND"
    WAITLIST_ALREADY_CONVERTED = "WAITLIST_ALREADY_CONVERTED"

    # ─── Deposit/Payment errors ──────────────────────────────────────────
    DEPOSIT_REQUIRED = "DEPOSIT_REQUIRED"
    DEPOSIT_COLLECTION_FAILED = "DEPOSIT_COLLECTION_FAILED"
    REFUND_FAILED = "REFUND_FAILED"

    # ─── Recurring reservation errors ────────────────────────────────────
    RECURRING_INVALID_FREQUENCY = "RECURRING_INVALID_FREQUENCY"
    RECURRING_END_BEFORE_START = "RECURRING_END_BEFORE_START"
    RECURRING_MAX_OCCURRENCES_EXCEEDED = "RECURRING_MAX_OCCURRENCES_EXCEEDED"

    # ─── Group reservation errors ────────────────────────────────────────
    GROUP_SIZE_EXCEEDED = "GROUP_SIZE_EXCEEDED"
    GROUP_INSUFFICIENT_RESOURCES = "GROUP_INSUFFICIENT_RESOURCES"

    # ─── Notification errors ─────────────────────────────────────────────
    NOTIFICATION_SEND_FAILED = "NOTIFICATION_SEND_FAILED"

    # ─── General ─────────────────────────────────────────────────────────
    CUSTOMER_NOT_FOUND = "CUSTOMER_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ServiceError(HTTPException):
    """Structured service error that produces a consistent JSON body."""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        detail = {
            "error_code": error_code.value,
            "message": message,
        }
        if details:
            detail["details"] = details
        super().__init__(status_code=status_code, detail=detail)


# ─── Convenience factories ───────────────────────────────────────────────────

def not_found(error_code: ErrorCode, message: str) -> ServiceError:
    return ServiceError(error_code, message, status.HTTP_404_NOT_FOUND)


def conflict(error_code: ErrorCode, message: str, details: Optional[dict] = None) -> ServiceError:
    return ServiceError(error_code, message, status.HTTP_409_CONFLICT, details)


def bad_request(error_code: ErrorCode, message: str, details: Optional[dict] = None) -> ServiceError:
    return ServiceError(error_code, message, status.HTTP_400_BAD_REQUEST, details)


def too_many_requests(message: str = "Rate limit exceeded") -> ServiceError:
    return ServiceError(
        ErrorCode.RATE_LIMIT_EXCEEDED,
        message,
        status.HTTP_429_TOO_MANY_REQUESTS,
    )
