"""Appointment System, Check-In & Queue API Routes for CliniXAI."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import UserInDB, UserRole
from app.models.appointment import AppointmentStatus, BookingSource
from app.schemas.appointments import (
    BookAppointmentRequest, StaffBookAppointmentRequest, RescheduleAppointmentRequest,
    CancelAppointmentRequest, CheckInRequest, UpdateAppointmentStatusRequest,
    AppointmentResponse, AppointmentSummaryResponse, QueueEntryResponse
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.appointment_service import AppointmentService
from app.services.patient_service import PatientService
from app.core.exceptions import ResourceNotFoundError, ForbiddenError, AppValidationError

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post(
    "",
    response_model=APIResponse[AppointmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Book Appointment",
)
async def book_appointment(
    request: BookAppointmentRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Books an appointment.

    - Patients: patient_id is automatically derived from authenticated account.
    - Staff / Admin: can specify target patient_id or book on behalf of patient.
    """
    if current_user.role == UserRole.PATIENT:
        patient = await PatientService.get_patient_by_user_id(db, current_user.user_id)
        if not patient:
            raise ResourceNotFoundError("Patient profile for authenticated user")
        target_patient_id = patient["patient_id"]
        source = BookingSource.PATIENT
    elif current_user.role in (UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN):
        if not request.patient_id:
            raise AppValidationError("Staff/Admin booking requires specifying 'patient_id'.")
        target_patient_id = request.patient_id
        source = BookingSource.HOSPITAL_STAFF if current_user.role == UserRole.HOSPITAL_STAFF else BookingSource.HOSPITAL_ADMIN
    else:
        raise ForbiddenError("Doctors cannot book appointments on behalf of patients. Only patients, staff, or admins may book appointments.")

    target_dept_id = request.department_id
    if not target_dept_id:
        from app.database.collections import COLLECTION_DOCTORS
        doctor_doc = await db[COLLECTION_DOCTORS].find_one({"doctor_id": request.doctor_id})
        target_dept_id = (doctor_doc.get("department_id") if doctor_doc else None) or "DEPT-CARD"

    apt = await AppointmentService.validate_slot_and_book(
        db,
        patient_id=target_patient_id,
        doctor_id=request.doctor_id,
        department_id=target_dept_id,
        appointment_date_str=request.appointment_date.isoformat(),
        start_time_str=request.start_time,
        reason=request.reason,
        appointment_type=request.appointment_type,
        booking_source=source,
        created_by_user_id=current_user.user_id,
        created_by_role=current_user.role.value,
    )
    return APIResponse(message="Appointment booked successfully", data=apt.model_dump())


@router.get(
    "",
    response_model=PaginatedResponse[AppointmentSummaryResponse],
    summary="List Appointments (Role-Aware)",
)
async def list_appointments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    patient_id: Optional[str] = Query(default=None),
    doctor_id: Optional[str] = Query(default=None),
    department_id: Optional[str] = Query(default=None),
    status: Optional[AppointmentStatus] = Query(default=None),
    date_from: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Lists appointments matching filters with object-level authorization."""
    docs, total = await AppointmentService.list_appointments(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=department_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=docs, pagination=meta)


@router.get(
    "/queue",
    response_model=APIResponse[List[QueueEntryResponse]],
    summary="Get Active Queue",
)
async def get_queue(
    doctor_id: Optional[str] = Query(default=None),
    department_id: Optional[str] = Query(default=None),
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    target_date_str: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Retrieves current active queue for doctor or department."""
    effective_date = date or target_date_str
    queue_docs = await AppointmentService.get_queue(
        db, current_user=current_user, doctor_id=doctor_id, department_id=department_id, target_date_str=effective_date
    )
    results = []
    for doc in queue_docs:
        results.append({
            "appointment_id": doc["appointment_id"],
            "patient_id": doc["patient_id"],
            "doctor_id": doc["doctor_id"],
            "department_id": doc.get("department_id", "DEPT-GEN"),
            "appointment_date": doc["appointment_date"],
            "start_time": doc.get("start_time", doc.get("appointment_time", "09:00")),
            "token_number": doc.get("queue", {}).get("token_number"),
            "position": doc.get("queue", {}).get("position"),
            "status": doc["status"],
            "checked_in_at": doc.get("check_in", {}).get("checked_in_at"),
            "called_at": doc.get("queue", {}).get("called_at"),
        })
    return APIResponse(data=results)


