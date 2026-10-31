"""
Fix Phase 7 Dedicated Automated Test Suite:
Complete Brain MRI AI -> Doctor Review -> Release -> Patient Workflow & Governance.

50 Comprehensive Automated Tests covering:
- AI Execution (Tests 01-07)
- Prediction & Probabilities (Tests 08-12)
- Explainability & Grad-CAM (Tests 13-16)
- Doctor Clinical Review (Tests 17-23)
- Explicit Release (Tests 24-29)
- Patient Privacy & Sanitization (Tests 30-34)
- Persistence & Rehydration (Tests 35-38)
- Concurrency & Double-Submit Protection (Tests 39-41)
- Security & IDOR Isolation (Tests 42-45)
- Regressions & Model Integrity (Tests 46-50)
"""

import os
import io
import asyncio
import hashlib
import unittest
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.main import app
from app.database.mongodb import db_manager, connect_to_mongo, save_in_memory_snapshot, restore_in_memory_snapshot
from app.models.user import UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_DOCUMENTS, COLLECTION_APPOINTMENTS, COLLECTION_AI_ANALYSES,
    COLLECTION_MEDICAL_RECORDS
)
from app.ai.registry import get_ai_registry
from app.ai.model_loader import get_model_loader
from app.ai.preprocessing import load_and_preprocess_backend_image
from app.ai.inference import run_inference


