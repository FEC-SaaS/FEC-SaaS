"""Customer Service database models."""

from app.models.base import Base
from app.models.customer import (
    Customer,
    CustomerFamily,
    CustomerFamilyMember,
    CustomerVisit,
    CustomerActivity,
    CustomerSegment,
    CustomerLTV,
    CustomerChurnRisk,
    CustomerPreference,
    CustomerNextVisitPrediction,
    CustomerType,
    SegmentType,
    RiskLevel,
    ActivityType,
    RelationshipType,
)

__all__ = [
    "Base",
    "Customer",
    "CustomerFamily",
    "CustomerFamilyMember",
    "CustomerVisit",
    "CustomerActivity",
    "CustomerSegment",
    "CustomerLTV",
    "CustomerChurnRisk",
    "CustomerPreference",
    "CustomerNextVisitPrediction",
    "CustomerType",
    "SegmentType",
    "RiskLevel",
    "ActivityType",
    "RelationshipType",
]
