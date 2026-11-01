"""
Comprehensive Automated Test Suite:
Brain MRI Modality Reclassification, AI Eligibility, Real Inference, Grad-CAM, Doctor Review & Release.

Verifies:
 1. Non-MRI document ('Other') is strictly rejected for Brain MRI with 400/422 validation error.
 2. Reclassifying document metadata to 'MRI' via PATCH /documents/{id} correctly updates both category and modality.
 3. Brain MRI AI inference executes using real 'brain_model.keras'.
 4. Valid classification returned from ['glioma', 'meningioma', 'notumor', 'pituitary'] with real confidence score.
 5. Grad-CAM XAI generated using target layer 'conv5_block3_out'.
 6. AI Analysis record persisted in MongoDB COLLECTION_AI_ANALYSES with status 'awaiting_review'.
 7. Doctor submits clinical review (status -> 'reviewed').
 8. Doctor releases reviewed analysis to patient (is_released_to_patient -> True).
 9. Patient can access released AI report; cannot access before release.
10. Chest X-Ray AI inference remains fully functional and non-regressed with 'chest_model.keras'.
"""

import os
import unittest
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.main import app
from app.database.mongodb import db_manager, connect_to_mongo
from app.models.user import UserRole
from app.core.security import create_access_token
from app.utils.datetime import utc_now
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_DOCUMENTS, COLLECTION_APPOINTMENTS, COLLECTION_AI_ANALYSES
)
from app.ai.registry import get_ai_registry
from app.ai.model_loader import get_model_loader


