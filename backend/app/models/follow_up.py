"""Follow-up domain model for CliniXAI."""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.utils.datetime import utc_now


class FollowUpStatus(str, Enum):
    """Follow-up operational status."""
    SCHEDULED = "scheduled"
    UPCOMING = "upcoming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class FollowUpInDB(BaseModel):
    """Internal follow-up document model stored in MongoDB `follow_ups` collection."""

    follow_up_id: str
    patient_id: str
    doctor_id: str
    consultation_id: Optional[str] = None
    appointment_id: Optional[str] = None
    scheduled_date: datetime
    reason: str
    notes: Optional[str] = None
    reminder_sent: bool = False
    status: FollowUpStatus = FollowUpStatus.SCHEDULED

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts follow-up model to dictionary for MongoDB."""
        return self.model_dump()
