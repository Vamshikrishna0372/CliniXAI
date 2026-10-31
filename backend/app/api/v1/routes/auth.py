"""Authentication API Version 1 Route Handlers."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from app.core.logging import logger
from app.core.exceptions import AppValidationError
from app.schemas.integrations import GoogleAuthRequest, GoogleAuthResponse
from app.integrations.google_auth import GoogleAuthService
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import UserInDB, UserRole
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    RefreshRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    EmailVerificationRequest,
    EmailVerificationConfirmRequest,
    InviteUserRequest,
    VerifyInvitationRequest,
    AcceptInvitationRequest,
    TestEmailRequest,
)
from app.schemas.common import MessageResponse, APIResponse
from app.services.auth_service import AuthService
from app.services.email_service import EmailService

router = APIRouter(prefix="/auth", tags=["Authentication & Security"])


async def _build_user_response(db: AsyncIOMotorDatabase, user: UserInDB) -> UserResponse:
    """Builds a UserResponse with populated patient_id or doctor_id."""
    data = user.model_dump()
    if user.role == UserRole.PATIENT:
        from app.database.collections import COLLECTION_PATIENTS
        patient = await db[COLLECTION_PATIENTS].find_one({"user_id": user.user_id})
        if patient:
            data["patient_id"] = patient.get("patient_id")
    elif user.role == UserRole.DOCTOR:
        from app.database.collections import COLLECTION_DOCTORS
        doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": user.user_id})
        if not doctor and getattr(user, "email", None):
            doctor = await db[COLLECTION_DOCTORS].find_one({"email": user.email})
        if not doctor:
            doctor = await db[COLLECTION_DOCTORS].find_one({"doctor_id": user.user_id})
        if doctor:
            data["doctor_id"] = doctor.get("doctor_id")
    return UserResponse(**data)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Public Patient Registration",
    description="Registers a new Patient user. Public registration strictly enforces the Patient role.",
)
async def register_patient(
    request: RegisterRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TokenResponse:
    """Public Patient registration endpoint."""
    user, access_token, refresh_token = await AuthService.register_patient(db, request)
    user_resp = await _build_user_response(db, user)

    # Set secure HttpOnly cookies for browser clients
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=not settings.DEBUG,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        samesite="lax",
        secure=not settings.DEBUG,
        path="/",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_resp,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticates email and password, returning JWT access and refresh tokens.",
)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TokenResponse:
    """User authentication login endpoint."""
    user, access_token, refresh_token = await AuthService.login_user(db, request)
    user_resp = await _build_user_response(db, user)

    # Set secure HttpOnly cookies for browser clients
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=not settings.DEBUG,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        samesite="lax",
        secure=not settings.DEBUG,
        path="/",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_resp,
    )




def _get_frontend_url(request: Request) -> str:
    """Dynamically resolves frontend origin based on request headers / environment."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        if "clini-xai.vercel.app" in origin or "vercel.app" in origin:
            return "https://clini-xai.vercel.app"
        if "localhost:3100" in origin or "127.0.0.1:3100" in origin:
            return "http://localhost:3100"
    host = request.headers.get("host", "").lower()
    if "onrender.com" in host or "clinixai" in host:
        return "https://clini-xai.vercel.app"
    return settings.FRONTEND_URL or "http://localhost:3100"


@router.post(
    "/google",
    response_model=GoogleAuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate via Google OAuth / OpenID Connect",
    description="Exchanges Google ID token, credential, or authorization code for CliniXAI tokens and Patient session.",
)
async def google_auth_post(
    request: GoogleAuthRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> GoogleAuthResponse:
    """Authenticates via Google OIDC ID token or exchanges authorization code."""
    id_token = request.id_token or request.credential
    if not id_token and request.code:
        token_data = await GoogleAuthService.exchange_code_for_tokens(
            request.code, request.redirect_uri
        )
        id_token = token_data.get("id_token")

    if not id_token:
        raise AppValidationError("Missing Google ID token, credential, or authorization code.")

    result = await GoogleAuthService.authenticate_google_user(db, id_token)

    # Set secure HttpOnly cookies for browser clients
    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=not settings.DEBUG,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        samesite="lax",
        secure=not settings.DEBUG,
        path="/",
    )

    return GoogleAuthResponse(**result)


