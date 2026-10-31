"""Prescription request and response Pydantic schemas for Phase 15."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator

from app.models.prescription import PrescriptionStatus, FollowUpStatus, Medication, FollowUp


# ── Request Schemas ────────────────────────────────────────────────────────────

class CreatePrescriptionRequest(BaseModel):
    """Schema for Doctor creating a prescription for a consultation."""
    consultation_id: Optional[str] = Field(None, description="Consultation ID (optional when in URL path)")
    medications: Optional[List[Medication]] = Field(None, description="List of medications")
    items: Optional[List[Medication]] = Field(None, description="Alias for medications")
    instructions: Optional[str] = Field(None, max_length=1000, description="Patient-facing administration instructions")
    notes: Optional[str] = Field(None, max_length=1000, description="Doctor confidential clinical notes")
    follow_up: Optional[FollowUp] = None

    @model_validator(mode="after")
    def validate_medications_list(self) -> "CreatePrescriptionRequest":
        # Resolve either medications or items
        meds = self.medications or self.items
        if not meds or len(meds) == 0:
            raise ValueError("At least one medication item is required to issue a prescription.")
        self.medications = meds
        return self


class UpdatePrescriptionRequest(BaseModel):
    """Schema for updating a draft prescription."""
    medications: Optional[List[Medication]] = None
    items: Optional[List[Medication]] = None
    instructions: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = Field(None, max_length=1000)
    follow_up: Optional[FollowUp] = None
    status: Optional[PrescriptionStatus] = None

    @model_validator(mode="after")
    def consolidate_meds(self) -> "UpdatePrescriptionRequest":
        if self.items and not self.medications:
            self.medications = self.items
        return self


class CancelPrescriptionRequest(BaseModel):
    """Schema for cancelling an active prescription."""
    reason: Optional[str] = Field(None, max_length=500, description="Reason for cancellation")
    cancellation_reason: Optional[str] = Field(None, max_length=500, description="Alias for reason")

    def get_reason(self) -> str:
        return (self.cancellation_reason or self.reason or "").strip()


# ── Response Schemas ───────────────────────────────────────────────────────────

class PrescriptionResponse(BaseModel):
    """Full prescription response for Doctor / Staff / Admin view."""
    prescription_id: str
    consultation_id: str
    appointment_id: Optional[str] = None
    patient_id: str
    doctor_id: str
    medical_record_id: Optional[str] = None
    medications: List[Medication]
    instructions: Optional[str] = None
    notes: Optional[str] = None
    follow_up: Optional[FollowUp] = None
    status: PrescriptionStatus
    prescription_date: Optional[str] = None
    issued_at: Optional[datetime] = None
    issued_by: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PatientPrescriptionResponse(BaseModel):
    """Sanitized prescription model returned to Patient (strips private doctor notes & internal IDs)."""
    prescription_id: str
    consultation_id: str
    appointment_id: Optional[str] = None
    doctor_id: str
    medications: List[Medication]
    instructions: Optional[str] = None
    follow_up: Optional[FollowUp] = None
    status: PrescriptionStatus
    prescription_date: Optional[str] = None
    issued_at: Optional[datetime] = None
    issued_by: Optional[str] = None


class FollowUpSummaryResponse(BaseModel):
    """Follow-up entry response for Doctor and Patient follow-up lists."""
    prescription_id: str
    consultation_id: str
    patient_id: str
    doctor_id: str
    follow_up: FollowUp
    issued_at: Optional[datetime] = None

