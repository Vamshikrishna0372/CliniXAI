"""Patient domain model for CliniXAI."""

from enum import Enum
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field

from app.utils.datetime import utc_now


class PatientStatus(str, Enum):
    """Patient profile operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class Gender(str, Enum):
    """Patient gender options."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class BloodGroup(str, Enum):
    """Standard blood group options."""
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"
    UNKNOWN = "unknown"


class EmergencyContact(BaseModel):
    """Emergency contact nested document."""
    name: str
    relationship: str
    phone: str


class PatientAddress(BaseModel):
    """Patient address nested document."""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class PatientInDB(BaseModel):
    """Internal patient document model stored in MongoDB `patients` collection."""

    patient_id: str
    user_id: Optional[str] = None         # Linked user account (may be None for walk-in)
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    blood_group: Optional[BloodGroup] = None
    address: Optional[PatientAddress] = None
    emergency_contact: Optional[EmergencyContact] = None
    allergies: List[str] = Field(default_factory=list)
    status: PatientStatus = PatientStatus.ACTIVE
    registered_by: Optional[str] = None   # user_id of staff/admin who registered

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts patient instance to MongoDB-ready dictionary."""
        data = self.model_dump()
        # Convert date to string for MongoDB storage
        if data.get("date_of_birth") and isinstance(data["date_of_birth"], date):
            data["date_of_birth"] = data["date_of_birth"].isoformat()
        return data
