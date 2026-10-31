"""Pydantic schemas for Phase 9 Integrations & QR endpoints."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, Field


from app.schemas.auth import UserResponse


# ── Google OAuth Schemas ───────────────────────────────────────────────────

class GoogleAuthRequest(BaseModel):
    """Google Sign-In request payload containing OpenID Connect ID token, credential, or auth code."""
    id_token: Optional[str] = Field(None, description="Google OIDC ID Token obtained from Google Identity Services")
    credential: Optional[str] = Field(None, description="Google credential JWT from GIS callback")
    code: Optional[str] = Field(None, description="OAuth authorization code if using code flow")
    redirect_uri: Optional[str] = Field(None, description="OAuth redirect URI matching the authorization request")


class GoogleAuthResponse(BaseModel):
    """Successful authentication response following Google Sign-In."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    email: str
    full_name: str
    expires_in: int = 1800
    user: Optional[UserResponse] = None


# ── Google Calendar Schemas ────────────────────────────────────────────────

class CalendarConnectRequest(BaseModel):
    """Google Calendar connection authorization code payload."""
    auth_code: str = Field(..., description="OAuth authorization code for Google Calendar access")


class CalendarStatusResponse(BaseModel):
    """Google Calendar integration status."""
    is_connected: bool
    connected_at: Optional[str] = None


# ── QR Schemas ─────────────────────────────────────────────────────────────

class QRTokenResponse(BaseModel):
    """Opaque QR token string response."""
    token: str
    payload: str
    created_at: str


class QRResolvePatientResponse(BaseModel):
    """Resolved Patient Health summary returned when hospital staff scans Patient QR."""
    patient_id: str
    user_id: str
    first_name: str
    last_name: str
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    contact_number: Optional[str] = None
    blood_group: Optional[str] = None


class QRCheckInRequest(BaseModel):
    """Check-In request payload containing scanned Appointment QR token."""
    token: str = Field(..., description="Scanned Appointment QR token or raw payload")


class QRCheckInResponse(BaseModel):
    """QR Check-In result."""
    message: str
    appointment_id: str
    patient_id: Optional[str] = None
    status: str
    queue_token: Optional[str] = None
    already_checked_in: bool = False


# ── Integration Status & Hospital Info Schemas ────────────────────────────

class HospitalInfoResponse(BaseModel):
    """Public Hospital location and directions metadata."""
    hospital_name: str
    address: str
    directions_url: str


class SystemIntegrationsStatusResponse(BaseModel):
    """System operational integration status overview."""
    google_auth: str          # "configured" / "unconfigured"
    google_calendar: str      # "enabled" / "disabled"
    email_delivery: str       # "configured" / "disabled"
    storage_provider: str     # "local" / "object"
    hospital_info: HospitalInfoResponse
