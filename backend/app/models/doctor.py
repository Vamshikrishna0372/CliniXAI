"""Doctor domain model for CliniXAI."""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.utils.datetime import utc_now


class DoctorStatus(str, Enum):
    """Doctor profile operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"


class DayOfWeek(str, Enum):
    """Day of week for schedule configuration."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class TimeSlotBlock(BaseModel):
    """A single availability block within a day (e.g., 09:00-13:00)."""
    start: str = Field(..., description="Start time in HH:MM 24h format, e.g. '09:00'")
    end: str = Field(..., description="End time in HH:MM 24h format, e.g. '13:00'")


class DaySchedule(BaseModel):
    """Doctor availability for a single weekday."""
    day: DayOfWeek
    is_available: bool = True
    slots: List[TimeSlotBlock] = Field(default_factory=list)


class DoctorSchedule(BaseModel):
    """Doctor's complete weekly schedule configuration."""
    slot_duration_minutes: int = Field(default=30, ge=5, le=120, description="Appointment slot duration in minutes")
    weekly: List[DaySchedule] = Field(default_factory=list)


class DoctorInDB(BaseModel):
    """Internal doctor document model stored in MongoDB `doctors` collection."""

    doctor_id: str
    user_id: str                           # Linked user account (required)
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    department_id: Optional[str] = None
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    experience_years: Optional[int] = None
    registration_number: Optional[str] = None
    consultation_fee: Optional[float] = None
    schedule: DoctorSchedule = Field(default_factory=DoctorSchedule)
    status: DoctorStatus = DoctorStatus.ACTIVE
    created_by: Optional[str] = None       # user_id of admin who provisioned

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts doctor instance to MongoDB-ready dictionary."""
        return self.model_dump()
