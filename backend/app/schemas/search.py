"""Unified search backend Pydantic schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    """Generic search match item from backend resources."""
    resource_type: str                  # e.g., "patient", "doctor", "appointment", "consultation", "document", etc.
    resource_id: str
    title: str
    subtitle: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Unified search API response payload."""
    query: str
    total_matches: int
    results: List[SearchResultItem]
