"""Medical Record domain model for CliniXAI Phase 5."""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.utils.datetime import utc_now


class RecordType(str, Enum):
    """Categorical types for medical records."""
    MEDICAL_IMAGE = "medical_image"
    LAB_REPORT = "lab_report"
    RADIOLOGY_REPORT = "radiology_report"
    PRESCRIPTION_DOCUMENT = "prescription_document"
    DISCHARGE_SUMMARY = "discharge_summary"
    CLINICAL_DOCUMENT = "clinical_document"
    CONSULTATION = "consultation"
    DIAGNOSIS = "diagnosis"
    CLINICAL_NOTE = "clinical_note"
    LAB_RESULT = "lab_result"
    FOLLOW_UP = "follow_up"
    OTHER = "other"


class RecordSource(str, Enum):
    """Origin source of the record."""
    PATIENT = "patient"
    DOCTOR = "doctor"
    HOSPITAL_STAFF = "hospital_staff"
    HOSPITAL = "hospital"
    SYSTEM = "system"


class RecordStatus(str, Enum):
    """Operational status of the medical record."""
    ACTIVE = "active"
    ARCHIVED = "archived"


class FileMetadata(BaseModel):
    """Embedded metadata for an uploaded file."""
    storage_key: str                      # Unique generated un-guessable storage filename
    original_filename: str                # Preserved original filename
    content_type: str                     # Validated MIME type e.g. "application/pdf"
    size_bytes: int                       # File size in bytes
    checksum: str                         # Cryptographic SHA-256 hash
    extension: str                        # File extension e.g. ".pdf"
    storage_provider: str = "local"       # "local", "s3", etc.
    uploaded_at: datetime = Field(default_factory=utc_now)


class MedicalRecordInDB(BaseModel):
    """Internal medical record document stored in MongoDB `medical_records` collection."""

    record_id: str
    patient_id: str
    appointment_id: Optional[str] = None
    consultation_id: Optional[str] = None
    doctor_id: Optional[str] = None
    department_id: Optional[str] = None

    record_type: RecordType = RecordType.OTHER
    title: str
    description: Optional[str] = None
    clinical_date: Optional[str] = None    # "YYYY-MM-DD"

    # Clinical fields
    diagnosis: Optional[str] = None
    clinical_notes: Optional[str] = None
    treatment_plan: Optional[str] = None
    symptoms: Optional[list[str]] = None

    file: Optional[FileMetadata] = None
    uploaded_by: str                       # user_id of uploader
    source: RecordSource = RecordSource.PATIENT
    status: RecordStatus = RecordStatus.ACTIVE

    document_id: Optional[str] = None       # Linked medical document if applicable
    ai_eligible: bool = False              # True if medical_image and valid decodable format

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts record instance to MongoDB-ready dictionary."""
        return self.model_dump()
