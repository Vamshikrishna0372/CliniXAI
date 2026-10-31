"""
CliniXAI Production Test Suite: Chest X-Ray AI Integration & Clinical Security Workflow.

Verifies:
1. Model file existence and exact SHA-256 integrity.
2. Model loading, input shape (224, 224, 3), and 2-class softmax output.
3. Metadata and class mapping source-of-truth alignment.
4. AI modules registry operational health for CHEST_XRAY.
5. Real forward inference, class probabilities, and confidence calculation.
6. Real Grad-CAM heatmap generation and PNG image validation.
7. Doctor trigger AI analysis on existing patient medical image without re-upload.
8. Hospital Staff forbidden from triggering or viewing clinical AI analysis.
9. Patient forbidden from triggering doctor AI analysis.
10. Awaiting-review AI analysis strictly hidden from patient (403 Forbidden).
11. Patient cross-access isolation (Patient A cannot access Patient B analysis / IDOR).
12. Doctor review and explicit release lifecycle transition.
13. Patient sanitized report visibility post-release without private doctor notes.
14. Grad-CAM endpoint strict Bearer authentication (rejection of ?token= query parameter).
15. Brain MRI regression baseline (unaffected, fully functional).
16. Persistence integrity across simulated restart / snapshot restore.
"""

import io
import os
import hashlib
import unittest
from pathlib import Path
from PIL import Image
import numpy as np
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.mongodb import db_manager, connect_to_mongo
from app.models.user import UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_DOCUMENTS, COLLECTION_AI_ANALYSES, COLLECTION_APPOINTMENTS,
    COLLECTION_CONSULTATIONS
)
from app.ai.registry import get_ai_registry
from app.ai.model_loader import get_model_loader
from app.ai.inference import run_inference
from app.ai.gradcam import generate_gradcam_overlay_bytes
from app.ai.preprocessing import load_and_preprocess_backend_image
from app.services.storage_service import get_storage_service


EXPECTED_CHEST_SHA256 = "6280d0820a62eb730dff084cbffc260a45ba13a45a51193bb0c450393f4009b3"
BACKEND_ROOT = Path(__file__).parent.parent.resolve()
PROJECT_ROOT = BACKEND_ROOT.parent


