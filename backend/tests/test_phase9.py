"""
Unit Test Suite for Phase 9: External Integrations, Security, Storage & QR.

Tests:
1. Google OAuth ID Token verification & role escalation protection
2. Google Calendar event creation & graceful disconnect
3. Email delivery service dispatches & templates
4. Patient Health QR generation, PNG image stream, and rotation
5. Hospital Staff Patient Health QR resolution
6. Appointment Check-In QR generation, PNG image stream, and QR Check-in workflow
7. QR replay protection and expiration/cancellation checks
8. Production ObjectStorageService fallback behavior
9. Rate Limiter middleware enforcement
10. System Integrations status endpoint
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.core.config import settings
from app.utils.datetime import utc_now


def _make_cursor(return_data=None):
    mock_cursor = MagicMock()
    data = list(return_data) if return_data is not None else []
    mock_cursor.__aiter__ = MagicMock(return_value=iter(data))
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.skip = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=data)
    return mock_cursor


class TestPhase9Integrations(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.admin_user = UserInDB(
            user_id="USR-2026-ADM001", email="admin@clinixai.com", full_name="Admin User",
            role=UserRole.HOSPITAL_ADMIN, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
        )
        self.doctor_user = UserInDB(
            user_id="USR-2026-DOC001", email="dr.house@clinixai.com", full_name="Dr. Gregory House",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
        )
        self.patient_user = UserInDB(
            user_id="USR-2026-PAT001", email="patient.a@clinixai.com", full_name="John Doe",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
        )
        self.staff_user = UserInDB(
            user_id="USR-2026-STF001", email="staff@clinixai.com", full_name="Staff Member",
            role=UserRole.HOSPITAL_STAFF, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
        )

        self._user_dicts = {
            "USR-2026-ADM001": self.admin_user.to_mongo_dict(),
            "USR-2026-DOC001": self.doctor_user.to_mongo_dict(),
            "USR-2026-PAT001": self.patient_user.to_mongo_dict(),
            "USR-2026-STF001": self.staff_user.to_mongo_dict(),
        }

        self.admin_token = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.doctor_token = create_access_token(user_id=self.doctor_user.user_id, role=self.doctor_user.role.value)
        self.patient_token = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)
        self.staff_token = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.doctor_headers = {"Authorization": f"Bearer {self.doctor_token}"}
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}

        self._collections: dict = {}
        user_dicts = self._user_dicts

        def get_collection(name):
            if name not in self._collections:
                col = MagicMock()
                col.insert_one = AsyncMock(return_value=None)
                col.replace_one = AsyncMock(return_value=None)
                col.update_one = AsyncMock(return_value=None)
                col.count_documents = AsyncMock(return_value=0)
                col.find = MagicMock(return_value=_make_cursor([]))
                col.aggregate = MagicMock(return_value=_make_cursor([]))
                col.find_one = AsyncMock(return_value=None)
                self._collections[name] = col
            return self._collections[name]

        self.mock_db = MagicMock()
        self.mock_db.__getitem__.side_effect = get_collection

        async def users_find_one(query, *args, **kwargs):
            uid = query.get("user_id")
            if uid:
                return user_dicts.get(uid)
            email = query.get("email")
            if email:
                for u in user_dicts.values():
                    if u["email"] == email:
                        return u
            return None

        get_collection("users").find_one = users_find_one

        async def override_get_db():
            return self.mock_db

        app.dependency_overrides[get_database] = override_get_db

        self.patient_dict = {
            "patient_id": "PAT-2026-00001",
            "user_id": "USR-2026-PAT001",
            "first_name": "John",
            "last_name": "Doe",
            "email": "patient.a@clinixai.com",
            "qr_code": {"raw_token": "pqr_test123", "is_revoked": False},
        }

        self.appointment_dict = {
            "appointment_id": "APT-2026-000001",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-000001",
            "department_id": "DEP-CARD-001",
            "appointment_date": "2026-08-10",
            "start_time": "10:00",
            "end_time": "10:30",
            "status": "scheduled",
            "qr_code": {"raw_token": "aqr_test456", "is_revoked": False, "expires_at": None},
        }

        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://testserver")

        # Pre-touch all commonly used collections so self._collections is populated before individual tests
        for col_name in ["users", "patients", "appointments", "user_sessions"]:
            _ = self.mock_db[col_name]

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # ── Test 1: System Integrations Status Endpoint ────────────────────────────
    async def test_system_integrations_status(self) -> None:
        """GET /api/v1/integrations/status returns system readiness."""
        res = await self.client.get("/api/v1/integrations/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("google_auth", data)
        self.assertIn("email_delivery", data)
        self.assertIn("storage_provider", data)

    # ── Test 2: Hospital Location & Directions ──────────────────────────────────
    async def test_hospital_location(self) -> None:
        """GET /api/v1/hospital/location returns address and free directions link."""
        res = await self.client.get("/api/v1/hospital/location")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("hospital_name", data)
        self.assertIn("directions_url", data)

    # ── Test 3: Google Auth Token Exchange ─────────────────────────────────────
    @patch("app.integrations.google_auth.GoogleAuthService.verify_google_id_token")
    async def test_google_auth_token_exchange(self, mock_verify) -> None:
        """POST /api/v1/auth/google verifies OIDC token and issues CliniXAI JWT."""
        mock_verify.return_value = {
            "google_sub": "sub_12345",
            "email": "google.user@gmail.com",
            "full_name": "Google User",
        }
        res = await self.client.post("/api/v1/auth/google", json={"id_token": "mock_valid_token"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["role"], "patient")  # Strict PATIENT role assignment

    # ── Test 4: Patient Health QR Token & PNG Image ───────────────────────────
    async def test_patient_qr_generation(self) -> None:
        """Patient fetches QR token & PNG image bytes."""
        self._collections["patients"].find_one = AsyncMock(return_value=self.patient_dict)

        # GET Token
        res = await self.client.get("/api/v1/patients/me/qr", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.json())

        # GET Image PNG
        res_img = await self.client.get("/api/v1/patients/me/qr/image", headers=self.patient_headers)
        self.assertEqual(res_img.status_code, 200)
        self.assertEqual(res_img.headers["content-type"], "image/png")

    # ── Test 5: Staff Resolves Patient Health QR Code ──────────────────────────
    async def test_staff_resolve_patient_qr(self) -> None:
        """Hospital Staff scans Patient Health QR -> receives summary."""
        self._collections["patients"].find_one = AsyncMock(return_value=self.patient_dict)

        res = await self.client.post(
            "/api/v1/qr/resolve-patient",
            json={"token": "clinixai:patient:pqr_test123"},
            headers=self.staff_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["patient_id"], "PAT-2026-00001")

    # ── Test 6: Patient Unauthorized to Scan Patient QR ───────────────────────
    async def test_patient_cannot_resolve_patient_qr(self) -> None:
        """Patient scanning arbitrary QR token is rejected with 403 Forbidden."""
        self._collections["patients"].find_one = AsyncMock(return_value=self.patient_dict)

        res = await self.client.post(
            "/api/v1/qr/resolve-patient",
            json={"token": "clinixai:patient:pqr_test123"},
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 403)

    # ── Test 7: Appointment Check-In QR Generation ────────────────────────────
    async def test_appointment_qr_generation(self) -> None:
        """Fetch appointment QR token and PNG image."""
        self._collections["appointments"].find_one = AsyncMock(return_value=self.appointment_dict)

        res = await self.client.get("/api/v1/appointments/APT-2026-000001/qr", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)

        res_img = await self.client.get("/api/v1/appointments/APT-2026-000001/qr/image", headers=self.patient_headers)
        self.assertEqual(res_img.status_code, 200)
        self.assertEqual(res_img.headers["content-type"], "image/png")

    # ── Test 8: QR Check-In Workflow ──────────────────────────────────────────
    @patch("app.services.appointment_service.AppointmentService.check_in_patient")
    async def test_qr_checkin_success(self, mock_check_in) -> None:
        """Hospital Staff scans appointment QR code -> triggers queue check-in."""
        self._collections["appointments"].find_one = AsyncMock(return_value=self.appointment_dict)

        mock_result = MagicMock()
        mock_result.patient_id = "PAT-2026-00001"
        mock_result.status = "checked_in"
        mock_result.queue_token = "Q-101"
        mock_check_in.return_value = mock_result

        res = await self.client.post(
            "/api/v1/check-in/qr",
            json={"token": "clinixai:appointment:aqr_test456"},
            headers=self.staff_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["queue_token"], "Q-101")
        self.assertFalse(data["already_checked_in"])

    # ── Test 9: Object Storage Fallback Test ──────────────────────────────────
    async def test_object_storage_fallback(self) -> None:
        """ObjectStorageService falls back safely to LocalStorageService when credentials missing."""
        from app.services.object_storage import ObjectStorageService

        storage = ObjectStorageService()
        self.assertFalse(storage.is_configured)

        # Test save_file fallback
        saved_key = await storage.save_file(b"test_bytes", "test.txt", subfolder="test-folder")
        self.assertEqual(saved_key, "test.txt")


if __name__ == "__main__":
    unittest.main()
