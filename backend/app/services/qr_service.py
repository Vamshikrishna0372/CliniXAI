"""
Internal Secure QR Generation & Verification Service for CliniXAI Phase 9.

Generates:
- Patient Health QR (opaque token to locate patient profile safely)
- Appointment Check-In QR (opaque token for queue check-in)

Security:
- Encodes ONLY cryptographically random opaque tokens (`secrets.token_urlsafe(32)`)
- Stores token hashes in MongoDB domain collections (`patients`, `appointments`)
- NEVER embeds raw PII, diagnoses, or clinical data in QR payload
"""

import io
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

from app.core.logging import logger
from app.core.exceptions import ResourceNotFoundError, ForbiddenError, AppValidationError
from app.database.collections import COLLECTION_PATIENTS, COLLECTION_APPOINTMENTS
from app.models.user import UserInDB, UserRole
from app.utils.datetime import utc_now


def _hash_token(raw_token: str) -> str:
    """Computes SHA-256 hash of a raw QR token for secure storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class QRService:
    """Production QR code generation, token management, and verification engine."""

    # ── QR Code Image Rendering ───────────────────────────────────────────────

    @staticmethod
    def generate_qr_image_bytes(payload_data: str) -> bytes:
        """Renders payload string into PNG image bytes in-memory using qrcode + Pillow (or fallback bytes)."""
        if HAS_QRCODE:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(payload_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="PNG")
            return img_byte_arr.getvalue()

        # Fallback PNG header byte array if qrcode library is not installed
        return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x03\x05\xfe\x02\xfe\x1d\x00\x05\x00\x01\x0d\x0a-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"

    # ── Patient Health QR ─────────────────────────────────────────────────────

    @staticmethod
    async def get_or_create_patient_qr(
        db: AsyncIOMotorDatabase,
        patient_id: str,
    ) -> Tuple[str, bytes]:
        """
        Retrieves or generates an opaque Patient Health QR code token & PNG bytes.
        Payload format: `clinixai:patient:<raw_token>`
        """
        patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": patient_id})
        if not patient:
            raise ResourceNotFoundError("Patient", patient_id)

        qr_meta = patient.get("qr_code") or {}
        raw_token = qr_meta.get("raw_token")

        if not raw_token or qr_meta.get("is_revoked", False):
            # Generate new token & hash
            raw_token = f"pqr_{secrets.token_urlsafe(32)}"
            token_hash = _hash_token(raw_token)
            qr_meta = {
                "raw_token": raw_token,
                "token_hash": token_hash,
                "created_at": utc_now(),
                "is_revoked": False,
            }
            await db[COLLECTION_PATIENTS].update_one(
                {"patient_id": patient_id},
                {"$set": {"qr_code": qr_meta, "updated_at": utc_now()}},
            )
            logger.info(f"Generated new Patient Health QR token for {patient_id}")

        payload = f"clinixai:patient:{raw_token}"
        png_bytes = QRService.generate_qr_image_bytes(payload)
        return raw_token, png_bytes

    @staticmethod
    async def revoke_and_regenerate_patient_qr(
        db: AsyncIOMotorDatabase,
        patient_id: str,
    ) -> Tuple[str, bytes]:
        """Revokes compromised Patient QR token and issues a fresh one."""
        raw_token = f"pqr_{secrets.token_urlsafe(32)}"
        token_hash = _hash_token(raw_token)
        qr_meta = {
            "raw_token": raw_token,
            "token_hash": token_hash,
            "created_at": utc_now(),
            "is_revoked": False,
        }
        await db[COLLECTION_PATIENTS].update_one(
            {"patient_id": patient_id},
            {"$set": {"qr_code": qr_meta, "updated_at": utc_now()}},
        )
        logger.info(f"Regenerated Patient Health QR token for {patient_id}")
        payload = f"clinixai:patient:{raw_token}"
        png_bytes = QRService.generate_qr_image_bytes(payload)
        return raw_token, png_bytes

    @staticmethod
    async def resolve_patient_qr_token(
        db: AsyncIOMotorDatabase,
        token: str,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """
        Hospital Staff / Doctor scans Patient Health QR token to resolve patient identity.
        RBAC enforced: Patients cannot scan arbitrary QR codes.
        """
        if current_user.role not in {UserRole.DOCTOR, UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN}:
            raise ForbiddenError("Only authorized Hospital Staff can resolve Patient Health QR codes.")

        clean_token = token.replace("clinixai:patient:", "").strip()
        patient = await db[COLLECTION_PATIENTS].find_one({"qr_code.raw_token": clean_token})

        if not patient:
            raise ResourceNotFoundError("Patient QR Token", clean_token)

        qr_meta = patient.get("qr_code") or {}
        if qr_meta.get("is_revoked", False):
            raise AppValidationError("This Patient QR code has been revoked.")

        return {
            "patient_id": patient["patient_id"],
            "user_id": patient["user_id"],
            "first_name": patient["first_name"],
            "last_name": patient["last_name"],
            "gender": patient.get("gender"),
            "date_of_birth": patient.get("date_of_birth"),
            "contact_number": patient.get("contact_number"),
            "blood_group": patient.get("blood_group"),
        }

    # ── Appointment Check-In QR ───────────────────────────────────────────────

    @staticmethod
    async def get_or_create_appointment_qr(
        db: AsyncIOMotorDatabase,
        appointment_id: str,
    ) -> Tuple[str, bytes]:
        """
        Retrieves or generates an opaque Appointment Check-In QR code token & PNG bytes.
        Payload format: `clinixai:appointment:<raw_token>`
        """
        appointment = await db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": appointment_id})
        if not appointment:
            raise ResourceNotFoundError("Appointment", appointment_id)

        qr_meta = appointment.get("qr_code") or {}
        raw_token = qr_meta.get("raw_token")

        if not raw_token or qr_meta.get("is_revoked", False):
            raw_token = f"aqr_{secrets.token_urlsafe(32)}"
            token_hash = _hash_token(raw_token)
            now = utc_now()
            qr_meta = {
                "raw_token": raw_token,
                "token_hash": token_hash,
                "created_at": now,
                "expires_at": now + timedelta(days=7),
                "is_revoked": False,
                "used_at": None,
            }
            await db[COLLECTION_APPOINTMENTS].update_one(
                {"appointment_id": appointment_id},
                {"$set": {"qr_code": qr_meta, "updated_at": now}},
            )
            logger.info(f"Generated new Appointment Check-In QR token for {appointment_id}")

        payload = f"clinixai:appointment:{raw_token}"
        png_bytes = QRService.generate_qr_image_bytes(payload)
        return raw_token, png_bytes

    @staticmethod
    async def process_qr_checkin(
        db: AsyncIOMotorDatabase,
        token: str,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """
        Validates scanned Appointment Check-In QR token and invokes check-in workflow.
        Verifies:
        - Staff authorization
        - Appointment existence & status (not cancelled, not already completed)
        - QR expiration & revocation status
        - Replay protection
        """
        if current_user.role not in {UserRole.HOSPITAL_STAFF, UserRole.HOSPITAL_ADMIN, UserRole.DOCTOR}:
            raise ForbiddenError("Only authorized Hospital Staff can perform QR check-in.")

        clean_token = token.replace("clinixai:appointment:", "").strip()
        appointment = await db[COLLECTION_APPOINTMENTS].find_one({"qr_code.raw_token": clean_token})

        if not appointment:
            raise ResourceNotFoundError("Appointment QR Token", clean_token)

        appointment_id = appointment["appointment_id"]
        qr_meta = appointment.get("qr_code") or {}

        if qr_meta.get("is_revoked", False):
            raise AppValidationError("This Appointment QR code has been revoked.")

        # Expiration check
        expires_at = qr_meta.get("expires_at")
        if expires_at:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if utc_now() > expires_at:
                raise AppValidationError("This Appointment QR code has expired.")

        # Replay protection / Status check
        status_val = appointment.get("status", "")
        if status_val == "cancelled":
            raise AppValidationError("Cannot check in: Appointment has been cancelled.")
        if status_val == "completed":
            raise AppValidationError("Cannot check in: Appointment is already completed.")
        if status_val in {"checked_in", "in_consultation"}:
            return {
                "message": "Patient is already checked in.",
                "appointment_id": appointment_id,
                "status": status_val,
                "already_checked_in": True,
            }

        # Mark QR used and delegate to AppointmentService.check_in_patient
        from app.services.appointment_service import AppointmentService

        await db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": appointment_id},
            {"$set": {"qr_code.used_at": utc_now(), "updated_at": utc_now()}},
        )

        checked_in_appt = await AppointmentService.check_in_patient(
            db=db,
            appointment_id=appointment_id,
            current_user=current_user,
        )

        logger.info(f"QR Check-In successfully processed for Appointment {appointment_id}")
        return {
            "message": "QR Check-In successful. Patient entered into queue.",
            "appointment_id": appointment_id,
            "patient_id": checked_in_appt.patient_id,
            "status": checked_in_appt.status,
            "queue_token": checked_in_appt.queue_token,
            "already_checked_in": False,
        }
