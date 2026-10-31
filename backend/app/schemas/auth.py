"""Authentication request and response Pydantic schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole, AccountStatus


class RegisterRequest(BaseModel):
    """Schema for public patient registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="User password (min 8 chars)")
    full_name: str = Field(..., min_length=2, max_length=100, description="User's full name")

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """Normalizes email by lowercasing and trimming whitespace."""
        return str(v).strip().lower()


class LoginRequest(BaseModel):
    """Schema for authentication login."""
    email: EmailStr
    password: str

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class UserResponse(BaseModel):
    """Public user profile details model returned in API responses."""
    user_id: str
    patient_id: Optional[str] = None
    doctor_id: Optional[str] = None
    email: str
    full_name: str
    role: UserRole
    email_verified: bool
    account_status: AccountStatus
    created_at: datetime
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    """Schema returned upon successful authentication or token refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiration duration in seconds")
    user: UserResponse


class RefreshRequest(BaseModel):
    """Schema for requesting new access and refresh tokens."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Schema for an authenticated password change."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    """Schema for requesting a password reset token."""
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class ResetPasswordRequest(BaseModel):
    """Schema for setting a new password using a reset token."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class EmailVerificationRequest(BaseModel):
    """Schema for requesting email verification token."""
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class EmailVerificationConfirmRequest(BaseModel):
    """Schema for confirming email verification using token."""
    token: str


class InviteUserRequest(BaseModel):
    """Schema for Hospital Admin inviting Doctor or Staff user."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()

    @field_validator("role", mode="after")
    @classmethod
    def validate_invite_role(cls, v: UserRole) -> UserRole:
        if v not in (UserRole.DOCTOR, UserRole.HOSPITAL_STAFF):
            raise ValueError("Invitations are allowed for 'doctor' or 'hospital_staff' roles only.")
        return v


class VerifyInvitationRequest(BaseModel):
    """Schema for verifying a provisioned invitation token."""
    token: str


class AcceptInvitationRequest(BaseModel):
    """Schema for accepting invitation and activating account with new password."""
    token: str
    password: str = Field(..., min_length=8, max_length=128, description="Set account password")


class TestEmailRequest(BaseModel):
    """Schema for requesting a test email dispatch (Admin-only diagnostic endpoint)."""
    to_email: EmailStr


