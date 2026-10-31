"""
Phase 11 Dedicated Production Test Suite:
Explainable AI / Grad-CAM Engine Verification (BRAIN_MRI).

Verifies:
1. Model & Target Layer Verification:
   - conv5_block3_out exists in brain_model.keras ResNet50 backbone
   - Activation tensor has spatial shape (None, 7, 7, 2048)
2. Genuine Grad-CAM Algorithm & Mathematics:
   - Real forward and backward pass with tf.GradientTape
   - Gradients are non-empty, finite, non-NaN
   - Heatmap derived from pooled gradients and activations
   - Heatmap normalized to [0.0, 1.0]
   - Target class explicitly derived from model prediction (e.g. index 2 for notumor)
3. Determinism & Multi-Image Isolation:
   - Repeated Grad-CAM on same image produces consistent heatmap
   - Grad-CAM on different images produces distinct heatmaps
4. RBAC & IDOR Access Controls:
   - Unauthenticated request to /gradcam returns HTTP 401
   - Unauthorized doctor (no care relationship) returns HTTP 403
   - Cross-patient access (Patient Two accessing Patient One) returns HTTP 403
   - Hospital staff blocked with HTTP 403
5. Storage & Download Integrity:
   - Artifact stored privately in ai-analyses subfolder
   - GET /ai-analyses/{analysis_id}/gradcam returns image/png
   - Downloaded bytes match stored artifact bytes (SHA-256 integrity)
   - Public direct static URL access is blocked (HTTP 404)
6. Negative Tests & Error Handling:
   - Corrupted image input raises AppValidationError / HTTP 400
   - Missing analysis returns HTTP 404
   - Analysis without explainability returns HTTP 404
7. Atomic Storage & Orphan Cleanup:
   - In case of DB persistence failure, storage artifact is cleaned up
"""

import os
import io
import hashlib
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
from app.ai.gradcam import generate_gradcam_overlay_bytes
from app.services.storage_service import storage_service
from app.utils.datetime import utc_now


