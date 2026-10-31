"""
AI Analysis domain models for CliniXAI Multi-Model Architecture.

Clinical Decision Support (CDS) data architecture for storing multi-model AI predictions,
Grad-CAM explainability artifacts, Doctor reviews, and Patient-safe reports.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, model_validator

from app.utils.datetime import utc_now

CLINICAL_SAFETY_DISCLAIMER = (
    "CliniXAI AI analysis is intended for clinical decision support only. "
    "AI-generated results must be interpreted by a qualified healthcare professional "
    "and must not be used as an independent diagnosis."
)


class AIAnalysisStatus(str, Enum):
    """Lifecycle status values for AI analysis."""
    PENDING = "pending"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    REVIEWED = "reviewed"
    FAILED = "failed"
    MODEL_UNAVAILABLE = "model_unavailable"


class DoctorReviewDecision(str, Enum):
    """Doctor review decision enum for clinical AI evaluations."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_FURTHER_REVIEW = "needs_further_review"
    ACCEPTED_AS_SUPPORTING = "accepted_as_supporting_information"
    NOT_CLINICALLY_RELEVANT = "not_clinically_relevant"


class ModelInfo(BaseModel):
    """Model provenance and identity information attached to every AI analysis."""
    module_id: str = "CHEST_XRAY"
    name: str = "Chest X-Ray Analysis"
    version: str = "1.0.0"
    architecture: str = "ResNet50"
    input_size: List[int] = Field(default_factory=lambda: [224, 224])
    preprocessing: str = "resnet50"
    classification_mode: str = "multiclass"


class InputInfo(BaseModel):
    """Input medical record or document reference."""
    medical_record_id: Optional[str] = None
    document_id: Optional[str] = None
    record_type: str
    content_type: str
    checksum: Optional[str] = None


class PredictionResult(BaseModel):
    """Raw model prediction output."""
    predicted_class: str
    confidence: float
    class_probabilities: Dict[str, float] = Field(default_factory=dict)
    decision_threshold: Optional[float] = 0.5
    low_confidence: bool = False


class ExplainabilityInfo(BaseModel):
    """Grad-CAM Explainable AI (XAI) metadata."""
    method: str = "grad_cam"
    target_layer: str = "conv5_block3_out"
    target_class: Optional[str] = None
    artifact_storage_key: Optional[str] = None


class DoctorReview(BaseModel):
    """Human clinician review record."""
    decision: DoctorReviewDecision
    clinical_interpretation: str
    notes: Optional[str] = None
    reviewed_by: str                    # Doctor User ID or Doctor ID
    reviewed_at: datetime = Field(default_factory=utc_now)


class PatientSafeReport(BaseModel):
    """Patient-safe representation of reviewed AI analysis."""
    report_date: datetime = Field(default_factory=utc_now)
    doctor_name: Optional[str] = None
    status: str = "reviewed"
    result_summary: str
    model_confidence: Optional[float] = None
    doctor_interpretation: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER


class AIAnalysisInDB(BaseModel):
    """Complete MongoDB document model for collection 'ai_analyses'."""
    analysis_id: str
    patient_id: str
    doctor_id: str
    appointment_id: Optional[str] = None
    consultation_id: Optional[str] = None
    medical_record_id: Optional[str] = None
    document_id: Optional[str] = None

    model: ModelInfo = Field(default_factory=ModelInfo)
    input: Optional[InputInfo] = None
    prediction: Optional[PredictionResult] = None
    explainability: Optional[ExplainabilityInfo] = None
    doctor_review: Optional[DoctorReview] = None
    patient_report: Optional[PatientSafeReport] = None

    status: AIAnalysisStatus = AIAnalysisStatus.PENDING
    is_released_to_patient: bool = False
    released_at: Optional[datetime] = None
    error_message: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER

    @model_validator(mode="before")
    @classmethod
    def populate_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            st = data.get("status")
            if (st == "reviewed" or st == AIAnalysisStatus.REVIEWED or getattr(st, "value", None) == "reviewed") and "is_released_to_patient" not in data:
                data["is_released_to_patient"] = True
        return data

    requested_by: str                   # User ID of requester (Doctor)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for MongoDB persistence."""
        d = self.model_dump()
        if "status" in d and hasattr(d["status"], "value"):
            d["status"] = d["status"].value
        elif "status" in d and isinstance(d["status"], AIAnalysisStatus):
            d["status"] = str(d["status"].value)
        elif "status" in d:
            d["status"] = str(d["status"])
        return d
