"""Medical document request and response Pydantic schemas."""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, model_validator
from app.models.document import DocumentCategory
from app.utils.datetime import utc_now


class DocumentMetadataUpdateRequest(BaseModel):
    """Schema for updating document metadata."""
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    category: Optional[DocumentCategory] = None
    modality: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            cat = d.get("category")
            if isinstance(cat, str):
                cat_norm = cat.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
                if cat_norm in ["mri", "brainmri"]:
                    d["category"] = DocumentCategory.MRI
                elif cat_norm in ["xray", "chestxray", "cxr"]:
                    d["category"] = DocumentCategory.XRAY
                elif cat_norm == "ct":
                    d["category"] = DocumentCategory.CT
                elif cat_norm in ["dermoscopy", "skin"]:
                    d["category"] = DocumentCategory.DERMOSCOPY
                elif cat_norm in ["fundus", "retina"]:
                    d["category"] = DocumentCategory.FUNDUS
                elif cat_norm in ["labreport", "lab"]:
                    d["category"] = DocumentCategory.LAB_REPORT
                elif cat_norm in ["prescription", "rx"]:
                    d["category"] = DocumentCategory.PRESCRIPTION
                elif cat_norm in ["medicalpdf", "pdf"]:
                    d["category"] = DocumentCategory.MEDICAL_PDF
                elif cat_norm == "other":
                    d["category"] = DocumentCategory.OTHER
            return d
        return data


class UploaderInfo(BaseModel):
    """Metadata regarding who uploaded the medical document."""
    user_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None


class DocumentResponse(BaseModel):
    """Public response model for a medical document with complete uploader provenance."""
    document_id: str
    patient_id: str
    uploaded_by: str
    uploaded_by_user_id: Optional[str] = None
    uploader_role: Optional[str] = None
    uploader_name: Optional[str] = None
    uploader: Optional[UploaderInfo] = None
    title: str
    category: DocumentCategory
    modality: Optional[str] = None
    file_name: str
    original_file_name: str
    mime_type: str
    file_size_bytes: int
    notes: Optional[str] = None
    consultation_id: Optional[str] = None
    appointment_id: Optional[str] = None
    medical_record_id: Optional[str] = None
    ai_analysis_id: Optional[str] = None
    ai_analysis_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            cat = d.get("category")
            if isinstance(cat, str):
                cat_norm = cat.strip().lower().replace("-", "").replace("_", "")
                if cat_norm in ["xray", "chestxray", "cxr"]:
                    d["category"] = DocumentCategory.XRAY
                elif cat_norm == "mri":
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
            if not d.get("patient_id"):
                d["patient_id"] = "PAT-SYSTEM"
            if not d.get("uploaded_by"):
                d["uploaded_by"] = "system"
            if not d.get("uploaded_by_user_id"):
                d["uploaded_by_user_id"] = d.get("uploaded_by")
            if not d.get("uploader") and (d.get("uploaded_by") or d.get("uploader_name") or d.get("uploader_role")):
                d["uploader"] = {
                    "user_id": d.get("uploaded_by_user_id") or d.get("uploaded_by"),
                    "name": d.get("uploader_name") or "Unknown",
                    "role": d.get("uploader_role") or "unknown",
                }
            if not d.get("file_name"):
                d["file_name"] = d.get("original_file_name") or "document.bin"
            if not d.get("original_file_name"):
                d["original_file_name"] = d.get("file_name") or "document.bin"
            if not d.get("mime_type"):
                d["mime_type"] = "application/octet-stream"
            if not d.get("category"):
                d["category"] = DocumentCategory.OTHER
            if not d.get("updated_at"):
                d["updated_at"] = d.get("created_at") or utc_now()
            return d
        return data


class DocumentListResponse(BaseModel):
    """Paginated list response for medical documents."""
    total: int
    items: List[DocumentResponse]
