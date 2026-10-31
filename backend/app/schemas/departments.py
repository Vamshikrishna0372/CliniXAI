"""Department request and response Pydantic schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.models.department import DepartmentStatus


# ── Request Schemas ────────────────────────────────────────────────────────────

class CreateDepartmentRequest(BaseModel):
    """Schema for Admin creating a new department."""
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=2, max_length=20, description="Short unique code e.g. 'CARD'")
    description: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=200)
    contact_extension: Optional[str] = Field(None, max_length=20)

    @classmethod
    def __get_validators__(cls):
        yield cls

    def model_post_init(self, __context) -> None:
        self.code = self.code.upper().strip()


class UpdateDepartmentRequest(BaseModel):
    """Schema for updating department fields."""
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=200)
    contact_extension: Optional[str] = Field(None, max_length=20)
    status: Optional[DepartmentStatus] = None


# ── Response Schemas ───────────────────────────────────────────────────────────

class DepartmentResponse(BaseModel):
    """Full department response."""
    department_id: str
    name: str
    code: str
    description: Optional[str] = None
    location: Optional[str] = None
    contact_extension: Optional[str] = None
    status: DepartmentStatus
    created_at: datetime
    updated_at: datetime


class DepartmentSummaryResponse(BaseModel):
    """Compact department card for list views."""
    department_id: str
    name: str
    code: str
    location: Optional[str] = None
    status: DepartmentStatus
