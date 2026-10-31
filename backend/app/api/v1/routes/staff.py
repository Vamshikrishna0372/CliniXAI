"""Hospital Staff Management API Routes for CliniXAI."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import UserInDB, UserRole
from app.models.staff import StaffStatus
from app.schemas.staff import (
    CreateStaffRequest, UpdateStaffRequest,
    StaffResponse, StaffSummaryResponse,
    StaffDashboardResponse
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.staff_service import StaffService
from app.core.exceptions import ResourceNotFoundError

router = APIRouter(prefix="/staff", tags=["Hospital Staff"])


@router.get(
    "/dashboard-overview",
    response_model=APIResponse[StaffDashboardResponse],
    summary="Get Staff Operational Dashboard Overview",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN))],
)
async def get_staff_dashboard_overview(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Returns real-time operational dashboard metrics for reception/front-desk staff.
    Computes today's appointments, waiting count, checked-in count, completed count,
    pending bills, collected revenue, upcoming appointments, active queue, and recent activity.
    """
    dashboard_data = await StaffService.get_operational_dashboard(db, current_user)
    return APIResponse(data=dashboard_data)


@router.get(
    "/me",
    response_model=APIResponse[StaffResponse],
    summary="Get Authenticated Staff Self Profile",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_STAFF))],
)
async def get_staff_me(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns staff profile associated with the logged-in staff user."""
    staff = await StaffService.get_staff_by_user_id(db, current_user.user_id)
    if not staff:
        raise ResourceNotFoundError("Staff profile for current user")
    return APIResponse(data=staff)


@router.patch(
    "/me",
    response_model=APIResponse[StaffResponse],
    summary="Update Authenticated Staff Self Profile",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_STAFF))],
)
async def update_staff_me(
    request: UpdateStaffRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Allows staff user to update allowed profile fields."""
    staff = await StaffService.get_staff_by_user_id(db, current_user.user_id)
    if not staff:
        raise ResourceNotFoundError("Staff profile for current user")

    request.status = None

    updated = await StaffService.update_staff(
        db, staff["staff_id"], request, updater_user_id=current_user.user_id
    )
    return APIResponse(message="Profile updated successfully", data=updated)


@router.post(
    "",
    response_model=APIResponse[StaffResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Provision Staff Account (Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def create_staff(
    request: CreateStaffRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin provisions a Hospital Staff profile and linked User account."""
    staff, raw_token = await StaffService.create_staff(
        db, request, admin_user_id=current_user.user_id
    )
    return APIResponse(message="Staff account created successfully", data=staff.model_dump())


@router.get(
    "",
    response_model=PaginatedResponse[StaffSummaryResponse],
    summary="List & Search Staff (Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def list_staff(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    department_id: Optional[str] = Query(default=None),
    status: Optional[StaffStatus] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Paginated staff list for admin management."""
    docs, total = await StaffService.list_staff(
        db, page=page, page_size=page_size, department_id=department_id,
        status=status, search=search
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=docs, pagination=meta)


@router.get(
    "/{staff_id}",
    response_model=APIResponse[StaffResponse],
    summary="Get Staff Details (Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def get_staff_detail(
    staff_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetch staff details."""
    staff = await StaffService.get_staff_by_id(db, staff_id)
    return APIResponse(data=staff)


@router.patch(
    "/{staff_id}",
    response_model=APIResponse[StaffResponse],
    summary="Update Staff Details (Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def update_staff(
    staff_id: str,
    request: UpdateStaffRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin updates staff profile details."""
    updated = await StaffService.update_staff(
        db, staff_id, request, updater_user_id=current_user.user_id
    )
    return APIResponse(message="Staff updated successfully", data=updated)
