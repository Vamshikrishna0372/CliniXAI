"""Department Management API Routes for CliniXAI."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import UserInDB, UserRole
from app.models.department import DepartmentStatus
from app.schemas.departments import (
    CreateDepartmentRequest, UpdateDepartmentRequest,
    DepartmentResponse, DepartmentSummaryResponse
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.department_service import DepartmentService

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.post(
    "",
    response_model=APIResponse[DepartmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Department (Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def create_department(
    request: CreateDepartmentRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin creates a new hospital department."""
    dept = await DepartmentService.create_department(db, request, created_by_user_id=current_user.user_id)
    return APIResponse(message="Department created successfully", data=dept.model_dump())


@router.get(
    "",
    response_model=PaginatedResponse[DepartmentSummaryResponse],
    summary="List Departments",
)
async def list_departments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[DepartmentStatus] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Public/Authenticated department listing for discovery and operations."""
    docs, total = await DepartmentService.list_departments(
        db, page=page, page_size=page_size, status=status, search=search
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)
    return PaginatedResponse(data=docs, pagination=meta)


@router.get(
    "/{department_id}",
    response_model=APIResponse[DepartmentResponse],
    summary="Get Department Details",
)
async def get_department_detail(
    department_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetch department detail."""
    dept = await DepartmentService.get_department_by_id(db, department_id)
    return APIResponse(data=dept)


@router.patch(
    "/{department_id}",
    response_model=APIResponse[DepartmentResponse],
    summary="Update Department (Admin)",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def update_department(
    department_id: str,
    request: UpdateDepartmentRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Admin updates department details or soft status."""
    updated = await DepartmentService.update_department(
        db, department_id, request, updater_user_id=current_user.user_id
    )
    return APIResponse(message="Department updated successfully", data=updated)
