"""Hospital Admin Schemas for CliniXAI Phase 19."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole, AccountStatus


class AdminUserListItem(BaseModel):
    """User summary item for admin user management."""
    user_id: str
    email: str
    full_name: str
    role: UserRole
    account_status: AccountStatus
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


class AdminUserDetailResponse(BaseModel):
    """Detailed user view for admin inspection (strictly no secret tokens or password hashes)."""
    user_id: str
    email: str
    full_name: str
    role: UserRole
    account_status: AccountStatus
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    profile: Optional[Dict[str, Any]] = None


class UpdateUserStatusRequest(BaseModel):
    """Payload for updating user account lifecycle state."""
    account_status: AccountStatus


class AdminDashboardMetrics(BaseModel):
    """Authoritative aggregated operational metrics for Hospital Admin."""
    total_patients: int
    active_doctors: int
    total_doctors: int
    active_staff: int
    total_staff: int
    active_users: int
    disabled_users: int
    password_setup_required_users: int
    today_appointments: int
    today_completed_consultations: int
    waiting_patients: int
    pending_appointments: int
    cancelled_appointments: int
    pending_bills: int
    collected_revenue: float
    today_revenue: float
    recent_activity: List[Dict[str, Any]] = Field(default_factory=list)
    operational_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    system_status: str = "operational"
    generated_at: datetime


class HospitalSettingsResponse(BaseModel):
    """Hospital system configuration."""
    setting_id: str
    hospital_name: str
    tagline: Optional[str] = None
    contact_email: str
    contact_phone: str
    emergency_number: str
    address: str
    opening_time: str
    closing_time: str
    appointment_slot_duration_minutes: int
    timezone: str
    currency: str
    total_bed_capacity: Optional[int] = 250
    emergency_contact: Optional[str] = None
    ai_auto_suggest: bool
    ai_confidence_threshold: int
    updated_at: datetime
    updated_by: Optional[str] = None


class UpdateHospitalSettingsRequest(BaseModel):
    """Payload for updating hospital configuration (strictly permitted fields only)."""
    hospital_name: Optional[str] = Field(None, min_length=2, max_length=200)
    tagline: Optional[str] = Field(None, max_length=200)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, min_length=5, max_length=30)
    emergency_number: Optional[str] = Field(None, min_length=5, max_length=30)
    emergency_contact: Optional[str] = Field(None, min_length=5, max_length=30)
    address: Optional[str] = Field(None, min_length=5, max_length=500)
    opening_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    closing_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    appointment_slot_duration_minutes: Optional[int] = Field(None, ge=10, le=120)
    timezone: Optional[str] = Field(None, max_length=50)
    currency: Optional[str] = Field(None, min_length=3, max_length=5)
    total_bed_capacity: Optional[int] = Field(None, ge=1, le=5000)
    ai_auto_suggest: Optional[bool] = None
    ai_confidence_threshold: Optional[int] = Field(None, ge=10, le=100)


class AdminCancelAppointmentRequest(BaseModel):
    """Payload for administrative cancellation of an appointment."""
    reason: str = Field(..., min_length=3, max_length=500)


class AdminDoctorStatusRequest(BaseModel):
    """Payload for toggling doctor account activation status."""
    status: str = Field(..., pattern=r"^(active|inactive)$")


class AdminStaffStatusRequest(BaseModel):
    """Payload for toggling staff account activation status."""
    status: str = Field(..., pattern=r"^(active|inactive)$")
