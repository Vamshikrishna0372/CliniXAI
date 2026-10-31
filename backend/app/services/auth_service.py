"""Authentication and Authorization Business Logic Service."""

from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import (
    ResourceConflictError,
    UnauthorizedError,
    ForbiddenError,
    AppValidationError,
    ResourceNotFoundError,
)
from app.core.security import (
    hash_password,
    verify_password,
    validate_password_policy,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.database.collections import COLLECTION_USERS, COLLECTION_PATIENTS
from app.database.indexes import COLLECTION_USER_SESSIONS
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    InviteUserRequest,
)
from app.utils.id_generator import generate_user_id, generate_patient_id
from app.utils.tokens import generate_secure_token, hash_token, verify_token_hash
from app.utils.datetime import utc_now, ensure_utc


class AuthService:
    """Core Authentication service managing user registration, login, JWT token lifecycle,

    email verification, password resets, and session revocation.
    """

    @staticmethod
    async def register_patient(
        db: AsyncIOMotorDatabase, request: RegisterRequest
    ) -> Tuple[UserInDB, str, str]:
        """Registers a new patient account.
        
        Public registration strictly assigns the PATIENT role.
        """
        validate_password_policy(request.password)
        email = request.email.strip().lower()

        # Check duplicate email
        existing_user = await db[COLLECTION_USERS].find_one({"email": email})
        if existing_user:
            raise ResourceConflictError(f"An account with email '{email}' already exists.")

        user_id = generate_user_id()
        hashed_pwd = hash_password(request.password)

        user_doc = UserInDB(
            user_id=user_id,
            email=email,
            full_name=request.full_name,
            password_hash=hashed_pwd,
            role=UserRole.PATIENT,  # Strict Patient role override
            auth_provider=AuthProvider.LOCAL,
            email_verified=False,
            account_status=AccountStatus.ACTIVE,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        # Insert user document with duplicate key handling
        try:
            await db[COLLECTION_USERS].insert_one(user_doc.to_mongo_dict())
        except Exception as exc:
            if "duplicate" in str(exc).lower() or "E11000" in str(exc):
                raise ResourceConflictError(f"An account with email '{email}' already exists.")
            raise exc

        # Establish linked patient profile for referential integrity
        from app.models.patient import PatientStatus
        patient_doc = {
            "patient_id": generate_patient_id(),
            "user_id": user_id,
            "full_name": request.full_name,
            "email": email,
            "status": PatientStatus.ACTIVE.value,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await db[COLLECTION_PATIENTS].insert_one(patient_doc)

        try:
            from app.database.mongodb import save_in_memory_snapshot
            asyncio.create_task(save_in_memory_snapshot(db))
        except Exception:
            pass

        logger.info(f"Registered new Patient user: {user_id} ({email})")

        try:
            from app.services.audit_service import log_audit_event
            await log_audit_event(
                db=db,
                actor_id=user_id,
                role=user_doc.role.value,
                action="patient_registered",
                resource="user",
                resource_id=user_id,
                metadata={"email": email, "full_name": request.full_name},
            )
        except Exception:
            pass

        # Generate authentication tokens
        access_token = create_access_token(user_id=user_id, role=user_doc.role.value)
        refresh_token, jti, expires_at = create_refresh_token(user_id=user_id)

        # Persist refresh session
        await db[COLLECTION_USER_SESSIONS].insert_one({
            "jti": jti,
            "user_id": user_id,
            "expires_at": expires_at,
            "created_at": utc_now(),
        })

        return user_doc, access_token, refresh_token

    @staticmethod
    async def login_user(
        db: AsyncIOMotorDatabase, request: LoginRequest
    ) -> Tuple[UserInDB, str, str]:
        """Authenticates a user via email and password."""
        email = request.email.strip().lower()
        user_dict = await db[COLLECTION_USERS].find_one({"email": email, "is_deleted": {"$ne": True}})

        if not user_dict:
            try:
                from app.services.audit_service import log_audit_event
                await log_audit_event(
                    db=db,
                    actor_id="anonymous",
                    role="guest",
                    action="user_login_failed",
                    resource="auth",
                    metadata={"email": email, "reason": "user_not_found"},
                )
            except Exception:
                pass
            raise UnauthorizedError("Invalid email or password.")

        user = UserInDB(**user_dict)

        if user.auth_provider != AuthProvider.LOCAL or not user.password_hash:
            raise UnauthorizedError("Invalid authentication method for this account.")

        if not verify_password(request.password, user.password_hash):
            try:
                from app.services.audit_service import log_audit_event
                await log_audit_event(
                    db=db,
                    actor_id=user.user_id,
                    role=user.role.value,
                    action="user_login_failed",
                    resource="auth",
                    resource_id=user.user_id,
                    metadata={"email": email, "reason": "invalid_password"},
                )
            except Exception:
                pass
            raise UnauthorizedError("Invalid email or password.")

        if user.account_status != AccountStatus.ACTIVE:
            raise ForbiddenError(f"Account is {user.account_status.value}. Contact administration.")

        # Update last login timestamp
        now = utc_now()
        await db[COLLECTION_USERS].update_one(
            {"user_id": user.user_id},
            {"$set": {"last_login_at": now, "updated_at": now}}
        )
        user.last_login_at = now

        # Create JWT tokens
        access_token = create_access_token(user_id=user.user_id, role=user.role.value)
        refresh_token, jti, expires_at = create_refresh_token(user_id=user.user_id)

        # Save session
        await db[COLLECTION_USER_SESSIONS].insert_one({
            "jti": jti,
            "user_id": user.user_id,
            "expires_at": expires_at,
            "created_at": now,
        })

        logger.info(f"Successful login for user: {user.user_id} ({email})")

        try:
            from app.services.audit_service import log_audit_event
            await log_audit_event(
                db=db,
                actor_id=user.user_id,
                role=user.role.value,
                action="user_login_success",
                resource="auth",
                resource_id=user.user_id,
                metadata={"email": email},
            )
        except Exception:
            pass

        return user, access_token, refresh_token

    @staticmethod
    async def refresh_tokens(
        db: AsyncIOMotorDatabase, refresh_token_str: str
    ) -> Tuple[UserInDB, str, str]:
        """Validates a refresh token, verifies the active session, rotates refresh token, and returns new tokens."""
        payload = decode_token(refresh_token_str)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid token type. Expected refresh token.")

        user_id = payload.get("sub")
        jti = payload.get("jti")

        if not user_id or not jti:
            raise UnauthorizedError("Invalid refresh token claims.")

        # Check session validity in database
        session = await db[COLLECTION_USER_SESSIONS].find_one({"jti": jti, "user_id": user_id})
        if not session:
            raise UnauthorizedError("Refresh token has been revoked or expired.")

        # Revoke old session (Rotation)
        await db[COLLECTION_USER_SESSIONS].delete_one({"jti": jti})

        # Check user account
        user_dict = await db[COLLECTION_USERS].find_one({"user_id": user_id})
        if not user_dict:
            raise UnauthorizedError("User account no longer exists.")

        user = UserInDB(**user_dict)
        if user.account_status != AccountStatus.ACTIVE:
            raise ForbiddenError(f"Account is {user.account_status.value}.")

        # Generate new token pair
        new_access_token = create_access_token(user_id=user.user_id, role=user.role.value)
        new_refresh_token, new_jti, expires_at = create_refresh_token(user_id=user.user_id)

        # Save new session
        await db[COLLECTION_USER_SESSIONS].insert_one({
            "jti": new_jti,
            "user_id": user.user_id,
            "expires_at": expires_at,
            "created_at": utc_now(),
        })

        return user, new_access_token, new_refresh_token

    @staticmethod
    async def logout_user(db: AsyncIOMotorDatabase, refresh_token_str: str) -> bool:
        """Revokes the refresh token session associated with logout."""
        try:
            payload = decode_token(refresh_token_str)
            jti = payload.get("jti")
            if jti:
                await db[COLLECTION_USER_SESSIONS].delete_one({"jti": jti})
                logger.info(f"Revoked refresh session jti={jti}")
        except Exception:
            pass  # Fail gracefully on logout
        return True

    @staticmethod
    async def request_email_verification(db: AsyncIOMotorDatabase, email: str) -> str:
        """Generates a secure email verification token and stores its SHA-256 hash."""
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        expires_at = utc_now() + timedelta(hours=settings.VERIFICATION_TOKEN_EXPIRE_HOURS)

        user_dict = await db[COLLECTION_USERS].find_one({"email": email})
        if user_dict:
            await db[COLLECTION_USERS].update_one(
                {"email": email},
                {"$set": {
                    "email_verification_token_hash": token_hash,
                    "email_verification_expires_at": expires_at,
                    "updated_at": utc_now(),
                }}
            )
            # Dispatch Verification Email
            from app.services.email_service import EmailService
            verify_url = f"http://localhost:5173/verify-email?token={raw_token}"
            await EmailService.send_verification_email(
                to_email=email,
                recipient_name=user_dict.get("full_name", email),
                verify_url=verify_url,
            )

        # In dev mode, return raw_token for test suite verification
        return raw_token

    @staticmethod
    async def confirm_email_verification(db: AsyncIOMotorDatabase, raw_token: str) -> bool:
        """Validates email verification token and marks user's email as verified."""
        token_hash = hash_token(raw_token)
        user_dict = await db[COLLECTION_USERS].find_one({
            "email_verification_token_hash": token_hash,
        })

        if not user_dict:
            raise AppValidationError("Invalid or expired email verification token.")

        user = UserInDB(**user_dict)

        if user.email_verification_expires_at and user.email_verification_expires_at < utc_now():
            raise AppValidationError("Email verification token has expired.")

        await db[COLLECTION_USERS].update_one(
            {"user_id": user.user_id},
            {"$set": {
                "email_verified": True,
                "email_verification_token_hash": None,
                "email_verification_expires_at": None,
                "updated_at": utc_now(),
            }}
        )
        logger.info(f"Verified email for user {user.user_id}")
        return True

    @staticmethod
    async def request_password_reset(db: AsyncIOMotorDatabase, email: str) -> Optional[str]:
        """Generates a password reset token for the given email."""
        user_dict = await db[COLLECTION_USERS].find_one({"email": email})
        if not user_dict:
            return None  # Do not reveal email non-existence

        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        expires_at = utc_now() + timedelta(hours=settings.RESET_TOKEN_EXPIRE_HOURS)

        await db[COLLECTION_USERS].update_one(
            {"email": email},
            {"$set": {
                "password_reset_token_hash": token_hash,
                "password_reset_expires_at": expires_at,
                "updated_at": utc_now(),
            }}
        )

        # Dispatch Password Reset Email
        from app.services.email_service import EmailService
        reset_url = f"http://localhost:5173/reset-password?token={raw_token}"
        await EmailService.send_password_reset_email(
            to_email=email,
            recipient_name=user_dict.get("full_name", email),
            reset_url=reset_url,
        )

        return raw_token

    @staticmethod
    async def reset_password(db: AsyncIOMotorDatabase, raw_token: str, new_password: str) -> bool:
        """Resets user password using a valid reset token and invalidates active refresh sessions."""
        validate_password_policy(new_password)
        token_hash = hash_token(raw_token)

        user_dict = await db[COLLECTION_USERS].find_one({"password_reset_token_hash": token_hash})
        if not user_dict:
            raise AppValidationError("Invalid or expired password reset token.")

        user = UserInDB(**user_dict)
        if user.password_reset_expires_at and ensure_utc(user.password_reset_expires_at) < utc_now():
            raise AppValidationError("Password reset token has expired.")

        new_hash = hash_password(new_password)
        now = utc_now()

        await db[COLLECTION_USERS].update_one(
            {"user_id": user.user_id},
            {"$set": {
                "password_hash": new_hash,
                "password_reset_token_hash": None,
                "password_reset_expires_at": None,
                "updated_at": now,
            }}
        )

        # Invalidate all existing refresh sessions for security
        await db[COLLECTION_USER_SESSIONS].delete_many({"user_id": user.user_id})
        logger.info(f"Reset password and revoked sessions for user {user.user_id}")
        return True

    @staticmethod
    async def change_password(
        db: AsyncIOMotorDatabase, user_id: str, current_password: str, new_password: str
    ) -> bool:
        """Changes password for an authenticated user."""
        user_dict = await db[COLLECTION_USERS].find_one({"user_id": user_id})
        if not user_dict:
            raise ResourceNotFoundError("User")

        user = UserInDB(**user_dict)
        if not user.password_hash or not verify_password(current_password, user.password_hash):
            raise AppValidationError("Current password is incorrect.")

        validate_password_policy(new_password)
        new_hash = hash_password(new_password)

        await db[COLLECTION_USERS].update_one(
            {"user_id": user_id},
            {"$set": {"password_hash": new_hash, "updated_at": utc_now()}}
        )
        logger.info(f"Password changed for user {user_id}")
        return True

    @staticmethod
    async def invite_user(
        db: AsyncIOMotorDatabase, request: InviteUserRequest, admin_user: UserInDB
    ) -> Tuple[UserInDB, str]:
        """Hospital Admin workflow for inviting a new Doctor or Hospital Staff account."""
        email = request.email
        existing = await db[COLLECTION_USERS].find_one({"email": email})
        if existing:
            raise ResourceConflictError(f"Account with email '{email}' already exists.")

        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        expires_at = utc_now() + timedelta(days=7)

        user_id = generate_user_id()
        user_doc = UserInDB(
            user_id=user_id,
            email=email,
            full_name=request.full_name,
            password_hash=None,
            role=request.role,
            auth_provider=AuthProvider.LOCAL,
            email_verified=False,
            account_status=AccountStatus.INACTIVE,
            invitation_token_hash=token_hash,
            invitation_expires_at=expires_at,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        await db[COLLECTION_USERS].insert_one(user_doc.to_mongo_dict())
        logger.info(f"Admin {admin_user.user_id} invited {request.role.value} user: {user_id} ({email})")

        # Dispatch SMTP invitation email
        from app.services.email_service import EmailService
        activation_url = f"http://localhost:5173/accept-invitation?token={raw_token}"
        await EmailService.send_invitation_email(
            to_email=email,
            recipient_name=request.full_name,
            role_name=request.role.value,
            activation_url=activation_url,
        )

        return user_doc, raw_token

    @staticmethod
    async def verify_invitation_token(db: AsyncIOMotorDatabase, raw_token: str) -> Dict[str, Any]:
        """Validates an invitation token and returns recipient metadata."""
        token_hash = hash_token(raw_token)
        user_dict = await db[COLLECTION_USERS].find_one({"invitation_token_hash": token_hash})
        if not user_dict:
            raise AppValidationError("Invalid or expired invitation token.")

        user = UserInDB(**user_dict)
        if user.account_status == AccountStatus.DISABLED or user.is_deleted:
            raise AppValidationError("Account has been disabled and invitation is no longer valid.")
        if user.invitation_expires_at and ensure_utc(user.invitation_expires_at) < utc_now():
            raise AppValidationError("Invitation token has expired.")

        return {
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "user_id": user.user_id,
        }

    @staticmethod
    async def accept_invitation(
        db: AsyncIOMotorDatabase, raw_token: str, new_password: str
    ) -> Tuple[UserInDB, str, str]:
        """Activates an invited account, sets password hash, invalidates token, and returns JWT session."""
        validate_password_policy(new_password)
        token_hash = hash_token(raw_token)

        user_dict = await db[COLLECTION_USERS].find_one({"invitation_token_hash": token_hash})
        if not user_dict:
            raise AppValidationError("Invalid or expired invitation token.")

        user = UserInDB(**user_dict)
        if user.account_status == AccountStatus.DISABLED or user.is_deleted:
            raise AppValidationError("Account has been disabled and cannot be activated.")
        if user.invitation_expires_at and ensure_utc(user.invitation_expires_at) < utc_now():
            raise AppValidationError("Invitation token has expired.")

        new_hash = hash_password(new_password)
        now = utc_now()

        # Update user to active, verified status and revoke single-use invitation token
        await db[COLLECTION_USERS].update_one(
            {"user_id": user.user_id},
            {"$set": {
                "password_hash": new_hash,
                "account_status": AccountStatus.ACTIVE,
                "email_verified": True,
                "invitation_token_hash": None,
                "invitation_expires_at": None,
                "updated_at": now,
            }}
        )

        # Retrieve updated user
        updated_dict = await db[COLLECTION_USERS].find_one({"user_id": user.user_id})
        updated_user = UserInDB(**updated_dict)

        # Generate JWT session tokens
        access_token = create_access_token(user_id=user.user_id, role=updated_user.role.value)
        refresh_token, jti, expires_at = create_refresh_token(user_id=user.user_id)

        await db[COLLECTION_USER_SESSIONS].insert_one({
            "jti": jti,
            "user_id": user.user_id,
            "expires_at": expires_at,
            "created_at": now,
        })

        logger.info(f"Activated provisioned account for {user.user_id} ({user.email}) as {updated_user.role.value}")
        return updated_user, access_token, refresh_token

