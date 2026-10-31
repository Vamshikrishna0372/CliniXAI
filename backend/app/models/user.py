"""User model, role enums, and domain representations for CliniXAI."""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field

from app.utils.datetime import utc_now


class UserRole(str, Enum):
    """Core roles supported in CliniXAI with alias compatibility."""
    HOSPITAL_ADMIN = "hospital_admin"
    DOCTOR = "doctor"
    PATIENT = "patient"
    HOSPITAL_STAFF = "hospital_staff"
    ADMIN = "admin"
    STAFF = "staff"

    @classmethod
    def normalize(cls, role_val: Any) -> "UserRole":
        """Normalizes role string/enum to standard UserRole."""
        if isinstance(role_val, cls):
            role_str = role_val.value
        else:
            role_str = str(role_val).strip().lower()

        if role_str in ("admin", "hospital_admin"):
            return cls.HOSPITAL_ADMIN
        elif role_str in ("staff", "hospital_staff"):
            return cls.HOSPITAL_STAFF
        elif role_str == "doctor":
            return cls.DOCTOR
        elif role_str == "patient":
            return cls.PATIENT
        return cls(role_str)


class AuthProvider(str, Enum):
    """Authentication provider type."""
    LOCAL = "local"
    GOOGLE = "google"


class AccountStatus(str, Enum):
    """User account operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DISABLED = "disabled"
    PASSWORD_SETUP_REQUIRED = "password_setup_required"


class UserInDB(BaseModel):
    """Internal user document model stored in MongoDB `users` collection."""

    user_id: str
    email: str
    full_name: str
    password_hash: Optional[str] = None
    role: UserRole
    auth_provider: AuthProvider = AuthProvider.LOCAL
    google_sub: Optional[str] = None
    email_verified: bool = False
    account_status: AccountStatus = AccountStatus.ACTIVE
    
    # Cryptographic hashes for single-use email verification & password reset tokens
    email_verification_token_hash: Optional[str] = None
    email_verification_expires_at: Optional[datetime] = None
    password_reset_token_hash: Optional[str] = None
    password_reset_expires_at: Optional[datetime] = None
    invitation_token_hash: Optional[str] = None
    invitation_expires_at: Optional[datetime] = None

    # Soft Delete Audit Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_login_at: Optional[datetime] = None

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts user instance to dictionary format suitable for MongoDB insertion/update."""
        data = self.model_dump()
        return data

