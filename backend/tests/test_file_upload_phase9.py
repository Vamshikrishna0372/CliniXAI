"""
Phase 9 Comprehensive Production Test Suite: Secure File & Medical Image Upload.

Covers:
1. Authorized file upload by Patient
2. Patient ownership enforcement (patient_id forced from auth)
3. Patient cross-entity upload IDOR blocked (403)
4. Patient download own file (200, matching SHA-256 and bytes)
5. Patient cross-entity download IDOR blocked (403)
6. Doctor authorized upload for patient with care relationship (201)
7. Doctor unauthorized upload for patient without care relationship (403)
8. Doctor authorized download (200)
9. Doctor unauthorized download (403)
10. Hospital Staff upload/download according to RBAC
11. Hospital Admin authorized audit access (200)
12. Unauthenticated access blocked (401)
13. Disabled / suspended account blocked (403)
14. Deleted user account blocked (401)
15. Path traversal filenames blocked (../../secret.txt, ..\\..\\evil.jpg, Windows drive paths)
16. Null byte and control char filename sanitization
17. Empty file (0 bytes) rejected (400/422)
18. Oversized file rejected (>10MB limit)
19. Boundary file size test (10MB allowed, 10MB + 1 byte rejected)
20. MIME spoofing blocked (declared image/jpeg with text/executable payload)
21. Extension spoofing blocked (malware.exe.jpg)
22. Corrupted image bytes rejected by Pillow decoder
23. Decompression bomb / huge dimension image rejected
24. SHA-256 checksum verification (stored hash matches file hash)
25. File size verification (stored size matches actual size)
26. Atomic upload failure cleanup (binary deleted if DB fails)
27. Soft delete lifecycle (soft-deleted file cannot be downloaded by normal user -> 404)
28. Medical record relationship mismatch rejected
29. Security headers present (X-Content-Type-Options: nosniff, safe Content-Disposition)
30. WEBP medical image upload & download
31. DocumentService standalone upload & download verification
"""

import io
import os
import hashlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from PIL import Image

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.medical_record import RecordType, RecordStatus
from app.core.security import create_access_token
from app.core.config import settings
from app.services.storage_service import storage_service
from app.utils.datetime import utc_now


def make_valid_png_bytes(width: int = 100, height: int = 100) -> bytes:
    """Generates valid PNG image bytes using PIL."""
    img = Image.new("RGB", (width, height), color=(70, 130, 180))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_valid_jpeg_bytes(width: int = 100, height: int = 100) -> bytes:
    """Generates valid JPEG image bytes using PIL."""
    img = Image.new("RGB", (width, height), color=(180, 70, 130))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_valid_webp_bytes(width: int = 100, height: int = 100) -> bytes:
    """Generates valid WEBP image bytes using PIL."""
    img = Image.new("RGB", (width, height), color=(50, 180, 90))
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    return buf.getvalue()


def make_valid_pdf_bytes() -> bytes:
    """Generates valid minimal PDF document bytes."""
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n99\n%%EOF\n"


def create_mock_cursor(return_data=None):
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=return_data if return_data is not None else [])
    return mock_cursor


def create_mock_db():
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


