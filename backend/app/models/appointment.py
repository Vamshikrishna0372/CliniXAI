"""Appointment domain model for CliniXAI.

Appointment document stores the full appointment lifecycle including
check-in metadata and queue position — no separate collections needed.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.utils.datetime import utc_now


class AppointmentStatus(str, Enum):
    """Controlled appointment status lifecycle."""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_QUEUE = "in_queue"
    IN_CONSULTATION = "in_consultation"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentType(str, Enum):
    """Appointment type options."""
    NEW_CONSULTATION = "new_consultation"
    FOLLOW_UP = "follow_up"


class BookingSource(str, Enum):
    """Who initiated the appointment booking."""
    PATIENT = "patient"
    HOSPITAL_STAFF = "hospital_staff"
    HOSPITAL_ADMIN = "hospital_admin"


class CheckInMethod(str, Enum):
    """How the check-in was performed."""
    MANUAL = "manual"       # Staff manual search + check-in
    QR = "qr"               # QR scan (Phase 6/9)


class CheckInData(BaseModel):
    """Nested check-in metadata embedded in appointment."""
    checked_in_at: Optional[datetime] = None
    checked_in_by: Optional[str] = None    # user_id of staff/admin
    method: CheckInMethod = CheckInMethod.MANUAL


class QueueData(BaseModel):
    """Nested queue metadata embedded in appointment."""
    token_number: Optional[str] = None     # Human-friendly daily token e.g. "A-012"
    position: Optional[int] = None         # Queue position (1-based)
    joined_at: Optional[datetime] = None
    called_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class CancellationData(BaseModel):
    """Nested cancellation metadata embedded in appointment."""
    cancelled_by: Optional[str] = None     # user_id
    cancelled_by_role: Optional[str] = None
    reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None


class RescheduleRecord(BaseModel):
    """Audit record for a single reschedule event."""
    previous_date: str                     # ISO date string
    previous_start_time: str
    previous_end_time: str
    rescheduled_by: str                    # user_id
    rescheduled_by_role: str
    rescheduled_at: datetime


class AppointmentInDB(BaseModel):
    """Internal appointment document stored in MongoDB `appointments` collection.

    Contains check-in and queue data as nested subdocuments.
    """

    appointment_id: str
    patient_id: str
    doctor_id: str
    department_id: str
    appointment_date: str                  # ISO date string "YYYY-MM-DD"
    start_time: str                        # "HH:MM" 24h
    end_time: str                          # "HH:MM" 24h
    reason: Optional[str] = None
    appointment_type: AppointmentType = AppointmentType.NEW_CONSULTATION
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
    booking_source: BookingSource = BookingSource.PATIENT
    check_in: CheckInData = Field(default_factory=CheckInData)
    queue: QueueData = Field(default_factory=QueueData)
    cancellation: Optional[CancellationData] = None
    reschedule_history: list = Field(default_factory=list)
    created_by: Optional[str] = None      # user_id of creator
    created_by_role: Optional[str] = None

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts appointment instance to MongoDB-ready dictionary."""
        return self.model_dump()


# Valid status transitions — centralized state machine
VALID_STATUS_TRANSITIONS: Dict[AppointmentStatus, list] = {
    AppointmentStatus.SCHEDULED: [
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    ],
    AppointmentStatus.CONFIRMED: [
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    ],
    AppointmentStatus.CHECKED_IN: [
        AppointmentStatus.IN_QUEUE,
        AppointmentStatus.CANCELLED,
    ],
    AppointmentStatus.IN_QUEUE: [
        AppointmentStatus.IN_CONSULTATION,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    ],
    AppointmentStatus.IN_CONSULTATION: [
        AppointmentStatus.COMPLETED,
    ],
    AppointmentStatus.COMPLETED: [],
    AppointmentStatus.CANCELLED: [],
    AppointmentStatus.NO_SHOW: [],
}

# Terminal statuses that cannot be modified
TERMINAL_STATUSES = {
    AppointmentStatus.COMPLETED,
    AppointmentStatus.CANCELLED,
    AppointmentStatus.NO_SHOW,
}

# Statuses eligible for rescheduling
RESCHEDULABLE_STATUSES = {
    AppointmentStatus.SCHEDULED,
    AppointmentStatus.CONFIRMED,
}

# Statuses eligible for cancellation
CANCELLABLE_STATUSES = {
    AppointmentStatus.SCHEDULED,
    AppointmentStatus.CONFIRMED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.IN_QUEUE,
}
