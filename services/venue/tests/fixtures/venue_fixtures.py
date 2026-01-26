"""
=============================================================================
FILE: tests/fixtures/venue_fixtures.py
PURPOSE: Reusable test fixtures for venue service
=============================================================================
"""

import uuid
from datetime import datetime, date, time
from typing import Dict, Any, List

from app.models.venue import (
    SubscriptionTier,
    VenueStatus,
    OnboardingStatus,
    SettingType,
    ContactType,
    ImageType,
    AIStrategy,
)


def create_venue_data(
    name: str = "Test FEC",
    subscription_tier: str = "pro",
    **overrides: Any,
) -> Dict[str, Any]:
    """Create venue data dictionary for tests."""
    data = {
        "name": name,
        "legal_name": f"{name} LLC",
        "description": f"A test venue for {name}",
        "address_line1": "123 Test Street",
        "address_line2": "Suite 100",
        "city": "Dallas",
        "state": "Texas",
        "postal_code": "75001",
        "country": "USA",
        "latitude": 32.7767,
        "longitude": -96.7970,
        "timezone": "America/Chicago",
        "phone": "+1-214-555-0100",
        "email": f"{name.lower().replace(' ', '')}@test.com",
        "website": f"https://{name.lower().replace(' ', '')}.com",
        "subscription_tier": subscription_tier,
        "total_capacity": 500,
        "square_footage": 25000,
    }
    data.update(overrides)
    return data


def create_hours_data(
    include_weekend: bool = True,
    closed_day: int = None,
) -> List[Dict[str, Any]]:
    """Create venue hours data for a week."""
    hours = []
    for day in range(7):
        if day == closed_day:
            hours.append({"day_of_week": day, "is_closed": True})
        elif day == 0 and not include_weekend:  # Sunday
            hours.append({"day_of_week": day, "is_closed": True})
        elif day in [0, 6]:  # Weekend
            hours.append({
                "day_of_week": day,
                "open_time": "09:00:00",
                "close_time": "23:00:00",
            })
        else:  # Weekday
            hours.append({
                "day_of_week": day,
                "open_time": "10:00:00",
                "close_time": "21:00:00",
            })
    return hours


def create_special_hours_data(
    special_date: str = None,
    name: str = "Holiday",
    is_closed: bool = False,
    **overrides: Any,
) -> Dict[str, Any]:
    """Create special hours data."""
    data = {
        "date": special_date or str(date.today()),
        "name": name,
        "is_closed": is_closed,
    }
    if not is_closed:
        data.update({
            "open_time": "12:00:00",
            "close_time": "18:00:00",
        })
    data.update(overrides)
    return data


def create_setting_data(
    key: str = "test_setting",
    value: str = "test_value",
    setting_type: str = "string",
    **overrides: Any,
) -> Dict[str, Any]:
    """Create venue setting data."""
    data = {
        "setting_key": key,
        "setting_value": value,
        "setting_type": setting_type,
        "description": f"Test setting for {key}",
        "category": "test",
        "is_sensitive": False,
    }
    data.update(overrides)
    return data


def create_feature_data(
    feature_name: str = "bowling",
    enabled: bool = True,
    config: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Create venue feature data."""
    return {
        "enabled": enabled,
        "config": config or {},
    }


def create_ai_config_data(
    service_name: str = "dynamic_pricing",
    strategy: str = "moderate",
    params: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Create AI config data."""
    return {
        "parameters": params or {
            "min_price_multiplier": 0.8,
            "max_price_multiplier": 1.5,
        }
    }


def create_performance_data(
    performance_date: str = None,
    revenue: float = 15000.00,
    guest_count: int = 333,
    **overrides: Any,
) -> Dict[str, Any]:
    """Create performance data."""
    data = {
        "date": performance_date or str(date.today()),
        "revenue": revenue,
        "revenue_per_guest": revenue / guest_count if guest_count > 0 else 0,
        "transaction_count": guest_count,
        "average_transaction": revenue / guest_count if guest_count > 0 else 0,
        "guest_count": guest_count,
        "new_customers": int(guest_count * 0.15),
        "returning_customers": int(guest_count * 0.85),
        "party_bookings": 5,
        "labor_hours": 120.0,
        "labor_cost": 2400.0,
        "labor_cost_percentage": 16.0,
        "nps_score": 72.0,
        "review_count": 15,
        "average_rating": 4.5,
        "peak_occupancy": 350,
        "capacity_utilization": 70.0,
    }
    data.update(overrides)
    return data


def create_contact_data(
    contact_type: str = "manager",
    name: str = "John Smith",
    **overrides: Any,
) -> Dict[str, Any]:
    """Create venue contact data."""
    data = {
        "contact_type": contact_type,
        "name": name,
        "title": "General Manager",
        "email": f"{name.lower().replace(' ', '.')}@test.com",
        "phone": "+1-214-555-0101",
        "is_primary": True,
    }
    data.update(overrides)
    return data


# Sample data collections for bulk testing
SAMPLE_VENUES = [
    create_venue_data("Dallas FEC", subscription_tier="enterprise"),
    create_venue_data("Houston FEC", subscription_tier="pro"),
    create_venue_data("Austin FEC", subscription_tier="starter"),
]

SAMPLE_FEATURES = [
    "bowling",
    "arcade",
    "food_beverage",
    "parties",
    "laser_tag",
]

SAMPLE_AI_SERVICES = [
    "dynamic_pricing",
    "smart_staff",
    "churn_prediction",
]
