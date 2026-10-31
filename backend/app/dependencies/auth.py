"""FastAPI Authentication and Role-Based Access Control (RBAC) dependencies."""

from typing import Callable, Sequence
from fastapi import Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.security import decode_token
from app.database.collections import COLLECTION_USERS
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AccountStatus

from typing import Callable, Sequence, Optional
from fastapi import Depends, Query, Request, status

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    token_param: Optional[str] = Query(None, alias="token"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserInDB:
    """Extracts Bearer token from authorization header, cookie 'access_token', or query parameter 'token', decodes JWT, verifies active user account, and returns UserInDB."""
    token: Optional[str] = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif token_param:
        token = token_param
    elif request.cookies.get("access_token"):
        token = request.cookies.get("access_token")

    if not token:
        raise UnauthorizedError("Missing or invalid Bearer authorization token.")
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type. Expected access token.")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload: missing user subject.")

    user_dict = await db[COLLECTION_USERS].find_one({"user_id": user_id, "is_deleted": {"$ne": True}})
    if not user_dict:
        raise UnauthorizedError("User account associated with token no longer exists.")

    user = UserInDB(**user_dict)

    if user.account_status != AccountStatus.ACTIVE:
        raise ForbiddenError(f"Account status is '{user.account_status.value}'. Access denied.")

    return user


async def get_current_active_user(
    current_user: UserInDB = Depends(get_current_user),
) -> UserInDB:
    """Verifies that the current user is active."""
    return current_user


async def get_current_active_user_strict_header(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserInDB:
    """
    Strict authentication dependency: ONLY accepts Bearer token in Authorization header.
    Explicitly ignores and rejects URL query parameter '?token=' for sensitive endpoints (e.g. Grad-CAM).
    """
    token: Optional[str] = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials

    if not token:
        raise UnauthorizedError("Missing or invalid Bearer authorization token in request headers.")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type. Expected access token.")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload: missing user subject.")

    user_dict = await db[COLLECTION_USERS].find_one({"user_id": user_id, "is_deleted": {"$ne": True}})
    if not user_dict:
        raise UnauthorizedError("User account associated with token no longer exists.")

    user = UserInDB(**user_dict)
    if user.account_status != AccountStatus.ACTIVE:
        raise ForbiddenError(f"Account status is '{user.account_status.value}'. Access denied.")

    return user


def require_roles(*allowed_roles: UserRole) -> Callable:
    """Dependency factory enforcing that the authenticated user possesses one of the allowed roles.
    
    Example:
        @router.get("/admin-only", dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))])
    """
    async def role_checker(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
        user_role_norm = UserRole.normalize(current_user.role)
        allowed_roles_norm = [UserRole.normalize(r) for r in allowed_roles]
        if user_role_norm not in allowed_roles_norm:
            allowed_str = ", ".join([r.value for r in allowed_roles])
            raise ForbiddenError(
                f"Access denied for role '{current_user.role.value}'. Requires one of: [{allowed_str}]."
            )
        return current_user

    return role_checker
