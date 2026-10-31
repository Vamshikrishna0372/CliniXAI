"""Appointment request and response Pydantic schemas."""

from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator, model_validator, AliasChoices

from app.models.appointment import (
    AppointmentStatus, AppointmentType, BookingSource,
    CheckInMethod, CheckInData, QueueData, CancellationData
)


# ── Request Schemas ────────────────────────────────────────────────────────────

def _validate_time_fmt(v: str) -> str:
    parts = v.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError("Time must be HH:MM format")
    if not (0 <= int(parts[0]) <= 23) or not (0 <= int(parts[1]) <= 59):
        raise ValueError("Invalid time value")
    return v


class BookAppointmentRequest(BaseModel):
    """Schema for booking an appointment (Patient or Staff/Admin on behalf of patient)."""
    doctor_id: str
    department_id: Optional[str] = None
    appointment_date: date
    start_time: str = Field(
        ...,
        validation_alias=AliasChoices("start_time", "appointment_time", "time"),
        description="HH:MM 24h format",
    )
    reason: Optional[str] = Field(None, max_length=500)
    appointment_type: AppointmentType = AppointmentType.NEW_CONSULTATION
    # Only used when Staff/Admin books on behalf of patient
    patient_id: Optional[str] = None

    @field_validator("start_time", mode="before")
    @classmethod
    def normalize_start_time(cls, v: Any) -> str:
        if isinstance(v, str):
            s = v.strip()
            parts = s.split(":")
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        return str(v)

    @field_validator("start_time", mode="after")
    @classmethod
    def validate_start_time(cls, v: str) -> str:
        return _validate_time_fmt(v)

    @field_validator("appointment_type", mode="before")
    @classmethod
    def normalize_appointment_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            norm = v.strip().lower().replace("-", "_").replace(" ", "_")
            if norm == "new_consultation":
                return AppointmentType.NEW_CONSULTATION
            if norm == "follow_up":
                return AppointmentType.FOLLOW_UP
        return v


class StaffBookAppointmentRequest(BaseModel):
    """Schema for Staff/Admin booking an appointment on behalf of a specific patient."""
    patient_id: str
    doctor_id: str
    department_id: str
    appointment_date: date
    start_time: str = Field(..., description="HH:MM 24h format")
    reason: Optional[str] = Field(None, max_length=500)
    appointment_type: AppointmentType = AppointmentType.NEW_CONSULTATION

    @field_validator("start_time", mode="after")
    @classmethod
    def validate_start_time(cls, v: str) -> str:
        return _validate_time_fmt(v)


class RescheduleAppointmentRequest(BaseModel):
    """Schema for rescheduling an existing appointment."""
    appointment_date: date
    start_time: str = Field(..., description="HH:MM 24h format")
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("start_time", mode="after")
    @classmethod
    def validate_start_time(cls, v: str) -> str:
        return _validate_time_fmt(v)


class CancelAppointmentRequest(BaseModel):
    """Schema for cancelling an appointment."""
    reason: Optional[str] = Field(None, max_length=500)


class CheckInRequest(BaseModel):
    """Schema for checking in a patient."""
    method: CheckInMethod = CheckInMethod.MANUAL


class UpdateAppointmentStatusRequest(BaseModel):
    """Schema for directly updating appointment status (authorized roles only)."""
    status: AppointmentStatus


# ── Response Schemas ───────────────────────────────────────────────────────────

class CheckInDataResponse(BaseModel):
    """Check-in nested response."""
    checked_in_at: Optional[datetime] = None
    checked_in_by: Optional[str] = None
    method: Optional[CheckInMethod] = None


class QueueDataResponse(BaseModel):
    """Queue nested response."""
    token_number: Optional[str] = None
    position: Optional[int] = None
    joined_at: Optional[datetime] = None
    called_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class CancellationDataResponse(BaseModel):
    """Cancellation nested response."""
    cancelled_by: Optional[str] = None
    cancelled_by_role: Optional[str] = None
    reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None


class AppointmentResponse(BaseModel):
    """Full appointment response."""
    appointment_id: str
    patient_id: str
    doctor_id: str
    department_id: str
    appointment_date: str
    start_time: str
    end_time: str
    reason: Optional[str] = None
    appointment_type: AppointmentType = AppointmentType.NEW_CONSULTATION
    status: AppointmentStatus
    booking_source: BookingSource = BookingSource.PATIENT
    check_in: CheckInDataResponse = Field(default_factory=CheckInDataResponse)
    queue: QueueDataResponse = Field(default_factory=QueueDataResponse)
    cancellation: Optional[CancellationDataResponse] = None
    reschedule_history: list = Field(default_factory=list)
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def sync_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "appointment_type" not in data or not data["appointment_type"]:
                data["appointment_type"] = AppointmentType.NEW_CONSULTATION.value
            if "booking_source" not in data or not data["booking_source"]:
                data["booking_source"] = BookingSource.PATIENT.value
            if not data.get("department_id"):
                data["department_id"] = "DEPT-GEN"
            if not data.get("start_time"):
                data["start_time"] = data.get("appointment_time") or "09:00"
            if not data.get("end_time"):
                data["end_time"] = data.get("end_time") or "09:30"
        return data


class AppointmentSummaryResponse(BaseModel):
    """Compact appointment card for list views."""
    appointment_id: str
    patient_id: str
    doctor_id: str
    department_id: str
    appointment_date: str
    start_time: str
    end_time: str
    appointment_type: AppointmentType
    status: AppointmentStatus
    reason: Optional[str] = None
    patient_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sync_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("department_id"):
                data["department_id"] = "DEPT-GEN"
            if not data.get("start_time"):
                data["start_time"] = data.get("appointment_time") or "09:00"
            if not data.get("end_time"):
                data["end_time"] = data.get("end_time") or "09:30"
            if "appointment_type" not in data or not data["appointment_type"]:
                data["appointment_type"] = AppointmentType.NEW_CONSULTATION.value
        return data


class QueueEntryResponse(BaseModel):
    """A single entry in the operational queue view."""
    appointment_id: str
    patient_id: str
    doctor_id: str
    department_id: str
    appointment_date: str
    start_time: str
    token_number: Optional[str] = None
    position: Optional[int] = None
    status: AppointmentStatus
    checked_in_at: Optional[datetime] = None
    called_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def sync_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("department_id"):
                data["department_id"] = "DEPT-GEN"
        return data
