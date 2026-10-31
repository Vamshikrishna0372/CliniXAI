"""Medical Record Pydantic request and response schemas for Phase 5."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.medical_record import RecordType, RecordSource, RecordStatus, FileMetadata


# ── Request Schemas ────────────────────────────────────────────────────────────

class CreateMedicalRecordRequest(BaseModel):
    """Schema for form fields or JSON submitted for medical record creation."""
    title: str = Field(..., min_length=2, max_length=200, description="Title of the medical record")
    description: Optional[str] = Field(None, max_length=2000)
    clinical_notes: Optional[str] = Field(None, max_length=5000)
    diagnosis: Optional[str] = Field(None, max_length=500)
    treatment_plan: Optional[str] = Field(None, max_length=2000)
    symptoms: Optional[list[str]] = None
    record_type: RecordType = RecordType.CLINICAL_DOCUMENT
    clinical_date: Optional[str] = Field(None, description="Clinical date in YYYY-MM-DD format")
    patient_id: Optional[str] = Field(None, description="Target patient ID (used by Staff/Doctor/Admin)")
    appointment_id: Optional[str] = None
    consultation_id: Optional[str] = None
    department_id: Optional[str] = None

    @field_validator("title", mode="after")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title cannot be empty or whitespace only")
        return v.strip()

    @field_validator("clinical_date", mode="after")
    @classmethod
    def validate_date_fmt(cls, v: Optional[str]) -> Optional[str]:
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("clinical_date must be a valid date in YYYY-MM-DD format")
        return v


class UpdateMedicalRecordRequest(BaseModel):
    """Schema for updating medical record metadata and clinical fields."""
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    clinical_notes: Optional[str] = Field(None, max_length=5000)
    diagnosis: Optional[str] = Field(None, max_length=500)
    treatment_plan: Optional[str] = Field(None, max_length=2000)
    symptoms: Optional[list[str]] = None
    clinical_date: Optional[str] = None

    @field_validator("title", mode="after")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or not v.strip():
                raise ValueError("title cannot be empty or whitespace only")
            return v.strip()
        return v

    @field_validator("clinical_date", mode="after")
    @classmethod
    def validate_date_fmt(cls, v: Optional[str]) -> Optional[str]:
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("clinical_date must be a valid date in YYYY-MM-DD format")
        return v


# ── Response Schemas ───────────────────────────────────────────────────────────

class FileMetadataResponse(BaseModel):
    """Sanitized file metadata response — never exposes internal absolute filesystem paths."""
    original_filename: str
    content_type: str
    size_bytes: int
    checksum: str
    extension: str
    uploaded_at: datetime


class MedicalRecordResponse(BaseModel):
    """Full medical record response model."""
    record_id: str
    patient_id: str
    appointment_id: Optional[str] = None
    consultation_id: Optional[str] = None
    doctor_id: Optional[str] = None
    department_id: Optional[str] = None
    record_type: RecordType
    title: str
    description: Optional[str] = None
    clinical_date: Optional[str] = None
    diagnosis: Optional[str] = None
    clinical_notes: Optional[str] = None
    treatment_plan: Optional[str] = None
    symptoms: Optional[list[str]] = None
    file: Optional[FileMetadataResponse] = None
    uploaded_by: str
    source: RecordSource
    status: RecordStatus
    ai_eligible: bool = False
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, values: Any) -> Any:
        if isinstance(values, dict):
            st = str(values.get("status") or "").lower()
            if st == "completed" or st not in ("active", "archived"):
                values["status"] = "active"
            rt = str(values.get("record_type") or "").lower()
            valid_types = {e.value for e in RecordType}
            if rt not in valid_types:
                values["record_type"] = "clinical_document"
        return values


class MedicalRecordSummaryResponse(BaseModel):
    """Compact record card for list views."""
    record_id: str
    patient_id: str
    appointment_id: Optional[str] = None
    consultation_id: Optional[str] = None
    doctor_id: Optional[str] = None
    record_type: RecordType
    title: str
    clinical_date: Optional[str] = None
    diagnosis: Optional[str] = None
    content_type: str = "text/plain"
    size_bytes: int = 0
    status: RecordStatus
    ai_eligible: bool = False
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, values: Any) -> Any:
        if isinstance(values, dict):
            st = str(values.get("status") or "").lower()
            if st == "completed" or st not in ("active", "archived"):
                values["status"] = "active"
            rt = str(values.get("record_type") or "").lower()
            valid_types = {e.value for e in RecordType}
            if rt not in valid_types:
                values["record_type"] = "clinical_document"
        return values