@router.get(
    "/{appointment_id}/queue-position",
    response_model=APIResponse[dict],
    summary="Get Patient Own Queue Position",
)
async def get_patient_queue_position(
    appointment_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns queue position and estimated patients ahead for an appointment."""
    pos_data = await AppointmentService.get_patient_queue_position(db, appointment_id, current_user)
    return APIResponse(data=pos_data)


@router.post(
    "/{appointment_id}/confirm",
    response_model=APIResponse[AppointmentResponse],
    summary="Confirm Appointment (Doctor/Staff/Admin)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN))],
)
async def confirm_appointment(
    appointment_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Confirms a scheduled appointment."""
    updated = await AppointmentService.confirm_appointment(db, appointment_id, current_user)
    return APIResponse(message="Appointment confirmed successfully", data=updated)


@router.post(
    "/{appointment_id}/complete",
    response_model=APIResponse[AppointmentResponse],
    summary="Complete Appointment (Doctor/Staff/Admin)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN))],
)
async def complete_appointment(
    appointment_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Marks an active appointment as completed."""
    updated = await AppointmentService.complete_appointment(db, appointment_id, current_user)
    return APIResponse(message="Appointment completed successfully", data=updated)


@router.patch(
    "/{appointment_id}/status",
    response_model=APIResponse[AppointmentResponse],
    summary="Update Appointment Status",
)
async def update_appointment_status(
    appointment_id: str,
    request: UpdateAppointmentStatusRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Updates appointment status with validated lifecycle state machine transitions."""
    updated = await AppointmentService.update_status(db, appointment_id, request.status, current_user)
    return APIResponse(message=f"Appointment status updated to '{request.status.value}'", data=updated)


@router.post(
    "/{appointment_id}/check-in",
    response_model=APIResponse[AppointmentResponse],
    summary="Check-In Patient (Patient/Doctor/Staff/Admin)",
    dependencies=[Depends(require_roles(UserRole.PATIENT, UserRole.DOCTOR, UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN))],
)
async def check_in_patient(
    appointment_id: str,
    request: CheckInRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Performs patient check-in on appointment date, issuing a queue token and moving to queue."""
    updated = await AppointmentService.check_in_patient(db, appointment_id, request, current_user)
    return APIResponse(message="Patient checked in successfully", data=updated)


@router.post(
    "/{appointment_id}/call",
    response_model=APIResponse[AppointmentResponse],
    summary="Call Next Patient (Doctor/Staff/Admin)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN))],
)
@router.post(
    "/{appointment_id}/call-patient",
    response_model=APIResponse[AppointmentResponse],
    summary="Call Next Patient Alias (Doctor/Staff/Admin)",
    dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN))],
)
async def call_next_patient(
    appointment_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Advances appointment status from queue into consultation call state."""
    updated = await AppointmentService.call_next_patient(db, appointment_id, current_user)
    return APIResponse(message="Patient called into consultation", data=updated)


@router.post(
    "/{appointment_id}/reschedule",
    response_model=APIResponse[AppointmentResponse],
    summary="Reschedule Appointment",
)
async def reschedule_appointment(
    appointment_id: str,
    request: RescheduleAppointmentRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Reschedules an existing eligible appointment."""
    updated = await AppointmentService.reschedule_appointment(db, appointment_id, request, current_user)
    return APIResponse(message="Appointment rescheduled successfully", data=updated)


@router.post(
    "/{appointment_id}/cancel",
    response_model=APIResponse[AppointmentResponse],
    summary="Cancel Appointment",
)
async def cancel_appointment(
    appointment_id: str,
    request: CancelAppointmentRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Cancels an eligible appointment."""
    updated = await AppointmentService.cancel_appointment(db, appointment_id, request, current_user)
    return APIResponse(message="Appointment cancelled successfully", data=updated)


@router.get(
    "/{appointment_id}",
    response_model=APIResponse[AppointmentResponse],
    summary="Get Appointment Details",
)
async def get_appointment_detail(
    appointment_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetch appointment details with object-level authorization."""
    apt = await AppointmentService.get_appointment_by_id(db, appointment_id)

    if current_user.role == UserRole.PATIENT:
        patient = await PatientService.get_patient_by_user_id(db, current_user.user_id)
        if not patient or patient["patient_id"] != apt["patient_id"]:
            raise ForbiddenError("You are not authorized to view this appointment.")
    elif current_user.role == UserRole.DOCTOR:
        doctor = await AppointmentService.get_doctor_for_user(db, current_user)
        if not doctor or doctor["doctor_id"] != apt["doctor_id"]:
            raise ForbiddenError("You are not authorized to view this appointment.")

    return APIResponse(data=apt)

