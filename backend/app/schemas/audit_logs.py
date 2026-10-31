"""Audit log response and query Pydantic schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """Response schema for persistent audit log entry."""
    audit_id: str
    actor_id: str
    role: str
    action: str
    resource: str
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime


class AuditLogListResponse(BaseModel):
    """Paginated list response for audit logs."""
    total: int
    items: List[AuditLogResponse]
