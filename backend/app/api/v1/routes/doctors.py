"""Doctor Management & Availability API Routes for CliniXAI."""

from typing import Optional, Union
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import UserInDB, UserRole
from app.models.doctor import DoctorStatus
from app.schemas.doctors import (
    CreateDoctorRequest, UpdateDoctorRequest, UpdateDoctorScheduleRequest,
    DoctorResponse, DoctorPublicResponse, DoctorSummaryResponse, DoctorAvailabilityResponse
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.doctor_service import DoctorService
from app.core.exceptions import ResourceNotFoundError, ForbiddenError

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get(
    "/me",
    response_model=APIResponse[DoctorResponse],
    summary="Get Authenticated Doctor Self Profile",
    dependencies=[Depends(require_roles(UserRole.DOCTOR))],
)
async def get_doctor_me(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns the doctor profile associated with the logged-in doctor account."""
    doctor = await DoctorService.get_doctor_by_user_id(db, current_user.user_id)
    if not doctor:
        raise ResourceNotFoundError("Doctor profile for current user")
    return APIResponse(data=doctor)


@router.patch(
    "/me",
    response_model=APIResponse[DoctorResponse],
    summary="Update Authenticated Doctor Self Profile",
    dependencies=[Depends(require_roles(UserRole.DOCTOR))],
)
async def update_doctor_me(
    request: UpdateDoctorRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Allows doctor to update allowed profile details."""
    doctor = await DoctorService.get_doctor_by_user_id(db, current_user.user_id)
    if not doctor:
        raise ResourceNotFoundError("Doctor profile for current user")

    # Prevent doctor from changing status via self profile
    request.status = None

    updated = await DoctorService.update_doctor(
        db, doctor["doctor_id"], request, updater_user_id=current_user.user_id
    )
    return APIResponse(message="Profile updated successfully", data=updated)


@router.patch(
    "/me/schedule",
    response_model=APIResponse[DoctorResponse],
    summary="Update Authenticated Doctor Schedule",
    dependencies=[Depends(require_roles(UserRole.DOCTOR))],
)
async def update_doctor_me_schedule(
    request: UpdateDoctorScheduleRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Allows doctor to update their weekly availability schedule."""
    doctor = await DoctorService.get_doctor_by_user_id(db, current_user.user_id)
    if not doctor:
        raise ResourceNotFoundError("Doctor profile for current user")

    updated = await DoctorService.update_doctor_schedule(
        db, doctor["doctor_id"], request, updater_user_id=current_user.user_id
    )
    return APIResponse(message="Schedule updated successfully", data=updated)


@router.post(
    "",
    response_model=APIResponse[DoctorResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Provision Doctor Account (Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def create_doctor(
    request: CreateDoctorRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin provisions a Doctor profile and linked User account."""
    doctor, raw_token = await DoctorService.create_doctor(
        db, request, admin_user_id=current_user.user_id
    )
    data = doctor.model_dump()
    return APIResponse(message="Doctor account created successfully", data=data)


@router.get(
    "",
    response_model=PaginatedResponse[DoctorSummaryResponse],
    summary="List & Search Doctors",
)
async def list_doctors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    department_id: Optional[str] = Query(default=None),
    specialization: Optional[str] = Query(default=None),
    status: Optional[DoctorStatus] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """List doctors with optional filtering by department, specialization, status, and search term."""
    docs, total = await DoctorService.list_doctors(
        db, page=page, page_size=page_size, department_id=department_id,
        specialization=specialization, status=status, search=search
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=docs, pagination=meta)


@router.get(
    "/{doctor_id}/availability",
    response_model=APIResponse[DoctorAvailabilityResponse],
    summary="Get Calculated Doctor Slot Availability",
)
async def get_doctor_availability(
    doctor_id: str,
    date: str = Query(..., description="Target date in YYYY-MM-DD format"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Dynamically computes available non-conflicting appointment slots for a given doctor on a date."""
    availability = await DoctorService.calculate_available_slots(db, doctor_id, target_date_str=date)
    return APIResponse(data=availability)


@router.get(
    "/{doctor_id}",
    response_model=APIResponse[DoctorResponse],
    summary="Get Doctor Details",
)
async def get_doctor_detail(
    doctor_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetch doctor details."""
    doctor = await DoctorService.get_doctor_by_id(db, doctor_id)
    return APIResponse(data=doctor)


@router.patch(
    "/{doctor_id}",
    response_model=APIResponse[DoctorResponse],
    summary="Update Doctor Details (Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def update_doctor(
    doctor_id: str,
    request: UpdateDoctorRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin updates doctor profile details."""
    updated = await DoctorService.update_doctor(
        db, doctor_id, request, updater_user_id=current_user.user_id
    )
    return APIResponse(message="Doctor updated successfully", data=updated)


@router.patch(
    "/{doctor_id}/schedule",
    response_model=APIResponse[DoctorResponse],
    summary="Update Doctor Schedule (Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def update_doctor_schedule(
    doctor_id: str,
    request: UpdateDoctorScheduleRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin updates a doctor's schedule configuration."""
    updated = await DoctorService.update_doctor_schedule(
        db, doctor_id, request, updater_user_id=current_user.user_id
    )
    return APIResponse(message="Doctor schedule updated successfully", data=updated)
