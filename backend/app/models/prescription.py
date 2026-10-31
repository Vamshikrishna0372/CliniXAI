"""Prescription & Medication domain model for CliniXAI Phase 15."""

import re
from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

from app.utils.datetime import utc_now


class PrescriptionStatus(str, Enum):
    """Prescription lifecycle status."""
    ACTIVE = "active"
    ISSUED = "issued"  # Backward-compatible alias for ACTIVE
    CANCELLED = "cancelled"
    DRAFT = "draft"


class MedicationRoute(str, Enum):
    """Medication administration route."""
    ORAL = "Oral"
    TOPICAL = "Topical"
    INHALATION = "Inhalation"
    SUBCUTANEOUS = "Subcutaneous"
    INTRAMUSCULAR = "Intramuscular"
    INTRAVENOUS = "Intravenous"
    OTHER = "Other"


VALID_ROUTES = {
    "oral", "topical", "inhalation", "subcutaneous", "intramuscular",
    "intravenous", "other", "sublingual", "rectal", "ophthalmic", "nasal", "otic"
}

VALID_DOSAGE_UNITS = {
    "mg", "g", "mcg", "ml", "l", "tablet", "tablets", "capsule", "capsules",
    "drop", "drops", "puff", "puffs", "patch", "patches", "unit", "units",
    "ampule", "ampules", "vial", "vials", "tsp", "tbsp", "application", "applications"
}

VALID_DURATION_UNITS = {
    "day", "days", "week", "weeks", "month", "months", "hour", "hours", "dose", "doses"
}


