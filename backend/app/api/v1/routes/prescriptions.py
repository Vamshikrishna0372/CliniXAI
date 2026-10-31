"""Prescription & Medication API Routes for CliniXAI Phase 15."""

from typing import Optional, List, Union
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import UserInDB, UserRole
from app.models.prescription import FollowUpStatus
from app.schemas.prescriptions import (
    CreatePrescriptionRequest, UpdatePrescriptionRequest, CancelPrescriptionRequest,
    PrescriptionResponse, PatientPrescriptionResponse, FollowUpSummaryResponse
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.prescription_service import PrescriptionService
from app.core.exceptions import ForbiddenError, ResourceNotFoundError, AppValidationError

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])


@router.post(
    "",
    response_model=APIResponse[PrescriptionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Prescription (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR))],
)
async def create_prescription(
    request: CreatePrescriptionRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor creates or updates a prescription for a valid clinical consultation."""
    consultation_id = request.consultation_id
    if not consultation_id:
        raise AppValidationError("consultation_id is required in request payload.")

    rx = await PrescriptionService.create_or_update_prescription(
        db, consultation_id, request, doctor_user=current_user
    )
    return APIResponse(message="Prescription issued successfully", data=rx.model_dump())


@router.post(
    "/consultation/{consultation_id}",
    response_model=APIResponse[PrescriptionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Issue / Update Prescription for Consultation (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR))],
)
async def create_or_update_prescription_by_consultation(
    consultation_id: str,
    request: CreatePrescriptionRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor issues or updates a prescription for an active consultation session."""
    rx = await PrescriptionService.create_or_update_prescription(
        db, consultation_id, request, doctor_user=current_user
    )
    return APIResponse(message="Prescription issued successfully", data=rx.model_dump())


@router.post(
    "/{prescription_id}/cancel",
    response_model=APIResponse[PrescriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel Prescription (Doctor)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR))],
)
async def cancel_prescription(
    prescription_id: str,
    request: CancelPrescriptionRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Doctor cancels an active prescription with documented clinical rationale."""
    reason = request.get_reason()
    rx = await PrescriptionService.cancel_prescription(
        db, prescription_id, reason=reason, doctor_user=current_user
    )
    return APIResponse(message="Prescription cancelled successfully", data=rx.model_dump())


@router.get(
    "/consultation/{consultation_id}",
    response_model=APIResponse[Union[PrescriptionResponse, PatientPrescriptionResponse, None]],
    summary="Get Prescription by Consultation",
)
async def get_prescription_by_consultation(
    consultation_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetches the active prescription linked to a specific consultation."""
    rx = await PrescriptionService.get_prescription_by_consultation(db, consultation_id)
    if not rx:
        return APIResponse(data=None)

    if current_user.role == UserRole.PATIENT:
        patient = await db["patients"].find_one({"user_id": current_user.user_id})
        if not patient or patient["patient_id"] != rx["patient_id"]:
            raise ForbiddenError("You are not authorized to view this prescription.")
        return APIResponse(data=PatientPrescriptionResponse(**rx))

    if current_user.role == UserRole.DOCTOR:
        from app.services.appointment_service import AppointmentService
        doctor = await AppointmentService.get_doctor_for_user(db, current_user)
        if not doctor:
            raise ForbiddenError("Authenticated user does not have an active Doctor profile.")
        doc_id = doctor.get("doctor_id")
        if doc_id != rx["doctor_id"]:
            from app.database.collections import COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS
            has_apt = await db[COLLECTION_APPOINTMENTS].find_one({"patient_id": rx["patient_id"], "doctor_id": doc_id})
            has_consult = await db[COLLECTION_CONSULTATIONS].find_one({"patient_id": rx["patient_id"], "doctor_id": doc_id})
            if not has_apt and not has_consult:
                raise ForbiddenError("You are not authorized to view another doctor's prescription.")
        return APIResponse(data=PrescriptionResponse(**rx))

    return APIResponse(data=PrescriptionResponse(**rx))


@router.get(
    "/follow-ups",
    response_model=APIResponse[List[FollowUpSummaryResponse]],
    summary="List Scheduled Follow-Ups",
)
async def list_follow_ups(
    status: Optional[FollowUpStatus] = Query(default=None),
    doctor_id: Optional[str] = Query(default=None),
    patient_id: Optional[str] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Retrieves scheduled follow-up list (Doctor sees own, Patient sees own upcoming)."""
    follow_ups = await PrescriptionService.list_follow_ups(
        db, current_user=current_user, status_filter=status, doctor_id=doctor_id, patient_id=patient_id
    )
    results = [
        FollowUpSummaryResponse(
            prescription_id=f["prescription_id"],
            consultation_id=f["consultation_id"],
            patient_id=f["patient_id"],
            doctor_id=f["doctor_id"],
            follow_up=f["follow_up"],
            issued_at=f.get("issued_at"),
        )
        for f in follow_ups
    ]
    return APIResponse(data=results)


@router.get(
    "",
    response_model=PaginatedResponse[Union[PrescriptionResponse, PatientPrescriptionResponse]],
    summary="List Prescriptions (Role-Aware)",
)
async def list_prescriptions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    patient_id: Optional[str] = Query(default=None),
    doctor_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    date: Optional[str] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Role-aware prescription list retrieval."""
    docs, total = await PrescriptionService.list_prescriptions(
        db, current_user=current_user, page=page, page_size=page_size,
        patient_id=patient_id, doctor_id=doctor_id, status_filter=status, date_filter=date
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)

    results = []
    for d in docs:
        if current_user.role == UserRole.PATIENT:
            results.append(PatientPrescriptionResponse(**d))
        else:
            results.append(PrescriptionResponse(**d))

    return PaginatedResponse(data=results, pagination=meta)


@router.get(
    "/{prescription_id}",
    response_model=APIResponse[Union[PrescriptionResponse, PatientPrescriptionResponse]],
    summary="Get Prescription Details",
)
async def get_prescription_detail(
    prescription_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetch prescription details with object-level authorization."""
    rx = await PrescriptionService.get_prescription_by_id(db, prescription_id)

    if current_user.role == UserRole.PATIENT:
        patient = await db["patients"].find_one({"user_id": current_user.user_id})
        if not patient or patient["patient_id"] != rx["patient_id"]:
            raise ForbiddenError("You are not authorized to view this prescription.")
        return APIResponse(data=PatientPrescriptionResponse(**rx))

    if current_user.role == UserRole.DOCTOR:
        from app.services.appointment_service import AppointmentService
        doctor = await AppointmentService.get_doctor_for_user(db, current_user)
        if not doctor:
            raise ForbiddenError("Authenticated user does not have an active Doctor profile.")
        doc_id = doctor.get("doctor_id")
        if doc_id != rx["doctor_id"]:
            from app.database.collections import COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS
            has_apt = await db[COLLECTION_APPOINTMENTS].find_one({"patient_id": rx["patient_id"], "doctor_id": doc_id})
            has_consult = await db[COLLECTION_CONSULTATIONS].find_one({"patient_id": rx["patient_id"], "doctor_id": doc_id})
            if not has_apt and not has_consult:
                raise ForbiddenError("You are not authorized to view another doctor's prescription.")
        return APIResponse(data=PrescriptionResponse(**rx))

    return APIResponse(data=PrescriptionResponse(**rx))

