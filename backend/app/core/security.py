"""Security module for password hashing and JWT token creation/decoding."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AppValidationError, UnauthorizedError

# Passlib CryptContext for Bcrypt password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hashes a plaintext password securely using Bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against the stored hash."""
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_policy(password: str) -> None:
    """Validates that a password satisfies security policy requirements.
    
    Raises AppValidationError if requirements are not met.
    """
    if len(password) < 8:
        raise AppValidationError("Password must be at least 8 characters long.")
    if len(password) > 128:
        raise AppValidationError("Password exceeds maximum length of 128 characters.")


def create_access_token(user_id: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JWT Access Token containing user_id, role, type="access", and exp claims."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str, expires_delta: Optional[timedelta] = None) -> tuple[str, str, datetime]:
    """Creates a signed JWT Refresh Token containing user_id, type="refresh", and jti claims.
    
    Returns a tuple of (token_str, jti_str, expires_at_datetime).
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    jti = str(uuid.uuid4())
    payload: Dict[str, Any] = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expire


def decode_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT token.
    
    Raises UnauthorizedError if the signature is invalid or token has expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired.")
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(f"Invalid authentication token: {str(exc)}")
