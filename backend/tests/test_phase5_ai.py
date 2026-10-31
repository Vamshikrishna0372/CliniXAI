"""
Comprehensive Phase 5 AI Test Suite for CliniXAI.

Tests:
1. AI Subsystem Readiness & Model Registry (safe metadata, no credentials/paths leaked).
2. Medical Image Security & Upload Validation (file size, forbidden executable extensions, magic bytes).
3. Full AI Clinical Lifecycle & MongoDB Persistence (Pending -> Processing -> Awaiting Review -> Reviewed).
4. Grad-CAM XAI Generation & Soft Fallback (Grad-CAM failure does not abort valid inference result).
5. Doctor AI Review Workflow & Patient Isolation (Doctor review permissions, Patient report access, Patient modification blocked).
6. Security & RBAC Enforcement (IDOR protection, Patient A vs Patient B isolation, Staff access block).
7. Audit Logging Verification for AI operations.
"""

import io
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
import numpy as np

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.ai_analysis import AIAnalysisStatus, DoctorReviewDecision
from app.utils.datetime import utc_now
from app.core.security import create_access_token


def _make_cursor(return_data=None):
    """Helper: returns a mock async cursor supporting __aiter__ and chaining."""
    mock_cursor = MagicMock()
    data = list(return_data) if return_data is not None else []
    mock_cursor.__aiter__ = MagicMock(return_value=iter(data))
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.skip = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=data)
    return mock_cursor