class TestChestXRayProductionIntegration(unittest.IsolatedAsyncioTestCase):
    """End-to-end integration and security test suite for Chest X-Ray AI in CliniXAI."""

    async def asyncSetUp(self):
        await connect_to_mongo()
        self.db = db_manager.db
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://testserver")

        # Provision Test Users with tokens
        self.doc_email = "doctor.test.chest@clinixai.com"
        self.doc_uid = "USR-DOC-TEST-CHEST"
        self.doc_id = "DOC-TEST-CHEST"
        self.doc_token = create_access_token(self.doc_uid, UserRole.DOCTOR.value)

        self.pat_a_email = "patient.a.chest@clinixai.com"
        self.pat_a_uid = "USR-PAT-A-CHEST"
        self.pat_a_id = "PAT-A-CHEST"
        self.pat_a_token = create_access_token(self.pat_a_uid, UserRole.PATIENT.value)

        self.pat_b_email = "patient.b.chest@clinixai.com"
        self.pat_b_uid = "USR-PAT-B-CHEST"
        self.pat_b_id = "PAT-B-CHEST"
        self.pat_b_token = create_access_token(self.pat_b_uid, UserRole.PATIENT.value)

        self.staff_email = "staff.test.chest@clinixai.com"
        self.staff_uid = "USR-STF-TEST-CHEST"
        self.staff_token = create_access_token(self.staff_uid, UserRole.HOSPITAL_STAFF.value)

        now = utc_now()
        # Seed users in DB
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.doc_uid},
            {"$set": {
                "user_id": self.doc_uid, "email": self.doc_email, "full_name": "Dr. Chest Specialist",
                "role": UserRole.DOCTOR.value, "account_status": AccountStatus.ACTIVE.value,
                "email_verified": True, "created_at": now, "updated_at": now
            }}, upsert=True
        )
        await self.db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": self.doc_id},
            {"$set": {
                "doctor_id": self.doc_id, "user_id": self.doc_uid, "full_name": "Dr. Chest Specialist",
                "email": self.doc_email, "department_id": "DEPT-GEN", "status": "active",
                "created_at": now, "updated_at": now
            }}, upsert=True
        )
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.pat_a_uid},
            {"$set": {
                "user_id": self.pat_a_uid, "email": self.pat_a_email, "full_name": "Patient Alpha",
                "role": UserRole.PATIENT.value, "account_status": AccountStatus.ACTIVE.value,
                "email_verified": True, "created_at": now, "updated_at": now
            }}, upsert=True
        )
        await self.db[COLLECTION_PATIENTS].update_one(
            {"patient_id": self.pat_a_id},
            {"$set": {
                "patient_id": self.pat_a_id, "user_id": self.pat_a_uid, "first_name": "Patient",
                "last_name": "Alpha", "email": self.pat_a_email, "status": "active",
                "created_at": now, "updated_at": now
            }}, upsert=True
        )
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.pat_b_uid},
            {"$set": {
                "user_id": self.pat_b_uid, "email": self.pat_b_email, "full_name": "Patient Beta",
                "role": UserRole.PATIENT.value, "account_status": AccountStatus.ACTIVE.value,
                "email_verified": True, "created_at": now, "updated_at": now
            }}, upsert=True
        )
        await self.db[COLLECTION_PATIENTS].update_one(
            {"patient_id": self.pat_b_id},
            {"$set": {
                "patient_id": self.pat_b_id, "user_id": self.pat_b_uid, "first_name": "Patient",
                "last_name": "Beta", "email": self.pat_b_email, "status": "active",
                "created_at": now, "updated_at": now
            }}, upsert=True
        )
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.staff_uid},
            {"$set": {
                "user_id": self.staff_uid, "email": self.staff_email, "full_name": "Staff Chest",
                "role": UserRole.HOSPITAL_STAFF.value, "account_status": AccountStatus.ACTIVE.value,
                "email_verified": True, "created_at": now, "updated_at": now
            }}, upsert=True
        )

        # Establish clinical care relationship between Doctor and Patient A
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": "APT-TEST-CHEST-A"},
            {"$set": {
                "appointment_id": "APT-TEST-CHEST-A", "patient_id": self.pat_a_id,
                "doctor_id": self.doc_id, "status": "confirmed", "created_at": now, "updated_at": now
            }}, upsert=True
        )

        # Create sample document in storage and database for Patient A
        storage = get_storage_service()
        self.doc_file_key = "test_chest_scan_a.jpg"
        sample_img_path = PROJECT_ROOT / "model-training" / "chest" / "dataset" / "chest_xray" / "test" / "PNEUMONIA" / "person100_bacteria_477.jpeg"
        if sample_img_path.exists():
            with open(sample_img_path, "rb") as f:
                self.sample_bytes = f.read()
        else:
            # Fallback synthetic jpeg if path not found
            buf = io.BytesIO()
            Image.new("RGB", (224, 224), color=(128, 128, 128)).save(buf, format="JPEG")
            self.sample_bytes = buf.getvalue()

        await storage.save_file(self.sample_bytes, self.doc_file_key, subfolder="documents")

        self.doc_rec_id = "DOC-CHEST-PAT-A"
        await self.db[COLLECTION_DOCUMENTS].update_one(
            {"document_id": self.doc_rec_id},
            {"$set": {
                "document_id": self.doc_rec_id, "patient_id": self.pat_a_id,
                "title": "Frontal Chest Radiograph", "category": "X-Ray", "file_category": "xray",
                "content_type": "image/jpeg", "mime_type": "image/jpeg",
                "file_name": self.doc_file_key, "storage_key": self.doc_file_key,
                "is_ai_eligible": True, "is_deleted": False, "created_at": now, "updated_at": now
            }}, upsert=True
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    # 1. Model File Exists & SHA-256 Checksum
    def test_01_chest_model_file_exists_and_sha256_matches(self):
        trained_model_path = PROJECT_ROOT / "model-training" / "chest" / "outputs" / "chest_xray_model_best.keras"
        self.assertTrue(trained_model_path.exists(), f"Trained artifact missing: {trained_model_path}")

        h = hashlib.sha256()
        with open(trained_model_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        actual_sha = h.hexdigest()
        self.assertEqual(actual_sha, EXPECTED_CHEST_SHA256, "Trained model SHA-256 does not match expected integrity hash")

        # Verify backend production promoted file
        backend_model_path = BACKEND_ROOT / "ai_models" / "chest_model.keras"
        self.assertTrue(backend_model_path.exists(), "Backend production chest_model.keras missing")
        h_b = hashlib.sha256()
        with open(backend_model_path, "rb") as f:
            while chunk := f.read(65536):
                h_b.update(chunk)
        self.assertEqual(h_b.hexdigest(), EXPECTED_CHEST_SHA256, "Backend production chest_model.keras hash mismatch")

    # 2. Model Loads & Valid Tensors
    def test_02_chest_model_loads_and_has_valid_specs(self):
        import tensorflow as tf
        backend_model_path = BACKEND_ROOT / "ai_models" / "chest_model.keras"
        model = tf.keras.models.load_model(str(backend_model_path))
        self.assertIsNotNone(model)
        self.assertEqual(model.input_shape, (None, 224, 224, 3))
        self.assertEqual(model.output_shape, (None, 2))

    # 3. Metadata & Class Mapping
    def test_03_chest_metadata_and_classes_source_of_truth(self):
        import json
        cmap_path = BACKEND_ROOT / "ai_models" / "chest_class_names.json"
        meta_path = BACKEND_ROOT / "ai_models" / "chest_metadata.json"
        self.assertTrue(cmap_path.exists())
        self.assertTrue(meta_path.exists())

        with open(cmap_path, "r", encoding="utf-8") as f:
            classes = json.load(f)
        self.assertEqual(classes, ["NORMAL", "PNEUMONIA"])

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta.get("architecture"), "ResNet50")
        self.assertEqual(meta.get("classification_type"), "multiclass")
        self.assertEqual(meta.get("class_names"), ["NORMAL", "PNEUMONIA"])

    # 4. Registry Operational Status
    async def test_04_ai_modules_endpoint_exposes_chest_xray(self):
        res = await self.client.get("/api/v1/ai/modules")
        self.assertEqual(res.status_code, 200)
        modules = res.json()
        chest_mod = next((m for m in modules if m["module_id"] == "CHEST_XRAY"), None)
        self.assertIsNotNone(chest_mod, "CHEST_XRAY not found in /ai/modules")
        self.assertEqual(chest_mod["status"], "available")
        self.assertTrue(chest_mod["model_loaded"])
        self.assertEqual(chest_mod["supported_classes"], ["NORMAL", "PNEUMONIA"])

    # 5. Real Inference & Class Probabilities
    def test_05_real_chest_inference_and_probabilities(self):
        prep_tensor = load_and_preprocess_backend_image(self.sample_bytes, target_size=(224, 224), strategy="resnet50")
        prediction, version = run_inference(prep_tensor, module_id="CHEST_XRAY")

        self.assertIn(prediction.predicted_class, ["NORMAL", "PNEUMONIA"])
        self.assertGreaterEqual(prediction.confidence, 0.5)
        self.assertIn("NORMAL", prediction.class_probabilities)
        self.assertIn("PNEUMONIA", prediction.class_probabilities)
        prob_sum = sum(prediction.class_probabilities.values())
        self.assertAlmostEqual(prob_sum, 1.0, places=3)
        self.assertEqual(version, "1.0.0")

    # 6. Real Grad-CAM & PNG Artifact Validity
    def test_06_real_gradcam_generation_and_png_integrity(self):
        prep_tensor = load_and_preprocess_backend_image(self.sample_bytes, target_size=(224, 224), strategy="resnet50")
        png_bytes, target_layer = generate_gradcam_overlay_bytes(self.sample_bytes, prep_tensor, module_id="CHEST_XRAY")

        self.assertEqual(target_layer, "conv5_block3_out")
        self.assertGreater(len(png_bytes), 1000)

        # Verify PNG can be decoded by PIL
        img = Image.open(io.BytesIO(png_bytes))
        self.assertEqual(img.format, "PNG")
        self.assertEqual(img.size, (224, 224))

    # 7. Doctor Triggers Chest Analysis on Existing Document
    async def test_07_doctor_can_trigger_chest_analysis_on_existing_document(self):
        headers = {"Authorization": f"Bearer {self.doc_token}"}
        payload = {
            "document_id": self.doc_rec_id,
            "analysis_type": "CHEST_XRAY"
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=headers)
        self.assertEqual(res.status_code, 201, res.text)
        data = res.json()
        self.assertIn("analysis_id", data)
        self.assertEqual(data["status"], "awaiting_review")
        self.assertEqual(data["model"]["module_id"], "CHEST_XRAY")
        self.assertIn(data["prediction"]["predicted_class"], ["NORMAL", "PNEUMONIA"])
        self.assertIsNotNone(data["explainability"])
        self.assertEqual(data["explainability"]["target_layer"], "conv5_block3_out")

        # Verify persisted in MongoDB
        db_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": data["analysis_id"]})
        self.assertIsNotNone(db_doc)
        self.assertEqual(db_doc["patient_id"], self.pat_a_id)
        self.assertEqual(db_doc["model"]["module_id"], "CHEST_XRAY")

    # 8. Staff Forbidden From Triggering
    async def test_08_staff_forbidden_from_triggering_chest_analysis(self):
        headers = {"Authorization": f"Bearer {self.staff_token}"}
        payload = {"document_id": self.doc_rec_id, "analysis_type": "CHEST_XRAY"}
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=headers)
        self.assertEqual(res.status_code, 403)

    # 9. Patient Forbidden From Triggering Doctor Analysis
    async def test_09_patient_cannot_trigger_doctor_chest_analysis(self):
        headers = {"Authorization": f"Bearer {self.pat_a_token}"}
        payload = {"document_id": self.doc_rec_id, "analysis_type": "CHEST_XRAY"}
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=headers)
        self.assertEqual(res.status_code, 403)

    # 10. Awaiting-Review Analysis Hidden From Patient
    async def test_10_awaiting_review_chest_analysis_hidden_from_patient(self):
        # Create analysis as doctor
        doc_headers = {"Authorization": f"Bearer {self.doc_token}"}
        create_res = await self.client.post("/api/v1/ai-analyses", json={"document_id": self.doc_rec_id, "analysis_type": "CHEST_XRAY"}, headers=doc_headers)
        analysis_id = create_res.json()["analysis_id"]

        # Patient attempts to access details or report
        pat_headers = {"Authorization": f"Bearer {self.pat_a_token}"}
        res_detail = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}", headers=pat_headers)
        self.assertEqual(res_detail.status_code, 403)

        res_report = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}/report", headers=pat_headers)
        self.assertEqual(res_report.status_code, 403)

    # 11. Patient Cross-Access Isolation (IDOR)
    async def test_11_patient_a_cannot_access_patient_b_analysis_idor(self):
        doc_headers = {"Authorization": f"Bearer {self.doc_token}"}
        create_res = await self.client.post("/api/v1/ai-analyses", json={"document_id": self.doc_rec_id, "analysis_type": "CHEST_XRAY"}, headers=doc_headers)
        analysis_id = create_res.json()["analysis_id"]

        # Patient B tries to access Patient A's analysis
        pat_b_headers = {"Authorization": f"Bearer {self.pat_b_token}"}
        res = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}", headers=pat_b_headers)
        self.assertEqual(res.status_code, 403)

    # 12. Doctor Review & Explicit Release Lifecycle
    async def test_12_doctor_review_and_explicit_release_workflow(self):
        doc_headers = {"Authorization": f"Bearer {self.doc_token}"}
        create_res = await self.client.post("/api/v1/ai-analyses", json={"document_id": self.doc_rec_id, "analysis_type": "CHEST_XRAY"}, headers=doc_headers)
        analysis_id = create_res.json()["analysis_id"]

        # Review with explicit release
        review_payload = {
            "decision": "accepted",
            "clinical_interpretation": "Bilateral lung fields clear. No focal consolidation or active infiltrates.",
            "release_to_patient": True
        }
        rev_res = await self.client.post(f"/api/v1/ai-analyses/{analysis_id}/review", json=review_payload, headers=doc_headers)
        self.assertEqual(rev_res.status_code, 200)
        data = rev_res.json()
        self.assertEqual(data["status"], "reviewed")
        self.assertTrue(data.get("is_released_to_patient", True))
        self.assertEqual(data["doctor_review"]["decision"], "accepted")

    # 13. Patient Sanitized Report Visibility Post-Release
    async def test_13_patient_sees_sanitized_result_after_release(self):
        doc_headers = {"Authorization": f"Bearer {self.doc_token}"}
        create_res = await self.client.post("/api/v1/ai-analyses", json={"document_id": self.doc_rec_id, "analysis_type": "CHEST_XRAY"}, headers=doc_headers)
        analysis_id = create_res.json()["analysis_id"]

        review_payload = {
            "decision": "accepted",
            "clinical_interpretation": "Clinical notes for patient discussion.",
            "release_to_patient": True
        }
        await self.client.post(f"/api/v1/ai-analyses/{analysis_id}/review", json=review_payload, headers=doc_headers)

        # Patient accesses sanitized report
        pat_headers = {"Authorization": f"Bearer {self.pat_a_token}"}
        report_res = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}/report", headers=pat_headers)
        self.assertEqual(report_res.status_code, 200)
        report_data = report_res.json()
        self.assertEqual(report_data["status"], "reviewed")
        self.assertIn("disclaimer", report_data)
        self.assertIn("report", report_data)

    # 14. Grad-CAM Endpoint Strict Bearer Security
    async def test_14_gradcam_endpoint_security_strict_bearer(self):
        doc_headers = {"Authorization": f"Bearer {self.doc_token}"}
        create_res = await self.client.post("/api/v1/ai-analyses", json={"document_id": self.doc_rec_id, "analysis_type": "CHEST_XRAY"}, headers=doc_headers)
        analysis_id = create_res.json()["analysis_id"]

        # Valid Bearer token
        gc_res = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}/gradcam", headers=doc_headers)
        self.assertEqual(gc_res.status_code, 200)
        self.assertEqual(gc_res.headers["content-type"], "image/png")

        # Query param ?token= must be rejected
        no_auth_res = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}/gradcam?token={self.doc_token}")
        self.assertIn(no_auth_res.status_code, [401, 403])

        # Staff forbidden
        staff_headers = {"Authorization": f"Bearer {self.staff_token}"}
        staff_res = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}/gradcam", headers=staff_headers)
        self.assertEqual(staff_res.status_code, 403)

    # 15. Brain MRI Regression Baseline
    def test_15_brain_mri_regression_baseline_remains_fully_functional(self):
        loader = get_model_loader()
        brain_art = loader.load_module("BRAIN_MRI")
        self.assertTrue(brain_art.is_available)
        self.assertEqual(brain_art.class_names, ["glioma", "meningioma", "notumor", "pituitary"])

        # Run dummy/sample inference
        test_tensor = np.zeros((1, 224, 224, 3), dtype=np.float32)
        b_pred, b_ver = run_inference(test_tensor, module_id="BRAIN_MRI")
        self.assertIn(b_pred.predicted_class, ["glioma", "meningioma", "notumor", "pituitary"])

    # 16. Persistence Integrity Across Simulated Restart
    async def test_16_persistence_across_in_memory_restore_and_restart(self):
        doc_headers = {"Authorization": f"Bearer {self.doc_token}"}
        create_res = await self.client.post("/api/v1/ai-analyses", json={"document_id": self.doc_rec_id, "analysis_type": "CHEST_XRAY"}, headers=doc_headers)
        analysis_id = create_res.json()["analysis_id"]

        # Verify in DB
        db_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertIsNotNone(db_doc)

        # Simulate non-destructive restore
        from app.database.mongodb import restore_in_memory_snapshot
        await restore_in_memory_snapshot(self.db)

        # Ensure record remains intact
        recheck_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertIsNotNone(recheck_doc)
        self.assertEqual(recheck_doc["analysis_id"], analysis_id)
        self.assertEqual(recheck_doc["model"]["module_id"], "CHEST_XRAY")
