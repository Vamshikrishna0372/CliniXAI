"""
Comprehensive Unit Test Suite for Phase 8: FastAPI AI/XAI Integration.

Tests AI subsystem health, model loader availability checks, medical record image
eligibility validation, role authorization, mock ResNet50 inference & Grad-CAM,
Doctor review workflow, Patient-safe report access isolation, and Admin AI operational metrics.
"""

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


class TestPhase8AIIntegration(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        """Set up real JWT tokens, mock DB with proper user lookups for Phase 8 tests."""
        # ── User objects ──────────────────────────────────────────────────────
        self.admin_user = UserInDB(
            user_id="USR-2026-ADM001", email="admin@clinixai.com", full_name="Admin User",
            role=UserRole.HOSPITAL_ADMIN, auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        self.doctor_user = UserInDB(
            user_id="USR-2026-DOC001", email="dr.house@clinixai.com", full_name="Dr. Gregory House",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        self.patient_user = UserInDB(
            user_id="USR-2026-PAT001", email="patient.a@clinixai.com", full_name="John Doe",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        self.patient2_user = UserInDB(
            user_id="USR-2026-PAT002", email="patient.b@clinixai.com", full_name="Jane Smith",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        self.staff_user = UserInDB(
            user_id="USR-2026-STF001", email="staff@clinixai.com", full_name="Staff Member",
            role=UserRole.HOSPITAL_STAFF, auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        # User dicts for DB mock (auth layer fetches user by user_id)
        self._user_dicts = {
            "USR-2026-ADM001": self.admin_user.to_mongo_dict(),
            "USR-2026-DOC001": self.doctor_user.to_mongo_dict(),
            "USR-2026-PAT001": self.patient_user.to_mongo_dict(),
            "USR-2026-PAT002": self.patient2_user.to_mongo_dict(),
            "USR-2026-STF001": self.staff_user.to_mongo_dict(),
        }

        # ── JWT tokens ────────────────────────────────────────────────────────
        self.admin_token = create_access_token(
            user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.doctor_token = create_access_token(
            user_id=self.doctor_user.user_id, role=self.doctor_user.role.value)
        self.patient_token = create_access_token(
            user_id=self.patient_user.user_id, role=self.patient_user.role.value)
        self.patient2_token = create_access_token(
            user_id=self.patient2_user.user_id, role=self.patient2_user.role.value)
        self.staff_token = create_access_token(
            user_id=self.staff_user.user_id, role=self.staff_user.role.value)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.doctor_headers = {"Authorization": f"Bearer {self.doctor_token}"}
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}
        self.patient2_headers = {"Authorization": f"Bearer {self.patient2_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}

        # ── Mock database ─────────────────────────────────────────────────────
        self._collections: dict = {}
        user_dicts = self._user_dicts  # capture for closure

        def get_collection(name):
            if name not in self._collections:
                col = MagicMock()
                col.insert_one = AsyncMock(return_value=None)
                col.replace_one = AsyncMock(return_value=None)
                col.update_one = AsyncMock(return_value=None)
                col.count_documents = AsyncMock(return_value=0)
                col.find = MagicMock(return_value=_make_cursor([]))
                col.aggregate = MagicMock(return_value=_make_cursor([]))
                # Default find_one returns None; tests override per-test
                col.find_one = AsyncMock(return_value=None)
                self._collections[name] = col
            return self._collections[name]

        self.mock_db = MagicMock()
        self.mock_db.__getitem__.side_effect = get_collection

        # Users collection auto-resolves by user_id (needed by JWT auth middleware)
        async def users_find_one(query, *args, **kwargs):
            uid = query.get("user_id")
            return user_dicts.get(uid)

        get_collection("users").find_one = users_find_one

        async def override_get_db():
            return self.mock_db

        app.dependency_overrides[get_database] = override_get_db

        # ── Domain entity dicts ───────────────────────────────────────────────
        self.patient_dict = {
            "patient_id": "PAT-2026-00001",
            "user_id": "USR-2026-PAT001",
            "first_name": "John", "last_name": "Doe",
        }
        self.patient2_dict = {
            "patient_id": "PAT-2026-00002",
            "user_id": "USR-2026-PAT002",
            "first_name": "Jane", "last_name": "Smith",
        }
        self.doctor_dict = {
            "doctor_id": "DOC-2026-000001",
            "user_id": "USR-2026-DOC001",
            "first_name": "Gregory", "last_name": "House",
        }
        self.image_record_dict = {
            "record_id": "MR-2026-XRAY01",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-000001",
            "record_type": "xray",
            "file_category": "xray",
            "content_type": "image/jpeg",
            "storage_key": "xray.jpg",
            "is_ai_eligible": True,
        }
        self.pdf_record_dict = {
            "record_id": "MR-2026-DOC001",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-000001",
            "record_type": "lab_report",
            "file_category": "lab_report",
            "content_type": "application/pdf",
            "storage_key": "report.pdf",
            "is_ai_eligible": False,
        }

        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()


    # ── Test 1: AI Health Endpoint ──────────────────────────────────────────
    async def test_ai_health_endpoint(self) -> None:
        """GET /api/v1/ai/health returns status and model health metadata."""
        res = await self.client.get("/api/v1/ai/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("ai_enabled", data)
        self.assertIn("model_loaded", data)

    # ── Test 2: Patient Role Request AI Analysis Rejected ────────────────────
    async def test_patient_request_ai_analysis_rejected(self) -> None:
        """Patient attempting POST /api/v1/ai-analyses is rejected with 403 Forbidden."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"medical_record_id": "MR-2026-XRAY01"},
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 403)

    # ── Test 3: Staff Role Request AI Analysis Rejected ──────────────────────
    async def test_staff_request_ai_analysis_rejected(self) -> None:
        """Hospital Staff attempting POST /api/v1/ai-analyses is rejected with 403 Forbidden."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"medical_record_id": "MR-2026-XRAY01"},
            headers=self.staff_headers,
        )
        self.assertEqual(res.status_code, 403)

    # ── Test 4: Non-Image Record AI Analysis Rejected ────────────────────
    async def test_non_image_record_rejected(self) -> None:
        """Requesting AI analysis on a non-image PDF record is rejected with 400 Bad Request."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["medical_records"].find_one.return_value = self.pdf_record_dict

        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"medical_record_id": "MR-2026-DOC001"},
            headers=self.doctor_headers,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("not an eligible medical image", res.json()["error"]["message"])

    # ── Test 5: Model Unavailable Graceful Creation ─────────────────────────
    @patch("app.services.ai_service.get_model_loader")
    async def test_model_unavailable_graceful_creation(self, mock_loader_getter) -> None:
        """When model is unavailable, analysis is created in model_unavailable status."""
        mock_loader = MagicMock()
        mock_loader.is_available = False
        mock_loader.model_name = "clinixai-resnet50-v1"
        mock_loader.model_version = "1.0.0"
        mock_loader.architecture = "ResNet50"
        mock_loader.error_message = "Model weights not found."
        mock_loader_getter.return_value = mock_loader

        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["medical_records"].find_one.return_value = self.image_record_dict
        self.mock_db["ai_analyses"].find_one.return_value = None

        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"medical_record_id": "MR-2026-XRAY01"},
            headers=self.doctor_headers,
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], AIAnalysisStatus.MODEL_UNAVAILABLE.value)
        self.assertIn("analysis_id", data)

    # ── Test 6: Mock Inference & Grad-CAM Execution ─────────────────────────
    @patch("app.services.ai_service.get_model_loader")
    @patch("app.services.ai_service.get_storage_service")
    @patch("app.services.ai_service.generate_gradcam_overlay_bytes")
    @patch("app.services.ai_service.run_inference")
    @patch("app.services.ai_service.load_and_preprocess_backend_image")
    async def test_successful_ai_analysis_execution(
        self, mock_preprocess, mock_run_inference, mock_gradcam, mock_storage_getter, mock_loader_getter
    ) -> None:
        """Doctor triggers analysis with mock model -> status becomes awaiting_review."""
        from app.models.ai_analysis import PredictionResult

        # Setup mock loader
        mock_loader = MagicMock()
        mock_loader.is_available = True
        mock_loader.model_name = "clinixai-resnet50-v1"
        mock_loader.model_version = "1.0.0"
        mock_loader.architecture = "ResNet50"
        mock_loader.gradcam_target_layer = "conv5_block3_out"
        mock_loader.class_names = ["Normal", "Pneumonia"]
        mock_loader.metadata = {"decision_threshold": 0.5}
        mock_loader_getter.return_value = mock_loader

        # Mock preprocessing
        mock_preprocess.return_value = np.zeros((1, 224, 224, 3), dtype=np.float32)

        # Mock run_inference returning a PredictionResult
        mock_prediction = PredictionResult(
            predicted_class="Pneumonia",
            confidence=0.85,
            class_probabilities={"Normal": 0.15, "Pneumonia": 0.85},
            decision_threshold=0.5,
            low_confidence=False,
        )
        mock_run_inference.return_value = (mock_prediction, "1.0.0")

        # Mock Storage
        mock_storage = AsyncMock()
        mock_storage.read_file.return_value = b"fake_jpeg_bytes"
        mock_storage.save_file.return_value = "gradcam_AI-2026-000001.png"
        mock_storage_getter.return_value = mock_storage

        mock_gradcam.return_value = (b"fake_png_overlay_bytes", "conv5_block3_out")

        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["medical_records"].find_one.return_value = self.image_record_dict
        self.mock_db["ai_analyses"].find_one.return_value = None

        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"medical_record_id": "MR-2026-XRAY01"},
            headers=self.doctor_headers,
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], AIAnalysisStatus.AWAITING_REVIEW.value)
        self.assertIsNotNone(data["prediction"])
        self.assertEqual(data["prediction"]["predicted_class"], "Pneumonia")


    # ── Test 7: Patient Cannot Access Unreviewed Analysis ────────────────────
    async def test_patient_unreviewed_analysis_forbidden(self) -> None:
        """Patient attempting GET /api/v1/ai-analyses/{id} on unreviewed analysis is rejected."""
        unreviewed_doc = {
            "analysis_id": "AI-2026-000001",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-000001",
            "medical_record_id": "MR-2026-XRAY01",
            "model": {"name": "ResNet50", "version": "1.0.0", "architecture": "ResNet50", "input_size": [224, 224], "preprocessing": "resnet50.preprocess_input"},
            "input": {"medical_record_id": "MR-2026-XRAY01", "record_type": "xray", "content_type": "image/jpeg"},
            "status": AIAnalysisStatus.AWAITING_REVIEW.value,
            "requested_by": "USR-2026-DOC001",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.mock_db["ai_analyses"].find_one.return_value = unreviewed_doc
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        res = await self.client.get(
            "/api/v1/ai-analyses/AI-2026-000001",
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 403)

    # ── Test 8: Doctor Submit Clinical Review ─────────────────────────────────
    async def test_doctor_submit_review(self) -> None:
        """Doctor submits POST /api/v1/ai-analyses/{id}/review -> status updates to REVIEWED."""
        awaiting_doc = {
            "analysis_id": "AI-2026-000001",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-000001",
            "medical_record_id": "MR-2026-XRAY01",
            "model": {"name": "ResNet50", "version": "1.0.0", "architecture": "ResNet50", "input_size": [224, 224], "preprocessing": "resnet50.preprocess_input"},
            "input": {"medical_record_id": "MR-2026-XRAY01", "record_type": "xray", "content_type": "image/jpeg"},
            "prediction": {"predicted_class": "Pneumonia", "confidence": 0.85, "class_probabilities": {"Normal": 0.15, "Pneumonia": 0.85}},
            "status": AIAnalysisStatus.AWAITING_REVIEW.value,
            "requested_by": "USR-2026-DOC001",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.mock_db["ai_analyses"].find_one.return_value = awaiting_doc
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        review_payload = {
            "decision": DoctorReviewDecision.ACCEPTED_AS_SUPPORTING.value,
            "clinical_interpretation": "Right lower lobe consolidation noted on X-ray, consistent with bacterial pneumonia.",
            "notes": "Recommend starting Amoxicillin.",
        }

        res = await self.client.post(
            "/api/v1/ai-analyses/AI-2026-000001/review",
            json=review_payload,
            headers=self.doctor_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], AIAnalysisStatus.REVIEWED.value)
        self.assertIsNotNone(data["doctor_review"])
        self.assertIsNotNone(data["patient_report"])

    # ── Test 9: Patient Retrieves Reviewed Report ─────────────────────────────
    async def test_patient_retrieves_reviewed_report(self) -> None:
        """Patient accesses GET /api/v1/ai-analyses/{id}/report -> returns patient-safe report."""
        reviewed_doc = {
            "analysis_id": "AI-2026-000001",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-000001",
            "medical_record_id": "MR-2026-XRAY01",
            "model": {"name": "ResNet50", "version": "1.0.0", "architecture": "ResNet50", "input_size": [224, 224], "preprocessing": "resnet50.preprocess_input"},
            "input": {"medical_record_id": "MR-2026-XRAY01", "record_type": "xray", "content_type": "image/jpeg"},
            "status": AIAnalysisStatus.REVIEWED.value,
            "patient_report": {
                "report_date": utc_now().isoformat(),
                "doctor_name": "Dr. Gregory House",
                "status": "reviewed",
                "result_summary": "AI Decision Support: Pneumonia (Confidence: 85.0%)",
                "model_confidence": 0.85,
                "doctor_interpretation": "Right lower lobe consolidation noted.",
                "disclaimer": "CliniXAI AI analysis is intended for clinical decision support only.",
            },
            "requested_by": "USR-2026-DOC001",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.mock_db["ai_analyses"].find_one.return_value = reviewed_doc
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        res = await self.client.get(
            "/api/v1/ai-analyses/AI-2026-000001/report",
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["analysis_id"], "AI-2026-000001")
        self.assertEqual(data["report"]["doctor_name"], "Dr. Gregory House")

    # ── Test 10: Unauthorized Patient Report Rejected ─────────────────────────
    async def test_unauthorized_patient_report_rejected(self) -> None:
        """Patient B attempting to access Patient A's report is rejected with 403 Forbidden."""
        reviewed_doc = {
            "analysis_id": "AI-2026-000001",
            "patient_id": "PAT-2026-00001",   # Patient A
            "doctor_id": "DOC-2026-000001",
            "medical_record_id": "MR-2026-XRAY01",
            "model": {"name": "ResNet50", "version": "1.0.0", "architecture": "ResNet50", "input_size": [224, 224], "preprocessing": "resnet50.preprocess_input"},
            "input": {"medical_record_id": "MR-2026-XRAY01", "record_type": "xray", "content_type": "image/jpeg"},
            "status": AIAnalysisStatus.REVIEWED.value,
            "patient_report": {"status": "reviewed", "result_summary": "Pneumonia", "disclaimer": "Safety notice"},
            "requested_by": "USR-2026-DOC001",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.mock_db["ai_analyses"].find_one.return_value = reviewed_doc
        self.mock_db["patients"].find_one.return_value = self.patient2_dict  # Patient B

        res = await self.client.get(
            "/api/v1/ai-analyses/AI-2026-000001/report",
            headers=self.patient2_headers,
        )
        self.assertEqual(res.status_code, 403)

    # ── Test 11: Admin AI Insights ───────────────────────────────────────────
    async def test_admin_ai_insights(self) -> None:
        """Hospital Admin fetches aggregated AI insights and metrics."""
        self.mock_db["ai_analyses"].count_documents.side_effect = [10, 6, 3, 1]

        mock_status_cursor = AsyncMock()
        mock_status_cursor.__aiter__.return_value = [
            {"_id": "reviewed", "count": 6},
            {"_id": "awaiting_review", "count": 3},
            {"_id": "failed", "count": 1},
        ]
        mock_version_cursor = AsyncMock()
        mock_version_cursor.__aiter__.return_value = [
            {"_id": "1.0.0", "count": 10},
        ]

        self.mock_db["ai_analyses"].aggregate.side_effect = [mock_status_cursor, mock_version_cursor]

        res = await self.client.get(
            "/api/v1/admin/ai-insights",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_analyses"], 10)
        self.assertEqual(data["reviewed_count"], 6)


if __name__ == "__main__":
    unittest.main()