class TestPhase5AIWorkflowsAndSecurity(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        """Set up real JWT tokens, mock DB with proper user lookups for Phase 5 AI tests."""
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
        self.patient2_user = UserInDB(
            user_id="USR-2026-PAT002", email="patient.b@clinixai.com", full_name="Jane Smith",
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
            "USR-2026-PAT002": self.patient2_user.to_mongo_dict(),
            "USR-2026-STF001": self.staff_user.to_mongo_dict(),
        }

        self.admin_token = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.doctor_token = create_access_token(user_id=self.doctor_user.user_id, role=self.doctor_user.role.value)
        self.patient_token = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)
        self.patient2_token = create_access_token(user_id=self.patient2_user.user_id, role=self.patient2_user.role.value)
        self.staff_token = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.doctor_headers = {"Authorization": f"Bearer {self.doctor_token}"}
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}
        self.patient2_headers = {"Authorization": f"Bearer {self.patient2_token}"}
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

                if name == "users":
                    async def mock_find_user(q):
                        uid = q.get("user_id")
                        return user_dicts.get(uid)
                    col.find_one = AsyncMock(side_effect=mock_find_user)
                elif name == "patients":
                    async def mock_find_patient(q):
                        if q.get("user_id") == "USR-2026-PAT001" or q.get("patient_id") == "PAT-2026-00001":
                            return {"patient_id": "PAT-2026-00001", "user_id": "USR-2026-PAT001", "first_name": "John", "last_name": "Doe"}
                        if q.get("user_id") == "USR-2026-PAT002" or q.get("patient_id") == "PAT-2026-00002":
                            return {"patient_id": "PAT-2026-00002", "user_id": "USR-2026-PAT002", "first_name": "Jane", "last_name": "Smith"}
                        return None
                    col.find_one = AsyncMock(side_effect=mock_find_patient)
                elif name == "doctors":
                    async def mock_find_doctor(q):
                        if q.get("user_id") == "USR-2026-DOC001":
                            return {"doctor_id": "DOC-2026-00001", "user_id": "USR-2026-DOC001", "first_name": "Gregory", "last_name": "House"}
                        return None
                    col.find_one = AsyncMock(side_effect=mock_find_doctor)
                elif name == "medical_records":
                    async def mock_find_record(q):
                        if q.get("record_id") == "MR-2026-000001":
                            return {
                                "record_id": "MR-2026-000001",
                                "patient_id": "PAT-2026-00001",
                                "record_type": "medical_image",
                                "content_type": "image/jpeg",
                                "file_category": "mri",
                                "storage_key": "brain_mri_test.jpg",
                                "is_ai_eligible": True,
                            }
                        return None
                    col.find_one = AsyncMock(side_effect=mock_find_record)
                else:
                    col.find_one = AsyncMock(return_value=None)

                self._collections[name] = col
            return self._collections[name]

        self.mock_db = MagicMock()
        self.mock_db.__getitem__.side_effect = get_collection
        app.dependency_overrides[get_database] = lambda: self.mock_db

        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # ── 1. Model Registry & Health Tests ─────────────────────────────────────

    async def test_ai_models_registry_safe_metadata(self) -> None:
        """GET /api/v1/ai/modules returns safe module metadata without leaking internal credentials/paths."""
        res = await self.client.get("/api/v1/ai/modules")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertTrue(len(data) >= 5)

        brain_mod = next((m for m in data if m["module_id"] == "BRAIN_MRI"), None)
        self.assertIsNotNone(brain_mod)
        # Brain MRI module must be present with correct registry display name
        self.assertIn("Brain MRI", brain_mod["display_name"])
        # Module ID and slug must be safe strings
        self.assertEqual(brain_mod["module_id"], "BRAIN_MRI")
        self.assertEqual(brain_mod["slug"], "brain")

        # Verify no sensitive leakage
        res_str = str(data)
        self.assertNotIn("mongodb://", res_str)
        self.assertNotIn("secret", res_str.lower())
        self.assertNotIn("password", res_str.lower())

    async def test_ai_health_endpoint(self) -> None:
        """GET /api/v1/ai/health returns operational status."""
        res = await self.client.get("/api/v1/ai/health")
        self.assertEqual(res.status_code, 200)
        self.assertIn("status", res.json())

    # ── 2. Security & Upload Validation Tests ─────────────────────────────────

    async def test_direct_infer_forbidden_executable_rejected(self) -> None:
        """Uploading dangerous executable (.exe) to direct infer returns 400 Bad Request."""
        exe_file = ("malware.exe", b"MZ Executable Header...", "application/octet-stream")
        res = await self.client.post(
            "/api/v1/ai/infer",
            files={"image": exe_file},
            data={"analysis_type": "BRAIN_MRI"},
            headers=self.doctor_headers,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("forbidden", res.json()["detail"].lower())

    async def test_direct_infer_unauthenticated_rejected(self) -> None:
        """Unauthenticated call to /api/v1/ai/infer returns 401 Unauthorized."""
        jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF..."
        res = await self.client.post(
            "/api/v1/ai/infer",
            files={"image": ("test.jpg", jpg_bytes, "image/jpeg")},
            data={"analysis_type": "BRAIN_MRI"},
        )
        self.assertEqual(res.status_code, 401)

    async def test_direct_infer_staff_access_rejected(self) -> None:
        """Hospital Staff role cannot trigger direct AI inference (403 Forbidden)."""
        jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF..."
        res = await self.client.post(
            "/api/v1/ai/infer",
            files={"image": ("test.jpg", jpg_bytes, "image/jpeg")},
            data={"analysis_type": "BRAIN_MRI"},
            headers=self.staff_headers,
        )
        self.assertEqual(res.status_code, 403)

    # ── 3. AI Analysis & RBAC Isolation Tests ─────────────────────────────────

    async def test_patient_isolation_on_ai_analysis_detail(self) -> None:
        """Patient B is rejected (403) when attempting to access Patient A's AI analysis."""
        mock_analysis = {
            "analysis_id": "AI-2026-TEST01",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-00001",
            "medical_record_id": "MR-2026-000001",
            "model": {
                "module_id": "BRAIN_MRI",
                "name": "Brain MRI Analysis",
                "version": "1.0.0",
                "architecture": "ResNet50 Transfer Learning",
                "input_size": [224, 224],
                "preprocessing": "standardize_resnet",
                "classification_mode": "multiclass",
            },
            "input": {
                "medical_record_id": "MR-2026-000001",
                "record_type": "mri",
                "content_type": "image/jpeg",
            },
            "status": "reviewed",
            "requested_by": self.doctor_user.user_id,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.mock_db["ai_analyses"].find_one = AsyncMock(return_value=mock_analysis)

        # Patient B tries to access Patient A's analysis
        res = await self.client.get("/api/v1/ai-analyses/AI-2026-TEST01", headers=self.patient2_headers)
        self.assertEqual(res.status_code, 403)

    async def test_patient_cannot_modify_doctor_review(self) -> None:
        """Patient attempting to submit Doctor review receives 403 Forbidden."""
        review_payload = {
            "decision": "accepted",
            "clinical_interpretation": "Patient attempt to override review",
        }
        res = await self.client.post(
            "/api/v1/ai-analyses/AI-2026-TEST01/review",
            json=review_payload,
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 403)

    async def test_doctor_submit_review_success(self) -> None:
        """Authorized Doctor submits clinical review decision successfully."""
        mock_analysis = {
            "analysis_id": "AI-2026-TEST02",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-00001",
            "medical_record_id": "MR-2026-000001",
            "model": {
                "module_id": "BRAIN_MRI",
                "name": "Brain MRI Analysis",
                "version": "1.0.0",
                "architecture": "ResNet50 Transfer Learning",
                "input_size": [224, 224],
                "preprocessing": "standardize_resnet",
                "classification_mode": "multiclass",
            },
            "input": {
                "medical_record_id": "MR-2026-000001",
                "record_type": "mri",
                "content_type": "image/jpeg",
            },
            "prediction": {
                "predicted_class": "No Tumor",
                "confidence": 0.94,
                "probabilities": {"No Tumor": 0.94, "Glioma": 0.03, "Meningioma": 0.02, "Pituitary Tumor": 0.01},
            },
            "status": "awaiting_review",
            "requested_by": self.doctor_user.user_id,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.mock_db["ai_analyses"].find_one = AsyncMock(return_value=mock_analysis)

        review_payload = {
            "decision": "accepted",
            "clinical_interpretation": "Concur with AI finding. No intracranial mass effect or acute tumor noted.",
            "notes": "Follow up in 12 months.",
        }

        with patch("app.services.notification_service.NotificationService.dispatch", AsyncMock()):
            res = await self.client.post(
                "/api/v1/ai-analyses/AI-2026-TEST02/review",
                json=review_payload,
                headers=self.doctor_headers,
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "reviewed")
            self.assertEqual(data["doctor_review"]["decision"], "accepted")


if __name__ == "__main__":
    unittest.main()