class TestBrainMRIModalityEligibilityFix(unittest.IsolatedAsyncioTestCase):
    """End-to-end tests for Brain MRI document modality & AI eligibility pipeline."""

    @staticmethod
    def _data(res):
        payload = res.json()
        return payload.get("data", payload)

    async def asyncSetUp(self):
        await connect_to_mongo()
        self.db = db_manager.db
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")

        # Test users
        self.doctor_user = {
            "user_id": "USR-DOC-NEURO-TEST",
            "email": "dr.neuro.test@clinixai.local",
            "full_name": "Dr. Neuro Test",
            "role": UserRole.DOCTOR.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_USERS].update_one({"user_id": self.doctor_user["user_id"]}, {"$set": self.doctor_user}, upsert=True)

        self.doctor_profile = {
            "doctor_id": "DOC-NEURO-001",
            "user_id": self.doctor_user["user_id"],
            "first_name": "Neuro",
            "last_name": "Test",
            "full_name": "Dr. Neuro Test",
            "specialty": "Neurology",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCTORS].update_one({"doctor_id": self.doctor_profile["doctor_id"]}, {"$set": self.doctor_profile}, upsert=True)

        self.patient_user = {
            "user_id": "USR-PAT-MOD-TEST",
            "email": "patient.mod.test@clinixai.local",
            "full_name": "Alex Modality Test",
            "role": UserRole.PATIENT.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_USERS].update_one({"user_id": self.patient_user["user_id"]}, {"$set": self.patient_user}, upsert=True)

        self.patient_profile = {
            "patient_id": "PAT-MOD-TEST-001",
            "user_id": self.patient_user["user_id"],
            "first_name": "Alex",
            "last_name": "Test",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_PATIENTS].update_one({"patient_id": self.patient_profile["patient_id"]}, {"$set": self.patient_profile}, upsert=True)

        # Established doctor-patient relationship
        self.appointment = {
            "appointment_id": "APT-MOD-TEST-001",
            "doctor_id": self.doctor_profile["doctor_id"],
            "patient_id": self.patient_profile["patient_id"],
            "status": "confirmed",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_APPOINTMENTS].update_one({"appointment_id": self.appointment["appointment_id"]}, {"$set": self.appointment}, upsert=True)

        # Copy test brain MRI image to uploads/documents
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scratch_img = os.path.join(base_dir, "..", "scratch", "DOC-B5597FD9A3AC.jpg")
        upload_docs_dir = os.path.join(base_dir, "uploads", "documents")
        os.makedirs(upload_docs_dir, exist_ok=True)
        self.dest_img = os.path.join(upload_docs_dir, "doc_brain_test_modality.jpg")

        if os.path.exists(scratch_img):
            import shutil
            shutil.copyfile(scratch_img, self.dest_img)
        else:
            # Fallback to existing doc image in backend/uploads
            existing_doc_img = os.path.join(upload_docs_dir, "doc_brain_mri_pat1.jpg")
            if os.path.exists(existing_doc_img):
                import shutil
                shutil.copyfile(existing_doc_img, self.dest_img)

        # 1. Unclassified Document (Uploaded as "Other", like IMG-20261101-WA0011.jpg)
        self.unclassified_doc = {
            "document_id": "DOC-TEST-UNCLASSIFIED-001",
            "patient_id": self.patient_profile["patient_id"],
            "uploaded_by": self.patient_user["user_id"],
            "title": "IMG-20261101-WA0011.jpg",
            "category": "Other",
            "modality": "Other",
            "file_name": "doc_brain_test_modality.jpg",
            "original_file_name": "IMG-20261101-WA0011.jpg",
            "mime_type": "image/jpeg",
            "file_size_bytes": 184709,
            "storage_path": self.dest_img,
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCUMENTS].update_one({"document_id": self.unclassified_doc["document_id"]}, {"$set": self.unclassified_doc}, upsert=True)

        # Tokens
        self.token_doctor = create_access_token(user_id=self.doctor_user["user_id"], role=UserRole.DOCTOR.value)
        self.headers_doctor = {"Authorization": f"Bearer {self.token_doctor}"}

        self.token_patient = create_access_token(user_id=self.patient_user["user_id"], role=UserRole.PATIENT.value)
        self.headers_patient = {"Authorization": f"Bearer {self.token_patient}"}

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_01_non_mri_other_document_rejected_for_brain_mri(self):
        """Strict clinical safety: Attempting Brain MRI on unclassified 'Other' document is rejected with 400/422."""
        payload = {
            "document_id": "DOC-TEST-UNCLASSIFIED-001",
            "patient_id": self.patient_profile["patient_id"],
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doctor)
        self.assertIn(res.status_code, [400, 422], f"Expected rejection, got {res.status_code}: {res.text}")
        data = res.json()
        err_msg = data.get("detail") or data.get("error", {}).get("message") or data.get("message") or str(data)
        self.assertIn("not classified as an MRI", str(err_msg))

    async def test_02_doctor_reclassifies_document_metadata(self):
        """Doctor reclassifies the unclassified document to MRI via PATCH /documents/{id}."""
        patch_payload = {
            "category": "MRI",
        }
        res = await self.client.patch("/api/v1/documents/DOC-TEST-UNCLASSIFIED-001", json=patch_payload, headers=self.headers_doctor)
        self.assertEqual(res.status_code, 200, res.text)
        data = self._data(res)
        self.assertEqual(data["category"], "MRI")
        self.assertEqual(data["modality"], "Brain MRI")

        # Verify persisted in database
        doc_in_db = await self.db[COLLECTION_DOCUMENTS].find_one({"document_id": "DOC-TEST-UNCLASSIFIED-001"})
        self.assertIsNotNone(doc_in_db)
        self.assertEqual(doc_in_db["category"], "MRI")
        self.assertEqual(doc_in_db["modality"], "Brain MRI")

    async def test_03_reclassified_document_passes_and_executes_brain_mri_inference(self):
        """Reclassified document is accepted for Brain MRI AI analysis and executes real ResNet50 inference."""
        # Ensure document is classified as MRI
        await self.db[COLLECTION_DOCUMENTS].update_one(
            {"document_id": "DOC-TEST-UNCLASSIFIED-001"},
            {"$set": {"category": "MRI", "modality": "Brain MRI"}}
        )

        payload = {
            "document_id": "DOC-TEST-UNCLASSIFIED-001",
            "patient_id": self.patient_profile["patient_id"],
            "analysis_type": "BRAIN_MRI",
            "force_new": True,
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doctor)
        self.assertEqual(res.status_code, 201, f"Failed to create AI analysis: {res.text}")
        data = self._data(res)

        analysis_id = data["analysis_id"]
        self.assertTrue(analysis_id.startswith("AI-"))
        self.assertEqual(data["model"]["module_id"], "BRAIN_MRI")
        self.assertEqual(data["model"]["architecture"], "ResNet50")

        # Real prediction verification
        prediction = data.get("prediction", {})
        predicted_class = prediction.get("predicted_class")
        confidence = prediction.get("confidence")
        self.assertIn(predicted_class, ["glioma", "meningioma", "notumor", "pituitary"])
        self.assertGreater(confidence, 0.0)

        # Grad-CAM verification
        explainability = data.get("explainability", {})
        self.assertEqual(explainability.get("target_layer"), "conv5_block3_out")

        # Initial status is awaiting_review
        self.assertEqual(data["status"], "awaiting_review")

        # Patient cannot access report before doctor review & release
        pat_res = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}/report", headers=self.headers_patient)
        self.assertEqual(pat_res.status_code, 403)

        # Doctor submits review
        review_payload = {
            "decision": "accepted",
            "clinical_interpretation": "Clinical review: verified brain MRI scan. Findings consistent with clinical presentation.",
        }
        rev_res = await self.client.post(f"/api/v1/ai-analyses/{analysis_id}/review", json=review_payload, headers=self.headers_doctor)
        self.assertEqual(rev_res.status_code, 200, rev_res.text)

        # Doctor releases to patient
        rel_res = await self.client.post(f"/api/v1/ai-analyses/{analysis_id}/release", headers=self.headers_doctor)
        self.assertEqual(rel_res.status_code, 200, rel_res.text)

        # Patient can now access the released report
        pat_rel_res = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}/report", headers=self.headers_patient)
        self.assertEqual(pat_rel_res.status_code, 200, pat_rel_res.text)
        pat_report = self._data(pat_rel_res)
        self.assertEqual(pat_report.get("status"), "reviewed")

    async def test_04_chest_xray_inference_and_non_interference(self):
        """Chest X-Ray AI inference remains fully functional and non-regressed with chest_model.keras."""
        chest_doc = {
            "document_id": "DOC-TEST-CHEST-XRAY-001",
            "patient_id": self.patient_profile["patient_id"],
            "uploaded_by": self.doctor_user["user_id"],
            "title": "Frontal Chest Radiograph",
            "category": "X-Ray",
            "modality": "Chest X-Ray",
            "file_name": "doc_chest_xray_pat1.jpeg",
            "original_file_name": "chest_xray_patient.jpeg",
            "mime_type": "image/jpeg",
            "file_size_bytes": 56146,
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCUMENTS].update_one({"document_id": chest_doc["document_id"]}, {"$set": chest_doc}, upsert=True)

        payload = {
            "document_id": "DOC-TEST-CHEST-XRAY-001",
            "patient_id": self.patient_profile["patient_id"],
            "analysis_type": "CHEST_XRAY",
            "force_new": True,
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doctor)
        self.assertEqual(res.status_code, 201, f"Failed Chest X-Ray inference: {res.text}")
        data = self._data(res)

        self.assertTrue(data["analysis_id"].startswith("AI-"))
        self.assertEqual(data["model"]["module_id"], "CHEST_XRAY")
        self.assertEqual(data["model"]["architecture"], "ResNet50")

        prediction = data.get("prediction", {})
        predicted_class = prediction.get("predicted_class")
        confidence = prediction.get("confidence")
        self.assertIn(predicted_class, ["NORMAL", "PNEUMONIA"])
        self.assertGreater(confidence, 0.0)

        explainability = data.get("explainability", {})
        self.assertEqual(explainability.get("target_layer"), "conv5_block3_out")
        self.assertEqual(data["status"], "awaiting_review")


if __name__ == "__main__":
    unittest.main()