class Medication(BaseModel):
    """Single medication prescription entry with clinical validations."""
    name: str = Field(..., min_length=1, max_length=200, description="Medication name e.g. 'Paracetamol 500mg'")
    generic_name: Optional[str] = Field(None, max_length=200, description="Generic drug name")
    strength: Optional[str] = Field(None, max_length=50, description="Strength e.g. '500 mg'")
    dosage: str = Field(..., min_length=1, max_length=100, description="Dosage e.g. '1 tablet' or '500mg'")
    dosage_unit: Optional[str] = Field(None, max_length=50, description="Dosage unit e.g. 'mg', 'tablet'")
    frequency: str = Field(..., min_length=1, max_length=100, description="Frequency e.g. 'Twice daily'")
    route: Optional[str] = Field(None, max_length=50, description="Route e.g. 'Oral'")
    duration: str = Field(..., min_length=1, max_length=100, description="Duration e.g. '5 days'")
    duration_unit: Optional[str] = Field(None, max_length=50, description="Duration unit e.g. 'days'")
    quantity: Optional[str] = Field(None, max_length=50, description="Total quantity e.g. '10'")
    timing: Optional[str] = Field(None, max_length=100, description="Timing e.g. 'After food'")
    instructions: Optional[str] = Field(None, max_length=500, description="Special administration instructions")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("Medicine name cannot be empty.")
        if re.search(r"<\s*script", v_clean, re.IGNORECASE) or re.search(r"javascript:", v_clean, re.IGNORECASE) or re.search(r"<\s*img[^>]+onerror", v_clean, re.IGNORECASE):
            raise ValueError("Script or JavaScript injection detected in medicine name.")
        return v_clean

    @field_validator("dosage")
    @classmethod
    def validate_dosage(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("Dosage cannot be empty.")
        if re.match(r"^-\s*\d+", v_clean):
            raise ValueError("Dosage cannot be negative.")
        if re.match(r"^(0+(\.0+)?(\s*(mg|ml|g|mcg|tablets?|capsules?|drops?|pills?|units?))?)$", v_clean, re.IGNORECASE):
            raise ValueError("Dosage must be positive and non-zero.")
        if re.search(r"<\s*script", v_clean, re.IGNORECASE) or re.search(r"javascript:", v_clean, re.IGNORECASE):
            raise ValueError("XSS injection detected in dosage.")
        return v_clean

    @field_validator("dosage_unit")
    @classmethod
    def validate_dosage_unit(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_clean = v.strip()
        if not v_clean or v_clean.lower() not in VALID_DOSAGE_UNITS:
            raise ValueError(f"Invalid dosage unit '{v}'. Allowed units include mg, ml, g, tablet, capsule, drops, units.")
        return v_clean

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("Frequency cannot be empty.")
        if re.search(r"<\s*script", v_clean, re.IGNORECASE) or re.search(r"javascript:", v_clean, re.IGNORECASE):
            raise ValueError("XSS injection detected in frequency.")
        return v_clean

    @field_validator("route")
    @classmethod
    def validate_route(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_clean = v.strip()
        if not v_clean or v_clean.lower() not in VALID_ROUTES:
            raise ValueError(f"Invalid administration route '{v}'. Allowed routes: {', '.join(sorted(VALID_ROUTES))}.")
        return v_clean.capitalize()

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("Duration cannot be empty.")
        if re.match(r"^-\s*\d+", v_clean):
            raise ValueError("Duration cannot be negative.")
        if re.match(r"^(0+(\.0+)?(\s*(days?|weeks?|months?|hours?|d|w|m|h))?)$", v_clean, re.IGNORECASE):
            raise ValueError("Duration must be greater than zero.")
        if re.search(r"<\s*script", v_clean, re.IGNORECASE) or re.search(r"javascript:", v_clean, re.IGNORECASE):
            raise ValueError("XSS injection detected in duration.")
        return v_clean

    @field_validator("duration_unit")
    @classmethod
    def validate_duration_unit(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_clean = v.strip()
        if not v_clean or v_clean.lower() not in VALID_DURATION_UNITS:
            raise ValueError(f"Invalid duration unit '{v}'. Allowed units: days, weeks, months, hours, doses.")
        return v_clean.lower()

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_clean = v.strip()
        if re.match(r"^-\s*\d+", v_clean):
            raise ValueError("Quantity cannot be negative.")
        if re.match(r"^0+(\s*.*)?$", v_clean):
            raise ValueError("Quantity must be greater than zero.")
        return v_clean

    @field_validator("instructions")
    @classmethod
    def validate_instructions(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_clean = v.strip()
        if re.search(r"<\s*script", v_clean, re.IGNORECASE) or re.search(r"javascript:", v_clean, re.IGNORECASE) or re.search(r"<\s*img[^>]+onerror", v_clean, re.IGNORECASE):
            raise ValueError("XSS injection detected in instructions.")
        return v_clean


class FollowUpStatus(str, Enum):
    """Follow-up operational status."""
    UPCOMING = "upcoming"
    OVERDUE = "overdue"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FollowUp(BaseModel):
    """Embedded follow-up metadata inside prescription."""
    required: bool = False
    follow_up_date: Optional[str] = Field(None, description="ISO date 'YYYY-MM-DD'")
    interval: Optional[str] = Field(None, description="e.g. '1 week', '2 months'")
    reason: Optional[str] = Field(None, max_length=300)
    notes: Optional[str] = Field(None, max_length=500)
    status: FollowUpStatus = FollowUpStatus.UPCOMING


class PrescriptionInDB(BaseModel):
    """Internal prescription document model stored in MongoDB `prescriptions` collection."""

    prescription_id: str
    consultation_id: str
    appointment_id: Optional[str] = None
    patient_id: str
    doctor_id: str
    medical_record_id: Optional[str] = None

    medications: List[Medication] = Field(default_factory=list)
    instructions: Optional[str] = None
    notes: Optional[str] = None  # Doctor confidential clinical notes (hidden from patient)
    follow_up: Optional[FollowUp] = None
    status: PrescriptionStatus = PrescriptionStatus.ACTIVE
    prescription_date: Optional[str] = None
    issued_at: Optional[datetime] = Field(default_factory=utc_now)
    issued_by: Optional[str] = None

    # Authorship & Cancellation audit trails
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts prescription instance to MongoDB-ready dictionary."""
        return self.model_dump()

