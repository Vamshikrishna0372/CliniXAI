"""Hospital Staff domain model for CliniXAI."""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.utils.datetime import utc_now


class StaffStatus(str, Enum):
    """Staff profile operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class StaffInDB(BaseModel):
    """Internal staff document model stored in MongoDB `staff` collection."""

    staff_id: str
    user_id: str                           # Linked user account (required)
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    department_id: Optional[str] = None
    job_title: Optional[str] = None        # e.g. "Receptionist", "Nurse", "Billing Clerk"
    employee_number: Optional[str] = None
    status: StaffStatus = StaffStatus.ACTIVE
    created_by: Optional[str] = None       # user_id of admin who provisioned

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts staff instance to MongoDB-ready dictionary."""
        return self.model_dump()
