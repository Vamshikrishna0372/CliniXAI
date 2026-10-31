"""Doctor request and response Pydantic schemas."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.doctor import DoctorStatus, DayOfWeek, DoctorSchedule, DaySchedule, TimeSlotBlock


# ── Request Schemas ────────────────────────────────────────────────────────────

class TimeSlotBlockSchema(BaseModel):
    """Input schema for a single time block."""
    start: str = Field(..., description="Start time HH:MM")
    end: str = Field(..., description="End time HH:MM")

    @field_validator("start", "end", mode="after")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("Time must be in HH:MM format")
        hh, mm = parts
        if not hh.isdigit() or not mm.isdigit():
            raise ValueError("Time must be in HH:MM format with numeric values")
        if not (0 <= int(hh) <= 23) or not (0 <= int(mm) <= 59):
            raise ValueError("Invalid hour or minute value")
        return v

    @model_validator(mode="after")
    def validate_start_before_end(self) -> "TimeSlotBlockSchema":
        if self.start >= self.end:
            raise ValueError(f"Start time '{self.start}' must be strictly earlier than end time '{self.end}'")
        return self


class DayScheduleSchema(BaseModel):
    """Input schema for a single day schedule."""
    day: DayOfWeek
    is_available: bool = True
    slots: List[TimeSlotBlockSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_no_overlapping_slots(self) -> "DayScheduleSchema":
        if not self.slots or len(self.slots) <= 1:
            return self
        # Convert to minutes and check for overlaps
        parsed_intervals = []
        for s in self.slots:
            sh, sm = [int(x) for x in s.start.split(":")]
            eh, em = [int(x) for x in s.end.split(":")]
            parsed_intervals.append((sh * 60 + sm, eh * 60 + em, s.start, s.end))
        
        parsed_intervals.sort(key=lambda x: x[0])
        for i in range(len(parsed_intervals) - 1):
            curr_start, curr_end, cs_str, ce_str = parsed_intervals[i]
            next_start, next_end, ns_str, ne_str = parsed_intervals[i + 1]
            if curr_end > next_start:
                raise ValueError(
                    f"Overlapping time intervals detected: '{cs_str}-{ce_str}' overlaps with '{ns_str}-{ne_str}'"
                )
        return self


class DoctorScheduleSchema(BaseModel):
    """Input schema for complete doctor weekly schedule."""
    slot_duration_minutes: int = Field(default=30, ge=5, le=120)
    weekly: List[DayScheduleSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_no_duplicate_days(self) -> "DoctorScheduleSchema":
        seen_days = set()
        for ds in self.weekly:
            day_val = ds.day.value if isinstance(ds.day, DayOfWeek) else str(ds.day).lower()
            if day_val in seen_days:
                raise ValueError(f"Duplicate schedule configuration found for day '{day_val}'")
            seen_days.add(day_val)
        return self


class CreateDoctorRequest(BaseModel):
    """Schema for Admin provisioning a new Doctor profile and linked user account."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    department_id: Optional[str] = None
    specialization: Optional[str] = Field(None, max_length=150)
    qualification: Optional[str] = Field(None, max_length=200)
    experience_years: Optional[int] = Field(None, ge=0, le=70)
    registration_number: Optional[str] = Field(None, max_length=100)
    consultation_fee: Optional[float] = Field(None, ge=0)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class UpdateDoctorRequest(BaseModel):
    """Schema for updating doctor profile fields (Admin or Doctor self-update)."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    department_id: Optional[str] = None
    specialization: Optional[str] = Field(None, max_length=150)
    qualification: Optional[str] = Field(None, max_length=200)
    experience_years: Optional[int] = Field(None, ge=0, le=70)
    registration_number: Optional[str] = Field(None, max_length=100)
    consultation_fee: Optional[float] = Field(None, ge=0)
    status: Optional[DoctorStatus] = None


class UpdateDoctorScheduleRequest(BaseModel):
    """Schema for updating a doctor's weekly schedule."""
    schedule: DoctorScheduleSchema


from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Any

# ── Response Schemas ───────────────────────────────────────────────────────────

def _normalize_name_dict(values: Any) -> Any:
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
            values["first_name"] = values.get("full_name") or "Doctor"
        if values.get("last_name") is None:
            values["last_name"] = ""
        if not values.get("full_name"):
            values["full_name"] = f"{values.get('first_name')} {values.get('last_name')}".strip()
        if not values.get("status"):
            values["status"] = "active"
    return values


class DoctorResponse(BaseModel):
    """Full doctor profile response."""
    doctor_id: str
    user_id: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    full_name: Optional[str] = ""
    email: str
    phone: Optional[str] = None
    department_id: Optional[str] = None
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    experience_years: Optional[int] = None
    registration_number: Optional[str] = None
    consultation_fee: Optional[float] = None
    schedule: Optional[DoctorScheduleSchema] = None
    status: DoctorStatus = DoctorStatus.ACTIVE
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def fill_name_defaults(cls, values: Any) -> Any:
        return _normalize_name_dict(values)


class DoctorPublicResponse(BaseModel):
    """Public-facing doctor profile (for patient discovery) — hides private fields."""
    doctor_id: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    full_name: Optional[str] = ""
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    experience_years: Optional[int] = None
    department_id: Optional[str] = None
    consultation_fee: Optional[float] = None
    status: DoctorStatus = DoctorStatus.ACTIVE

    @model_validator(mode="before")
    @classmethod
    def fill_name_defaults(cls, values: Any) -> Any:
        return _normalize_name_dict(values)


class DoctorSummaryResponse(BaseModel):
    """Compact doctor card for list views."""
    doctor_id: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    full_name: Optional[str] = ""
    email: str
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    experience_years: Optional[int] = None
    consultation_fee: Optional[float] = None
    department_id: Optional[str] = None
    status: DoctorStatus = DoctorStatus.ACTIVE

    @model_validator(mode="before")
    @classmethod
    def fill_name_defaults(cls, values: Any) -> Any:
        return _normalize_name_dict(values)


class AvailableSlot(BaseModel):
    """A single dynamically-calculated available appointment slot."""
    date: str                              # "YYYY-MM-DD"
    start_time: str                        # "HH:MM"
    end_time: str                          # "HH:MM"
    doctor_id: str
    is_available: bool = True


class DoctorAvailabilityResponse(BaseModel):
    """Response for doctor availability endpoint."""
    doctor_id: str
    date: str
    slot_duration_minutes: int
    available_slots: List[AvailableSlot]
    total_available: int
