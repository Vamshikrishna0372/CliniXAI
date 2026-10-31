"""Follow-up request and response Pydantic schemas."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models.follow_up import FollowUpStatus


class CreateFollowUpRequest(BaseModel):
    """Schema for creating a new patient follow-up."""
    patient_id: str
    doctor_id: str
    consultation_id: Optional[str] = None
    appointment_id: Optional[str] = None
    scheduled_date: datetime
    reason: str = Field(..., min_length=2, max_length=500)
    notes: Optional[str] = Field(None, max_length=1000)


class UpdateFollowUpRequest(BaseModel):
    """Schema for updating follow-up status/details."""
    scheduled_date: Optional[datetime] = None
    reason: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=1000)
    status: Optional[FollowUpStatus] = None


class FollowUpResponse(BaseModel):
    """Public response model for follow-up details."""
    follow_up_id: str
    patient_id: str
    doctor_id: str
    consultation_id: Optional[str] = None
    appointment_id: Optional[str] = None
    scheduled_date: datetime
    reason: str
    notes: Optional[str] = None
    reminder_sent: bool
    status: FollowUpStatus
    created_at: datetime
    updated_at: datetime


class FollowUpListResponse(BaseModel):
    """Paginated response list for follow-ups."""
    total: int
    items: List[FollowUpResponse]