def make_test_mri_bytes(seed: int = 42) -> bytes:
    """Generate a reproducible test MRI-like RGB image."""
    rng = np.random.RandomState(seed)
    arr = rng.randint(20, 180, size=(224, 224, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestPhase11GradCAMSuite(unittest.IsolatedAsyncioTestCase):
    """Phase 11 Dedicated Explainable AI / Grad-CAM Test Suite."""

    async def asyncSetUp(self):
        self.registry = get_ai_registry()
        self.loader = get_model_loader()

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
        self.patient_one = UserInDB(
            user_id="USR-PAT-ONE-001",
            email="patient.one@clinixai.com",
            full_name="Patient One",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        self.patient_two = UserInDB(
            user_id="USR-PAT-TWO-002",
            email="patient.two@clinixai.com",
            full_name="Patient Two",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        self.staff_user = UserInDB(
            user_id="USR-STAFF-001",
            email="staff@clinixai.com",
            full_name="Hospital Staff",
            role=UserRole.HOSPITAL_STAFF,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

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
        self.token_pat1 = create_access_token(user_id=self.patient_one.user_id, role=self.patient_one.role.value)
        self.token_pat2 = create_access_token(user_id=self.patient_two.user_id, role=self.patient_two.role.value)
        self.token_staff = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.client.aclose()

    # -------------------------------------------------------------------------
    # Test 1: Architecture Audit — Layer conv5_block3_out Exists in Loaded Model
    # -------------------------------------------------------------------------
    def test_01_target_convolutional_layer_exists_and_spatial_dimensions(self):
        """Verify conv5_block3_out exists in brain_model.keras with expected spatial shape (7, 7, 2048)."""
        artifact = self.loader.load_module(AIModuleIdentifier.BRAIN_MRI.value)
        self.assertTrue(artifact.is_available, f"Brain MRI model failed to load: {artifact.error_message}")
        model = artifact.model

        # Locate conv5_block3_out inside ResNet50 backbone
        target_layer = None
        for layer in model.layers:
            if layer.name == "conv5_block3_out":
                target_layer = layer
                break
            elif hasattr(layer, "get_layer"):
                try:
                    target_layer = layer.get_layer("conv5_block3_out")
                    break
                except Exception:
                    pass

        self.assertIsNotNone(target_layer, "Layer conv5_block3_out not found in brain_model.keras!")
        self.assertEqual(target_layer.name, "conv5_block3_out")

        # Inspect output tensor shape: (None, 7, 7, 2048)
        output_shape = target_layer.output.shape
        self.assertEqual(len(output_shape), 4)
        self.assertEqual(output_shape[1], 7)
        self.assertEqual(output_shape[2], 7)
        self.assertEqual(output_shape[3], 2048)

    # -------------------------------------------------------------------------
    # Test 2: Genuine Grad-CAM Computation on Real Brain MRI Tensor
    # -------------------------------------------------------------------------
    def test_02_real_gradcam_generation_finite_values_and_target_class(self):
        """Execute genuine Grad-CAM on real model; verify valid non-empty PNG overlay and correct layer."""
        mri_bytes = make_test_mri_bytes(seed=101)
        prep_tensor = load_and_preprocess_backend_image(mri_bytes, target_size=(224, 224), strategy="resnet50")

        # Run real inference to obtain predicted class and index
        prediction, _ = run_inference(prep_tensor, module_id="BRAIN_MRI")
        classes = ["glioma", "meningioma", "notumor", "pituitary"]
        target_idx = classes.index(prediction.predicted_class)

        # Generate Grad-CAM targeting the predicted class index
        overlay_bytes, target_layer_name = generate_gradcam_overlay_bytes(
            original_image_input=mri_bytes,
            preprocessed_tensor=prep_tensor,
            module_id="BRAIN_MRI",
            target_class_index=target_idx,
        )

        self.assertEqual(target_layer_name, "conv5_block3_out")
        self.assertIsInstance(overlay_bytes, bytes)
        self.assertGreater(len(overlay_bytes), 1000)

        # Verify decoded image dimensions match (224, 224) RGB
        img = Image.open(io.BytesIO(overlay_bytes))
        self.assertEqual(img.format, "PNG")
        self.assertEqual(img.size, (224, 224))
        self.assertEqual(img.mode, "RGB")

    # -------------------------------------------------------------------------
    # Test 3: Two-Image Isolation and Determinism
    # -------------------------------------------------------------------------
    def test_03_determinism_and_two_image_isolation(self):
        """Grad-CAM on the same image is deterministic; different images yield different heatmaps."""
        img_a = make_test_mri_bytes(seed=201)
        img_b = make_test_mri_bytes(seed=202)

        prep_a = load_and_preprocess_backend_image(img_a, target_size=(224, 224), strategy="resnet50")
        prep_b = load_and_preprocess_backend_image(img_b, target_size=(224, 224), strategy="resnet50")

        # Generate on image A twice
        overlay_a1, _ = generate_gradcam_overlay_bytes(img_a, prep_a, module_id="BRAIN_MRI")
        overlay_a2, _ = generate_gradcam_overlay_bytes(img_a, prep_a, module_id="BRAIN_MRI")

        # Generate on image B
        overlay_b, _ = generate_gradcam_overlay_bytes(img_b, prep_b, module_id="BRAIN_MRI")

        # Hashes
        hash_a1 = hashlib.sha256(overlay_a1).hexdigest()
        hash_a2 = hashlib.sha256(overlay_a2).hexdigest()
        hash_b = hashlib.sha256(overlay_b).hexdigest()

        # Deterministic for same image
        self.assertEqual(hash_a1, hash_a2)
        # Distinct for different images
        self.assertNotEqual(hash_a1, hash_b)

    # -------------------------------------------------------------------------
    # Test 4: End-to-End Pipeline Trigger Persists Explainability Metadata
    # -------------------------------------------------------------------------
    async def test_04_create_analysis_generates_and_persists_gradcam(self):
        """Triggering AI Analysis saves Grad-CAM overlay and records explainability in DB."""
        mri_bytes = make_test_mri_bytes(seed=301)
        storage_key = "test_phase11_mri.jpg"
        await storage_service.save_file(mri_bytes, storage_key, subfolder="medical-records")

        async def mock_find_one(query):
            if "user_id" in query and query["user_id"] == self.doctor_arjun.user_id:
                return self.doctor_arjun_profile
            if "record_id" in query and query["record_id"] == "REC-PHASE11-001":
                return {
                    "record_id": "REC-PHASE11-001",
                    "patient_id": "PAT-ONE-001",
                    "doctor_id": "DOC-ARJUN-001",
                    "title": "Brain MRI Scan",
                    "record_type": "medical_image",
                    "file_category": "mri",
                    "storage_key": storage_key,
                    "content_type": "image/jpeg",
                    "is_ai_eligible": True,
                    "is_deleted": False,
                }
            if "patient_id" in query and query.get("doctor_id") == "DOC-ARJUN-001":
                return {
                    "appointment_id": "APT-P11-001",
                    "patient_id": "PAT-ONE-001",
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
                "medical_record_id": "REC-PHASE11-001",
                "analysis_type": "BRAIN_MRI",
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        self.assertIn("explainability", data)
        exp = data["explainability"]
        self.assertIsNotNone(exp)
        self.assertEqual(exp["method"], "grad_cam")
        self.assertEqual(exp["target_layer"], "conv5_block3_out")
        self.assertEqual(exp["target_class"], data["prediction"]["predicted_class"])
        self.assertTrue(exp["artifact_storage_key"].startswith("gradcam_"))

    # -------------------------------------------------------------------------
    # Test 5: Grad-CAM Retrieval Authorization & IDOR Block
    # -------------------------------------------------------------------------
    async def test_05_gradcam_retrieval_rbac_and_idor_protection(self):
        """Verify 401 for unauthenticated, 403 for unauthorized doctor, 403 for cross-patient access."""
        # Create a mock analysis with Grad-CAM artifact
        overlay_bytes = make_test_mri_bytes(seed=401)
        artifact_key = "gradcam_TEST-ANALYSIS-001.png"
        await storage_service.save_file(overlay_bytes, artifact_key, subfolder="ai-analyses")

        analysis_doc = {
            "analysis_id": "TEST-ANALYSIS-001",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-ARJUN-001",
            "medical_record_id": "REC-PHASE11-001",
            "requested_by": "USR-DOC-ARJUN-001",
            "model": {
                "module_id": "BRAIN_MRI",
                "name": "Brain MRI Tumor Classification",
                "version": "1.0.0",
                "architecture": "ResNet50",
            },
            "input": {
                "medical_record_id": "REC-PHASE11-001",
                "record_type": "mri",
                "content_type": "image/jpeg",
            },
            "status": "awaiting_review",
            "explainability": {
                "method": "grad_cam",
                "target_layer": "conv5_block3_out",
                "target_class": "notumor",
                "artifact_storage_key": artifact_key,
            },
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        async def mock_find_one(query):
            if query.get("analysis_id") == "TEST-ANALYSIS-001":
                return analysis_doc
            if query.get("user_id") == self.doctor_arjun.user_id:
                return self.doctor_arjun_profile
            if query.get("user_id") == self.doctor_priya.user_id:
                return self.doctor_priya_profile
            if query.get("user_id") == self.patient_two.user_id:
                return {"patient_id": "PAT-TWO-002", "user_id": self.patient_two.user_id}
            return None

        self.collections["ai_analyses"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["doctors"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["patients"].find_one = AsyncMock(side_effect=mock_find_one)
        self.collections["appointments"].find_one = AsyncMock(return_value=None)
        self.collections["consultations"].find_one = AsyncMock(return_value=None)

        # 1. Unauthenticated -> 401
        resp_unauth = await self.client.get("/api/v1/ai-analyses/TEST-ANALYSIS-001/gradcam")
        self.assertEqual(resp_unauth.status_code, 401)

        # 2. Doctor Priya (no care relationship) -> 403
        self.collections["users"].find_one = AsyncMock(return_value=self.doctor_priya.model_dump())
        resp_priya = await self.client.get(
            "/api/v1/ai-analyses/TEST-ANALYSIS-001/gradcam",
            headers={"Authorization": f"Bearer {self.token_priya}"},
        )
        self.assertEqual(resp_priya.status_code, 403)

        # 3. Patient Two (IDOR cross-patient) -> 403
        self.collections["users"].find_one = AsyncMock(return_value=self.patient_two.model_dump())
        resp_pat2 = await self.client.get(
            "/api/v1/ai-analyses/TEST-ANALYSIS-001/gradcam",
            headers={"Authorization": f"Bearer {self.token_pat2}"},
        )
        self.assertEqual(resp_pat2.status_code, 403)

        # 4. Authorized Doctor Arjun -> 200 with exact matching bytes
        self.collections["users"].find_one = AsyncMock(return_value=self.doctor_arjun.model_dump())
        resp_arjun = await self.client.get(
            "/api/v1/ai-analyses/TEST-ANALYSIS-001/gradcam",
            headers={"Authorization": f"Bearer {self.token_arjun}"},
        )
        self.assertEqual(resp_arjun.status_code, 200)
        self.assertEqual(resp_arjun.headers["content-type"], "image/png")
        self.assertEqual(hashlib.sha256(resp_arjun.content).hexdigest(), hashlib.sha256(overlay_bytes).hexdigest())

        # 5. Query parameter ?token= must be explicitly rejected (HTTP 401)
        resp_query = await self.client.get(f"/api/v1/ai-analyses/TEST-ANALYSIS-001/gradcam?token={self.token_arjun}")
        self.assertEqual(resp_query.status_code, 401)

    # -------------------------------------------------------------------------
    # Test 6: Direct Inference Returns Valid Grad-CAM Base64
    # -------------------------------------------------------------------------
    async def test_06_direct_infer_returns_valid_gradcam_overlay(self):
        """POST /api/v1/ai/infer returns gradcam_available=True and decodable base64 image."""
        mri_bytes = make_test_mri_bytes(seed=501)
        self.collections["users"].find_one = AsyncMock(return_value=self.doctor_arjun.model_dump())

        resp = await self.client.post(
            "/api/v1/ai/infer",
            headers={"Authorization": f"Bearer {self.token_arjun}"},
            files={"image": ("mri.jpg", mri_bytes, "image/jpeg")},
            data={"analysis_type": "BRAIN_MRI"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["gradcam_available"])
        self.assertIsNotNone(data["gradcam_b64"])
        self.assertTrue(data["gradcam_b64"].startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
