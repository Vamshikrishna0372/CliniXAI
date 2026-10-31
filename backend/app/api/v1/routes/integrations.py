"""
External Integrations & Systems Operational Status API Routes for CliniXAI Phase 9.

Endpoints for:
- Google OAuth token exchange (`POST /api/v1/auth/google`)
- Google Calendar connection / disconnection (`POST /api/v1/integrations/google-calendar/connect`, `DELETE /api/v1/integrations/google-calendar`)
- Hospital directions & location configuration (`GET /api/v1/hospital/location`)
- Integration operational status overview (`GET /api/v1/integrations/status`)
"""

from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.dependencies.database import get_database
from app.dependencies.auth import get_current_active_user
from app.models.user import UserInDB
from app.schemas.integrations import (
    GoogleAuthRequest, GoogleAuthResponse, CalendarConnectRequest,
    CalendarStatusResponse, HospitalInfoResponse, SystemIntegrationsStatusResponse
)
from app.integrations.google_auth import GoogleAuthService
from app.integrations.google_calendar import GoogleCalendarService

router = APIRouter(tags=["External Integrations"])


# ── Google OAuth Endpoint ──────────────────────────────────────────────────

@router.post(
    "/auth/google",
    response_model=GoogleAuthResponse,
    summary="Authenticate via Google OAuth / OpenID Connect",
)
async def google_auth(
    request: GoogleAuthRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Exchanges verified Google OIDC ID token for CliniXAI JWT Access & Refresh Tokens.
    Performs safe account linking and default PATIENT role assignment for new users.
    """
    result = await GoogleAuthService.authenticate_google_user(db, request.id_token)
    return GoogleAuthResponse(**result)


# ── Google Calendar Endpoints ──────────────────────────────────────────────

@router.post(
    "/integrations/google-calendar/connect",
    summary="Connect Google Calendar Integration",
)
async def connect_google_calendar(
    request: CalendarConnectRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Stores user incremental authorization for Google Calendar sync."""
    return await GoogleCalendarService.connect_calendar(db, current_user.user_id, request.auth_code)


@router.delete(
    "/integrations/google-calendar",
    summary="Disconnect Google Calendar Integration",
)
async def disconnect_google_calendar(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Disconnects Google Calendar sync without modifying appointments."""
    return await GoogleCalendarService.disconnect_calendar(db, current_user.user_id)


# ── Hospital Location & Directions ─────────────────────────────────────────

@router.get(
    "/hospital/location",
    response_model=HospitalInfoResponse,
    summary="Get Hospital Location & Free Directions URL",
)
async def get_hospital_location():
    """Returns hospital address and free-first Google Maps directions link."""
    return HospitalInfoResponse(
        hospital_name=settings.HOSPITAL_NAME,
        address=settings.HOSPITAL_ADDRESS,
        directions_url=settings.HOSPITAL_DIRECTIONS_URL,
    )


# ── System Integrations Operational Status ─────────────────────────────────

@router.get(
    "/integrations/status",
    response_model=SystemIntegrationsStatusResponse,
    summary="Get System External Integrations Status",
)
async def get_integrations_status():
    """Returns non-sensitive operational status of optional external integrations."""
    return SystemIntegrationsStatusResponse(
        google_auth="configured" if GoogleAuthService.is_configured() else "unconfigured",
        google_calendar="enabled" if GoogleCalendarService.is_configured() else "disabled",
        email_delivery="configured" if settings.EMAIL_ENABLED else "disabled",
        storage_provider=settings.STORAGE_PROVIDER,
        hospital_info=HospitalInfoResponse(
            hospital_name=settings.HOSPITAL_NAME,
            address=settings.HOSPITAL_ADDRESS,
            directions_url=settings.HOSPITAL_DIRECTIONS_URL,
        ),
    )
