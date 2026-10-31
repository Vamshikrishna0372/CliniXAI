"""Consultation domain model for CliniXAI Phase 4."""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

from app.utils.datetime import utc_now


class ConsultationStatus(str, Enum):
    """Consultation operational status."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class RiskLevel(str, Enum):
    """Patient risk/priority assessment levels."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class SymptomSeverity(str, Enum):
    """Symptom severity levels."""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


class DiagnosisType(str, Enum):
    """Diagnosis types."""
    PRIMARY = "primary"
    SECONDARY = "secondary"


class ChiefComplaint(BaseModel):
    """Structured chief complaint data."""
    complaint: str = Field(..., min_length=2, max_length=300)
    duration: Optional[str] = Field(None, max_length=100)      # e.g., "3 days"
    description: Optional[str] = Field(None, max_length=1000)


class Symptom(BaseModel):
    """Structured symptom object."""
    name: str = Field(..., min_length=2, max_length=150)
    severity: SymptomSeverity = SymptomSeverity.MODERATE
    duration: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class Vitals(BaseModel):
    """Structured patient physiological vitals with validation ranges."""
    temperature_c: Optional[float] = Field(None, ge=30.0, le=45.0, description="Temperature in °C")
    heart_rate_bpm: Optional[int] = Field(None, ge=30, le=250, description="Heart rate in bpm")
    bp_systolic: Optional[int] = Field(None, ge=50, le=250, description="Systolic Blood Pressure in mmHg")
    bp_diastolic: Optional[int] = Field(None, ge=30, le=150, description="Diastolic Blood Pressure in mmHg")
    respiratory_rate: Optional[int] = Field(None, ge=5, le=60, description="Respiratory rate per minute")
    spo2_percent: Optional[float] = Field(None, ge=50.0, le=100.0, description="SpO2 percentage")
    weight_kg: Optional[float] = Field(None, ge=0.5, le=300.0, description="Weight in kg")
    height_cm: Optional[float] = Field(None, ge=20.0, le=250.0, description="Height in cm")
    bmi: Optional[float] = Field(None, description="Derived Body Mass Index kg/m²")

    def calculate_bmi() -> Optional[float]:
        """Calculates BMI dynamically if weight and height are present."""
        if self.weight_kg and self.height_cm and self.height_cm > 0:
            height_m = self.height_cm / 100.0
            return round(self.weight_kg / (height_m ** 2), 2)
        return None


class ClinicalAssessment(BaseModel):
    """Structured Doctor clinical assessment."""
    summary: str = Field(..., min_length=2, max_length=2000)
    impression: Optional[str] = Field(None, max_length=1000)
    differential_diagnoses: List[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    notes: Optional[str] = Field(None, max_length=1000)


class Diagnosis(BaseModel):
    """Structured diagnosis entry."""
    name: str = Field(..., min_length=2, max_length=200)
    type: DiagnosisType = DiagnosisType.PRIMARY
    code: Optional[str] = Field(None, max_length=50, description="ICD/Coding reference if available")
    notes: Optional[str] = Field(None, max_length=500)


class ConsultationInDB(BaseModel):
    """Internal consultation document model stored in MongoDB `consultations` collection."""

    consultation_id: str
    appointment_id: str                    # Unique 1-to-1 mapping
    patient_id: str
    doctor_id: str
    department_id: str
    status: ConsultationStatus = ConsultationStatus.IN_PROGRESS

    chief_complaint: Optional[ChiefComplaint] = None
    symptoms: List[Symptom] = Field(default_factory=list)
    vitals: Optional[Vitals] = None
    clinical_notes: Optional[str] = None    # Confidential Doctor notes
    clinical_assessment: Optional[ClinicalAssessment] = None
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    doctor_instructions: List[str] = Field(default_factory=list)
    care_plan: Optional[str] = None
    follow_up_required: bool = False
    follow_up_date: Optional[str] = None

    prescription_references: List[str] = Field(default_factory=list)
    follow_up_references: List[str] = Field(default_factory=list)
    ai_analysis_references: List[str] = Field(default_factory=list)    # AI readiness
    medical_record_references: List[str] = Field(default_factory=list) # Medical Record readiness
    linked_ai_analysis_ids: List[str] = Field(default_factory=list)
    linked_medical_record_ids: List[str] = Field(default_factory=list)

    created_by: Optional[str] = None
    completed_by: Optional[str] = None
    version: int = 1

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts consultation instance to MongoDB-ready dictionary."""
        return self.model_dump()
