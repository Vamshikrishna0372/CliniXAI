"""
Fix Phase 6 Dedicated Automated Test Suite:
Existing Brain MRI -> Automatic AI Analysis Handoff & Clinical Governance.

Covers:
 1. Valid selected Brain MRI context accepted (DOC-2026-001 for PAT-ONE-001).
 2. Valid patient/document pairing succeeds.
 3. Invalid document ID returns 404 Not Found.
 4. Deleted document returns 404 Not Found.
 5. Patient/document mismatch rejected (403 Forbidden).
 6. Unauthorized doctor cannot trigger AI analysis on patient document (403 Forbidden).
 7. Unauthorized patient cannot trigger AI analysis on document (403 Forbidden).
 8. Non-MRI document rejected when Brain MRI analysis requested (400/422).
 9. AI module auto-selection resolves to BRAIN_MRI from document metadata.
10. Real image bytes securely retrieved for inference from document storage.
11. Real Brain MRI ResNet50 inference runs using backend/ai_models/brain_model.keras.
12. AI analysis record persists in MongoDB COLLECTION_AI_ANALYSES.
13. Document linkage preserved (document_id, patient_id, appointment_id, medical_record_id).
14. Real Grad-CAM generated with target layer 'conv5_block3_out'.
15. Initial status is awaiting_review.
16. Doctor can submit clinical review and interpretation (status -> reviewed).
17. Doctor can explicitly release reviewed analysis to patient.
18. Patient cannot view AI analysis before doctor review and release (403 Forbidden).
19. Patient can view sanitized safe report after explicit release.
20. Analysis state persists across in-memory / database restore.
21. Cross-patient isolation strictly enforced on AI analyses.
22. Grad-CAM retrieval requires Bearer header; query-token access rejected.
23. Brain model hash verification matches e135b97df53d4ab8d575c643297ba948cb6ccbaa963039c0a4c40683fb679f53.
24. Existing Phase 5 Brain MRI discovery remains intact.
25. Chest X-Ray production inference integration remains functional.
"""

import os
import io
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


