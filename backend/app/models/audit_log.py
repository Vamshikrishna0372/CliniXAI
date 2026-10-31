"""Audit log domain model for tracking sensitive actions in CliniXAI."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.utils.datetime import utc_now


class AuditLogInDB(BaseModel):
    """Internal persistent audit log record stored in MongoDB `audit_logs` collection."""

    audit_id: str
    actor_id: str                          # user_id of actor performing action
    role: str                              # role of actor
    action: str                            # e.g., "LOGIN", "LOGOUT", "PATIENT_CREATE", "APPOINTMENT_CANCEL", "AI_ANALYSIS_SUBMIT"
    resource: str                          # e.g., "users", "patients", "appointments", "documents", "ai_analyses"
    resource_id: Optional[str] = None      # Target entity ID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts audit log model to dictionary for MongoDB."""
        return self.model_dump()
