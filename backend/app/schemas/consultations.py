"""Consultation request and response Pydantic schemas for Phase 4."""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from app.utils.datetime import utc_now

from app.models.consultation import (
    ConsultationStatus, RiskLevel, SymptomSeverity, DiagnosisType,
    ChiefComplaint, Symptom, Vitals, ClinicalAssessment, Diagnosis
)
from app.models.patient import Gender, BloodGroup


# ── Request Schemas ────────────────────────────────────────────────────────────

class StartConsultationRequest(BaseModel):
    """Schema for initiating a consultation from an appointment."""
    appointment_id: str


class UpdateChiefComplaintRequest(BaseModel):
    """Schema for updating chief complaint."""
    chief_complaint: ChiefComplaint


class UpdateSymptomsRequest(BaseModel):
    """Schema for updating symptoms list."""
    symptoms: List[Symptom]


class UpdateVitalsRequest(BaseModel):
    """Schema for recording patient vitals."""
    vitals: Vitals

    @field_validator("vitals", mode="after")
    @classmethod
    def compute_bmi_if_possible(cls, v: Vitals) -> Vitals:
        if v.weight_kg and v.height_cm and v.height_cm > 0:
            height_m = v.height_cm / 100.0
            v.bmi = round(v.weight_kg / (height_m ** 2), 2)
        return v


class UpdateClinicalNotesRequest(BaseModel):
    """Schema for updating Doctor confidential clinical notes."""
    notes: Optional[str] = Field(default=None, max_length=5000)
    clinical_notes: Optional[str] = Field(default=None, max_length=5000)
    expected_version: Optional[int] = None

    @model_validator(mode="after")
    def resolve_notes(self):
        if not self.notes and not self.clinical_notes:
            raise ValueError("Either 'notes' or 'clinical_notes' must be provided.")
        if not self.notes:
            self.notes = self.clinical_notes
        return self


class UpdateClinicalAssessmentRequest(BaseModel):
    """Schema for recording Doctor clinical assessment."""
    assessment: Optional[ClinicalAssessment] = None
    summary: Optional[str] = None
    risk_level: Optional[RiskLevel] = None

    @model_validator(mode="after")
    def resolve_assessment(self):
        if self.assessment is None:
            if not self.summary:
                raise ValueError("Clinical assessment summary is required.")
            self.assessment = ClinicalAssessment(
                summary=self.summary,
                risk_level=self.risk_level or RiskLevel.LOW
            )
        return self


class UpdateDiagnosesRequest(BaseModel):
    """Schema for setting primary and secondary diagnoses."""
    diagnoses: List[Diagnosis]


class UpdateInstructionsRequest(BaseModel):
    """Schema for recording patient care instructions."""
    doctor_instructions: List[str] = Field(..., description="List of doctor instructions")


class UpdateCarePlanRequest(BaseModel):
    """Schema for recording care plan and follow-up requirements."""
    care_plan: str = Field(..., min_length=2, max_length=2000)
    follow_up_required: bool = False
    follow_up_date: Optional[str] = None


class LinkAIAnalysisRequest(BaseModel):
    """Schema for linking an AI Analysis to a Consultation."""
    ai_analysis_id: Optional[str] = None
    analysis_id: Optional[str] = None

    @model_validator(mode="after")
    def resolve_ai_id(self):
        val = self.ai_analysis_id or self.analysis_id
        if not val:
            raise ValueError("ai_analysis_id is required")
        self.ai_analysis_id = val
        return self


class LinkMedicalRecordRequest(BaseModel):
    """Schema for linking a Medical Record to a Consultation."""
    record_id: Optional[str] = None
    medical_record_id: Optional[str] = None

    @model_validator(mode="after")
    def resolve_record_id(self):
        val = self.record_id or self.medical_record_id
        if not val:
            raise ValueError("record_id is required")
        self.record_id = val
        return self


class CancelConsultationRequest(BaseModel):
    """Schema for cancelling/aborting a consultation."""
    reason: Optional[str] = Field(None, max_length=500)


# ── Response Schemas ───────────────────────────────────────────────────────────