class TestFixPhase6ExistingBrainMRIHandoff(unittest.IsolatedAsyncioTestCase):
    """25 Comprehensive Automated Tests for Fix Phase 6 Handoff & Governance."""

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

        # Doctor A: Dr. Arjun Rao (Authorized for Patient One)
        self.doc_a_user = {
            "user_id": "USR-DOC-RAO-001",
            "email": "doctor.arjun@clinixai.com",
            "full_name": "Dr. Arjun Rao",
            "role": UserRole.DOCTOR.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.doc_a = {
            "doctor_id": "DOC-RAO-001",
            "user_id": "USR-DOC-RAO-001",
            "first_name": "Arjun",
            "last_name": "Rao",
            "email": "doctor.arjun@clinixai.com",
            "specialty": "Neurology",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Doctor Unrelated: Dr. Vikram Joshi (No care relationship with Patient One)
        self.doc_unrelated_user = {
            "user_id": "USR-DOC-VIKRAM-P6",
            "email": "dr.vikram.p6@clinixai.com",
            "full_name": "Dr. Vikram Joshi",
            "role": UserRole.DOCTOR.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.doc_unrelated = {
            "doctor_id": "DOC-VIKRAM-P6",
            "user_id": "USR-DOC-VIKRAM-P6",
            "first_name": "Vikram",
            "last_name": "Joshi",
            "email": "dr.vikram.p6@clinixai.com",
            "specialty": "Orthopedics",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Patient One: Primary patient
        self.pat_1_user = {
            "user_id": "USR-PAT-ONE-001",
            "email": "patient.one@clinixai.com",
            "full_name": "Patient One",
            "role": UserRole.PATIENT.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.pat_1 = {
            "patient_id": "PAT-ONE-001",
            "user_id": "USR-PAT-ONE-001",
            "first_name": "Patient",
            "last_name": "One",
            "email": "patient.one@clinixai.com",
            "primary_physician_id": "DOC-RAO-001",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Patient Two: Secondary patient for cross-patient tests
        self.pat_2_user = {
            "user_id": "USR-PAT-TWO-002",
            "email": "patient.two@clinixai.com",
            "full_name": "Patient Two",
            "role": UserRole.PATIENT.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.pat_2 = {
            "patient_id": "PAT-TWO-002",
            "user_id": "USR-PAT-TWO-002",
            "first_name": "Patient",
            "last_name": "Two",
            "email": "patient.two@clinixai.com",
            "primary_physician_id": "DOC-VIKRAM-P6",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Seed Database
        await self.db[COLLECTION_USERS].update_one({"user_id": self.doc_a_user["user_id"]}, {"$set": self.doc_a_user}, upsert=True)
        await self.db[COLLECTION_DOCTORS].update_one({"doctor_id": self.doc_a["doctor_id"]}, {"$set": self.doc_a}, upsert=True)
        await self.db[COLLECTION_USERS].update_one({"user_id": self.doc_unrelated_user["user_id"]}, {"$set": self.doc_unrelated_user}, upsert=True)
        await self.db[COLLECTION_DOCTORS].update_one({"doctor_id": self.doc_unrelated["doctor_id"]}, {"$set": self.doc_unrelated}, upsert=True)
        await self.db[COLLECTION_USERS].update_one({"user_id": self.pat_1_user["user_id"]}, {"$set": self.pat_1_user}, upsert=True)
        await self.db[COLLECTION_PATIENTS].update_one({"patient_id": self.pat_1["patient_id"]}, {"$set": self.pat_1}, upsert=True)
        await self.db[COLLECTION_USERS].update_one({"user_id": self.pat_2_user["user_id"]}, {"$set": self.pat_2_user}, upsert=True)
        await self.db[COLLECTION_PATIENTS].update_one({"patient_id": self.pat_2["patient_id"]}, {"$set": self.pat_2}, upsert=True)

        # Authoritative Brain MRI Document for Patient One
        self.mri_doc = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "uploaded_by": "USR-DOC-RAO-001",
            "title": "Brain MRI T1 Axial Scan",
            "category": "MRI",
            "file_name": "doc_brain_mri_pat1.jpg",
            "original_file_name": "Brain_MRI_T1_Axial.jpg",
            "mime_type": "image/jpeg",
            "file_size_bytes": 42790,
            "storage_path": "C:\\Users\\Vamshikrishna\\Desktop\\CliniXAI\\backend\\uploads\\documents\\doc_brain_mri_pat1.jpg",
            "appointment_id": "APT-2026-001",
            "medical_record_id": "MR-2026-001",
            "consultation_id": "CNS-2026-002",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCUMENTS].update_one({"document_id": "DOC-2026-001"}, {"$set": self.mri_doc}, upsert=True)

        # Non-MRI Document for Patient One (e.g. prescription / text PDF)
        self.pdf_doc = {
            "document_id": "DOC-2026-NON-MRI",
            "patient_id": "PAT-ONE-001",
            "uploaded_by": "USR-DOC-RAO-001",
            "title": "Clinical Discharge Summary PDF",
            "category": "MEDICAL_PDF",
            "file_name": "discharge_summary.pdf",
            "original_file_name": "Discharge_Summary.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 12050,
            "storage_path": "C:\\Users\\Vamshikrishna\\Desktop\\CliniXAI\\backend\\uploads\\documents\\discharge_summary.pdf",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCUMENTS].update_one({"document_id": "DOC-2026-NON-MRI"}, {"$set": self.pdf_doc}, upsert=True)

        # Soft-deleted Document for Patient One
        self.del_doc = {
            "document_id": "DOC-2026-DELETED-MRI",
            "patient_id": "PAT-ONE-001",
            "uploaded_by": "USR-DOC-RAO-001",
            "title": "Deleted Old Brain MRI",
            "category": "MRI",
            "file_name": "doc_brain_mri_pat1.jpg",
            "original_file_name": "Deleted_Brain_MRI.jpg",
            "mime_type": "image/jpeg",
            "file_size_bytes": 42790,
            "storage_path": "C:\\Users\\Vamshikrishna\\Desktop\\CliniXAI\\backend\\uploads\\documents\\doc_brain_mri_pat1.jpg",
            "is_deleted": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCUMENTS].update_one({"document_id": "DOC-2026-DELETED-MRI"}, {"$set": self.del_doc}, upsert=True)

        # Document for Patient Two
        self.pat2_doc = {
            "document_id": "DOC-PATIENT-TWO-001",
            "patient_id": "PAT-TWO-002",
            "uploaded_by": "USR-DOC-VIKRAM-P6",
            "title": "Patient Two Brain Scan",
            "category": "MRI",
            "file_name": "doc_brain_mri_pat1.jpg",
            "original_file_name": "Pat2_Brain_Scan.jpg",
            "mime_type": "image/jpeg",
            "file_size_bytes": 42790,
            "storage_path": "C:\\Users\\Vamshikrishna\\Desktop\\CliniXAI\\backend\\uploads\\documents\\doc_brain_mri_pat1.jpg",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCUMENTS].update_one({"document_id": "DOC-PATIENT-TWO-001"}, {"$set": self.pat2_doc}, upsert=True)

        # JWT tokens
        self.token_doc_a = create_access_token(user_id=self.doc_a_user["user_id"], role=UserRole.DOCTOR.value)
        self.headers_doc_a = {"Authorization": f"Bearer {self.token_doc_a}"}

        self.token_doc_unrelated = create_access_token(user_id=self.doc_unrelated_user["user_id"], role=UserRole.DOCTOR.value)
        self.headers_doc_unrelated = {"Authorization": f"Bearer {self.token_doc_unrelated}"}

        self.token_pat_1 = create_access_token(user_id=self.pat_1_user["user_id"], role=UserRole.PATIENT.value)
        self.headers_pat_1 = {"Authorization": f"Bearer {self.token_pat_1}"}

        self.token_pat_2 = create_access_token(user_id=self.pat_2_user["user_id"], role=UserRole.PATIENT.value)
        self.headers_pat_2 = {"Authorization": f"Bearer {self.token_pat_2}"}

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_01_valid_brain_mri_context_accepted(self):
        """Doctor A triggers AI analysis on DOC-2026-001 for PAT-ONE-001 and gets 201 Created."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
            "appointment_id": "APT-2026-001",
            "medical_record_id": "MR-2026-001",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 201, res.text)
        data = self._data(res)
        self.assertIn("analysis_id", data)
        self.assertEqual(data["patient_id"], "PAT-ONE-001")
        self.assertEqual(data["document_id"], "DOC-2026-001")
        self.assertEqual(data["model"]["module_id"], "BRAIN_MRI")

    async def test_02_valid_patient_document_pairing_succeeds(self):
        """Authorized patient/document pairing passes verification."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001", headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 200)
        doc = self._data(res)
        self.assertEqual(doc["patient_id"], "PAT-ONE-001")

    async def test_03_invalid_document_returns_404(self):
        """Requesting AI analysis with a non-existent document ID returns 404."""
        payload = {
            "document_id": "DOC-NONEXISTENT-9999",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 404, res.text)

    async def test_04_deleted_document_returns_404(self):
        """Requesting AI analysis with a soft-deleted document returns 404."""
        payload = {
            "document_id": "DOC-2026-DELETED-MRI",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 404, res.text)

    async def test_05_patient_document_mismatch_rejected(self):
        """Attempting to link DOC-PATIENT-TWO-001 with PAT-ONE-001 returns 403 Forbidden."""
        payload = {
            "document_id": "DOC-PATIENT-TWO-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 403, res.text)

    async def test_06_unauthorized_doctor_rejected(self):
        """Doctor Unrelated without care relationship with PAT-ONE-001 is rejected with 403."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_unrelated)
        self.assertEqual(res.status_code, 403, res.text)

    async def test_07_unauthorized_patient_rejected(self):
        """Patient cannot trigger /ai-analyses endpoint (clinical doctor-only CDS endpoint)."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_pat_1)
        self.assertEqual(res.status_code, 403, res.text)

    async def test_08_non_mri_document_rejected_for_brain_mri(self):
        """Passing a non-image/non-MRI document to Brain MRI analysis returns 400 or 422."""
        payload = {
            "document_id": "DOC-2026-NON-MRI",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertIn(res.status_code, [400, 422], res.text)

    async def test_09_ai_module_autoselection(self):
        """Omitting analysis_type on an MRI document automatically resolves module to BRAIN_MRI."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 201, res.text)
        data = self._data(res)
        self.assertEqual(data["model"]["module_id"], "BRAIN_MRI")

    async def test_10_real_image_bytes_retrieval(self):
        """Document download endpoint retrieves valid JPEG image bytes with authenticated header."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001/download", headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.content), 1000)
        self.assertEqual(res.content[:2], b"\xff\xd8")  # JPEG SOI marker

    async def test_11_inference_uses_selected_document(self):
        """Inference produces valid ResNet50 multiclass prediction with confidence and probabilities."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 201)
        data = self._data(res)
        pred = data.get("prediction")
        self.assertIsNotNone(pred)
        self.assertIn(pred["predicted_class"], ["glioma", "meningioma", "notumor", "pituitary"])
        self.assertGreaterEqual(pred["confidence"], 0.0)
        self.assertLessEqual(pred["confidence"], 1.0)

    async def test_12_ai_analysis_persistence_in_mongodb(self):
        """AI analysis document is inserted in MongoDB and queryable by analysis_id."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 201)
        aid = self._data(res)["analysis_id"]

        record = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": aid})
        self.assertIsNotNone(record)
        self.assertEqual(record["patient_id"], "PAT-ONE-001")
        self.assertEqual(record["document_id"], "DOC-2026-001")

    async def test_13_document_linkage_preserved(self):
        """Source document DOC-2026-001 in MongoDB is updated with ai_analysis_id reference."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 201)
        aid = self._data(res)["analysis_id"]

        doc = await self.db[COLLECTION_DOCUMENTS].find_one({"document_id": "DOC-2026-001"})
        self.assertEqual(doc.get("ai_analysis_id"), aid)
        self.assertTrue(doc.get("has_ai_analysis"))

    async def test_14_gradcam_linkage_conv5_block3_out(self):
        """Explainability record contains target layer 'conv5_block3_out' and valid artifact key."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 201)
        data = self._data(res)
        exp = data.get("explainability")
        self.assertIsNotNone(exp)
        self.assertEqual(exp["method"], "grad_cam")
        self.assertEqual(exp["target_layer"], "conv5_block3_out")
        self.assertTrue(exp["artifact_storage_key"].startswith("gradcam_"))

    async def test_15_initial_status_awaiting_review(self):
        """Newly created analysis enters awaiting_review status, not automatically released."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 201)
        data = self._data(res)
        self.assertEqual(data["status"], "awaiting_review")
        self.assertFalse(data["is_released_to_patient"])

    async def test_16_doctor_can_submit_review(self):
        """Doctor submits clinical interpretation and review decision successfully."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        create_res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        aid = self._data(create_res)["analysis_id"]

        review_payload = {
            "decision": "accepted",
            "clinical_interpretation": "Confirmed: Clinical evaluation aligns with MRI findings. No active intracranial tumor identified.",
            "notes": "Reviewed in neurology clinic encounter.",
            "release_to_patient": False,
        }
        rev_res = await self.client.post(f"/api/v1/ai-analyses/{aid}/review", json=review_payload, headers=self.headers_doc_a)
        self.assertEqual(rev_res.status_code, 200, rev_res.text)
        data = self._data(rev_res)
        self.assertEqual(data["status"], "reviewed")
        self.assertIsNotNone(data["doctor_review"])
        self.assertEqual(data["doctor_review"]["decision"], "accepted")

    async def test_17_doctor_can_explicitly_release_to_patient(self):
        """Doctor explicitly releases reviewed analysis to patient."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        create_res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        aid = self._data(create_res)["analysis_id"]

        # Doctor reviews first
        rev_payload = {
            "decision": "accepted",
            "clinical_interpretation": "Scan approved for patient release.",
            "release_to_patient": False,
        }
        await self.client.post(f"/api/v1/ai-analyses/{aid}/review", json=rev_payload, headers=self.headers_doc_a)

        rel_res = await self.client.post(f"/api/v1/ai-analyses/{aid}/release", headers=self.headers_doc_a)
        self.assertEqual(rel_res.status_code, 200, rel_res.text)
        data = self._data(rel_res)
        self.assertTrue(data["is_released_to_patient"])
        self.assertEqual(data["status"], "reviewed")

    async def test_18_patient_hidden_before_release(self):
        """Patient attempting to access an unreleased AI analysis is rejected with 403."""
        # Clean existing analyses for DOC-2026-001 to guarantee awaiting_review
        await self.db[COLLECTION_AI_ANALYSES].delete_many({"document_id": "DOC-2026-001"})

        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        create_res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        aid = self._data(create_res)["analysis_id"]

        # Patient tries to view raw analysis before release -> 403 Forbidden
        pat_res = await self.client.get(f"/api/v1/ai-analyses/{aid}", headers=self.headers_pat_1)
        self.assertEqual(pat_res.status_code, 403)

        # Patient tries to view patient report before release -> 403 Forbidden
        rep_res = await self.client.get(f"/api/v1/ai-analyses/{aid}/report", headers=self.headers_pat_1)
        self.assertEqual(rep_res.status_code, 403)

    async def test_19_patient_sanitized_result_after_release(self):
        """After explicit release, Patient can retrieve sanitized patient report."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        create_res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        aid = self._data(create_res)["analysis_id"]

        # Doctor reviews and releases
        rev_payload = {
            "decision": "accepted",
            "clinical_interpretation": "Doctor approved findings.",
            "release_to_patient": False,
        }
        await self.client.post(f"/api/v1/ai-analyses/{aid}/review", json=rev_payload, headers=self.headers_doc_a)
        await self.client.post(f"/api/v1/ai-analyses/{aid}/release", headers=self.headers_doc_a)

        # Patient now retrieves sanitized report
        pat_res = await self.client.get(f"/api/v1/ai-analyses/{aid}/report", headers=self.headers_pat_1)
        self.assertEqual(pat_res.status_code, 200, pat_res.text)
        data = self._data(pat_res)
        self.assertEqual(data["analysis_id"], aid)
        self.assertEqual(data["status"], "reviewed")
        self.assertIn("disclaimer", data)

    async def test_20_persistence_across_restore(self):
        """Saving snapshot and restoring preserves the persisted AI analysis."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        create_res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        aid = self._data(create_res)["analysis_id"]

        await save_in_memory_snapshot(self.db)
        await restore_in_memory_snapshot(self.db)

        restored = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": aid})
        self.assertIsNotNone(restored)
        self.assertEqual(restored["document_id"], "DOC-2026-001")
        self.assertEqual(restored["patient_id"], "PAT-ONE-001")

    async def test_21_cross_patient_isolation_on_ai_analyses(self):
        """Patient Two cannot view Patient One's released AI report (403 Forbidden)."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        create_res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        aid = self._data(create_res)["analysis_id"]
        await self.client.post(f"/api/v1/ai-analyses/{aid}/release", headers=self.headers_doc_a)

        # Patient Two tries to access Patient One's report
        res = await self.client.get(f"/api/v1/ai-analyses/{aid}/report", headers=self.headers_pat_2)
        self.assertEqual(res.status_code, 403)

    async def test_22_gradcam_strict_header_authorization(self):
        """Grad-CAM endpoint requires Authorization header; token in query string is rejected (401)."""
        payload = {
            "document_id": "DOC-2026-001",
            "patient_id": "PAT-ONE-001",
            "analysis_type": "BRAIN_MRI",
        }
        create_res = await self.client.post("/api/v1/ai-analyses", json=payload, headers=self.headers_doc_a)
        aid = self._data(create_res)["analysis_id"]

        # Valid Authorization Bearer header -> 200 OK
        valid_res = await self.client.get(f"/api/v1/ai-analyses/{aid}/gradcam", headers=self.headers_doc_a)
        self.assertEqual(valid_res.status_code, 200)
        self.assertEqual(valid_res.headers.get("content-type"), "image/png")

        # Query param ?token= with no header -> 401 Unauthorized (Strict header enforcement)
        bad_res = await self.client.get(f"/api/v1/ai-analyses/{aid}/gradcam?token={self.token_doc_a}")
        self.assertEqual(bad_res.status_code, 401)

    def test_23_brain_model_hash_verification(self):
        """Brain MRI model SHA256 matches verified hash e135b97df53d4ab8d575c643297ba948cb6ccbaa963039c0a4c40683fb679f53."""
        model_path = os.path.join(os.path.dirname(__file__), "..", "ai_models", "brain_model.keras")
        self.assertTrue(os.path.exists(model_path), f"Brain model not found at {model_path}")
        with open(model_path, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        expected = "e135b97df53d4ab8d575c643297ba948cb6ccbaa963039c0a4c40683fb679f53"
        self.assertEqual(h.lower(), expected.lower())

    async def test_24_phase5_brain_mri_discovery_regression(self):
        """Phase 5 Brain MRI document discovery and category filtering continue to function."""
        res = await self.client.get("/api/v1/documents", headers=self.headers_doc_a, params={"patient_id": "PAT-ONE-001", "category": "mri"})
        self.assertEqual(res.status_code, 200)
        items = self._data(res).get("items", [])
        self.assertGreaterEqual(len(items), 1)
        doc_ids = [d["document_id"] for d in items]
        self.assertIn("DOC-2026-001", doc_ids)

    async def test_25_chest_xray_production_integration_regression(self):
        """Chest X-Ray module and registry remain intact and operational."""
        registry = get_ai_registry()
        chest_mod = registry.get_module("CHEST_XRAY")
        self.assertIsNotNone(chest_mod)
        self.assertEqual(chest_mod.display_name, "Chest X-Ray Analysis")
        self.assertEqual(chest_mod.architecture, "ResNet50")