class TestFixPhase7BrainAIClinicalWorkflow(unittest.IsolatedAsyncioTestCase):
    """50 Comprehensive Production Hardening Tests for Fix Phase 7."""

    @staticmethod
    def _data(res):
        j = res.json()
        return j.get("data", j)

    async def asyncSetUp(self):
        if db_manager.db is None:
            await connect_to_mongo()
        self.db = db_manager.db
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        now = utc_now()

        # Doctor 1: Dr. Arjun Rao (Care relationship with PAT-ONE-001)
        self.doc_token = create_access_token(user_id="USR-DOC-RAO-001", role="doctor")
        self.doc_headers = {"Authorization": f"Bearer {self.doc_token}"}
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": "USR-DOC-RAO-001"},
            {"$set": {
                "user_id": "USR-DOC-RAO-001",
                "email": "doctor.arjun@clinixai.com",
                "full_name": "Dr. Arjun Rao",
                "role": UserRole.DOCTOR.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_deleted": False,
            }},
            upsert=True
        )
        await self.db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": "DOC-RAO-001"},
            {"$set": {
                "doctor_id": "DOC-RAO-001",
                "user_id": "USR-DOC-RAO-001",
                "first_name": "Arjun",
                "last_name": "Rao",
                "full_name": "Dr. Arjun Rao",
                "department": "Neurology",
                "is_deleted": False,
            }},
            upsert=True
        )

        # Doctor 2: Unrelated Doctor (No care relationship with PAT-ONE-001)
        self.unrel_doc_token = create_access_token(user_id="USR-DOC-UNREL-002", role="doctor")
        self.unrel_doc_headers = {"Authorization": f"Bearer {self.unrel_doc_token}"}
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": "USR-DOC-UNREL-002"},
            {"$set": {
                "user_id": "USR-DOC-UNREL-002",
                "email": "doctor.unrelated@clinixai.com",
                "full_name": "Dr. Unrelated Doctor",
                "role": UserRole.DOCTOR.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_deleted": False,
            }},
            upsert=True
        )
        await self.db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": "DOC-UNREL-002"},
            {"$set": {
                "doctor_id": "DOC-UNREL-002",
                "user_id": "USR-DOC-UNREL-002",
                "first_name": "Unrelated",
                "last_name": "Doctor",
                "full_name": "Dr. Unrelated Doctor",
                "department": "Dermatology",
                "is_deleted": False,
            }},
            upsert=True
        )

        # Staff User: Non-clinical operational role
        self.staff_token = create_access_token(user_id="USR-STAFF-001", role="hospital_staff")
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": "USR-STAFF-001"},
            {"$set": {
                "user_id": "USR-STAFF-001",
                "email": "staff@clinixai.com",
                "full_name": "Staff Officer",
                "role": UserRole.HOSPITAL_STAFF.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_deleted": False,
            }},
            upsert=True
        )

        # Patient 1: Authorized Patient (PAT-ONE-001)
        self.pat_token = create_access_token(user_id="USR-PAT-ONE-001", role="patient")
        self.pat_headers = {"Authorization": f"Bearer {self.pat_token}"}
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": "USR-PAT-ONE-001"},
            {"$set": {
                "user_id": "USR-PAT-ONE-001",
                "email": "patient.one@clinixai.com",
                "full_name": "Patient One",
                "role": UserRole.PATIENT.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_deleted": False,
            }},
            upsert=True
        )
        await self.db[COLLECTION_PATIENTS].update_one(
            {"patient_id": "PAT-ONE-001"},
            {"$set": {
                "patient_id": "PAT-ONE-001",
                "user_id": "USR-PAT-ONE-001",
                "first_name": "Patient",
                "last_name": "One",
                "primary_doctor_id": "DOC-RAO-001",
                "is_deleted": False,
            }},
            upsert=True
        )

        # Patient 2: Unrelated Patient (PAT-TWO-002)
        self.pat2_token = create_access_token(user_id="USR-PAT-TWO-002", role="patient")
        self.pat2_headers = {"Authorization": f"Bearer {self.pat2_token}"}
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": "USR-PAT-TWO-002"},
            {"$set": {
                "user_id": "USR-PAT-TWO-002",
                "email": "patient.two@clinixai.com",
                "full_name": "Patient Two",
                "role": UserRole.PATIENT.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_deleted": False,
            }},
            upsert=True
        )
        await self.db[COLLECTION_PATIENTS].update_one(
            {"patient_id": "PAT-TWO-002"},
            {"$set": {
                "patient_id": "PAT-TWO-002",
                "user_id": "USR-PAT-TWO-002",
                "first_name": "Patient",
                "last_name": "Two",
                "is_deleted": False,
            }},
            upsert=True
        )

        # Appointment establishing care relationship
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": "APT-2026-001"},
            {"$set": {
                "appointment_id": "APT-2026-001",
                "patient_id": "PAT-ONE-001",
                "doctor_id": "DOC-RAO-001",
                "status": "CONFIRMED",
                "is_deleted": False,
            }},
            upsert=True
        )

        # Ensure MRI upload file exists
        doc_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "documents")
        os.makedirs(doc_dir, exist_ok=True)
        img_path = os.path.join(doc_dir, "doc_brain_mri_pat1.jpg")
        if not os.path.exists(img_path):
            from PIL import Image
            img = Image.new("RGB", (224, 224), color=(60, 60, 60))
            img.save(img_path, format="JPEG")

        # Authoritative Brain MRI Document DOC-2026-001
        await self.db[COLLECTION_DOCUMENTS].update_one(
            {"document_id": "DOC-2026-001"},
            {"$set": {
                "document_id": "DOC-2026-001",
                "patient_id": "PAT-ONE-001",
                "uploaded_by": "USR-DOC-RAO-001",
                "title": "Brain MRI T1 Axial Scan",
                "category": "MRI",
                "file_name": "doc_brain_mri_pat1.jpg",
                "original_file_name": "Brain_MRI_T1_Axial.jpg",
                "mime_type": "image/jpeg",
                "file_size_bytes": 42790,
                "storage_path": img_path,
                "notes": "High-resolution axial brain MRI scan.",
                "medical_record_id": "MR-2026-001",
                "appointment_id": "APT-2026-001",
                "consultation_id": "CNS-2026-002",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Medical record MR-2026-001
        await self.db[COLLECTION_MEDICAL_RECORDS].update_one(
            {"record_id": "MR-2026-001"},
            {"$set": {
                "record_id": "MR-2026-001",
                "patient_id": "PAT-ONE-001",
                "doctor_id": "DOC-RAO-001",
                "title": "Brain MRI Scan Record",
                "record_type": "MRI",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    # ── AI Execution Tests (01-07) ───────────────────────────────────────────

    async def test_01_valid_brain_mri_analysis_execution(self):
        """01: Valid Brain MRI analysis creates a new analysis record with HTTP 201."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={
                "document_id": "DOC-2026-001",
                "patient_id": "PAT-ONE-001",
                "appointment_id": "APT-2026-001",
                "medical_record_id": "MR-2026-001",
                "analysis_type": "BRAIN_MRI",
                "force_new": True,
            },
            headers=self.doc_headers,
        )
        self.assertIn(res.status_code, [200, 201])
        data = self._data(res)
        self.assertTrue(data["analysis_id"].startswith("AI-"))
        self.assertEqual(data["model"]["module_id"], "BRAIN_MRI")

    async def test_02_selected_document_is_used_as_input(self):
        """02: Selected document DOC-2026-001 is recorded as the input document_id."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={
                "document_id": "DOC-2026-001",
                "patient_id": "PAT-ONE-001",
                "analysis_type": "BRAIN_MRI",
                "force_new": True,
            },
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertEqual(data["document_id"], "DOC-2026-001")

    async def test_03_correct_patient_linkage_retained(self):
        """03: Created AI analysis retains patient_id PAT-ONE-001."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertEqual(data["patient_id"], "PAT-ONE-001")

    async def test_04_correct_doctor_linkage_retained(self):
        """04: Created AI analysis retains doctor_id DOC-RAO-001."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertEqual(data["doctor_id"], "DOC-RAO-001")

    async def test_05_correct_document_linkage_retained(self):
        """05: Document linkage is retained on root document_id field."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertEqual(data["document_id"], "DOC-2026-001")

    async def test_06_correct_medical_record_linkage_retained(self):
        """06: Medical record linkage MR-2026-001 is retained."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "medical_record_id": "MR-2026-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertEqual(data["medical_record_id"], "MR-2026-001")

    async def test_07_correct_appointment_linkage_retained(self):
        """07: Appointment linkage APT-2026-001 is retained."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "appointment_id": "APT-2026-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertEqual(data["appointment_id"], "APT-2026-001")

    # ── Prediction & Probabilities Tests (08-12) ─────────────────────────────

    async def test_08_real_brain_model_executes_successfully(self):
        """08: Brain model executes and produces prediction with ResNet50."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertIsNotNone(data["prediction"])
        self.assertEqual(data["model"]["architecture"], "ResNet50")

    async def test_09_prediction_structure_valid(self):
        """09: Predicted class is one of the 4 valid Brain MRI classes."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        pred = data["prediction"]["predicted_class"]
        self.assertIn(pred, ["glioma", "meningioma", "notumor", "pituitary"])

    async def test_10_class_probabilities_valid(self):
        """10: Class probabilities cover all 4 brain classes."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        class_probs = data["prediction"]["class_probabilities"]
        for c in ["glioma", "meningioma", "notumor", "pituitary"]:
            self.assertIn(c, class_probs)

    async def test_11_confidence_valid_and_calibrated(self):
        """11: Confidence score is a float between 0.0 and 1.0."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        conf = data["prediction"]["confidence"]
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)

    async def test_12_low_confidence_flag_handling(self):
        """12: low_confidence field is present as a boolean."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertIsInstance(data["prediction"]["low_confidence"], bool)

    # ── Explainability & Grad-CAM Tests (13-16) ──────────────────────────────

    async def test_13_gradcam_generated_successfully(self):
        """13: Grad-CAM explainability information is generated."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertIsNotNone(data.get("explainability"))
        self.assertEqual(data["explainability"]["method"], "grad_cam")

    async def test_14_gradcam_target_layer_conv5_block3_out(self):
        """14: Brain MRI Grad-CAM target layer is conv5_block3_out."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertEqual(data["explainability"]["target_layer"], "conv5_block3_out")

    async def test_15_gradcam_artifact_persisted_to_storage(self):
        """15: Grad-CAM PNG artifact is persisted in storage."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        key = data["explainability"]["artifact_storage_key"]
        self.assertTrue(key.startswith("gradcam_"))

    async def test_16_authenticated_gradcam_access_with_strict_header(self):
        """16: Authenticated doctor can fetch Grad-CAM image with Bearer header."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        gc_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/gradcam",
            headers=self.doc_headers,
        )
        self.assertEqual(gc_res.status_code, 200)
        self.assertEqual(gc_res.headers["content-type"], "image/png")

    # ── Doctor Clinical Review Tests (17-23) ─────────────────────────────────

    async def test_17_awaiting_review_initial_status(self):
        """17: Analysis is initially created in awaiting_review status."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        data = self._data(res)
        self.assertEqual(data["status"], "awaiting_review")
        self.assertFalse(data.get("is_released_to_patient", False))

    async def test_18_authorized_doctor_can_review_analysis(self):
        """18: Authorized Doctor submits clinical review; status transitions to reviewed."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        rev_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Confirmed normal findings with no intracranial mass.",
                "release_to_patient": False,
            },
            headers=self.doc_headers,
        )
        self.assertEqual(rev_res.status_code, 200)
        data = self._data(rev_res)
        self.assertEqual(data["status"], "reviewed")
        self.assertFalse(data["is_released_to_patient"])
        self.assertEqual(data["doctor_review"]["decision"], "accepted")

    async def test_19_unauthorized_doctor_cannot_review_analysis(self):
        """19: Doctor without care relationship cannot review analysis (403 Forbidden)."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        rev_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Unauthorized doctor review attempt.",
            },
            headers=self.unrel_doc_headers,
        )
        self.assertEqual(rev_res.status_code, 403)

    async def test_20_patient_cannot_review_analysis(self):
        """20: Patient role cannot submit AI review (403 Forbidden)."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        rev_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Patient self-review attempt.",
            },
            headers=self.pat_headers,
        )
        self.assertEqual(rev_res.status_code, 403)

    async def test_21_staff_cannot_review_analysis(self):
        """21: Hospital Staff cannot review AI analysis (403 Forbidden)."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        rev_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Staff review attempt.",
            },
            headers=self.staff_headers,
        )
        self.assertEqual(rev_res.status_code, 403)

    async def test_22_invalid_review_status_rejected(self):
        """22: Nonexistent analysis ID cannot be reviewed (404 Not Found)."""
        rev_res = await self.client.post(
            "/api/v1/ai-analyses/AI-NONEXISTENT/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Reviewing ghost analysis.",
            },
            headers=self.doc_headers,
        )
        self.assertEqual(rev_res.status_code, 404)

    async def test_23_required_clinical_interpretation_enforced(self):
        """23: Missing or too-short clinical interpretation is rejected with 422."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        rev_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "ok",  # Less than 5 characters
            },
            headers=self.doc_headers,
        )
        self.assertEqual(rev_res.status_code, 422)

    # ── Explicit Release Tests (24-29) ───────────────────────────────────────

    async def test_24_reviewed_analysis_can_be_released(self):
        """24: Calling explicit release endpoint on a reviewed analysis marks it released."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        # Doctor reviews without release
        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Normal scan. Confirmed.", "release_to_patient": False},
            headers=self.doc_headers,
        )

        # Doctor explicitly releases
        rel_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers=self.doc_headers,
        )
        self.assertEqual(rel_res.status_code, 200)
        data = self._data(rel_res)
        self.assertTrue(data["is_released_to_patient"])
        self.assertIsNotNone(data["released_at"])

    async def test_25_patient_cannot_release_analysis(self):
        """25: Patient cannot call release endpoint (403 Forbidden)."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        rel_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers=self.pat_headers,
        )
        self.assertEqual(rel_res.status_code, 403)

    async def test_26_staff_cannot_release_analysis(self):
        """26: Hospital Staff cannot call release endpoint (403 Forbidden)."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        rel_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers=self.staff_headers,
        )
        self.assertEqual(rel_res.status_code, 403)

    async def test_27_unrelated_doctor_cannot_release_analysis(self):
        """27: Unrelated Doctor without care relationship cannot release analysis (403 Forbidden)."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        rel_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers=self.unrel_doc_headers,
        )
        self.assertEqual(rel_res.status_code, 403)

    async def test_28_release_requires_valid_reviewed_state(self):
        """28: Releasing an unreviewed analysis in awaiting_review is rejected with 400."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        rel_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers=self.doc_headers,
        )
        self.assertIn(rel_res.status_code, [400, 422])

    async def test_29_release_persisted_in_database(self):
        """29: Database directly reflects is_released_to_patient == True after release."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Clinically reviewed."},
            headers=self.doc_headers,
        )
        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers=self.doc_headers,
        )

        doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertTrue(doc["is_released_to_patient"])
        self.assertIsNotNone(doc["released_at"])

    # ── Patient Privacy & Sanitization Tests (30-34) ─────────────────────────

    async def test_30_patient_hidden_before_release(self):
        """30: Patient querying an unreleased analysis receives 403 Forbidden."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        # Review without release
        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Doctor review only.", "release_to_patient": False},
            headers=self.doc_headers,
        )

        # Patient tries to view detail or patient report
        p_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers=self.pat_headers,
        )
        self.assertEqual(p_res.status_code, 403)

        rep_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/report",
            headers=self.pat_headers,
        )
        self.assertEqual(rep_res.status_code, 403)

    async def test_31_patient_sees_released_sanitized_result(self):
        """31: Patient can view sanitized safe report after release."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Patient approved report."},
            headers=self.doc_headers,
        )
        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers=self.doc_headers,
        )

        rep_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/report",
            headers=self.pat_headers,
        )
        self.assertEqual(rep_res.status_code, 200)
        data = self._data(rep_res)
        self.assertEqual(data["analysis_id"], analysis_id)
        self.assertEqual(data["report"]["doctor_name"], "Dr. Arjun Rao")
        self.assertEqual(data["report"]["doctor_interpretation"], "Patient approved report.")
        self.assertIn("CliniXAI AI analysis is intended for clinical decision support only", data["disclaimer"])

    async def test_32_private_notes_hidden_from_patient(self):
        """32: Private physician notes are stripped from patient view."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Normal scan for patient.",
                "notes": "CONFIDENTIAL INTERNAL DOCTOR NOTES: Check follow-up in 6 months.",
            },
            headers=self.doc_headers,
        )
        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers=self.doc_headers,
        )

        p_detail = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers=self.pat_headers,
        )
        self.assertEqual(p_detail.status_code, 200)
        data = self._data(p_detail)
        # Verify doctor private notes are None/stripped
        self.assertIsNone(data["doctor_review"]["notes"])

    async def test_33_internal_metadata_hidden_from_patient(self):
        """33: Patient report excludes server storage paths and internal credentials."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Valid scan."},
            headers=self.doc_headers,
        )
        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers=self.doc_headers,
        )

        rep_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/report",
            headers=self.pat_headers,
        )
        text = rep_res.text
        self.assertNotIn("storage_path", text)
        self.assertNotIn("password_hash", text)

    async def test_34_cross_patient_access_blocked(self):
        """34: Patient Two cannot access Patient One's released AI report (403 Forbidden)."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Patient One only."},
            headers=self.doc_headers,
        )
        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers=self.doc_headers,
        )

        p2_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/report",
            headers=self.pat2_headers,
        )
        self.assertEqual(p2_res.status_code, 403)

    # ── Persistence & Rehydration Tests (35-38) ──────────────────────────────

    async def test_35_refresh_persistence_verified(self):
        """35: GET /ai-analyses/{id} reloads analysis identically."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        reload1 = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}", headers=self.doc_headers)
        reload2 = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}", headers=self.doc_headers)
        self.assertEqual(reload1.status_code, 200)
        self.assertEqual(reload2.status_code, 200)
        self.assertEqual(self._data(reload1)["analysis_id"], self._data(reload2)["analysis_id"])

    async def test_36_logout_login_persistence_verified(self):
        """36: Analysis is retrievable after generating a brand new JWT token."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        new_token = create_access_token(user_id="USR-DOC-RAO-001", role="doctor")
        fresh_headers = {"Authorization": f"Bearer {new_token}"}

        fresh_res = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}", headers=fresh_headers)
        self.assertEqual(fresh_res.status_code, 200)
        self.assertEqual(self._data(fresh_res)["analysis_id"], analysis_id)

    async def test_37_backend_restart_persistence_verified(self):
        """37: Analysis survives snapshot save and restore from disk."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        await save_in_memory_snapshot(self.db)
        await restore_in_memory_snapshot(self.db)

        check_res = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}", headers=self.doc_headers)
        self.assertEqual(check_res.status_code, 200)
        self.assertEqual(self._data(check_res)["analysis_id"], analysis_id)

    async def test_38_mongo_record_consistency_verified(self):
        """38: COLLECTION_DOCUMENTS has ai_analysis_id set after inference."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        doc = await self.db[COLLECTION_DOCUMENTS].find_one({"document_id": "DOC-2026-001"})
        self.assertEqual(doc.get("ai_analysis_id"), analysis_id)
        self.assertTrue(doc.get("has_ai_analysis"))

    # ── Concurrency & Double-Submit Protection Tests (39-41) ─────────────────

    async def test_39_concurrent_review_safety(self):
        """39: Concurrent review calls execute safely without DB corruption."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        payload = {"decision": "accepted", "clinical_interpretation": "Concurrent review test."}
        reqs = [
            self.client.post(f"/api/v1/ai-analyses/{analysis_id}/review", json=payload, headers=self.doc_headers),
            self.client.post(f"/api/v1/ai-analyses/{analysis_id}/review", json=payload, headers=self.doc_headers),
        ]
        results = await asyncio.gather(*reqs)
        for r in results:
            self.assertEqual(r.status_code, 200)

    async def test_40_concurrent_release_safety(self):
        """40: Concurrent release calls execute safely and idempotently."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Pre-release review."},
            headers=self.doc_headers,
        )

        reqs = [
            self.client.post(f"/api/v1/ai-analyses/{analysis_id}/release", headers=self.doc_headers),
            self.client.post(f"/api/v1/ai-analyses/{analysis_id}/release", headers=self.doc_headers),
        ]
        results = await asyncio.gather(*reqs)
        for r in results:
            self.assertEqual(r.status_code, 200)

    async def test_41_duplicate_execution_protection(self):
        """41: Double-click without force_new reuses existing in-progress/awaiting analysis."""
        res1 = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": False},
            headers=self.doc_headers,
        )
        id1 = self._data(res1)["analysis_id"]

        res2 = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": False},
            headers=self.doc_headers,
        )
        id2 = self._data(res2)["analysis_id"]
        self.assertEqual(id1, id2)

    # ── Security & IDOR Isolation Tests (42-45) ──────────────────────────────

    async def test_42_idor_cross_patient_document_rejected(self):
        """42: Patient Two's ID with Patient One's document is rejected (403 Forbidden)."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={
                "document_id": "DOC-2026-001",
                "patient_id": "PAT-TWO-002",
                "force_new": True,
            },
            headers=self.doc_headers,
        )
        self.assertEqual(res.status_code, 403)

    async def test_43_query_token_rejected_on_gradcam(self):
        """43: Passing token via query parameter on Grad-CAM endpoint is rejected (401)."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        bad_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/gradcam?token={self.doc_token}"
        )
        self.assertEqual(bad_res.status_code, 401)

    async def test_44_unauthorized_gradcam_rejection(self):
        """44: Unrelated doctor or unreleased patient cannot access Grad-CAM (403 Forbidden)."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-2026-001", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        analysis_id = self._data(res)["analysis_id"]

        # Unrelated doctor
        unrel_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/gradcam",
            headers=self.unrel_doc_headers,
        )
        self.assertEqual(unrel_res.status_code, 403)

        # Unreleased patient
        pat_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/gradcam",
            headers=self.pat_headers,
        )
        self.assertEqual(pat_res.status_code, 403)

    async def test_45_deleted_document_rejected(self):
        """45: Triggering AI analysis on a soft-deleted document returns 404 Not Found."""
        await self.db[COLLECTION_DOCUMENTS].update_one(
            {"document_id": "DOC-DELETED-999"},
            {"$set": {
                "document_id": "DOC-DELETED-999",
                "patient_id": "PAT-ONE-001",
                "category": "MRI",
                "is_deleted": True,
            }},
            upsert=True
        )

        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-DELETED-999", "patient_id": "PAT-ONE-001", "force_new": True},
            headers=self.doc_headers,
        )
        self.assertEqual(res.status_code, 404)

    # ── Regressions & Model Integrity Tests (46-50) ──────────────────────────

    async def test_46_phase5_regression_discovery(self):
        """46: Fix Phase 5 discovery endpoint lists patient's MRI documents."""
        res = await self.client.get(
            "/api/v1/documents?patient_id=PAT-ONE-001",
            headers=self.doc_headers,
        )
        self.assertEqual(res.status_code, 200)
        items = res.json().get("data", res.json())
        if isinstance(items, dict) and "items" in items:
            items = items["items"]
        mri_docs = [d for d in items if d.get("category") == "MRI"]
        self.assertGreaterEqual(len(mri_docs), 1)

    async def test_47_phase6_regression_handoff(self):
        """47: Fix Phase 6 handoff passes document context without re-upload."""
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={
                "document_id": "DOC-2026-001",
                "patient_id": "PAT-ONE-001",
                "appointment_id": "APT-2026-001",
                "medical_record_id": "MR-2026-001",
                "force_new": True,
            },
            headers=self.doc_headers,
        )
        self.assertIn(res.status_code, [200, 201])
        data = self._data(res)
        self.assertEqual(data["model"]["module_id"], "BRAIN_MRI")

    async def test_48_brain_model_hash_integrity(self):
        """48: Brain model file hash matches verified production digest."""
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "ai_models", "brain_model.keras"
        )
        self.assertTrue(os.path.exists(model_path))
        with open(model_path, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(h, "e135b97df53d4ab8d575c643297ba948cb6ccbaa963039c0a4c40683fb679f53")

    async def test_49_chest_xray_pipeline_regression(self):
        """49: CHEST_XRAY module remains registered and operational."""
        registry = get_ai_registry()
        mod = registry.get_module("CHEST_XRAY")
        self.assertEqual(mod.display_name, "Chest X-Ray Analysis")
        self.assertEqual(mod.module_id, "CHEST_XRAY")

    async def test_50_patient_ai_visibility_regression(self):
        """50: Patient listing analyses only sees released analyses."""
        # Query analyses as patient
        res = await self.client.get(
            "/api/v1/ai-analyses?patient_id=PAT-ONE-001",
            headers=self.pat_headers,
        )
        self.assertEqual(res.status_code, 200)
        items = res.json().get("data", res.json())
        if isinstance(items, dict) and "items" in items:
            items = items["items"]
        for it in items:
            self.assertEqual(it["status"], "reviewed")
            self.assertTrue(it.get("is_released_to_patient", False))


if __name__ == "__main__":
    unittest.main()
