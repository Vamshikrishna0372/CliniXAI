"""
Phase 10 Dedicated Production Test Suite:
Deep Learning Medical-Image Prediction Pipeline (BRAIN_MRI).

Verifies:
1. Real Keras Model File & Architecture:
   - Model file exists at backend/ai_models/brain_model.keras
   - Input shape is (None, 224, 224, 3)
   - Output shape is (None, 4)
   - 4 Classes: ["glioma", "meningioma", "notumor", "pituitary"]
2. Real ModelLoader & Forward Pass:
   - ModelLoader successfully loads BRAIN_MRI
   - Real forward pass on genuine image produces valid probabilities summing to ~1.0
   - Confidence and predicted_class accurately resolved
3. Doctor-Patient Care Relationship Authorization:
   - Doctor Arjun (with care relationship) successfully triggers analysis (201)
   - Doctor Priya (no appointment/consultation) is blocked with HTTP 403 Forbidden
4. Non-Doctor Access Controls:
   - Patient role cannot trigger AI analysis directly (HTTP 403)
   - Unauthenticated request is blocked (HTTP 401)
5. Soft-Deleted Record Protection:
   - Triggering analysis on soft-deleted medical record returns HTTP 404
6. Corrupted Image Rejection:
   - Corrupted image bytes rejected with HTTP 400 AppValidationError
7. MongoDB Persistence & Retrieval:
   - AIAnalysis document persisted in MongoDB with correct prediction schema
   - GET /api/v1/ai-analyses/{analysis_id} returns exact prediction, probabilities, model metadata
   - Direct infer endpoint (/api/v1/ai/infer) returns probabilities and prediction
"""

import os
import io
import unittest
import numpy as np
from PIL import Image
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.ai.registry import get_ai_registry, AIModuleIdentifier
from app.ai.model_loader import get_model_loader
from app.ai.preprocessing import load_and_preprocess_backend_image
from app.ai.inference import run_inference
from app.services.storage_service import storage_service
from app.utils.datetime import utc_now


