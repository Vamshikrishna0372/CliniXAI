"""Unified Search API endpoint for multi-collection queries."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user
from app.models.user import UserInDB
from app.schemas.search import SearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Unified Multi-Resource Search",
    description="Search across backend resources (Patients, Doctors, Staff, Departments, Appointments, Consultations, Documents, etc.) with RBAC filtering.",
)
async def search_backend(
    q: str = Query(..., min_length=1, max_length=200, description="Search query string"),
    resource_type: Optional[List[str]] = Query(None, description="Target resource filters"),
    limit_per_resource: int = Query(10, ge=1, le=50),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> SearchResponse:
    """Executes backend search."""
    service = SearchService(db)
    return await service.search(
        query_str=q,
        user=current_user,
        resource_types=resource_type,
        limit_per_resource=limit_per_resource,
    )
