"""Patient request and response Pydantic schemas."""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.patient import (
    PatientStatus, Gender, BloodGroup, EmergencyContact, PatientAddress
)
from app.utils.datetime import utc_now


# ── Request Schemas ────────────────────────────────────────────────────────────

class EmergencyContactSchema(BaseModel):
    """Emergency contact input schema."""
    name: str = Field(..., min_length=2, max_length=100)
    relationship: str = Field(..., min_length=2, max_length=50)
    phone: str = Field(..., min_length=7, max_length=20)


class PatientAddressSchema(BaseModel):
    """Patient address input schema."""
    street: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)


class CreatePatientRequest(BaseModel):
    """Schema for Staff/Admin registering a new patient."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    blood_group: Optional[BloodGroup] = None
    address: Optional[PatientAddressSchema] = None
    emergency_contact: Optional[EmergencyContactSchema] = None
    allergies: List[str] = Field(default_factory=list)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        return str(v).strip().lower() if v else None


class UpdatePatientRequest(BaseModel):
    """Schema for updating patient profile fields (Patient self-update or Staff)."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    blood_group: Optional[BloodGroup] = None
    address: Optional[PatientAddressSchema] = None
    emergency_contact: Optional[EmergencyContactSchema] = None
    allergies: Optional[List[str]] = None


class UpdatePatientStatusRequest(BaseModel):
    """Schema for Admin/Staff activating or deactivating a patient profile."""
    status: PatientStatus


from pydantic import model_validator
from typing import Any

# ── Response Schemas ───────────────────────────────────────────────────────────

def _normalize_patient_name_dict(values: Any) -> Any:
    if isinstance(values, dict):
        fn = values.get("full_name") or ""
        f_name = values.get("first_name")
        l_name = values.get("last_name")
        if fn and not f_name:
            parts = fn.split(" ")
            values["first_name"] = parts[0]
            values["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""
        elif (f_name or l_name) and not fn:
            values["full_name"] = f"{f_name or ''} {l_name or ''}".strip()
        if not values.get("first_name"):
            values["first_name"] = values.get("full_name") or "Patient"
        if values.get("last_name") is None:
            values["last_name"] = ""
        if not values.get("full_name"):
            values["full_name"] = f"{values.get('first_name')} {values.get('last_name')}".strip()
        if not values.get("status"):
            values["status"] = "active"
        if not values.get("created_at"):
            values["created_at"] = utc_now()
        if not values.get("updated_at"):
            values["updated_at"] = values.get("created_at") or utc_now()
        if isinstance(values.get("date_of_birth"), (date, datetime)):
            values["date_of_birth"] = values["date_of_birth"].isoformat()
    return values


class PatientResponse(BaseModel):
    """Full patient profile response."""
    patient_id: str
    user_id: Optional[str] = None
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    full_name: Optional[str] = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[Gender] = None
    blood_group: Optional[BloodGroup] = None
    address: Optional[PatientAddressSchema] = None
    emergency_contact: Optional[EmergencyContactSchema] = None
    allergies: List[str] = Field(default_factory=list)
    status: PatientStatus = PatientStatus.ACTIVE
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def fill_name_defaults(cls, values: Any) -> Any:
        return _normalize_patient_name_dict(values)


class PatientSummaryResponse(BaseModel):
    """Compact patient card for list views."""
    patient_id: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    full_name: Optional[str] = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[Gender] = None
    date_of_birth: Optional[str] = None
    blood_group: Optional[BloodGroup] = None
    allergies: List[str] = Field(default_factory=list)
    address: Optional[PatientAddressSchema] = None
    status: PatientStatus = PatientStatus.ACTIVE
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def fill_name_defaults(cls, values: Any) -> Any:
        return _normalize_patient_name_dict(values)
