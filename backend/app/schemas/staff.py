"""Hospital Staff request and response Pydantic schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.staff import StaffStatus


# ── Request Schemas ────────────────────────────────────────────────────────────

class CreateStaffRequest(BaseModel):
    """Schema for Admin provisioning a new Hospital Staff profile and linked user account."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    department_id: Optional[str] = None
    job_title: Optional[str] = Field(None, max_length=100)
    employee_number: Optional[str] = Field(None, max_length=50)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class UpdateStaffRequest(BaseModel):
    """Schema for updating staff profile fields (Admin or Staff self-update)."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    department_id: Optional[str] = None
    job_title: Optional[str] = Field(None, max_length=100)
    employee_number: Optional[str] = Field(None, max_length=50)
    status: Optional[StaffStatus] = None


from pydantic import model_validator
from typing import Any

# ── Response Schemas ───────────────────────────────────────────────────────────

def _normalize_staff_name_dict(values: Any) -> Any:
    if isinstance(values, dict):
        fn = values.get("full_name") or ""
        f_name = values.get("first_name")
        l_name = values.get("last_name")
        if fn and not f_name:
            parts = fn.split(" ")
            values["first_name"] = parts[0]
            values["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""
        elif (f_name or l_name) and not fn:
            values["full_name"] = f"{f_name or ''} {l_name or ''}".strip()
        if not values.get("first_name"):
            values["first_name"] = values.get("full_name") or "Staff"
        if values.get("last_name") is None:
            values["last_name"] = ""
        if not values.get("full_name"):
            values["full_name"] = f"{values.get('first_name')} {values.get('last_name')}".strip()
        if not values.get("status"):
            values["status"] = "active"
    return values


class StaffResponse(BaseModel):
    """Full staff profile response."""
    staff_id: str
    user_id: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    full_name: Optional[str] = ""
    email: str
    phone: Optional[str] = None
    department_id: Optional[str] = None
    job_title: Optional[str] = None
    employee_number: Optional[str] = None
    status: StaffStatus = StaffStatus.ACTIVE
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def fill_name_defaults(cls, values: Any) -> Any:
        return _normalize_staff_name_dict(values)


class StaffSummaryResponse(BaseModel):
    """Compact staff card for list views."""
    staff_id: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    full_name: Optional[str] = ""
    email: str
    job_title: Optional[str] = None
    department_id: Optional[str] = None
    status: StaffStatus = StaffStatus.ACTIVE

    @model_validator(mode="before")
    @classmethod
    def fill_name_defaults(cls, values: Any) -> Any:
        return _normalize_staff_name_dict(values)


class StaffDashboardMetrics(BaseModel):
    """Real-time hospital operational metrics for staff dashboard."""
    today_appointments: int = 0
    waiting_patients: int = 0
    checked_in_today: int = 0
    completed_consultations: int = 0
    pending_bills: int = 0
    today_collected_amount: float = 0.0
    total_registered_patients: int = 0


class StaffDashboardResponse(BaseModel):
    """Structured response for hospital staff operational dashboard."""
    metrics: StaffDashboardMetrics
    upcoming_appointments: list[dict[str, Any]] = []
    active_queue: list[dict[str, Any]] = []
    recent_activity: list[dict[str, Any]] = []
    operational_alerts: list[dict[str, Any]] = []

