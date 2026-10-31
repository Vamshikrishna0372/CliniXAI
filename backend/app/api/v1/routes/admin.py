"""Hospital Admin API routes for CliniXAI Phase 19.

Comprehensive administrative workflows:
- Operational Dashboard Metrics (/admin/dashboard)
- User Account Lifecycle (/admin/users)
- Doctor Management (/admin/doctors)
- Staff Management (/admin/staff)
- Patient Operational Oversight (/admin/patients)
- Appointment Oversight & Cancellation (/admin/appointments)
- Billing Oversight (/admin/billing)
- Hospital Settings Management (/admin/settings)
- Multi-Collection Operational Search (/admin/search)
- Soft-Delete Management & Restoration (/admin/deleted, /admin/restore, /admin/permanent-delete)
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import UserInDB, UserRole, AccountStatus
from app.models.doctor import DoctorStatus
from app.models.staff import StaffStatus
from app.database.collections import ALL_COLLECTIONS
from app.core.exceptions import AppValidationError, NotFoundError, ForbiddenError, ResourceNotFoundError
from app.services.audit_service import log_audit_event
from app.services.admin_service import AdminService
from app.services.doctor_service import DoctorService
from app.services.staff_service import StaffService
from app.services.patient_service import PatientService
from app.services.appointment_service import AppointmentService
from app.services.billing_service import BillingService
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.schemas.admin import (
    AdminUserListItem,
    AdminUserDetailResponse,
    UpdateUserStatusRequest,
    AdminDashboardMetrics,
    HospitalSettingsResponse,
    UpdateHospitalSettingsRequest,
    AdminCancelAppointmentRequest,
    AdminDoctorStatusRequest,
    AdminStaffStatusRequest,
)
from app.schemas.doctors import CreateDoctorRequest, UpdateDoctorRequest, DoctorResponse, DoctorSummaryResponse
from app.schemas.staff import CreateStaffRequest, UpdateStaffRequest, StaffResponse, StaffSummaryResponse
from app.schemas.patients import PatientSummaryResponse
from app.schemas.appointments import AppointmentSummaryResponse
from app.schemas.billing import BillSummaryResponse
from app.utils.datetime import utc_now

router = APIRouter(prefix="/admin", tags=["Hospital Admin"])


# ── 1. Operational Dashboard ─────────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=APIResponse[AdminDashboardMetrics],
    status_code=status.HTTP_200_OK,
    summary="Get Authoritative Admin Dashboard Metrics",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def get_admin_dashboard(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> APIResponse[AdminDashboardMetrics]:
    """Returns aggregated real operational metrics, live alerts, and recent audit activity from MongoDB."""
    metrics = await AdminService.get_dashboard_metrics(db)
    return APIResponse(data=metrics)


# ── 2. User & Account Lifecycle Management ───────────────────────────────────

@router.get(
    "/users",
    response_model=PaginatedResponse[AdminUserListItem],
    status_code=status.HTTP_200_OK,
    summary="List & Search User Accounts",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name, email, or user_id"),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    status: Optional[AccountStatus] = Query(None, description="Filter by account status"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> PaginatedResponse[AdminUserListItem]:
    """Lists system user accounts with role, status, and text search. Excludes all secrets and token hashes."""
    skip = (page - 1) * page_size
    items, total = await AdminService.list_users(
        db, search=search, role=role, account_status=status, skip=skip, limit=page_size
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=items, pagination=meta)


@router.get(
    "/users/{user_id}",
    response_model=APIResponse[AdminUserDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Get User Account Details",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def get_user_detail(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[AdminUserDetailResponse]:
    """Inspects a user account and linked professional/patient profile."""
    detail = await AdminService.get_user_detail(db, user_id)
    return APIResponse(data=detail)


@router.patch(
    "/users/{user_id}/status",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Update User Account Lifecycle Status",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def update_user_status(
    user_id: str,
    request: UpdateUserStatusRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[Dict[str, Any]]:
    """Enables or disables a user account.

    Disabling automatically revokes all active sessions. Self-disable is prohibited.
    """
    updated = await AdminService.update_user_status(
        db, user_id=user_id, new_status=request.account_status, admin_user=current_user
    )
    return APIResponse(message=f"User account status updated to {request.account_status.value}.", data=updated)


@router.post(
    "/users/{user_id}/reinvite",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Resend Setup Invitation Token",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def reinvite_user(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[Dict[str, Any]]:
    """Regenerates and redispatches secure setup token for unverified or invited account."""
    res = await AdminService.reinvite_user(db, user_id=user_id, admin_user=current_user)
    return APIResponse(message="Setup invitation token redispatched successfully.", data=res)


# ── 3. Doctor Administration ─────────────────────────────────────────────────

@router.post(
    "/doctors",
    response_model=APIResponse[DoctorResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Provision Doctor Profile & Account",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def create_doctor(
    request: CreateDoctorRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[DoctorResponse]:
    """Admin provisions doctor account with secure invitation token and default weekly schedule."""
    doctor, raw_token = await DoctorService.create_doctor(db, request, admin_user_id=current_user.user_id)
    await log_audit_event(
        db=db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="DOCTOR_PROVISIONED",
        resource="doctors",
        resource_id=doctor.doctor_id,
        metadata={"email": doctor.email, "specialization": doctor.specialization},
    )
    return APIResponse(message="Doctor account provisioned successfully.", data=doctor.model_dump())


@router.get(
    "/doctors",
    response_model=PaginatedResponse[DoctorSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List Doctors (Admin View)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def list_doctors_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department_id: Optional[str] = Query(None),
    specialization: Optional[str] = Query(None),
    status: Optional[DoctorStatus] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> PaginatedResponse[DoctorSummaryResponse]:
    """Lists doctors for admin management."""
    docs, total = await DoctorService.list_doctors(
        db, page=page, page_size=page_size, department_id=department_id,
        specialization=specialization, status=status, search=search
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=docs, pagination=meta)


@router.get(
    "/doctors/{doctor_id}",
    response_model=APIResponse[DoctorResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Doctor Details (Admin View)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def get_doctor_detail_admin(
    doctor_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[DoctorResponse]:
    """Retrieves full doctor profile for admin."""
    doc = await DoctorService.get_doctor_by_id(db, doctor_id)
    return APIResponse(data=doc)


@router.patch(
    "/doctors/{doctor_id}",
    response_model=APIResponse[DoctorResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Doctor Profile Details",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def update_doctor_admin(
    doctor_id: str,
    request: UpdateDoctorRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[DoctorResponse]:
    """Updates permitted doctor profile fields with strict mass assignment protection."""
    updated = await DoctorService.update_doctor(db, doctor_id, request, updater_user_id=current_user.user_id)
    await log_audit_event(
        db=db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="DOCTOR_UPDATED",
        resource="doctors",
        resource_id=doctor_id,
    )
    return APIResponse(message="Doctor profile updated successfully.", data=updated)


@router.patch(
    "/doctors/{doctor_id}/status",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Toggle Doctor Activation Status",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def update_doctor_status_admin(
    doctor_id: str,
    request: AdminDoctorStatusRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[Dict[str, Any]]:
    """Activates or deactivates doctor account with synchronized user account state."""
    res = await AdminService.update_doctor_status(db, doctor_id, request.status, current_user)
    return APIResponse(message=f"Doctor status updated to {request.status}.", data=res)


# ── 4. Staff Administration ──────────────────────────────────────────────────

@router.post(
    "/staff",
    response_model=APIResponse[StaffResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Provision Staff Profile & Account",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def create_staff(
    request: CreateStaffRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[StaffResponse]:
    """Admin provisions staff account with secure invitation token."""
    staff, raw_token = await StaffService.create_staff(db, request, admin_user_id=current_user.user_id)
    await log_audit_event(
        db=db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="STAFF_PROVISIONED",
        resource="staff",
        resource_id=staff.staff_id,
        metadata={"email": staff.email, "job_title": staff.job_title},
    )
    return APIResponse(message="Staff account provisioned successfully.", data=staff.model_dump())


@router.get(
    "/staff",
    response_model=PaginatedResponse[StaffSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List Staff (Admin View)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def list_staff_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department_id: Optional[str] = Query(None),
    status: Optional[StaffStatus] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> PaginatedResponse[StaffSummaryResponse]:
    """Lists staff members for admin management."""
    docs, total = await StaffService.list_staff(
        db, page=page, page_size=page_size, department_id=department_id,
        status=status, search=search
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=docs, pagination=meta)


@router.get(
    "/staff/{staff_id}",
    response_model=APIResponse[StaffResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Staff Details (Admin View)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def get_staff_detail_admin(
    staff_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[StaffResponse]:
    """Retrieves staff member details for admin."""
    st = await StaffService.get_staff_by_id(db, staff_id)
    return APIResponse(data=st)


@router.patch(
    "/staff/{staff_id}",
    response_model=APIResponse[StaffResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Staff Profile Details",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def update_staff_admin(
    staff_id: str,
    request: UpdateStaffRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[StaffResponse]:
    """Updates permitted staff profile fields with strict mass assignment protection."""
    updated = await StaffService.update_staff(db, staff_id, request, updater_user_id=current_user.user_id)
    await log_audit_event(
        db=db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="STAFF_UPDATED",
        resource="staff",
        resource_id=staff_id,
    )
    return APIResponse(message="Staff profile updated successfully.", data=updated)


@router.patch(
    "/staff/{staff_id}/status",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Toggle Staff Activation Status",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def update_staff_status_admin(
    staff_id: str,
    request: AdminStaffStatusRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[Dict[str, Any]]:
    """Activates or deactivates staff account with synchronized user account state."""
    res = await AdminService.update_staff_status(db, staff_id, request.status, current_user)
    return APIResponse(message=f"Staff status updated to {request.status}.", data=res)


# ── 5. Patient Operational Oversight ─────────────────────────────────────────

@router.get(
    "/patients",
    response_model=PaginatedResponse[PatientSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Patient Operational Oversight Directory",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def list_patients_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> PaginatedResponse[PatientSummaryResponse]:
    """Lists patients for administrative oversight (demographic and registration view only)."""
    docs, total = await PatientService.list_patients(db, page=page, page_size=page_size, search=search)
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=docs, pagination=meta)


@router.get(
    "/patients/{patient_id}",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get Patient Operational Overview",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def get_patient_detail_admin(
    patient_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[Dict[str, Any]]:
    """Returns patient demographic and operational registration summary."""
    pat = await PatientService.get_patient_by_id(db, patient_id)
    if pat:
        pat = dict(pat)
        if "_id" in pat:
            pat["_id"] = str(pat["_id"])
    return APIResponse(data=pat)


# ── 6. Administrative Appointment Oversight ──────────────────────────────────

@router.get(
    "/appointments",
    response_model=PaginatedResponse[AppointmentSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List Appointments (Admin Oversight)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def list_appointments_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    doctor_id: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> PaginatedResponse[AppointmentSummaryResponse]:
    """Administrative appointment search and monitoring."""
    docs, total = await AppointmentService.list_appointments(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        patient_id=patient_id,
        doctor_id=doctor_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=docs, pagination=meta)


@router.patch(
    "/appointments/{appointment_id}/cancel",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Administrative Appointment Cancellation",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def cancel_appointment_admin(
    appointment_id: str,
    request: AdminCancelAppointmentRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[Dict[str, Any]]:
    """Administrative cancellation with reason and audit trail."""
    res = await AdminService.cancel_appointment(
        db, appointment_id=appointment_id, reason=request.reason, admin_user=current_user
    )
    return APIResponse(message="Appointment cancelled by administrator.", data=res)


# ── 7. Administrative Billing Oversight ──────────────────────────────────────

@router.get(
    "/billing",
    response_model=PaginatedResponse[BillSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List Hospital Invoices (Admin Oversight)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def list_billing_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    patient_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> PaginatedResponse[BillSummaryResponse]:
    """Administrative billing overview respecting Phase 16 financial invariants."""
    docs, total = await BillingService.list_bills(
        db, current_user=current_user, page=page, page_size=page_size, patient_id=patient_id, status=status
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=docs, pagination=meta)


# ── 8. Hospital Settings Management ──────────────────────────────────────────

@router.get(
    "/settings",
    response_model=APIResponse[HospitalSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Hospital Configuration Settings",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def get_hospital_settings(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[HospitalSettingsResponse]:
    """Retrieves persisted hospital settings from MongoDB. Strictly protects all system secrets."""
    settings_data = await AdminService.get_hospital_settings(db)
    return APIResponse(data=settings_data)


@router.patch(
    "/settings",
    response_model=APIResponse[HospitalSettingsResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Hospital Configuration Settings",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def update_hospital_settings(
    request: UpdateHospitalSettingsRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[HospitalSettingsResponse]:
    """Updates permitted hospital configuration settings. Audited."""
    settings_data = await AdminService.update_hospital_settings(db, request, admin_user=current_user)
    return APIResponse(message="Hospital settings updated successfully.", data=settings_data)


# ── 9. Operational Multi-Collection Search ───────────────────────────────────

@router.get(
    "/search",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Global Administrative Operational Search",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def admin_operational_search(
    q: str = Query(..., min_length=1, max_length=100, description="Search query string"),
    limit_per_resource: int = Query(10, ge=1, le=50),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> APIResponse[Dict[str, Any]]:
    """Role-aware global search across users, patients, doctors, staff, appointments, billing."""
    res = await AdminService.operational_search(db, q=q, limit_per_resource=limit_per_resource)
    return APIResponse(data=res)


# ── 10. Soft-Delete Management & Restoration ─────────────────────────────────

@router.get(
    "/deleted/{collection_name}",
    status_code=status.HTTP_200_OK,
    summary="List Soft-Deleted Records",
    description="Returns all soft-deleted records in the target collection. Hospital Admin only.",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def list_soft_deleted_records(
    collection_name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """Lists soft-deleted items in a collection."""
    if collection_name not in ALL_COLLECTIONS:
        raise AppValidationError(f"Invalid collection '{collection_name}'. Supported: {sorted(list(ALL_COLLECTIONS))}")

    query = {"is_deleted": True}
    total = await db[collection_name].count_documents(query)
    cursor = db[collection_name].find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)

    for doc in docs:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

    return {
        "collection": collection_name,
        "total_deleted": total,
        "items": docs
    }


@router.post(
    "/restore/{collection_name}/{resource_id}",
    status_code=status.HTTP_200_OK,
    summary="Restore Soft-Deleted Record",
    description="Restores a soft-deleted record in the target collection. Hospital Admin only.",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def restore_soft_deleted_record(
    collection_name: str,
    resource_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """Restores a soft-deleted record."""
    if collection_name not in ALL_COLLECTIONS:
        raise AppValidationError(f"Invalid collection '{collection_name}'.")

    pk_map = {
        "users": "user_id",
        "patients": "patient_id",
        "doctors": "doctor_id",
        "staff": "staff_id",
        "departments": "department_id",
        "appointments": "appointment_id",
        "consultations": "consultation_id",
        "prescriptions": "prescription_id",
        "medical_records": "record_id",
        "billing": "bill_id",
        "notifications": "notification_id",
        "ai_analyses": "analysis_id",
        "follow_ups": "follow_up_id",
        "payments": "payment_id",
        "documents": "document_id",
        "audit_logs": "audit_id",
        "hospital_settings": "setting_id",
    }
    pk_field = pk_map.get(collection_name, f"{collection_name[:-1]}_id")

    res = await db[collection_name].update_one(
        {pk_field: resource_id, "is_deleted": True},
        {"$set": {"is_deleted": False, "deleted_at": None, "deleted_by": None}}
    )

    if res.matched_count == 0:
        raise NotFoundError(f"Soft-deleted record '{resource_id}' in '{collection_name}' not found.")

    await log_audit_event(
        db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="RESTORE",
        resource=collection_name,
        resource_id=resource_id,
    )

    return {
        "message": f"Successfully restored '{resource_id}' in collection '{collection_name}'.",
        "resource_id": resource_id,
        "collection": collection_name,
    }


@router.delete(
    "/permanent-delete/{collection_name}/{resource_id}",
    status_code=status.HTTP_200_OK,
    summary="Permanently Delete Record",
    description="Permanently purges a record from the database. Requires Hospital Admin authorization.",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN))],
)
async def permanent_delete_record(
    collection_name: str,
    resource_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """Permanently deletes a record."""
    if collection_name not in ALL_COLLECTIONS:
        raise AppValidationError(f"Invalid collection '{collection_name}'.")

    pk_map = {
        "users": "user_id",
        "patients": "patient_id",
        "doctors": "doctor_id",
        "staff": "staff_id",
        "departments": "department_id",
        "appointments": "appointment_id",
        "consultations": "consultation_id",
        "prescriptions": "prescription_id",
        "medical_records": "record_id",
        "billing": "bill_id",
        "notifications": "notification_id",
        "ai_analyses": "analysis_id",
        "follow_ups": "follow_up_id",
        "payments": "payment_id",
        "documents": "document_id",
        "audit_logs": "audit_id",
        "hospital_settings": "setting_id",
    }
    pk_field = pk_map.get(collection_name, f"{collection_name[:-1]}_id")

    res = await db[collection_name].delete_one({pk_field: resource_id})
    if res.deleted_count == 0:
        raise NotFoundError(f"Record '{resource_id}' in '{collection_name}' not found.")

    await log_audit_event(
        db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="PERMANENT_DELETE",
        resource=collection_name,
        resource_id=resource_id,
    )

    return {
        "message": f"Permanently deleted record '{resource_id}' from '{collection_name}'.",
        "resource_id": resource_id,
        "collection": collection_name,
    }
