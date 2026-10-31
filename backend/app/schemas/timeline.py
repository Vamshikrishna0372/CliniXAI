"""Clinical Timeline aggregation response Pydantic schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    """Single chronological clinical event."""
    event_id: str
    event_type: str                     # e.g., "appointment", "check_in", "consultation", "prescription", "ai_analysis", "billing", "payment", "follow_up", "document"
    timestamp: datetime
    title: str
    description: Optional[str] = None
    actor_id: Optional[str] = None
    doctor_id: Optional[str] = None
    status: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    """Aggregated clinical timeline for a patient."""
    patient_id: str
    total_events: int
    events: List[TimelineEvent]
