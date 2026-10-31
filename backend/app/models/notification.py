"""Notification domain model for CliniXAI Phase 17."""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

from app.utils.datetime import utc_now


class NotificationType(str, Enum):
    """Categorized notification types."""
    # Appointments
    APPOINTMENT = "appointment"
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    APPOINTMENT_CHECKED_IN = "appointment_checked_in"
    APPOINTMENT_COMPLETED = "appointment_completed"
    APPOINTMENT_NO_SHOW = "appointment_no_show"
    APPOINTMENT_REMINDER = "appointment_reminder"
    CHECKIN_SUCCESS = "checkin_success"

    # Consultations
    CLINICAL = "clinical"
    CONSULTATION_STARTED = "consultation_started"
    CONSULTATION_COMPLETED = "consultation_completed"
    CONSULTATION_CANCELLED = "consultation_cancelled"
    CONSULTATION_FINALIZED = "consultation_finalized"

    # Prescriptions
    PRESCRIPTION_ISSUED = "prescription_issued"
    PRESCRIPTION_CREATED = "prescription_created"
    PRESCRIPTION_CANCELLED = "prescription_cancelled"

    # Billing & Payments
    BILLING = "billing"
    BILL_ISSUED = "bill_issued"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_COMPLETED = "payment_completed"
    PAYMENT_VOIDED = "payment_voided"

    # AI & Clinical Intelligence
    AI_ANALYSIS_COMPLETED = "ai_analysis_completed"
    AI_REVIEW_REQUIRED = "ai_review_required"
    MEDICAL_RECORD_UPLOADED = "medical_record_uploaded"

    # Follow-ups
    FOLLOW_UP = "follow_up"
    FOLLOW_UP_SCHEDULED = "follow_up_scheduled"
    FOLLOW_UP_REMINDER = "follow_up_reminder"
    FOLLOW_UP_COMPLETED = "follow_up_completed"

    # System & Account
    SYSTEM = "system"


class NotificationChannel(str, Enum):
    """Delivery channel for notification."""
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"


class NotificationStatus(str, Enum):
    """Delivery/read status."""
    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    FAILED = "failed"


class NotificationCategory(str, Enum):
    """High-level notification category for grouping and filtering."""
    APPOINTMENT = "appointment"
    CONSULTATION = "consultation"
    PRESCRIPTION = "prescription"
    BILLING = "billing"
    AI = "ai"
    CLINICAL = "clinical"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    """Notification urgency priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationInDB(BaseModel):
    """Internal notification document stored in MongoDB `notifications` collection."""

    notification_id: str
    recipient_user_id: str
    user_id: Optional[str] = None
    notification_type: NotificationType
    type: Optional[str] = None
    category: str = "system"
    priority: str = "normal"
    channel: NotificationChannel = NotificationChannel.IN_APP
    status: NotificationStatus = NotificationStatus.SENT
    read: bool = False

    title: str = Field(..., max_length=200)
    body: str = Field(..., max_length=1000)
    message: Optional[str] = None

    # Reference / Source / Entity links
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None

    actor_user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    dedupe_key: Optional[str] = None

    read_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def sync_aliases(self) -> "NotificationInDB":
        """Synchronizes alias fields for dual compatibility."""
        if not self.user_id:
            self.user_id = self.recipient_user_id
        if not self.type:
            self.type = self.notification_type.value if hasattr(self.notification_type, "value") else str(self.notification_type)
        if not self.message:
            self.message = self.body
        if not self.source_id and self.reference_id:
            self.source_id = self.reference_id
        if not self.source_type and self.reference_type:
            self.source_type = self.reference_type
        if not self.entity_id and self.source_id:
            self.entity_id = self.source_id
        if not self.entity_type and self.source_type:
            self.entity_type = self.source_type
        if not self.reference_id and self.source_id:
            self.reference_id = self.source_id
        if not self.reference_type and self.source_type:
            self.reference_type = self.source_type
        if self.status == NotificationStatus.READ:
            self.read = True
        elif self.read:
            self.status = NotificationStatus.READ
        return self

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts notification instance to MongoDB-ready dictionary."""
        return self.model_dump()