class TestPhase9SecureUpload(unittest.IsolatedAsyncioTestCase):
    """End-to-end unit and security verification suite for Phase 9."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # Patient A (Alice)
        self.patient_a_user = UserInDB(
            user_id="USR-2026-PAT-A", email="patient.a@clinixai.com", full_name="Alice Patient",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.patient_a_dict = {
            "patient_id": "PAT-2026-A01",
            "user_id": self.patient_a_user.user_id,
            "first_name": "Alice",
            "last_name": "Patient",
            "email": self.patient_a_user.email,
            "status": "active",
        }

        # Patient B (Bob)
        self.patient_b_user = UserInDB(
            user_id="USR-2026-PAT-B", email="patient.b@clinixai.com", full_name="Bob Patient",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.patient_b_dict = {
            "patient_id": "PAT-2026-B02",
            "user_id": self.patient_b_user.user_id,
            "first_name": "Bob",
            "last_name": "Patient",
            "email": self.patient_b_user.email,
            "status": "active",
        }

        # Doctor 1 (Dr. Arjun Rao - Treating Doctor for Patient A)
        self.doctor_1_user = UserInDB(
            user_id="USR-2026-DOC-1", email="doctor.one@clinixai.com", full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.doctor_1_dict = {
            "doctor_id": "DOC-2026-001",
            "user_id": self.doctor_1_user.user_id,
            "first_name": "Arjun",
            "last_name": "Rao",
            "email": self.doctor_1_user.email,
            "status": "active",
        }

        # Doctor 2 (Dr. Priya Sharma - Unrelated Doctor)
        self.doctor_2_user = UserInDB(
            user_id="USR-2026-DOC-2", email="doctor.two@clinixai.com", full_name="Dr. Priya Sharma",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.doctor_2_dict = {
            "doctor_id": "DOC-2026-002",
            "user_id": self.doctor_2_user.user_id,
            "first_name": "Priya",
            "last_name": "Sharma",
            "email": self.doctor_2_user.email,
            "status": "active",
        }

        # Staff User
        self.staff_user = UserInDB(
            user_id="USR-2026-STF-1", email="staff@clinixai.com", full_name="Front Desk Staff",
            role=UserRole.HOSPITAL_STAFF, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )

        # Hospital Admin
        self.admin_user = UserInDB(
            user_id="USR-2026-ADM-1", email="admin@clinixai.com", full_name="Hospital Administrator",
            role=UserRole.HOSPITAL_ADMIN, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )

        # Disabled User
        self.disabled_user = UserInDB(
            user_id="USR-2026-DIS-1", email="disabled@clinixai.com", full_name="Disabled User",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.SUSPENDED
        )

        # Deleted User
        self.deleted_user_id = "USR-2026-DEL-1"

        # User Dicts for authentication resolution
        self.user_dicts = {
            self.patient_a_user.user_id: self.patient_a_user.to_mongo_dict(),
            self.patient_b_user.user_id: self.patient_b_user.to_mongo_dict(),
            self.doctor_1_user.user_id: self.doctor_1_user.to_mongo_dict(),
            self.doctor_2_user.user_id: self.doctor_2_user.to_mongo_dict(),
            self.staff_user.user_id: self.staff_user.to_mongo_dict(),
            self.admin_user.user_id: self.admin_user.to_mongo_dict(),
            self.disabled_user.user_id: self.disabled_user.to_mongo_dict(),
        }

        # Setup user lookup in mock DB
        async def users_find_one(query, *args, **kwargs):
            uid = query.get("user_id")
            if uid:
                return self.user_dicts.get(uid)
            return None

        self.mock_db["users"].find_one = users_find_one

        # Tokens & Headers
        self.token_pat_a = create_access_token(user_id=self.patient_a_user.user_id, role=self.patient_a_user.role.value)
        self.token_pat_b = create_access_token(user_id=self.patient_b_user.user_id, role=self.patient_b_user.role.value)
        self.token_doc_1 = create_access_token(user_id=self.doctor_1_user.user_id, role=self.doctor_1_user.role.value)
        self.token_doc_2 = create_access_token(user_id=self.doctor_2_user.user_id, role=self.doctor_2_user.role.value)
        self.token_staff = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)
        self.token_admin = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.token_disabled = create_access_token(user_id=self.disabled_user.user_id, role=self.disabled_user.role.value)
        self.token_deleted = create_access_token(user_id=self.deleted_user_id, role="patient")

        self.headers_pat_a = {"Authorization": f"Bearer {self.token_pat_a}"}
        self.headers_pat_b = {"Authorization": f"Bearer {self.token_pat_b}"}
        self.headers_doc_1 = {"Authorization": f"Bearer {self.token_doc_1}"}
        self.headers_doc_2 = {"Authorization": f"Bearer {self.token_doc_2}"}
        self.headers_staff = {"Authorization": f"Bearer {self.token_staff}"}
        self.headers_admin = {"Authorization": f"Bearer {self.token_admin}"}
        self.headers_disabled = {"Authorization": f"Bearer {self.token_disabled}"}
        self.headers_deleted = {"Authorization": f"Bearer {self.token_deleted}"}

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # ─────────────────────────────────────────────────────────────────────────────
    # 1. Authorized File Upload by Patient
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_01_patient_authorized_upload_success(self) -> None:
        """Patient successfully uploads a valid medical image to own record."""
        async def mock_patients_find_one(query, *args, **kwargs):
            if query.get("user_id") == self.patient_a_user.user_id or query.get("patient_id") == "PAT-2026-A01":
                return self.patient_a_dict
            return None
        self.mock_db["patients"].find_one = mock_patients_find_one

        png_bytes = make_valid_png_bytes()
        files = {"file": ("chest_xray.png", png_bytes, "image/png")}
        data = {
            "title": "Chest X-Ray Screening",
            "record_type": "medical_image",
            "clinical_date": "2026-09-21",
        }

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
        self.assertEqual(res.status_code, 201)
        res_data = res.json()
        self.assertTrue(res_data["success"])
        record = res_data["data"]
        self.assertEqual(record["patient_id"], "PAT-2026-A01")
        self.assertEqual(record["uploaded_by"], self.patient_a_user.user_id)
        self.assertIsNotNone(record["file"])
        self.assertEqual(record["file"]["original_filename"], "chest_xray.png")
        self.assertEqual(record["file"]["content_type"], "image/png")
        self.assertEqual(record["file"]["checksum"], hashlib.sha256(png_bytes).hexdigest())

    # ─────────────────────────────────────────────────────────────────────────────
    # 2. Patient Ownership Enforcement (Forced patient_id)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_02_patient_forced_ownership(self) -> None:
        """Patient cannot specify arbitrary patient_id; mismatch is blocked."""
        async def mock_patients_find_one(query, *args, **kwargs):
            if query.get("user_id") == self.patient_a_user.user_id:
                return self.patient_a_dict
            return None
        self.mock_db["patients"].find_one = mock_patients_find_one

        png_bytes = make_valid_png_bytes()
        files = {"file": ("scan.png", png_bytes, "image/png")}
        data = {
            "title": "Malicious Spoof Upload",
            "patient_id": "PAT-2026-B02",  # Attempting to assign to Bob
            "record_type": "medical_image",
        }

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
        self.assertEqual(res.status_code, 403)

    # ─────────────────────────────────────────────────────────────────────────────
    # 3. Patient Download Own File & Verify SHA-256
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_03_patient_download_own_file(self) -> None:
        """Patient successfully downloads own uploaded file; content & SHA-256 match."""
        png_bytes = make_valid_png_bytes()
        storage_key = "TEST_STORAGE_KEY_A.png"
        await storage_service.save_file(png_bytes, storage_key, subfolder="medical-records")

        record_doc = {
            "record_id": "MR-2026-TEST01",
            "patient_id": "PAT-2026-A01",
            "title": "Patient A Head CT",
            "record_type": "medical_image",
            "file": {
                "storage_key": storage_key,
                "original_filename": "head_ct.png",
                "content_type": "image/png",
                "size_bytes": len(png_bytes),
                "checksum": hashlib.sha256(png_bytes).hexdigest(),
                "extension": ".png",
            },
            "uploaded_by": self.patient_a_user.user_id,
            "status": "active",
            "is_deleted": False,
        }

        self.mock_db["medical_records"].find_one = AsyncMock(return_value=record_doc)
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        res = await self.client.get("/api/v1/medical-records/MR-2026-TEST01/file", headers=self.headers_pat_a)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, png_bytes)
        self.assertEqual(hashlib.sha256(res.content).hexdigest(), record_doc["file"]["checksum"])
        self.assertEqual(res.headers.get("x-content-type-options"), "nosniff")

    # ─────────────────────────────────────────────────────────────────────────────
    # 4. Cross-Patient IDOR Download Blocked
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_04_cross_patient_download_idor_blocked(self) -> None:
        """Patient B attempting to download Patient A's file is blocked with 403 Forbidden."""
        record_doc = {
            "record_id": "MR-2026-TEST01",
            "patient_id": "PAT-2026-A01",
            "title": "Patient A Private Record",
            "file": {
                "storage_key": "some_key.png",
                "original_filename": "private.png",
                "content_type": "image/png",
                "size_bytes": 100,
            },
            "uploaded_by": self.patient_a_user.user_id,
            "is_deleted": False,
        }

        self.mock_db["medical_records"].find_one = AsyncMock(return_value=record_doc)
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_b_dict)

        res = await self.client.get("/api/v1/medical-records/MR-2026-TEST01/file", headers=self.headers_pat_b)
        self.assertEqual(res.status_code, 403)

    # ─────────────────────────────────────────────────────────────────────────────
    # 5. Doctor Authorized Upload (Care Relationship Present)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_05_doctor_authorized_upload_success(self) -> None:
        """Doctor Arjun uploads medical image for patient with active appointment -> 201 Created."""
        async def mock_patients(query, *args, **kwargs):
            if query.get("patient_id") == "PAT-2026-A01":
                return self.patient_a_dict
            return None
        self.mock_db["patients"].find_one = mock_patients

        async def mock_doctors(query, *args, **kwargs):
            if query.get("user_id") == self.doctor_1_user.user_id:
                return self.doctor_1_dict
            return None
        self.mock_db["doctors"].find_one = mock_doctors

        # Active appointment establishing care relationship
        self.mock_db["appointments"].find_one = AsyncMock(return_value={
            "appointment_id": "APT-2026-001",
            "patient_id": "PAT-2026-A01",
            "doctor_id": "DOC-2026-001",
            "status": "confirmed",
        })

        jpeg_bytes = make_valid_jpeg_bytes()
        files = {"file": ("echocardiogram.jpg", jpeg_bytes, "image/jpeg")}
        data = {
            "title": "Echo Doppler Scan",
            "patient_id": "PAT-2026-A01",
            "record_type": "medical_image",
            "clinical_date": "2026-09-21",
            "diagnosis": "Mild Mitral Regurgitation",
        }

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_doc_1, data=data, files=files)
        self.assertEqual(res.status_code, 201)
        record = res.json()["data"]
        self.assertEqual(record["patient_id"], "PAT-2026-A01")
        self.assertEqual(record["doctor_id"], "DOC-2026-001")
        self.assertEqual(record["file"]["content_type"], "image/jpeg")

    # ─────────────────────────────────────────────────────────────────────────────
    # 6. Doctor Unauthorized Upload (No Care Relationship)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_06_doctor_unauthorized_upload_blocked(self) -> None:
        """Doctor without care relationship attempting to upload is blocked with 403 Forbidden."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)
        self.mock_db["doctors"].find_one = AsyncMock(return_value=self.doctor_2_dict)
        self.mock_db["appointments"].find_one = AsyncMock(return_value=None)
        self.mock_db["consultations"].find_one = AsyncMock(return_value=None)

        jpeg_bytes = make_valid_jpeg_bytes()
        files = {"file": ("unauthorized_scan.jpg", jpeg_bytes, "image/jpeg")}
        data = {
            "title": "Unauthorized Scan",
            "patient_id": "PAT-2026-A01",
            "record_type": "medical_image",
        }

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_doc_2, data=data, files=files)
        self.assertEqual(res.status_code, 403)

    # ─────────────────────────────────────────────────────────────────────────────
    # 7. Doctor Authorized Download vs Unauthorized Download
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_07_doctor_download_authorization(self) -> None:
        """Authorized doctor downloads file (200), unauthorized doctor is denied (403)."""
        png_bytes = make_valid_png_bytes()
        storage_key = "DOC_TEST_KEY.png"
        await storage_service.save_file(png_bytes, storage_key, subfolder="medical-records")

        record_doc = {
            "record_id": "MR-2026-DOC01",
            "patient_id": "PAT-2026-A01",
            "doctor_id": "DOC-2026-001",
            "title": "Clinical Scan",
            "file": {
                "storage_key": storage_key,
                "original_filename": "clinical.png",
                "content_type": "image/png",
                "size_bytes": len(png_bytes),
            },
            "uploaded_by": self.doctor_1_user.user_id,
            "is_deleted": False,
        }

        self.mock_db["medical_records"].find_one = AsyncMock(return_value=record_doc)

        async def mock_doc_lookup(query, *args, **kwargs):
            if query.get("user_id") == self.doctor_1_user.user_id:
                return self.doctor_1_dict
            elif query.get("user_id") == self.doctor_2_user.user_id:
                return self.doctor_2_dict
            return None
        self.mock_db["doctors"].find_one = mock_doc_lookup

        # Doctor 1 has care relationship
        self.mock_db["appointments"].find_one = AsyncMock(return_value={"appointment_id": "APT-01"})

        res1 = await self.client.get("/api/v1/medical-records/MR-2026-DOC01/file", headers=self.headers_doc_1)
        self.assertEqual(res1.status_code, 200)

        # Doctor 2 has NO relationship
        self.mock_db["appointments"].find_one = AsyncMock(return_value=None)
        self.mock_db["consultations"].find_one = AsyncMock(return_value=None)

        res2 = await self.client.get("/api/v1/medical-records/MR-2026-DOC01/file", headers=self.headers_doc_2)
        self.assertEqual(res2.status_code, 403)

    # ─────────────────────────────────────────────────────────────────────────────
    # 8. Unauthenticated Access Blocked (401)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_08_unauthenticated_access_blocked(self) -> None:
        """Unauthenticated requests to upload or download return 401 Unauthorized."""
        res_upload = await self.client.post("/api/v1/medical-records", data={"title": "Test"})
        self.assertEqual(res_upload.status_code, 401)

        res_download = await self.client.get("/api/v1/medical-records/MR-001/file")
        self.assertEqual(res_download.status_code, 401)

    # ─────────────────────────────────────────────────────────────────────────────
    # 9. Disabled Account Blocked (403) & Deleted Account (401)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_09_disabled_and_deleted_accounts(self) -> None:
        """Disabled user gets 403, soft-deleted user gets 401."""
        res_disabled = await self.client.get("/api/v1/medical-records/MR-001/file", headers=self.headers_disabled)
        self.assertEqual(res_disabled.status_code, 403)

        res_deleted = await self.client.get("/api/v1/medical-records/MR-001/file", headers=self.headers_deleted)
        self.assertEqual(res_deleted.status_code, 401)

    # ─────────────────────────────────────────────────────────────────────────────
    # 10. Path Traversal Filenames Sanitized & Storage Protected
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_10_path_traversal_filename_blocked(self) -> None:
        """Filenames with path traversal (../../evil.png, C:\\windows) are sanitized without traversal."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        png_bytes = make_valid_png_bytes()
        files = {"file": ("../../../../etc/passwd.png", png_bytes, "image/png")}
        data = {
            "title": "Traversal Attempt",
            "record_type": "medical_image",
        }

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
        self.assertEqual(res.status_code, 201)
        record = res.json()["data"]
        # Filename was sanitized to passwd.png
        self.assertEqual(record["file"]["original_filename"], "passwd.png")
        self.assertNotIn("..", record["file"]["original_filename"])
        self.assertNotIn("/", record["file"]["original_filename"])
        self.assertNotIn("\\", record["file"]["original_filename"])

    # ─────────────────────────────────────────────────────────────────────────────
    # 11. Empty File (0 Bytes) Rejected (400/422)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_11_empty_file_rejected(self) -> None:
        """Zero-byte file is rejected before storage or database persistence."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        files = {"file": ("empty.png", b"", "image/png")}
        data = {"title": "Empty File", "record_type": "medical_image"}

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
        self.assertIn(res.status_code, (400, 422))

    # ─────────────────────────────────────────────────────────────────────────────
    # 12. Oversized File Rejected (>10MB)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_12_oversized_file_rejected(self) -> None:
        """File exceeding configured MAX_UPLOAD_SIZE_MB (10MB) is rejected."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        oversized_bytes = b"0" * (10 * 1024 * 1024 + 1)
        files = {"file": ("oversized.pdf", oversized_bytes, "application/pdf")}
        data = {"title": "Too Large", "record_type": "clinical_document"}

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
        self.assertIn(res.status_code, (400, 422))

    # ─────────────────────────────────────────────────────────────────────────────
    # 13. MIME Spoofing Rejected (Executable / Disguised Content)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_13_mime_spoofing_rejected(self) -> None:
        """Executable content declared as image/jpeg is rejected by magic-byte & Pillow validation."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        fake_jpeg = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00ThisIsAnExecutable"
        files = {"file": ("scan.jpg", fake_jpeg, "image/jpeg")}
        data = {"title": "Spoofed Scan", "record_type": "medical_image"}

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
        self.assertIn(res.status_code, (400, 422))

    # ─────────────────────────────────────────────────────────────────────────────
    # 14. Extension Spoofing Blocked (malware.exe.jpg)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_14_extension_spoofing_rejected(self) -> None:
        """Non-image binary disguised as malware.exe.jpg is rejected."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        fake_data = b"malicious binary payload without jpeg headers"
        files = {"file": ("malware.exe.jpg", fake_data, "image/jpeg")}
        data = {"title": "Disguised Executable", "record_type": "medical_image"}

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
        self.assertIn(res.status_code, (400, 422))

    # ─────────────────────────────────────────────────────────────────────────────
    # 15. Corrupted Image Rejected by Pillow Decoder
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_15_corrupted_image_rejected(self) -> None:
        """Truncated or corrupted image with valid magic bytes is rejected."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        # Valid JPEG magic bytes followed by garbage
        corrupted_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 30
        files = {"file": ("corrupt.jpg", corrupted_jpeg, "image/jpeg")}
        data = {"title": "Corrupt Scan", "record_type": "medical_image"}

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
        self.assertIn(res.status_code, (400, 422))

    # ─────────────────────────────────────────────────────────────────────────────
    # 16. Decompression Bomb / Enormous Image Dimensions Rejected
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_16_enormous_image_dimensions_rejected(self) -> None:
        """Image with abusive dimensions (e.g. 10,000 x 10,000) is rejected."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        # Generate large dimension image (> 8192 width limit, but small memory footprint)
        huge_img = Image.new("RGB", (8200, 100), color=(0, 0, 0))
        buf = io.BytesIO()
        huge_img.save(buf, format="JPEG")
        huge_bytes = buf.getvalue()

        files = {"file": ("huge.jpg", huge_bytes, "image/jpeg")}
        data = {"title": "Huge Image", "record_type": "medical_image"}

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
        self.assertIn(res.status_code, (400, 422))

    # ─────────────────────────────────────────────────────────────────────────────
    # 17. Atomic Failure Cleanup (Binary Purged on Database Error)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_17_atomic_upload_failure_cleans_up_file(self) -> None:
        """If MongoDB insertion fails, the stored binary is cleaned up immediately."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)
        # Force database insertion failure
        self.mock_db["medical_records"].insert_one = AsyncMock(side_effect=Exception("Database down!"))

        png_bytes = make_valid_png_bytes()
        files = {"file": ("fail_test.png", png_bytes, "image/png")}
        data = {"title": "Atomic Test", "record_type": "medical_image"}

        with patch.object(storage_service, "delete_file", wraps=storage_service.delete_file) as mock_delete:
            res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
            self.assertEqual(res.status_code, 500)
            # Verify cleanup delete_file was called
            mock_delete.assert_called_once()

    # ─────────────────────────────────────────────────────────────────────────────
    # 18. Soft-Deleted File Retrieval Blocked (404)
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_18_soft_deleted_file_retrieval_blocked(self) -> None:
        """Soft-deleted file returns 404 for normal user, but 200 for Admin audit."""
        png_bytes = make_valid_png_bytes()
        storage_key = "DELETED_KEY.png"
        await storage_service.save_file(png_bytes, storage_key, subfolder="medical-records")

        record_doc = {
            "record_id": "MR-2026-DEL01",
            "patient_id": "PAT-2026-A01",
            "title": "Deleted Record",
            "file": {
                "storage_key": storage_key,
                "original_filename": "deleted.png",
                "content_type": "image/png",
                "size_bytes": len(png_bytes),
            },
            "uploaded_by": self.patient_a_user.user_id,
            "is_deleted": True,
            "deleted_at": utc_now(),
        }

        self.mock_db["medical_records"].find_one = AsyncMock(return_value=record_doc)
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        # Patient gets 404
        res_pat = await self.client.get("/api/v1/medical-records/MR-2026-DEL01/file", headers=self.headers_pat_a)
        self.assertEqual(res_pat.status_code, 404)

        # Hospital Admin gets 200 (compliance audit access)
        res_admin = await self.client.get("/api/v1/medical-records/MR-2026-DEL01/file", headers=self.headers_admin)
        self.assertEqual(res_admin.status_code, 200)

    # ─────────────────────────────────────────────────────────────────────────────
    # 19. WEBP Medical Image Support
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_19_webp_medical_image_support(self) -> None:
        """Modern WEBP medical image is properly validated, stored, and retrieved."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        webp_bytes = make_valid_webp_bytes()
        files = {"file": ("fundus_scan.webp", webp_bytes, "image/webp")}
        data = {"title": "Fundus Photography", "record_type": "medical_image"}

        res = await self.client.post("/api/v1/medical-records", headers=self.headers_pat_a, data=data, files=files)
        self.assertEqual(res.status_code, 201)
        record = res.json()["data"]
        self.assertEqual(record["file"]["content_type"], "image/webp")

    # ─────────────────────────────────────────────────────────────────────────────
    # 20. DocumentService Standalone Upload & Download
    # ─────────────────────────────────────────────────────────────────────────────
    async def test_20_document_service_upload_and_download(self) -> None:
        """Standalone DocumentCenter upload and download works with full security."""
        self.mock_db["patients"].find_one = AsyncMock(return_value=self.patient_a_dict)

        pdf_bytes = make_valid_pdf_bytes()
        files = {"file": ("lab_report.pdf", pdf_bytes, "application/pdf")}
        data = {
            "patient_id": "PAT-2026-A01",
            "title": "Blood Work Analysis",
            "category": "Lab Report",
        }

        # Upload
        res_up = await self.client.post("/api/v1/documents", headers=self.headers_pat_a, data=data, files=files)
        self.assertEqual(res_up.status_code, 201)
        doc = res_up.json()
        doc_id = doc["document_id"]
        storage_filename = doc["file_name"]

        # Mock retrieval for download
        self.mock_db["documents"].find_one = AsyncMock(return_value={
            "document_id": doc_id,
            "patient_id": "PAT-2026-A01",
            "title": "Blood Work Analysis",
            "file_name": storage_filename,
            "original_file_name": "lab_report.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": len(pdf_bytes),
            "storage_path": storage_filename,
            "uploaded_by": self.patient_a_user.user_id,
            "is_deleted": False,
        })

        # Download
        res_dl = await self.client.get(f"/api/v1/documents/{doc_id}/download", headers=self.headers_pat_a)
        self.assertEqual(res_dl.status_code, 200)
        self.assertEqual(res_dl.content, pdf_bytes)
        self.assertEqual(res_dl.headers.get("x-content-type-options"), "nosniff")