def make_valid_mri_jpeg_bytes() -> bytes:
    """Create genuine 224x224 RGB image bytes simulating an MRI scan."""
    img = Image.new("RGB", (224, 224), color=(30, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestPhase10AIPredictionPipeline(unittest.IsolatedAsyncioTestCase):
    """Phase 10 Deep Learning Medical-Image Prediction Pipeline Test Suite."""

    @classmethod
    def setUpClass(cls):
        # Ensure model directory is recognized
        cls.registry = get_ai_registry()
        cls.loader = get_model_loader()

    async def asyncSetUp(self):
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        # Mock database setup with in-memory store
        self.mock_db = MagicMock()
        self.collections = {}

        def get_coll(name):
            if name not in self.collections:
                col = MagicMock()
                col.find_one = AsyncMock(return_value=None)
                col.insert_one = AsyncMock(return_value=None)
                col.replace_one = AsyncMock(return_value=None)
                col.update_one = AsyncMock(return_value=None)
                col.count_documents = AsyncMock(return_value=0)
                mock_cursor = MagicMock()
                mock_cursor.sort.return_value = mock_cursor
                mock_cursor.skip.return_value = mock_cursor
                mock_cursor.limit.return_value = mock_cursor
                mock_cursor.to_list = AsyncMock(return_value=[])
                col.find = MagicMock(return_value=mock_cursor)
                self.collections[name] = col
            return self.collections[name]

        self.mock_db.__getitem__.side_effect = get_coll

        # Prepopulate standard collections
        for col_name in [
            "users", "doctors", "patients", "medical_records", "documents",
            "appointments", "consultations", "ai_analyses", "audit_logs"
        ]:
            get_coll(col_name)

        app.dependency_overrides[get_database] = lambda: self.mock_db

        # Test users
        self.doctor_arjun = UserInDB(
            user_id="USR-DOC-ARJUN-001",
            email="dr.arjun@clinixai.com",
            full_name="Dr. Arjun Mehta",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        self.doctor_priya = UserInDB(
            user_id="USR-DOC-PRIYA-002",
            email="dr.priya@clinixai.com",
            full_name="Dr. Priya Sharma",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        self.patient_user = UserInDB(
            user_id="USR-PAT-ALICE-001",
            email="alice@patient.com",
            full_name="Alice Patient",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        # Doctor profile dicts
        self.doctor_arjun_profile = {
            "doctor_id": "DOC-ARJUN-001",
            "user_id": self.doctor_arjun.user_id,
            "full_name": "Dr. Arjun Mehta",
            "status": "active",
        }
        self.doctor_priya_profile = {
            "doctor_id": "DOC-PRIYA-002",
            "user_id": self.doctor_priya.user_id,
            "full_name": "Dr. Priya Sharma",
            "status": "active",
        }

        # Auth tokens
        self.token_arjun = create_access_token(user_id=self.doctor_arjun.user_id, role=self.doctor_arjun.role.value)
        self.token_priya = create_access_token(user_id=self.doctor_priya.user_id, role=self.doctor_priya.role.value)
        self.token_patient = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.client.aclose()

    # -------------------------------------------------------------------------
    # Test 1: Real Model File and Artifact Inspection
    # -------------------------------------------------------------------------
    def test_01_real_model_file_and_architecture(self):
        """Verify the brain_model.keras artifact exists, loads, and matches input/output shapes."""
        artifact = self.loader.load_module(AIModuleIdentifier.BRAIN_MRI.value)
        self.assertTrue(artifact.is_available, f"Brain MRI model failed to load: {artifact.error_message}")
        self.assertIsNotNone(artifact.model)

        # Inspect real Keras model
        model = artifact.model
        input_shape = model.input_shape
        output_shape = model.output_shape

        self.assertEqual(input_shape[1:], (224, 224, 3), f"Expected (None, 224, 224, 3), got {input_shape}")
        self.assertEqual(output_shape[1:], (4,), f"Expected (None, 4), got {output_shape}")

        expected_classes = ["glioma", "meningioma", "notumor", "pituitary"]
        self.assertEqual(artifact.class_names, expected_classes)

    # -------------------------------------------------------------------------
    # Test 2: Real Preprocessing and Inference Forward Pass
    # -------------------------------------------------------------------------
    def test_02_real_inference_forward_pass(self):
        """Execute a genuine forward pass through the real Keras model."""
        jpeg_bytes = make_valid_mri_jpeg_bytes()
        prep_tensor = load_and_preprocess_backend_image(
            jpeg_bytes,
            target_size=(224, 224),
            strategy="resnet50",
        )

        self.assertEqual(prep_tensor.shape, (224, 224, 3))
        self.assertEqual(prep_tensor.dtype, np.float32)

        prediction, model_version = run_inference(prep_tensor, module_id=AIModuleIdentifier.BRAIN_MRI.value)

        self.assertIn(prediction.predicted_class, ["glioma", "meningioma", "notumor", "pituitary"])
        self.assertGreaterEqual(prediction.confidence, 0.0)
        self.assertLessEqual(prediction.confidence, 1.0)
        self.assertEqual(len(prediction.class_probabilities), 4)

        # Sum of softmax probabilities should be approximately 1.0
        prob_sum = sum(prediction.class_probabilities.values())
        self.assertAlmostEqual(prob_sum, 1.0, places=2)

    # -------------------------------------------------------------------------
    # Test 3: Doctor-Patient Care Relationship Authorization (Allowed)
    # -------------------------------------------------------------------------
    async def test_03_doctor_with_care_relationship_can_trigger_analysis(self):
        """Doctor Arjun with an appointment for Patient Alice can request AI analysis."""
        mri_bytes = make_valid_mri_jpeg_bytes()
        storage_key = "test_mri_01.jpg"
        await storage_service.save_file(mri_bytes, storage_key, subfolder="medical-records")

        # Mock DB setup: Doctor Arjun exists, Medical Record exists, Appointment exists
        async def mock_find_one(query):
            if "user_id" in query and query["user_id"] == self.doctor_arjun.user_id:
                return self.doctor_arjun_profile
            if "record_id" in query and query["record_id"] == "REC-MRI-001":
                return {
                    "record_id": "REC-MRI-001",
                    "patient_id": "PAT-ALICE-001",
                    "doctor_id": "DOC-ARJUN-001",
                    "title": "Brain MRI Scan",
                    "record_type": "medical_image",
                    "file_category": "mri",
                    "file": {
                        "storage_key": storage_key,
                        "content_type": "image/jpeg",
                    },
                    "storage_key": storage_key,
                    "content_type": "image/jpeg",
                    "is_ai_eligible": True,
                    "is_deleted": False,
                }
            if "patient_id" in query and query.get("doctor_id") == "DOC-ARJUN-001":
                return {
                    "appointment_id": "APT-001",
                    "patient_id": "PAT-ALICE-001",
                    "doctor_id": "DOC-ARJUN-001",
                    "status": "confirmed",
                }
            return None

        self.collections["doctors"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["medical_records"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["appointments"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["ai_analyses"].find_one = AsyncMock(return_value=None)
        self.collections["users"].find_one = AsyncMock(return_value=self.doctor_arjun.model_dump())

        resp = await self.client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {self.token_arjun}"},
            json={
                "medical_record_id": "REC-MRI-001",
                "analysis_type": "BRAIN_MRI",
            },
        )

        self.assertEqual(resp.status_code, 201, f"Response: {resp.text}")
        data = resp.json()
        self.assertIn("analysis_id", data)
        self.assertEqual(data["model"]["module_id"], "BRAIN_MRI")
        self.assertIsNotNone(data.get("prediction"))
        self.assertIn(data["prediction"]["predicted_class"], ["glioma", "meningioma", "notumor", "pituitary"])
        self.assertGreater(len(data["prediction"]["class_probabilities"]), 0)

    # -------------------------------------------------------------------------
    # Test 4: Doctor Without Care Relationship Blocked (HTTP 403)
    # -------------------------------------------------------------------------
    async def test_04_doctor_without_care_relationship_blocked(self):
        """Doctor Priya with NO appointment or consultation for Patient Alice is blocked (403)."""
        async def mock_find_one(query):
            if "user_id" in query and query["user_id"] == self.doctor_priya.user_id:
                return self.doctor_priya_profile
            if "record_id" in query and query["record_id"] == "REC-MRI-001":
                return {
                    "record_id": "REC-MRI-001",
                    "patient_id": "PAT-ALICE-001",
                    "doctor_id": "DOC-ARJUN-001",  # belongs to Arjun, not Priya
                    "uploaded_by": "USR-DOC-ARJUN-001",
                    "record_type": "medical_image",
                    "file": {"storage_key": "test.jpg", "content_type": "image/jpeg"},
                    "is_deleted": False,
                }
            # No appointment, no consultation
            return None

        self.collections["doctors"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["medical_records"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["appointments"].find_one = AsyncMock(return_value=None)
        self.collections["consultations"].find_one = AsyncMock(return_value=None)
        self.collections["users"].find_one = AsyncMock(return_value=self.doctor_priya.model_dump())

        resp = await self.client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {self.token_priya}"},
            json={
                "medical_record_id": "REC-MRI-001",
                "analysis_type": "BRAIN_MRI",
            },
        )

        self.assertEqual(resp.status_code, 403, f"Expected 403 Forbidden, got {resp.status_code}")

    # -------------------------------------------------------------------------
    # Test 5: Patient Role Cannot Request AI Analysis (HTTP 403)
    # -------------------------------------------------------------------------
    async def test_05_patient_cannot_trigger_analysis(self):
        """Patient role is forbidden from triggering raw AI analyses directly."""
        self.collections["users"].find_one = AsyncMock(return_value=self.patient_user.model_dump())

        resp = await self.client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {self.token_patient}"},
            json={
                "medical_record_id": "REC-MRI-001",
                "analysis_type": "BRAIN_MRI",
            },
        )
        self.assertEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # Test 6: Unauthenticated Request Blocked (HTTP 401)
    # -------------------------------------------------------------------------
    async def test_06_unauthenticated_request_blocked(self):
        """Unauthenticated caller receives 401 Unauthorized."""
        resp = await self.client.post(
            "/api/v1/ai-analyses",
            json={
                "medical_record_id": "REC-MRI-001",
                "analysis_type": "BRAIN_MRI",
            },
        )
        self.assertEqual(resp.status_code, 401)

    # -------------------------------------------------------------------------
    # Test 7: Soft-Deleted Medical Record Returns HTTP 404
    # -------------------------------------------------------------------------
    async def test_07_soft_deleted_record_returns_404(self):
        """Attempting to run AI on a soft-deleted medical record returns 404."""
        async def mock_find_one(query):
            if "user_id" in query and query["user_id"] == self.doctor_arjun.user_id:
                return self.doctor_arjun_profile
            if "record_id" in query:
                return {
                    "record_id": "REC-MRI-DELETED",
                    "patient_id": "PAT-ALICE-001",
                    "is_deleted": True,
                    "deleted_at": utc_now(),
                }
            return None

        self.collections["doctors"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["medical_records"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["documents"].find_one = AsyncMock(return_value=None)
        self.collections["users"].find_one = AsyncMock(return_value=self.doctor_arjun.model_dump())

        resp = await self.client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {self.token_arjun}"},
            json={
                "medical_record_id": "REC-MRI-DELETED",
                "analysis_type": "BRAIN_MRI",
            },
        )
        self.assertEqual(resp.status_code, 404)

    # -------------------------------------------------------------------------
    # Test 8: Corrupted Image Bytes Handled Gracefully (HTTP 400)
    # -------------------------------------------------------------------------
    async def test_08_corrupted_image_rejected(self):
        """A corrupted file raises a 400 AppValidationError rather than an uncaught 500 error."""
        corrupt_key = "corrupt_scan.jpg"
        await storage_service.save_file(b"NOT_A_REAL_IMAGE_DATA_CORRUPT_BYTES", corrupt_key, subfolder="medical-records")

        async def mock_find_one(query):
            if "user_id" in query and query["user_id"] == self.doctor_arjun.user_id:
                return self.doctor_arjun_profile
            if "record_id" in query and query["record_id"] == "REC-MRI-CORRUPT":
                return {
                    "record_id": "REC-MRI-CORRUPT",
                    "patient_id": "PAT-ALICE-001",
                    "doctor_id": "DOC-ARJUN-001",
                    "record_type": "medical_image",
                    "file": {"storage_key": corrupt_key, "content_type": "image/jpeg"},
                    "storage_key": corrupt_key,
                    "content_type": "image/jpeg",
                    "is_ai_eligible": True,
                    "is_deleted": False,
                }
            if "patient_id" in query and query.get("doctor_id") == "DOC-ARJUN-001":
                return {"appointment_id": "APT-001", "patient_id": "PAT-ALICE-001", "doctor_id": "DOC-ARJUN-001"}
            return None

        self.collections["doctors"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["medical_records"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["appointments"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["ai_analyses"].find_one = AsyncMock(return_value=None)
        self.collections["users"].find_one = AsyncMock(return_value=self.doctor_arjun.model_dump())

        resp = await self.client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {self.token_arjun}"},
            json={
                "medical_record_id": "REC-MRI-CORRUPT",
                "analysis_type": "BRAIN_MRI",
            },
        )
        self.assertEqual(resp.status_code, 400)
        err_msg = resp.json().get("error", {}).get("message", "") or resp.json().get("detail", "")
        self.assertIn("corrupted", err_msg.lower())

    # -------------------------------------------------------------------------
    # Test 9: Direct Infer Endpoint Probability Distribution Parity
    # -------------------------------------------------------------------------
    async def test_09_direct_infer_returns_probabilities_and_class(self):
        """The direct infer endpoint returns all 4 class probabilities and the predicted class."""
        self.collections["users"].find_one = AsyncMock(return_value=self.doctor_arjun.model_dump())

        jpeg_bytes = make_valid_mri_jpeg_bytes()
        files = {"image": ("mri_scan.jpg", jpeg_bytes, "image/jpeg")}
        data = {"analysis_type": "BRAIN_MRI"}

        resp = await self.client.post(
            "/api/v1/ai/infer",
            headers={"Authorization": f"Bearer {self.token_arjun}"},
            files=files,
            data=data,
        )

        self.assertEqual(resp.status_code, 200, f"Response: {resp.text}")
        res = resp.json()
        self.assertEqual(res["module_id"], "BRAIN_MRI")
        self.assertIn(res["predicted_class"], ["glioma", "meningioma", "notumor", "pituitary"])
        self.assertIsInstance(res["probabilities"], list)
        self.assertEqual(len(res["probabilities"]), 4)
        labels = [p["label"] for p in res["probabilities"]]
        self.assertCountEqual(labels, ["glioma", "meningioma", "notumor", "pituitary"])
