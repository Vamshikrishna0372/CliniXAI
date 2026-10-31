"""Audit Log API endpoint for Hospital Admin monitoring."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user
from app.models.user import UserInDB, UserRole
from app.core.exceptions import ForbiddenError
from app.schemas.audit_logs import AuditLogResponse, AuditLogListResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get(
    "",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Persistent Audit Logs",
    description="Inspect persistent security and operational audit logs for authenticated users (role-scoped).",
)
async def list_audit_logs(
    actor_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None, description="Start date ISO timestamp filter"),
    end_date: Optional[str] = Query(None, description="End date ISO timestamp filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> AuditLogListResponse:
    """Lists persistent audit log entries enforcing role-based scoping."""
    if current_user.role == UserRole.PATIENT:
        raise ForbiddenError("Patients are not authorized to access system audit logs.")
    service = AuditService(db)
    items, total = await service.list_audit_logs(
        actor_id=actor_id,
        action=action,
        resource=resource,
        start_date=start_date,
        end_date=end_date,
        current_user=current_user,
        skip=skip,
        limit=limit,
    )

    resp_items = [AuditLogResponse(**item.model_dump()) for item in items]
    return AuditLogListResponse(total=total, items=resp_items)