@router.post(
    "/google/callback",
    response_model=GoogleAuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Google OAuth POST Callback Alias",
    include_in_schema=False,
)
async def google_auth_callback_post(
    request: GoogleAuthRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> GoogleAuthResponse:
    """Alias for POST /auth/google."""
    return await google_auth_post(request, response, db)


@router.get(
    "/google/callback",
    summary="Google OAuth Redirect GET Callback",
    description="Receives authorization code from Google OAuth redirect, issues CliniXAI tokens, and redirects to frontend.",
)
async def google_auth_callback_get(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Processes browser redirect callback from Google OAuth."""
    frontend_url = _get_frontend_url(request)

    if error:
        logger.warning(f"Google OAuth redirect error: {error}")
        return RedirectResponse(
            url=f"{frontend_url}/auth/login?error=Google+authentication+cancelled+or+failed.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if not code:
        return RedirectResponse(
            url=f"{frontend_url}/auth/login?error=Missing+authorization+code+from+Google.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        req_redirect_uri = str(request.url).split("?")[0]
        token_data = await GoogleAuthService.exchange_code_for_tokens(code, req_redirect_uri)
        id_token = token_data.get("id_token")
        if not id_token:
            raise AppValidationError("Google did not return an ID token.")

        result = await GoogleAuthService.authenticate_google_user(db, id_token)

        redirect_target = f"{frontend_url}/auth/login?google_success=true&access_token={result['access_token']}&refresh_token={result['refresh_token']}"
        redirect_res = RedirectResponse(url=redirect_target, status_code=status.HTTP_303_SEE_OTHER)

        redirect_res.set_cookie(
            key="access_token",
            value=result["access_token"],
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax",
            secure=not settings.DEBUG,
            path="/",
        )
        redirect_res.set_cookie(
            key="refresh_token",
            value=result["refresh_token"],
            httponly=True,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            samesite="lax",
            secure=not settings.DEBUG,
            path="/",
        )
        return redirect_res
    except Exception as exc:
        logger.error(f"Google OAuth callback processing error: {exc}")
        return RedirectResponse(
            url=f"{frontend_url}/auth/login?error=Google+sign-in+failed.+Please+try+again.",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get(
    "/google/login",
    summary="Initiate Google OAuth Redirect Flow",
    description="Redirects browser to Google OAuth consent screen with correct client_id, scope, and redirect_uri.",
)
async def google_auth_login_redirect(request: Request):
    """Initiates Google OAuth 2.0 authorization code redirect."""
    if not settings.GOOGLE_CLIENT_ID:
        raise AppValidationError("Google Client ID is not configured on the server.")

    host = request.headers.get("host", "").lower()
    if "onrender.com" in host or "clinixai" in host:
        redirect_uri = "https://clinixai-2qfy.onrender.com/api/v1/auth/google/callback"
    else:
        redirect_uri = settings.GOOGLE_REDIRECT_URI or "http://localhost:8000/api/v1/auth/google/callback"

    from urllib.parse import urlencode
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    google_oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=google_oauth_url, status_code=status.HTTP_303_SEE_OTHER)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Authentication Tokens",
    description="Exchanges a valid refresh token for a new access token and rotated refresh token.",
)
async def refresh_token(
    req: Request,
    response: Response,
    request: Optional[RefreshRequest] = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TokenResponse:
    """JWT Refresh token endpoint."""
    token_str = (request.refresh_token if request and request.refresh_token else None) or req.cookies.get("refresh_token")
    if not token_str:
        from app.core.exceptions import UnauthorizedError
        raise UnauthorizedError("Missing refresh token in request body or cookie.")

    user, access_token, new_refresh_token = await AuthService.refresh_tokens(db, token_str)
    user_resp = await _build_user_response(db, user)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=not settings.DEBUG,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        samesite="lax",
        secure=not settings.DEBUG,
        path="/",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_resp,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile",
    description="Returns authenticated user's profile details.",
)
async def get_me(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserResponse:
    """Returns profile for currently authenticated user."""
    return await _build_user_response(db, current_user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Revokes the active refresh token session.",
)
async def logout(
    req: Request,
    response: Response,
    request: Optional[RefreshRequest] = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    """Logout and session revocation endpoint."""
    token_str = (request.refresh_token if request and request.refresh_token else None) or req.cookies.get("refresh_token")
    if token_str:
        await AuthService.logout_user(db, token_str)

    # Clear HttpOnly cookies
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")

    # Proactively close active WebSocket connections for the logging out user
    access_tok = req.cookies.get("access_token")
    if not access_tok:
        auth_hdr = req.headers.get("authorization")
        if auth_hdr and auth_hdr.lower().startswith("bearer "):
            access_tok = auth_hdr[7:].strip()
    if access_tok:
        try:
            from app.core.security import decode_token
            from app.core.websocket_manager import manager
            payload = decode_token(access_tok)
            uid = payload.get("sub")
            if uid:
                await manager.close_user_connections(uid, code=1000, reason="Logged out")
        except Exception:
            pass

    return MessageResponse(success=True, message="Successfully logged out.")


@router.post(
    "/password/change",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change Password",
    description="Changes password for the currently authenticated user.",
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    """Authenticated user password change endpoint."""
    await AuthService.change_password(
        db,
        user_id=current_user.user_id,
        current_password=request.current_password,
        new_password=request.new_password,
    )
    return MessageResponse(success=True, message="Password successfully updated.")


@router.post(
    "/password/forgot",
    response_model=APIResponse[Dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="Request Password Reset",
    description="Generates a password reset token.",
)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> APIResponse[Dict[str, str]]:
    """Password reset token generation endpoint."""
    raw_token = await AuthService.request_password_reset(db, request.email)
    msg = "If the account exists, a password reset token has been generated."
    data = {"reset_token": raw_token} if raw_token and settings.DEBUG else None
    return APIResponse(success=True, message=msg, data=data)


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset Password with Token",
    description="Sets a new password using a valid reset token.",
)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    """Password reset endpoint."""
    await AuthService.reset_password(db, raw_token=request.token, new_password=request.new_password)
    return MessageResponse(success=True, message="Password successfully reset. Please log in with your new password.")


@router.post(
    "/email-verification/request",
    response_model=APIResponse[Dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="Request Email Verification Token",
    description="Generates an email verification token for the requested email.",
)
async def request_email_verification(
    request: EmailVerificationRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> APIResponse[Dict[str, str]]:
    """Email verification token generation endpoint."""
    raw_token = await AuthService.request_email_verification(db, request.email)
    msg = "An email verification token has been generated."
    data = {"verification_token": raw_token} if settings.DEBUG else None
    return APIResponse(success=True, message=msg, data=data)


@router.post(
    "/email-verification/confirm",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm Email Verification",
    description="Confirms email verification using token.",
)
async def confirm_email_verification(
    request: EmailVerificationConfirmRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    """Email verification confirmation endpoint."""
    await AuthService.confirm_email_verification(db, raw_token=request.token)
    return MessageResponse(success=True, message="Email address successfully verified.")


@router.post(
    "/invite",
    response_model=APIResponse[Dict[str, str]],
    status_code=status.HTTP_201_CREATED,
    summary="Invite Doctor or Staff User",
    description="Hospital Admin endpoint for inviting new Doctor or Hospital Staff accounts.",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def invite_user(
    request: InviteUserRequest,
    admin_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> APIResponse[Dict[str, str]]:
    """Hospital Admin user invitation endpoint."""
    invited_user, raw_token = await AuthService.invite_user(db, request, admin_user)
    return APIResponse(
        success=True,
        message=f"Invitation created for {request.role.value} account.",
        data={
            "user_id": invited_user.user_id,
            "email": invited_user.email,
            "invitation_token": raw_token if settings.DEBUG else "[hidden]",
        },
    )


@router.post(
    "/invitation/verify",
    response_model=APIResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Verify Invitation Token",
    description="Verifies a provisioned Doctor or Staff invitation token and returns recipient metadata.",
)
async def verify_invitation(
    request: VerifyInvitationRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> APIResponse[Dict[str, Any]]:
    """Invitation token verification endpoint."""
    info = await AuthService.verify_invitation_token(db, request.token)
    return APIResponse(
        success=True,
        message="Invitation token is valid.",
        data=info,
    )


@router.post(
    "/invitation/accept",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept Invitation & Activate Account",
    description="Sets user password, activates provisioned Doctor/Staff account, and returns authenticated JWT session.",
)
async def accept_invitation(
    request: AcceptInvitationRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TokenResponse:
    """Account activation endpoint for invited Doctors and Staff."""
    user, access_token, refresh_token = await AuthService.accept_invitation(
        db, raw_token=request.token, new_password=request.password
    )
    user_resp = UserResponse(**user.model_dump())
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_resp,
    )


@router.post(
    "/test-email",
    response_model=APIResponse[Dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="Test Email Dispatch (Admin Diagnostic)",
    description="Hospital Admin endpoint for verifying Gmail SMTP integration by sending a diagnostic email.",
    dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))],
)
async def test_email_endpoint(
    request: TestEmailRequest,
    admin_user: UserInDB = Depends(get_current_user),
) -> APIResponse[Dict[str, str]]:
    """Admin-only diagnostic endpoint for verifying live SMTP email delivery."""
    success = await EmailService.send_email(
        to_email=request.to_email,
        subject=f"Diagnostic SMTP Test — {settings.APP_NAME}",
        html_content=f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #1e293b;">
            <h2 style="color: #0284c7;">CliniXAI SMTP Diagnostic Test</h2>
            <p>Hello Admin {admin_user.full_name},</p>
            <p>This diagnostic message confirms that Gmail SMTP email integration is active and operating normally.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <p style="font-size: 12px; color: #64748b;">CliniXAI Clinical Decision Support Portal</p>
        </div>
        """,
        text_content=f"Hello Admin {admin_user.full_name}! CliniXAI SMTP diagnostic test passed."
    )
    if not success:
        return APIResponse(
            success=False,
            message="Email delivery failed. Check backend server logs for sanitized SMTP error details.",
            data={"recipient": request.to_email, "status": "failed"},
        )
    return APIResponse(
        success=True,
        message=f"Test email successfully dispatched to {request.to_email}.",
        data={"recipient": request.to_email, "status": "delivered"},
    )


