"""Medical Document domain model for CliniXAI."""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

from app.utils.datetime import utc_now


class DocumentCategory(str, Enum):
    """Medical document classification categories."""
    MRI = "MRI"
    CT = "CT"
    XRAY = "X-Ray"
    DERMOSCOPY = "Dermoscopy"
    FUNDUS = "Fundus"
    LAB_REPORT = "Lab Report"
    PRESCRIPTION = "Prescription"
    MEDICAL_PDF = "Medical PDF"
    OTHER = "Other"


class MedicalDocumentInDB(BaseModel):
    """Internal medical document model stored in MongoDB `documents` collection."""

    document_id: str
    patient_id: str
    uploaded_by: str                       # user_id of uploader
    uploaded_by_user_id: Optional[str] = None
    uploaded_by_role: Optional[str] = None # "patient", "doctor", "staff", "hospital_admin"
    uploader_role: Optional[str] = None    # "patient", "doctor", "staff", "hospital_admin"
    uploader_name: Optional[str] = None
    title: str
    category: DocumentCategory = DocumentCategory.OTHER
    modality: Optional[str] = None
    file_name: str
    original_file_name: str
    mime_type: str
    file_size_bytes: int = 0
    storage_path: Optional[str] = None     # Internal path or object key
    notes: Optional[str] = None
    consultation_id: Optional[str] = None
    appointment_id: Optional[str] = None
    medical_record_id: Optional[str] = None
    ai_analysis_id: Optional[str] = None
    ai_analysis_status: Optional[str] = None

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if not d.get("patient_id"):
                d["patient_id"] = "PAT-SYSTEM"
            if not d.get("uploaded_by"):
                d["uploaded_by"] = "system"
            if not d.get("uploaded_by_user_id"):
                d["uploaded_by_user_id"] = d.get("uploaded_by")
            if not d.get("uploaded_by") and d.get("uploaded_by_user_id"):
                d["uploaded_by"] = d.get("uploaded_by_user_id")

            # Clean and normalize uploader role
            raw_role = d.get("uploaded_by_role") or d.get("uploader_role")
            clean_role = None
            if raw_role:
                if hasattr(raw_role, "value"):
                    raw_role = raw_role.value
                r_str = str(raw_role).strip().lower().replace("userrole.", "")
                if "patient" in r_str:
                    clean_role = "patient"
                elif "doctor" in r_str:
                    clean_role = "doctor"
                elif "admin" in r_str:
                    clean_role = "hospital_admin"
                elif "staff" in r_str:
                    clean_role = "staff"
                else:
                    clean_role = r_str

            if clean_role:
                d["uploaded_by_role"] = clean_role
                d["uploader_role"] = clean_role
            if not d.get("file_name"):
                d["file_name"] = d.get("original_file_name") or "document.bin"
            if not d.get("original_file_name"):
                d["original_file_name"] = d.get("file_name") or "document.bin"
            if not d.get("mime_type"):
                d["mime_type"] = "application/octet-stream"
            cat = d.get("category")
            if isinstance(cat, str):
                cat_norm = cat.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
                if cat_norm in ["xray", "chestxray", "cxr"]:
                    d["category"] = DocumentCategory.XRAY
                elif cat_norm in ["mri", "brainmri", "brain", "mriscan"]:
                    d["category"] = DocumentCategory.MRI
                elif cat_norm == "ct":
                    d["category"] = DocumentCategory.CT
                elif cat_norm in ["dermoscopy", "skin"]:
                    d["category"] = DocumentCategory.DERMOSCOPY
                elif cat_norm in ["fundus", "retina", "eye"]:
                    d["category"] = DocumentCategory.FUNDUS
                elif cat_norm in ["labreport", "lab"]:
                    d["category"] = DocumentCategory.LAB_REPORT
                elif cat_norm in ["prescription", "rx"]:
                    d["category"] = DocumentCategory.PRESCRIPTION
                elif cat_norm in ["medicalpdf", "pdf"]:
                    d["category"] = DocumentCategory.MEDICAL_PDF
                elif cat_norm == "other":
                    d["category"] = DocumentCategory.OTHER
            if not d.get("category"):
                d["category"] = DocumentCategory.OTHER
            if not d.get("created_at"):
                d["created_at"] = utc_now()
            if not d.get("updated_at"):
                d["updated_at"] = d.get("created_at") or utc_now()
            return d
        return data

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts document model to dictionary for MongoDB."""
        data = self.model_dump()
        if hasattr(self.category, "value"):
            data["category"] = self.category.value
        return data
