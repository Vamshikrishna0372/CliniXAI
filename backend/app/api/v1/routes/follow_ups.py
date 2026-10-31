"""Follow-up API endpoints for scheduling, querying, and updating patient follow-ups."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import UserInDB, UserRole
from app.models.follow_up import FollowUpStatus
from app.schemas.follow_ups import (
    CreateFollowUpRequest, UpdateFollowUpRequest, FollowUpResponse, FollowUpListResponse
)
from app.services.follow_up_service import FollowUpService
from app.services.audit_service import log_audit_event
from app.core.exceptions import ForbiddenError

router = APIRouter(prefix="/follow-ups", tags=["Follow-ups"])


@router.post(
    "",
    response_model=FollowUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Patient Follow-up",
    description="Schedule a new follow-up appointment for a patient.",
)
async def create_follow_up(
    req: CreateFollowUpRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> FollowUpResponse:
    """Creates a new follow-up appointment."""
    service = FollowUpService(db)
    follow_up = await service.create_follow_up(req, actor_id=current_user.user_id)

    await log_audit_event(
        db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="FOLLOW_UP_CREATE",
        resource="follow_ups",
        resource_id=follow_up.follow_up_id,
    )

    return FollowUpResponse(**follow_up.model_dump())


@router.get(
    "",
    response_model=FollowUpListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Follow-ups",
    description="List follow-ups with optional patient, doctor, and status filtering.",
)
async def list_follow_ups(
    patient_id: Optional[str] = None,
    doctor_id: Optional[str] = None,
    status_val: Optional[FollowUpStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> FollowUpListResponse:
    """Lists follow-up records enforcing patient and doctor isolation."""
    if current_user.role == UserRole.PATIENT:
        pat = await db["patients"].find_one({"user_id": current_user.user_id})
        if pat:
            patient_id = pat["patient_id"]
        else:
            patient_id = current_user.user_id
    elif current_user.role == UserRole.DOCTOR:
        doc = await db["doctors"].find_one({"user_id": current_user.user_id})
        if doc:
            doctor_id = doc["doctor_id"]

    service = FollowUpService(db)
    items, total = await service.list_follow_ups(
        patient_id=patient_id,
        doctor_id=doctor_id,
        status=status_val,
        skip=skip,
        limit=limit,
    )

    resp_items = [FollowUpResponse(**item.model_dump()) for item in items]
    return FollowUpListResponse(total=total, items=resp_items)


@router.get(
    "/{follow_up_id}",
    response_model=FollowUpResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Follow-up Details",
)
async def get_follow_up(
    follow_up_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> FollowUpResponse:
    """Retrieves a single follow-up detail."""
    service = FollowUpService(db)
    item = await service.get_follow_up(follow_up_id)

    if current_user.role == UserRole.PATIENT:
        pat = await db["patients"].find_one({"user_id": current_user.user_id})
        target_pat_id = pat["patient_id"] if pat else current_user.user_id
        if item.patient_id != target_pat_id:
            raise ForbiddenError("You are not authorized to view this follow-up record.")
    elif current_user.role == UserRole.DOCTOR:
        doc = await db["doctors"].find_one({"user_id": current_user.user_id})
        target_doc_id = doc["doctor_id"] if doc else current_user.user_id
        if item.doctor_id != target_doc_id:
            raise ForbiddenError("You are not authorized to view this follow-up record.")

    return FollowUpResponse(**item.model_dump())


@router.put(
    "/{follow_up_id}",
    response_model=FollowUpResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Follow-up Record",
)
async def update_follow_up(
    follow_up_id: str,
    req: UpdateFollowUpRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> FollowUpResponse:
    """Updates follow-up details or status."""
    service = FollowUpService(db)
    updated = await service.update_follow_up(follow_up_id, req)

    await log_audit_event(
        db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="FOLLOW_UP_UPDATE",
        resource="follow_ups",
        resource_id=follow_up_id,
    )

    return FollowUpResponse(**updated.model_dump())


@router.delete(
    "/{follow_up_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft Delete Follow-up Record",
)
async def delete_follow_up(
    follow_up_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """Soft deletes follow-up record."""
    service = FollowUpService(db)
    await service.soft_delete_follow_up(follow_up_id, deleted_by=current_user.user_id)

    await log_audit_event(
        db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="FOLLOW_UP_DELETE",
        resource="follow_ups",
        resource_id=follow_up_id,
    )

    return {"message": f"Follow-up record '{follow_up_id}' soft-deleted."}
