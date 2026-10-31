"""Patient Management API Routes for CliniXAI."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import UserInDB, UserRole
from app.models.patient import PatientStatus
from app.schemas.patients import (
    CreatePatientRequest, UpdatePatientRequest, UpdatePatientStatusRequest,
    PatientResponse, PatientSummaryResponse
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.patient_service import PatientService
from app.core.exceptions import ResourceNotFoundError, ForbiddenError

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get(
    "/me",
    response_model=APIResponse[PatientResponse],
    summary="Get Authenticated Patient Self Profile",
    dependencies=[Depends(require_roles(UserRole.PATIENT))],
)
async def get_patient_me(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns the patient profile associated with the logged-in patient account."""
    patient = await PatientService.get_patient_by_user_id(db, current_user.user_id)
    if not patient:
        raise ResourceNotFoundError("Patient profile for current user")
    return APIResponse(data=patient)


@router.patch(
    "/me",
    response_model=APIResponse[PatientResponse],
    summary="Update Authenticated Patient Self Profile",
    dependencies=[Depends(require_roles(UserRole.PATIENT))],
)
async def update_patient_me(
    request: UpdatePatientRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Allows authenticated patient to update personal profile information."""
    patient = await PatientService.get_patient_by_user_id(db, current_user.user_id)
    if not patient:
        raise ResourceNotFoundError("Patient profile for current user")

    updated = await PatientService.update_patient(
        db, patient["patient_id"], request, updater_user_id=current_user.user_id
    )
    return APIResponse(message="Profile updated successfully", data=updated)


@router.post(
    "",
    response_model=APIResponse[PatientResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register New Patient (Staff/Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN))],
)
async def create_patient(
    request: CreatePatientRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Staff or Admin operational patient registration."""
    patient = await PatientService.create_patient(db, request, created_by_user_id=current_user.user_id)
    return APIResponse(message="Patient created successfully", data=patient.model_dump())


@router.get(
    "",
    response_model=PaginatedResponse[PatientSummaryResponse],
    summary="List & Search Patients (Staff/Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN, UserRole.DOCTOR))],
)
async def list_patients(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, description="Search by ID, name, email, or phone"),
    status: Optional[PatientStatus] = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Paginated patient listing for staff/admin/doctors."""
    docs, total = await PatientService.list_patients(
        db, page=page, page_size=page_size, search=search, status=status
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=docs, pagination=meta)


@router.get(
    "/{patient_id}",
    response_model=APIResponse[PatientResponse],
    summary="Get Patient Details",
)
async def get_patient_detail(
    patient_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetch patient detail with object-level authorization."""
    patient = await PatientService.get_patient_by_id(db, patient_id)

    if current_user.role == UserRole.PATIENT:
        if patient.get("user_id") != current_user.user_id:
            raise ForbiddenError("You are not authorized to view this patient profile.")
    elif current_user.role == UserRole.DOCTOR:
        from app.services.appointment_service import AppointmentService
        from app.database.collections import COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS
        doctor = await AppointmentService.get_doctor_for_user(db, current_user)
        doc_id = doctor.get("doctor_id") if doctor else None
        if not doc_id:
            raise ForbiddenError("You are not authorized to view this patient profile without an established clinical care relationship.")
        has_apt = await db[COLLECTION_APPOINTMENTS].find_one({"patient_id": patient_id, "doctor_id": doc_id})
        has_consult = await db[COLLECTION_CONSULTATIONS].find_one({"patient_id": patient_id, "doctor_id": doc_id})
        if not has_apt and not has_consult:
            raise ForbiddenError("You are not authorized to view this patient profile without an established clinical care relationship.")

    return APIResponse(data=patient)


@router.patch(
    "/{patient_id}",
    response_model=APIResponse[PatientResponse],
    summary="Update Patient (Staff/Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN))],
)
async def update_patient(
    patient_id: str,
    request: UpdatePatientRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Update patient details by Staff or Admin."""
    updated = await PatientService.update_patient(
        db, patient_id, request, updater_user_id=current_user.user_id
    )
    return APIResponse(message="Patient updated successfully", data=updated)


@router.patch(
    "/{patient_id}/status",
    response_model=APIResponse[PatientResponse],
    summary="Change Patient Status (Staff/Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN))],
)
async def update_patient_status(
    patient_id: str,
    request: UpdatePatientStatusRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Activate or deactivate a patient profile."""
    updated = await PatientService.update_patient_status(
        db, patient_id, request.status, updater_user_id=current_user.user_id
    )
    return APIResponse(message=f"Patient status updated to {request.status.value}", data=updated)


@router.get(
    "/{patient_id}/timeline",
    summary="Get Aggregated Patient Clinical Timeline",
    description="Chronologically aggregates appointments, consultations, prescriptions, AI analyses, reviews, billing, payments, follow-ups, and documents for a patient.",
)
async def get_patient_clinical_timeline(
    patient_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Retrieves patient clinical timeline with role-based isolation."""
    if current_user.role == UserRole.PATIENT and patient_id != current_user.user_id:
        patient_profile = await PatientService.get_patient_by_user_id(db, current_user.user_id)
        if not patient_profile or patient_profile.get("patient_id") != patient_id:
            raise ForbiddenError("You are not authorized to access this patient's clinical timeline.")
    elif current_user.role == UserRole.DOCTOR:
        from app.services.appointment_service import AppointmentService
        from app.database.collections import COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS
        doctor = await AppointmentService.get_doctor_for_user(db, current_user)
        doc_id = doctor.get("doctor_id") if doctor else None
        if not doc_id:
            raise ForbiddenError("You are not authorized to access this patient's clinical timeline without an established care relationship.")
        has_apt = await db[COLLECTION_APPOINTMENTS].find_one({"patient_id": patient_id, "doctor_id": doc_id})
        has_consult = await db[COLLECTION_CONSULTATIONS].find_one({"patient_id": patient_id, "doctor_id": doc_id})
        if not has_apt and not has_consult:
            raise ForbiddenError("You are not authorized to access this patient's clinical timeline without an established care relationship.")

    from app.services.timeline_service import TimelineService
    service = TimelineService(db)
    return await service.get_patient_timeline(patient_id)