class ConsultationResponse(BaseModel):
    """Full consultation detail response (for authorized Doctor workspace)."""
    consultation_id: str
    appointment_id: str
    patient_id: str
    doctor_id: str
    department_id: str
    status: ConsultationStatus
    chief_complaint: Optional[ChiefComplaint] = None
    symptoms: List[Symptom] = Field(default_factory=list)
    vitals: Optional[Vitals] = None
    clinical_notes: Optional[str] = None
    clinical_assessment: Optional[ClinicalAssessment] = None
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    doctor_instructions: List[str] = Field(default_factory=list)
    care_plan: Optional[str] = None
    follow_up_required: bool = False
    follow_up_date: Optional[str] = None
    ai_analysis_references: List[str] = Field(default_factory=list)
    medical_record_references: List[str] = Field(default_factory=list)
    linked_ai_analysis_ids: List[str] = Field(default_factory=list)
    linked_medical_record_ids: List[str] = Field(default_factory=list)
    created_by: Optional[str] = None
    completed_by: Optional[str] = None
    version: int = 1
    started_at: Optional[datetime] = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if not values.get("created_at"):
                values["created_at"] = values.get("started_at") or utc_now()
            if not values.get("updated_at"):
                values["updated_at"] = values.get("created_at") or utc_now()
            if not values.get("department_id"):
                values["department_id"] = "DEPT-GEN"
            if not values.get("started_at"):
                values["started_at"] = values.get("created_at") or utc_now()
            # Sync alias fields
            if not values.get("linked_ai_analysis_ids") and values.get("ai_analysis_references"):
                values["linked_ai_analysis_ids"] = list(values["ai_analysis_references"])
            elif not values.get("ai_analysis_references") and values.get("linked_ai_analysis_ids"):
                values["ai_analysis_references"] = list(values["linked_ai_analysis_ids"])

            if not values.get("linked_medical_record_ids") and values.get("medical_record_references"):
                values["linked_medical_record_ids"] = list(values["medical_record_references"])
            elif not values.get("medical_record_references") and values.get("linked_medical_record_ids"):
                values["medical_record_references"] = list(values["linked_medical_record_ids"])

            # Resilient normalization for chief complaint
            if isinstance(values.get("chief_complaint"), str):
                values["chief_complaint"] = {
                    "complaint": values["chief_complaint"],
                    "description": values["chief_complaint"]
                }
            elif isinstance(values.get("chief_complaint"), dict) and "complaint" not in values.get("chief_complaint"):
                cc = dict(values["chief_complaint"])
                cc["complaint"] = cc.get("description") or cc.get("name") or "Medical consultation"
                values["chief_complaint"] = cc

            # Resilient normalization for clinical assessment
            if isinstance(values.get("clinical_assessment"), str):
                values["clinical_assessment"] = {
                    "summary": values["clinical_assessment"],
                    "risk_level": "low"
                }

            # Resilient normalization for diagnoses
            if isinstance(values.get("diagnoses"), list):
                sanitized_diags = []
                for d in values["diagnoses"]:
                    if isinstance(d, dict):
                        d_copy = dict(d)
                        if "name" not in d_copy and "description" in d_copy:
                            d_copy["name"] = d_copy["description"]
                        sanitized_diags.append(d_copy)
                    elif isinstance(d, str):
                        sanitized_diags.append({"name": d, "type": "primary"})
                    else:
                        sanitized_diags.append(d)
                values["diagnoses"] = sanitized_diags
        return values


class PatientConsultationResponse(BaseModel):
    """Sanitized consultation summary for Patient view — strictly hides confidential Doctor draft notes."""
    consultation_id: str
    appointment_id: str
    patient_id: str
    doctor_id: str
    department_id: str
    status: ConsultationStatus
    chief_complaint: Optional[ChiefComplaint] = None
    symptoms: List[Symptom] = Field(default_factory=list)
    vitals: Optional[Vitals] = None
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    doctor_instructions: List[str] = Field(default_factory=list)
    care_plan: Optional[str] = None
    follow_up_required: bool = False
    follow_up_date: Optional[str] = None
    linked_ai_analysis_ids: List[str] = Field(default_factory=list)
    linked_medical_record_ids: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if not values.get("department_id"):
                values["department_id"] = "DEPT-GEN"
            if not values.get("started_at"):
                values["started_at"] = values.get("created_at") or utc_now()
            if not values.get("linked_ai_analysis_ids") and values.get("ai_analysis_references"):
                values["linked_ai_analysis_ids"] = list(values["ai_analysis_references"])
            if not values.get("linked_medical_record_ids") and values.get("medical_record_references"):
                values["linked_medical_record_ids"] = list(values["medical_record_references"])

            # Resilient normalization for chief complaint
            if isinstance(values.get("chief_complaint"), str):
                values["chief_complaint"] = {
                    "complaint": values["chief_complaint"],
                    "description": values["chief_complaint"]
                }
            elif isinstance(values.get("chief_complaint"), dict) and "complaint" not in values.get("chief_complaint"):
                cc = dict(values["chief_complaint"])
                cc["complaint"] = cc.get("description") or cc.get("name") or "Medical consultation"
                values["chief_complaint"] = cc

            # Resilient normalization for diagnoses
            if isinstance(values.get("diagnoses"), list):
                sanitized_diags = []
                for d in values["diagnoses"]:
                    if isinstance(d, dict):
                        d_copy = dict(d)
                        if "name" not in d_copy and "description" in d_copy:
                            d_copy["name"] = d_copy["description"]
                        sanitized_diags.append(d_copy)
                    elif isinstance(d, str):
                        sanitized_diags.append({"name": d, "type": "primary"})
                    else:
                        sanitized_diags.append(d)
                values["diagnoses"] = sanitized_diags
        return values


class StaffConsultationResponse(BaseModel):
    """Operational status summary for Staff view."""
    consultation_id: str
    appointment_id: str
    patient_id: str
    doctor_id: str
    department_id: str
    status: ConsultationStatus
    care_plan: Optional[str] = None
    follow_up_required: bool = False
    follow_up_date: Optional[str] = None
    started_at: Optional[datetime] = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def fill_defaults(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if not values.get("department_id"):
                values["department_id"] = "DEPT-GEN"
            if not values.get("started_at"):
                values["started_at"] = values.get("created_at") or utc_now()
        return values


class PastConsultationSummary(BaseModel):
    """Compact record of a past consultation for Doctor patient context workspace."""
    consultation_id: str
    appointment_id: str
    date: str
    diagnoses: List[Diagnosis]
    assessment_summary: Optional[str] = None


class PatientClinicalContextResponse(BaseModel):
    """Clinical workspace context for assigned Doctor prior to / during consultation."""
    patient_id: str
    first_name: str = "Patient"
    last_name: str = ""
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[Gender] = None
    blood_group: Optional[BloodGroup] = None
    allergies: List[str] = Field(default_factory=list)
    past_consultations: List[PastConsultationSummary] = Field(default_factory=list)
    recent_prescriptions: List[Any] = Field(default_factory=list)
