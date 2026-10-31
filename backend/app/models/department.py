"""Department domain model for CliniXAI."""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.utils.datetime import utc_now


class DepartmentStatus(str, Enum):
    """Department operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class DepartmentInDB(BaseModel):
    """Internal department document model stored in MongoDB `departments` collection."""

    department_id: str
    name: str
    code: str                              # Short unique code e.g. "CARD", "NEURO"
    description: Optional[str] = None
    location: Optional[str] = None
    contact_extension: Optional[str] = None
    status: DepartmentStatus = DepartmentStatus.ACTIVE
    created_by: Optional[str] = None      # user_id of admin who created

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts department instance to MongoDB-ready dictionary."""
        return self.model_dump()
