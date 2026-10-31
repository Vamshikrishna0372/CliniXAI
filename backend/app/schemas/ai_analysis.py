"""
Pydantic request and response schemas for AI Analyses & Multi-Model Registry.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator

from app.models.ai_analysis import (
    AIAnalysisStatus, DoctorReviewDecision, ModelInfo,
    PredictionResult, ExplainabilityInfo, DoctorReview,
    PatientSafeReport, CLINICAL_SAFETY_DISCLAIMER
)


class AIAnalysisCreateRequest(BaseModel):
    """Payload for triggering an AI analysis on a medical record or existing document."""
    medical_record_id: Optional[str] = Field(None, description="ID of the medical record image to analyze")
    document_id: Optional[str] = Field(None, description="ID of an existing medical document/image to analyze directly")
    patient_id: Optional[str] = Field(None, description="Optional patient ID to validate ownership against")
    appointment_id: Optional[str] = Field(None, description="Optional linked appointment ID")
    analysis_type: Optional[str] = Field(None, description="Optional medical AI module: CHEST_XRAY, BRAIN_MRI, SKIN_DERMOSCOPY, RETINAL_FUNDUS, BONE_XRAY (defaults to CHEST_XRAY or auto-detect)")
    consultation_id: Optional[str] = Field(None, description="Optional linked consultation ID")
    force_new: Optional[bool] = Field(False, description="Whether to bypass reuse and run a fresh analysis")

    @model_validator(mode="after")
    def check_source_id(self):
        if not self.medical_record_id and not self.document_id:
            raise ValueError("Either medical_record_id or document_id must be provided.")
        return self


class AIReviewRequest(BaseModel):
    """Payload for Doctor review of an AI analysis."""
    decision: DoctorReviewDecision
    clinical_interpretation: str = Field(..., min_length=5, description="Clinician's diagnostic assessment and interpretation")
    notes: Optional[str] = Field(None, description="Optional additional review notes")
    release_to_patient: Optional[bool] = Field(False, description="Whether to explicitly release the reviewed result to the patient")


class AIModuleInfoResponse(BaseModel):
    """Public/protected information about a registered medical AI module."""
    module_id: str
    slug: str
    display_name: str
    modality: str
    architecture: str
    classification_mode: str
    enabled: bool
    model_loaded: bool
    status: str
    version: str
    description: str
    supported_classes: Optional[List[str]] = None
    input_shape: Optional[List[int]] = None
    preprocessing: Optional[str] = None


class AIHealthResponse(BaseModel):
    """Safe public/protected health status for AI subsystem."""
    status: str
    ai_enabled: bool
    model_loaded: bool
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    architecture: Optional[str] = None
    target_layer: Optional[str] = None
    modules: Optional[Dict[str, Dict[str, Any]]] = None
    message: str


class AIAnalysisDoctorResponse(BaseModel):
    """Detailed AI Analysis response for authorized Doctor view."""
    analysis_id: str
    patient_id: str
    doctor_id: str
    appointment_id: Optional[str] = None
    consultation_id: Optional[str] = None
    medical_record_id: Optional[str] = None
    document_id: Optional[str] = None

    model: ModelInfo
    prediction: Optional[PredictionResult] = None
    explainability: Optional[ExplainabilityInfo] = None
    doctor_review: Optional[DoctorReview] = None
    patient_report: Optional[PatientSafeReport] = None

    status: AIAnalysisStatus
    is_released_to_patient: bool = False
    released_at: Optional[datetime] = None
    error_message: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER

    requested_by: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AIAnalysisPatientReportResponse(BaseModel):
    """Patient-safe AI Analysis report response."""
    analysis_id: str
    patient_id: str
    medical_record_id: Optional[str] = None
    document_id: Optional[str] = None
    status: str
    report: PatientSafeReport
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER


class AIAnalysisListResponse(BaseModel):
    """Paginated list response of AI Analyses."""
    items: List[AIAnalysisDoctorResponse]
    total: int
    page: int
    page_size: int


class AIInsightsResponse(BaseModel):
    """Hospital Admin aggregate AI insights response."""
    total_analyses: int
    by_status: Dict[str, int]
    by_model_version: Dict[str, int]
    reviewed_count: int
    awaiting_review_count: int
    failed_count: int
    message: str = "Aggregated AI utilization operational metrics"


class AIDirectInferResponse(BaseModel):
    """
    Response for stateless POST /ai/infer — direct image upload without a DB medical record.

    Returns the full inference result including prediction, confidence, per-class probabilities,
    and a base64-encoded Grad-CAM PNG overlay ready to render in the browser.
    """
    analysis_id: Optional[str] = None
    module_id: str
    display_name: str
    architecture: str
    model_version: str

    predicted_class: str
    confidence: float
    probabilities: List[Dict[str, Any]]

    gradcam_available: bool
    gradcam_b64: Optional[str] = None   # data:image/png;base64,... ready for <img src>

    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER
