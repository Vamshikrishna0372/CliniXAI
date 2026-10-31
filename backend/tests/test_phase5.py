"""Comprehensive Unit & Security Test Suite for Phase 5: Medical Records & Secure File Management."""

import io
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now


def create_mock_cursor(return_data=None):
    """Helper creating a mock cursor with chainable sort, skip, limit methods."""
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=return_data if return_data is not None else [])
    return mock_cursor


def create_mock_db_phase5():
    """Returns a flexible mock database supporting async motor operations for Phase 5."""
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=None)
            col.count_documents = AsyncMock(return_value=0)
            col.find = MagicMock(return_value=create_mock_cursor([]))
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase5MedicalRecordEndpoints(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 5 Medical Records & Secure Files."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase5()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # User definitions
        self.patient_user = UserInDB(
            user_id="USR-2026-PAT001", email="patient@clinixai.com", full_name="Jane Patient",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.other_patient_user = UserInDB(
            user_id="USR-2026-PAT002", email="otherpatient@clinixai.com", full_name="Bob Patient",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.doctor_user = UserInDB(
            user_id="USR-2026-DOC001", email="doctor@clinixai.com", full_name="Dr. House",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )

        # Tokens
        self.patient_token = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)
        self.other_patient_token = create_access_token(user_id=self.other_patient_user.user_id, role=self.other_patient_user.role.value)
        self.doctor_token = create_access_token(user_id=self.doctor_user.user_id, role=self.doctor_user.role.value)

        # Headers
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}
        self.other_patient_headers = {"Authorization": f"Bearer {self.other_patient_token}"}
        self.doctor_headers = {"Authorization": f"Bearer {self.doctor_token}"}

        # Mock DB entities
        self.patient_dict = {
            "patient_id": "PAT-2026-00001",
            "user_id": self.patient_user.user_id,
            "first_name": "Jane",
            "last_name": "Patient",
            "email": "patient@clinixai.com",
            "status": "active",
        }
        self.doctor_dict = {
            "doctor_id": "DOC-2026-00001",
            "user_id": self.doctor_user.user_id,
            "first_name": "Gregory",
            "last_name": "House",
            "email": "doctor@clinixai.com",
            "status": "active",
        }
        self.medical_record_dict = {
            "record_id": "MR-2026-000001",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-00001",
            "record_type": "pdf_document",
            "title": "Blood Test Report",
            "description": "Routine blood panel",
            "clinical_date": "2026-07-20",
            "file": {
                "storage_key": "MOCK_KEY_12345.pdf",
                "original_filename": "blood_report.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1024,
                "checksum": "abc123hash",
                "extension": ".pdf",
                "storage_provider": "local",
                "uploaded_at": utc_now().isoformat(),
            },
            "uploaded_by": self.patient_user.user_id,
            "source": "patient",
            "status": "active",
            "ai_eligible": False,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # ── Upload Tests ─────────────────────────────────────────────────────────

    async def test_patient_upload_pdf_success(self) -> None:
        """Patient uploads valid PDF document."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        pdf_bytes = b"%PDF-1.4 Mock valid PDF document content bytes..."
        files = {"file": ("my_report.pdf", pdf_bytes, "application/pdf")}
        data = {"title": "Lab Results", "description": "Annual blood test"}

        with patch("app.services.storage_service.storage_service.save_file", return_value="SAVED_KEY.pdf"):
            res = await self.client.post("/api/v1/medical-records", files=files, data=data, headers=self.patient_headers)
            self.assertEqual(res.status_code, 201)
            self.assertEqual(res.json()["data"]["title"], "Lab Results")
            self.assertEqual(res.json()["data"]["patient_id"], "PAT-2026-00001")

    async def test_patient_upload_medical_image_ai_eligible(self) -> None:
        """Uploading valid JPEG medical image sets ai_eligible=True."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (100, 100), color=(200, 200, 200)).save(buf, format="JPEG")
        jpg_bytes = buf.getvalue()
        files = {"file": ("chest_xray.jpg", jpg_bytes, "image/jpeg")}
        data = {"title": "Chest X-Ray", "record_type": "medical_image"}

        with patch("app.services.storage_service.storage_service.save_file", return_value="SAVED_XRAY.jpg"):
            res = await self.client.post("/api/v1/medical-records", files=files, data=data, headers=self.patient_headers)
            self.assertEqual(res.status_code, 201)
            self.assertTrue(res.json()["data"]["ai_eligible"])

    async def test_upload_forbidden_extension_rejected(self) -> None:
        """Uploading dangerous executable extension (.exe) is rejected with 400 Bad Request."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        files = {"file": ("malware.exe", b"MZ Executable binary...", "application/octet-stream")}
        data = {"title": "Executable"}

        res = await self.client.post("/api/v1/medical-records", files=files, data=data, headers=self.patient_headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("forbidden", res.json()["error"]["message"].lower())

    async def test_upload_invalid_magic_bytes_rejected(self) -> None:
        """Uploading fake JPEG containing non-image data is rejected cleanly."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        files = {"file": ("fake.jpg", b"This is plain text not a jpeg", "image/jpeg")}
        data = {"title": "Fake Image"}

        res = await self.client.post("/api/v1/medical-records", files=files, data=data, headers=self.patient_headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("header", res.json()["error"]["message"].lower())

    # ── Security & Access Control Tests ──────────────────────────────────────

    async def test_unauthorized_patient_cannot_access_other_patient_record(self) -> None:
        """Patient B is rejected (403) from viewing Patient A's medical record."""
        self.mock_db["users"].find_one.return_value = self.other_patient_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = {"patient_id": "PAT-2026-00002", "user_id": self.other_patient_user.user_id}
        self.mock_db["medical_records"].find_one.return_value = self.medical_record_dict

        res = await self.client.get("/api/v1/medical-records/MR-2026-000001", headers=self.other_patient_headers)
        self.assertEqual(res.status_code, 403)

    async def test_secure_file_download(self) -> None:
        """Authorized Patient streams file content with security headers."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = self.patient_dict
        self.mock_db["medical_records"].find_one.return_value = self.medical_record_dict

        file_bytes = b"%PDF-1.4 Content bytes..."
        with patch("app.services.storage_service.storage_service.read_file", return_value=file_bytes):
            res = await self.client.get("/api/v1/medical-records/MR-2026-000001/file", headers=self.patient_headers)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("blood_report.pdf", res.headers["Content-Disposition"])


if __name__ == "__main__":
    unittest.main()
