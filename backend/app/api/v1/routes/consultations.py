"""Doctor Consultation Workflow API Routes for CliniXAI Phase 4."""

from typing import Optional, Union, List
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import UserInDB, UserRole
from app.models.consultation import ConsultationStatus
from app.schemas.consultations import (
    StartConsultationRequest, UpdateChiefComplaintRequest, UpdateSymptomsRequest,
    UpdateVitalsRequest, UpdateClinicalNotesRequest, UpdateClinicalAssessmentRequest,
    UpdateDiagnosesRequest, UpdateInstructionsRequest, UpdateCarePlanRequest,
    LinkAIAnalysisRequest, LinkMedicalRecordRequest, CancelConsultationRequest,
    ConsultationResponse, PatientConsultationResponse, StaffConsultationResponse,
    PatientClinicalContextResponse
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.consultation_service import ConsultationService
from app.core.exceptions import ForbiddenError, ResourceNotFoundError

router = APIRouter(prefix="/consultations", tags=["Consultations"])


@router.post(
    "",
    response_model=APIResponse[ConsultationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create / Start Consultation (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
@router.post(
    "/start",
    response_model=APIResponse[ConsultationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Start Consultation (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def start_consultation(
    request: StartConsultationRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor starts a consultation session for an assigned appointment."""
    consult = await ConsultationService.start_consultation(db, request.appointment_id, doctor_user=current_user)
    return APIResponse(message="Consultation started successfully", data=consult.model_dump())


@router.post(
    "/start/{appointment_id}",
    response_model=APIResponse[ConsultationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Start Consultation by Appointment ID Path (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def start_consultation_by_path(
    appointment_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor starts a consultation session using appointment ID path."""
    consult = await ConsultationService.start_consultation(db, appointment_id, doctor_user=current_user)
    return APIResponse(message="Consultation started successfully", data=consult.model_dump())


@router.get(
    "/patient-context/{patient_id}",
    response_model=APIResponse[PatientClinicalContextResponse],
    summary="Get Patient Clinical Context Workspace (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.HOSPITAL_STAFF))],
)
async def get_patient_clinical_context(
    patient_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Retrieves patient clinical context (history, allergies, past completed consultations, prescriptions) for Doctor workspace."""
    ctx = await ConsultationService.get_patient_clinical_context(db, patient_id, doctor_user=current_user)
    return APIResponse(data=ctx)


@router.get(
    "",
    response_model=PaginatedResponse[Union[ConsultationResponse, PatientConsultationResponse, StaffConsultationResponse]],
    summary="List Consultations (Role-Aware)",
)
async def list_consultations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[ConsultationStatus] = Query(default=None),
    patient_id: Optional[str] = Query(default=None),
    doctor_id: Optional[str] = Query(default=None),
    department_id: Optional[str] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Role-aware consultation listing (Patients see own completed, Doctors see assigned, Staff/Admin see operational)."""
    docs, total = await ConsultationService.list_consultations(
        db, current_user=current_user, page=page, page_size=page_size,
        status=status, patient_id=patient_id, doctor_id=doctor_id, department_id=department_id
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)

    # Transform responses according to role visibility
    results = []
    for d in docs:
        if current_user.role == UserRole.PATIENT:
            results.append(PatientConsultationResponse(**d))
        elif current_user.role == UserRole.HOSPITAL_STAFF:
            results.append(StaffConsultationResponse(**d))
        else:
            results.append(ConsultationResponse(**d))

    return PaginatedResponse(data=results, pagination=meta)


@router.get(
    "/{consultation_id}",
    response_model=APIResponse[Union[ConsultationResponse, PatientConsultationResponse, StaffConsultationResponse]],
    summary="Get Consultation Detail",
)
async def get_consultation_detail(
    consultation_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetch consultation details with object-level authorization."""
    c = await ConsultationService.get_consultation_by_id(db, consultation_id)

    if current_user.role == UserRole.PATIENT:
        patient = await db["patients"].find_one({"user_id": current_user.user_id})
        if not patient or patient["patient_id"] != c["patient_id"]:
            raise ForbiddenError("You are not authorized to view this consultation.")
        if c["status"] != ConsultationStatus.COMPLETED.value:
            raise ForbiddenError("Patient can only view completed consultations.")
        return APIResponse(data=PatientConsultationResponse(**c))

    if current_user.role == UserRole.DOCTOR:
        await ConsultationService._check_doctor_authorization(db, current_user, c)
        return APIResponse(data=ConsultationResponse(**c))

    if current_user.role == UserRole.HOSPITAL_STAFF:
        return APIResponse(data=StaffConsultationResponse(**c))

    return APIResponse(data=ConsultationResponse(**c))


@router.patch(
    "/{consultation_id}/chief-complaint",
    response_model=APIResponse[ConsultationResponse],
    summary="Record Chief Complaint (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def update_chief_complaint(
    consultation_id: str,
    request: UpdateChiefComplaintRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor records or updates the chief complaint."""
    updated = await ConsultationService.update_consultation_data(
        db, consultation_id, "chief_complaint", request.chief_complaint.model_dump(), doctor_user=current_user
    )
    return APIResponse(message="Chief complaint recorded", data=updated)


@router.patch(
    "/{consultation_id}/symptoms",
    response_model=APIResponse[ConsultationResponse],
    summary="Record Symptoms (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def update_symptoms(
    consultation_id: str,
    request: UpdateSymptomsRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor records or updates symptoms."""
    symptoms_dict = [s.model_dump() for s in request.symptoms]
    updated = await ConsultationService.update_consultation_data(
        db, consultation_id, "symptoms", symptoms_dict, doctor_user=current_user
    )
    return APIResponse(message="Symptoms recorded", data=updated)


@router.patch(
    "/{consultation_id}/vitals",
    response_model=APIResponse[ConsultationResponse],
    summary="Record Vitals (Doctor/Staff)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.HOSPITAL_STAFF))],
)
async def update_vitals(
    consultation_id: str,
    request: UpdateVitalsRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor records patient physiological vitals (automatically computes BMI)."""
    updated = await ConsultationService.update_consultation_data(
        db, consultation_id, "vitals", request.vitals.model_dump(), doctor_user=current_user
    )
    return APIResponse(message="Vitals recorded", data=updated)


@router.patch(
    "/{consultation_id}/clinical-notes",
    response_model=APIResponse[ConsultationResponse],
    summary="Save Draft Confidential Clinical Notes (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def update_clinical_notes(
    consultation_id: str,
    request: UpdateClinicalNotesRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor updates draft clinical notes during consultation."""
    updated = await ConsultationService.update_consultation_data(
        db, consultation_id, "clinical_notes", request.notes, doctor_user=current_user,
        expected_version=request.expected_version
    )
    return APIResponse(message="Clinical notes saved", data=updated)


@router.patch(
    "/{consultation_id}/assessment",
    response_model=APIResponse[ConsultationResponse],
    summary="Record Doctor Clinical Assessment (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def update_assessment(
    consultation_id: str,
    request: UpdateClinicalAssessmentRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor records clinical assessment."""
    updated = await ConsultationService.update_consultation_data(
        db, consultation_id, "clinical_assessment", request.assessment.model_dump(), doctor_user=current_user
    )
    return APIResponse(message="Clinical assessment recorded", data=updated)


@router.patch(
    "/{consultation_id}/diagnoses",
    response_model=APIResponse[ConsultationResponse],
    summary="Record Diagnoses (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def update_diagnoses(
    consultation_id: str,
    request: UpdateDiagnosesRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor records primary and secondary diagnoses."""
    diagnoses_dict = [d.model_dump() for d in request.diagnoses]
    updated = await ConsultationService.update_consultation_data(
        db, consultation_id, "diagnoses", diagnoses_dict, doctor_user=current_user
    )
    return APIResponse(message="Diagnoses recorded", data=updated)


@router.patch(
    "/{consultation_id}/instructions",
    response_model=APIResponse[ConsultationResponse],
    summary="Record Doctor Instructions (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def update_instructions(
    consultation_id: str,
    request: UpdateInstructionsRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor records patient instructions."""
    updated = await ConsultationService.update_consultation_data(
        db, consultation_id, "doctor_instructions", request.doctor_instructions, doctor_user=current_user
    )
    return APIResponse(message="Instructions recorded", data=updated)


@router.patch(
    "/{consultation_id}/care-plan",
    response_model=APIResponse[ConsultationResponse],
    summary="Record Care Plan & Follow-Up (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def update_care_plan(
    consultation_id: str,
    request: UpdateCarePlanRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor records care plan and follow up instructions."""
    updated = await ConsultationService.update_care_plan(
        db, consultation_id, care_plan=request.care_plan,
        follow_up_required=request.follow_up_required,
        follow_up_date=request.follow_up_date,
        doctor_user=current_user
    )
    return APIResponse(message="Care plan recorded", data=updated)


@router.post(
    "/{consultation_id}/link-ai-analysis",
    response_model=APIResponse[ConsultationResponse],
    summary="Link AI Analysis to Consultation (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def link_ai_analysis(
    consultation_id: str,
    request: LinkAIAnalysisRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor links an authorized AI analysis to this clinical consultation."""
    updated = await ConsultationService.link_ai_analysis(
        db, consultation_id, ai_analysis_id=request.ai_analysis_id, doctor_user=current_user
    )
    return APIResponse(message="AI analysis linked successfully", data=updated)


@router.post(
    "/{consultation_id}/link-medical-record",
    response_model=APIResponse[ConsultationResponse],
    summary="Link Medical Record to Consultation (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def link_medical_record(
    consultation_id: str,
    request: LinkMedicalRecordRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor links an authorized Medical Record to this clinical consultation."""
    updated = await ConsultationService.link_medical_record(
        db, consultation_id, record_id=request.record_id, doctor_user=current_user
    )
    return APIResponse(message="Medical record linked successfully", data=updated)


@router.post(
    "/{consultation_id}/complete",
    response_model=APIResponse[ConsultationResponse],
    summary="Complete & Finalize Consultation (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def complete_consultation(
    consultation_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Finalizes and completes consultation, moving appointment and queue states to completed."""
    completed = await ConsultationService.complete_consultation(db, consultation_id, doctor_user=current_user)
    return APIResponse(message="Consultation completed and finalized successfully", data=completed)


@router.post(
    "/{consultation_id}/cancel",
    response_model=APIResponse[ConsultationResponse],
    summary="Cancel Consultation (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN))],
)
async def cancel_consultation(
    consultation_id: str,
    request: CancelConsultationRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Cancels/aborts an active consultation."""
    cancelled = await ConsultationService.cancel_consultation(
        db, consultation_id, reason=request.reason, doctor_user=current_user
    )
    return APIResponse(message="Consultation cancelled", data=cancelled)
