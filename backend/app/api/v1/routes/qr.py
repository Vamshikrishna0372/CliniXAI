"""
QR Code API Routes for CliniXAI Phase 9.

Endpoints for:
- Patient Health QR generation & PNG rendering (`GET /api/v1/patients/me/qr`, `GET /api/v1/patients/me/qr/image`)
- Patient Health QR regeneration (`POST /api/v1/patients/me/qr/regenerate`)
- Hospital Staff scanning Patient Health QR (`POST /api/v1/qr/resolve-patient`)
- Appointment Check-In QR generation (`GET /api/v1/appointments/{id}/qr`, `GET /api/v1/appointments/{id}/qr/image`)
- Hospital Staff scanning Appointment Check-In QR (`POST /api/v1/check-in/qr`)
"""

from fastapi import APIRouter, Depends, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_active_user, require_roles
from app.models.user import UserInDB, UserRole
from app.schemas.integrations import (
    QRTokenResponse, QRResolvePatientResponse, QRCheckInRequest, QRCheckInResponse
)
from app.services.qr_service import QRService
from app.services.patient_service import PatientService
from app.utils.datetime import utc_now

from app.core.exceptions import ResourceNotFoundError, ForbiddenError

router = APIRouter(tags=["QR Codes & Check-In"])


# ── Patient Health QR Endpoints ───────────────────────────────────────────────

async def _get_patient_id_for_user(db, user_id: str) -> str:
    """Helper: returns patient_id for the given user_id or raises 404."""
    patient_doc = await PatientService.get_patient_by_user_id(db, user_id)
    if not patient_doc:
        raise ResourceNotFoundError("Patient profile", user_id)
    return patient_doc["patient_id"]


@router.get(
    "/patients/me/qr",
    response_model=QRTokenResponse,
    summary="Get Patient Health QR Token",
)
async def get_patient_qr_token(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns opaque Patient Health QR token for current authenticated patient."""
    if current_user.role != UserRole.PATIENT:
        raise ForbiddenError("Only registered patients can access personal QR health cards.")
    patient_id = await _get_patient_id_for_user(db, current_user.user_id)
    raw_token, _ = await QRService.get_or_create_patient_qr(db, patient_id)
    return QRTokenResponse(
        token=raw_token,
        payload=f"clinixai:patient:{raw_token}",
        created_at=utc_now().isoformat(),
    )


@router.get(
    "/patients/me/qr/image",
    summary="Get Patient Health QR PNG Image",
    responses={200: {"content": {"image/png": {}}}},
)
async def get_patient_qr_image(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Streams PNG image bytes of current Patient Health QR code."""
    if current_user.role != UserRole.PATIENT:
        raise ForbiddenError("Only registered patients can access personal QR health cards.")
    patient_id = await _get_patient_id_for_user(db, current_user.user_id)
    _, png_bytes = await QRService.get_or_create_patient_qr(db, patient_id)
    return Response(content=png_bytes, media_type="image/png")


@router.post(
    "/patients/me/qr/regenerate",
    response_model=QRTokenResponse,
    summary="Regenerate & Rotate Patient Health QR Token",
)
async def regenerate_patient_qr_token(
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Revokes current Patient Health QR code and generates a fresh token."""
    if current_user.role != UserRole.PATIENT:
        raise ForbiddenError("Only registered patients can rotate personal QR health cards.")
    patient_id = await _get_patient_id_for_user(db, current_user.user_id)
    raw_token, _ = await QRService.revoke_and_regenerate_patient_qr(db, patient_id)
    return QRTokenResponse(
        token=raw_token,
        payload=f"clinixai:patient:{raw_token}",
        created_at=utc_now().isoformat(),
    )


@router.post(
    "/qr/resolve-patient",
    response_model=QRResolvePatientResponse,
    summary="Resolve Scanned Patient Health QR Code (Staff Only)",
)
async def resolve_patient_qr(
    request: QRCheckInRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Authorized Hospital Staff/Doctor scans Patient Health QR to retrieve summary."""
    patient_data = await QRService.resolve_patient_qr_token(db, request.token, current_user)
    return QRResolvePatientResponse(**patient_data)


# ── Appointment Check-In QR Endpoints ─────────────────────────────────────────

@router.get(
    "/appointments/{appointment_id}/qr",
    response_model=QRTokenResponse,
    summary="Get Appointment Check-In QR Token",
)
async def get_appointment_qr_token(
    appointment_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns opaque Appointment Check-In QR token."""
    raw_token, _ = await QRService.get_or_create_appointment_qr(db, appointment_id)
    return QRTokenResponse(
        token=raw_token,
        payload=f"clinixai:appointment:{raw_token}",
        created_at=utc_now().isoformat(),
    )


@router.get(
    "/appointments/{appointment_id}/qr/image",
    summary="Get Appointment Check-In QR PNG Image",
    responses={200: {"content": {"image/png": {}}}},
)
async def get_appointment_qr_image(
    appointment_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Streams PNG image bytes of Appointment Check-In QR code."""
    _, png_bytes = await QRService.get_or_create_appointment_qr(db, appointment_id)
    return Response(content=png_bytes, media_type="image/png")


@router.post(
    "/check-in/qr",
    response_model=QRCheckInResponse,
    summary="Perform QR Check-In (Staff Only)",
)
async def process_qr_checkin(
    request: QRCheckInRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Authorized Hospital Staff scans Appointment QR code to check in patient."""
    result = await QRService.process_qr_checkin(db, request.token, current_user)
    return QRCheckInResponse(**result)
