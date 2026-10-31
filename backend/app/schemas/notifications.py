"""Notification Pydantic request and response schemas for CliniXAI Phase 17."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

from app.models.notification import (
    NotificationType, NotificationChannel, NotificationStatus,
    NotificationCategory, NotificationPriority
)


# ── Creation Schema ────────────────────────────────────────────────────────────

class CreateNotificationRequest(BaseModel):
    """Schema for programmatically dispatching a notification."""
    recipient_user_id: str
    notification_type: NotificationType
    channel: NotificationChannel = NotificationChannel.IN_APP
    title: str = Field(..., max_length=200)
    body: str = Field(..., max_length=1000)
    message: Optional[str] = None
    category: Optional[str] = "system"
    priority: Optional[str] = "normal"
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    actor_user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    dedupe_key: Optional[str] = None


# ── Response Schemas ───────────────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    """Full notification response object."""
    notification_id: str
    recipient_user_id: str
    user_id: Optional[str] = None
    notification_type: NotificationType
    type: Optional[str] = None
    category: str = "system"
    priority: str = "normal"
    channel: NotificationChannel = NotificationChannel.IN_APP
    status: NotificationStatus
    read: bool = False
    title: str
    body: str
    message: Optional[str] = None
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
    created_at: datetime
    updated_at: datetime


class NotificationSummaryResponse(BaseModel):
    """Compact notification card for inbox listing."""
    notification_id: str
    notification_type: NotificationType
    type: Optional[str] = None
    category: str = "system"
    priority: str = "normal"
    title: str
    body: str
    message: Optional[str] = None
    status: NotificationStatus
    read: bool = False
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    created_at: datetime

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return handler(source_type)

    @model_validator(mode="before")
    @classmethod
    def normalize_summary_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            nt = data.get("notification_type") or data.get("type")
            if nt and isinstance(nt, str):
                try:
                    NotificationType(nt)
                except ValueError:
                    data["notification_type"] = NotificationType.SYSTEM
            st = data.get("status")
            if st and isinstance(st, str):
                try:
                    NotificationStatus(st)
                except ValueError:
                    data["status"] = NotificationStatus.SENT
        return data


class UnreadCountResponse(BaseModel):
    """Authoritative unread notification count response from MongoDB."""
    unread_count: int
